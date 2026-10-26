import argparse
import os

import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    precision_score,
    recall_score,
    root_mean_squared_error,
)

from mibici import config, features
from mibici.modeling.registry import NOMBRES


def leer_argumentos():
    parser = argparse.ArgumentParser(
        description="Predice con el modelo en producción de una pregunta (models:/<nombre>@champion) sobre el conjunto de prueba y guarda las predicciones en models/."
    )
    parser.add_argument("--pregunta", choices=["p1", "p2", "p3"], required=True)
    parser.add_argument("--modelo_uri", default=None,
                        help="URI del modelo en MLflow (por defecto models:/<nombre registrado de la pregunta>@champion)")
    parser.add_argument("--salida", default=None,
                        help="archivo CSV de salida (por defecto models/predicciones_<pregunta>.csv)")
    parser.add_argument("--fin_entrenamiento", default=config.FIN_ENTRENAMIENTO)
    parser.add_argument("--fin_validacion", default=config.FIN_VALIDACION)
    parser.add_argument("--umbral_riesgo", type=float, default=config.UMBRAL_RIESGO)
    parser.add_argument("--tracking_uri", default=os.environ.get("MLFLOW_TRACKING_URI", config.TRACKING_URI))
    return parser.parse_args()


def main():
    args = leer_argumentos()
    uri = args.modelo_uri or f"models:/{NOMBRES[args.pregunta]}@champion"
    viajes = pd.read_parquet(config.ARCHIVO_VIAJES)
    estaciones = pd.read_parquet(config.ARCHIVO_ESTACIONES)
    mlflow.set_tracking_uri(args.tracking_uri)
    modelo = mlflow.sklearn.load_model(uri)
    print("Modelo:", uri)

    if args.pregunta == "p1":
        _, _, prueba = features.conjuntos_p1(viajes, estaciones, args.fin_entrenamiento, args.fin_validacion)
        salida = prueba[["estacion_id", "fecha", features.OBJETIVO_P1]].copy()
        salida["prediccion"] = modelo.predict(prueba[features.COLUMNAS_P1])
        print("test_mae:", round(mean_absolute_error(salida[features.OBJETIVO_P1], salida["prediccion"]), 4))
        print("test_rmse:", round(root_mean_squared_error(salida[features.OBJETIVO_P1], salida["prediccion"]), 4))
    elif args.pregunta == "p2":
        _, _, prueba = features.conjuntos_p2(viajes, estaciones, args.umbral_riesgo, config.VENTANA_RIESGO_HORAS,
                                             args.fin_entrenamiento, args.fin_validacion)
        salida = prueba[["estacion_id", "hora", features.OBJETIVO_P2]].copy()
        salida["prediccion"] = modelo.predict(prueba[features.COLUMNAS_P2])
        salida["probabilidad"] = modelo.predict_proba(prueba[features.COLUMNAS_P2])[:, 1]
        real, prediccion = salida[features.OBJETIVO_P2], salida["prediccion"]
        matriz = confusion_matrix(real, prediccion, labels=[0, 1])
        print("umbral de decisión del modelo:", getattr(modelo, "threshold", "sin umbral"))
        print("test_recall:", round(recall_score(real, prediccion, zero_division=0), 4))
        print("test_precision:", round(precision_score(real, prediccion, zero_division=0), 4))
        print("test_f1:", round(f1_score(real, prediccion, zero_division=0), 4))
        print("test_falsos_positivos:", int(matriz[0, 1]), "test_falsos_negativos:", int(matriz[1, 0]))
        print("test_costo:", int(matriz[0, 1]) + config.COSTO_FALSO_NEGATIVO * int(matriz[1, 0]))
    else:
        perfil = features.conjunto_p3(viajes, estaciones, args.fin_entrenamiento)
        columnas = [columna for columna in perfil.columns if columna not in ("estacion_id", "nombre", "latitud", "longitud")]
        salida = perfil[["estacion_id", "nombre", "latitud", "longitud"]].copy()
        salida["grupo"] = modelo.predict(perfil[columnas])
        print("estaciones por grupo:", salida["grupo"].value_counts().sort_index().to_dict())

    ruta = args.salida or config.DIR_MODELOS / f"predicciones_{args.pregunta}.csv"
    config.DIR_MODELOS.mkdir(parents=True, exist_ok=True)
    salida.to_csv(ruta, index=False)
    print("Predicciones:", len(salida), "registros en", ruta)


if __name__ == "__main__":
    main()
