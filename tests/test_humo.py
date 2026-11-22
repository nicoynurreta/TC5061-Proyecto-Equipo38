import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from api import main, modelo
from scripts import prueba_humo

PETICION = json.loads((prueba_humo.EJEMPLOS / "peticion_p2.json").read_text(encoding="utf-8"))
LOTE = json.loads((prueba_humo.EJEMPLOS / "peticion_lote.json").read_text(encoding="utf-8"))


def _pedir(cliente):
    def pedir(metodo, ruta, cuerpo=None):
        respuesta = cliente.request(metodo, ruta, json=cuerpo)
        return respuesta.status_code, respuesta.json()
    return pedir


def _registry(version, origen=None, codigo=200):
    etiquetas = [{"key": "origen", "value": origen}] if origen else []

    def pedir(metodo, ruta, cuerpo=None):
        if ruta == "/health":
            return 200, "OK"
        return codigo, {"model_version": {"name": modelo.NOMBRE, "version": version, "tags": etiquetas}}
    return pedir


class _Manejador(BaseHTTPRequestHandler):
    def do_GET(self):
        cuerpo = b"OK" if self.path == "/health" else json.dumps({"ruta": self.path}).encode("utf-8")
        self.send_response(404 if self.path == "/no-existe" else 200)
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_POST(self):
        recibido = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({"recibido": recibido}).encode("utf-8"))

    def log_message(self, *argumentos):
        pass


def test_la_prueba_de_humo_recorre_los_cinco_pasos_con_el_servicio_sano(cliente_api):
    lineas = list(prueba_humo.revisar(_pedir(cliente_api), PETICION, LOTE, espera=0))
    assert len(lineas) == 5
    assert lineas[0] == f"GET  /health -> 200, modelo {modelo.NOMBRE} versión 7"
    assert "13 columnas" in lineas[1] and "umbral 0.92" in lineas[1]
    assert lineas[2].startswith("POST /predecir -> 200, estación 2")
    assert f"{len(LOTE)} predicciones" in lineas[3] and lineas[4].endswith("-> 422")


def test_la_prueba_de_humo_falla_si_el_servicio_no_tiene_modelo():
    main.app.state.modelo = None
    with pytest.raises(prueba_humo.Fallo, match="/health no respondió 200"):
        list(prueba_humo.revisar(_pedir(TestClient(main.app)), PETICION, LOTE, espera=0))


def test_la_prueba_de_humo_falla_si_una_respuesta_es_incoherente(cliente_api):
    pedir = _pedir(cliente_api)

    def con_clase_invertida(metodo, ruta, cuerpo=None):
        codigo, respuesta = pedir(metodo, ruta, cuerpo)
        if ruta == "/predecir" and codigo == 200:
            respuesta["riesgo"] = 1 - respuesta["riesgo"]
        return codigo, respuesta

    def con_lote_desordenado(metodo, ruta, cuerpo=None):
        codigo, respuesta = pedir(metodo, ruta, cuerpo)
        return codigo, respuesta[::-1] if ruta == "/predecir/lote" else respuesta

    with pytest.raises(prueba_humo.Fallo, match="/predecir devolvió una respuesta incoherente"):
        list(prueba_humo.revisar(con_clase_invertida, PETICION, LOTE, espera=0))
    with pytest.raises(prueba_humo.Fallo, match="/predecir/lote devolvió una respuesta incoherente"):
        list(prueba_humo.revisar(con_lote_desordenado, PETICION, LOTE, espera=0))


def test_coherente_exige_los_campos_del_esquema_y_la_clase_del_umbral():
    buena = {"estacion_id": 2, "riesgo": 0, "probabilidad": 0.2, "umbral": 0.92, "modelo": {"nombre": modelo.NOMBRE}}
    assert prueba_humo.coherente(buena)
    assert prueba_humo.coherente({**buena, "riesgo": 1, "probabilidad": 0.92})
    assert not prueba_humo.coherente({**buena, "riesgo": 1})
    assert not prueba_humo.coherente({**buena, "modelo": {"nombre": "otro"}})
    assert not prueba_humo.coherente({clave: valor for clave, valor in buena.items() if clave != "umbral"})
    assert not prueba_humo.coherente({"detail": "el modelo no está cargado"}) and not prueba_humo.coherente([buena])


def test_el_registry_debe_marcar_como_champion_la_version_que_sirve_la_api(cliente_api):
    pedir_api = _pedir(cliente_api)
    linea = prueba_humo.revisar_registry(pedir_api, _registry("7", "siembra"))
    assert "es la versión 7 (siembra)" in linea
    assert "(registry del equipo)" in prueba_humo.revisar_registry(pedir_api, _registry("7"))
    with pytest.raises(prueba_humo.Fallo, match="la API sirve la 7"):
        prueba_humo.revisar_registry(pedir_api, _registry("3"))
    with pytest.raises(prueba_humo.Fallo, match="el registry no tiene"):
        prueba_humo.revisar_registry(pedir_api, _registry("7", codigo=404))


def test_pedir_devuelve_json_o_texto_y_el_codigo_de_la_respuesta():
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), _Manejador)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    base = f"http://127.0.0.1:{servidor.server_address[1]}"
    try:
        assert prueba_humo.pedir(base, "GET", "/health") == (200, "OK")
        assert prueba_humo.pedir(base, "GET", "/metadata") == (200, {"ruta": "/metadata"})
        assert prueba_humo.pedir(base, "GET", "/no-existe") == (404, {"ruta": "/no-existe"})
        assert prueba_humo.pedir(base, "POST", "/predecir", {"capacidad": 15}) == (200, {"recibido": {"capacidad": 15}})
    finally:
        servidor.shutdown()
        servidor.server_close()
