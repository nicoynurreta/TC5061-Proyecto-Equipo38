import mlflow
import mlflow.pyfunc
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow import MlflowClient
from mlflow.models import infer_signature
from sklearn.linear_model import LogisticRegression

from mibici.modeling import registry


def _corrida_de_prueba(tmp_path):
    mlflow.set_tracking_uri("sqlite:///" + (tmp_path / "mlflow.db").as_posix())
    experimento = mlflow.create_experiment("prueba-registry", artifact_location=(tmp_path / "artefactos").as_uri())
    X = pd.DataFrame({"a": np.linspace(0, 1, 20), "b": np.linspace(1, 0, 20)})
    y = (X["a"] > 0.5).astype(int)
    modelo = LogisticRegression().fit(X, y)
    with mlflow.start_run(experiment_id=experimento, run_name="p2_prueba") as corrida:
        mlflow.log_params({"modelo": "regresion_logistica", "version_datos": "abc123", "threshold": 0.4,
                           "fin_entrenamiento": "2025-09-30", "fin_validacion": "2025-10-31"})
        mlflow.log_metric("test_costo", 123.0)
        mlflow.set_tags({"commit_git": "0123456789abcdef", "rama": "feat/prueba"})
        mlflow.sklearn.log_model(modelo, name="modelo", signature=infer_signature(X, modelo.predict(X)), input_example=X.head(3))
    return corrida.info.run_id, X


def test_registrar_version_con_linaje_y_alias(tmp_path):
    run_id, X = _corrida_de_prueba(tmp_path)
    cliente = MlflowClient()
    nombre, version = registry.registrar_version(cliente, "p2", run_id, "champion")
    assert nombre == registry.NOMBRES["p2"]
    registrado = cliente.get_registered_model(nombre)
    assert "P2" in registrado.description and "champion" in registrado.description
    detalle = cliente.get_model_version_by_alias(nombre, "champion")
    assert str(detalle.version) == version
    assert detalle.tags["run_id"] == run_id
    assert detalle.tags["commit_git"] == "0123456789abcdef"
    assert detalle.tags["version_datos"] == "abc123"
    assert detalle.tags["threshold"] == "0.4"
    assert detalle.tags["experimento"] == "prueba-registry"
    assert "test_costo 123.0000" in detalle.description
    cargado = mlflow.pyfunc.load_model(f"models:/{nombre}@champion")
    assert list(cargado.predict(X.head(3))) == [0, 0, 0]


def test_segunda_version_como_challenger(tmp_path):
    run_id, _ = _corrida_de_prueba(tmp_path)
    cliente = MlflowClient()
    registry.registrar_version(cliente, "p1", run_id, "champion")
    nombre, version = registry.registrar_version(cliente, "p1", run_id, "challenger")
    assert version == "2"
    assert str(cliente.get_model_version_by_alias(nombre, "champion").version) == "1"
    assert str(cliente.get_model_version_by_alias(nombre, "challenger").version) == "2"
