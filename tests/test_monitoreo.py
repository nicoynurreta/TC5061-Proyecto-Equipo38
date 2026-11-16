import json

import numpy as np
import pandas as pd
import pytest
import yaml
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import FixedThresholdClassifier

from mibici import config, dataset, features
from mibici.monitoreo import costos, datos, desempeno, drift


def _viajes(inicio, fin, semilla, primer_id=0):
    rng = np.random.default_rng(semilla)
    dias = pd.date_range(inicio, fin, freq="D")
    partes = []
    for estacion, base in zip(range(2, 8), [3, 6, 4, 8, 5, 7]):
        salidas = base + (dias.dayofweek >= 5) * 2 + rng.integers(0, 3, len(dias))
        hora = dias.repeat(salidas) + pd.to_timedelta(rng.integers(6, 22, salidas.sum()), unit="h")
        partes.append(pd.DataFrame({"inicio": hora, "origen_id": estacion, "destino_id": 2 + (estacion - 1) % 6}))
    viajes = pd.concat(partes, ignore_index=True).sort_values("inicio").reset_index(drop=True)
    viajes["fin"] = viajes["inicio"] + pd.Timedelta(minutes=12)
    viajes["duracion_min"] = 12.0
    viajes.insert(0, "viaje_id", range(primer_id, primer_id + len(viajes)))
    return viajes[["viaje_id", "inicio", "fin", "origen_id", "destino_id", "duracion_min"]]


def _estaciones():
    return pd.DataFrame({"estacion_id": range(2, 8), "nombre": list("abcdef"),
                         "latitud": np.linspace(20.6, 20.75, 6), "longitud": np.linspace(-103.45, -103.3, 6),
                         "capacidad": [12, 20, 16, 24, 18, 22]})


def _tabla_de_monitoreo(desplazamiento=0, estacion_nueva=None):
    rng = np.random.default_rng(3)
    horas = pd.date_range("2025-01-08", "2026-10-31 18:00", freq="6h")
    partes = []
    for estacion in [2, 3, 4] + ([estacion_nueva] if estacion_nueva else []):
        n = len(horas)
        df = pd.DataFrame({columna: rng.integers(0, 12, n) for columna in features.COLUMNAS_P2})
        df["neto_3h"] = (df["llegadas_h0"] + df["llegadas_h1"] + df["llegadas_h2"]
                         - df["salidas_h0"] - df["salidas_h1"] - df["salidas_h2"])
        df["neto_futuro_semana_anterior"] = rng.integers(-10, 11, n)
        df["riesgo_semana_anterior"] = rng.integers(0, 2, n)
        df["hora_dia"] = horas.hour
        df["dia_semana"] = horas.dayofweek
        df["fin_de_semana"] = (df["dia_semana"] >= 5).astype(int)
        df["capacidad"] = 10 + estacion
        df[features.OBJETIVO_P2] = ((df["neto_3h"].abs() + rng.integers(0, 6, n)) >= 12).astype(int)
        df["probabilidad"] = np.clip(0.15 + 0.5 * df[features.OBJETIVO_P2] + rng.normal(0, 0.15, n), 0, 1)
        df.insert(0, "hora", horas)
        df.insert(0, "estacion_id", estacion)
        partes.append(df[df["hora"] >= "2026-01-01"] if estacion == estacion_nueva else df)
    tabla = pd.concat(partes, ignore_index=True)
    es_actual = tabla["hora"] >= pd.Timestamp(config.FECHA_INICIO_ACTUAL)
    tabla.loc[es_actual, "salidas_h0"] += desplazamiento
    tabla = tabla.astype({columna: "float32" for columna in features.COLUMNAS_P2})
    tabla["prediccion"] = (tabla["probabilidad"] >= 0.5).astype("int8")
    en_2025 = np.select([tabla["hora"] <= pd.Timestamp(config.FIN_ENTRENAMIENTO) + pd.Timedelta(hours=23),
                         tabla["hora"] <= pd.Timestamp(config.FIN_VALIDACION) + pd.Timedelta(hours=23)],
                        ["referencia", "validacion_2025"], "prueba_2025")
    tabla["conjunto"] = np.where(es_actual, datos.asignar_conjunto(tabla["hora"]), en_2025)
    return tabla


