import argparse
import json
import time
from datetime import datetime

import numpy as np
import pandas as pd

from mibici import config, features
from mibici.monitoreo import costos, datos, graficas
from mibici.monitoreo.formato import con_signo, decimal, numero, porcentaje, tabla_markdown

BASE = "prueba_2025"
FUERA_DE_MUESTRA = ["validacion_2025", "prueba_2025", "actual", "evaluacion", "confirmacion"]
POSTERIORES = ["actual", "evaluacion", "confirmacion"]
ESTRATOS = np.round(np.arange(0, 1.01, 0.1), 1)
NOMBRES_CONJUNTOS = {"referencia": "Referencia", "validacion_2025": "Validación", "prueba_2025": "Prueba",
                     "actual": "Actual", "evaluacion": "Evaluación", "confirmacion": "Confirmación"}
ARCHIVO_DESEMPENO = config.DIR_MONITOREO / "desempeno.json"
ARCHIVO_RESUMEN = config.DIR_MONITOREO / "desempeno.md"
FIGURAS = {
    "mensual": config.DIR_FIGURAS / "desempeno_mensual.png",
    "estaciones": config.DIR_FIGURAS / "desempeno_estaciones.png",
}


def metricas_de(parte):
    """Métricas del modelo vigente sobre una parte de la tabla de monitoreo."""
    return costos.metricas(parte[features.OBJETIVO_P2], parte["prediccion"], parte["probabilidad"])


def por_conjunto(tabla):
    """Métricas por conjunto; la referencia es el entrenamiento del modelo, así que sus cifras son dentro de la muestra."""
    return {conjunto: metricas_de(parte) for conjunto, parte in tabla.groupby("conjunto", sort=False)}


def por_mes(tabla):
    """Métricas por mes en los conjuntos que el modelo no usó para entrenar."""
    fuera = tabla[tabla["conjunto"].isin(FUERA_DE_MUESTRA)]
    meses = fuera["hora"].dt.to_period("M").astype(str)
    filas = []
    for mes, parte in fuera.groupby(meses):
        filas.append({"mes": mes, "conjunto": parte["conjunto"].iloc[0], **metricas_de(parte)})
    return pd.DataFrame(filas).set_index("mes").sort_index()


def perfil_por_estrato(parte, cortes=ESTRATOS):
    """Peso, tasa de riesgo y parte de las horas en riesgo de cada estrato de la probabilidad que asigna el modelo."""
    estrato = pd.cut(parte["probabilidad"], cortes, include_lowest=True)
    grupo = parte.groupby(estrato, observed=False)[features.OBJETIVO_P2]
    perfil = pd.DataFrame({"filas": grupo.size(), "positivos": grupo.sum()})
    perfil["peso"] = perfil["filas"] / len(parte)
    perfil["tasa"] = perfil["positivos"] / perfil["filas"]
    perfil["parte_de_positivos"] = perfil["positivos"] / max(int(perfil["positivos"].sum()), 1)
    return perfil


