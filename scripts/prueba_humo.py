"""Prueba de humo del sistema levantado con Docker Compose: salud, metadatos, predicción individual, lote, validación y registry."""
import argparse
import http.client
import json
import sys
import time
from pathlib import Path
from urllib.parse import quote, urlsplit

RAIZ = Path(__file__).resolve().parents[1]
EJEMPLOS = RAIZ / "api" / "ejemplos"
MODELO = "mibici-equipo38-p2-riesgo"
ALIAS = "champion"
CAMPOS_RESPUESTA = {"estacion_id", "riesgo", "probabilidad", "umbral", "modelo"}


class Fallo(Exception):
    """Una comprobación de la prueba de humo no se cumplió."""


def leer_argumentos():
    parser = argparse.ArgumentParser(description="Comprueba que el servicio de predicción levantado con Compose responde y sirve el modelo del registry.")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="dirección del servicio de predicción")
    parser.add_argument("--mlflow", default="", help="dirección del servidor de MLflow; si se da, su champion se compara con la versión que sirve la API")
    parser.add_argument("--espera", type=int, default=120, help="segundos que se espera a que /health responda 200")
    return parser.parse_args()


def pedir(base, metodo, ruta, cuerpo=None, espera=30):
    """Código HTTP y cuerpo de una petición; el cuerpo vuelve como JSON cuando lo es y como texto cuando no."""
    partes = urlsplit(base)
    conexion = http.client.HTTPConnection(partes.hostname, partes.port or 80, timeout=espera)
    try:
        datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
        conexion.request(metodo, ruta, body=datos, headers={"Content-Type": "application/json"})
        respuesta = conexion.getresponse()
        texto = respuesta.read().decode("utf-8", errors="replace")
    finally:
        conexion.close()
    try:
        return respuesta.status, json.loads(texto)
    except ValueError:
        return respuesta.status, texto


def exigir(condicion, mensaje):
    if not condicion:
        raise Fallo(mensaje)


def esperar_salud(pedir_api, espera, pausa=2):
    """Reintenta /health hasta que responde 200 o se agota la espera; devuelve su cuerpo."""
    limite = time.monotonic() + espera
    while True:
        try:
            codigo, cuerpo = pedir_api("GET", "/health")
            if codigo == 200:
                return cuerpo
            ultimo = f"HTTP {codigo}"
        except OSError as error:
            ultimo = str(error)
        if time.monotonic() >= limite:
            raise Fallo(f"/health no respondió 200 en {espera} s ({ultimo})")
        time.sleep(pausa)


def coherente(prediccion):
    """La respuesta trae los campos del esquema y la clase es probabilidad >= umbral."""
    return (isinstance(prediccion, dict) and set(prediccion) == CAMPOS_RESPUESTA and prediccion["riesgo"] in (0, 1)
            and prediccion["riesgo"] == int(prediccion["probabilidad"] >= prediccion["umbral"])
            and prediccion["modelo"]["nombre"] == MODELO)


def revisar(pedir_api, peticion, lote, espera=120):
    """Recorre los endpoints del servicio y entrega una línea por cada comprobación superada."""
    salud = esperar_salud(pedir_api, espera)
    exigir(salud.get("estado") == "ok" and salud.get("modelo") == MODELO, f"/health no describe el modelo esperado: {salud}")
    yield f"GET  /health -> 200, modelo {salud['modelo']} versión {salud['version']}"

    codigo, metadata = pedir_api("GET", "/metadata")
    exigir(codigo == 200, f"/metadata respondió {codigo}")
    columnas = [columna["nombre"] for columna in metadata["columnas"]]
    campos = [campo for campo in peticion if campo != "estacion_id"]
    exigir(sorted(columnas) == sorted(campos), f"las columnas de la firma no son las de la petición de ejemplo: {columnas}")
    yield (f"GET  /metadata -> 200, alias {metadata['alias']}, {len(columnas)} columnas, umbral {metadata['umbral']}, "
           f"MLflow {metadata['mlflow']}")

    codigo, prediccion = pedir_api("POST", "/predecir", peticion)
    exigir(codigo == 200, f"/predecir respondió {codigo}: {prediccion}")
    exigir(coherente(prediccion) and prediccion["estacion_id"] == peticion.get("estacion_id"),
           f"/predecir devolvió una respuesta incoherente: {prediccion}")
    yield (f"POST /predecir -> 200, estación {prediccion['estacion_id']}: riesgo {prediccion['riesgo']}, "
           f"probabilidad {prediccion['probabilidad']}")

    codigo, predicciones = pedir_api("POST", "/predecir/lote", lote)
    exigir(codigo == 200, f"/predecir/lote respondió {codigo}: {predicciones}")
    exigir(all(coherente(fila) for fila in predicciones)
           and [fila["estacion_id"] for fila in predicciones] == [fila.get("estacion_id") for fila in lote],
           f"/predecir/lote devolvió una respuesta incoherente: {predicciones}")
    yield f"POST /predecir/lote -> 200, {len(predicciones)} predicciones en el orden de la petición"

    incompleta = {campo: valor for campo, valor in peticion.items() if campo != "capacidad"}
    codigo, detalle = pedir_api("POST", "/predecir", incompleta)
    exigir(codigo == 422, f"una petición sin capacidad debía responder 422 y respondió {codigo}: {detalle}")
    yield "POST /predecir sin capacidad -> 422"


def revisar_registry(pedir_api, pedir_mlflow):
    """El servidor de MLflow responde y su alias champion apunta a la versión que sirve la API."""
    codigo, _ = pedir_mlflow("GET", "/health")
    exigir(codigo == 200, f"el servidor de MLflow respondió {codigo} en /health")
    codigo, cuerpo = pedir_mlflow("GET", f"/api/2.0/mlflow/registered-models/alias?name={quote(MODELO)}&alias={ALIAS}")
    exigir(codigo == 200, f"el registry no tiene {MODELO}@{ALIAS} (HTTP {codigo})")
    version = cuerpo["model_version"]
    servida = str(pedir_api("GET", "/health")[1]["version"])
    exigir(str(version["version"]) == servida, f"el registry marca la versión {version['version']} como {ALIAS} y la API sirve la {servida}")
    origen = {etiqueta["key"]: etiqueta["value"] for etiqueta in version.get("tags", [])}.get("origen", "registry del equipo")
    return f"GET  registry -> 200, {MODELO}@{ALIAS} es la versión {version['version']} ({origen}), la que sirve la API"


def main():
    args = leer_argumentos()
    peticion = json.loads((EJEMPLOS / "peticion_p2.json").read_text(encoding="utf-8"))
    lote = json.loads((EJEMPLOS / "peticion_lote.json").read_text(encoding="utf-8"))

    def pedir_api(metodo, ruta, cuerpo=None):
        return pedir(args.url, metodo, ruta, cuerpo)

    def pedir_mlflow(metodo, ruta, cuerpo=None):
        return pedir(args.mlflow, metodo, ruta, cuerpo)

    print("servicio:", args.url)
    superadas = 0
    try:
        for linea in revisar(pedir_api, peticion, lote, args.espera):
            print(linea)
            superadas += 1
        if args.mlflow:
            print(revisar_registry(pedir_api, pedir_mlflow))
            superadas += 1
    except Fallo as error:
        print("prueba de humo fallida:", error)
        return 1
    print(f"prueba de humo superada: {superadas} comprobaciones")
    return 0


if __name__ == "__main__":
    sys.exit(main())
