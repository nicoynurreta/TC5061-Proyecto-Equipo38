import argparse
import hashlib
import json
import os
import time
from datetime import datetime

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow import MlflowClient

from mibici import config, dataset, features
from mibici.modeling.registry import NOMBRES

PREGUNTA = "p2"
ALIAS = "champion"
IDENTIFICACION = ["estacion_id", "hora"]
SALIDAS_MODELO = ["probabilidad", "prediccion"]
CONJUNTOS = ["referencia", "validacion_2025", "prueba_2025", "actual", "evaluacion", "confirmacion"]


def dia_siguiente(fecha):
    """Fecha AAAA-MM-DD del día posterior a la que se recibe."""
    return str((pd.Timestamp(fecha) + pd.Timedelta(days=1)).date())


def ruta_corta(ruta):
    """Ruta relativa a la raíz del proyecto; solo el nombre cuando el archivo está fuera de ella."""
    if config.RAIZ_PROYECTO in ruta.parents:
        return ruta.relative_to(config.RAIZ_PROYECTO).as_posix()
    return ruta.name


def ventanas():
    """Primer y último día de cada conjunto de la tabla de monitoreo, según las fechas de config.py."""
    return {
        "referencia": [config.FECHA_INICIO, config.FIN_ENTRENAMIENTO],
        "validacion_2025": [dia_siguiente(config.FIN_ENTRENAMIENTO), config.FIN_VALIDACION],
        "prueba_2025": [dia_siguiente(config.FIN_VALIDACION), config.FECHA_FIN],
        "actual": [config.FECHA_INICIO_ACTUAL, config.FIN_MONITOREO],
        "evaluacion": [dia_siguiente(config.FIN_MONITOREO), config.FIN_EVALUACION],
        "confirmacion": [dia_siguiente(config.FIN_EVALUACION), config.FECHA_FIN_ACTUAL],
    }


def escribir_manifiesto(meses, crudos, limpieza, viajes, estaciones):
    """Escribe data/manifiesto_actual.json con la estructura del manifiesto de 2025 y el detalle de la limpieza por mes."""
    nomenclatura = {"archivo": config.ARCHIVO_ESTACIONES.name, "registros": len(estaciones),
                    "sha256": dataset.sha256_archivo(config.ARCHIVO_ESTACIONES)}
    sumas = sorted([archivo["sha256"] for archivo in crudos] + [nomenclatura["sha256"]])
    conocidos = viajes["origen_conocido"] & viajes["destino_conocido"]
    manifiesto = {
        "version_datos": hashlib.sha256("".join(sumas).encode()).hexdigest()[:12],
        "generado": datetime.now().isoformat(timespec="seconds"),
        "fuente": config.URL_DATOS_ABIERTOS,
        "meses": meses,
        "resumen": {
            "viajes": len(viajes),
            "fecha_inicio": str(viajes["inicio"].min().date()),
            "fecha_fin": str(viajes["inicio"].max().date()),
            "estaciones_en_nomenclatura": len(estaciones),
            "estaciones_con_viajes": int(pd.concat([viajes["origen_id"], viajes["destino_id"]]).nunique()),
            "viajes_con_estacion_fuera_de_nomenclatura": int((~conocidos).sum()),
        },
        "limpieza": limpieza,
        "nomenclatura": nomenclatura,
        "archivos_crudos": crudos,
        "archivos_procesados": [{"archivo": config.ARCHIVO_VIAJES_ACTUAL.name, "registros": len(viajes),
                                 "bytes": config.ARCHIVO_VIAJES_ACTUAL.stat().st_size,
                                 "sha256": dataset.sha256_archivo(config.ARCHIVO_VIAJES_ACTUAL)}],
    }
    with open(config.ARCHIVO_MANIFIESTO_ACTUAL, "w", encoding="utf-8") as archivo:
        json.dump(manifiesto, archivo, indent=2, ensure_ascii=False)
    return manifiesto


