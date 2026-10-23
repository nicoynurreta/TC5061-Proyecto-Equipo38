import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression, Ridge
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
from sklearn.model_selection import FixedThresholdClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from mibici import config, features, plots
from mibici.modeling import artefactos

MODELOS = {pregunta: list(modelos) for pregunta, modelos in config.HIPERPARAMETROS.items()}
BASELINES = {"p1": ["naive7"], "p2": ["dummy", "regla_semana"], "p3": ["kmeans"]}
FAMILIAS = {
    "naive7": "ingenuo_estacional",
    "hgb": "hist_gradient_boosting",
    "bosque": "random_forest",
    "ridge": "ridge",
    "dummy": "dummy",
    "regla_semana": "regla",
    "regresion_logistica": "regresion_logistica",
    "kmeans": "kmeans",
    "kmeans_pca": "kmeans_pca",
    "aglomerativo": "aglomerativo",
}
HIPERPARAMETROS_CLI = ["n_estimators", "learning_rate", "max_depth", "min_samples_leaf", "C", "max_iter", "alpha", "k", "componentes"]
CATEGORICAS_P1 = ["dia_semana", "mes"]
IDENTIFICACION_P3 = ["estacion_id", "nombre", "latitud", "longitud"]
FUENTE = "mibici/modeling/train.py"


def leer_argumentos():
    parser = argparse.ArgumentParser(
        description="Entrena el baseline o una candidata de una pregunta del proyecto MiBici y registra la corrida con sus artefactos en MLflow."
    )
    parser.add_argument("--pregunta", choices=["p1", "p2", "p3"], required=True,
                        help="p1 demanda por estación y día, p2 riesgo por estación y hora, p3 grupos de estaciones")
    parser.add_argument("--modelo", required=True,
                        help="p1: naive7, hgb, bosque o ridge; p2: dummy, regla_semana, regresion_logistica, bosque o hgb; p3: kmeans, aglomerativo o kmeans_pca")
    parser.add_argument("--nombre_corrida", default="",
                        help="nombre de la corrida (por defecto pregunta_modelo)")
    for nombre in HIPERPARAMETROS_CLI:
        parser.add_argument(f"--{nombre}", default="",
                            help=f"{nombre} del modelo; vacío toma el valor de config.HIPERPARAMETROS")
    parser.add_argument("--threshold", default="",
                        help="umbral de decisión de los clasificadores de p2; vacío lo elige en validación con el costo de los errores")
    parser.add_argument("--semilla", type=int, default=config.SEMILLA,
                        help="semilla de los modelos (por defecto %(default)s)")
    parser.add_argument("--fin_entrenamiento", default=config.FIN_ENTRENAMIENTO,
                        help="último día del conjunto de entrenamiento (por defecto %(default)s)")
    parser.add_argument("--fin_validacion", default=config.FIN_VALIDACION,
                        help="último día del conjunto de validación; la prueba empieza al día siguiente (por defecto %(default)s)")
    parser.add_argument("--umbral_riesgo", type=float, default=config.UMBRAL_RIESGO,
                        help="fracción de la capacidad que define el riesgo en p2 (por defecto %(default)s)")
    parser.add_argument("--experimento", default=config.EXPERIMENTO,
                        help="nombre del experimento en MLflow (por defecto %(default)s)")
    parser.add_argument("--tracking_uri", default=os.environ.get("MLFLOW_TRACKING_URI", config.TRACKING_URI),
                        help="servidor o almacén de MLflow (por defecto MLFLOW_TRACKING_URI o mlflow.db en la raíz)")
    args = parser.parse_args()
    for nombre in ["modelo", "nombre_corrida", "threshold", *HIPERPARAMETROS_CLI]:
        setattr(args, nombre, limpiar(getattr(args, nombre)))
    return args


def limpiar(texto):
    """Quita espacios y comillas sobrantes de un argumento de texto; mlflow run entrega los vacíos como comillas en Windows."""
    return str(texto).strip().strip("\"'").strip()


def git(*argumentos):
    """Ejecuta un comando de git en la raíz del repositorio; devuelve 'desconocido' si no hay repositorio."""
    try:
        resultado = subprocess.run(["git", *argumentos], capture_output=True, text=True, check=True, cwd=config.RAIZ_PROYECTO)
        return resultado.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "desconocido"