def _detalle(tabla):
    return {"modelo": {"nombre": "mibici-equipo38-p2-riesgo", "version": "1", "corrida": "p2_prueba", "umbral": 0.5},
            "version_datos": "abc123", "version_datos_actual": "def456", "ventanas": datos.ventanas(),
            "conjuntos": datos.resumen_conjuntos(tabla)}


def _manifiesto(meses, con_detalle=False):
    limpieza = {"registros_crudos": 1000, "sin_fecha_o_estacion": 0, "duplicados": 2, "duracion_negativa": 0,
                "duracion_menor_1_min": 30, "duracion_mayor_24_h": 1}
    crudos = [{"archivo": f"datos_abiertos_{mes.replace('-', '_')}.csv", "codificacion": "utf-8", "registros": 1000,
               **({"viajes_validos": 967, "limpieza": limpieza} if con_detalle else {})} for mes in meses]
    total = {clave: valor * len(meses) for clave, valor in limpieza.items()}
    return {"meses": meses, "limpieza": {**total, "duplicados_entre_meses": 0}, "archivos_crudos": crudos,
            "resumen": {"viajes": 967 * len(meses), "estaciones_con_viajes": 6, "viajes_con_estacion_fuera_de_nomenclatura": 4}}


def test_las_ventanas_cubren_los_dos_periodos_sin_huecos_ni_traslapes():
    ventanas = datos.ventanas()
    assert list(ventanas) == datos.CONJUNTOS
    for anterior, siguiente in [("referencia", "validacion_2025"), ("validacion_2025", "prueba_2025"),
                                ("actual", "evaluacion"), ("evaluacion", "confirmacion")]:
        assert datos.dia_siguiente(ventanas[anterior][1]) == ventanas[siguiente][0]
    assert ventanas["referencia"] == [config.FECHA_INICIO, config.FIN_ENTRENAMIENTO]
    assert ventanas["actual"][0] == config.FECHA_INICIO_ACTUAL and ventanas["confirmacion"][1] == config.FECHA_FIN_ACTUAL
    assert config.FIN_REENTRENAMIENTO < config.FIN_MONITOREO < config.FIN_EVALUACION <= config.FECHA_FIN_ACTUAL


def test_asignar_conjunto_respeta_los_cortes_de_config():
    horas = pd.to_datetime(["2026-01-01 00:00", "2026-06-30 23:00", "2026-07-01 00:00", "2026-09-30 23:00", "2026-10-01 00:00"])
    assert list(datos.asignar_conjunto(horas)) == ["actual", "actual", "evaluacion", "evaluacion", "confirmacion"]


def test_armar_tabla_conserva_la_particion_de_2025_y_agrega_el_periodo_actual():
    viajes, estaciones = _viajes("2025-01-01", "2025-12-31", 4), _estaciones()
    viajes_actual = _viajes("2026-01-01", "2026-10-31", 5, primer_id=len(viajes))
    tabla = datos.armar_tabla(viajes, viajes_actual, estaciones)
    entrenamiento, validacion, prueba = features.conjuntos_p2(viajes, estaciones)
    conteo = tabla["conjunto"].value_counts()
    assert list(tabla.columns) == ["estacion_id", "hora"] + features.COLUMNAS_P2 + [features.OBJETIVO_P2, "conjunto"]
    assert set(conteo.index) == set(datos.CONJUNTOS)
    assert (conteo["referencia"], conteo["validacion_2025"], conteo["prueba_2025"]) == (len(entrenamiento), len(validacion), len(prueba))
    referencia = tabla[tabla["conjunto"] == "referencia"].reset_index(drop=True)
    pd.testing.assert_frame_equal(referencia[features.COLUMNAS_P2], entrenamiento[features.COLUMNAS_P2].reset_index(drop=True))
    limites = tabla.groupby("conjunto")["hora"].agg(["min", "max"])
    assert limites.loc["actual", "min"] == pd.Timestamp("2026-01-01 00:00")
    assert limites.loc["actual", "max"] == pd.Timestamp("2026-06-30 23:00")
    assert limites.loc["evaluacion", "min"] == pd.Timestamp("2026-07-01 00:00")
    assert limites.loc["evaluacion", "max"] == pd.Timestamp("2026-09-30 23:00")
    assert limites.loc["confirmacion", "min"] == pd.Timestamp("2026-10-01 00:00")
    assert not tabla.duplicated(["estacion_id", "hora"]).any()


