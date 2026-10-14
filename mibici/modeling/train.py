import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow.models import infer_signature
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    davies_bouldin_score,
    f1_score,
    mean_absolute_error,
    precision_score,
    recall_score,
    root_mean_squared_error,
    silhouette_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from mibici import config, features, plots

MODELOS = {
    "p1": ["naive7", "hgb"],
    "p2": ["dummy", "regla_semana", "regresion_logistica", "bosque"],
    "p3": ["kmeans"],
}
CANDIDATOS = {"p1": "hgb", "p2": "regresion_logistica", "p3": "kmeans"}
TIPOS_CONFIABLES = ["sklearn.ensemble._hist_gradient_boosting.predictor.TreePredictor", "sklearn.tree._tree.Tree"]


def leer_argumentos():
    parser = argparse.ArgumentParser(
        description="Experimento base del proyecto MiBici: entrena el baseline o el modelo candidato de una pregunta y registra la corrida en MLflow."
    )
    parser.add_argument("--pregunta", choices=["p1", "p2", "p3"], required=True,
                        help="p1 demanda por estación y día, p2 riesgo por estación y hora, p3 grupos de estaciones")
    parser.add_argument("--modelo", default=None,
                        help="naive7 u hgb en p1; dummy, regla_semana, regresion_logistica o bosque en p2; kmeans en p3 (por defecto el candidato de cada pregunta)")
    parser.add_argument("--semilla", type=int, default=config.SEMILLA,
                        help="semilla de los modelos (por defecto %(default)s)")
    parser.add_argument("--fin_entrenamiento", default=config.FIN_ENTRENAMIENTO,
                        help="último día del conjunto de entrenamiento (por defecto %(default)s)")
    parser.add_argument("--fin_validacion", default=config.FIN_VALIDACION,
                        help="último día del conjunto de validación; la prueba empieza al día siguiente (por defecto %(default)s)")
    parser.add_argument("--umbral_riesgo", type=float, default=config.UMBRAL_RIESGO,
                        help="fracción de la capacidad que define el riesgo en p2 (por defecto %(default)s)")
    parser.add_argument("--learning_rate", type=float, default=0.1,
                        help="tasa de aprendizaje del HistGradientBoosting de p1 (por defecto %(default)s)")
    parser.add_argument("--n_estimadores", type=int, default=200,
                        help="árboles del HistGradientBoosting de p1 y del bosque de p2 (por defecto %(default)s)")
    parser.add_argument("--max_depth", type=int, default=None,
                        help="profundidad máxima de los árboles (por defecto sin límite)")
    parser.add_argument("--C", type=float, default=1.0,
                        help="inverso de la regularización de la regresión logística (por defecto %(default)s)")
    parser.add_argument("--max_iter", type=int, default=1000,
                        help="iteraciones máximas de la regresión logística (por defecto %(default)s)")
    parser.add_argument("--k", type=int, default=4,
                        help="número de grupos de kmeans en p3 (por defecto %(default)s)")
    parser.add_argument("--seleccionar_k", action="store_true",
                        help="en p3, elige k entre --k_min y --k_max por silueta en lugar de usar --k")
    parser.add_argument("--k_min", type=int, default=3)
    parser.add_argument("--k_max", type=int, default=8)
    parser.add_argument("--experimento", default=config.EXPERIMENTO,
                        help="nombre del experimento en MLflow (por defecto %(default)s)")
    parser.add_argument("--nombre_corrida", default=None,
                        help="nombre de la corrida (por defecto pregunta_modelo)")
    parser.add_argument("--tracking_uri", default=os.environ.get("MLFLOW_TRACKING_URI", config.TRACKING_URI),
                        help="almacén de MLflow (por defecto mlflow.db en la raíz del repositorio)")
    return parser.parse_args()


