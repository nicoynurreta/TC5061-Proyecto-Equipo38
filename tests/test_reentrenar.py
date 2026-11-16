import json
import sys

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
import pytest
from mlflow import MlflowClient

from mibici import config, features
from mibici.modeling import artefactos, reentrenar, registry, train
from mibici.monitoreo import datos


def _tabla_de_monitoreo():
    rng = np.random.default_rng(11)
    horas = pd.date_range("2025-01-08", "2026-10-31 21:00", freq="3h")
    partes = []
    for estacion in (2, 3):
        n = len(horas)
        df = pd.DataFrame({columna: rng.integers(0, 12, n) for columna in features.COLUMNAS_P2})
        df["neto_3h"] = (df["llegadas_h0"] + df["llegadas_h1"] + df["llegadas_h2"]
                         - df["salidas_h0"] - df["salidas_h1"] - df["salidas_h2"])
        df["hora_dia"] = horas.hour
        df["dia_semana"] = horas.dayofweek
        df["fin_de_semana"] = (df["dia_semana"] >= 5).astype(int)
        df["capacidad"] = 10 + estacion
        df[features.OBJETIVO_P2] = ((df["neto_3h"].abs() + rng.integers(0, 6, n)) >= 10).astype(int)
        df.insert(0, "hora", horas)
        df.insert(0, "estacion_id", estacion)
        partes.append(df)
    tabla = pd.concat(partes, ignore_index=True).astype({columna: "float32" for columna in features.COLUMNAS_P2})
    en_2025 = np.select([tabla["hora"] <= pd.Timestamp(config.FIN_ENTRENAMIENTO) + pd.Timedelta(hours=23),
                         tabla["hora"] <= pd.Timestamp(config.FIN_VALIDACION) + pd.Timedelta(hours=23)],
                        ["referencia", "validacion_2025"], "prueba_2025")
    es_actual = tabla["hora"] >= pd.Timestamp(config.FECHA_INICIO_ACTUAL)
    tabla["conjunto"] = np.where(es_actual, datos.asignar_conjunto(tabla["hora"]), en_2025)
    return tabla


def _registrar_vigente_y_candidata(tmp_path, tabla):
    uri = "sqlite:///" + (tmp_path / "mlflow.db").as_posix()
    mlflow.set_tracking_uri(uri)
    experimento = mlflow.create_experiment("prueba-reentrenar", artifact_location=(tmp_path / "artefactos").as_uri())
    conjuntos = [tabla[tabla["conjunto"] == nombre] for nombre in ("referencia", "validacion_2025", "prueba_2025")]
    h = train.completar_hiperparametros("p2", "hgb", {"n_estimators": 20})
    resultado = train.entrenar_p2("hgb", h, config.SEMILLA, conjuntos)
    with mlflow.start_run(experiment_id=experimento, run_name="p2_hgb_mejor") as corrida:
        mlflow.log_params({"modelo": "hgb", "version_datos": "abc123", **train.parametros_hiperparametros(h), "threshold": resultado["umbral"],
                           "fin_entrenamiento": config.FIN_ENTRENAMIENTO, "fin_validacion": config.FIN_VALIDACION})
        mlflow.log_metric("test_costo", resultado["metricas"]["test_costo"])
        artefactos.registrar_modelo(resultado["modelo"], resultado["ejemplo"])
    cliente = MlflowClient()
    registry.registrar_version(cliente, "p2", corrida.info.run_id, "champion")
    registry.registrar_version(cliente, "p2", corrida.info.run_id, "challenger")
    return uri, cliente


def _preparar_archivos(tmp_path, monkeypatch, tabla):
    rutas = {"ARCHIVO_MONITOREO": tmp_path / "monitoreo_p2.parquet", "ARCHIVO_DETALLE_MONITOREO": tmp_path / "monitoreo_p2.json",
             "ARCHIVO_MANIFIESTO": tmp_path / "manifiesto.json", "ARCHIVO_MANIFIESTO_ACTUAL": tmp_path / "manifiesto_actual.json"}
    for nombre, ruta in rutas.items():
        monkeypatch.setattr(config, nombre, ruta)
    tabla.to_parquet(rutas["ARCHIVO_MONITOREO"], index=False)
    rutas["ARCHIVO_DETALLE_MONITOREO"].write_text(json.dumps({"version_datos": "abc123", "version_datos_actual": "def456"}), encoding="utf-8")
    rutas["ARCHIVO_MANIFIESTO"].write_text(json.dumps({"version_datos": "abc123", "meses": config.MESES,
                                                       "resumen": {"fecha_inicio": "2025-01-01", "fecha_fin": "2025-12-31"}}), encoding="utf-8")
    rutas["ARCHIVO_MANIFIESTO_ACTUAL"].write_text(json.dumps({"version_datos": "def456", "meses": config.MESES_ACTUAL,
                                                              "resumen": {"fecha_inicio": "2026-01-01", "fecha_fin": "2026-10-31"}}), encoding="utf-8")