def ingerir(meses, forzar=False):
    """Descarga y limpia los meses del periodo actual en archivos aparte, sin tocar los datos ni el manifiesto de 2025."""
    if not config.ARCHIVO_ESTACIONES.exists():
        raise SystemExit("falta data/processed/estaciones.parquet; se genera con make ingest")
    inicio = time.time()
    enlaces = dataset.obtener_enlaces()
    faltan = [mes for mes in meses if mes not in enlaces]
    if faltan:
        raise SystemExit(f"el portal no publica estos meses: {faltan}")
    estaciones = pd.read_parquet(config.ARCHIVO_ESTACIONES)
    config.DIR_DATOS_CRUDOS.mkdir(parents=True, exist_ok=True)

    crudos, partes, limpieza = [], [], {}
    for mes in meses:
        url = enlaces[mes]
        ruta = config.DIR_DATOS_CRUDOS / url.rsplit("/", 1)[-1]
        tamano = dataset.descargar(url, ruta, forzar)
        df, codificacion = dataset.leer_csv(ruta)
        viajes_mes, conteo = dataset.limpiar_viajes(df)
        crudos.append({"archivo": ruta.name, "url": url, "bytes": tamano, "sha256": dataset.sha256_archivo(ruta),
                       "codificacion": codificacion, "registros": conteo["registros_crudos"],
                       "viajes_validos": len(viajes_mes), "limpieza": conteo})
        for clave, valor in conteo.items():
            limpieza[clave] = limpieza.get(clave, 0) + valor
        partes.append(viajes_mes)
        print(mes, codificacion, conteo["registros_crudos"], "registros,", len(viajes_mes), "viajes válidos")

    viajes = pd.concat(partes, ignore_index=True)
    duplicados = viajes["viaje_id"].duplicated()
    limpieza["duplicados_entre_meses"] = int(duplicados.sum())
    viajes = viajes[~duplicados].sort_values("inicio").reset_index(drop=True)
    viajes = dataset.marcar_estaciones(viajes, estaciones)
    viajes.to_parquet(config.ARCHIVO_VIAJES_ACTUAL, index=False)
    manifiesto = escribir_manifiesto(meses, crudos, limpieza, viajes, estaciones)

    resumen = manifiesto["resumen"]
    print("Meses:", len(meses))
    print("Viajes válidos:", len(viajes), "del", resumen["fecha_inicio"], "al", resumen["fecha_fin"])
    print("Estaciones con viajes:", resumen["estaciones_con_viajes"], "de", len(estaciones), "en la nomenclatura")
    print("Viajes con estación fuera de la nomenclatura:", resumen["viajes_con_estacion_fuera_de_nomenclatura"])
    print("Descartados:", {clave: valor for clave, valor in limpieza.items() if clave != "registros_crudos"})
    print("Versión de los datos:", manifiesto["version_datos"])
    print("Tiempo:", round(time.time() - inicio, 1), "s")
    return manifiesto


def asignar_conjunto(hora):
    """Conjunto del periodo actual al que pertenece cada hora: actual, evaluacion o confirmacion."""
    hora = pd.to_datetime(hora)
    fin_monitoreo = pd.Timestamp(dia_siguiente(config.FIN_MONITOREO))
    fin_evaluacion = pd.Timestamp(dia_siguiente(config.FIN_EVALUACION))
    return np.select([hora < fin_monitoreo, hora < fin_evaluacion], ["actual", "evaluacion"], "confirmacion")


def armar_tabla(viajes, viajes_actual, estaciones):
    """Une las particiones de 2025 tal como las vio el modelo vigente con las horas del periodo actual.

    Las filas de 2025 salen de `features.conjuntos_p2` sobre los viajes de 2025, de modo que
    la referencia es exactamente el conjunto de entrenamiento del modelo. Las del periodo
    actual se calculan sobre la serie continua de los dos periodos, para que la primera
    semana tenga sus rezagos y la etiqueta de la semana anterior, como ocurre en producción.
    """
    entrenamiento, validacion, prueba = features.conjuntos_p2(viajes, estaciones)
    partes = [entrenamiento.assign(conjunto="referencia"), validacion.assign(conjunto="validacion_2025"),
              prueba.assign(conjunto="prueba_2025")]
    continuo = pd.concat([viajes, viajes_actual], ignore_index=True).drop_duplicates("viaje_id")
    etiquetado = features.etiquetar_riesgo(features.flujo_por_estacion_y_hora(continuo, estaciones), estaciones)
    completo = features.construir_features_p2(etiquetado)
    actual = completo[completo["hora"] >= pd.Timestamp(config.FECHA_INICIO_ACTUAL)]
    partes.append(actual.assign(conjunto=asignar_conjunto(actual["hora"])))
    tabla = pd.concat(partes, ignore_index=True)
    return tabla[IDENTIFICACION + features.COLUMNAS_P2 + [features.OBJETIVO_P2, "conjunto"]]


