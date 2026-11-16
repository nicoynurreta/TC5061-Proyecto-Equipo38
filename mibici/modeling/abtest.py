import argparse
import json
import os
import time
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from scipy import stats

from mibici import config, features
from mibici.modeling import train
from mibici.modeling.registry import NOMBRES
from mibici.monitoreo import costos, datos
from mibici.monitoreo.formato import decimal, numero, porcentaje, tabla_markdown

PREGUNTA = "p2"
ENTREGA = "5"
CONFIANZA = 0.95
NIVEL = f"{CONFIANZA * 100:.0f} %"
REPLICAS = 2000
MARGEN_RECALL = 0.01
PROPORCION_B = 0.5
EXACTA_HASTA = 25
CON_INTERVALO = ["recall", "precision", "f1", "costo_por_mil"]
REGLA = (
    "La versión B se promueve a champion solo si, sobre el conjunto de evaluación, se cumplen las dos condiciones: "
    f"(1) el intervalo de confianza de {NIVEL} de la diferencia de costo por mil horas-estación (B menos A), "
    "calculado por bootstrap de bloques de un día sobre la comparación pareada, queda completo por debajo de cero; y "
    f"(2) el límite inferior del intervalo de {NIVEL} de la diferencia de recall (B menos A) no baja de -{MARGEN_RECALL}. "
    "Si alguna falla, el alias champion no se mueve y la versión B conserva el alias challenger."
)
FUENTE = "mibici/modeling/abtest.py"
ARCHIVO_JSON = config.DIR_MONITOREO / "abtest.json"
ARCHIVO_REPORTE = config.DIR_MONITOREO / "abtest.md"
FIGURA = config.DIR_FIGURAS / "abtest_costo.png"
NOMBRES_METRICAS = [("recall", "Recall"), ("precision", "Precisión"), ("f1", "F1"), ("pr_auc", "PR-AUC"), ("alertas", "Alertas"),
                    ("falsos_positivos", "Falsos positivos"), ("falsos_negativos", "Falsos negativos"), ("costo", "Costo"),
                    ("costo_por_mil", "Costo por mil horas-estación"), ("costo_relativo", "Costo frente a no alertar")]
ENTERAS = ["alertas", "falsos_positivos", "falsos_negativos", "costo"]
NOMBRES_CONJUNTOS = {"evaluacion": "Evaluación", "confirmacion": "Confirmación"}


def conteos_por_dia(real, alerta, codigos, dias):
    """Filas, aciertos, falsos positivos y falsos negativos de cada día, que es el bloque del bootstrap."""
    real, alerta = np.asarray(real).astype(bool), np.asarray(alerta).astype(bool)
    return {
        "filas": np.bincount(codigos, minlength=dias).astype(float),
        "aciertos": np.bincount(codigos, weights=real & alerta, minlength=dias),
        "falsos_positivos": np.bincount(codigos, weights=~real & alerta, minlength=dias),
        "falsos_negativos": np.bincount(codigos, weights=real & ~alerta, minlength=dias),
    }


def metricas_de_sumas(sumas, costo_falso_negativo=config.COSTO_FALSO_NEGATIVO):
    """Recall, precisión, F1 y costo por mil horas-estación a partir de las sumas de conteos de cada réplica."""
    aciertos, falsos_positivos, falsos_negativos = sumas["aciertos"], sumas["falsos_positivos"], sumas["falsos_negativos"]
    positivos, alertas = aciertos + falsos_negativos, aciertos + falsos_positivos
    recall = np.divide(aciertos, positivos, out=np.zeros_like(aciertos, dtype=float), where=positivos > 0)
    precision = np.divide(aciertos, alertas, out=np.zeros_like(aciertos, dtype=float), where=alertas > 0)
    suma = precision + recall
    f1 = np.divide(2 * precision * recall, suma, out=np.zeros_like(suma, dtype=float), where=suma > 0)
    costo = np.divide(1000 * (falsos_positivos + costo_falso_negativo * falsos_negativos), sumas["filas"],
                      out=np.zeros_like(aciertos, dtype=float), where=sumas["filas"] > 0)
    return {"recall": recall, "precision": precision, "f1": f1, "costo_por_mil": costo}


def resta(de_b, de_a):
    """Diferencia B menos A de cada métrica de la tabla comparativa; sin valor cuando alguna versión no la tiene."""
    return {metrica: None if de_a.get(metrica) is None or de_b.get(metrica) is None else de_b[metrica] - de_a[metrica]
            for metrica, _ in NOMBRES_METRICAS}


