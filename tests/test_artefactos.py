import argparse
import json

import numpy as np
from sklearn.linear_model import LinearRegression

from mibici import config
from mibici.modeling import artefactos


def test_constantes_sin_rutas_absolutas():
    valores = artefactos.constantes_configuracion()
    json.dumps(valores)
    assert valores["RAIZ_PROYECTO"] == "."
    assert valores["ARCHIVO_MANIFIESTO"] == "data/manifiesto.json"
    assert valores["SEMILLA"] == config.SEMILLA
    raiz = config.RAIZ_PROYECTO.as_posix()
    for clave, valor in valores.items():
        if clave != "TRACKING_URI":
            assert raiz not in str(valor), clave


def test_registrar_configuracion_escribe_tres_archivos(tmp_path):
    argumentos = argparse.Namespace(pregunta="p3", modelo="kmeans", semilla=42)
    destino = artefactos.registrar_configuracion(argumentos, {"k": 4}, tmp_path)
    assert sorted(ruta.name for ruta in destino.iterdir()) == ["argumentos.json", "config.json", "python_env.yaml"]
    with open(destino / "argumentos.json", encoding="utf-8") as archivo:
        corrida = json.load(archivo)
    assert corrida["argumentos"]["modelo"] == "kmeans"
    assert corrida["hiperparametros"] == {"k": 4}


def test_preparar_carpeta_crea_subcarpetas(tmp_path):
    carpeta = artefactos.preparar_carpeta(tmp_path / "corrida")
    assert sorted(ruta.name for ruta in carpeta.iterdir()) == ["config", "data", "plots"]


def test_tamano_y_cronometro():
    assert artefactos.tamano_modelo_mb(None) == 0.0
    modelo = LinearRegression().fit(np.arange(10).reshape(-1, 1), np.arange(10))
    assert artefactos.tamano_modelo_mb(modelo) > 0
    resultado, segundos = artefactos.cronometrar(sum, [1, 2, 3])
    assert resultado == 6 and segundos >= 0