def valor_hiperparametro(texto, referencia):
    """Convierte el texto de la línea de comandos al tipo del valor por defecto; vacío conserva el valor por defecto."""
    texto = limpiar(texto)
    if texto == "":
        return referencia
    if texto.lower() in ("none", "sin_limite"):
        return None
    if isinstance(referencia, bool):
        return texto.lower() in ("1", "true", "si")
    if isinstance(referencia, int):
        return int(texto)
    if isinstance(referencia, float):
        return float(texto)
    return int(texto) if texto.lstrip("-").isdigit() else float(texto)


def completar_hiperparametros(pregunta, modelo, valores=None):
    """Completa un diccionario de hiperparámetros con los valores por defecto de config.py."""
    completos = dict(config.HIPERPARAMETROS[pregunta][modelo])
    completos.update(valores or {})
    if pregunta == "p2" and modelo not in BASELINES["p2"]:
        completos.setdefault("threshold", None)
    return completos


def resolver_hiperparametros(pregunta, modelo, args):
    """Toma los hiperparámetros de config.py y sustituye los que llegaron por la línea de comandos.

    Devuelve los valores ya convertidos y, aparte, el texto original de los que se pasaron,
    que es el que se registra como parámetro para que coincida con el que anotó mlflow run.
    """
    valores = completar_hiperparametros(pregunta, modelo)
    textos = {}
    for nombre in HIPERPARAMETROS_CLI:
        texto = getattr(args, nombre)
        if nombre in valores:
            valores[nombre] = valor_hiperparametro(texto, valores[nombre])
            if texto != "":
                textos[nombre] = texto
        elif texto != "":
            raise SystemExit(f"el modelo {modelo} de {pregunta} no usa {nombre}")
    if "threshold" in valores:
        valores["threshold"] = valor_hiperparametro(args.threshold, None)
        if args.threshold != "":
            textos["threshold"] = args.threshold
    elif args.threshold != "":
        raise SystemExit(f"el modelo {modelo} de {pregunta} no usa threshold")
    return valores, textos


def etapa_de_trabajo(pregunta, modelo, hiperparametros):
    """baseline cuando es el modelo de referencia de la propuesta con sus valores por defecto; candidate en otro caso."""
    if modelo in BASELINES[pregunta] and hiperparametros == completar_hiperparametros(pregunta, modelo):
        return "baseline"
    return "candidate"


def etiquetas(pregunta, modelo, etapa, fuente=FUENTE):
    valores = {
        "equipo": config.EQUIPO,
        "pregunta": pregunta.upper(),
        "question": pregunta,
        "model_family": FAMILIAS[modelo],
        "stage_of_work": etapa,
        "commit_git": git("rev-parse", "HEAD"),
        "rama": git("rev-parse", "--abbrev-ref", "HEAD"),
        "mlflow.source.git.repoURL": config.REPOSITORIO,
    }
    if not os.environ.get("MLFLOW_RUN_ID"):
        valores["mlflow.source.name"] = fuente
    return valores


def parametros_comunes(args, manifiesto):
    return {
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
    }


def parametros_hiperparametros(hiperparametros, textos=None):
    textos = textos or {}
    return {clave: textos.get(clave, "sin_limite" if valor is None else valor)
            for clave, valor in hiperparametros.items() if clave != "threshold"}


def cargar_datos():
    viajes = pd.read_parquet(config.ARCHIVO_VIAJES)
    estaciones = pd.read_parquet(config.ARCHIVO_ESTACIONES)
    with open(config.ARCHIVO_MANIFIESTO, encoding="utf-8") as archivo:
        manifiesto = json.load(archivo)
    return viajes, estaciones, manifiesto


def construir_conjuntos(pregunta, viajes, estaciones, args):
    if pregunta == "p1":
        return features.conjuntos_p1(viajes, estaciones, args.fin_entrenamiento, args.fin_validacion)
    if pregunta == "p2":
        return features.conjuntos_p2(viajes, estaciones, args.umbral_riesgo, config.VENTANA_RIESGO_HORAS,
                                     args.fin_entrenamiento, args.fin_validacion)
    return features.conjunto_p3(viajes, estaciones, args.fin_entrenamiento)


