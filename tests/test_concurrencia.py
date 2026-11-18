import threading
import time
from concurrent.futures import ThreadPoolExecutor

import anyio
import pytest
from fastapi.testclient import TestClient

from api import esquemas, main, modelo


async def _cupos():
    return main.limitar_hilos()


def test_sin_la_variable_quedan_los_hilos_por_defecto(monkeypatch):
    monkeypatch.delenv("HILOS_PREDICCION", raising=False)
    assert anyio.run(_cupos) == 40
    monkeypatch.setenv("HILOS_PREDICCION", "")
    assert anyio.run(_cupos) == 40
    monkeypatch.setenv("HILOS_PREDICCION", "0")
    assert anyio.run(_cupos) == 40


@pytest.mark.parametrize("hilos", [1, 2, 8])
def test_hilos_prediccion_fija_las_peticiones_simultaneas_del_proceso(monkeypatch, hilos):
    monkeypatch.setenv("HILOS_PREDICCION", str(hilos))
    assert anyio.run(_cupos) == hilos


def test_un_valor_que_no_es_entero_detiene_el_arranque(monkeypatch):
    monkeypatch.setenv("HILOS_PREDICCION", "muchos")
    with pytest.raises(ValueError):
        anyio.run(_cupos)


def test_con_un_hilo_las_predicciones_se_atienden_de_una_en_una(monkeypatch, cliente_api):
    cargado = main.app.state.modelo
    predecir = modelo.predecir
    cerrojo = threading.Lock()
    activas, maximo = [], []

    def lenta(*argumentos):
        with cerrojo:
            activas.append(1)
            maximo.append(len(activas))
        time.sleep(0.03)
        with cerrojo:
            activas.pop()
        return predecir(*argumentos)

    monkeypatch.setenv("HILOS_PREDICCION", "1")
    monkeypatch.setattr(modelo, "cargar", lambda: cargado)
    monkeypatch.setattr(modelo, "predecir", lenta)
    with TestClient(main.app) as cliente:
        with ThreadPoolExecutor(6) as grupo:
            codigos = list(grupo.map(lambda _: cliente.post("/predecir", json=esquemas.EJEMPLO).status_code, range(6)))
    assert codigos == [200] * 6 and max(maximo) == 1
