import argparse
import json
import os
import time
import warnings
from datetime import datetime

warnings.filterwarnings("ignore", category=SyntaxWarning, module=r".*evidently.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, message=r"numpy\.core is deprecated")

import evidently
import mlflow
import pandas as pd
from evidently import DataDefinition, Dataset, Report
from evidently.presets import DataDriftPreset, DataSummaryPreset

from mibici import config, features
from mibici.modeling import train
from mibici.monitoreo import datos, graficas
from mibici.monitoreo.formato import con_signo, decimal, numero, porcentaje, tabla_markdown

COLUMNAS = features.COLUMNAS_P2 + [features.OBJETIVO_P2] + datos.SALIDAS_MODELO
CATEGORICAS = ["riesgo_semana_anterior", "hora_dia", "dia_semana", "fin_de_semana", features.OBJETIVO_P2, "prediccion"]
NUMERICAS = [columna for columna in COLUMNAS if columna not in CATEGORICAS]
BINARIAS = ["riesgo_semana_anterior", "fin_de_semana", features.OBJETIVO_P2, "prediccion"]
PAPEL = {features.OBJETIVO_P2: "objetivo", "probabilidad": "predicción", "prediccion": "predicción"}
METODO_NUMERICAS = "wasserstein"
METODO_CATEGORICAS = "jensenshannon"
UMBRAL_DRIFT = 0.1
PROPORCION_DRIFT = 0.5
PRUEBAS = {"wasserstein": "Distancia de Wasserstein normalizada", "jensenshannon": "Distancia de Jensen-Shannon"}
CALIDAD = {"RowCount()": "filas", "DuplicatedRowCount()": "filas_duplicadas", "EmptyRowsCount()": "filas_vacias",
           "DatasetMissingValueCount()": "valores_faltantes", "ConstantColumnsCount()": "columnas_constantes",
           "AlmostConstantColumnsCount()": "columnas_casi_constantes", "DuplicatedColumnsCount()": "columnas_duplicadas"}
NOMBRES_CONJUNTOS = {"referencia": "Referencia", "validacion_2025": "Validación", "prueba_2025": "Prueba",
                     "actual": "Actual", "evaluacion": "Evaluación", "confirmacion": "Confirmación"}
VARIABLES_EN_FIGURA = 4
FUENTE = "mibici/monitoreo/drift.py"
ARCHIVO_HTML = config.DIR_MONITOREO / "evidently_p2.html"
ARCHIVO_EVIDENTLY = config.DIR_MONITOREO / "evidently_p2.json"
ARCHIVO_HTML_ALERTA = config.DIR_MONITOREO / "evidently_p2_alerta.html"
ARCHIVO_EVIDENTLY_ALERTA = config.DIR_MONITOREO / "evidently_p2_alerta.json"
ARCHIVO_DRIFT = config.DIR_MONITOREO / "drift.json"
ARCHIVO_RESUMEN = config.DIR_MONITOREO / "resumen.md"
FIGURAS = {
    "puntuaciones": config.DIR_FIGURAS / "drift_puntuaciones.png",
    "variables": config.DIR_FIGURAS / "drift_variables.png",
    "objetivo": config.DIR_FIGURAS / "drift_objetivo.png",
    "mensual": config.DIR_FIGURAS / "drift_mensual.png",
}


def conjunto_evidently(tabla):
    """Dataset de Evidently con las columnas del reporte; las categóricas van como enteros, que es como admite las etiquetas."""
    if isinstance(tabla, Dataset):
        return tabla
    definicion = DataDefinition(numerical_columns=NUMERICAS, categorical_columns=CATEGORICAS)
    return Dataset.from_pandas(tabla[COLUMNAS].astype({columna: "int64" for columna in CATEGORICAS}), data_definition=definicion)


def correr_reporte(referencia, actual, con_calidad=False):
    """Corre el preset de drift de Evidently del conjunto actual contra la referencia y, si se pide, el resumen de calidad."""
    metricas = [DataDriftPreset(columns=COLUMNAS, num_method=METODO_NUMERICAS, cat_method=METODO_CATEGORICAS,
                                num_threshold=UMBRAL_DRIFT, cat_threshold=UMBRAL_DRIFT, drift_share=PROPORCION_DRIFT)]
    if con_calidad:
        metricas.append(DataSummaryPreset(columns=COLUMNAS))
    return Report(metricas).run(conjunto_evidently(actual), conjunto_evidently(referencia))


def tabla_drift(resultado):
    """Prueba, estadístico, umbral y veredicto de cada columna, leídos del resultado de Evidently."""
    filas = []
    for metrica in resultado.dict()["metrics"]:
        configuracion = metrica["config"]
        if configuracion["type"].endswith("ValueDrift"):
            estadistico, umbral = float(metrica["value"]), float(configuracion["threshold"])
            filas.append({"columna": configuracion["column"], "tipo": "categórica" if configuracion["column"] in CATEGORICAS else "numérica",
                          "prueba": PRUEBAS.get(configuracion["method"], configuracion["method"]),
                          "estadistico": estadistico, "umbral": umbral, "deriva": bool(estadistico >= umbral)})
    return pd.DataFrame(filas)


def comparar(referencia, actual):
    """Tabla de drift por columna entre dos conjuntos, sin el resumen de calidad."""
    return tabla_drift(correr_reporte(referencia, actual))


def estadisticas(resultado):
    """Conteos de calidad del conjunto y estadísticas por columna, leídos del resumen de datos de Evidently."""
    conjunto, columnas = {}, {columna: {} for columna in COLUMNAS}
    for metrica in resultado.dict()["metrics"]:
        nombre, valor, columna = metrica["metric_name"], metrica["value"], metrica["config"].get("column")
        tipo = metrica["config"]["type"].rsplit(":", 1)[-1]
        if nombre in CALIDAD:
            conjunto[CALIDAD[nombre]] = int(valor["count"] if isinstance(valor, dict) else valor)
        elif columna in columnas and tipo == "MissingValueCount":
            columnas[columna]["faltantes"] = int(valor["count"])
        elif columna in columnas and tipo in ("MinValue", "MaxValue", "MeanValue", "StdValue"):
            columnas[columna][{"MinValue": "minimo", "MaxValue": "maximo", "MeanValue": "media", "StdValue": "desviacion"}[tipo]] = float(valor)
        elif columna in columnas and tipo == "UniqueValueCount":
            columnas[columna]["valores"] = len(valor["counts"])
            if columna in BINARIAS:
                columnas[columna]["media"] = float(sum(parte for etiqueta, parte in valor["shares"].items() if str(etiqueta) in ("1", "1.0")))
    return {"conjunto": conjunto, "columnas": columnas}


def resumen_de_calidad(tabla):
    """Corre solo el resumen de datos de Evidently sobre un conjunto y devuelve sus estadísticas."""
    return estadisticas(Report([DataSummaryPreset(columns=COLUMNAS)]).run(conjunto_evidently(tabla)))


def con_medias(drift, referencia, actual):
    """Agrega a la tabla de drift la media de cada columna en los dos conjuntos y su cambio relativo."""
    filas = []
    for fila in drift.to_dict("records"):
        media_referencia = referencia["columnas"][fila["columna"]].get("media")
        media_actual = actual["columnas"][fila["columna"]].get("media")
        cambio = None
        if fila["columna"] not in CATEGORICAS or fila["columna"] in BINARIAS:
            if media_referencia and not fila["columna"].startswith("neto_"):
                cambio = (media_actual - media_referencia) / abs(media_referencia)
        else:
            media_referencia = media_actual = None
        filas.append({**fila, "media_referencia": media_referencia, "media_actual": media_actual, "cambio_relativo": cambio})
    return pd.DataFrame(filas)


def partes(tabla):
    """Conjuntos de la tabla de monitoreo y las comparaciones de control que se derivan de ellos."""
    referencia = tabla[tabla["conjunto"] == "referencia"]
    actual = tabla[tabla["conjunto"] == "actual"]
    meses = actual["hora"].dt.month.unique()
    conocidas = referencia["estacion_id"].unique()
    return {
        "referencia": referencia,
        "actual": actual,
        "controles": {
            "mismos_meses": ("Mismos meses un año después", referencia[referencia["hora"].dt.month.isin(meses)], actual),
            "mismas_estaciones": ("Solo estaciones de la referencia", referencia, actual[actual["estacion_id"].isin(conocidas)]),
            "estacional": ("Referencia contra prueba de 2025", referencia, tabla[tabla["conjunto"] == "prueba_2025"]),
        },
    }


def resumir_comparacion(drift, filas_referencia, filas_actual):
    detalle = [{clave: None if isinstance(valor, float) and valor != valor else valor for clave, valor in fila.items()}
               for fila in drift.to_dict("records")]
    return {
        "filas_referencia": int(filas_referencia),
        "filas_actual": int(filas_actual),
        "columnas": len(drift),
        "columnas_con_deriva": int(drift["deriva"].sum()),
        "proporcion_con_deriva": float(drift["deriva"].mean()),
        "deriva_del_conjunto": bool(drift["deriva"].mean() >= PROPORCION_DRIFT),
        "detalle": detalle,
    }


def deriva_mensual(tabla, base=None):
    """Tabla de drift de cada mes del periodo actual contra la referencia."""
    if base is None:
        base = conjunto_evidently(tabla[tabla["conjunto"] == "referencia"])
    posterior = tabla[tabla["hora"] >= pd.Timestamp(config.FECHA_INICIO_ACTUAL)]
    meses = posterior["hora"].dt.to_period("M").astype(str)
    return {mes: comparar(base, parte) for mes, parte in posterior.groupby(meses)}


def primer_mes_con_deriva(mensual):
    """Primer mes en que la proporción de columnas con deriva alcanza la que Evidently usa para declarar deriva del conjunto."""
    for mes, drift in mensual.items():
        if drift["deriva"].mean() >= PROPORCION_DRIFT:
            return mes
    return None


def tasas_por_mes(tabla):
    """Tasa de horas en riesgo y tasa de alertas del modelo por mes, con el conjunto al que pertenece cada mes."""
    meses = tabla["hora"].dt.to_period("M").astype(str).rename("mes")
    mensual = tabla.groupby(meses).agg(filas=("prediccion", "size"), tasa_riesgo=(features.OBJETIVO_P2, "mean"),
                                       tasa_alertas=("prediccion", "mean"), conjunto=("conjunto", "first"))
    return mensual.sort_index()


def estaciones_nuevas(referencia, actual):
    """Estaciones del periodo actual que no existían en la referencia y qué parte de las filas aportan."""
    conocidas = set(referencia["estacion_id"].unique())
    presentes = set(actual["estacion_id"].unique())
    nuevas = ~actual["estacion_id"].isin(conocidas)
    objetivo = features.OBJETIVO_P2
    return {
        "estaciones_referencia": len(conocidas),
        "estaciones_actual": len(presentes),
        "estaciones_nuevas": len(presentes - conocidas),
        "estaciones_sin_actividad": len(conocidas - presentes),
        "filas_de_estaciones_nuevas": int(nuevas.sum()),
        "proporcion_de_filas": float(nuevas.mean()),
        "tasa_riesgo_estaciones_nuevas": float(actual.loc[nuevas, objetivo].mean()) if nuevas.any() else None,
        "tasa_riesgo_estaciones_conocidas": float(actual.loc[~nuevas, objetivo].mean()) if (~nuevas).any() else None,
    }


def calidad_crudos(manifiesto, manifiesto_actual):
    """Registros crudos y descartes de la limpieza en los dos periodos, y por mes en el periodo actual."""
    def periodo(datos_periodo):
        limpieza, resumen = datos_periodo["limpieza"], datos_periodo["resumen"]
        return {
            "meses": len(datos_periodo["meses"]),
            "registros_crudos": limpieza["registros_crudos"],
            "viajes_validos": resumen["viajes"],
            "duplicados": limpieza["duplicados"] + limpieza.get("duplicados_entre_meses", 0),
            "sin_fecha_o_estacion": limpieza["sin_fecha_o_estacion"],
            "duracion_negativa": limpieza["duracion_negativa"],
            "duracion_menor_1_min": limpieza["duracion_menor_1_min"],
            "duracion_mayor_24_h": limpieza["duracion_mayor_24_h"],
            "estaciones_con_viajes": resumen["estaciones_con_viajes"],
            "viajes_con_estacion_fuera_de_nomenclatura": resumen["viajes_con_estacion_fuera_de_nomenclatura"],
            "codificaciones": sorted({archivo["codificacion"] for archivo in datos_periodo["archivos_crudos"]}),
        }

    por_mes = [{"mes": mes, "codificacion": archivo["codificacion"], "registros_crudos": archivo["registros"],
                "viajes_validos": archivo["viajes_validos"], "duplicados": archivo["limpieza"]["duplicados"],
                "duracion_menor_1_min": archivo["limpieza"]["duracion_menor_1_min"],
                "duracion_mayor_24_h": archivo["limpieza"]["duracion_mayor_24_h"]}
               for mes, archivo in zip(manifiesto_actual["meses"], manifiesto_actual["archivos_crudos"])]
    return {"referencia": periodo(manifiesto), "actual": periodo(manifiesto_actual), "por_mes": por_mes}


def analizar(tabla, detalle, manifiesto, manifiesto_actual, carpeta=config.DIR_MONITOREO, figuras=None):
    """Corre el reporte principal, las comparaciones de control y la serie mensual, y deja el HTML, los JSON y las figuras."""
    figuras = figuras or FIGURAS
    conjuntos = partes(tabla)
    referencia, actual = conjuntos["referencia"], conjuntos["actual"]
    base = conjunto_evidently(referencia)
    resultado = correr_reporte(base, actual, con_calidad=True)
    resultado.save_html(str(carpeta / ARCHIVO_HTML.name))
    resultado.save_json(str(carpeta / ARCHIVO_EVIDENTLY.name))
    calidad_actual = estadisticas(resultado)
    calidad_referencia = resumen_de_calidad(base)
    principal = con_medias(tabla_drift(resultado), calidad_referencia, calidad_actual)

    controles = {}
    for nombre, (descripcion, origen, comparado) in conjuntos["controles"].items():
        drift = comparar(base if origen is referencia else origen, comparado)
        controles[nombre] = {"descripcion": descripcion, **resumir_comparacion(drift, len(origen), len(comparado))}
    mensual = deriva_mensual(tabla, base)
    tasas = tasas_por_mes(tabla)
    alerta = primer_mes_con_deriva(mensual)
    for nombre in (ARCHIVO_HTML_ALERTA.name, ARCHIVO_EVIDENTLY_ALERTA.name):
        (carpeta / nombre).unlink(missing_ok=True)
    if alerta is not None:
        del_mes = tabla[(tabla["hora"].dt.to_period("M").astype(str) == alerta) & (tabla["conjunto"] != "referencia")]
        reporte_del_mes = correr_reporte(base, del_mes, con_calidad=True)
        reporte_del_mes.save_html(str(carpeta / ARCHIVO_HTML_ALERTA.name))
        reporte_del_mes.save_json(str(carpeta / ARCHIVO_EVIDENTLY_ALERTA.name))

    resumen = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "evidently": evidently.__version__,
        "modelo": detalle["modelo"],
        "version_datos": detalle["version_datos"],
        "version_datos_actual": detalle["version_datos_actual"],
        "metodos": {"numericas": PRUEBAS[METODO_NUMERICAS], "categoricas": PRUEBAS[METODO_CATEGORICAS],
                    "umbral": UMBRAL_DRIFT, "proporcion_para_deriva_del_conjunto": PROPORCION_DRIFT},
        "ventanas": detalle["ventanas"],
        "conjuntos": detalle["conjuntos"],
        "principal": {"descripcion": "Referencia contra actual", **resumir_comparacion(principal, len(referencia), len(actual))},
        "controles": controles,
        "mensual": {mes: {"columnas_con_deriva": int(drift["deriva"].sum()), "proporcion_con_deriva": float(drift["deriva"].mean()),
                          "deriva_del_conjunto": bool(drift["deriva"].mean() >= PROPORCION_DRIFT),
                          "con_deriva": drift.loc[drift["deriva"], "columna"].tolist(),
                          "estadisticos": dict(zip(drift["columna"], drift["estadistico"]))} for mes, drift in mensual.items()},
        "primer_mes_con_deriva_del_conjunto": alerta,
        "tasas_por_mes": tasas.reset_index().to_dict("records"),
        "calidad": {"referencia": calidad_referencia, "actual": calidad_actual,
                    "crudos": calidad_crudos(manifiesto, manifiesto_actual), "estaciones": estaciones_nuevas(referencia, actual)},
    }
    with open(carpeta / ARCHIVO_DRIFT.name, "w", encoding="utf-8") as archivo:
        json.dump(resumen, archivo, indent=2, ensure_ascii=False)

    series = {valores["descripcion"]: pd.Series({fila["columna"]: fila["estadistico"] for fila in valores["detalle"]})
              for valores in controles.values()}
    graficas.grafica_puntuaciones(principal, series, UMBRAL_DRIFT, figuras["puntuaciones"])
    sin_rezagos = principal[~principal["columna"].str.endswith(("_h1", "_h2"))]
    mayores = sin_rezagos.sort_values("estadistico", ascending=False)["columna"].head(VARIABLES_EN_FIGURA).tolist()
    graficas.grafica_distribuciones(referencia, actual, mayores, dict(zip(principal["columna"], principal["estadistico"])), figuras["variables"])
    graficas.grafica_objetivo(tasas, NOMBRES_CONJUNTOS, figuras["objetivo"])
    matriz = pd.DataFrame({mes: valores["estadisticos"] for mes, valores in resumen["mensual"].items()}).reindex(COLUMNAS)
    graficas.grafica_drift_mensual(matriz, {mes: valores["columnas_con_deriva"] for mes, valores in resumen["mensual"].items()},
                                   UMBRAL_DRIFT, figuras["mensual"])
    return resumen