def descomponer_tasa(base, periodo, cortes=ESTRATOS):
    """Parte el cambio de la tasa de riesgo entre dos periodos en un efecto de mezcla y un efecto condicional.

    Con las horas agrupadas por estratos de la probabilidad que asigna el modelo, el cambio de la
    tasa es la suma de dos términos: cuánto cambió el peso de cada estrato con la tasa de riesgo
    de la base (las entradas llevan al modelo a otras zonas de probabilidad, que es data drift) y
    cuánto cambió la tasa de riesgo dentro de cada estrato con los pesos del periodo (la misma
    probabilidad ya no corresponde a la misma frecuencia de riesgo, que es concept drift).
    """
    antes, despues = perfil_por_estrato(base, cortes), perfil_por_estrato(periodo, cortes)
    tasa_antes = antes["tasa"].fillna(despues["tasa"]).fillna(0.0)
    tasa_despues = despues["tasa"].fillna(tasa_antes)
    mezcla = float(((despues["peso"] - antes["peso"]) * tasa_antes).sum())
    condicional = float((despues["peso"] * (tasa_despues - tasa_antes)).sum())
    estratos = [{"estrato": f"{max(intervalo.left, 0):.1f} a {intervalo.right:.1f}", "peso_base": float(antes.loc[intervalo, "peso"]),
                 "peso_periodo": float(despues.loc[intervalo, "peso"]), "tasa_base": float(tasa_antes.loc[intervalo]),
                 "tasa_periodo": float(tasa_despues.loc[intervalo]),
                 "parte_de_positivos_base": float(antes.loc[intervalo, "parte_de_positivos"]),
                 "parte_de_positivos_periodo": float(despues.loc[intervalo, "parte_de_positivos"])} for intervalo in antes.index]
    tasa_base, tasa_periodo = float(base[features.OBJETIVO_P2].mean()), float(periodo[features.OBJETIVO_P2].mean())
    return {"tasa_base": tasa_base, "tasa_periodo": tasa_periodo, "cambio": tasa_periodo - tasa_base,
            "efecto_mezcla": mezcla, "efecto_condicional": condicional, "estratos": estratos}


def por_antiguedad(tabla, conjunto):
    """Métricas de un conjunto del periodo actual separando las estaciones de la referencia de las nuevas."""
    conocidas = tabla.loc[tabla["conjunto"] == "referencia", "estacion_id"].unique()
    parte = tabla[tabla["conjunto"] == conjunto]
    es_conocida = parte["estacion_id"].isin(conocidas)
    cohortes = {}
    for nombre, filtro in [("Estaciones de la referencia", es_conocida), ("Estaciones nuevas", ~es_conocida)]:
        if filtro.any():
            cohortes[nombre] = {"estaciones": int(parte.loc[filtro, "estacion_id"].nunique()), **metricas_de(parte[filtro])}
    return cohortes


def analizar(tabla, detalle, figuras=None):
    """Calcula el desempeño del modelo vigente por conjunto, por mes y por antigüedad de la estación, y la descomposición del cambio de la tasa."""
    figuras = figuras or FIGURAS
    mensual = por_mes(tabla)
    conjuntos = por_conjunto(tabla)
    base = tabla[tabla["conjunto"] == BASE]
    presentes = [conjunto for conjunto in POSTERIORES if conjunto in conjuntos]
    resumen = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "modelo": detalle["modelo"],
        "costo_falso_negativo": config.COSTO_FALSO_NEGATIVO,
        "ventanas": detalle["ventanas"],
        "base": BASE,
        "por_conjunto": conjuntos,
        "por_mes": mensual.reset_index().to_dict("records"),
        "descomposicion": {conjunto: descomponer_tasa(base, tabla[tabla["conjunto"] == conjunto]) for conjunto in presentes},
        "por_antiguedad": {conjunto: por_antiguedad(tabla, conjunto) for conjunto in presentes},
    }
    graficas.grafica_desempeno_mensual(mensual, conjuntos[BASE], NOMBRES_CONJUNTOS, figuras["mensual"])
    if "actual" in resumen["por_antiguedad"] and len(resumen["por_antiguedad"]["actual"]) > 1:
        graficas.grafica_cohortes(pd.DataFrame(resumen["por_antiguedad"]["actual"]).T, figuras["estaciones"])
    return resumen


def celdas_de_metricas(valores):
    return [numero(valores["filas"]), numero(valores["positivos"]), porcentaje(valores["tasa_riesgo"]), porcentaje(valores["tasa_alertas"]),
            decimal(valores["recall"]), decimal(valores["precision"]), decimal(valores["f1"]), decimal(valores.get("pr_auc")),
            numero(valores["falsos_positivos"]), numero(valores["falsos_negativos"]), numero(valores["costo"]), decimal(valores["costo_por_mil"], 2),
            decimal(valores["costo_relativo"])]


