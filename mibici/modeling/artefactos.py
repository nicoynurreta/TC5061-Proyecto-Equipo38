import json
import pickle
import shutil
import time
from pathlib import Path

import mlflow
import mlflow.data
import mlflow.sklearn
from mlflow.data.dataset_source_registry import get_dataset_source_from_json
from mlflow.models import infer_signature

from mibici import config

TIPOS_CONFIABLES = [
    "sklearn.ensemble._hist_gradient_boosting.predictor.TreePredictor",
    "sklearn.ensemble._hist_gradient_boosting._bitset.set_bitset_memoryview",
    "sklearn.tree._tree.Tree",
    "sklearn.frozen._frozen.FrozenEstimator",
    "sklearn.model_selection._classification_threshold.FixedThresholdClassifier",
]
SUBCARPETAS = ["plots", "data", "config"]


def preparar_carpeta(carpeta):
    """Crea las subcarpetas plots/, data/ y config/ en la carpeta temporal de la corrida."""
    carpeta = Path(carpeta)
    for nombre in SUBCARPETAS:
        (carpeta / nombre).mkdir(parents=True, exist_ok=True)
    return carpeta


def constantes_configuracion():
    """Constantes de config.py en un diccionario serializable, con las rutas relativas a la raíz del proyecto."""
    valores = {}
    for nombre in dir(config):
        if not nombre.isupper():
            continue
        valor = getattr(config, nombre)
        if isinstance(valor, Path):
            valor = "." if valor == config.RAIZ_PROYECTO else valor.relative_to(config.RAIZ_PROYECTO).as_posix()
        valores[nombre] = valor
    valores["TRACKING_URI"] = mlflow.get_tracking_uri()
    return valores


def registrar_configuracion(argumentos, hiperparametros, carpeta):
    """Escribe en config/ las constantes del proyecto, los argumentos de la corrida y el entorno declarado."""
    destino = Path(carpeta) / "config"
    destino.mkdir(parents=True, exist_ok=True)
    with open(destino / "config.json", "w", encoding="utf-8") as archivo:
        json.dump(constantes_configuracion(), archivo, indent=2, ensure_ascii=False)
    corrida = {"argumentos": vars(argumentos), "hiperparametros": hiperparametros}
    with open(destino / "argumentos.json", "w", encoding="utf-8") as archivo:
        json.dump(corrida, archivo, indent=2, ensure_ascii=False, default=str)
    if config.ARCHIVO_ENTORNO.exists():
        shutil.copy(config.ARCHIVO_ENTORNO, destino / config.ARCHIVO_ENTORNO.name)
    return destino


def registrar_datos(entrenamiento, pregunta, version_datos, carpeta, objetivo=None):
    """Copia el manifiesto a data/ y registra el conjunto de entrenamiento con mlflow.log_input."""
    destino = Path(carpeta) / "data"
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copy(config.ARCHIVO_MANIFIESTO, destino / config.ARCHIVO_MANIFIESTO.name)
    origen = {"uri": config.ARCHIVO_VIAJES.relative_to(config.RAIZ_PROYECTO).as_posix()}
    conjunto = mlflow.data.from_pandas(
        entrenamiento,
        source=get_dataset_source_from_json(json.dumps(origen), "local"),
        name=f"mibici_{pregunta}_entrenamiento",
        digest=version_datos,
        targets=objetivo,
    )
    mlflow.log_input(conjunto, context="training")
    return conjunto


def registrar_metricas(metricas, carpeta):
    """Registra las métricas en MLflow y las deja también en metricas.json."""
    metricas = {clave: float(valor) for clave, valor in metricas.items()}
    with open(Path(carpeta) / "metricas.json", "w", encoding="utf-8") as archivo:
        json.dump(metricas, archivo, indent=2)
    mlflow.log_metrics(metricas)
    return metricas


def registrar_modelo(modelo, ejemplo, salida=None, fuente="mibici/modeling/train.py"):
    """Registra el modelo con su firma y un ejemplo de entrada bajo el nombre modelo."""
    enteras = {columna: "float64" for columna in ejemplo.columns if str(ejemplo[columna].dtype).startswith("int")}
    ejemplo = ejemplo.astype(enteras)
    if salida is None:
        salida = modelo.predict(ejemplo)
    firma = infer_signature(ejemplo, salida)
    info = mlflow.sklearn.log_model(modelo, name="modelo", signature=firma, input_example=ejemplo.head(5),
                                    skops_trusted_types=TIPOS_CONFIABLES)
    mlflow.set_logged_model_tags(info.model_id, {"mlflow.source.name": fuente, "mlflow.source.git.repoURL": config.REPOSITORIO})
    return info


def tamano_modelo_mb(modelo):
    """Tamaño del modelo serializado, en megabytes."""
    if modelo is None:
        return 0.0
    return len(pickle.dumps(modelo)) / 1e6


def cronometrar(funcion, *argumentos):
    """Ejecuta una función y devuelve su resultado junto con los segundos que tardó."""
    inicio = time.perf_counter()
    resultado = funcion(*argumentos)
    return resultado, time.perf_counter() - inicio


def registrar_artefactos(carpeta):
    """Sube la carpeta temporal completa (plots/, data/, config/ y metricas.json) a la corrida."""
    mlflow.log_artifacts(str(carpeta))