def registrar_conjuntos(pregunta, conjuntos, args):
    if pregunta == "p3":
        perfil = conjuntos
        columnas = [columna for columna in perfil.columns if columna not in IDENTIFICACION_P3]
        mlflow.log_params({"estaciones": len(perfil), "variables": len(columnas), "viajes_minimos_perfil": config.VIAJES_MINIMOS_PERFIL})
        return
    entrenamiento, validacion, prueba = conjuntos
    mlflow.log_params({
        "registros_entrenamiento": len(entrenamiento),
        "registros_validacion": len(validacion),
        "registros_prueba": len(prueba),
        "estaciones": entrenamiento["estacion_id"].nunique(),
    })
    if pregunta == "p2":
        objetivo = features.OBJETIVO_P2
        mlflow.log_params({
            "umbral_riesgo": args.umbral_riesgo,
            "ventana_riesgo_horas": config.VENTANA_RIESGO_HORAS,
            "positivos_entrenamiento": int(entrenamiento[objetivo].sum()),
            "tasa_positivos_entrenamiento": round(float(entrenamiento[objetivo].mean()), 4),
            "costo_falso_negativo": config.COSTO_FALSO_NEGATIVO,
        })


# P1: demanda por estación y día

def regresor_p1(modelo, h, semilla):
    if modelo == "hgb":
        return HistGradientBoostingRegressor(learning_rate=h["learning_rate"], max_iter=h["n_estimators"],
                                             max_depth=h["max_depth"], random_state=semilla)
    if modelo == "bosque":
        return RandomForestRegressor(n_estimators=h["n_estimators"], max_depth=h["max_depth"],
                                     min_samples_leaf=h["min_samples_leaf"], random_state=semilla, n_jobs=-1)
    numericas = [columna for columna in features.COLUMNAS_P1 if columna not in CATEGORICAS_P1]
    preprocesamiento = ColumnTransformer([
        ("numericas", StandardScaler(), numericas),
        ("categoricas", OneHotEncoder(handle_unknown="ignore"), CATEGORICAS_P1),
    ])
    return Pipeline([("preprocesamiento", preprocesamiento), ("regresion", Ridge(alpha=h["alpha"]))])


def entrenar_p1(modelo, h, semilla, conjuntos):
    entrenamiento, validacion, prueba = conjuntos
    columnas, objetivo = features.COLUMNAS_P1, features.OBJETIVO_P1
    if modelo == "naive7":
        ajustado, tiempo = None, 0.0
        predecir = lambda df: df["rezago_7"].to_numpy(dtype=float)
    else:
        ajustado = regresor_p1(modelo, h, semilla)
        _, tiempo = artefactos.cronometrar(ajustado.fit, entrenamiento[columnas], entrenamiento[objetivo])
        predecir = lambda df: ajustado.predict(df[columnas])
    metricas = {}
    for nombre, conjunto in [("val", validacion), ("test", prueba)]:
        prediccion = predecir(conjunto)
        metricas[f"{nombre}_mae"] = mean_absolute_error(conjunto[objetivo], prediccion)
        metricas[f"{nombre}_rmse"] = root_mean_squared_error(conjunto[objetivo], prediccion)
    prediccion_prueba, tiempo_inferencia = artefactos.cronometrar(predecir, prueba)
    return {
        "modelo": ajustado, "metricas": metricas, "tiempo_entrenamiento": tiempo, "tiempo_inferencia": tiempo_inferencia,
        "prueba": prueba, "prediccion_prueba": prediccion_prueba, "objetivo": objetivo,
        "entrenamiento": entrenamiento[columnas + [objetivo]], "ejemplo": prueba[columnas].head(100),
    }


# P2: riesgo por estación y hora

