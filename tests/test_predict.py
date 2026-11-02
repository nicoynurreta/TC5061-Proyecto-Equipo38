import sys

import mlflow
import numpy as np
import pandas as pd
from mlflow import MlflowClient

from mibici import config, features
from mibici.modeling import artefactos, predict, registry, train


def _viajes_de_prueba():
    rng = np.random.default_rng(4)
    dias = pd.date_range("2025-01-01", "2025-12-31", freq="D")
    partes = []
    for estacion, base in zip(range(2, 8), [3, 6, 4, 8, 5, 7]):
        salidas = base + (dias.dayofweek >= 5) * 2 + rng.integers(0, 3, len(dias))
        inicio = dias.repeat(salidas) + pd.to_timedelta(rng.integers(6, 22, salidas.sum()), unit="h")
        partes.append(pd.DataFrame({"inicio": inicio, "origen_id": estacion, "destino_id": 2 + (estacion - 1) % 6}))
    viajes = pd.concat(partes, ignore_index=True).sort_values("inicio").reset_index(drop=True)
    viajes["fin"] = viajes["inicio"] + pd.Timedelta(minutes=12)
    viajes["duracion_min"] = 12.0
    viajes.insert(0, "viaje_id", range(len(viajes)))
    return viajes[["viaje_id", "inicio", "fin", "origen_id", "destino_id", "duracion_min"]]


def _estaciones_de_prueba():
    return pd.DataFrame({"estacion_id": range(2, 8), "nombre": list("abcdef"),
                         "latitud": np.linspace(20.6, 20.75, 6), "longitud": np.linspace(-103.45, -103.3, 6),
                         "capacidad": [12, 20, 16, 24, 18, 22]})


def _registrar_champion(tmp_path, pregunta, resultado, metrica):
    uri = "sqlite:///" + (tmp_path / "mlflow.db").as_posix()
    mlflow.set_tracking_uri(uri)
    experimento = mlflow.create_experiment("prueba-predict", artifact_location=(tmp_path / "artefactos").as_uri())
    with mlflow.start_run(experiment_id=experimento, run_name=f"{pregunta}_prueba") as corrida:
        mlflow.log_params({"modelo": "prueba", "version_datos": "abc123",
                           "fin_entrenamiento": config.FIN_ENTRENAMIENTO, "fin_validacion": config.FIN_VALIDACION})
        mlflow.log_metric(metrica, resultado["metricas"][metrica])
        artefactos.registrar_modelo(resultado["modelo"], resultado["ejemplo"], resultado.get("salida_ejemplo"))
    registry.registrar_version(MlflowClient(), pregunta, corrida.info.run_id, "champion")
    return uri


def _preparar_datos(tmp_path, monkeypatch):
    viajes, estaciones = _viajes_de_prueba(), _estaciones_de_prueba()
    viajes.to_parquet(tmp_path / "viajes.parquet", index=False)
    estaciones.to_parquet(tmp_path / "estaciones.parquet", index=False)
    monkeypatch.setattr(config, "ARCHIVO_VIAJES", tmp_path / "viajes.parquet")
    monkeypatch.setattr(config, "ARCHIVO_ESTACIONES", tmp_path / "estaciones.parquet")
    monkeypatch.setattr(config, "DIR_MODELOS", tmp_path / "models")
    return viajes, estaciones


def test_predict_p1_carga_el_champion_y_reporta_metricas_de_prueba(tmp_path, monkeypatch, capsys):
    viajes, estaciones = _preparar_datos(tmp_path, monkeypatch)
    conjuntos = features.conjuntos_p1(viajes, estaciones)
    resultado = train.entrenar_p1("ridge", train.completar_hiperparametros("p1", "ridge"), config.SEMILLA, conjuntos)
    uri = _registrar_champion(tmp_path, "p1", resultado, "test_mae")
    salida = tmp_path / "predicciones_p1.csv"
    monkeypatch.setattr(sys, "argv", ["predict", "--pregunta", "p1", "--tracking_uri", uri, "--salida", str(salida)])
    predict.main()
    texto = capsys.readouterr().out
    assert f"Modelo: models:/{registry.NOMBRES['p1']}@champion" in texto
    assert f"test_mae: {round(resultado['metricas']['test_mae'], 4)}" in texto
    assert f"test_rmse: {round(resultado['metricas']['test_rmse'], 4)}" in texto
    predicciones = pd.read_csv(salida)
    assert list(predicciones.columns) == ["estacion_id", "fecha", "salidas", "prediccion"]
    assert len(predicciones) == len(conjuntos[2]) > 0
    assert np.allclose(predicciones["prediccion"], resultado["prediccion_prueba"])


def test_predict_p2_aplica_el_umbral_guardado_en_el_modelo(tmp_path, monkeypatch, capsys):
    viajes, estaciones = _preparar_datos(tmp_path, monkeypatch)
    conjuntos = features.conjuntos_p2(viajes, estaciones, 0.05)
    h = train.completar_hiperparametros("p2", "regresion_logistica")
    resultado = train.entrenar_p2("regresion_logistica", h, config.SEMILLA, conjuntos)
    uri = _registrar_champion(tmp_path, "p2", resultado, "test_costo")
    salida = tmp_path / "predicciones_p2.csv"
    monkeypatch.setattr(sys, "argv", ["predict", "--pregunta", "p2", "--tracking_uri", uri, "--salida", str(salida),
                                      "--umbral_riesgo", "0.05"])
    predict.main()
    texto = capsys.readouterr().out
    assert f"Modelo: models:/{registry.NOMBRES['p2']}@champion" in texto
    assert f"umbral de decisión del modelo: {resultado['umbral']}" in texto
    assert f"test_costo: {resultado['metricas']['test_costo']}" in texto
    assert f"test_recall: {round(resultado['metricas']['test_recall'], 4)}" in texto
    predicciones = pd.read_csv(salida)
    assert list(predicciones.columns) == ["estacion_id", "hora", "riesgo", "prediccion", "probabilidad"]
    assert len(predicciones) == len(conjuntos[2]) > 0
    assert predicciones["riesgo"].nunique() == 2 and predicciones["prediccion"].nunique() == 2
    assert predicciones["prediccion"].tolist() == resultado["prediccion_prueba"].tolist()
    assert np.allclose(predicciones["probabilidad"], resultado["puntuacion_prueba"])


def test_predict_p3_asigna_grupo_a_cada_estacion_con_el_champion(tmp_path, monkeypatch, capsys):
    viajes, estaciones = _preparar_datos(tmp_path, monkeypatch)
    perfil = features.conjunto_p3(viajes, estaciones)
    resultado = train.entrenar_p3("kmeans", {"k": 2}, config.SEMILLA, perfil)
    uri = _registrar_champion(tmp_path, "p3", resultado, "train_silhouette")
    salida = tmp_path / "predicciones_p3.csv"
    monkeypatch.setattr(sys, "argv", ["predict", "--pregunta", "p3", "--tracking_uri", uri, "--salida", str(salida)])
    predict.main()
    texto = capsys.readouterr().out
    assert f"Modelo: models:/{registry.NOMBRES['p3']}@champion" in texto
    assert "estaciones por grupo:" in texto
    predicciones = pd.read_csv(salida)
    assert list(predicciones.columns) == ["estacion_id", "nombre", "latitud", "longitud", "grupo"]
    assert len(predicciones) == len(perfil) == 6
    assert predicciones["grupo"].tolist() == resultado["grupos"].tolist()
    assert sorted(predicciones["grupo"].unique()) == [0, 1]