def bootstrap_por_dia(conteos_a, conteos_b, replicas=REPLICAS, semilla=config.SEMILLA, confianza=CONFIANZA):
    """Intervalos de la diferencia B menos A remuestreando días completos; los dos brazos usan los mismos días en cada réplica."""
    rng = np.random.default_rng(semilla)
    dias = len(conteos_a["filas"])
    indices = rng.integers(0, dias, (replicas, dias))
    de_a = metricas_de_sumas({clave: valores[indices].sum(axis=1) for clave, valores in conteos_a.items()})
    de_b = metricas_de_sumas({clave: valores[indices].sum(axis=1) for clave, valores in conteos_b.items()})
    cola = (1 - confianza) / 2
    diferencias = {metrica: de_b[metrica] - de_a[metrica] for metrica in CON_INTERVALO}
    intervalos = {metrica: {"inferior": float(np.quantile(valores, cola)), "superior": float(np.quantile(valores, 1 - cola))}
                  for metrica, valores in diferencias.items()}
    return intervalos, diferencias


def mcnemar(acierta_a, acierta_b):
    """Prueba de McNemar sobre los pares discordantes: exacta con pocos pares y con corrección de continuidad en otro caso."""
    acierta_a, acierta_b = np.asarray(acierta_a).astype(bool), np.asarray(acierta_b).astype(bool)
    solo_a = int(np.sum(acierta_a & ~acierta_b))
    solo_b = int(np.sum(~acierta_a & acierta_b))
    discordantes = solo_a + solo_b
    if discordantes == 0:
        return {"solo_acierta_a": 0, "solo_acierta_b": 0, "estadistico": 0.0, "p_valor": 1.0, "prueba": "sin pares discordantes"}
    if discordantes < EXACTA_HASTA:
        p_valor = float(stats.binomtest(min(solo_a, solo_b), discordantes, 0.5).pvalue)
        return {"solo_acierta_a": solo_a, "solo_acierta_b": solo_b, "estadistico": float(min(solo_a, solo_b)), "p_valor": p_valor,
                "prueba": "binomial exacta"}
    estadistico = (abs(solo_a - solo_b) - 1) ** 2 / discordantes
    return {"solo_acierta_a": solo_a, "solo_acierta_b": solo_b, "estadistico": float(estadistico),
            "p_valor": float(stats.chi2.sf(estadistico, 1)), "prueba": "ji cuadrada con corrección de continuidad"}


def comparar(real, salidas_a, salidas_b, dia, replicas=REPLICAS, semilla=config.SEMILLA):
    """Comparación pareada de dos versiones sobre las mismas horas-estación: métricas, diferencias, intervalos y McNemar."""
    real = np.asarray(real).astype(bool)
    (alerta_a, probabilidad_a), (alerta_b, probabilidad_b) = salidas_a, salidas_b
    alerta_a, alerta_b = np.asarray(alerta_a).astype(bool), np.asarray(alerta_b).astype(bool)
    codigos, dias = pd.factorize(np.asarray(dia), sort=True)
    de_a, de_b = costos.metricas(real, alerta_a, probabilidad_a), costos.metricas(real, alerta_b, probabilidad_b)
    intervalos, diferencias = bootstrap_por_dia(conteos_por_dia(real, alerta_a, codigos, len(dias)),
                                                conteos_por_dia(real, alerta_b, codigos, len(dias)), replicas, semilla)
    acierta_a, acierta_b = alerta_a == real, alerta_b == real
    resultado = {
        "filas": int(len(real)),
        "dias": int(len(dias)),
        "positivos": int(real.sum()),
        "a": de_a,
        "b": de_b,
        "diferencia": resta(de_b, de_a),
        "intervalos": intervalos,
        "coinciden": float(np.mean(alerta_a == alerta_b)),
        "mcnemar": {"todas": mcnemar(acierta_a, acierta_b), "en_riesgo": mcnemar(acierta_a[real], acierta_b[real]),
                    "sin_riesgo": mcnemar(acierta_a[~real], acierta_b[~real])},
    }
    return resultado, diferencias


def trafico_dividido(real, alerta_a, alerta_b, dia, proporcion=PROPORCION_B, replicas=REPLICAS, semilla=config.SEMILLA):
    """Simula el experimento en producción: cada hora-estación se atiende al azar con A o con B y solo se observa ese brazo."""
    real = np.asarray(real).astype(bool)
    alerta_a, alerta_b = np.asarray(alerta_a).astype(bool), np.asarray(alerta_b).astype(bool)
    rng = np.random.default_rng(semilla)
    con_b = rng.random(len(real)) < proporcion
    codigos, dias = pd.factorize(np.asarray(dia), sort=True)
    de_a, de_b = costos.metricas(real[~con_b], alerta_a[~con_b]), costos.metricas(real[con_b], alerta_b[con_b])
    intervalos, _ = bootstrap_por_dia(conteos_por_dia(real[~con_b], alerta_a[~con_b], codigos[~con_b], len(dias)),
                                      conteos_por_dia(real[con_b], alerta_b[con_b], codigos[con_b], len(dias)), replicas, semilla)
    return {"proporcion_b": proporcion, "semilla": semilla, "a": de_a, "b": de_b,
            "diferencia": {metrica: de_b[metrica] - de_a[metrica] for metrica in CON_INTERVALO}, "intervalos": intervalos}


