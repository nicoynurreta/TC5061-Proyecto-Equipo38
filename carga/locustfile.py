"""Escenario de carga del servicio de predicción de P2: tres tareas ponderadas y usuarios que suben por escalones."""
import json
import os
import random
import time
from pathlib import Path

import gevent
import locust
from locust import FastHttpUser, LoadTestShape, constant_throughput, events, tag, task

from carga import escalones

RAIZ = Path(__file__).resolve().parents[1]
EJEMPLOS = RAIZ / "api" / "ejemplos"
PETICION = json.loads((EJEMPLOS / "peticion_p2.json").read_text(encoding="utf-8"))
EJEMPLO_LOTE = json.loads((EJEMPLOS / "peticion_lote.json").read_text(encoding="utf-8"))
USUARIOS = escalones.leer_escalones(os.environ.get("CARGA_ESCALONES"), [2, 4, 6, 8, 10, 15, 20, 30, 60])
DURACION = int(os.environ.get("CARGA_DURACION") or 60)
CALENTAMIENTO = int(os.environ.get("CARGA_CALENTAMIENTO") or 10)
TIEMPO_LIMITE = float(os.environ.get("CARGA_TIEMPO_LIMITE") or 5)
SEMILLA = int(os.environ.get("CARGA_SEMILLA") or 42)
LOTE = escalones.armar_lote(EJEMPLO_LOTE, int(os.environ.get("CARGA_TAMANO_LOTE") or len(EJEMPLO_LOTE)))
PESOS = {"individual": 6, "lote": 3, "salud": 1}
PREDICCIONES = {"/predecir": 1, "/predecir/lote": len(LOTE), "/health": 0}
MUESTRAS = []
INICIO = {}
random.seed(SEMILLA)


def comprobar(respuesta, valida):
    """Cuenta como fallo cualquier código distinto de 200 y cualquier cuerpo que no cumpla la condición."""
    if respuesta.status_code != 200:
        respuesta.failure(f"HTTP {respuesta.status_code}")
        return
    try:
        correcta = valida(respuesta.json())
    except (ValueError, KeyError, TypeError):
        correcta = False
    if correcta:
        respuesta.success()
    else:
        respuesta.failure("respuesta con contenido inesperado")


class Operador(FastHttpUser):
    """Cliente del servicio: a lo más una tarea por segundo, repartida entre predicción individual, lote y salud."""

    wait_time = constant_throughput(1)
    network_timeout = TIEMPO_LIMITE
    connection_timeout = TIEMPO_LIMITE

    def on_start(self):
        gevent.sleep(random.random())

    @tag("individual")
    @task(PESOS["individual"])
    def predecir(self):
        with self.client.post("/predecir", json=PETICION, catch_response=True) as respuesta:
            comprobar(respuesta, lambda cuerpo: cuerpo["riesgo"] == int(cuerpo["probabilidad"] >= cuerpo["umbral"]))

    @tag("lote")
    @task(PESOS["lote"])
    def predecir_lote(self):
        with self.client.post("/predecir/lote", json=LOTE, catch_response=True) as respuesta:
            comprobar(respuesta, lambda cuerpo: [fila["estacion_id"] for fila in cuerpo] == [fila["estacion_id"] for fila in LOTE])

    @tag("salud")
    @task(PESOS["salud"])
    def salud(self):
        with self.client.get("/health", catch_response=True) as respuesta:
            comprobar(respuesta, lambda cuerpo: cuerpo["estado"] == "ok")


class Escalones(LoadTestShape):
    """Sube los usuarios por escalones de la misma duración y termina la prueba al acabar el último."""

    def tick(self):
        escalon = int(self.get_run_time() // DURACION)
        if escalon >= len(USUARIOS):
            return None
        return USUARIOS[escalon], min(100, max(USUARIOS))


@events.test_start.add_listener
def al_iniciar(environment, **_):
    MUESTRAS.clear()
    INICIO["epoch"] = time.time()


@events.request.add_listener
def al_responder(name, response_time, exception, start_time, **_):
    MUESTRAS.append((start_time - INICIO["epoch"], name, response_time, exception is None))


@events.test_stop.add_listener
def al_terminar(environment, **_):
    prefijo = environment.parsed_options.csv_prefix
    if not prefijo:
        return
    escalones.escribir(f"{prefijo}_escalones.csv", escalones.resumir(MUESTRAS, USUARIOS, DURACION, CALENTAMIENTO, PREDICCIONES))
    escenario = {
        "inicio_epoch": INICIO["epoch"], "usuarios": USUARIOS, "duracion_s": DURACION, "calentamiento_s": CALENTAMIENTO,
        "tiempo_limite_s": TIEMPO_LIMITE, "tareas_por_usuario_y_segundo": 1, "semilla": SEMILLA, "pesos": PESOS, "tamano_lote": len(LOTE),
        "etiquetas": environment.parsed_options.tags or [], "destino": environment.host, "locust": locust.__version__,
    }
    Path(f"{prefijo}_escenario.json").write_text(json.dumps(escenario, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
