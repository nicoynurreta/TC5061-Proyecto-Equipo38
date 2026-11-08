"""Manda una petición de ejemplo al servicio de predicción de P2 y muestra la respuesta."""
import argparse
import json
import sys
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[1]
PETICION = RAIZ / "api" / "ejemplos" / "peticion_p2.json"


def leer_argumentos():
    parser = argparse.ArgumentParser(description="Envía una petición de prueba al servicio de predicción y muestra la respuesta.")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="dirección del servicio (por defecto el contenedor local)")
    parser.add_argument("--peticion", default=str(PETICION),
                        help="archivo JSON con una petición o con una lista de peticiones para /predecir/lote")
    parser.add_argument("--salida", default="", help="archivo donde además se guarda la respuesta, por ejemplo api/ejemplos/respuesta_p2.json")
    return parser.parse_args()


def main():
    args = leer_argumentos()
    cuerpo = json.loads(Path(args.peticion).read_text(encoding="utf-8"))
    ruta = "/predecir/lote" if isinstance(cuerpo, list) else "/predecir"
    salud = requests.get(args.url + "/health", timeout=30)
    print("GET", args.url + "/health", "->", salud.status_code, salud.json())
    print("POST", args.url + ruta)
    print(json.dumps(cuerpo, indent=2, ensure_ascii=False))
    respuesta = requests.post(args.url + ruta, json=cuerpo, timeout=30)
    print("HTTP", respuesta.status_code)
    print(json.dumps(respuesta.json(), indent=2, ensure_ascii=False))
    if args.salida and respuesta.ok:
        destino = Path(args.salida)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(respuesta.json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if respuesta.ok else 1


if __name__ == "__main__":
    sys.exit(main())
