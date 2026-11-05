import os
from pathlib import Path

import mlflow
import mlflow.pyfunc
import pandas as pd
import yaml
from mlflow import MlflowClient

from api import esquemas

NOMBRE = "mibici-equipo38-p2-riesgo"
ALIAS = "champion"
TRACKING_URI_LOCAL = "sqlite:///mlflow.db"
CAMPOS = [campo for campo in esquemas.PeticionRiesgo.model_fields if campo != "estacion_id"]


def cargar():
    """Carga el modelo de P2 por nombre y alias desde el Model Registry o, si RUTA_MODELO existe, desde esa carpeta."""
    ruta = os.environ.get("RUTA_MODELO")
    if ruta:
        cargado = mlflow.pyfunc.load_model(ruta)
        return describir(cargado.get_raw_model(), cargado.metadata, ruta, version_exportada(ruta))
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", TRACKING_URI_LOCAL))
    version = MlflowClient().get_model_version_by_alias(NOMBRE, ALIAS)
    uri = f"models:/{NOMBRE}@{ALIAS}"
    cargado = mlflow.pyfunc.load_model(uri)
    return describir(cargado.get_raw_model(), cargado.metadata, uri, str(version.version), ALIAS)


def version_exportada(ruta):
    """Versión que mlflow artifacts download anota en registered_model_meta; None si la carpeta no salió del registry."""
    meta = Path(ruta) / "registered_model_meta"
    if not meta.is_file():
        return None
    datos = yaml.safe_load(meta.read_text(encoding="utf-8")) or {}
    return str(datos["model_version"]) if datos.get("model_name") == NOMBRE and "model_version" in datos else None


def describir(estimador, metadata, origen, version=None, alias=None):
    """Reúne el estimador con su identidad y con las columnas y los tipos de la firma, en el orden del entrenamiento."""
    firma = metadata.get_input_schema()
    columnas = firma.input_names()
    if sorted(columnas) != sorted(CAMPOS):
        raise ValueError(f"la firma del modelo no coincide con PeticionRiesgo: {columnas}")
    return {
        "estimador": estimador, "nombre": NOMBRE, "version": version, "alias": alias, "origen": origen,
        "run_id": metadata.run_id, "umbral": float(getattr(estimador, "threshold", 0.5)), "mlflow": mlflow.__version__,
        "columnas": columnas, "tipos": {columna.name: columna.type.to_pandas() for columna in firma.inputs},
    }


def predecir(modelo, peticiones):
    """Predice riesgo y probabilidad de cada petición con las columnas en el orden y los tipos de la firma."""
    filas = [peticion.model_dump(exclude={"estacion_id"}) for peticion in peticiones]
    entrada = pd.DataFrame(filas, columns=modelo["columnas"]).astype(modelo["tipos"])
    riesgos = modelo["estimador"].predict(entrada)
    probabilidades = modelo["estimador"].predict_proba(entrada)[:, 1]
    servido = esquemas.ModeloServido(nombre=modelo["nombre"], version=modelo["version"], alias=modelo["alias"])
    return [
        esquemas.RespuestaRiesgo(estacion_id=peticion.estacion_id, riesgo=int(riesgo),
                                 probabilidad=round(float(probabilidad), 6), umbral=modelo["umbral"], modelo=servido)
        for peticion, riesgo, probabilidad in zip(peticiones, riesgos, probabilidades)
    ]


def metadata(modelo):
    """Identidad del modelo cargado, columnas de la firma con su tipo y versión de MLflow que sirve."""
    columnas = [esquemas.ColumnaFirma(nombre=nombre, tipo=str(tipo)) for nombre, tipo in modelo["tipos"].items()]
    return esquemas.Metadata(nombre=modelo["nombre"], version=modelo["version"], alias=modelo["alias"],
                             origen=modelo["origen"], run_id=modelo["run_id"], umbral=modelo["umbral"],
                             columnas=columnas, mlflow=modelo["mlflow"])