def umbral_para_recall(real, probabilidad, recall):
    """Mayor umbral con que unas probabilidades alcanzan al menos el recall indicado."""
    de_positivos = np.sort(np.asarray(probabilidad)[np.asarray(real).astype(bool)])[::-1]
    necesarios = min(max(int(np.ceil(recall * len(de_positivos))), 1), len(de_positivos))
    return float(de_positivos[necesarios - 1])


def decidir(comparacion, margen=MARGEN_RECALL):
    """Aplica la regla de decisión de REGLA a la comparación pareada del conjunto de evaluación."""
    condiciones = {"costo_menor": bool(comparacion["intervalos"]["costo_por_mil"]["superior"] < 0),
                   "recall_no_inferior": bool(comparacion["intervalos"]["recall"]["inferior"] >= -margen)}
    return {**condiciones, "promover": all(condiciones.values())}


def predecir(modelo, parte):
    entradas = parte[features.COLUMNAS_P2]
    return np.asarray(modelo.predict(entradas)).astype(bool), modelo.predict_proba(entradas)[:, 1]


def evaluar(tabla, modelo_a, modelo_b, replicas=REPLICAS, semilla=config.SEMILLA):
    """Compara las dos versiones en el conjunto de evaluación, simula el tráfico dividido, aplica la regla y repite la comparación en la confirmación.

    Después de la regla deja un análisis aparte: la misma comparación con el umbral con que B
    alcanza el recall de A en la evaluación, para distinguir lo que aporta el reentrenamiento de
    lo que cambia el umbral. Ese umbral se elige con las etiquetas de la evaluación, así que solo
    su resultado en la confirmación es fuera de muestra.
    """
    resultado, diferencias = {"por_mes": []}, None
    for conjunto in ("evaluacion", "confirmacion"):
        parte = tabla[tabla["conjunto"] == conjunto]
        if parte.empty:
            continue
        real = parte[features.OBJETIVO_P2].to_numpy().astype(bool)
        salidas_a, salidas_b = predecir(modelo_a, parte), predecir(modelo_b, parte)
        dia = parte["hora"].dt.normalize().to_numpy()
        resultado[conjunto], muestras = comparar(real, salidas_a, salidas_b, dia, replicas, semilla)
        meses = parte["hora"].dt.to_period("M").astype(str).to_numpy()
        for mes in sorted(set(meses)):
            filtro = meses == mes
            resultado["por_mes"].append({"mes": mes, "conjunto": conjunto, "a": costos.metricas(real[filtro], salidas_a[0][filtro]),
                                         "b": costos.metricas(real[filtro], salidas_b[0][filtro])})
        if conjunto == "evaluacion":
            diferencias = muestras
            resultado["trafico"] = trafico_dividido(real, salidas_a[0], salidas_b[0], dia, PROPORCION_B, replicas, semilla)
            resultado["a_igual_recall"] = {"umbral_b": umbral_para_recall(real, salidas_b[1], resultado[conjunto]["a"]["recall"])}
        if "a_igual_recall" in resultado:
            ajustada = (salidas_b[1] >= resultado["a_igual_recall"]["umbral_b"], salidas_b[1])
            resultado["a_igual_recall"][conjunto], _ = comparar(real, salidas_a, ajustada, dia, replicas, semilla)
    if "evaluacion" not in resultado:
        raise SystemExit("la tabla de monitoreo no tiene filas en el conjunto de evaluación")
    resultado["decision"] = decidir(resultado["evaluacion"])
    return resultado, diferencias


def cargar_version(cliente, nombre, version, alias):
    """Carga una versión de P2 por número o, si no se indica, por alias; devuelve el modelo y su registro."""
    try:
        registrada = cliente.get_model_version(nombre, version) if version else cliente.get_model_version_by_alias(nombre, alias)
    except MlflowException as error:
        raise SystemExit(f"no se encontró la versión de {nombre} ({version or alias}): {error}")
    uri = f"models:/{nombre}/{registrada.version}"
    return mlflow.sklearn.load_model(uri), registrada


def describir_version(registrada, modelo, alias):
    return {"version": str(registrada.version), "alias": alias, "run_id": registrada.run_id, "corrida": registrada.tags.get("corrida", ""),
            "umbral": float(getattr(modelo, "threshold", 0.5)), "version_datos": registrada.tags.get("version_datos", ""),
            "periodo_entrenamiento": registrada.tags.get("periodo_entrenamiento", f"{config.FECHA_INICIO} a {config.FIN_ENTRENAMIENTO}"),
            "commit_git": registrada.tags.get("commit_git", "")[:7]}


