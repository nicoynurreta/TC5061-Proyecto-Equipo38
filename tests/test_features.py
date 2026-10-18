import numpy as np
import pandas as pd

from mibici import features


def _viajes_de_prueba():
    inicios = pd.date_range("2025-03-01 08:00", periods=40, freq="D")
    viajes = pd.DataFrame({
        "viaje_id": range(40),
        "inicio": inicios,
        "fin": inicios + pd.Timedelta(minutes=10),
        "origen_id": [2] * 40,
        "destino_id": [3] * 40,
        "duracion_min": 10.0,
    })
    return viajes


def _estaciones_de_prueba():
    return pd.DataFrame({"estacion_id": [2, 3], "nombre": ["a", "b"], "latitud": [20.6, 20.7],
                         "longitud": [-103.3, -103.4], "capacidad": [10, 10]})


def test_rezagos_p1_no_miran_el_dia_actual():
    diario = features.viajes_por_estacion_y_dia(_viajes_de_prueba())
    diario.loc[diario["fecha"] == "2025-03-20", "salidas"] = 100
    datos = features.construir_features_p1(diario, _estaciones_de_prueba())
    pico = datos[datos["fecha"] == "2025-03-20"].iloc[0]
    siguiente = datos[datos["fecha"] == "2025-03-21"].iloc[0]
    assert pico["rezago_1"] == 1 and pico["media_7"] == 1
    assert siguiente["rezago_1"] == 100
    assert datos["fecha"].min() == pd.Timestamp("2025-03-15")


def test_etiqueta_p2_usa_solo_la_ventana_posterior():
    horas = pd.date_range("2025-03-01", periods=6, freq="h")
    horario = pd.DataFrame({"estacion_id": 2, "hora": horas, "salidas": [0, 0, 8, 0, 0, 0], "llegadas": 0})
    etiquetado = features.etiquetar_riesgo(horario, _estaciones_de_prueba(), umbral=0.5, ventana=2)
    assert etiquetado["riesgo"].tolist() == [1, 1, 0, 0]
    assert len(etiquetado) == 4


def test_particion_temporal_no_mezcla_periodos():
    df = pd.DataFrame({"fecha": pd.date_range("2025-01-01", "2025-12-31", freq="D")})
    entrenamiento, validacion, prueba = features.particion_temporal(df, "fecha", "2025-09-30", "2025-10-31")
    assert entrenamiento["fecha"].max() < validacion["fecha"].min() < prueba["fecha"].min()
    assert len(entrenamiento) + len(validacion) + len(prueba) == len(df)


def test_perfiles_p3_suman_uno_por_bloque():
    perfil = features.perfiles_por_estacion(_viajes_de_prueba(), _estaciones_de_prueba(), viajes_minimos=1)
    salidas = [columna for columna in perfil.columns if columna.startswith("salidas_")]
    llegadas = [columna for columna in perfil.columns if columna.startswith("llegadas_")]
    assert len(salidas) == 48 and len(llegadas) == 48
    assert np.allclose(perfil.loc[perfil["estacion_id"] == 2, salidas].sum(axis=1), 1)
    assert np.allclose(perfil.loc[perfil["estacion_id"] == 3, llegadas].sum(axis=1), 1)
