import numpy as np
from sklearn.cluster import KMeans

from mibici import config
from mibici.modeling import train


def test_valor_hiperparametro_respeta_el_tipo_del_valor_por_defecto():
    assert train.valor_hiperparametro("", 0.1) == 0.1
    assert train.valor_hiperparametro("0.05", 0.1) == 0.05
    assert train.valor_hiperparametro("300", 200) == 300
    assert train.valor_hiperparametro("8", None) == 8
    assert train.valor_hiperparametro("sin_limite", 4) is None
    assert train.valor_hiperparametro("0.3", None) == 0.3


def test_completar_hiperparametros_toma_los_valores_de_config():
    valores = train.completar_hiperparametros("p2", "hgb", {"learning_rate": 0.05})
    assert valores["learning_rate"] == 0.05
    assert valores["n_estimators"] == config.HIPERPARAMETROS["p2"]["hgb"]["n_estimators"]
    assert valores["threshold"] is None
    assert "threshold" not in train.completar_hiperparametros("p2", "regla_semana")


def test_etapa_de_trabajo_distingue_baseline_de_candidata():
    assert train.etapa_de_trabajo("p3", "kmeans", {"k": 4}) == "baseline"
    assert train.etapa_de_trabajo("p3", "kmeans", {"k": 3}) == "candidate"
    assert train.etapa_de_trabajo("p1", "naive7", {}) == "baseline"
    assert train.etapa_de_trabajo("p1", "hgb", train.completar_hiperparametros("p1", "hgb")) == "candidate"


def test_elegir_umbral_minimiza_el_costo_de_los_errores():
    real = np.array([1, 1, 0, 0, 0])
    probabilidad = np.array([0.9, 0.6, 0.5, 0.2, 0.1])
    umbral, costos = train.elegir_umbral(real, probabilidad, costo_falso_negativo=5)
    assert 0.5 < umbral <= 0.6
    assert min(costos) == 0


def test_metricas_clasificacion_incluyen_el_costo():
    real = np.array([1, 1, 0, 0, 0, 0])
    prediccion = np.array([1, 0, 1, 1, 0, 0])
    metricas = train.metricas_clasificacion(real, prediccion, prediccion.astype(float), "test")
    assert metricas["test_falsos_positivos"] == 2
    assert metricas["test_falsos_negativos"] == 1
    assert metricas["test_costo"] == 2 + config.COSTO_FALSO_NEGATIVO
    assert metricas["test_positivos"] == 2


def test_inercia_coincide_con_kmeans():
    rng = np.random.default_rng(0)
    X = np.vstack([rng.normal(0, 1, (30, 4)), rng.normal(6, 1, (30, 4))])
    kmeans = KMeans(n_clusters=2, n_init=5, random_state=0).fit(X)
    assert np.isclose(train.inercia(X, kmeans.labels_), kmeans.inertia_)