def grafica_abtest(por_mes, diferencias, intervalo, versiones, ruta):
    """Costo por mil horas-estación de cada versión por mes y distribución por bootstrap de la diferencia en la evaluación."""
    figura, ejes = plt.subplots(1, 2, figsize=(13, 4.6))
    posiciones = np.arange(len(por_mes))
    ejes[0].bar(posiciones - 0.2, [fila["a"]["costo_por_mil"] for fila in por_mes], width=0.4, color="steelblue",
                label=f"A, versión {versiones['a']['version']}")
    ejes[0].bar(posiciones + 0.2, [fila["b"]["costo_por_mil"] for fila in por_mes], width=0.4, color="crimson",
                label=f"B, versión {versiones['b']['version']}")
    ejes[0].set_xticks(posiciones)
    ejes[0].set_xticklabels([f"{fila['mes']}\n{NOMBRES_CONJUNTOS[fila['conjunto']]}" for fila in por_mes], fontsize=8)
    ejes[0].set_ylabel("Costo por mil horas-estación")
    ejes[0].set_title("Costo de los errores por mes")
    ejes[0].legend(fontsize=8)
    ejes[0].grid(axis="y", alpha=0.3)
    ejes[1].hist(diferencias, bins=50, color="steelblue", alpha=0.85)
    ejes[1].axvline(0, color="black", linewidth=1, label="Sin diferencia")
    ejes[1].axvline(intervalo["inferior"], color="crimson", linestyle="--", linewidth=1,
                    label=f"IC de {NIVEL}: {intervalo['inferior']:.2f} a {intervalo['superior']:.2f}")
    ejes[1].axvline(intervalo["superior"], color="crimson", linestyle="--", linewidth=1)
    ejes[1].set_xlabel("Diferencia de costo por mil horas-estación (B menos A)")
    ejes[1].set_ylabel("Réplicas del bootstrap")
    ejes[1].set_title("Diferencia de costo en el conjunto de evaluación")
    ejes[1].legend(fontsize=8)
    ejes[1].grid(axis="y", alpha=0.3)
    figura.tight_layout()
    figura.savefig(ruta, dpi=150)
    plt.close(figura)
    return ruta


def celda(metrica, valor):
    if valor is None:
        return "n. a."
    return numero(valor) if metrica in ENTERAS else decimal(valor, 2 if metrica == "costo_por_mil" else 4)


def filas_comparativas(comparacion):
    filas = []
    for metrica, titulo in NOMBRES_METRICAS:
        diferencia = comparacion["diferencia"][metrica]
        decimales = 2 if metrica == "costo_por_mil" else 4
        if diferencia is None:
            texto = "n. a."
        else:
            texto = f"{diferencia:+,.0f}" if metrica in ENTERAS else f"{diferencia:+.{decimales}f}"
        intervalo = comparacion["intervalos"].get(metrica)
        rango = f"{intervalo['inferior']:+.{decimales}f} a {intervalo['superior']:+.{decimales}f}" if intervalo else ""
        filas.append((titulo, celda(metrica, comparacion["a"][metrica]), celda(metrica, comparacion["b"][metrica]), texto, rango))
    return filas


def filas_mcnemar(comparacion):
    nombres = [("todas", "Todas las horas-estación (acierto de la clase)"), ("en_riesgo", "Horas en riesgo (recall)"),
               ("sin_riesgo", "Horas sin riesgo (falsas alertas)")]
    return [(titulo, numero(comparacion["mcnemar"][clave]["solo_acierta_a"]), numero(comparacion["mcnemar"][clave]["solo_acierta_b"]),
             comparacion["mcnemar"][clave]["prueba"], decimal(comparacion["mcnemar"][clave]["estadistico"], 2),
             valor_p(comparacion["mcnemar"][clave]["p_valor"])) for clave, titulo in nombres]


def valor_p(valor):
    return "menor que 0.001" if valor < 0.001 else f"{valor:.3f}"


def filas_a_igual_recall(resultado):
    filas = []
    for conjunto in ("evaluacion", "confirmacion"):
        comparacion = resultado["a_igual_recall"].get(conjunto)
        if comparacion is None:
            continue
        costo = comparacion["intervalos"]["costo_por_mil"]
        filas.append((NOMBRES_CONJUNTOS[conjunto], decimal(comparacion["a"]["recall"], 4), decimal(comparacion["b"]["recall"], 4),
                      decimal(comparacion["a"]["precision"], 4), decimal(comparacion["b"]["precision"], 4),
                      numero(comparacion["a"]["alertas"]), numero(comparacion["b"]["alertas"]),
                      decimal(comparacion["a"]["costo_por_mil"], 2), decimal(comparacion["b"]["costo_por_mil"], 2),
                      f"{comparacion['diferencia']['costo_por_mil']:+.2f} ({costo['inferior']:+.2f} a {costo['superior']:+.2f})"))
    return filas


