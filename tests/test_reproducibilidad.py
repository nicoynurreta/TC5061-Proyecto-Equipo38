import numpy as np
import pandas as pd
import pytest

from mibici import config, features
from mibici.modeling import train


def _conjuntos_p1():
    rng = np.random.default_rng(0)

    def bloque(n):
        rezago_7 = rng.integers(0, 30, n)
        df = pd.DataFrame({
            "rezago_1": rng.integers(0, 30, n),
            "rezago_7": rezago_7,
            "rezago_14": rng.integers(0, 30, n),
            "media_7": rng.uniform(0, 30, n),
            "media_28": rng.uniform(0, 30, n),
            "dia_semana": rng.integers(0, 7, n),
            "mes": rng.integers(1, 13, n),
            "fin_de_semana": rng.integers(0, 2, n),
            "capacidad": rng.integers(10, 40, n),
        })
        df[features.OBJETIVO_P1] = rezago_7 + rng.integers(-3, 4, n)
        return df[features.COLUMNAS_P1 + [features.OBJETIVO_P1]]

    return bloque(300), bloque(60), bloque(60)


def _conjuntos_p2():
    rng = np.random.default_rng(1)

    def bloque(n):
        df = pd.DataFrame({columna: rng.integers(0, 12, n) for columna in features.COLUMNAS_P2})
        df["neto_3h"] = (df["llegadas_h0"] + df["llegadas_h1"] + df["llegadas_h2"]
                         - df["salidas_h0"] - df["salidas_h1"] - df["salidas_h2"])
        df["neto_futuro_semana_anterior"] = rng.integers(-10, 11, n)
        df["riesgo_semana_anterior"] = rng.integers(0, 2, n)
        df["hora_dia"] = rng.integers(0, 24, n)
        df["dia_semana"] = rng.integers(0, 7, n)
        df["fin_de_semana"] = (df["dia_semana"] >= 5).astype(int)
        df["capacidad"] = rng.integers(10, 30, n)
        df[features.OBJETIVO_P2] = ((df["neto_3h"].abs() + rng.integers(0, 6, n)) >= 8).astype(int)
        return df.astype({columna: "float32" for columna in features.COLUMNAS_P2})

    return bloque(400), bloque(100), bloque(100)


def _perfil_p3():
    rng = np.random.default_rng(2)
    estaciones = 60
    columnas = [f"{tipo}_{dia}_{hora:02d}" for tipo in ("salidas", "llegadas") for dia in ("habil", "finde") for hora in range(24)]
    centros = rng.uniform(0, 1, (3, len(columnas)))
    valores = np.abs(np.vstack([centro + rng.normal(0, 0.05, (estaciones // 3, len(columnas))) for centro in centros]))
    perfil = pd.DataFrame(valores, columns=columnas)
    perfil["log_viajes"] = rng.uniform(4, 9, estaciones)
    perfil["proporcion_salidas"] = rng.uniform(0.3, 0.7, estaciones)
    identificacion = pd.DataFrame({
        "estacion_id": range(1, estaciones + 1),
        "nombre": [f"estacion {i}" for i in range(1, estaciones + 1)],
        "latitud": rng.uniform(20.6, 20.75, estaciones),
        "longitud": rng.uniform(-103.45, -103.3, estaciones),
    })
    return pd.concat([identificacion, perfil], axis=1)


def test_p1_hgb_reproduce_predicciones_y_metricas_con_la_misma_semilla():
    conjuntos = _conjuntos_p1()
    h = train.completar_hiperparametros("p1", "hgb", {"n_estimators": 50})
    primero = train.entrenar_p1("hgb", h, config.SEMILLA, conjuntos)
    segundo = train.entrenar_p1("hgb", h, config.SEMILLA, conjuntos)
    assert np.array_equal(primero["prediccion_prueba"], segundo["prediccion_prueba"])
    assert primero["metricas"] == segundo["metricas"]
    assert primero["modelo"].get_params()["random_state"] == config.SEMILLA


def test_p2_hgb_reproduce_umbral_probabilidades_y_metricas_con_la_misma_semilla():
    conjuntos = _conjuntos_p2()
    h = train.completar_hiperparametros("p2", "hgb", {"n_estimators": 50})
    primero = train.entrenar_p2("hgb", h, config.SEMILLA, conjuntos)
    segundo = train.entrenar_p2("hgb", h, config.SEMILLA, conjuntos)
    assert primero["umbral"] == segundo["umbral"] and primero["origen_umbral"] == "validacion"
    assert np.array_equal(primero["prediccion_prueba"], segundo["prediccion_prueba"])
    assert np.array_equal(primero["puntuacion_prueba"], segundo["puntuacion_prueba"])
    assert primero["metricas"] == segundo["metricas"]
    clasificador = primero["modelo"].estimator.estimator.named_steps["clasificador"]
    assert clasificador.get_params()["random_state"] == config.SEMILLA


def test_p3_kmeans_reproduce_grupos_y_metricas_con_la_misma_semilla():
    perfil = _perfil_p3()
    h = train.completar_hiperparametros("p3", "kmeans")
    primero = train.entrenar_p3("kmeans", h, config.SEMILLA, perfil)
    segundo = train.entrenar_p3("kmeans", h, config.SEMILLA, perfil)
    assert np.array_equal(primero["grupos"], segundo["grupos"])
    assert primero["metricas"] == segundo["metricas"]
    assert len(np.unique(primero["grupos"])) == h["k"]
    assert primero["modelo"].named_steps["kmeans"].get_params()["random_state"] == config.SEMILLA


@pytest.mark.lento
@pytest.mark.skipif(not (config.ARCHIVO_VIAJES.exists() and config.ARCHIVO_ESTACIONES.exists()),
                    reason="hace falta data/processed; se genera con make ingest")
def test_p1_ridge_reproduce_sobre_los_datos_reales():
    viajes, estaciones, _ = train.cargar_datos()
    conjuntos = features.conjuntos_p1(viajes, estaciones)
    h = train.completar_hiperparametros("p1", "ridge")
    primero = train.entrenar_p1("ridge", h, config.SEMILLA, conjuntos)
    segundo = train.entrenar_p1("ridge", h, config.SEMILLA, conjuntos)
    assert len(primero["prediccion_prueba"]) == len(conjuntos[2]) > 0
    assert np.array_equal(primero["prediccion_prueba"], segundo["prediccion_prueba"])
    assert primero["metricas"] == segundo["metricas"]
