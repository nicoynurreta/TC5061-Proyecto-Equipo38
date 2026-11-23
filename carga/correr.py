"""Corre la prueba de carga contra el sistema levantado con Docker Compose y muestrea los recursos de los contenedores."""
import argparse
import http.client
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from carga import muestreador

RAIZ = Path(__file__).resolve().parents[1]
REPORTES = RAIZ / "reports" / "carga"
ESTACIONES = 472
MIXTA = {"memoria": "1g", "escalones": "2,4,6,8,10,15,20,30,60", "duracion": 60, "calentamiento": 10, "tamano_lote": 3, "etiquetas": []}
CORRIDAS = {
    "un_proceso": {**MIXTA, "procesos": 1, "cpus": "1.0"},
    "dos_procesos": {**MIXTA, "procesos": 2, "cpus": "2.0"},
    "dos_procesos_un_cpu": {**MIXTA, "procesos": 2, "cpus": "1.0"},
    "un_proceso_en_serie": {**MIXTA, "procesos": 1, "cpus": "1.0", "hilos": 1},
    "dos_procesos_en_serie": {**MIXTA, "procesos": 2, "cpus": "2.0", "hilos": 1},
    "lote_hora": {"procesos": 1, "cpus": "1.0", "memoria": "1g", "escalones": "1,2,4,8,12", "duracion": 45,
                  "calentamiento": 10, "tamano_lote": ESTACIONES, "etiquetas": ["lote"]},
}


def leer_argumentos():
    parser = argparse.ArgumentParser(description="Prueba de carga por escalones con Locust sobre el sistema de Compose, con muestreo de docker stats.")
    parser.add_argument("--solo", choices=sorted(CORRIDAS), action="append", help="corrida que se ejecuta; se puede repetir; sin la opción corren todas")
    parser.add_argument("--sufijo", default="", help="texto que se agrega al nombre de los archivos, por ejemplo _r2 para una repetición")
    parser.add_argument("--escalones", default="", help="usuarios por escalón separados por comas, en lugar de los de la corrida")
    parser.add_argument("--duracion", type=int, default=0, help="segundos por escalón, en lugar de los de la corrida")
    parser.add_argument("--intervalo", type=float, default=1.0, help="segundos de pausa entre dos lecturas de docker stats")
    parser.add_argument("--diagnostico", default="", metavar="HILOS",
                        help="en lugar de las corridas, mide dentro del contenedor las predicciones por segundo con estos hilos, por ejemplo 1,2,4,8,16")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="dirección del servicio en el anfitrión, para esperar a /health")
    parser.add_argument("--motor", default="docker", help="docker o podman")
    return parser.parse_args()


def componer(motor, argumentos, entorno, capturar=False):
    """Corre docker compose en la raíz del repositorio con las variables de la corrida."""
    return subprocess.run([motor, "compose", *argumentos], cwd=RAIZ, env=entorno, check=False, text=True, capture_output=capturar)


def consultar(url, ruta, espera=5):
    """Código HTTP y cuerpo JSON de un GET al servicio publicado en el anfitrión."""
    servidor, _, puerto = url.removeprefix("http://").partition(":")
    conexion = http.client.HTTPConnection(servidor, int(puerto or 80), timeout=espera)
    try:
        conexion.request("GET", ruta)
        respuesta = conexion.getresponse()
        cuerpo = respuesta.read()
        return respuesta.status, json.loads(cuerpo) if respuesta.status == 200 else None
    finally:
        conexion.close()


def esperar_salud(url, espera=300, pausa=0.25):
    """Segundos que tarda /health en responder 200 desde que se llama a la función."""
    inicio = time.monotonic()
    while time.monotonic() - inicio < espera:
        try:
            if consultar(url, "/health")[0] == 200:
                return round(time.monotonic() - inicio, 2)
        except OSError:
            pass
        time.sleep(pausa)
    raise TimeoutError(f"/health no respondió 200 en {espera} s; revisa docker compose logs api")


def desfase_del_reloj(motor, entorno):
    """Segundos que el reloj de los contenedores adelanta al del anfitrión, para alinear las lecturas de recursos con los escalones."""
    antes = time.time()
    salida = componer(motor, ["exec", "-T", "api", "python", "-c", "import time; print(time.time())"], entorno, capturar=True).stdout
    despues = time.time()
    try:
        return round(float(salida.strip()) - (antes + despues) / 2, 3)
    except ValueError:
        return 0.0