def escribir_reporte(resultado, ruta=ARCHIVO_REPORTE):
    """Escribe el reporte del A/B en Markdown: versiones, regla, tabla comparativa, McNemar, tráfico dividido, meses y decisión."""
    versiones, evaluacion, trafico, decision = resultado["versiones"], resultado["evaluacion"], resultado["trafico"], resultado["decision"]
    inicio, fin = resultado["ventanas"]["evaluacion"]
    a, b = versiones["a"], versiones["b"]
    encabezado = ["Métrica", f"A, versión {a['version']}", f"B, versión {b['version']}", "B menos A", f"IC de {NIVEL} de B menos A"]
    brazos = [(f"A, versión {a['version']}", numero(trafico["a"]["filas"]), numero(trafico["a"]["positivos"]), decimal(trafico["a"]["recall"], 4),
               decimal(trafico["a"]["precision"], 4), decimal(trafico["a"]["costo_por_mil"], 2)),
              (f"B, versión {b['version']}", numero(trafico["b"]["filas"]), numero(trafico["b"]["positivos"]), decimal(trafico["b"]["recall"], 4),
               decimal(trafico["b"]["precision"], 4), decimal(trafico["b"]["costo_por_mil"], 2)),
              ("B menos A", "", "", f"{trafico['diferencia']['recall']:+.4f} ({trafico['intervalos']['recall']['inferior']:+.4f} a {trafico['intervalos']['recall']['superior']:+.4f})",
               f"{trafico['diferencia']['precision']:+.4f} ({trafico['intervalos']['precision']['inferior']:+.4f} a {trafico['intervalos']['precision']['superior']:+.4f})",
               f"{trafico['diferencia']['costo_por_mil']:+.2f} ({trafico['intervalos']['costo_por_mil']['inferior']:+.2f} a {trafico['intervalos']['costo_por_mil']['superior']:+.2f})")]
    meses = [(fila["mes"], NOMBRES_CONJUNTOS[fila["conjunto"]], numero(fila["a"]["filas"]), numero(fila["a"]["positivos"]), decimal(fila["a"]["recall"], 4),
              decimal(fila["b"]["recall"], 4), decimal(fila["a"]["precision"], 4), decimal(fila["b"]["precision"], 4),
              decimal(fila["a"]["costo_por_mil"], 2), decimal(fila["b"]["costo_por_mil"], 2),
              f"{fila['b']['costo_por_mil'] - fila['a']['costo_por_mil']:+.2f}") for fila in resultado["por_mes"]]
    costo, recall = evaluacion["intervalos"]["costo_por_mil"], evaluacion["intervalos"]["recall"]
    texto = [
        "# A/B testing de P2: versión vigente contra versión reentrenada",
        "",
        f"Generado el {resultado['generado'].replace('T', ' ')} con `python -m mibici.modeling.abtest` sobre la tabla de monitoreo "
        f"(`data/interim/{config.ARCHIVO_MONITOREO.name}`). Las dos versiones se cargan del Model Registry (`{resultado['modelo']}`) y predicen "
        "las mismas horas-estación con el umbral de decisión que cada una lleva dentro.",
        "",
        tabla_markdown(["", "Versión", "Alias al evaluar", "Corrida", "Entrenamiento", "Umbral", "Datos"],
                       [("A", a["version"], a["alias"], f"`{a['corrida']}`", a["periodo_entrenamiento"], a["umbral"], f"`{a['version_datos']}`"),
                        ("B", b["version"], b["alias"], f"`{b['corrida']}`", b["periodo_entrenamiento"], b["umbral"], f"`{b['version_datos']}`")]),
        "",
        "## Regla de decisión",
        "",
        REGLA,
        "",
        "## Comparación pareada en el conjunto de evaluación",
        "",
        f"Conjunto de evaluación: del {inicio} al {fin}, {numero(evaluacion['filas'])} horas-estación en {evaluacion['dias']} días, con "
        f"{numero(evaluacion['positivos'])} horas en riesgo ({porcentaje(evaluacion['positivos'] / evaluacion['filas'])}). Ninguna de las dos versiones "
        f"usó este periodo para entrenar ni para elegir su umbral. Las dos versiones dan la misma clase en {porcentaje(evaluacion['coinciden'])} de las filas. "
        f"Los intervalos salen de {resultado['replicas']:,} réplicas de bootstrap por bloques de un día (semilla {resultado['semilla']}), con los mismos días "
        f"para las dos versiones en cada réplica. El costo cuenta un falso positivo como 1 y un falso negativo como {config.COSTO_FALSO_NEGATIVO}.",
        "",
        tabla_markdown(encabezado, filas_comparativas(evaluacion)),
        "",
        "Prueba de McNemar sobre los pares discordantes (una versión acierta y la otra no):",
        "",
        tabla_markdown(["Subconjunto", "Solo acierta A", "Solo acierta B", "Prueba", "Estadístico", "Valor p"], filas_mcnemar(evaluacion)),
        "",
        "## Simulación de tráfico dividido",
        "",
        f"Cada hora-estación del conjunto de evaluación se asigna al azar a una versión ({porcentaje(trafico['proporcion_b'], 0)} a B, semilla {trafico['semilla']}) "
        "y solo se cuenta la respuesta de la versión asignada, como ocurriría al repartir el tráfico del servicio. Entre paréntesis, el intervalo de "
        f"{NIVEL} por bootstrap de bloques de un día.",
        "",
        tabla_markdown(["Brazo", "Horas-estación", "Horas en riesgo", "Recall", "Precisión", "Costo por mil horas-estación"], brazos),
        "",
        "## Por mes",
        "",
        tabla_markdown(["Mes", "Conjunto", "Horas-estación", "Horas en riesgo", "Recall A", "Recall B", "Precisión A", "Precisión B",
                        "Costo por mil A", "Costo por mil B", "B menos A"], meses),
        "",
    ]
    if "confirmacion" in resultado:
        confirmacion = resultado["confirmacion"]
        inicio, fin = resultado["ventanas"]["confirmacion"]
        texto += ["## Confirmación fuera de la regla", "",
                  f"Misma comparación pareada sobre el tramo posterior al conjunto de evaluación, del {inicio} al {fin} ({numero(confirmacion['filas'])} "
                  f"horas-estación en {confirmacion['dias']} días, {numero(confirmacion['positivos'])} en riesgo). No entra en la regla; muestra si la "
                  "diferencia se sostiene un mes después.", "",
                  tabla_markdown(encabezado, filas_comparativas(confirmacion)), ""]
    texto += [
        "## Decisión",
        "",
        f"- Condición 1, costo: el intervalo de la diferencia de costo por mil horas-estación va de {costo['inferior']:+.2f} a {costo['superior']:+.2f}; "
        f"{'se cumple' if decision['costo_menor'] else 'no se cumple'}.",
        f"- Condición 2, recall: el límite inferior de la diferencia de recall es {recall['inferior']:+.4f} frente al margen de -{MARGEN_RECALL}; "
        f"{'se cumple' if decision['recall_no_inferior'] else 'no se cumple'}.",
        f"- Resultado de la regla: {'promover la versión B' if decision['promover'] else 'mantener la versión A'}. {resultado['accion']}",
        "",
        "## Análisis posterior a la decisión: B con el recall de A",
        "",
        "Este apartado no cambia la decisión. Separa lo que aporta el reentrenamiento de lo que cambia el umbral: se busca el umbral con que la "
        f"versión B alcanza el recall de la versión A en el conjunto de evaluación ({resultado['a_igual_recall']['umbral_b']:.4f}, frente a "
        f"{b['umbral']} con que está registrada) y se repite la comparación pareada con ese umbral. En la evaluación el umbral se eligió con sus "
        "propias etiquetas, así que esa fila es optimista; en la confirmación el umbral ya estaba fijo. Entre paréntesis, el intervalo de "
        f"{NIVEL} de la diferencia de costo por mil horas-estación.",
        "",
        tabla_markdown(["Conjunto", "Recall A", "Recall B", "Precisión A", "Precisión B", "Alertas A", "Alertas B", "Costo por mil A",
                        "Costo por mil B", "B menos A"], filas_a_igual_recall(resultado)),
        "",
    ]
    ruta.write_text("\n".join(texto), encoding="utf-8")
    return ruta


