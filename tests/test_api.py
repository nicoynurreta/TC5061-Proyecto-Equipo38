import os

import mlflow
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from mlflow import MlflowClient
from mlflow.models import Model, infer_signature
from sklearn.linear_model import LogisticRegression

from api import esquemas, main, modelo
from mibici import features


def test_predecir_responde_al_ejemplo_con_el_modelo_y_el_umbral(cliente_api):
    respuesta = cliente_api.post("/predecir", json=esquemas.EJEMPLO)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estacion_id"] == 2
    assert cuerpo["riesgo"] in (0, 1) and 0 <= cuerpo["probabilidad"] <= 1
    assert cuerpo["riesgo"] == int(cuerpo["probabilidad"] >= cuerpo["umbral"])
    assert cuerpo["umbral"] == 0.92
    assert cuerpo["modelo"] == {"nombre": modelo.NOMBRE, "version": "7", "alias": "champion"}
    assert set(cuerpo) == set(esquemas.RespuestaRiesgo.model_fields)


def test_estacion_id_es_opcional_y_se_devuelve_tal_cual(cliente_api):
    sin_estacion = {clave: valor for clave, valor in esquemas.EJEMPLO.items() if clave != "estacion_id"}
    cuerpo = cliente_api.post("/predecir", json=sin_estacion).json()
    assert cuerpo["estacion_id"] is None
    assert cuerpo["probabilidad"] == cliente_api.post("/predecir", json=esquemas.EJEMPLO).json()["probabilidad"]


def test_campo_faltante_devuelve_422(cliente_api):
    sin_capacidad = {clave: valor for clave, valor in esquemas.EJEMPLO.items() if clave != "capacidad"}
    respuesta = cliente_api.post("/predecir", json=sin_capacidad)
    assert respuesta.status_code == 422
    detalle = respuesta.json()["detail"]
    assert len(detalle) == 1 and detalle[0]["loc"] == ["body", "capacidad"] and detalle[0]["type"] == "missing"


def test_campo_de_mas_devuelve_422(cliente_api):
    respuesta = cliente_api.post("/predecir", json={**esquemas.EJEMPLO, "temperatura": 25})
    assert respuesta.status_code == 422
    detalle = respuesta.json()["detail"]
    assert detalle[0]["loc"] == ["body", "temperatura"] and detalle[0]["type"] == "extra_forbidden"


@pytest.mark.parametrize("campo, valor", [("hora_dia", 24), ("hora_dia", -1), ("dia_semana", 7), ("salidas_h0", -3),
                                          ("capacidad", 0), ("riesgo_semana_anterior", 2), ("llegadas_h1", 2.5),
                                          ("fin_de_semana", "si"), ("estacion_id", 0)])
def test_valor_fuera_de_rango_o_de_tipo_devuelve_422(cliente_api, campo, valor):
    respuesta = cliente_api.post("/predecir", json={**esquemas.EJEMPLO, campo: valor})
    assert respuesta.status_code == 422
    assert respuesta.json()["detail"][0]["loc"] == ["body", campo]


def test_variables_derivadas_incoherentes_devuelven_422(cliente_api):
    respuesta = cliente_api.post("/predecir", json={**esquemas.EJEMPLO, "neto_3h": 2})
    assert respuesta.status_code == 422 and "neto_3h" in respuesta.json()["detail"][0]["msg"]
    respuesta = cliente_api.post("/predecir", json={**esquemas.EJEMPLO, "fin_de_semana": 0})
    assert respuesta.status_code == 422 and "fin_de_semana" in respuesta.json()["detail"][0]["msg"]


def test_el_orden_de_los_campos_del_json_no_cambia_la_prediccion(cliente_api):
    invertido = dict(reversed(list(esquemas.EJEMPLO.items())))
    assert cliente_api.post("/predecir", json=invertido).json() == cliente_api.post("/predecir", json=esquemas.EJEMPLO).json()


def test_lote_devuelve_una_respuesta_por_peticion_en_el_mismo_orden(cliente_api):
    segunda = {**esquemas.EJEMPLO, "estacion_id": 3, "salidas_h0": 9, "llegadas_h0": 0, "neto_3h": -7}
    respuesta = cliente_api.post("/predecir/lote", json=[esquemas.EJEMPLO, segunda])
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert [fila["estacion_id"] for fila in cuerpo] == [2, 3]
    assert cuerpo[0] == cliente_api.post("/predecir", json=esquemas.EJEMPLO).json()
    assert cuerpo[1] == cliente_api.post("/predecir", json=segunda).json()
    con_error = cliente_api.post("/predecir/lote", json=[esquemas.EJEMPLO, {**segunda, "hora_dia": 24}])
    assert con_error.status_code == 422 and con_error.json()["detail"][0]["loc"] == ["body", 1, "hora_dia"]