def git(*argumentos):
    """Ejecuta un comando de git en la raíz del repositorio; devuelve 'desconocido' si no hay repositorio."""
    try:
        resultado = subprocess.run(["git", *argumentos], capture_output=True, text=True, check=True, cwd=config.RAIZ_PROYECTO)
        return resultado.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "desconocido"


def registrar_conjuntos(entrenamiento, validacion, prueba):
    mlflow.log_params({
        "registros_entrenamiento": len(entrenamiento),
        "registros_validacion": len(validacion),
        "registros_prueba": len(prueba),
        "estaciones": entrenamiento["estacion_id"].nunique(),
    })


def correr_p1(args, viajes, estaciones, carpeta):
    """Baseline ingenuo de hace siete días o HistGradientBoosting para las salidas por estación y día."""
    entrenamiento, validacion, prueba = features.conjuntos_p1(viajes, estaciones, args.fin_entrenamiento, args.fin_validacion)
    registrar_conjuntos(entrenamiento, validacion, prueba)
    columnas = features.COLUMNAS_P1
    objetivo = features.OBJETIVO_P1
    if args.modelo == "naive7":
        modelo = None
        predecir = lambda df: df["rezago_7"].to_numpy()
    else:
        mlflow.log_params({"learning_rate": args.learning_rate, "n_estimadores": args.n_estimadores,
                           "max_depth": args.max_depth or "sin_limite"})
        modelo = HistGradientBoostingRegressor(learning_rate=args.learning_rate, max_iter=args.n_estimadores,
                                               max_depth=args.max_depth, random_state=args.semilla)
        modelo.fit(entrenamiento[columnas], entrenamiento[objetivo])
        predecir = lambda df: np.clip(modelo.predict(df[columnas]), 0, None)
    metricas = {}
    for nombre, conjunto in [("val", validacion), ("test", prueba)]:
        prediccion = predecir(conjunto)
        metricas[f"{nombre}_mae"] = mean_absolute_error(conjunto[objetivo], prediccion)
        metricas[f"{nombre}_rmse"] = root_mean_squared_error(conjunto[objetivo], prediccion)
    plots.grafica_real_vs_predicho(prueba["fecha"], prueba[objetivo], predecir(prueba), carpeta / "real_vs_predicho.png")
    return metricas, modelo, prueba[columnas]