def aplicar_decision(cliente, nombre, registrada_a, registrada_b, decision, promover):
    """Mueve el alias champion a la versión B solo si la regla se cumple y se pidió promover; devuelve lo que se hizo."""
    if decision["promover"] and promover:
        cliente.set_registered_model_alias(nombre, "champion", registrada_b.version)
        if "challenger" in registrada_b.aliases:
            cliente.delete_registered_model_alias(nombre, "challenger")
        cliente.set_model_version_tag(nombre, registrada_a.version, "alias_anterior", "champion")
        cliente.set_model_version_tag(nombre, registrada_a.version, "relevada_por", str(registrada_b.version))
        return f"El alias champion pasó de la versión {registrada_a.version} a la versión {registrada_b.version}; la versión {registrada_a.version} conserva su registro para revertir."
    if decision["promover"]:
        return f"La regla se cumple; el alias champion sigue en la versión {registrada_a.version} hasta ejecutar el comando con --promover."
    return f"El alias champion se queda en la versión {registrada_a.version} y la versión {registrada_b.version} conserva el alias challenger."


def registrar(resultado, archivos, args):
    """Deja la corrida del A/B en MLflow con las versiones y la regla como parámetros, las métricas de cada versión y los reportes."""
    versiones, evaluacion, trafico = resultado["versiones"], resultado["evaluacion"], resultado["trafico"]
    nombre = f"p2_abtest_v{versiones['a']['version']}_v{versiones['b']['version']}"
    mlflow.set_experiment(args.experimento)
    reanudada = bool(os.environ.get("MLFLOW_RUN_ID"))
    with mlflow.start_run(run_name=None if reanudada else nombre) as corrida:
        if corrida.info.run_name != nombre:
            mlflow.set_tag("mlflow.runName", nombre)
        mlflow.set_tags({**train.etiquetas(PREGUNTA, "hgb", "abtest", FUENTE), "entrega": ENTREGA,
                         "decision": "promover" if resultado["decision"]["promover"] else "mantener"})
        mlflow.log_params({
            "pregunta": "P2", "modelo_registrado": resultado["modelo"], "version_modelo_a": versiones["a"]["version"],
            "version_modelo_b": versiones["b"]["version"],
            "run_id_a": versiones["a"]["run_id"], "run_id_b": versiones["b"]["run_id"], "threshold_a": versiones["a"]["umbral"],
            "threshold_b": versiones["b"]["umbral"], "evaluacion_inicio": resultado["ventanas"]["evaluacion"][0],
            "evaluacion_fin": resultado["ventanas"]["evaluacion"][1], "registros_evaluacion": evaluacion["filas"], "dias_evaluacion": evaluacion["dias"],
            "replicas_bootstrap": resultado["replicas"], "semilla": resultado["semilla"], "confianza": CONFIANZA, "margen_recall": MARGEN_RECALL,
            "proporcion_b": PROPORCION_B, "costo_falso_negativo": config.COSTO_FALSO_NEGATIVO, "regla": REGLA,
        })
        metricas = {}
        for brazo in ("a", "b"):
            for metrica in ("recall", "precision", "f1", "pr_auc", "falsos_positivos", "falsos_negativos", "costo", "costo_por_mil"):
                metricas[f"{brazo}_{metrica}"] = evaluacion[brazo][metrica]
            metricas[f"trafico_{brazo}_costo_por_mil"] = trafico[brazo]["costo_por_mil"]
        for metrica in CON_INTERVALO:
            metricas[f"delta_{metrica}"] = evaluacion["diferencia"][metrica]
            metricas[f"delta_{metrica}_inferior"] = evaluacion["intervalos"][metrica]["inferior"]
            metricas[f"delta_{metrica}_superior"] = evaluacion["intervalos"][metrica]["superior"]
        metricas["mcnemar_p_valor"] = evaluacion["mcnemar"]["todas"]["p_valor"]
        metricas["trafico_delta_costo_por_mil"] = trafico["diferencia"]["costo_por_mil"]
        metricas["promover"] = int(resultado["decision"]["promover"])
        metricas["a_igual_recall_umbral_b"] = resultado["a_igual_recall"]["umbral_b"]
        if "confirmacion" in resultado:
            metricas["confirmacion_delta_recall"] = resultado["confirmacion"]["diferencia"]["recall"]
            metricas["confirmacion_delta_costo_por_mil"] = resultado["confirmacion"]["diferencia"]["costo_por_mil"]
            metricas["a_igual_recall_confirmacion_delta_costo_por_mil"] = resultado["a_igual_recall"]["confirmacion"]["diferencia"]["costo_por_mil"]
        mlflow.log_metrics({clave: float(valor) for clave, valor in metricas.items() if valor is not None})
        for ruta in archivos:
            mlflow.log_artifact(str(ruta), artifact_path="plots" if ruta.suffix == ".png" else "abtest")
    return corrida.info.run_id