def test_lote_vacio_devuelve_422(cliente_api):
    respuesta = cliente_api.post("/predecir/lote", json=[])
    assert respuesta.status_code == 422 and respuesta.json()["detail"][0]["type"] == "too_short"


def test_health_y_metadata_describen_el_modelo_cargado(cliente_api):
    assert cliente_api.get("/health").status_code == 200
    assert cliente_api.get("/health").json() == {"estado": "ok", "modelo": modelo.NOMBRE, "version": "7"}
    cuerpo = cliente_api.get("/metadata").json()
    assert cuerpo["nombre"] == modelo.NOMBRE and cuerpo["version"] == "7" and cuerpo["alias"] == "champion"
    assert cuerpo["origen"] == "models:/prueba@champion" and cuerpo["run_id"] == "corrida_de_prueba"
    assert [columna["nombre"] for columna in cuerpo["columnas"]] == features.COLUMNAS_P2
    assert {columna["tipo"] for columna in cuerpo["columnas"]} == {"float32"}
    assert cuerpo["umbral"] == 0.92 and cuerpo["mlflow"] == mlflow.__version__


def test_los_campos_del_esquema_son_las_columnas_de_p2_en_su_orden():
    assert modelo.CAMPOS == features.COLUMNAS_P2


def test_sin_modelo_cargado_responde_503():
    main.app.state.modelo = None
    cliente = TestClient(main.app)
    assert cliente.get("/health").status_code == 503
    assert cliente.get("/metadata").status_code == 503
    respuesta = cliente.post("/predecir", json=esquemas.EJEMPLO)
    assert respuesta.status_code == 503 and modelo.NOMBRE in respuesta.json()["detail"]


def test_version_exportada_lee_la_version_que_deja_mlflow_artifacts_download(tmp_path):
    assert modelo.version_exportada(tmp_path) is None
    meta = tmp_path / "registered_model_meta"
    meta.write_text("model_name: otro-modelo\nmodel_version: '3'\n", encoding="utf-8")
    assert modelo.version_exportada(tmp_path) is None
    meta.write_text(f"model_name: {modelo.NOMBRE}\nmodel_version: '1'\n", encoding="utf-8")
    assert modelo.version_exportada(str(tmp_path)) == "1"


def test_describir_rechaza_una_firma_distinta_al_esquema():
    X = pd.DataFrame({"a": [0.0, 1.0, 2.0, 3.0]})
    estimador = LogisticRegression().fit(X, [0, 0, 1, 1])
    metadata = Model(run_id="otra", signature=infer_signature(X, estimador.predict(X)))
    with pytest.raises(ValueError, match="firma"):
        modelo.describir(estimador, metadata, "models:/otra@champion")


@pytest.mark.lento
def test_el_champion_del_registry_responde_al_ejemplo():
    uri = os.environ.get("MLFLOW_TRACKING_URI", "")
    if not uri.startswith("http"):
        pytest.skip("hace falta MLFLOW_TRACKING_URI con el servidor de tracking del equipo")
    mlflow.set_tracking_uri(uri)
    try:
        version = MlflowClient().get_model_version_by_alias(modelo.NOMBRE, modelo.ALIAS)
    except Exception as error:
        pytest.skip(f"el registry en {uri} no responde: {error}")
    with TestClient(main.app) as cliente:
        assert cliente.get("/health").status_code == 200
        cuerpo = cliente.post("/predecir", json=esquemas.EJEMPLO).json()
        columnas = [columna["nombre"] for columna in cliente.get("/metadata").json()["columnas"]]
    main.app.state.modelo = None
    assert columnas == features.COLUMNAS_P2
    assert cuerpo["modelo"] == {"nombre": modelo.NOMBRE, "version": str(version.version), "alias": modelo.ALIAS}
    assert cuerpo["riesgo"] == int(cuerpo["probabilidad"] >= cuerpo["umbral"])
    if "threshold" in version.tags:
        assert cuerpo["umbral"] == float(version.tags["threshold"])