def escribir_resumen(resumen, ruta=ARCHIVO_RESUMEN):
    """Escribe el desempeño del modelo vigente en Markdown: por conjunto, por mes, descomposición de la tasa y antigüedad de la estación."""
    modelo, base = resumen["modelo"], resumen["por_conjunto"][resumen["base"]]
    encabezados = ["Filas", "Horas en riesgo", "Tasa de riesgo", "Tasa de alertas", "Recall", "Precisión", "F1", "PR-AUC",
                   "Falsos positivos", "Falsos negativos", "Costo", "Costo por mil horas-estación", "Costo frente a no alertar"]
    conjuntos = []
    for conjunto, valores in resumen["por_conjunto"].items():
        inicio, fin = resumen["ventanas"][conjunto]
        nota = " (dentro de la muestra)" if conjunto == "referencia" else ""
        conjuntos.append([NOMBRES_CONJUNTOS[conjunto] + nota, f"{inicio} a {fin}"] + celdas_de_metricas(valores))
    meses = [[fila["mes"], NOMBRES_CONJUNTOS[fila["conjunto"]]] + celdas_de_metricas(fila)
             + [con_signo(fila["recall"] / base["recall"] - 1),
                con_signo(fila["costo_relativo"] / base["costo_relativo"] - 1 if fila["costo_relativo"] is not None else None)]
             for fila in resumen["por_mes"]]
    descomposicion = []
    for conjunto, valores in resumen["descomposicion"].items():
        cambio = valores["cambio"]
        descomposicion.append((NOMBRES_CONJUNTOS[conjunto], porcentaje(valores["tasa_base"], 3), porcentaje(valores["tasa_periodo"], 3),
                               f"{cambio * 100:+.3f} pp", f"{valores['efecto_mezcla'] * 100:+.3f} pp", f"{valores['efecto_condicional'] * 100:+.3f} pp",
                               porcentaje(valores["efecto_mezcla"] / cambio, 0) if cambio else "n. a.",
                               porcentaje(valores["efecto_condicional"] / cambio, 0) if cambio else "n. a."))
    texto = [
        "# Monitoreo de P2: desempeño del modelo vigente en el periodo actual",
        "",
        f"Generado el {resumen['generado'].replace('T', ' ')} con `python -m mibici.monitoreo.desempeno` sobre la tabla de monitoreo. Modelo: "
        f"`{modelo['nombre']}` versión {modelo['version']} (corrida `{modelo['corrida']}`), con su umbral de decisión de {modelo['umbral']}. "
        f"El costo cuenta un falso positivo como 1 y un falso negativo como {resumen['costo_falso_negativo']}. Se reporta por mil horas-estación, que es "
        "el costo operativo del periodo, y frente a no alertar: el costo dividido entre lo que costaría no emitir ninguna alerta, que no depende de "
        "cuántas horas en riesgo tiene cada periodo y vale 1 cuando el modelo no aporta nada.",
        "",
        "## Por conjunto",
        "",
        tabla_markdown(["Conjunto", "Periodo"] + encabezados, conjuntos),
        "",
        "## Por mes fuera del entrenamiento",
        "",
        f"Las dos últimas columnas son el cambio relativo frente a la prueba de 2025 (recall {decimal(base['recall'])}, "
        f"costo frente a no alertar {decimal(base['costo_relativo'])}).",
        "",
        tabla_markdown(["Mes", "Conjunto"] + encabezados + ["Cambio del recall", "Cambio del costo frente a no alertar"], meses),
        "",
        "## Descomposición del cambio de la tasa de riesgo",
        "",
        "Cambio de la tasa de horas en riesgo de cada conjunto del periodo actual frente a la prueba de 2025, separado por estratos de 0.1 de la "
        "probabilidad que asigna el modelo. El efecto de mezcla es la parte del cambio que se explica porque las horas caen en otros estratos "
        "(cambian las entradas: data drift); el efecto condicional es la parte que se explica porque dentro del mismo estrato la frecuencia de "
        "riesgo ya es otra (cambia la relación entre entradas y objetivo: concept drift). Los dos efectos suman el cambio.",
        "",
        tabla_markdown(["Conjunto", "Tasa en la prueba de 2025", "Tasa en el conjunto", "Cambio", "Efecto de mezcla", "Efecto condicional",
                        "Parte de mezcla", "Parte condicional"], descomposicion),
        "",
    ]
    for conjunto, valores in resumen["descomposicion"].items():
        estratos = [(fila["estrato"], porcentaje(fila["peso_base"]), porcentaje(fila["peso_periodo"]), porcentaje(fila["tasa_base"]),
                     porcentaje(fila["tasa_periodo"]), porcentaje(fila["parte_de_positivos_base"], 1), porcentaje(fila["parte_de_positivos_periodo"], 1))
                    for fila in valores["estratos"]]
        texto += [f"Estratos de probabilidad, prueba de 2025 contra {NOMBRES_CONJUNTOS[conjunto].lower()}:", "",
                  tabla_markdown(["Probabilidad", "Peso en la prueba", "Peso en el conjunto", "Tasa de riesgo en la prueba", "Tasa de riesgo en el conjunto",
                                  "Horas en riesgo en la prueba", "Horas en riesgo en el conjunto"], estratos), ""]
    texto += ["## Estaciones de la referencia y estaciones nuevas", "",
              "Mismas métricas en cada conjunto del periodo actual, separando las estaciones que existían en el entrenamiento del modelo de las que se abrieron después.", ""]
    cohortes = []
    for conjunto, grupos in resumen["por_antiguedad"].items():
        for nombre, valores in grupos.items():
            cohortes.append([NOMBRES_CONJUNTOS[conjunto], nombre, valores["estaciones"]] + celdas_de_metricas(valores))
    texto += [tabla_markdown(["Conjunto", "Estaciones", "Número de estaciones"] + encabezados, cohortes), ""]
    ruta.write_text("\n".join(texto), encoding="utf-8")
    return ruta


