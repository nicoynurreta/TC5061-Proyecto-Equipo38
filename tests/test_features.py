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


def test_particion_p2_excluye_la_ventana_que_cruza_el_corte():
    horas = pd.date_range("2025-09-29", "2025-10-02 23:00", freq="h")
    df = pd.DataFrame({"estacion_id": 2, "hora": horas, "riesgo": 0})
    entrenamiento, validacion, _ = features.particion_temporal(df, "hora", "2025-09-30", "2025-10-01")
    recortado = features.sin_ventana_posterior(entrenamiento, "2025-09-30", ventana=2)
    assert len(entrenamiento) - len(recortado) == 2
    assert recortado["hora"].max() == pd.Timestamp("2025-09-30 21:00")
    assert len(features.sin_ventana_posterior(validacion, "2025-10-01", ventana=2)) == 22


def test_perfiles_p3_incluyen_estaciones_de_solo_llegada():
    perfil = features.perfiles_por_estacion(_viajes_de_prueba(), _estaciones_de_prueba(), viajes_minimos=1)
    assert sorted(perfil["estacion_id"]) == [2, 3]
    solo_llegada = perfil[perfil["estacion_id"] == 3].iloc[0]
    salidas = [columna for columna in perfil.columns if columna.startswith("salidas_")]
    assert solo_llegada[salidas].sum() == 0
    assert solo_llegada["proporcion_salidas"] == 0
    assert np.isclose(solo_llegada["log_viajes"], np.log1p(40))


def test_perfiles_p3_suman_uno_por_bloque():
    perfil = features.perfiles_por_estacion(_viajes_de_prueba(), _estaciones_de_prueba(), viajes_minimos=1)
    salidas = [columna for columna in perfil.columns if columna.startswith("salidas_")]
    llegadas = [columna for columna in perfil.columns if columna.startswith("llegadas_")]
    assert len(salidas) == 48 and len(llegadas) == 48
    assert np.allclose(perfil.loc[perfil["estacion_id"] == 2, salidas].sum(axis=1), 1)
    assert np.allclose(perfil.loc[perfil["estacion_id"] == 3, llegadas].sum(axis=1), 1)


def test_particion_temporal_en_la_fecha_exacta_del_corte():
    horas = pd.to_datetime(["2025-09-30 23:00:00", "2025-10-01 00:00:00", "2025-10-31 23:00:00", "2025-11-01 00:00:00"])
    entrenamiento, validacion, prueba = features.particion_temporal(pd.DataFrame({"hora": horas}), "hora", "2025-09-30", "2025-10-31")
    assert entrenamiento["hora"].tolist() == [pd.Timestamp("2025-09-30 23:00:00")]
    assert validacion["hora"].tolist() == [pd.Timestamp("2025-10-01 00:00:00"), pd.Timestamp("2025-10-31 23:00:00")]
    assert prueba["hora"].tolist() == [pd.Timestamp("2025-11-01 00:00:00")]


def test_particion_temporal_con_periodo_vacio():
    df = pd.DataFrame({"fecha": pd.date_range("2025-01-01", "2025-06-30", freq="D"), "salidas": 1})
    entrenamiento, validacion, prueba = features.particion_temporal(df, "fecha", "2025-09-30", "2025-10-31")
    assert len(entrenamiento) == len(df)
    assert validacion.empty and prueba.empty
    assert list(prueba.columns) == ["fecha", "salidas"]
    assert all(parte.empty for parte in features.particion_temporal(df.iloc[:0], "fecha", "2025-09-30", "2025-10-31"))


def test_sin_ventana_posterior_con_ventana_que_cubre_todo_el_bloque():
    df = pd.DataFrame({"estacion_id": 2, "hora": pd.date_range("2025-09-30 00:00", periods=24, freq="h"), "riesgo": 0})
    assert len(features.sin_ventana_posterior(df, "2025-09-30", ventana=24)) == 0
    assert len(features.sin_ventana_posterior(df, "2025-09-30", ventana=0)) == 24
    recortado = features.sin_ventana_posterior(df, "2025-09-30", ventana=23)
    assert recortado["hora"].tolist() == [pd.Timestamp("2025-09-30 00:00")]


def test_etiquetar_riesgo_descarta_las_horas_cuya_ventana_cruza_el_final():
    horas = pd.date_range("2025-03-01", periods=6, freq="h")
    horario = pd.concat([
        pd.DataFrame({"estacion_id": 2, "hora": horas, "salidas": 0, "llegadas": 6}),
        pd.DataFrame({"estacion_id": 3, "hora": horas[:4], "salidas": 6, "llegadas": 0}),
    ], ignore_index=True)
    etiquetado = features.etiquetar_riesgo(horario, _estaciones_de_prueba(), umbral=0.5, ventana=2)
    assert etiquetado.groupby("estacion_id")["hora"].max().tolist() == [horas[3], horas[1]]
    assert etiquetado["riesgo"].tolist() == [1, 1, 1, 1, 1, 1]
    vacio = features.etiquetar_riesgo(horario, _estaciones_de_prueba(), umbral=0.5, ventana=6)
    assert vacio.empty and "riesgo" in vacio.columns


def test_perfiles_p3_excluyen_estaciones_por_debajo_de_viajes_minimos():
    extra = pd.DataFrame({
        "viaje_id": range(100, 109),
        "inicio": pd.date_range("2025-03-01 09:00", periods=9, freq="D"),
        "fin": pd.date_range("2025-03-01 09:10", periods=9, freq="D"),
        "origen_id": [4] * 5 + [5] * 4,
        "destino_id": [5] * 5 + [4] * 4,
        "duracion_min": 10.0,
    })
    viajes = pd.concat([_viajes_de_prueba(), extra], ignore_index=True)
    nuevas = pd.DataFrame({"estacion_id": [4, 5], "nombre": ["c", "d"], "latitud": [20.65, 20.66],
                           "longitud": [-103.35, -103.36], "capacidad": [10, 10]})
    estaciones = pd.concat([_estaciones_de_prueba(), nuevas], ignore_index=True)
    assert sorted(features.perfiles_por_estacion(viajes, estaciones, viajes_minimos=9)["estacion_id"]) == [2, 3, 4, 5]
    assert sorted(features.perfiles_por_estacion(viajes, estaciones, viajes_minimos=10)["estacion_id"]) == [2, 3]


def test_perfiles_p3_sin_salidas_o_sin_llegadas_no_dejan_valores_indefinidos():
    perfil = features.perfiles_por_estacion(_viajes_de_prueba(), _estaciones_de_prueba(), viajes_minimos=1)
    numericas = perfil.drop(columns=["estacion_id", "nombre", "latitud", "longitud"])
    assert not numericas.isna().any().any()
    assert np.isfinite(numericas.to_numpy()).all()
    solo_salida = perfil[perfil["estacion_id"] == 2].iloc[0]
    llegadas = [columna for columna in perfil.columns if columna.startswith("llegadas_")]
    assert solo_salida[llegadas].sum() == 0 and solo_salida["proporcion_salidas"] == 1