def agregar_predicciones(tabla, modelo):
    """Agrega la probabilidad de riesgo y la clase que el modelo asigna a cada hora-estación con su umbral."""
    entradas = tabla[features.COLUMNAS_P2]
    tabla = tabla.copy()
    tabla["probabilidad"] = modelo.predict_proba(entradas)[:, 1]
    tabla["prediccion"] = np.asarray(modelo.predict(entradas)).astype("int8")
    return tabla


def cargar_modelo(tracking_uri, version=""):
    """Carga el modelo de P2 del Model Registry por alias champion o por número de versión."""
    mlflow.set_tracking_uri(tracking_uri)
    nombre = NOMBRES[PREGUNTA]
    cliente = MlflowClient()
    if version:
        registrado = cliente.get_model_version(nombre, version)
        uri = f"models:/{nombre}/{version}"
    else:
        registrado = cliente.get_model_version_by_alias(nombre, ALIAS)
        uri = f"models:/{nombre}@{ALIAS}"
    return mlflow.sklearn.load_model(uri), registrado, uri


def resumen_conjuntos(tabla):
    """Filas, horas en riesgo, alertas, estaciones y rango de fechas de cada conjunto de la tabla."""
    resumen = {}
    for conjunto in CONJUNTOS:
        parte = tabla[tabla["conjunto"] == conjunto]
        if parte.empty:
            continue
        resumen[conjunto] = {
            "filas": len(parte),
            "positivos": int(parte[features.OBJETIVO_P2].sum()),
            "tasa_riesgo": float(parte[features.OBJETIVO_P2].mean()),
            "alertas": int(parte["prediccion"].sum()),
            "estaciones": int(parte["estacion_id"].nunique()),
            "primera_hora": str(parte["hora"].min()),
            "ultima_hora": str(parte["hora"].max()),
        }
    return resumen


def leer_manifiesto(ruta):
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