def clasificador_p2(modelo, h, semilla):
    if modelo == "dummy":
        clasificador = DummyClassifier(strategy="stratified", random_state=semilla)
    elif modelo == "regresion_logistica":
        clasificador = LogisticRegression(C=h["C"], class_weight="balanced", max_iter=h["max_iter"])
    elif modelo == "bosque":
        clasificador = RandomForestClassifier(n_estimators=h["n_estimators"], max_depth=h["max_depth"],
                                              min_samples_leaf=h["min_samples_leaf"], class_weight="balanced",
                                              random_state=semilla, n_jobs=-1)
    else:
        clasificador = HistGradientBoostingClassifier(learning_rate=h["learning_rate"], max_iter=h["n_estimators"],
                                                      max_depth=h["max_depth"], class_weight="balanced", random_state=semilla)
    numericas = [columna for columna in features.COLUMNAS_P2 if columna not in features.CATEGORICAS_P2]
    preprocesamiento = ColumnTransformer([
        ("numericas", StandardScaler(), numericas),
        ("categoricas", OneHotEncoder(handle_unknown="ignore"), features.CATEGORICAS_P2),
    ])
    return Pipeline([("preprocesamiento", preprocesamiento), ("clasificador", clasificador)])


def elegir_umbral(real, probabilidad, costo_falso_negativo=config.COSTO_FALSO_NEGATIVO):
    """Umbral de decisión que minimiza falsos positivos más costo_falso_negativo veces los falsos negativos."""
    real = np.asarray(real).astype(bool)
    probabilidad = np.asarray(probabilidad)
    candidatos = np.round(np.arange(0.01, 1.0, 0.01), 2)
    costos = []
    for umbral in candidatos:
        alerta = probabilidad >= umbral
        costos.append(int(np.sum(alerta & ~real)) + costo_falso_negativo * int(np.sum(~alerta & real)))
    return float(candidatos[int(np.argmin(costos))]), costos


def metricas_clasificacion(real, prediccion, puntuacion, prefijo):
    matriz = confusion_matrix(real, prediccion, labels=[0, 1])
    return {
        f"{prefijo}_recall": recall_score(real, prediccion, zero_division=0),
        f"{prefijo}_precision": precision_score(real, prediccion, zero_division=0),
        f"{prefijo}_f1": f1_score(real, prediccion, zero_division=0),
        f"{prefijo}_pr_auc": average_precision_score(real, puntuacion),
        f"{prefijo}_falsos_positivos": int(matriz[0, 1]),
        f"{prefijo}_falsos_negativos": int(matriz[1, 0]),
        f"{prefijo}_positivos": int(np.sum(real)),
        f"{prefijo}_costo": int(matriz[0, 1]) + config.COSTO_FALSO_NEGATIVO * int(matriz[1, 0]),
    }


def entrenar_p2(modelo, h, semilla, conjuntos):
    entrenamiento, validacion, prueba = conjuntos
    columnas, objetivo = features.COLUMNAS_P2, features.OBJETIVO_P2
    umbral, origen_umbral = None, None
    if modelo == "regla_semana":
        ajustado, tiempo = None, 0.0
        predecir = lambda df: df["riesgo_semana_anterior"].to_numpy().astype(int)
        puntuar = lambda df: df["riesgo_semana_anterior"].to_numpy(dtype=float)
    else:
        canalizacion = clasificador_p2(modelo, h, semilla)
        _, tiempo = artefactos.cronometrar(canalizacion.fit, entrenamiento[columnas], entrenamiento[objetivo])
        if modelo == "dummy":
            ajustado = canalizacion
        else:
            umbral, origen_umbral = h.get("threshold"), "argumento"
            if umbral is None:
                umbral, _ = elegir_umbral(validacion[objetivo], canalizacion.predict_proba(validacion[columnas])[:, 1])
                origen_umbral = "validacion"
            ajustado = FixedThresholdClassifier(FrozenEstimator(canalizacion), threshold=umbral)
            ajustado.fit(validacion[columnas], validacion[objetivo])
        predecir = lambda df: ajustado.predict(df[columnas])
        puntuar = lambda df: ajustado.predict_proba(df[columnas])[:, 1]
    metricas = {}
    for nombre, conjunto in [("val", validacion), ("test", prueba)]:
        metricas.update(metricas_clasificacion(conjunto[objetivo], predecir(conjunto), puntuar(conjunto), nombre))
    prediccion_prueba, tiempo_inferencia = artefactos.cronometrar(predecir, prueba)
    return {
        "modelo": ajustado, "metricas": metricas, "tiempo_entrenamiento": tiempo, "tiempo_inferencia": tiempo_inferencia,
        "prueba": prueba, "prediccion_prueba": prediccion_prueba, "puntuacion_prueba": puntuar(prueba), "objetivo": objetivo,
        "umbral": umbral, "origen_umbral": origen_umbral,
        "entrenamiento": entrenamiento[columnas + [objetivo]], "ejemplo": prueba[columnas].head(100),
    }


