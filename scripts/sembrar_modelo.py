"""Siembra un modelo de prueba de P2 en el Model Registry cuando el alias champion no existe (pipeline de CI y clones sin el registry del equipo)."""
import argparse
import os
import sys

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
import sklearn
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from mlflow.models import infer_signature
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import FixedThresholdClassifier

from api import modelo

EXPERIMENTO = "mibici-equipo38"
CORRIDA = "p2_modelo_de_prueba"
SEMILLA = 7
FILAS = 200
UMBRAL = 0.92
TIPOS_CONFIABLES = [
    "sklearn.frozen._frozen.FrozenEstimator",
    "sklearn.model_selection._classification_threshold.FixedThresholdClassifier",
]
DESCRIPCION = ("Modelo de prueba sembrado por scripts/sembrar_modelo.py: regresión logística sobre datos sintéticos con la firma de P2 "
               "y el umbral dentro del modelo. Comprueba que el sistema levanta y responde; no sirve para predecir.")


def leer_argumentos():
    parser = argparse.ArgumentParser(description="Registra un modelo de prueba de P2 como champion si el Model Registry no tiene uno.")
    parser.add_argument("--tracking_uri", default=os.environ.get("MLFLOW_TRACKING_URI", modelo.TRACKING_URI_LOCAL),
                        help="servidor de tracking; por defecto MLFLOW_TRACKING_URI")
    return parser.parse_args()


def entrenar():
    """Clasificador mínimo con las columnas de la firma de P2 y el umbral dentro del modelo, como el de tests/conftest.py."""
    rng = np.random.default_rng(SEMILLA)
    X = pd.DataFrame(rng.integers(0, 10, (FILAS, len(modelo.CAMPOS))), columns=modelo.CAMPOS).astype("float32")
    y = (X["llegadas_h0"] - X["salidas_h0"] > 3).astype(int)
    ajustado = FixedThresholdClassifier(FrozenEstimator(LogisticRegression().fit(X, y)), threshold=UMBRAL).fit(X, y)
    return ajustado, X


def vigente(cliente):
    """Versión a la que apunta el alias champion; None si el modelo o el alias no existen."""
    try:
        return cliente.get_model_version_by_alias(modelo.NOMBRE, modelo.ALIAS)
    except MlflowException:
        return None


def sembrar(tracking_uri):
    """Registra el modelo de prueba como champion solo si el registry no tiene uno; devuelve la versión y si se sembró."""
    mlflow.set_tracking_uri(tracking_uri)
    cliente = MlflowClient()
    version = vigente(cliente)
    if version is not None:
        return version, False
    ajustado, X = entrenar()
    mlflow.set_experiment(EXPERIMENTO)
    with mlflow.start_run(run_name=CORRIDA) as corrida:
        mlflow.log_params({"modelo": "regresion_logistica", "threshold": UMBRAL, "semilla": SEMILLA, "filas": FILAS,
                           "version_datos": "sinteticos"})
        mlflow.set_tags({"stage_of_work": "siembra", "question": "p2", "pregunta": "P2"})
        info = mlflow.sklearn.log_model(ajustado, name="modelo", signature=infer_signature(X, ajustado.predict(X)),
                                        input_example=X.head(5), skops_trusted_types=TIPOS_CONFIABLES,
                                        pip_requirements=[f"scikit-learn=={sklearn.__version__}"])
    if not cliente.search_registered_models(f"name='{modelo.NOMBRE}'"):
        cliente.create_registered_model(modelo.NOMBRE, tags={"origen": "siembra"}, description=DESCRIPCION)
    etiquetas = {"origen": "siembra", "datos": "sinteticos", "corrida": CORRIDA, "run_id": corrida.info.run_id,
                 "modelo": "regresion_logistica", "threshold": str(UMBRAL)}
    registrada = mlflow.register_model(info.model_uri, modelo.NOMBRE, tags=etiquetas)
    cliente.update_model_version(modelo.NOMBRE, registrada.version, description=DESCRIPCION)
    cliente.set_registered_model_alias(modelo.NOMBRE, modelo.ALIAS, registrada.version)
    return cliente.get_model_version(modelo.NOMBRE, registrada.version), True


def main():
    args = leer_argumentos()
    version, sembrado = sembrar(args.tracking_uri)
    destino = f"{modelo.NOMBRE}@{modelo.ALIAS}"
    if sembrado:
        print(f"modelo de prueba sembrado en {args.tracking_uri}: {destino} -> versión {version.version} "
              f"(corrida {CORRIDA}, umbral {UMBRAL})")
    else:
        print(f"el registry de {args.tracking_uri} ya tiene {destino}: versión {version.version} "
              f"(corrida {version.tags.get('corrida', version.run_id)}); no se siembra nada")
    return 0


if __name__ == "__main__":
    sys.exit(main())
