import json
import re
import sys

import mlflow
import numpy as np
import pandas as pd
import pytest
from mlflow import MlflowClient
from scipy import stats
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import FixedThresholdClassifier

from mibici import config, features
from mibici.modeling import abtest, artefactos, registry
from mibici.monitoreo import datos


def _tabla_de_evaluacion():
    rng = np.random.default_rng(21)
    horas = pd.date_range("2026-06-01", "2026-10-31 21:00", freq="3h")
    partes = []
    for estacion in (2, 3, 4):
        n = len(horas)
        df = pd.DataFrame({columna: rng.integers(0, 12, n) for columna in features.COLUMNAS_P2})
        df["neto_3h"] = (df["llegadas_h0"] + df["llegadas_h1"] + df["llegadas_h2"]
                         - df["salidas_h0"] - df["salidas_h1"] - df["salidas_h2"])
        df[features.OBJETIVO_P2] = ((df["neto_3h"] + rng.integers(0, 8, n)) >= 12).astype(int)
        df.insert(0, "hora", horas)
        df.insert(0, "estacion_id", estacion)
        partes.append(df)
    tabla = pd.concat(partes, ignore_index=True).astype({columna: "float32" for columna in features.COLUMNAS_P2})
    tabla["conjunto"] = datos.asignar_conjunto(tabla["hora"])
    return tabla


def _modelo(tabla, umbral):
    junio = tabla[tabla["conjunto"] == "actual"]
    X, y = junio[features.COLUMNAS_P2], junio[features.OBJETIVO_P2]
    return FixedThresholdClassifier(FrozenEstimator(LogisticRegression(max_iter=2000).fit(X, y)), threshold=umbral).fit(X, y)


def _dias_y_errores(dias=40, por_dia=300, semilla=8):
    rng = np.random.default_rng(semilla)
    dia = np.repeat(pd.date_range("2026-07-01", periods=dias, freq="D").to_numpy(), por_dia)
    real = rng.random(dias * por_dia) < 0.1
    alerta_a = np.where(rng.random(len(real)) < 0.35, ~real, real)
    alerta_b = np.where(rng.random(len(real)) < 0.10, ~real, real)
    return real, alerta_a, alerta_b, dia


def test_mcnemar_sin_pares_discordantes_exacta_y_con_ji_cuadrada():
    iguales = abtest.mcnemar([1, 0, 1, 1], [1, 0, 1, 1])
    assert iguales["p_valor"] == 1.0 and iguales["prueba"] == "sin pares discordantes"
    pocos = abtest.mcnemar([1] * 1 + [0] * 9 + [1] * 30, [0] * 1 + [1] * 9 + [1] * 30)
    assert (pocos["solo_acierta_a"], pocos["solo_acierta_b"], pocos["prueba"]) == (1, 9, "binomial exacta")
    assert pocos["p_valor"] == pytest.approx(22 / 1024)
    muchos = abtest.mcnemar([1] * 10 + [0] * 40 + [1] * 100, [0] * 10 + [1] * 40 + [1] * 100)
    assert (muchos["solo_acierta_a"], muchos["solo_acierta_b"]) == (10, 40)
    assert muchos["estadistico"] == pytest.approx(29 ** 2 / 50)
    assert muchos["p_valor"] == pytest.approx(stats.chi2.sf(29 ** 2 / 50, 1))


def test_metricas_de_sumas_calcula_recall_precision_y_costo_por_replica():
    sumas = {"filas": np.array([1000.0, 500.0]), "aciertos": np.array([30.0, 0.0]),
             "falsos_positivos": np.array([10.0, 0.0]), "falsos_negativos": np.array([20.0, 5.0])}
    valores = abtest.metricas_de_sumas(sumas)
    assert valores["recall"].tolist() == pytest.approx([0.6, 0.0])
    assert valores["precision"].tolist() == pytest.approx([0.75, 0.0])
    assert valores["f1"].tolist() == pytest.approx([2 * 0.6 * 0.75 / 1.35, 0.0])
    assert valores["costo_por_mil"].tolist() == pytest.approx([10 + config.COSTO_FALSO_NEGATIVO * 20, 1000 * config.COSTO_FALSO_NEGATIVO * 5 / 500])