def exportar(tracking_uri, version=""):
    """Escribe en data/interim la tabla de monitoreo de P2 con las predicciones del modelo y su detalle."""
    necesarios = [config.ARCHIVO_VIAJES, config.ARCHIVO_ESTACIONES, config.ARCHIVO_VIAJES_ACTUAL]
    faltan = [ruta_corta(ruta) for ruta in necesarios if not ruta.exists()]
    if faltan:
        print("Faltan datos procesados:", ", ".join(faltan))
        print("Orden: make ingest (2025), python -m mibici.monitoreo.datos --ingerir (periodo actual) y después --exportar")
        return None
    inicio = time.time()
    viajes = pd.read_parquet(config.ARCHIVO_VIAJES)
    viajes_actual = pd.read_parquet(config.ARCHIVO_VIAJES_ACTUAL)
    estaciones = pd.read_parquet(config.ARCHIVO_ESTACIONES)
    modelo, registrado, uri = cargar_modelo(tracking_uri, version)
    tabla = agregar_predicciones(armar_tabla(viajes, viajes_actual, estaciones), modelo)
    config.DIR_DATOS_INTERMEDIOS.mkdir(parents=True, exist_ok=True)
    tabla.to_parquet(config.ARCHIVO_MONITOREO, index=False)

    detalle = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "version_datos": leer_manifiesto(config.ARCHIVO_MANIFIESTO)["version_datos"],
        "version_datos_actual": leer_manifiesto(config.ARCHIVO_MANIFIESTO_ACTUAL)["version_datos"],
        "modelo": {"nombre": registrado.name, "version": str(registrado.version), "uri": uri, "run_id": registrado.run_id,
                   "corrida": registrado.tags.get("corrida", ""), "umbral": float(getattr(modelo, "threshold", 0.5))},
        "ventanas": ventanas(),
        "conjuntos": resumen_conjuntos(tabla),
        "columnas": features.COLUMNAS_P2,
        "objetivo": features.OBJETIVO_P2,
        "salidas_modelo": SALIDAS_MODELO,
        "umbral_riesgo": config.UMBRAL_RIESGO,
        "ventana_riesgo_horas": config.VENTANA_RIESGO_HORAS,
        "costo_falso_negativo": config.COSTO_FALSO_NEGATIVO,
        "archivo": config.ARCHIVO_MONITOREO.name,
        "bytes": config.ARCHIVO_MONITOREO.stat().st_size,
        "segundos": round(time.time() - inicio, 1),
    }
    with open(config.ARCHIVO_DETALLE_MONITOREO, "w", encoding="utf-8") as archivo:
        json.dump(detalle, archivo, indent=2, ensure_ascii=False)

    print("Modelo:", uri, "-> versión", registrado.version, "umbral", detalle["modelo"]["umbral"])
    for conjunto, valores in detalle["conjuntos"].items():
        print(conjunto + ":", valores["filas"], "filas,", valores["positivos"], "en riesgo,", valores["alertas"], "alertas,",
              valores["estaciones"], "estaciones")
    print("Tabla:", ruta_corta(config.ARCHIVO_MONITOREO), round(detalle["bytes"] / 1e6, 1), "MB")
    print("Tiempo:", detalle["segundos"], "s")
    return detalle


def estado():
    """Muestra qué archivos del periodo actual existen y el orden de los pasos."""
    for ruta in [config.ARCHIVO_VIAJES_ACTUAL, config.ARCHIVO_MANIFIESTO_ACTUAL, config.ARCHIVO_MONITOREO]:
        print(ruta_corta(ruta) + ":", "existe" if ruta.exists() else "falta")
    print("Orden: python -m mibici.monitoreo.datos --ingerir y después --exportar, con el servidor de tracking levantado")


def leer_argumentos():
    parser = argparse.ArgumentParser(
        description="Ingesta del periodo actual de MiBici y tabla de monitoreo de P2 con las predicciones del modelo vigente."
    )
    parser.add_argument("--ingerir", action="store_true",
                        help="descarga y limpia los meses del periodo actual en data/processed/viajes_actual.parquet y data/manifiesto_actual.json")
    parser.add_argument("--exportar", action="store_true",
                        help="escribe en data/interim la tabla de P2 de los dos periodos con la predicción del modelo")
    parser.add_argument("--meses", nargs="+", default=config.MESES_ACTUAL, metavar="AAAA-MM",
                        help="meses del periodo actual, separados por espacios o por comas (por defecto %s a %s)" % (config.MESES_ACTUAL[0], config.MESES_ACTUAL[-1]))
    parser.add_argument("--forzar", action="store_true",
                        help="vuelve a descargar los archivos que ya estén en data/raw")
    parser.add_argument("--version", default="",
                        help="versión registrada del modelo de P2 con que se predice; vacío usa el alias champion")
    parser.add_argument("--tracking_uri", default=os.environ.get("MLFLOW_TRACKING_URI", config.TRACKING_URI),
                        help="servidor o almacén de MLflow (por defecto MLFLOW_TRACKING_URI o mlflow.db en la raíz)")
    return parser.parse_args()


def main():
    args = leer_argumentos()
    meses = [mes.strip() for parte in args.meses for mes in parte.strip().strip("\"'").split(",") if mes.strip()] or config.MESES_ACTUAL
    if args.ingerir:
        ingerir(meses, args.forzar)
    if args.exportar:
        exportar(args.tracking_uri, str(args.version).strip().strip("\"'"))
    if not (args.ingerir or args.exportar):
        estado()


if __name__ == "__main__":
    main()