def correr_p2(args, viajes, estaciones, carpeta):
    """Baselines y clasificadores del riesgo por estación y hora."""
    entrenamiento, validacion, prueba = features.conjuntos_p2(viajes, estaciones, args.umbral_riesgo, config.VENTANA_RIESGO_HORAS,
                                                              args.fin_entrenamiento, args.fin_validacion)
    registrar_conjuntos(entrenamiento, validacion, prueba)
    columnas = features.COLUMNAS_P2
    objetivo = features.OBJETIVO_P2
    mlflow.log_params({
        "umbral_riesgo": args.umbral_riesgo,
        "ventana_riesgo_horas": config.VENTANA_RIESGO_HORAS,
        "positivos_entrenamiento": int(entrenamiento[objetivo].sum()),
        "tasa_positivos_entrenamiento": round(float(entrenamiento[objetivo].mean()), 4),
    })
    if args.modelo == "regla_semana":
        modelo = None
        predecir = lambda df: df["riesgo_semana_anterior"].to_numpy().astype(int)
        puntuar = predecir
    else:
        if args.modelo == "dummy":
            clasificador = DummyClassifier(strategy="stratified", random_state=args.semilla)
            mlflow.log_param("estrategia", "stratified")
        elif args.modelo == "regresion_logistica":
            clasificador = LogisticRegression(C=args.C, class_weight="balanced", max_iter=args.max_iter)
            mlflow.log_params({"C": args.C, "class_weight": "balanced", "max_iter": args.max_iter})
        else:
            clasificador = RandomForestClassifier(n_estimators=args.n_estimadores, max_depth=args.max_depth, min_samples_leaf=50,
                                                  class_weight="balanced", random_state=args.semilla, n_jobs=-1)
            mlflow.log_params({"n_estimadores": args.n_estimadores, "max_depth": args.max_depth or "sin_limite",
                               "min_samples_leaf": 50, "class_weight": "balanced"})
        numericas = [columna for columna in columnas if columna not in features.CATEGORICAS_P2]
        preprocesamiento = ColumnTransformer([
            ("numericas", StandardScaler(), numericas),
            ("categoricas", OneHotEncoder(handle_unknown="ignore"), features.CATEGORICAS_P2),
        ])
        modelo = Pipeline([("preprocesamiento", preprocesamiento), ("clasificador", clasificador)])
        modelo.fit(entrenamiento[columnas], entrenamiento[objetivo])
        predecir = lambda df: modelo.predict(df[columnas])
        puntuar = lambda df: modelo.predict_proba(df[columnas])[:, 1]
    metricas = {}
    for nombre, conjunto in [("val", validacion), ("test", prueba)]:
        prediccion = predecir(conjunto)
        matriz = confusion_matrix(conjunto[objetivo], prediccion, labels=[0, 1])
        metricas[f"{nombre}_recall"] = recall_score(conjunto[objetivo], prediccion, zero_division=0)
        metricas[f"{nombre}_precision"] = precision_score(conjunto[objetivo], prediccion, zero_division=0)
        metricas[f"{nombre}_f1"] = f1_score(conjunto[objetivo], prediccion, zero_division=0)
        metricas[f"{nombre}_pr_auc"] = average_precision_score(conjunto[objetivo], puntuar(conjunto))
        metricas[f"{nombre}_falsos_positivos"] = int(matriz[0, 1])
        metricas[f"{nombre}_falsos_negativos"] = int(matriz[1, 0])
        metricas[f"{nombre}_positivos"] = int(conjunto[objetivo].sum())
    plots.grafica_matriz_confusion(prueba[objetivo], predecir(prueba), carpeta / "matriz_confusion.png")
    plots.grafica_curva_precision_recall(prueba[objetivo], puntuar(prueba), carpeta / "curva_precision_recall.png")
    return metricas, modelo, prueba[columnas]


def correr_p3(args, viajes, estaciones, carpeta):
    """KMeans sobre los perfiles de uso de las estaciones, con k fijo o elegido por silueta."""
    perfil = features.conjunto_p3(viajes, estaciones, args.fin_entrenamiento)
    columnas = [columna for columna in perfil.columns if columna not in ("estacion_id", "nombre", "latitud", "longitud")]
    X = perfil[columnas]
    k = args.k
    if args.seleccionar_k:
        escalado = StandardScaler().fit_transform(X)
        siluetas = {}
        for candidato in range(args.k_min, args.k_max + 1):
            grupos = KMeans(n_clusters=candidato, n_init=10, random_state=args.semilla).fit_predict(escalado)
            siluetas[candidato] = silhouette_score(escalado, grupos)
            mlflow.log_metric("train_silhouette_por_k", siluetas[candidato], step=candidato)
        k = max(siluetas, key=siluetas.get)
        print("Silueta por k:", {clave: round(valor, 4) for clave, valor in siluetas.items()})
    mlflow.log_params({"k": k, "seleccionar_k": args.seleccionar_k, "k_min": args.k_min, "k_max": args.k_max, "n_init": 10,
                       "estaciones": len(perfil), "variables": len(columnas), "viajes_minimos_perfil": config.VIAJES_MINIMOS_PERFIL})
    modelo = Pipeline([("escalado", StandardScaler()), ("kmeans", KMeans(n_clusters=k, n_init=10, random_state=args.semilla))])
    modelo.fit(X)
    grupos = modelo.named_steps["kmeans"].labels_
    escalado = modelo.named_steps["escalado"].transform(X)
    metricas = {
        "train_silhouette": silhouette_score(escalado, grupos),
        "train_davies_bouldin": davies_bouldin_score(escalado, grupos),
        "train_inercia": float(modelo.named_steps["kmeans"].inertia_),
    }
    plots.grafica_mapa_grupos(perfil, grupos, carpeta / "mapa_grupos.png")
    plots.grafica_perfiles_grupos(perfil, grupos, carpeta / "perfiles_grupos.png")
    asignacion = perfil[["estacion_id", "nombre", "latitud", "longitud"]].assign(grupo=grupos)
    asignacion.to_csv(carpeta / "grupos_estaciones.csv", index=False)
    print("Estaciones por grupo:", asignacion["grupo"].value_counts().sort_index().to_dict())
    return metricas, modelo, X