def test_el_bootstrap_por_dia_es_pareado_y_reproducible():
    real, alerta_a, alerta_b, dia = _dias_y_errores()
    codigos, dias = pd.factorize(dia, sort=True)
    de_a = abtest.conteos_por_dia(real, alerta_a, codigos, len(dias))
    de_b = abtest.conteos_por_dia(real, alerta_b, codigos, len(dias))
    assert de_a["filas"].tolist() == [300.0] * 40
    assert de_a["aciertos"].sum() + de_a["falsos_negativos"].sum() == real.sum()
    iguales, _ = abtest.bootstrap_por_dia(de_a, de_a, replicas=200)
    assert all(intervalo == {"inferior": 0.0, "superior": 0.0} for intervalo in iguales.values())
    intervalos, diferencias = abtest.bootstrap_por_dia(de_a, de_b, replicas=500, semilla=7)
    repetidos, _ = abtest.bootstrap_por_dia(de_a, de_b, replicas=500, semilla=7)
    assert intervalos == repetidos and len(diferencias["costo_por_mil"]) == 500
    assert set(intervalos) == set(abtest.CON_INTERVALO)
    assert intervalos["costo_por_mil"]["superior"] < 0 and intervalos["recall"]["inferior"] > 0
    assert intervalos["costo_por_mil"]["inferior"] < np.median(diferencias["costo_por_mil"]) < intervalos["costo_por_mil"]["superior"]


def test_la_regla_exige_menor_costo_y_recall_no_inferior():
    def comparacion(costo_superior, recall_inferior):
        return {"intervalos": {"costo_por_mil": {"inferior": -9.0, "superior": costo_superior},
                               "recall": {"inferior": recall_inferior, "superior": 0.2}}}

    assert abtest.decidir(comparacion(-0.5, 0.02)) == {"costo_menor": True, "recall_no_inferior": True, "promover": True}
    assert abtest.decidir(comparacion(-0.5, -abtest.MARGEN_RECALL)) == {"costo_menor": True, "recall_no_inferior": True, "promover": True}
    assert abtest.decidir(comparacion(0.0, 0.02)) == {"costo_menor": False, "recall_no_inferior": True, "promover": False}
    assert abtest.decidir(comparacion(-0.5, -0.05)) == {"costo_menor": True, "recall_no_inferior": False, "promover": False}
    assert abtest.decidir(comparacion(0.3, -0.05))["promover"] is False
    assert "champion" in abtest.REGLA and str(abtest.MARGEN_RECALL) in abtest.REGLA


def test_comparar_reporta_metricas_diferencias_intervalos_y_mcnemar():
    real, alerta_a, alerta_b, dia = _dias_y_errores()
    probabilidad = np.where(real, 0.8, 0.2)
    resultado, diferencias = abtest.comparar(real, (alerta_a, probabilidad), (alerta_b, probabilidad), dia, replicas=400)
    assert (resultado["filas"], resultado["dias"], resultado["positivos"]) == (12000, 40, int(real.sum()))
    assert resultado["b"]["costo"] < resultado["a"]["costo"] and resultado["b"]["recall"] > resultado["a"]["recall"]
    assert resultado["diferencia"]["costo_por_mil"] == pytest.approx(resultado["b"]["costo_por_mil"] - resultado["a"]["costo_por_mil"])
    assert resultado["diferencia"]["pr_auc"] == pytest.approx(0.0)
    assert resultado["intervalos"]["costo_por_mil"]["inferior"] <= resultado["diferencia"]["costo_por_mil"] <= resultado["intervalos"]["costo_por_mil"]["superior"]
    todas = resultado["mcnemar"]["todas"]
    assert todas["solo_acierta_b"] > todas["solo_acierta_a"] and todas["p_valor"] < 0.001
    assert set(resultado["mcnemar"]) == {"todas", "en_riesgo", "sin_riesgo"}
    assert todas["solo_acierta_a"] == resultado["mcnemar"]["en_riesgo"]["solo_acierta_a"] + resultado["mcnemar"]["sin_riesgo"]["solo_acierta_a"]
    assert 0 < resultado["coinciden"] < 1 and len(diferencias["costo_por_mil"]) == 400
    assert abtest.decidir(resultado)["promover"] is True


def test_el_trafico_dividido_reparte_las_filas_y_cuenta_solo_el_brazo_asignado():
    real, alerta_a, alerta_b, dia = _dias_y_errores()
    trafico = abtest.trafico_dividido(real, alerta_a, alerta_b, dia, replicas=300, semilla=5)
    assert trafico["a"]["filas"] + trafico["b"]["filas"] == len(real)
    assert abs(trafico["b"]["filas"] / len(real) - 0.5) < 0.03
    assert trafico == abtest.trafico_dividido(real, alerta_a, alerta_b, dia, replicas=300, semilla=5)
    assert trafico["diferencia"]["costo_por_mil"] < 0 and trafico["intervalos"]["costo_por_mil"]["superior"] < 0
    solo_b = abtest.trafico_dividido(real, alerta_a, alerta_b, dia, proporcion=1.0, replicas=50)
    assert solo_b["a"]["filas"] == 0 and solo_b["b"]["filas"] == len(real)