# P3: grupos de estaciones

def agrupador_p3(modelo, h, semilla):
    pasos = [("escalado", StandardScaler())]
    if modelo == "kmeans_pca":
        pasos.append(("pca", PCA(n_components=h["componentes"], random_state=semilla)))
    if modelo == "aglomerativo":
        pasos.append(("aglomerativo", AgglomerativeClustering(n_clusters=h["k"], linkage="ward")))
    else:
        pasos.append(("kmeans", KMeans(n_clusters=h["k"], n_init=10, random_state=semilla)))
    return Pipeline(pasos)


def inercia(escalado, grupos):
    """Suma de distancias al cuadrado de cada estación al centro de su grupo, en el espacio escalado de las 98 variables."""
    total = 0.0
    for grupo in np.unique(grupos):
        parte = escalado[grupos == grupo]
        total += float(((parte - parte.mean(axis=0)) ** 2).sum())
    return total


def entrenar_p3(modelo, h, semilla, conjuntos):
    perfil = conjuntos
    columnas = [columna for columna in perfil.columns if columna not in IDENTIFICACION_P3]
    X = perfil[columnas]
    ajustado = agrupador_p3(modelo, h, semilla)
    grupos, tiempo = artefactos.cronometrar(ajustado.fit_predict, X)
    escalado = ajustado.named_steps["escalado"].transform(X)
    metricas = {
        "train_silhouette": silhouette_score(escalado, grupos),
        "train_davies_bouldin": davies_bouldin_score(escalado, grupos),
        "train_inercia": inercia(escalado, grupos),
    }
    tiempo_inferencia, salida_ejemplo = None, grupos[:100]
    if hasattr(ajustado, "predict"):
        _, tiempo_inferencia = artefactos.cronometrar(ajustado.predict, X)
        salida_ejemplo = None
    return {
        "modelo": ajustado, "metricas": metricas, "tiempo_entrenamiento": tiempo, "tiempo_inferencia": tiempo_inferencia,
        "perfil": perfil, "grupos": grupos, "entrenamiento": X, "ejemplo": X.head(100), "salida_ejemplo": salida_ejemplo,
    }


def entrenar(pregunta, modelo, h, semilla, conjuntos):
    correr = {"p1": entrenar_p1, "p2": entrenar_p2, "p3": entrenar_p3}[pregunta]
    return correr(modelo, h, semilla, conjuntos)


# Registro en MLflow

def graficas(pregunta, resultado, destino):
    if pregunta == "p1":
        prueba, objetivo = resultado["prueba"], resultado["objetivo"]
        plots.grafica_real_vs_predicho(prueba["fecha"], prueba[objetivo], resultado["prediccion_prueba"], destino / "real_vs_predicho.png")
        plots.grafica_residuales(prueba[objetivo], resultado["prediccion_prueba"], destino / "residuales.png")
    elif pregunta == "p2":
        prueba, objetivo = resultado["prueba"], resultado["objetivo"]
        plots.grafica_matriz_confusion(prueba[objetivo], resultado["prediccion_prueba"], destino / "matriz_confusion.png")
        plots.grafica_curva_precision_recall(prueba[objetivo], resultado["puntuacion_prueba"], destino / "curva_precision_recall.png",
                                             resultado["umbral"])
    else:
        plots.grafica_mapa_grupos(resultado["perfil"], resultado["grupos"], destino / "mapa_grupos.png")
        plots.grafica_perfiles_grupos(resultado["perfil"], resultado["grupos"], destino / "perfiles_grupos.png")


