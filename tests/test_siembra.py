import sys

import mlflow
import numpy as np
import pytest
from fastapi.testclient import TestClient
from mlflow import MlflowClient

from api import esquemas, main, modelo
from mibici import features
from scripts import sembrar_modelo


@pytest.fixture
def registry_vacio(tmp_path, monkeypatch):
    """Tracking temporal en SQLite, con el experimento ya creado para que los artefactos no caigan en el clon."""
    uri = "sqlite:///" + (tmp_path / "mlflow.db").as_posix()
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    mlflow.set_tracking_uri(uri)
    mlflow.create_experiment(sembrar_modelo.EXPERIMENTO, artifact_location=(tmp_path / "artefactos").as_uri())
    return uri


def test_el_modelo_de_prueba_tiene_la_firma_de_p2_y_el_umbral_dentro():
    ajustado, X = sembrar_modelo.entrenar()
    assert list(X.columns) == features.COLUMNAS_P2 == modelo.CAMPOS
    assert set(X.dtypes.astype(str)) == {"float32"} and len(X) == sembrar_modelo.FILAS
    assert ajustado.threshold == sembrar_modelo.UMBRAL
    assert np.array_equal(ajustado.predict(X), (ajustado.predict_proba(X)[:, 1] >= sembrar_modelo.UMBRAL).astype(int))
    otro, _ = sembrar_modelo.entrenar()
    assert np.array_equal(ajustado.predict_proba(X), otro.predict_proba(X))


def test_sembrar_registra_el_champion_una_sola_vez_y_lo_marca_como_modelo_de_prueba(registry_vacio, monkeypatch, capsys):
    version, sembrado = sembrar_modelo.sembrar(registry_vacio)
    cliente = MlflowClient()
    assert sembrado and str(version.version) == "1"
    assert str(cliente.get_model_version_by_alias(modelo.NOMBRE, modelo.ALIAS).version) == "1"
    assert version.tags["origen"] == "siembra" and version.tags["datos"] == "sinteticos"
    assert version.tags["threshold"] == str(sembrar_modelo.UMBRAL) and version.tags["corrida"] == sembrar_modelo.CORRIDA
    assert "no sirve para predecir" in version.description
    assert cliente.get_run(version.tags["run_id"]).data.params["version_datos"] == "sinteticos"
    de_nuevo, sembrado = sembrar_modelo.sembrar(registry_vacio)
    assert not sembrado and str(de_nuevo.version) == "1"
    assert len(cliente.search_model_versions(f"name='{modelo.NOMBRE}'")) == 1
    monkeypatch.setattr(sys, "argv", ["sembrar_modelo", "--tracking_uri", registry_vacio])
    assert sembrar_modelo.main() == 0
    assert "no se siembra nada" in capsys.readouterr().out


def test_el_servicio_carga_el_modelo_sembrado_y_responde_al_ejemplo(registry_vacio):
    sembrar_modelo.sembrar(registry_vacio)
    with TestClient(main.app) as cliente:
        assert cliente.get("/health").json() == {"estado": "ok", "modelo": modelo.NOMBRE, "version": "1"}
        cuerpo = cliente.post("/predecir", json=esquemas.EJEMPLO).json()
        columnas = [columna["nombre"] for columna in cliente.get("/metadata").json()["columnas"]]
    main.app.state.modelo = None
    assert columnas == features.COLUMNAS_P2
    assert cuerpo["umbral"] == sembrar_modelo.UMBRAL and cuerpo["riesgo"] == int(cuerpo["probabilidad"] >= cuerpo["umbral"])
    assert cuerpo["modelo"] == {"nombre": modelo.NOMBRE, "version": "1", "alias": modelo.ALIAS}