def leer_argumentos():
    parser = argparse.ArgumentParser(
        description="A/B testing de dos versiones registradas del modelo de P2 sobre el conjunto de evaluación del periodo actual."
    )
    parser.add_argument("--version_a", default="", help="versión vigente; vacío usa el alias champion")
    parser.add_argument("--version_b", default="", help="versión alternativa; vacío usa el alias challenger")
    parser.add_argument("--replicas", type=int, default=REPLICAS, help="réplicas del bootstrap por bloques de un día (por defecto %(default)s)")
    parser.add_argument("--semilla", type=int, default=config.SEMILLA, help="semilla del bootstrap y del reparto de tráfico (por defecto %(default)s)")
    parser.add_argument("--promover", nargs="?", const="1", default="",
                        help="mueve el alias champion a la versión B si la regla de decisión se cumple (--promover o --promover 1)")
    parser.add_argument("--experimento", default=config.EXPERIMENTO, help="nombre del experimento en MLflow (por defecto %(default)s)")
    parser.add_argument("--tracking_uri", default=os.environ.get("MLFLOW_TRACKING_URI", config.TRACKING_URI),
                        help="servidor o almacén de MLflow (por defecto MLFLOW_TRACKING_URI o mlflow.db en la raíz)")
    args = parser.parse_args()
    args.version_a, args.version_b = train.limpiar(args.version_a), train.limpiar(args.version_b)
    args.promover = train.limpiar(args.promover).lower() in ("1", "true", "si", "sí")
    return args