def filas_de_conjuntos(resumen):
    filas = []
    for conjunto, valores in resumen["conjuntos"].items():
        inicio, fin = resumen["ventanas"][conjunto]
        filas.append((NOMBRES_CONJUNTOS[conjunto], f"{inicio} a {fin}", numero(valores["filas"]), valores["estaciones"],
                      numero(valores["positivos"]), porcentaje(valores["tasa_riesgo"]),
                      numero(valores["alertas"]), porcentaje(valores["alertas"] / valores["filas"])))
    return filas


def filas_de_drift(detalle):
    return [(f"`{fila['columna']}`", PAPEL.get(fila["columna"], "entrada"), fila["prueba"], decimal(fila["estadistico"]), fila["umbral"],
             "Deriva" if fila["deriva"] else "Sin deriva", decimal(fila["media_referencia"]), decimal(fila["media_actual"]),
             con_signo(fila["cambio_relativo"])) for fila in detalle]


def filas_de_controles(resumen):
    controles = resumen["controles"]
    estadisticos = {nombre: {fila["columna"]: fila for fila in valores["detalle"]} for nombre, valores in controles.items()}
    filas = []
    for fila in resumen["principal"]["detalle"]:
        celdas = [f"`{fila['columna']}`", decimal(fila["estadistico"]) + (" (deriva)" if fila["deriva"] else "")]
        for nombre in controles:
            control = estadisticos[nombre][fila["columna"]]
            celdas.append(decimal(control["estadistico"]) + (" (deriva)" if control["deriva"] else ""))
        filas.append(celdas)
    totales = ["Columnas con deriva", f"{resumen['principal']['columnas_con_deriva']} de {resumen['principal']['columnas']}"]
    totales += [f"{valores['columnas_con_deriva']} de {valores['columnas']}" for valores in controles.values()]
    return filas + [totales]