def test_agregar_predicciones_aplica_el_umbral_que_viaja_en_el_modelo():
    tabla = _tabla_de_monitoreo().drop(columns=["probabilidad", "prediccion"]).head(400)
    X, y = tabla[features.COLUMNAS_P2], tabla[features.OBJETIVO_P2]
    modelo = FixedThresholdClassifier(FrozenEstimator(LogisticRegression(max_iter=500).fit(X, y)), threshold=0.3).fit(X, y)
    con_salidas = datos.agregar_predicciones(tabla, modelo)
    assert "probabilidad" not in tabla.columns
    assert con_salidas["probabilidad"].between(0, 1).all()
    assert (con_salidas["prediccion"] == (con_salidas["probabilidad"] >= 0.3)).all()
    assert con_salidas["prediccion"].nunique() == 2


def test_ingerir_escribe_archivos_aparte_y_no_toca_los_de_2025(tmp_path, monkeypatch, capsys):
    meses = {
        "2026-01": pd.DataFrame({
            "Viaje_Id": [1, 2, 3, 4], "Usuario_Id": [10, 11, 12, 13], "Genero": ["M", "F", "M", None],
            "Año_de_nacimiento": [1990, 1985, 2000, 1970],
            "Inicio_del_viaje": ["2026-01-05 08:00:00", "2026-01-05 09:00:00", "2026-01-06 10:00:00", "2026-01-07 11:00:00"],
            "Fin_del_viaje": ["2026-01-05 08:15:00", "2026-01-05 09:00:20", "2026-01-06 10:20:00", "2026-01-07 11:30:00"],
            "Origen_Id": [2, 3, 4, 99], "Destino_Id": [3, 4, 5, 2]}),
        "2026-02": pd.DataFrame({
            "Viaje_Id": [4, 5, 6], "Usuario_Id": [13, 14, 15], "Genero": ["F", "M", "F"], "Año_de_nacimiento": [1970, 1999, 2001],
            "Inicio_del_viaje": ["2026-02-01 08:00:00", "2026-02-02 08:00:00", "2026-02-03 08:00:00"],
            "Fin_del_viaje": ["2026-02-01 08:10:00", "2026-02-02 08:25:00", "2026-02-03 08:05:00"],
            "Origen_Id": [2, 5, 6], "Destino_Id": [7, 6, 7]}),
    }

    def descargar(url, destino, forzar=False):
        mes = destino.stem[-7:].replace("_", "-")
        meses[mes].to_csv(destino, index=False, encoding="utf-8")
        return destino.stat().st_size

    rutas = {"DIR_DATOS_CRUDOS": tmp_path / "raw", "ARCHIVO_ESTACIONES": tmp_path / "estaciones.parquet",
             "ARCHIVO_VIAJES": tmp_path / "viajes.parquet", "ARCHIVO_MANIFIESTO": tmp_path / "manifiesto.json",
             "ARCHIVO_VIAJES_ACTUAL": tmp_path / "viajes_actual.parquet", "ARCHIVO_MANIFIESTO_ACTUAL": tmp_path / "manifiesto_actual.json"}
    for nombre, ruta in rutas.items():
        monkeypatch.setattr(config, nombre, ruta)
    _estaciones().to_parquet(rutas["ARCHIVO_ESTACIONES"], index=False)
    rutas["ARCHIVO_VIAJES"].write_bytes(b"viajes de 2025")
    rutas["ARCHIVO_MANIFIESTO"].write_text("{\"version_datos\": \"abc123\"}", encoding="utf-8")
    monkeypatch.setattr(dataset, "obtener_enlaces", lambda: {mes: f"https://portal.invalid/datos_abiertos_{mes.replace('-', '_')}.csv" for mes in meses})
    monkeypatch.setattr(dataset, "descargar", descargar)

    manifiesto = datos.ingerir(["2026-01", "2026-02"])
    viajes = pd.read_parquet(rutas["ARCHIVO_VIAJES_ACTUAL"])
    assert viajes["viaje_id"].tolist() == [1, 3, 4, 5, 6]
    assert not {"usuario_id", "genero", "anio_nacimiento"} & set(viajes.columns)
    assert viajes.loc[viajes["viaje_id"] == 4, "origen_conocido"].tolist() == [False]
    assert manifiesto == json.loads(rutas["ARCHIVO_MANIFIESTO_ACTUAL"].read_text(encoding="utf-8"))
    assert manifiesto["meses"] == ["2026-01", "2026-02"]
    assert manifiesto["resumen"]["viajes"] == 5 and manifiesto["resumen"]["viajes_con_estacion_fuera_de_nomenclatura"] == 1
    assert manifiesto["limpieza"]["registros_crudos"] == 7
    assert manifiesto["limpieza"]["duracion_menor_1_min"] == 1 and manifiesto["limpieza"]["duplicados_entre_meses"] == 1
    assert [archivo["viajes_validos"] for archivo in manifiesto["archivos_crudos"]] == [3, 3]
    assert all(len(archivo["sha256"]) == 64 for archivo in manifiesto["archivos_crudos"] + [manifiesto["nomenclatura"]])
    assert len(manifiesto["version_datos"]) == 12
    assert rutas["ARCHIVO_VIAJES"].read_bytes() == b"viajes de 2025"
    assert json.loads(rutas["ARCHIVO_MANIFIESTO"].read_text(encoding="utf-8")) == {"version_datos": "abc123"}
    assert "Viajes válidos: 5" in capsys.readouterr().out