def main():
    args = leer_argumentos()
    if not config.ARCHIVO_MONITOREO.exists():
        raise SystemExit("falta la tabla de monitoreo; se genera con python -m mibici.monitoreo.datos --ingerir --exportar")
    inicio = time.time()
    mlflow.set_tracking_uri(args.tracking_uri)
    cliente = MlflowClient()
    nombre = NOMBRES[PREGUNTA]
    modelo_a, registrada_a = cargar_version(cliente, nombre, args.version_a, "champion")
    modelo_b, registrada_b = cargar_version(cliente, nombre, args.version_b, "challenger")
    if str(registrada_a.version) == str(registrada_b.version):
        raise SystemExit("las dos versiones son la misma; indica --version_a y --version_b")
    tabla = pd.read_parquet(config.ARCHIVO_MONITOREO)
    resultado, diferencias = evaluar(tabla, modelo_a, modelo_b, args.replicas, args.semilla)
    resultado.update({
        "generado": datetime.now().isoformat(timespec="seconds"),
        "modelo": nombre,
        "versiones": {"a": describir_version(registrada_a, modelo_a, ", ".join(registrada_a.aliases) or "sin alias"),
                      "b": describir_version(registrada_b, modelo_b, ", ".join(registrada_b.aliases) or "sin alias")},
        "ventanas": datos.ventanas(),
        "regla": REGLA,
        "replicas": args.replicas,
        "semilla": args.semilla,
        "confianza": CONFIANZA,
        "margen_recall": MARGEN_RECALL,
    })
    resultado["accion"] = aplicar_decision(cliente, nombre, registrada_a, registrada_b, resultado["decision"], args.promover)

    config.DIR_MONITOREO.mkdir(parents=True, exist_ok=True)
    config.DIR_FIGURAS.mkdir(parents=True, exist_ok=True)
    with open(ARCHIVO_JSON, "w", encoding="utf-8") as archivo:
        json.dump(resultado, archivo, indent=2, ensure_ascii=False)
    escribir_reporte(resultado, ARCHIVO_REPORTE)
    grafica_abtest(resultado["por_mes"], diferencias["costo_por_mil"], resultado["evaluacion"]["intervalos"]["costo_por_mil"],
                   resultado["versiones"], FIGURA)
    run_id = registrar(resultado, [ARCHIVO_JSON, ARCHIVO_REPORTE, FIGURA], args)
    for version in (registrada_a.version, registrada_b.version):
        cliente.set_model_version_tag(nombre, version, "abtest_run_id", run_id)
    cliente.set_model_version_tag(nombre, registrada_b.version, "abtest_decision",
                                  "promover" if resultado["decision"]["promover"] else "mantener la versión vigente")

    evaluacion = resultado["evaluacion"]
    print("A: versión", registrada_a.version, "| B: versión", registrada_b.version, "|", evaluacion["filas"], "horas-estación en", evaluacion["dias"], "días")
    for metrica, titulo in NOMBRES_METRICAS:
        print(f"{titulo}: A {celda(metrica, evaluacion['a'][metrica])}, B {celda(metrica, evaluacion['b'][metrica])}")
    for metrica in CON_INTERVALO:
        intervalo = evaluacion["intervalos"][metrica]
        print(f"delta {metrica}: {evaluacion['diferencia'][metrica]:+.4f} (IC {intervalo['inferior']:+.4f} a {intervalo['superior']:+.4f})")
    print("McNemar, valor p:", ", ".join(f"{clave} {valor_p(valores['p_valor'])}" for clave, valores in evaluacion["mcnemar"].items()))
    trafico = resultado["trafico"]
    print(f"tráfico dividido, delta costo_por_mil: {trafico['diferencia']['costo_por_mil']:+.4f} "
          f"(IC {trafico['intervalos']['costo_por_mil']['inferior']:+.4f} a {trafico['intervalos']['costo_por_mil']['superior']:+.4f})")
    print("Regla:", ", ".join(f"{clave} {'sí' if valor else 'no'}" for clave, valor in resultado["decision"].items()))
    print(resultado["accion"])
    print("Corrida en MLflow:", run_id)
    print("Tiempo:", round(time.time() - inicio, 1), "s")


if __name__ == "__main__":
    main()