def test_evaluar_compara_en_la_evaluacion_y_repite_en_la_confirmacion(tmp_path):
    tabla = _tabla_de_evaluacion()
    modelo_a, modelo_b = _modelo(tabla, 0.9), _modelo(tabla, 0.25)
    resultado, diferencias = abtest.evaluar(tabla, modelo_a, modelo_b, replicas=300)
    evaluacion = tabla[tabla["conjunto"] == "evaluacion"]
    assert resultado["evaluacion"]["filas"] == len(evaluacion) and resultado["evaluacion"]["dias"] == 92
    assert resultado["confirmacion"]["filas"] == int((tabla["conjunto"] == "confirmacion").sum())
    assert [fila["mes"] for fila in resultado["por_mes"]] == ["2026-07", "2026-08", "2026-09", "2026-10"]
    assert resultado["evaluacion"]["b"]["alertas"] > resultado["evaluacion"]["a"]["alertas"]
    assert resultado["evaluacion"]["b"]["recall"] > resultado["evaluacion"]["a"]["recall"]
    assert resultado["decision"] == abtest.decidir(resultado["evaluacion"])
    assert resultado["trafico"]["a"]["filas"] + resultado["trafico"]["b"]["filas"] == len(evaluacion)
    assert len(diferencias["costo_por_mil"]) == 300
    ajuste = resultado["a_igual_recall"]
    assert 0.25 < ajuste["umbral_b"] <= 1 and set(ajuste) == {"umbral_b", "evaluacion", "confirmacion"}
    assert ajuste["evaluacion"]["b"]["recall"] >= resultado["evaluacion"]["a"]["recall"]
    assert ajuste["evaluacion"]["b"]["alertas"] < resultado["evaluacion"]["b"]["alertas"]
    assert ajuste["confirmacion"]["a"] == resultado["confirmacion"]["a"]
    with pytest.raises(SystemExit, match="evaluación"):
        abtest.evaluar(tabla[tabla["conjunto"] == "actual"], modelo_a, modelo_b, replicas=10)

    version = {"alias": "champion", "run_id": "abc", "corrida": "p2_prueba", "umbral": 0.9, "version_datos": "abc123",
               "periodo_entrenamiento": "2025-01-01 a 2025-09-30", "commit_git": "0123456"}
    resultado.update({"generado": "2026-11-15T03:00:00", "modelo": registry.NOMBRES["p2"], "ventanas": datos.ventanas(), "replicas": 300,
                      "semilla": config.SEMILLA, "versiones": {"a": {**version, "version": "1"}, "b": {**version, "version": "3", "alias": "challenger"}},
                      "accion": "El alias champion se queda en la versión 1 y la versión 3 conserva el alias challenger."})
    abtest.escribir_reporte(resultado, tmp_path / "abtest.md")
    texto = (tmp_path / "abtest.md").read_text(encoding="utf-8")
    assert abtest.REGLA in texto and "Condición 1, costo" in texto and "Simulación de tráfico dividido" in texto
    assert "| Recall |" in texto and "Confirmación fuera de la regla" in texto and resultado["accion"] in texto
    assert "Análisis posterior a la decisión" in texto and "| Evaluación |" in texto
    figura = abtest.grafica_abtest(resultado["por_mes"], diferencias["costo_por_mil"], resultado["evaluacion"]["intervalos"]["costo_por_mil"],
                                   resultado["versiones"], tmp_path / "abtest.png")
    assert figura.stat().st_size > 5000
    json.dumps(resultado)