def filas_mensuales(resumen):
    meses = list(resumen["mensual"])
    filas = [[f"`{columna}`"] + [decimal(resumen["mensual"][mes]["estadisticos"][columna], 2)
                                 + (" *" if resumen["mensual"][mes]["estadisticos"][columna] >= UMBRAL_DRIFT else "") for mes in meses]
             for columna in COLUMNAS]
    filas.append(["Columnas con deriva"] + [resumen["mensual"][mes]["columnas_con_deriva"] for mes in meses])
    return meses, filas


def filas_de_calidad(resumen):
    referencia, actual = resumen["calidad"]["referencia"], resumen["calidad"]["actual"]
    nombres = [("filas", "Filas"), ("filas_duplicadas", "Filas duplicadas en las columnas del reporte"), ("filas_vacias", "Filas vacías"),
               ("valores_faltantes", "Valores faltantes"), ("columnas_constantes", "Columnas constantes"),
               ("columnas_casi_constantes", "Columnas casi constantes"), ("columnas_duplicadas", "Columnas duplicadas")]
    filas = [(titulo, numero(referencia["conjunto"][clave]), numero(actual["conjunto"][clave])) for clave, titulo in nombres
             if clave in referencia["conjunto"] and clave in actual["conjunto"]]
    rangos = []
    for columna in NUMERICAS:
        antes, despues = referencia["columnas"][columna], actual["columnas"][columna]
        rangos.append((f"`{columna}`", f"{limite(antes['minimo'])} a {limite(antes['maximo'])}", f"{limite(despues['minimo'])} a {limite(despues['maximo'])}",
                       decimal(antes["desviacion"]), decimal(despues["desviacion"]), antes["faltantes"] + despues["faltantes"]))
    return filas, rangos


