import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from mlflow.models import Model, infer_signature
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import FixedThresholdClassifier

from api import main, modelo
from mibici import features


def modelo_de_prueba():
    """Clasificador mínimo con la firma de P2 y el umbral dentro del modelo, descrito como el que carga la API."""
    rng = np.random.default_rng(7)
    X = pd.DataFrame(rng.integers(0, 10, (200, len(features.COLUMNAS_P2))), columns=features.COLUMNAS_P2).astype("float32")
    y = (X["llegadas_h0"] - X["salidas_h0"] > 3).astype(int)
    ajustado = FixedThresholdClassifier(FrozenEstimator(LogisticRegression().fit(X, y)), threshold=0.92).fit(X, y)
    metadata = Model(run_id="corrida_de_prueba", signature=infer_signature(X, ajustado.predict(X)))
    return modelo.describir(ajustado, metadata, "models:/prueba@champion", "7", "champion")


@pytest.fixture
def cliente_api():
    """Cliente de la API con el modelo de prueba inyectado, sin servidor ni Model Registry."""
    main.app.state.modelo = modelo_de_prueba()
    yield TestClient(main.app)
    main.app.state.modelo = None
