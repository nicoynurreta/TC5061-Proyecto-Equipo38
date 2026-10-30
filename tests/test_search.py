import sys

import mlflow
import numpy as np
import pandas as pd
from mlflow import MlflowClient

from mibici import config
from mibici.modeling import search, train


def test_combinaciones_recorren_la_rejilla_con_los_fijos():
    combos = list(search.combinaciones(config.BUSQUEDAS["p1"]["hgb"]))
    assert len(combos) == 9
    assert all(set(c) == {"n_estimators", "learning_rate", "max_depth"} and c["n_estimators"] == 300 for c in combos)
    assert {(c["learning_rate"], c["max_depth"]) for c in combos} == {
        (0.05, 4), (0.05, 8), (0.05, None), (0.1, 4), (0.1, 8), (0.1, None), (0.2, 4), (0.2, 8), (0.2, None)}
    assert len(list(search.combinaciones(config.BUSQUEDAS["p2"]["hgb"]))) == 6
    assert [c["k"] for c in search.combinaciones(config.BUSQUEDAS["p3"]["kmeans"])] == [3, 4, 5, 6, 7, 8]


def test_combinaciones_con_rejilla_vacia_o_sin_valores():
    assert list(search.combinaciones({"fijos": {"k": 4}, "rejilla": {}})) == [{"k": 4}]
    assert list(search.combinaciones({"fijos": {}, "rejilla": {"k": []}})) == []


def test_etiqueta_combinacion_abrevia_y_marca_sin_limite():
    h = train.completar_hiperparametros("p1", "hgb", {"learning_rate": 0.05, "max_depth": None, "n_estimators": 300})
    assert search.etiqueta_combinacion(h, ["learning_rate", "max_depth"]) == "lr0.05_mdsin_limite"
    assert search.etiqueta_combinacion({"learning_rate": 0.1, "max_depth": 8}, ["max_depth", "learning_rate"]) == "md8_lr0.1"
    assert search.etiqueta_combinacion({"k": 3}, ["k"]) == "k3"


def test_es_mejor_respeta_el_sentido_de_la_metrica():
    assert search.METRICA_BUSQUEDA == {"p1": ("val_mae", True), "p2": ("val_costo", True), "p3": ("train_silhouette", False)}
    assert search.es_mejor(5.0, None, True) and search.es_mejor(0.1, None, False)
    assert search.es_mejor(4.0, 5.0, True) and not search.es_mejor(5.0, 4.0, True)
    assert search.es_mejor(0.2, 0.1, False) and not search.es_mejor(0.1, 0.2, False)
    assert not search.es_mejor(1.0, 1.0, True) and not search.es_mejor(1.0, 1.0, False)


def _perfil_de_prueba():
    rng = np.random.default_rng(3)
    estaciones = 30
    columnas = [f"{tipo}_{dia}_{hora:02d}" for tipo in ("salidas", "llegadas") for dia in ("habil", "finde") for hora in range(24)]
    centros = rng.uniform(0, 1, (3, len(columnas)))
    valores = np.abs(np.vstack([centro + rng.normal(0, 0.05, (estaciones // 3, len(columnas))) for centro in centros]))
    perfil = pd.DataFrame(valores, columns=columnas)
    perfil["log_viajes"] = rng.uniform(4, 9, estaciones)
    perfil["proporcion_salidas"] = rng.uniform(0.3, 0.7, estaciones)
    perfil.insert(0, "longitud", rng.uniform(-103.45, -103.3, estaciones))
    perfil.insert(0, "latitud", rng.uniform(20.6, 20.75, estaciones))
    perfil.insert(0, "nombre", [f"estacion {i}" for i in range(1, estaciones + 1)])
    perfil.insert(0, "estacion_id", range(1, estaciones + 1))
    return perfil


def test_busqueda_p3_abre_una_hija_por_combinacion_y_promueve_la_mejor(tmp_path, monkeypatch):
    uri = "sqlite:///" + (tmp_path / "mlflow.db").as_posix()
    mlflow.set_tracking_uri(uri)
    mlflow.create_experiment("prueba-search", artifact_location=(tmp_path / "artefactos").as_uri())
    manifiesto = {"version_datos": "abc123", "meses": ["2025-01"],
                  "resumen": {"fecha_inicio": "2025-01-01", "fecha_fin": "2025-01-31"}}
    perfil = _perfil_de_prueba()
    monkeypatch.setattr(train, "cargar_datos", lambda: (None, None, manifiesto))
    monkeypatch.setattr(train, "construir_conjuntos", lambda pregunta, viajes, estaciones, args: perfil)
    monkeypatch.setattr(sys, "argv", ["search", "--pregunta", "p3", "--modelo", "kmeans",
                                      "--tracking_uri", uri, "--experimento", "prueba-search"])
    search.main()

    cliente = MlflowClient()
    experimento = cliente.get_experiment_by_name("prueba-search").experiment_id
    padres = cliente.search_runs([experimento], "attributes.run_name = 'p3_busqueda_kmeans'")
    assert len(padres) == 1
    padre = padres[0]
    hijas = cliente.search_runs([experimento], f"tags.mlflow.parentRunId = '{padre.info.run_id}'")
    valores_k = config.BUSQUEDAS["p3"]["kmeans"]["rejilla"]["k"]
    assert padre.data.params["combinaciones"] == str(len(valores_k))
    assert padre.data.params["metrica_busqueda"] == "train_silhouette"
    assert len(hijas) == len(valores_k)

    mejor = padre.data.tags["mejor_combinacion"]
    esperados = {f"p3_busqueda_kmeans_k{k}" for k in valores_k if f"k{k}" != mejor} | {"p3_kmeans_mejor"}
    assert {hija.info.run_name for hija in hijas} == esperados
    assert sorted(hija.data.tags["combinacion"] for hija in hijas) == sorted(f"k{k}" for k in valores_k)
    siluetas = {hija.info.run_id: hija.data.metrics["train_silhouette"] for hija in hijas}
    assert padre.data.tags["mejor_hija"] == max(siluetas, key=siluetas.get)
    historial = cliente.get_metric_history(padre.info.run_id, "train_silhouette_por_combinacion")
    assert sorted(punto.step for punto in historial) == list(range(1, len(valores_k) + 1))

    promovida = [hija for hija in hijas if hija.info.run_id == padre.data.tags["mejor_hija"]][0]
    assert promovida.info.run_name == "p3_kmeans_mejor"
    assert promovida.data.tags["stage_of_work"] == "candidate" and promovida.data.tags["mejor_de_busqueda"] == "true"
    assert all(hija.data.tags["stage_of_work"] == "search" for hija in hijas if hija.info.run_id != promovida.info.run_id)
    rutas = {artefacto.path for artefacto in cliente.list_artifacts(promovida.info.run_id)}
    assert {"plots", "data", "config", "metricas.json"} <= rutas
    assert "data/grupos_estaciones.csv" in {artefacto.path for artefacto in cliente.list_artifacts(promovida.info.run_id, "data")}
