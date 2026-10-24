from datetime import date, timedelta
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]

DIR_DATOS = RAIZ_PROYECTO / "data"
DIR_DATOS_CRUDOS = DIR_DATOS / "raw"
DIR_DATOS_INTERMEDIOS = DIR_DATOS / "interim"
DIR_DATOS_PROCESADOS = DIR_DATOS / "processed"
DIR_DATOS_EXTERNOS = DIR_DATOS / "external"
DIR_MODELOS = RAIZ_PROYECTO / "models"
DIR_REPORTES = RAIZ_PROYECTO / "reports"
DIR_FIGURAS = DIR_REPORTES / "figures"

URL_DATOS_ABIERTOS = "https://mibici.net/es/datos-abiertos/"
URL_NOMENCLATURA = "https://mibici.net/site/assets/files/1118/nomenclatura_2026_09.csv"

FECHA_INICIO = "2025-01-01"
FECHA_FIN = "2025-12-31"
FIN_ENTRENAMIENTO = "2025-09-30"
FIN_VALIDACION = "2025-10-31"

ARCHIVO_VIAJES = DIR_DATOS_PROCESADOS / "viajes.parquet"
ARCHIVO_ESTACIONES = DIR_DATOS_PROCESADOS / "estaciones.parquet"
ARCHIVO_MANIFIESTO = DIR_DATOS / "manifiesto.json"
ARCHIVO_ENTORNO = RAIZ_PROYECTO / "python_env.yaml"

DURACION_MINIMA_MIN = 1
DURACION_MAXIMA_MIN = 24 * 60
VENTANA_RIESGO_HORAS = 2
UMBRAL_RIESGO = 0.5
VIAJES_MINIMOS_PERFIL = 100
COSTO_FALSO_NEGATIVO = 5

SEMILLA = 42
EQUIPO = "38"
EXPERIMENTO = "mibici-equipo38"
TRACKING_URI = "sqlite:///" + (RAIZ_PROYECTO / "mlflow.db").as_posix()
REPOSITORIO = "https://github.com/nicoynurreta/TC5061-Proyecto-Equipo38"

HIPERPARAMETROS = {
    "p1": {
        "naive7": {},
        "hgb": {"learning_rate": 0.1, "n_estimators": 200, "max_depth": None},
        "bosque": {"n_estimators": 300, "max_depth": None, "min_samples_leaf": 5},
        "ridge": {"alpha": 1.0},
    },
    "p2": {
        "dummy": {},
        "regla_semana": {},
        "regresion_logistica": {"C": 1.0, "max_iter": 1000},
        "bosque": {"n_estimators": 200, "max_depth": None, "min_samples_leaf": 50},
        "hgb": {"learning_rate": 0.1, "n_estimators": 200, "max_depth": None},
    },
    "p3": {
        "kmeans": {"k": 4},
        "aglomerativo": {"k": 4},
        "kmeans_pca": {"k": 4, "componentes": 10},
    },
}

BUSQUEDAS = {
    "p1": {"hgb": {"fijos": {"n_estimators": 300}, "rejilla": {"learning_rate": [0.05, 0.1, 0.2], "max_depth": [4, 8, None]}}},
    "p2": {"hgb": {"fijos": {"n_estimators": 200}, "rejilla": {"learning_rate": [0.05, 0.1], "max_depth": [4, 8, None]}}},
    "p3": {"kmeans": {"fijos": {}, "rejilla": {"k": [3, 4, 5, 6, 7, 8]}}},
}


def meses_entre(inicio=FECHA_INICIO, fin=FECHA_FIN):
    """Meses AAAA-MM que cubre el rango de fechas del proyecto."""
    actual = date.fromisoformat(inicio).replace(day=1)
    ultimo = date.fromisoformat(fin)
    meses = []
    while actual <= ultimo:
        meses.append(actual.strftime("%Y-%m"))
        actual = (actual + timedelta(days=32)).replace(day=1)
    return meses


MESES = meses_entre()