def limite(valor):
    """Extremo de un rango sin ceros de relleno: 205, -117 o 0.5."""
    return f"{valor:.3f}".rstrip("0").rstrip(".") or "0"


def minuscula(texto):
    """Primera letra en minúscula, para usar el nombre de una prueba a mitad de una oración."""
    return texto[0].lower() + texto[1:]


def filas_de_crudos(resumen):
    crudos = resumen["calidad"]["crudos"]
    conceptos = [("meses", "Meses"), ("registros_crudos", "Registros crudos"), ("viajes_validos", "Viajes válidos"),
                 ("duplicados", "`viaje_id` duplicado"), ("sin_fecha_o_estacion", "Sin fecha o sin estación"),
                 ("duracion_negativa", "Duración negativa"), ("duracion_menor_1_min", "Duración menor a 1 min"),
                 ("duracion_mayor_24_h", "Duración mayor a 24 h"), ("estaciones_con_viajes", "Estaciones con viajes"),
                 ("viajes_con_estacion_fuera_de_nomenclatura", "Viajes con estación fuera de la nomenclatura")]
    sin_tasa = ("meses", "registros_crudos", "estaciones_con_viajes")
    filas = []
    for clave, titulo in conceptos:
        celdas = [titulo]
        for periodo in ("referencia", "actual"):
            valor = crudos[periodo][clave]
            celdas.append(numero(valor) if clave in sin_tasa else f"{numero(valor)} ({porcentaje(valor / crudos[periodo]['registros_crudos'])})")
        filas.append(celdas)
    por_mes = [(fila["mes"], fila["codificacion"], numero(fila["registros_crudos"]), numero(fila["viajes_validos"]),
                numero(fila["duplicados"]), f"{numero(fila['duracion_menor_1_min'])} ({porcentaje(fila['duracion_menor_1_min'] / fila['registros_crudos'])})",
                fila["duracion_mayor_24_h"]) for fila in crudos["por_mes"]]
    return filas, por_mes