def metricas_de_costo(resultado):
    metricas = dict(resultado["metricas"])
    metricas["tiempo_entrenamiento_s"] = resultado["tiempo_entrenamiento"]
    if resultado["tiempo_inferencia"] is not None:
        metricas["tiempo_inferencia_s"] = resultado["tiempo_inferencia"]
    metricas["tamano_modelo_mb"] = artefactos.tamano_modelo_mb(resultado["modelo"])
    return metricas


def registrar_artefactos_completos(resultado, pregunta, h, args, version_datos, carpeta, fuente=FUENTE):
    """Gráficas en plots/, manifiesto y conjunto de entrenamiento en data/, configuración en config/ y el modelo con firma."""
    carpeta = artefactos.preparar_carpeta(carpeta)
    graficas(pregunta, resultado, carpeta / "plots")
    artefactos.registrar_datos(resultado["entrenamiento"], pregunta, version_datos, carpeta, resultado.get("objetivo"))
    artefactos.registrar_configuracion(args, h, carpeta)
    if pregunta == "p3":
        asignacion = resultado["perfil"][IDENTIFICACION_P3].assign(grupo=resultado["grupos"])
        asignacion.to_csv(carpeta / "data" / "grupos_estaciones.csv", index=False)
        mlflow.log_param("grupos", json.dumps(asignacion["grupo"].value_counts().sort_index().to_dict()))
    if resultado["modelo"] is not None:
        artefactos.registrar_modelo(resultado["modelo"], resultado["ejemplo"], resultado.get("salida_ejemplo"), fuente)


def registrar_resultado(resultado, pregunta, h, args, version_datos, carpeta, completo=True, fuente=FUENTE):
    carpeta = Path(carpeta)
    if resultado.get("umbral") is not None:
        texto = getattr(args, "textos", {}).get("threshold", resultado["umbral"])
        mlflow.log_params({"threshold": texto, "threshold_origen": resultado["origen_umbral"]})
    if completo:
        registrar_artefactos_completos(resultado, pregunta, h, args, version_datos, carpeta, fuente)
    metricas = artefactos.registrar_metricas(metricas_de_costo(resultado), carpeta)
    artefactos.registrar_artefactos(carpeta)
    return metricas


def main():
    args = leer_argumentos()
    pregunta, modelo = args.pregunta, args.modelo
    if modelo not in MODELOS[pregunta]:
        raise SystemExit(f"el modelo {modelo} no aplica a {pregunta}; opciones: {MODELOS[pregunta]}")
    h, args.textos = resolver_hiperparametros(pregunta, modelo, args)
    etapa = etapa_de_trabajo(pregunta, modelo, h)
    nombre = args.nombre_corrida or f"{pregunta}_{modelo}"
    inicio = time.time()

    viajes, estaciones, manifiesto = cargar_datos()
    mlflow.set_tracking_uri(args.tracking_uri)
    mlflow.set_experiment(args.experimento)
    reanudada = bool(os.environ.get("MLFLOW_RUN_ID"))
    with mlflow.start_run(run_name=None if reanudada else nombre) as corrida:
        if corrida.info.run_name != nombre:
            mlflow.set_tag("mlflow.runName", nombre)
        mlflow.set_tags(etiquetas(pregunta, modelo, etapa))
        mlflow.log_params({**parametros_comunes(args, manifiesto), **parametros_hiperparametros(h, args.textos)})
        conjuntos = construir_conjuntos(pregunta, viajes, estaciones, args)
        registrar_conjuntos(pregunta, conjuntos, args)
        resultado = entrenar(pregunta, modelo, h, args.semilla, conjuntos)
        with tempfile.TemporaryDirectory() as temporal:
            metricas = registrar_resultado(resultado, pregunta, h, args, manifiesto["version_datos"], temporal)

    print("Corrida:", nombre, "(" + corrida.info.run_id + ")", etapa)
    for clave, valor in metricas.items():
        print(f"{clave}: {valor:.4f}")
    if resultado.get("umbral") is not None:
        print("Umbral de decisión:", resultado["umbral"], "elegido en", resultado["origen_umbral"])
    if pregunta == "p3":
        print("Estaciones por grupo:", pd.Series(resultado["grupos"]).value_counts().sort_index().to_dict())
    print("Tiempo:", round(time.time() - inicio, 1), "s")


if __name__ == "__main__":
    main()
