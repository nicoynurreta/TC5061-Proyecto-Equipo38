"""Diagnóstico de concurrencia: predicciones por segundo del modelo servido según cuántos hilos predicen a la vez, dentro del contenedor."""
import argparse
import json
import sys
import threading
import time

from api import esquemas, modelo

ARCHIVO_CPU = "/sys/fs/cgroup/cpu.stat"


def leer_argumentos():
    parser = argparse.ArgumentParser(description="Mide las predicciones por segundo del modelo cargado con distinto número de hilos, sin pasar por HTTP.")
    parser.add_argument("--hilos", default="1,2,4,8,16", help="números de hilos que se prueban, separados por comas")
    parser.add_argument("--segundos", type=float, default=8, help="segundos que dura cada medición")
    return parser.parse_args()


def uso_de_cpu(archivo=ARCHIVO_CPU):
    """Contadores de CPU del contenedor (cgroup v2); vacío fuera de un contenedor."""
    try:
        with open(archivo, encoding="utf-8") as lectura:
            return {clave: int(valor) for clave, valor in (linea.split() for linea in lectura)}
    except OSError:
        return {}


def medir(predecir, hilos, segundos, archivo_cpu=ARCHIVO_CPU):
    """Predicciones por segundo de varios hilos que llaman a predecir sin pausa, con la CPU que consume cada predicción."""
    cuentas = [0] * hilos
    fin = time.monotonic() + segundos

    def trabajar(indice):
        while time.monotonic() < fin:
            predecir()
            cuentas[indice] += 1

    antes, inicio = uso_de_cpu(archivo_cpu), time.monotonic()
    grupo = [threading.Thread(target=trabajar, args=(indice,)) for indice in range(hilos)]
    for hilo in grupo:
        hilo.start()
    for hilo in grupo:
        hilo.join()
    duracion, despues, total = time.monotonic() - inicio, uso_de_cpu(archivo_cpu), sum(cuentas)
    fila = {"hilos": hilos, "predicciones": total, "predicciones_s": round(total / duracion, 2)}
    if antes and despues and total:
        consumo = despues["usage_usec"] - antes["usage_usec"]
        fila["cpu_ms_por_prediccion"] = round(consumo / 1000 / total, 2)
        fila["cpu_sistema_pct"] = round(100 * (despues["system_usec"] - antes["system_usec"]) / consumo, 1) if consumo else 0.0
        fila["periodos_frenados"] = despues.get("nr_throttled", 0) - antes.get("nr_throttled", 0)
    return fila


def main():
    args = leer_argumentos()
    cargado = modelo.cargar()
    peticion = esquemas.PeticionRiesgo(**esquemas.EJEMPLO)
    filas = [medir(lambda: modelo.predecir(cargado, [peticion]), int(hilos), args.segundos) for hilos in args.hilos.split(",")]
    print(json.dumps({"modelo": cargado["nombre"], "version": cargado["version"], "segundos": args.segundos, "filas": filas}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