def leer_argumentos():
    parser = argparse.ArgumentParser(
        description="Desempeño del modelo vigente de P2 por conjunto y por mes del periodo actual, frente a su conjunto de prueba."
    )
    return parser.parse_args()


def main():
    leer_argumentos()
    if not (config.ARCHIVO_MONITOREO.exists() and config.ARCHIVO_DETALLE_MONITOREO.exists()):
        print("No hay tabla de monitoreo en", datos.ruta_corta(config.DIR_DATOS_INTERMEDIOS))
        print("Orden: python -m mibici.monitoreo.datos --ingerir --exportar y después este comando")
        return
    inicio = time.time()
    tabla = pd.read_parquet(config.ARCHIVO_MONITOREO)
    detalle = datos.leer_manifiesto(config.ARCHIVO_DETALLE_MONITOREO)
    config.DIR_MONITOREO.mkdir(parents=True, exist_ok=True)
    config.DIR_FIGURAS.mkdir(parents=True, exist_ok=True)
    resumen = analizar(tabla, detalle)
    with open(ARCHIVO_DESEMPENO, "w", encoding="utf-8") as archivo:
        json.dump(resumen, archivo, indent=2, ensure_ascii=False)
    escribir_resumen(resumen)

    for fila in resumen["por_mes"]:
        print(fila["mes"], fila["conjunto"] + ":", "recall", round(fila["recall"], 4), "precisión", round(fila["precision"], 4),
              "f1", round(fila["f1"], 4), "pr_auc", round(fila["pr_auc"], 4), "costo por mil", round(fila["costo_por_mil"], 2),
              "costo frente a no alertar", round(fila["costo_relativo"], 4))
    for conjunto, valores in resumen["descomposicion"].items():
        print("tasa de riesgo, prueba de 2025 contra", conjunto + ":", round(valores["cambio"] * 100, 4), "pp; mezcla",
              round(valores["efecto_mezcla"] * 100, 4), "pp; condicional", round(valores["efecto_condicional"] * 100, 4), "pp")
    print("Reportes en", datos.ruta_corta(config.DIR_MONITOREO), "y figuras en",
          datos.ruta_corta(config.DIR_FIGURAS))
    print("Tiempo:", round(time.time() - inicio, 1), "s")


if __name__ == "__main__":
    main()