def texto_de_alerta(resumen):
    alerta = resumen["primer_mes_con_deriva_del_conjunto"]
    proporcion = porcentaje(resumen["metodos"]["proporcion_para_deriva_del_conjunto"], 0)
    if alerta is None:
        return f"Ningún mes alcanza la proporción de columnas con deriva ({proporcion}) con que Evidently declara deriva del conjunto."
    del_mes = resumen["mensual"][alerta]
    columnas = ", ".join(f"`{columna}`" for columna in del_mes["con_deriva"])
    return (f"El primer mes con deriva del conjunto, es decir, con al menos {proporcion} de las columnas sobre el umbral, es {alerta} "
            f"({del_mes['columnas_con_deriva']} de {len(del_mes['estadisticos'])}: {columnas}). El reporte de Evidently de ese mes contra la referencia "
            f"queda en `reports/monitoreo/{ARCHIVO_HTML_ALERTA.name}` y sus métricas en `reports/monitoreo/{ARCHIVO_EVIDENTLY_ALERTA.name}`.")


def escribir_resumen(resumen, ruta=ARCHIVO_RESUMEN):
    """Escribe el resumen en Markdown con los conjuntos, la prueba y el veredicto por columna, los controles y la calidad de los datos."""
    modelo, principal, estaciones = resumen["modelo"], resumen["principal"], resumen["calidad"]["estaciones"]
    conjuntos = resumen["conjuntos"]
    meses, mensuales = filas_mensuales(resumen)
    calidad, rangos = filas_de_calidad(resumen)
    crudos, crudos_por_mes = filas_de_crudos(resumen)
    referencia, actual = conjuntos["referencia"], conjuntos["actual"]
    esperadas = referencia["tasa_riesgo"] * actual["filas"]
    texto = [
        "# Monitoreo de P2: drift entre la referencia y el periodo actual",
        "",
        f"Reporte generado el {resumen['generado'].replace('T', ' ')} con Evidently {resumen['evidently']} (`python -m mibici.monitoreo.drift`) sobre la tabla "
        f"`data/interim/{config.ARCHIVO_MONITOREO.name}`, que `python -m mibici.monitoreo.datos --exportar` arma con las versiones de datos "
        f"`{resumen['version_datos']}` (2025) y `{resumen['version_datos_actual']}` (periodo actual) y con las predicciones de "
        f"`{modelo['nombre']}` versión {modelo['version']} (corrida `{modelo['corrida']}`, umbral de decisión {modelo['umbral']}). "
        f"El reporte interactivo de Evidently queda en `reports/monitoreo/{ARCHIVO_HTML.name}` (fuera de Git por su tamaño) y sus métricas en "
        f"`reports/monitoreo/{ARCHIVO_EVIDENTLY.name}`; las cifras de este resumen están también en `reports/monitoreo/{ARCHIVO_DRIFT.name}`.",
        "",
        "## Conjuntos",
        "",
        "Cada fila es una estación en una hora, con las 13 variables de entrada de P2, la etiqueta de riesgo de las dos horas siguientes y la "
        "probabilidad y la clase que asigna el modelo vigente. La referencia es el conjunto de entrenamiento del modelo; el periodo actual es "
        "el que el modelo atendió después, sin reentrenarse.",
        "",
        tabla_markdown(["Conjunto", "Periodo", "Filas", "Estaciones", "Horas en riesgo", "Tasa de riesgo", "Alertas del modelo", "Tasa de alertas"],
                       filas_de_conjuntos(resumen)),
        "",
        "## Drift por columna: referencia contra actual",
        "",
        f"Preset `DataDriftPreset` de Evidently con {minuscula(resumen['metodos']['numericas'])} en las columnas numéricas y "
        f"{minuscula(resumen['metodos']['categoricas'])} en las categóricas; hay deriva en una columna cuando el estadístico alcanza "
        f"{resumen['metodos']['umbral']} y en el conjunto cuando deriva al menos {porcentaje(resumen['metodos']['proporcion_para_deriva_del_conjunto'], 0)} de las columnas. "
        "En las columnas binarias la media es la proporción de unos.",
        "",
        tabla_markdown(["Columna", "Papel", "Prueba", "Estadístico", "Umbral", "Veredicto", "Media en referencia", "Media en actual", "Cambio relativo"],
                       filas_de_drift(principal["detalle"])),
        "",
        f"Columnas con deriva: {principal['columnas_con_deriva']} de {principal['columnas']} ({porcentaje(principal['proporcion_con_deriva'], 1)}); "
        f"deriva del conjunto según Evidently: {'sí' if principal['deriva_del_conjunto'] else 'no'}.",
        "",
        "## Comparaciones de control",
        "",
        "El mismo preset sobre tres pares de conjuntos que aíslan el origen de la deriva: los mismos meses del año en la referencia y en el periodo "
        "actual (quita la estacionalidad), el periodo actual restringido a las estaciones que existían en la referencia (quita la expansión del "
        "sistema) y la referencia contra la prueba de 2025 (la deriva que el modelo ya enfrentó al evaluarse, solo por cambio de temporada).",
        "",
        tabla_markdown(["Columna", "Referencia contra actual"] + [valores["descripcion"] for valores in resumen["controles"].values()],
                       filas_de_controles(resumen)),
        "",
        "## Drift por mes del periodo actual",
        "",
        f"Estadístico de cada columna en cada mes contra la referencia; el asterisco marca los que alcanzan el umbral de {resumen['metodos']['umbral']}.",
        "",
        tabla_markdown(["Columna"] + meses, mensuales),
        "",
        texto_de_alerta(resumen),
        "",
        "## Objetivo y predicción",
        "",
        f"- La tasa de horas en riesgo pasa de {porcentaje(referencia['tasa_riesgo'])} en la referencia a {porcentaje(actual['tasa_riesgo'])} en el periodo actual "
        f"({con_signo(actual['tasa_riesgo'] / referencia['tasa_riesgo'] - 1)}). Con la tasa de la referencia se esperarían {numero(esperadas)} horas en riesgo "
        f"en las {numero(actual['filas'])} filas del periodo actual y ocurren {numero(actual['positivos'])}.",
        f"- El modelo vigente alerta en {porcentaje(referencia['alertas'] / referencia['filas'])} de las horas de la referencia y en "
        f"{porcentaje(actual['alertas'] / actual['filas'])} de las del periodo actual; por cada hora en riesgo observada emite "
        f"{referencia['alertas'] / referencia['positivos']:.2f} alertas en la referencia y {actual['alertas'] / actual['positivos']:.2f} en el periodo actual.",
        f"- Estaciones: {estaciones['estaciones_referencia']} en la referencia y {estaciones['estaciones_actual']} en el periodo actual; "
        f"{estaciones['estaciones_nuevas']} son nuevas y aportan {numero(estaciones['filas_de_estaciones_nuevas'])} filas "
        f"({porcentaje(estaciones['proporcion_de_filas'])}). Estaciones de la referencia sin actividad en el periodo actual: {estaciones['estaciones_sin_actividad']}.",
    ]
    if estaciones["tasa_riesgo_estaciones_nuevas"] is not None:
        texto.append(f"- Tasa de riesgo en el periodo actual: {porcentaje(estaciones['tasa_riesgo_estaciones_conocidas'])} en las estaciones de la referencia y "
                     f"{porcentaje(estaciones['tasa_riesgo_estaciones_nuevas'])} en las nuevas.")
    texto += [
        "",
        "## Calidad de los datos",
        "",
        "Resumen `DataSummaryPreset` de Evidently sobre las mismas columnas en los dos conjuntos:",
        "",
        tabla_markdown(["Concepto", "Referencia", "Actual"], calidad),
        "",
        tabla_markdown(["Columna numérica", "Rango en referencia", "Rango en actual", "Desviación en referencia", "Desviación en actual", "Faltantes"], rangos),
        "",
        "Archivos crudos del portal y descartes de la limpieza (`data/manifiesto.json` y `data/manifiesto_actual.json`); el porcentaje es sobre los registros crudos:",
        "",
        tabla_markdown(["Concepto", "2025", "Periodo actual"], crudos),
        "",
        tabla_markdown(["Mes", "Codificación", "Registros crudos", "Viajes válidos", "`viaje_id` duplicado", "Duración menor a 1 min", "Duración mayor a 24 h"],
                       crudos_por_mes),
        "",
    ]
    ruta.write_text("\n".join(texto), encoding="utf-8")
    return ruta