def correr(nombre, corrida, args, motor):
    """Recrea el servicio con la configuración de la corrida, lanza Locust y muestrea los recursos mientras dura."""
    escalones = args.escalones or corrida["escalones"]
    duracion = args.duracion or corrida["duracion"]
    archivo = nombre + args.sufijo
    hilos = corrida.get("hilos", 0)
    entorno = {**os.environ, "API_PROCESOS": str(corrida["procesos"]), "API_CPUS": corrida["cpus"], "API_MEMORIA": corrida["memoria"],
               "API_HILOS": str(hilos), "CARGA_NOMBRE": archivo, "CARGA_ESCALONES": escalones, "CARGA_DURACION": str(duracion),
               "CARGA_CALENTAMIENTO": str(corrida["calentamiento"]), "CARGA_TAMANO_LOTE": str(corrida["tamano_lote"])}
    print(f"[{datetime.now():%H:%M:%S}] {archivo}: {corrida['procesos']} proceso(s), {corrida['cpus']} CPU, "
          f"{hilos or 'sin límite de'} peticiones a la vez por proceso, escalones {escalones} de {duracion} s")
    if componer(motor, ["up", "-d", "--force-recreate", "--no-deps", "api"], entorno).returncode != 0:
        raise RuntimeError("docker compose no pudo recrear el servicio api; levanta antes el sistema completo")
    arranque = esperar_salud(args.url)
    sistema = {
        "corrida": archivo, "fecha": datetime.now().isoformat(timespec="seconds"), "procesos": corrida["procesos"],
        "cpus": float(corrida["cpus"]), "memoria": corrida["memoria"], "hilos": hilos, "arranque_s": arranque,
        "modelo": consultar(args.url, "/metadata")[1], "desfase_reloj_s": desfase_del_reloj(motor, entorno),
        "motor": subprocess.run([motor, "version", "--format", "{{.Server.Version}}"], capture_output=True, text=True, check=False).stdout.strip(),
    }
    (REPORTES / f"{archivo}_sistema.json").write_text(json.dumps(sistema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  servicio listo en {arranque} s con {sistema['modelo']['nombre']} versión {sistema['modelo']['version']}")
    parar = threading.Event()
    hilo = threading.Thread(target=muestreador.muestrear, daemon=True,
                            args=(REPORTES / f"{archivo}_recursos.csv", args.intervalo, parar, 0, motor))
    hilo.start()
    usuario = ["--user", f"{os.getuid()}:{os.getgid()}"] if os.name == "posix" else []
    locust = ["--profile", "carga", "run", "--rm", *usuario, "locust", "-f", "carga/locustfile.py", "--headless",
              "--host", "http://api:8000", "--html", f"reports/carga/{archivo}.html", "--csv", f"reports/carga/{archivo}",
              "--csv-full-history", "--only-summary", "--exit-code-on-error", "0"]
    if corrida["etiquetas"]:
        locust += ["--tags", *corrida["etiquetas"]]
    try:
        codigo = componer(motor, locust, entorno).returncode
    finally:
        parar.set()
        hilo.join(timeout=30)
    print(f"[{datetime.now():%H:%M:%S}] {archivo}: Locust terminó con código {codigo}; archivos en reports/carga/{archivo}*")
    return codigo


def diagnosticar(hilos, motor, corrida=CORRIDAS["un_proceso"]):
    """Corre carga/hilos.py en un contenedor del servicio con los límites de la corrida y guarda la medición en hilos.json."""
    entorno = {**os.environ, "API_PROCESOS": str(corrida["procesos"]), "API_CPUS": corrida["cpus"], "API_MEMORIA": corrida["memoria"],
               "API_HILOS": "0"}
    orden = ["run", "--rm", "--no-deps", "-T", "-v", f"{RAIZ / 'carga'}:/code/carga:ro", "api", "python", "-m", "carga.hilos", "--hilos", hilos]
    resultado = componer(motor, orden, entorno, capturar=True)
    if resultado.returncode != 0:
        print(resultado.stderr)
        return resultado.returncode
    medicion = {"fecha": datetime.now().isoformat(timespec="seconds"), "cpus": float(corrida["cpus"]), "memoria": corrida["memoria"],
                **json.loads(resultado.stdout)}
    (REPORTES / "hilos.json").write_text(json.dumps(medicion, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for fila in medicion["filas"]:
        print(f"  {fila['hilos']} hilo(s): {fila['predicciones_s']} predicciones por segundo")
    return 0


def main():
    args = leer_argumentos()
    motor = shutil.which(args.motor)
    if motor is None:
        raise SystemExit(f"{args.motor} no está en el PATH")
    REPORTES.mkdir(parents=True, exist_ok=True)
    if args.diagnostico:
        return diagnosticar(args.diagnostico, motor)
    codigos = [correr(nombre, CORRIDAS[nombre], args, motor) for nombre in (args.solo or list(CORRIDAS))]
    return max(codigos)


if __name__ == "__main__":
    sys.exit(main())
