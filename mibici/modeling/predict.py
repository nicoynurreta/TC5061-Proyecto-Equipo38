import argparse
import os

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd

from mibici import config, features


def leer_argumentos():
    parser = argparse.ArgumentParser(
        description="Predice con un modelo registrado en MLflow sobre el conjunto de prueba de una pregunta y guarda las predicciones en models/."
    )
    parser.add_argument("--pregunta", choices=["p1", "p2", "p3"], required=True)
    parser.add_argument("--modelo_uri", required=True,
                        help="URI del modelo en MLflow, por ejemplo runs:/<run_id>/modelo")
    parser.add_argument("--salida", default=None,
                        help="archivo CSV de salida (por defecto models/predicciones_<pregunta>.csv)")
    parser.add_argument("--fin_entrenamiento", default=config.FIN_ENTRENAMIENTO)
    parser.add_argument("--fin_validacion", default=config.FIN_VALIDACION)
    parser.add_argument("--umbral_riesgo", type=float, default=config.UMBRAL_RIESGO)
    parser.add_argument("--tracking_uri", default=os.environ.get("MLFLOW_TRACKING_URI", config.TRACKING_URI))
    return parser.parse_args()


def main():
    args = leer_argumentos()
    viajes = pd.read_parquet(config.ARCHIVO_VIAJES)
    estaciones = pd.read_parquet(config.ARCHIVO_ESTACIONES)
    mlflow.set_tracking_uri(args.tracking_uri)
    modelo = mlflow.sklearn.load_model(args.modelo_uri)

    if args.pregunta == "p1":
        _, _, prueba = features.conjuntos_p1(viajes, estaciones, args.fin_entrenamiento, args.fin_validacion)
        salida = prueba[["estacion_id", "fecha", features.OBJETIVO_P1]].copy()
        salida["prediccion"] = np.clip(modelo.predict(prueba[features.COLUMNAS_P1]), 0, None)
    elif args.pregunta == "p2":
        _, _, prueba = features.conjuntos_p2(viajes, estaciones, args.umbral_riesgo, config.VENTANA_RIESGO_HORAS,
                                             args.fin_entrenamiento, args.fin_validacion)
        salida = prueba[["estacion_id", "hora", features.OBJETIVO_P2]].copy()
        salida["prediccion"] = modelo.predict(prueba[features.COLUMNAS_P2])
        salida["probabilidad"] = modelo.predict_proba(prueba[features.COLUMNAS_P2])[:, 1]
    else:
        perfil = features.conjunto_p3(viajes, estaciones, args.fin_entrenamiento)
        columnas = [columna for columna in perfil.columns if columna not in ("estacion_id", "nombre", "latitud", "longitud")]
        salida = perfil[["estacion_id", "nombre", "latitud", "longitud"]].copy()
        salida["grupo"] = modelo.predict(perfil[columnas])

    ruta = args.salida or config.DIR_MODELOS / f"predicciones_{args.pregunta}.csv"
    config.DIR_MODELOS.mkdir(parents=True, exist_ok=True)
    salida.to_csv(ruta, index=False)
    print("Predicciones:", len(salida), "registros en", ruta)


if __name__ == "__main__":
    main()