def registrar(resumen, archivos, tracking_uri, experimento):
    """Deja la corrida de monitoreo en MLflow: ventanas y modelo como parámetros, estadísticos de drift como métricas y los reportes como artefactos."""
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experimento)
    nombre = "p2_monitoreo_drift"
    reanudada = bool(os.environ.get("MLFLOW_RUN_ID"))
    with mlflow.start_run(run_name=None if reanudada else nombre) as corrida:
        if corrida.info.run_name != nombre:
            mlflow.set_tag("mlflow.runName", nombre)
        mlflow.set_tags({**train.etiquetas(datos.PREGUNTA, "hgb", "monitoring", FUENTE), "entrega": "5"})
        parametros = {"pregunta": "P2", "modelo_registrado": resumen["modelo"]["nombre"], "version_modelo": resumen["modelo"]["version"],
                      "version_datos": resumen["version_datos"], "version_datos_actual": resumen["version_datos_actual"],
                      "evidently": resumen["evidently"], "umbral_drift": UMBRAL_DRIFT, "metodo_numericas": METODO_NUMERICAS,
                      "metodo_categoricas": METODO_CATEGORICAS}
        for conjunto in ("referencia", "actual"):
            parametros[f"{conjunto}_inicio"], parametros[f"{conjunto}_fin"] = resumen["ventanas"][conjunto]
            parametros[f"registros_{conjunto}"] = resumen["conjuntos"][conjunto]["filas"]
        mlflow.log_params(parametros)
        metricas = {"columnas_con_deriva": resumen["principal"]["columnas_con_deriva"],
                    "proporcion_con_deriva": resumen["principal"]["proporcion_con_deriva"],
                    "tasa_riesgo_referencia": resumen["conjuntos"]["referencia"]["tasa_riesgo"],
                    "tasa_riesgo_actual": resumen["conjuntos"]["actual"]["tasa_riesgo"]}
        metricas.update({f"drift_{fila['columna']}": fila["estadistico"] for fila in resumen["principal"]["detalle"]})
        mlflow.log_metrics(metricas)
        for paso, valores in enumerate(resumen["mensual"].values(), start=1):
            mlflow.log_metric("columnas_con_deriva_por_mes", valores["columnas_con_deriva"], step=paso)
        if resumen["primer_mes_con_deriva_del_conjunto"]:
            mlflow.set_tag("primer_mes_con_deriva", resumen["primer_mes_con_deriva_del_conjunto"])
        for ruta in archivos:
            if ruta.exists():
                mlflow.log_artifact(str(ruta), artifact_path="plots" if ruta.suffix == ".png" else "monitoreo")
    return corrida.info.run_id