def test_ingerir_se_detiene_si_el_portal_no_publica_un_mes(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARCHIVO_ESTACIONES", tmp_path / "estaciones.parquet")
    _estaciones().to_parquet(tmp_path / "estaciones.parquet", index=False)
    monkeypatch.setattr(dataset, "obtener_enlaces", lambda: {"2026-01": "https://portal.invalid/datos_abiertos_2026_01.csv"})
    with pytest.raises(SystemExit, match="2026-12"):
        datos.ingerir(["2026-01", "2026-12"])


def test_exportar_sin_datos_procesados_explica_el_orden(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "ARCHIVO_VIAJES_ACTUAL", tmp_path / "viajes_actual.parquet")
    assert datos.exportar("sqlite:///" + (tmp_path / "mlflow.db").as_posix()) is None
    salida = capsys.readouterr().out
    assert "Faltan datos procesados" in salida and "--ingerir" in salida


def test_el_reporte_detecta_la_columna_desplazada_con_la_prueba_de_su_tipo():
    tabla = _tabla_de_monitoreo(desplazamiento=6)
    partes = drift.partes(tabla)
    resultado = drift.comparar(partes["referencia"], partes["actual"]).set_index("columna")
    assert list(resultado.index) == drift.COLUMNAS and len(resultado) == 16
    assert resultado.loc["salidas_h0", "deriva"] and resultado.loc["salidas_h0", "estadistico"] > 1
    assert not resultado.drop(index="salidas_h0")["deriva"].any()
    assert set(resultado.loc[drift.NUMERICAS, "prueba"]) == {"Distancia de Wasserstein normalizada"}
    assert set(resultado.loc[drift.CATEGORICAS, "prueba"]) == {"Distancia de Jensen-Shannon"}
    assert (resultado["umbral"] == drift.UMBRAL_DRIFT).all()


def test_sin_cambios_ninguna_columna_deriva():
    tabla = _tabla_de_monitoreo()
    partes = drift.partes(tabla)
    resultado = drift.comparar(partes["referencia"], partes["actual"])
    assert not resultado["deriva"].any()
    assert (resultado["estadistico"] < drift.UMBRAL_DRIFT).all()


def test_los_controles_separan_meses_estaciones_y_temporada():
    tabla = _tabla_de_monitoreo(estacion_nueva=9)
    partes = drift.partes(tabla)
    _, mismos_meses, actual = partes["controles"]["mismos_meses"]
    assert set(mismos_meses["hora"].dt.month) == set(actual["hora"].dt.month) == {1, 2, 3, 4, 5, 6}
    _, _, mismas_estaciones = partes["controles"]["mismas_estaciones"]
    assert set(mismas_estaciones["estacion_id"]) == {2, 3, 4} and set(actual["estacion_id"]) == {2, 3, 4, 9}
    _, _, temporada = partes["controles"]["estacional"]
    assert set(temporada["conjunto"]) == {"prueba_2025"}
    nuevas = drift.estaciones_nuevas(partes["referencia"], actual)
    assert nuevas["estaciones_referencia"] == 3 and nuevas["estaciones_actual"] == 4 and nuevas["estaciones_nuevas"] == 1
    assert nuevas["proporcion_de_filas"] == pytest.approx(0.25)


@pytest.mark.filterwarnings("ignore:Starting with pandas version 4.0")
def test_analizar_deja_el_reporte_de_evidently_el_resumen_y_las_figuras(tmp_path):
    tabla = _tabla_de_monitoreo(desplazamiento=6, estacion_nueva=9)
    tabla = tabla[tabla["hora"].dt.month.isin([1, 7, 10, 11, 12]) | (tabla["conjunto"] == "referencia")].copy()
    flujos = [columna for columna in features.COLUMNAS_P2 if columna.startswith(("salidas_h", "llegadas_h", "neto_"))]
    tabla.loc[tabla["conjunto"] == "evaluacion", flujos] += 9
    figuras = {nombre: tmp_path / f"{nombre}.png" for nombre in drift.FIGURAS}
    resumen = drift.analizar(tabla, _detalle(tabla), _manifiesto(config.MESES), _manifiesto(config.MESES_ACTUAL, True), tmp_path, figuras)
    drift.escribir_resumen(resumen, tmp_path / "resumen.md")
    assert (tmp_path / "evidently_p2.html").stat().st_size > 100000
    evidently = json.loads((tmp_path / "evidently_p2.json").read_text(encoding="utf-8"))
    assert any(metrica["config"]["type"].endswith("ValueDrift") for metrica in evidently["metrics"])
    guardado = json.loads((tmp_path / "drift.json").read_text(encoding="utf-8"))
    assert guardado["principal"]["columnas"] == 16 and guardado["principal"]["columnas_con_deriva"] >= 1
    assert list(guardado["controles"]) == ["mismos_meses", "mismas_estaciones", "estacional"]
    assert list(guardado["mensual"]) == ["2026-01", "2026-07", "2026-10"]
    assert not guardado["mensual"]["2026-01"]["deriva_del_conjunto"] and guardado["mensual"]["2026-07"]["deriva_del_conjunto"]
    assert guardado["primer_mes_con_deriva_del_conjunto"] == "2026-07"
    assert set(flujos) <= set(guardado["mensual"]["2026-07"]["con_deriva"])
    assert (tmp_path / "evidently_p2_alerta.html").exists() and (tmp_path / "evidently_p2_alerta.json").exists()
    assert guardado["calidad"]["referencia"]["conjunto"]["filas"] == int((tabla["conjunto"] == "referencia").sum())
    assert guardado["calidad"]["actual"]["conjunto"]["valores_faltantes"] == 0
    assert guardado["calidad"]["crudos"]["actual"]["duracion_menor_1_min"] == 30 * len(config.MESES_ACTUAL)
    assert all(ruta.stat().st_size > 5000 for ruta in figuras.values())
    texto = (tmp_path / "resumen.md").read_text(encoding="utf-8")
    assert all(f"`{columna}`" in texto for columna in drift.COLUMNAS)
    assert "Distancia de Wasserstein normalizada" in texto and "Calidad de los datos" in texto
    assert str(tmp_path) not in texto


def test_metricas_cuentan_los_errores_y_el_costo_con_el_peso_del_falso_negativo():
    real = [1, 1, 1, 0, 0, 0, 0, 0, 0, 0]
    alerta = [1, 0, 0, 1, 1, 0, 0, 0, 0, 0]
    valores = costos.metricas(real, alerta, [0.9, 0.2, 0.1, 0.8, 0.7, 0.1, 0.1, 0.1, 0.1, 0.1])
    assert (valores["falsos_positivos"], valores["falsos_negativos"]) == (2, 2)
    assert valores["recall"] == pytest.approx(1 / 3) and valores["precision"] == pytest.approx(1 / 3)
    assert valores["costo"] == 2 + config.COSTO_FALSO_NEGATIVO * 2
    assert valores["costo_por_mil"] == pytest.approx(1000 * valores["costo"] / 10)
    assert 0 < valores["pr_auc"] <= 1
    sin_riesgo = costos.metricas([0, 0, 0], [0, 1, 0], [0.1, 0.9, 0.2])
    assert sin_riesgo["recall"] == 0.0 and sin_riesgo["pr_auc"] is None and sin_riesgo["costo"] == 1


def test_la_descomposicion_de_la_tasa_separa_mezcla_y_efecto_condicional():
    base = pd.DataFrame({"probabilidad": [0.05] * 80 + [0.95] * 20, features.OBJETIVO_P2: [0] * 76 + [1] * 4 + [1] * 10 + [0] * 10})
    otra_mezcla = pd.DataFrame({"probabilidad": [0.05] * 60 + [0.95] * 40, features.OBJETIVO_P2: [0] * 57 + [1] * 3 + [1] * 20 + [0] * 20})
    otra_relacion = pd.DataFrame({"probabilidad": [0.05] * 80 + [0.95] * 20, features.OBJETIVO_P2: [0] * 76 + [1] * 4 + [1] * 5 + [0] * 15})
    mezcla = desempeno.descomponer_tasa(base, otra_mezcla)
    assert mezcla["efecto_mezcla"] == pytest.approx(mezcla["cambio"]) and mezcla["efecto_condicional"] == pytest.approx(0)
    relacion = desempeno.descomponer_tasa(base, otra_relacion)
    assert relacion["efecto_condicional"] == pytest.approx(relacion["cambio"]) and relacion["efecto_mezcla"] == pytest.approx(0)
    assert relacion["cambio"] == pytest.approx(-0.05)
    assert len(relacion["estratos"]) == 10 and relacion["estratos"][0]["estrato"] == "0.0 a 0.1"


def test_el_desempeno_por_mes_deja_fuera_el_entrenamiento_y_separa_estaciones_nuevas(tmp_path):
    tabla = _tabla_de_monitoreo(estacion_nueva=9)
    mensual = desempeno.por_mes(tabla)
    assert mensual.index[0] == "2025-10" and mensual.index[-1] == "2026-10" and len(mensual) == 13
    assert "referencia" not in set(mensual["conjunto"])
    figuras = {nombre: tmp_path / f"{nombre}.png" for nombre in desempeno.FIGURAS}
    resumen = desempeno.analizar(tabla, _detalle(tabla), figuras)
    assert list(resumen["por_conjunto"]) == datos.CONJUNTOS
    for valores in resumen["descomposicion"].values():
        assert valores["efecto_mezcla"] + valores["efecto_condicional"] == pytest.approx(valores["cambio"])
    assert resumen["por_antiguedad"]["actual"]["Estaciones nuevas"]["estaciones"] == 1
    assert resumen["por_antiguedad"]["actual"]["Estaciones de la referencia"]["estaciones"] == 3
    desempeno.escribir_resumen(resumen, tmp_path / "desempeno.md")
    texto = (tmp_path / "desempeno.md").read_text(encoding="utf-8")
    assert "Por mes fuera del entrenamiento" in texto and "Estaciones nuevas" in texto and "(dentro de la muestra)" in texto
    assert all(ruta.stat().st_size > 5000 for ruta in figuras.values())
    json.dumps(resumen)


def test_mlproject_declara_los_puntos_de_entrada_del_monitoreo():
    proyecto = yaml.safe_load((config.RAIZ_PROYECTO / "MLproject").read_text(encoding="utf-8"))
    entradas = proyecto["entry_points"]
    assert {"ingest", "train", "search", "ingest_actual", "monitor", "reentrenar", "abtest"} <= set(entradas)
    assert "mibici.monitoreo.datos" in entradas["ingest_actual"]["command"] and "--ingerir" in entradas["ingest_actual"]["command"]
    for modulo in ("mibici.monitoreo.datos", "mibici.monitoreo.drift", "mibici.monitoreo.desempeno"):
        assert modulo in entradas["monitor"]["command"]
    assert "mibici.modeling.reentrenar" in entradas["reentrenar"]["command"]
    assert "mibici.modeling.abtest" in entradas["abtest"]["command"]
