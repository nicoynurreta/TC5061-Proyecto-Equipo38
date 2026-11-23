"""Muestrea con docker stats la CPU y la memoria de los contenedores del sistema y las guarda en un CSV."""
import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PROYECTO = "mibici"
COLUMNAS = ["epoch", "hora", "contenedor", "servicio", "cpu_pct", "mem_mib", "mem_limite_mib", "mem_pct", "red_entrada_mb",
            "red_salida_mb", "pids"]
UNIDADES = {"b": 1, "kb": 1e3, "mb": 1e6, "gb": 1e9, "tb": 1e12, "kib": 2**10, "mib": 2**20, "gib": 2**30, "tib": 2**40}
CANTIDAD = re.compile(r"\s*([0-9.]+(?:e[+-]?[0-9]+)?)\s*([A-Za-z]*)\s*")


def leer_argumentos():
    parser = argparse.ArgumentParser(description="Guarda en un CSV el uso de CPU y memoria de los contenedores del sistema, leído con docker stats.")
    parser.add_argument("--salida", default=str(RAIZ / "reports" / "carga" / "recursos.csv"), help="archivo CSV de salida")
    parser.add_argument("--intervalo", type=float, default=1.0, help="segundos de pausa entre dos lecturas de docker stats")
    parser.add_argument("--duracion", type=float, default=0, help="segundos que dura el muestreo; 0 muestrea hasta Ctrl+C")
    parser.add_argument("--motor", default="docker", help="docker o podman")
    return parser.parse_args()


def a_bytes(texto):
    """Convierte cantidades de docker stats como 183.4MiB, 1.2kB, 0B o 1e+03kB a bytes."""
    cantidad = CANTIDAD.fullmatch(texto)
    if cantidad is None:
        raise ValueError(f"cantidad de docker stats que no se entiende: {texto!r}")
    numero, unidad = cantidad.groups()
    return float(numero) * UNIDADES[unidad.lower() or "b"]


def servicio(contenedor, proyecto=PROYECTO):
    """Servicio de Compose al que pertenece un contenedor: mibici-api-1 es api y mibici-locust-run-3f2a es locust."""
    return contenedor.removeprefix(proyecto + "-").split("-")[0]


def interpretar(linea, epoch, proyecto=PROYECTO):
    """Fila del CSV a partir de una línea JSON de docker stats; None si el contenedor no es del sistema o no reporta cifras que se entiendan."""
    dato = json.loads(linea)
    if not dato["Name"].startswith(proyecto + "-") or "--" in dato["CPUPerc"] or "--" in dato["MemUsage"]:
        return None
    try:
        uso, limite = (a_bytes(parte) for parte in dato["MemUsage"].split("/"))
        entrada, salida = (a_bytes(parte) for parte in dato["NetIO"].split("/"))
    except (KeyError, ValueError):
        return None
    return {
        "epoch": round(epoch, 3), "hora": datetime.fromtimestamp(epoch).strftime("%H:%M:%S"), "contenedor": dato["Name"],
        "servicio": servicio(dato["Name"], proyecto), "cpu_pct": float(dato["CPUPerc"].rstrip("%")),
        "mem_mib": round(uso / 2**20, 2), "mem_limite_mib": round(limite / 2**20, 2),
        "mem_pct": float(dato["MemPerc"].rstrip("%")), "red_entrada_mb": round(entrada / 1e6, 3),
        "red_salida_mb": round(salida / 1e6, 3), "pids": int(dato["PIDs"]) if dato["PIDs"].isdigit() else 0,
    }


def leer_una_vez(motor, proyecto=PROYECTO):
    """Una lectura de docker stats de los contenedores en marcha del proyecto de Compose."""
    nombres = subprocess.run([motor, "ps", "--filter", f"label=com.docker.compose.project={proyecto}", "--format", "{{.Names}}"],
                             capture_output=True, text=True, check=False).stdout.split()
    if not nombres:
        return []
    salida = subprocess.run([motor, "stats", "--no-stream", "--format", "{{json .}}", *nombres],
                            capture_output=True, text=True, check=False).stdout
    epoch = time.time()
    filas = [interpretar(linea, epoch, proyecto) for linea in salida.splitlines() if linea.strip().startswith("{")]
    return [fila for fila in filas if fila is not None]


def muestrear(salida, intervalo=1.0, parar=None, duracion=0, motor="docker", proyecto=PROYECTO):
    """Escribe una fila por contenedor en cada lectura hasta que parar se activa o se cumple la duración; devuelve las lecturas."""
    ejecutable = shutil.which(motor)
    if ejecutable is None:
        raise FileNotFoundError(f"{motor} no está en el PATH")
    parar = parar or threading.Event()
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    limite = time.monotonic() + duracion if duracion else None
    lecturas = 0
    with open(salida, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS)
        escritor.writeheader()
        while not parar.is_set() and (limite is None or time.monotonic() < limite):
            filas = leer_una_vez(ejecutable, proyecto)
            if filas:
                escritor.writerows(filas)
                archivo.flush()
                lecturas += 1
            parar.wait(intervalo)
    return lecturas


def main():
    args = leer_argumentos()
    try:
        lecturas = muestrear(args.salida, args.intervalo, duracion=args.duracion, motor=args.motor)
    except KeyboardInterrupt:
        print("muestreo interrumpido; el CSV conserva las lecturas hechas")
        return 0
    print(f"{lecturas} lecturas en {args.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