def leer_argumentos():
    parser = argparse.ArgumentParser(
        description="Reporte de drift y de calidad de datos de P2 con Evidently: referencia (entrenamiento del modelo vigente) contra el periodo actual."
    )
    parser.add_argument("--registrar", action="store_true",
                        help="deja además una corrida en MLflow con los estadísticos de drift y los reportes como artefactos")
    parser.add_argument("--experimento", default=config.EXPERIMENTO,
                        help="nombre del experimento en MLflow (por defecto %(default)s)")
    parser.add_argument("--tracking_uri", default=os.environ.get("MLFLOW_TRACKING_URI", config.TRACKING_URI),
                        help="servidor o almacén de MLflow (por defecto MLFLOW_TRACKING_URI o mlflow.db en la raíz)")
    return parser.parse_args()


def main():
    args = leer_argumentos()
    if not (config.ARCHIVO_MONITOREO.exists() and config.ARCHIVO_DETALLE_MONITOREO.exists()):
        print("No hay tabla de monitoreo en", datos.ruta_corta(config.DIR_DATOS_INTERMEDIOS))
        print("Orden: python -m mibici.monitoreo.datos --ingerir --exportar y después este comando")
        return
    inicio = time.time()
    tabla = pd.read_parquet(config.ARCHIVO_MONITOREO)
    detalle = datos.leer_manifiesto(config.ARCHIVO_DETALLE_MONITOREO)
    config.DIR_MONITOREO.mkdir(parents=True, exist_ok=True)
    config.DIR_FIGURAS.mkdir(parents=True, exist_ok=True)
    resumen = analizar(tabla, detalle, datos.leer_manifiesto(config.ARCHIVO_MANIFIESTO), datos.leer_manifiesto(config.ARCHIVO_MANIFIESTO_ACTUAL))
    escribir_resumen(resumen)

    principal = resumen["principal"]
    print("Referencia:", principal["filas_referencia"], "filas; actual:", principal["filas_actual"], "filas")
    for fila in principal["detalle"]:
        print(fila["columna"] + ":", fila["prueba"], round(fila["estadistico"], 4), "deriva" if fila["deriva"] else "sin deriva")
    print("Columnas con deriva:", principal["columnas_con_deriva"], "de", principal["columnas"])
    for nombre, valores in resumen["controles"].items():
        print(nombre + ":", valores["columnas_con_deriva"], "de", valores["columnas"], "columnas con deriva")
    print("Columnas con deriva por mes:", {mes: valores["columnas_con_deriva"] for mes, valores in resumen["mensual"].items()})
    print("Primer mes con deriva del conjunto:", resumen["primer_mes_con_deriva_del_conjunto"] or "ninguno")
    if args.registrar:
        archivos = [ARCHIVO_HTML, ARCHIVO_EVIDENTLY, ARCHIVO_HTML_ALERTA, ARCHIVO_EVIDENTLY_ALERTA, ARCHIVO_DRIFT, ARCHIVO_RESUMEN, *FIGURAS.values()]
        print("Corrida en MLflow:", registrar(resumen, archivos, args.tracking_uri, args.experimento))
    print("Reportes en", datos.ruta_corta(config.DIR_MONITOREO), "y figuras en",
          datos.ruta_corta(config.DIR_FIGURAS))
    print("Tiempo:", round(time.time() - inicio, 1), "s")


if __name__ == "__main__":
    main()