def test_main_compara_las_versiones_del_registry_y_solo_promueve_si_la_regla_se_cumple(tmp_path, monkeypatch, capsys):
    tabla = _tabla_de_evaluacion()
    uri = "sqlite:///" + (tmp_path / "mlflow.db").as_posix()
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    mlflow.set_tracking_uri(uri)
    experimento = mlflow.create_experiment("prueba-abtest", artifact_location=(tmp_path / "artefactos").as_uri())
    modelo = _modelo(tabla, 0.5)
    with mlflow.start_run(experiment_id=experimento, run_name="p2_prueba") as corrida:
        mlflow.log_params({"modelo": "regresion_logistica", "version_datos": "abc123", "threshold": 0.5,
                           "fin_entrenamiento": config.FIN_ENTRENAMIENTO, "fin_validacion": config.FIN_VALIDACION})
        mlflow.log_metric("test_costo", 1.0)
        artefactos.registrar_modelo(modelo, tabla[features.COLUMNAS_P2].head(20))
    cliente = MlflowClient()
    nombre, _ = registry.registrar_version(cliente, "p2", corrida.info.run_id, "champion")
    registry.registrar_version(cliente, "p2", corrida.info.run_id, "challenger")

    monkeypatch.setattr(config, "ARCHIVO_MONITOREO", tmp_path / "monitoreo_p2.parquet")
    monkeypatch.setattr(config, "DIR_MONITOREO", tmp_path / "monitoreo")
    monkeypatch.setattr(config, "DIR_FIGURAS", tmp_path / "figuras")
    monkeypatch.setattr(abtest, "ARCHIVO_JSON", tmp_path / "monitoreo" / "abtest.json")
    monkeypatch.setattr(abtest, "ARCHIVO_REPORTE", tmp_path / "monitoreo" / "abtest.md")
    monkeypatch.setattr(abtest, "FIGURA", tmp_path / "figuras" / "abtest_costo.png")
    tabla.to_parquet(tmp_path / "monitoreo_p2.parquet", index=False)
    with mlflow.start_run(experiment_id=experimento) as del_proyecto:
        mlflow.log_params({"version_a": "\"\"", "version_b": "\"\"", "promote": "1"})
    monkeypatch.setenv("MLFLOW_RUN_ID", del_proyecto.info.run_id)
    monkeypatch.setattr(sys, "argv", ["abtest", "--tracking_uri", uri, "--experimento", "prueba-abtest", "--replicas", "200", "--promover"])
    abtest.main()
    salida = capsys.readouterr().out
    assert "A: versión 1 | B: versión 2" in salida and "conserva el alias challenger" in salida

    texto = (tmp_path / "monitoreo" / "abtest.json").read_text(encoding="utf-8")
    assert re.search(r"[A-Za-z0-9+/]{40,}", texto) is None
    guardado = json.loads(texto)
    assert guardado["decision"] == {"costo_menor": False, "recall_no_inferior": True, "promover": False}
    assert guardado["evaluacion"]["coinciden"] == 1.0 and guardado["evaluacion"]["mcnemar"]["todas"]["prueba"] == "sin pares discordantes"
    assert guardado["versiones"]["a"]["alias"] == "champion" and guardado["versiones"]["b"]["alias"] == "challenger"
    assert (tmp_path / "monitoreo" / "abtest.md").exists() and (tmp_path / "figuras" / "abtest_costo.png").exists()
    vigente = cliente.get_model_version_by_alias(nombre, "champion")
    candidata = cliente.get_model_version_by_alias(nombre, "challenger")
    assert (str(vigente.version), str(candidata.version)) == ("1", "2")
    corridas = mlflow.search_runs(experiment_ids=[experimento], filter_string="tags.stage_of_work = 'abtest'", output_format="list")
    assert len(corridas) == 1 and corridas[0].data.tags["decision"] == "mantener" and corridas[0].info.run_name == "p2_abtest_v1_v2"
    assert corridas[0].info.run_id == del_proyecto.info.run_id and corridas[0].data.params["version_a"] == "\"\""
    assert corridas[0].data.params["version_modelo_a"] == "1" and corridas[0].data.params["version_modelo_b"] == "2"
    assert corridas[0].data.metrics["promover"] == 0
    assert vigente.tags["abtest_run_id"] == candidata.tags["abtest_run_id"] == corridas[0].info.run_id
    assert candidata.tags["abtest_decision"] == "mantener la versión vigente"

    cumple = {"costo_menor": True, "recall_no_inferior": True, "promover": True}
    pendiente = abtest.aplicar_decision(cliente, nombre, vigente, candidata, cumple, promover=False)
    assert "--promover" in pendiente and str(cliente.get_model_version_by_alias(nombre, "champion").version) == "1"
    hecho = abtest.aplicar_decision(cliente, nombre, vigente, candidata, cumple, promover=True)
    assert "pasó de la versión 1 a la versión 2" in hecho
    assert str(cliente.get_model_version_by_alias(nombre, "champion").version) == "2"
    assert "challenger" not in cliente.get_model_version(nombre, "2").aliases
    relevada = cliente.get_model_version(nombre, "1")
    assert relevada.tags["relevada_por"] == "2" and relevada.tags["alias_anterior"] == "champion"