def test_los_conjuntos_de_reentrenamiento_respetan_los_cortes_y_no_tocan_la_confirmacion():
    tabla = _tabla_de_monitoreo()
    entrenamiento, validacion, evaluacion = reentrenar.conjuntos_de_reentrenamiento(tabla)
    assert entrenamiento["hora"].min() == tabla["hora"].min()
    assert entrenamiento["hora"].max() == pd.Timestamp("2026-05-31 21:00")
    assert validacion["hora"].min() == pd.Timestamp("2026-06-01 00:00") and validacion["hora"].max() == pd.Timestamp("2026-06-30 21:00")
    assert evaluacion["hora"].min() == pd.Timestamp("2026-07-01 00:00") and evaluacion["hora"].max() == pd.Timestamp("2026-09-30 21:00")
    assert set(evaluacion["conjunto"]) == {"evaluacion"}
    assert {"referencia", "validacion_2025", "prueba_2025", "actual"} == set(entrenamiento["conjunto"])
    assert len(entrenamiento) + len(validacion) + len(evaluacion) < len(tabla)


def test_las_horas_con_etiqueta_del_bloque_siguiente_quedan_fuera():
    horas = pd.to_datetime(["2026-05-31 21:00", "2026-05-31 22:00", "2026-05-31 23:00", "2026-06-01 00:00",
                            "2026-06-30 21:00", "2026-06-30 22:00", "2026-07-01 00:00", "2026-10-01 00:00"])
    tabla = pd.DataFrame({"hora": horas, "conjunto": "actual"})
    entrenamiento, validacion, evaluacion = reentrenar.conjuntos_de_reentrenamiento(tabla)
    assert entrenamiento["hora"].tolist() == [pd.Timestamp("2026-05-31 21:00")]
    assert validacion["hora"].tolist() == [pd.Timestamp("2026-06-01 00:00"), pd.Timestamp("2026-06-30 21:00")]
    assert evaluacion["hora"].tolist() == [pd.Timestamp("2026-07-01 00:00")]


def test_los_periodos_salen_de_las_fechas_de_config():
    periodos = reentrenar.periodos()
    assert periodos["periodo_entrenamiento"] == f"{config.FECHA_INICIO} a {config.FIN_REENTRENAMIENTO}"
    assert periodos["periodo_validacion"] == f"{datos.dia_siguiente(config.FIN_REENTRENAMIENTO)} a {config.FIN_MONITOREO}"
    assert periodos["periodo_evaluacion"] == f"{datos.dia_siguiente(config.FIN_MONITOREO)} a {config.FIN_EVALUACION}"


@pytest.mark.filterwarnings("ignore:Hint. Inferred schema contains integer column")
def test_reentrenar_usa_la_receta_del_champion_y_registra_la_version_como_challenger(tmp_path, monkeypatch, capsys):
    tabla = _tabla_de_monitoreo()
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "sqlite:///" + (tmp_path / "mlflow.db").as_posix())
    uri, cliente = _registrar_vigente_y_candidata(tmp_path, tabla)
    _preparar_archivos(tmp_path, monkeypatch, tabla)
    monkeypatch.setattr(artefactos, "constantes_configuracion", lambda: {"SEMILLA": config.SEMILLA})
    monkeypatch.setattr(sys, "argv", ["reentrenar", "--tracking_uri", uri, "--experimento", "prueba-reentrenar"])
    reentrenar.main()
    salida = capsys.readouterr().out
    nombre = registry.NOMBRES["p2"]
    assert f"{nombre} versión 3 -> challenger" in salida and "La versión 2 deja el alias challenger" in salida

    assert str(cliente.get_model_version_by_alias(nombre, "champion").version) == "1"
    nueva = cliente.get_model_version_by_alias(nombre, "challenger")
    assert str(nueva.version) == "3"
    assert nueva.tags["entrega"] == "5" and nueva.tags["origen"] == "reentrenamiento" and nueva.tags["receta_de_la_version"] == "1"
    assert nueva.tags["periodo_entrenamiento"] == "2025-01-01 a 2026-05-31" and nueva.tags["periodo_validacion"] == "2026-06-01 a 2026-06-30"
    assert nueva.tags["version_datos"] == "abc123+def456" and nueva.tags["corrida"] == reentrenar.NOMBRE_CORRIDA
    anterior = cliente.get_model_version(nombre, "2")
    assert anterior.tags["alias_anterior"] == "challenger" and anterior.tags["relevada_por"] == "3" and list(anterior.aliases) == []

    corrida = cliente.get_run(nueva.run_id)
    entrenamiento, validacion, evaluacion = reentrenar.conjuntos_de_reentrenamiento(tabla)
    parametros = corrida.data.params
    assert (parametros["modelo"], parametros["n_estimators"], parametros["learning_rate"], parametros["max_depth"]) == ("hgb", "20", "0.1", "sin_limite")
    assert (parametros["fin_entrenamiento"], parametros["fin_validacion"], parametros["fin_evaluacion"]) == ("2026-05-31", "2026-06-30", "2026-09-30")
    assert int(parametros["registros_entrenamiento"]) == len(entrenamiento) and int(parametros["registros_prueba"]) == len(evaluacion)
    assert parametros["threshold_origen"] == "validacion" and parametros["meses"] == str(len(config.MESES) + len(config.MESES_ACTUAL))
    assert corrida.data.tags["stage_of_work"] == "retrain" and corrida.data.tags["entrega"] == "5"
    assert {"val_costo", "test_costo", "test_recall", "tiempo_entrenamiento_s"} <= set(corrida.data.metrics)
    assert {"data/manifiesto.json", "data/manifiesto_actual.json"} <= {artefacto.path for artefacto in cliente.list_artifacts(nueva.run_id, "data")}
    modelo = mlflow.sklearn.load_model(f"models:/{nombre}@challenger")
    assert modelo.threshold == float(parametros["threshold"]) == float(nueva.tags["threshold"])
    assert len(modelo.predict(validacion[features.COLUMNAS_P2])) == len(validacion)
