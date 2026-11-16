import argparse
import os
import shutil
import tempfile
import time

import mlflow
import pandas as pd
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from mibici import config, features
from mibici.modeling import artefactos, registry, train
from mibici.monitoreo import datos

PREGUNTA = "p2"
ENTREGA = "5"
NOMBRE_CORRIDA = "p2_hgb_reentrenado"
FUENTE = "mibici/modeling/reentrenar.py"


def receta_del_vigente(cliente):
    """Algoritmo e hiperparámetros de la versión champion de P2, leídos de los parámetros de su corrida de origen."""
    vigente = cliente.get_model_version_by_alias(registry.NOMBRES[PREGUNTA], "champion")
    parametros = cliente.get_run(vigente.run_id).data.params
    modelo = parametros["modelo"]
    referencia = config.HIPERPARAMETROS[PREGUNTA][modelo]
    valores = {nombre: train.valor_hiperparametro(parametros.get(nombre, ""), valor) for nombre, valor in referencia.items()}
    return vigente, modelo, train.completar_hiperparametros(PREGUNTA, modelo, valores)


def conjuntos_de_reentrenamiento(tabla):
    """Entrenamiento hasta FIN_REENTRENAMIENTO, validación hasta FIN_MONITOREO y evaluación hasta FIN_EVALUACION.

    Parte la tabla de monitoreo con las fechas de config.py: el entrenamiento reúne todo 2025 y los
    primeros meses del periodo actual, la validación es el último mes de ese tramo (con ella se elige
    el umbral de decisión) y la evaluación es el tramo posterior, que la versión vigente tampoco vio.
    Como en la partición original, se quitan de entrenamiento y validación las horas cuya etiqueta
    mira al bloque siguiente.
    """
    limite = pd.Timestamp(datos.dia_siguiente(config.FIN_EVALUACION))
    entrenamiento, validacion, evaluacion = features.particion_temporal(tabla[tabla["hora"] < limite], "hora",
                                                                        config.FIN_REENTRENAMIENTO, config.FIN_MONITOREO)
    entrenamiento = features.sin_ventana_posterior(entrenamiento, config.FIN_REENTRENAMIENTO)
    validacion = features.sin_ventana_posterior(validacion, config.FIN_MONITOREO)
    return entrenamiento, validacion, evaluacion


def datos_de_la_corrida(detalle):
    """Resumen de los dos periodos de datos con la forma que esperan los parámetros comunes de train.py."""
    manifiesto = datos.leer_manifiesto(config.ARCHIVO_MANIFIESTO)
    manifiesto_actual = datos.leer_manifiesto(config.ARCHIVO_MANIFIESTO_ACTUAL)
    return {
        "version_datos": f"{detalle['version_datos']}+{detalle['version_datos_actual']}",
        "meses": manifiesto["meses"] + manifiesto_actual["meses"],
        "resumen": {"fecha_inicio": manifiesto["resumen"]["fecha_inicio"], "fecha_fin": manifiesto_actual["resumen"]["fecha_fin"]},
    }


def periodos():
    """Periodos de entrenamiento, validación y evaluación de la versión reentrenada, como texto para etiquetas."""
    return {
        "periodo_entrenamiento": f"{config.FECHA_INICIO} a {config.FIN_REENTRENAMIENTO}",
        "periodo_validacion": f"{datos.dia_siguiente(config.FIN_REENTRENAMIENTO)} a {config.FIN_MONITOREO}",
        "periodo_evaluacion": f"{datos.dia_siguiente(config.FIN_MONITOREO)} a {config.FIN_EVALUACION}",
    }


def registrar_como_challenger(cliente, run_id, vigente):
    """Registra la corrida como versión nueva de P2 con alias challenger y deja anotada la versión que tenía ese alias."""
    nombre = registry.NOMBRES[PREGUNTA]
    try:
        anterior = cliente.get_model_version_by_alias(nombre, "challenger")
    except MlflowException:
        anterior = None
    _, version = registry.registrar_version(cliente, PREGUNTA, run_id, "challenger")
    etiquetas = {"entrega": ENTREGA, "origen": "reentrenamiento", "receta_de_la_version": str(vigente.version), **periodos()}
    for clave, valor in etiquetas.items():
        cliente.set_model_version_tag(nombre, version, clave, valor)
    if anterior is not None and str(anterior.version) != version:
        cliente.set_model_version_tag(nombre, anterior.version, "alias_anterior", "challenger")
        cliente.set_model_version_tag(nombre, anterior.version, "relevada_por", version)
    return nombre, version, None if anterior is None else str(anterior.version)


