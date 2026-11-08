import json
from pathlib import Path

from api import esquemas, modelo

EJEMPLOS = Path(__file__).resolve().parents[1] / "api" / "ejemplos"


def _leer(nombre):
    return json.loads((EJEMPLOS / nombre).read_text(encoding="utf-8"))


def test_la_peticion_de_ejemplo_es_la_del_esquema_y_responde_200(cliente_api):
    peticion = _leer("peticion_p2.json")
    assert peticion == esquemas.EJEMPLO
    esquemas.PeticionRiesgo.model_validate(peticion)
    respuesta = cliente_api.post("/predecir", json=peticion)
    assert respuesta.status_code == 200
    esquemas.RespuestaRiesgo.model_validate(respuesta.json())


def test_el_lote_de_ejemplo_responde_una_prediccion_por_estacion(cliente_api):
    lote = _leer("peticion_lote.json")
    assert len(lote) >= 2 and len({peticion["estacion_id"] for peticion in lote}) == len(lote)
    assert len({(peticion["hora_dia"], peticion["dia_semana"]) for peticion in lote}) == 1
    for peticion in lote:
        esquemas.PeticionRiesgo.model_validate(peticion)
    respuesta = cliente_api.post("/predecir/lote", json=lote)
    assert respuesta.status_code == 200
    assert [fila["estacion_id"] for fila in respuesta.json()] == [peticion["estacion_id"] for peticion in lote]


def test_la_respuesta_de_ejemplo_tiene_la_forma_del_esquema_y_el_modelo_del_registry():
    respuesta = esquemas.RespuestaRiesgo.model_validate(_leer("respuesta_p2.json"))
    assert respuesta.estacion_id == _leer("peticion_p2.json")["estacion_id"]
    assert respuesta.riesgo == int(respuesta.probabilidad >= respuesta.umbral)
    assert respuesta.modelo.nombre == modelo.NOMBRE and respuesta.modelo.alias == modelo.ALIAS
    assert respuesta.modelo.version is not None


def test_los_ejemplos_no_traen_campos_fuera_del_esquema():
    campos = set(esquemas.PeticionRiesgo.model_fields)
    assert set(_leer("peticion_p2.json")) <= campos
    assert all(set(peticion) <= campos for peticion in _leer("peticion_lote.json"))