def main():
    args = leer_argumentos()
    args.modelo = args.modelo or CANDIDATOS[args.pregunta]
    if args.modelo not in MODELOS[args.pregunta]:
        raise SystemExit(f"el modelo {args.modelo} no aplica a {args.pregunta}; opciones: {MODELOS[args.pregunta]}")
    nombre = args.nombre_corrida or f"{args.pregunta}_{args.modelo}"
    inicio = time.time()

    viajes = pd.read_parquet(config.ARCHIVO_VIAJES)
    estaciones = pd.read_parquet(config.ARCHIVO_ESTACIONES)
    with open(config.ARCHIVO_MANIFIESTO, encoding="utf-8") as archivo:
        manifiesto = json.load(archivo)

    mlflow.set_tracking_uri(args.tracking_uri)
    mlflow.set_experiment(args.experimento)
    reanudada = bool(os.environ.get("MLFLOW_RUN_ID"))
    with mlflow.start_run(run_name=None if reanudada else nombre) as corrida:
        if args.nombre_corrida and corrida.info.run_name != nombre:
            mlflow.set_tag("mlflow.runName", nombre)
        mlflow.set_tags({
            "equipo": config.EQUIPO,
            "pregunta": args.pregunta.upper(),
            "commit_git": git("rev-parse", "HEAD"),
            "rama": git("rev-parse", "--abbrev-ref", "HEAD"),
            "mlflow.source.name": "mibici/modeling/train.py",
            "mlflow.source.git.repoURL": config.REPOSITORIO,
        })
        mlflow.log_params({
            "pregunta": args.pregunta.upper(),
            "modelo": args.modelo,
            "semilla": args.semilla,
            "fecha_inicio": manifiesto["resumen"]["fecha_inicio"],
            "fecha_fin": manifiesto["resumen"]["fecha_fin"],
            "meses": len(manifiesto["meses"]),
            "version_datos": manifiesto["version_datos"],
            "fin_entrenamiento": args.fin_entrenamiento,
            "fin_validacion": args.fin_validacion,
            "repositorio": config.REPOSITORIO,
        })
        correr = {"p1": correr_p1, "p2": correr_p2, "p3": correr_p3}[args.pregunta]
        with tempfile.TemporaryDirectory() as temporal:
            carpeta = Path(temporal)
            metricas, modelo, X_ejemplo = correr(args, viajes, estaciones, carpeta)
            metricas = {clave: float(valor) for clave, valor in metricas.items()}
            with open(carpeta / "metricas.json", "w", encoding="utf-8") as archivo:
                json.dump(metricas, archivo, indent=2)
            mlflow.log_metrics(metricas)
            mlflow.log_artifacts(temporal)
        mlflow.log_artifact(str(config.ARCHIVO_MANIFIESTO))
        if modelo is not None:
            ejemplo = X_ejemplo.head(100)
            firma = infer_signature(ejemplo, modelo.predict(ejemplo))
            mlflow.sklearn.log_model(modelo, name="modelo", signature=firma, input_example=ejemplo.head(5),
                                     skops_trusted_types=TIPOS_CONFIABLES)

    print("Corrida:", nombre, "(" + corrida.info.run_id + ")")
    for clave, valor in metricas.items():
        print(f"{clave}: {valor:.4f}")
    print("Tiempo:", round(time.time() - inicio, 1), "s")


if __name__ == "__main__":
    main()