def leer_argumentos():
    parser = argparse.ArgumentParser(
        description="Reentrena el modelo de P2 con la receta de la versión champion sobre 2025 más el periodo actual y lo registra como challenger."
    )
    parser.add_argument("--nombre_corrida", default=NOMBRE_CORRIDA, help="nombre de la corrida (por defecto %(default)s)")
    parser.add_argument("--semilla", type=int, default=config.SEMILLA, help="semilla del modelo (por defecto %(default)s)")
    parser.add_argument("--sin_registro", action="store_true",
                        help="entrena y deja la corrida en MLflow sin crear la versión ni mover el alias challenger")
    parser.add_argument("--experimento", default=config.EXPERIMENTO, help="nombre del experimento en MLflow (por defecto %(default)s)")
    parser.add_argument("--tracking_uri", default=os.environ.get("MLFLOW_TRACKING_URI", config.TRACKING_URI),
                        help="servidor o almacén de MLflow (por defecto MLFLOW_TRACKING_URI o mlflow.db en la raíz)")
    args = parser.parse_args()
    args.nombre_corrida = train.limpiar(args.nombre_corrida) or NOMBRE_CORRIDA
    return args


def main():
    args = leer_argumentos()
    if not (config.ARCHIVO_MONITOREO.exists() and config.ARCHIVO_DETALLE_MONITOREO.exists()):
        raise SystemExit("falta la tabla de monitoreo; se genera con python -m mibici.monitoreo.datos --ingerir --exportar")
    inicio = time.time()
    mlflow.set_tracking_uri(args.tracking_uri)
    cliente = MlflowClient()
    vigente, modelo, h = receta_del_vigente(cliente)
    args.pregunta, args.modelo, args.textos = PREGUNTA, modelo, {}
    args.fin_entrenamiento, args.fin_validacion, args.umbral_riesgo = config.FIN_REENTRENAMIENTO, config.FIN_MONITOREO, config.UMBRAL_RIESGO

    columnas = datos.IDENTIFICACION + features.COLUMNAS_P2 + [features.OBJETIVO_P2]
    conjuntos = conjuntos_de_reentrenamiento(pd.read_parquet(config.ARCHIVO_MONITOREO, columns=columnas))
    detalle = datos.leer_manifiesto(config.ARCHIVO_DETALLE_MONITOREO)
    resumen_datos = datos_de_la_corrida(detalle)

    mlflow.set_experiment(args.experimento)
    reanudada = bool(os.environ.get("MLFLOW_RUN_ID"))
    with mlflow.start_run(run_name=None if reanudada else args.nombre_corrida) as corrida:
        if corrida.info.run_name != args.nombre_corrida:
            mlflow.set_tag("mlflow.runName", args.nombre_corrida)
        mlflow.set_tags({**train.etiquetas(PREGUNTA, modelo, "retrain", FUENTE), "entrega": ENTREGA,
                         "receta_de_la_version": str(vigente.version), **periodos()})
        mlflow.log_params({**train.parametros_comunes(args, resumen_datos), **train.parametros_hiperparametros(h),
                           "fin_evaluacion": config.FIN_EVALUACION, "version_datos_2025": detalle["version_datos"],
                           "version_datos_actual": detalle["version_datos_actual"]})
        train.registrar_conjuntos(PREGUNTA, conjuntos, args)
        resultado = train.entrenar(PREGUNTA, modelo, h, args.semilla, conjuntos)
        with tempfile.TemporaryDirectory() as temporal:
            carpeta = artefactos.preparar_carpeta(temporal)
            shutil.copy(config.ARCHIVO_MANIFIESTO_ACTUAL, carpeta / "data" / config.ARCHIVO_MANIFIESTO_ACTUAL.name)
            metricas = train.registrar_resultado(resultado, PREGUNTA, h, args, resumen_datos["version_datos"], carpeta, fuente=FUENTE)

    print("Corrida:", args.nombre_corrida, "(" + corrida.info.run_id + ")", "con la receta de la versión", vigente.version, "(" + modelo + ")")
    print("Registros:", len(conjuntos[0]), "de entrenamiento,", len(conjuntos[1]), "de validación y", len(conjuntos[2]), "de evaluación")
    for clave, valor in metricas.items():
        print(f"{clave}: {valor:.4f}")
    print("Umbral de decisión:", resultado["umbral"], "elegido en", resultado["origen_umbral"])
    if not args.sin_registro:
        nombre, version, anterior = registrar_como_challenger(cliente, corrida.info.run_id, vigente)
        print(nombre, "versión", version, "-> challenger")
        if anterior is not None:
            print("La versión", anterior, "deja el alias challenger y conserva su registro con la etiqueta relevada_por")
    print("Tiempo:", round(time.time() - inicio, 1), "s")


if __name__ == "__main__":
    main()
