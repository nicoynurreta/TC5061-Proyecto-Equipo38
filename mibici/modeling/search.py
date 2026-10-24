import argparse
import itertools
import json
import os
import tempfile
import time
from pathlib import Path

import mlflow
import pandas as pd

from mibici import config, plots
from mibici.modeling import artefactos, train

METRICA_BUSQUEDA = {"p1": ("val_mae", True), "p2": ("val_costo", True), "p3": ("train_silhouette", False)}
ABREVIATURAS = {"learning_rate": "lr", "max_depth": "md", "n_estimators": "n", "min_samples_leaf": "hoja",
                "componentes": "pca", "alpha": "a"}
FUENTE = "mibici/modeling/search.py"


def leer_argumentos():
    parser = argparse.ArgumentParser(
        description="Búsqueda de hiperparámetros de una pregunta del proyecto MiBici con nested runs: una corrida padre y una hija por combinación de config.BUSQUEDAS."
    )
    parser.add_argument("--pregunta", choices=["p1", "p2", "p3"], required=True)
    parser.add_argument("--modelo", required=True, help="modelo con rejilla en config.BUSQUEDAS (hgb en p1 y p2, kmeans en p3)")
    parser.add_argument("--nombre_corrida", default="", help="nombre de la corrida padre (por defecto pregunta_busqueda_modelo)")
    parser.add_argument("--semilla", type=int, default=config.SEMILLA)
    parser.add_argument("--fin_entrenamiento", default=config.FIN_ENTRENAMIENTO)
    parser.add_argument("--fin_validacion", default=config.FIN_VALIDACION)
    parser.add_argument("--umbral_riesgo", type=float, default=config.UMBRAL_RIESGO)
    parser.add_argument("--experimento", default=config.EXPERIMENTO)
    parser.add_argument("--tracking_uri", default=os.environ.get("MLFLOW_TRACKING_URI", config.TRACKING_URI))
    args = parser.parse_args()
    args.modelo = train.limpiar(args.modelo)
    args.nombre_corrida = train.limpiar(args.nombre_corrida)
    return args


def combinaciones(busqueda):
    """Una combinación por elemento del producto cartesiano de la rejilla, más los hiperparámetros fijos."""
    claves = list(busqueda["rejilla"])
    for valores in itertools.product(*(busqueda["rejilla"][clave] for clave in claves)):
        yield {**busqueda["fijos"], **dict(zip(claves, valores))}


def etiqueta_combinacion(valores, claves):
    partes = []
    for clave in claves:
        valor = "sin_limite" if valores[clave] is None else valores[clave]
        partes.append(f"{ABREVIATURAS.get(clave, clave)}{valor}")
    return "_".join(partes)


def es_mejor(valor, referencia, menor_es_mejor):
    if referencia is None:
        return True
    return valor < referencia if menor_es_mejor else valor > referencia


def main():
    args = leer_argumentos()
    pregunta, modelo = args.pregunta, args.modelo
    if modelo not in config.BUSQUEDAS.get(pregunta, {}):
        raise SystemExit(f"no hay rejilla para {modelo} en {pregunta}; opciones: {list(config.BUSQUEDAS[pregunta])}")
    busqueda = config.BUSQUEDAS[pregunta][modelo]
    claves = list(busqueda["rejilla"])
    metrica, menor_es_mejor = METRICA_BUSQUEDA[pregunta]
    nombre = args.nombre_corrida or f"{pregunta}_busqueda_{modelo}"
    inicio = time.time()

    viajes, estaciones, manifiesto = train.cargar_datos()
    version_datos = manifiesto["version_datos"]
    mlflow.set_tracking_uri(args.tracking_uri)
    mlflow.set_experiment(args.experimento)
    reanudada = bool(os.environ.get("MLFLOW_RUN_ID"))
    with mlflow.start_run(run_name=None if reanudada else nombre) as padre:
        if padre.info.run_name != nombre:
            mlflow.set_tag("mlflow.runName", nombre)
        mlflow.set_tags(train.etiquetas(pregunta, modelo, "search", FUENTE))
        comunes = train.parametros_comunes(args, manifiesto)
        mlflow.log_params({**comunes, "rejilla": json.dumps(busqueda["rejilla"]), "fijos": json.dumps(busqueda["fijos"]),
                           "combinaciones": len(list(combinaciones(busqueda))), "metrica_busqueda": metrica})
        conjuntos = train.construir_conjuntos(pregunta, viajes, estaciones, args)
        train.registrar_conjuntos(pregunta, conjuntos, args)

        resultados, mejor = [], None
        for indice, valores in enumerate(combinaciones(busqueda), start=1):
            h = train.completar_hiperparametros(pregunta, modelo, valores)
            etiqueta = etiqueta_combinacion(h, claves)
            with mlflow.start_run(run_name=f"{nombre}_{etiqueta}", nested=True) as hija:
                mlflow.set_tags({**train.etiquetas(pregunta, modelo, "search", FUENTE), "combinacion": etiqueta})
                mlflow.log_params({**comunes, **train.parametros_hiperparametros(h), "combinacion": etiqueta})
                train.registrar_conjuntos(pregunta, conjuntos, args)
                resultado = train.entrenar(pregunta, modelo, h, args.semilla, conjuntos)
                with tempfile.TemporaryDirectory() as temporal:
                    metricas = train.registrar_resultado(resultado, pregunta, h, args, version_datos, temporal, completo=False)
            mlflow.log_metric(f"{metrica}_por_combinacion", metricas[metrica], step=indice)
            resultados.append({"combinacion": etiqueta, "run_id": hija.info.run_id, **train.parametros_hiperparametros(h), **metricas})
            print(indice, etiqueta, metrica, round(metricas[metrica], 4), "tiempo_entrenamiento_s", round(metricas["tiempo_entrenamiento_s"], 1))
            if es_mejor(metricas[metrica], None if mejor is None else mejor["metricas"][metrica], menor_es_mejor):
                mejor = {"run_id": hija.info.run_id, "etiqueta": etiqueta, "h": h, "resultado": resultado, "metricas": metricas}

        tabla = pd.DataFrame(resultados)
        with tempfile.TemporaryDirectory() as temporal:
            carpeta = artefactos.preparar_carpeta(temporal)
            tabla.to_csv(carpeta / "data" / "resultados_busqueda.csv", index=False)
            plots.grafica_resultados_busqueda(tabla, metrica, carpeta / "plots" / "resultados_busqueda.png", menor_es_mejor)
            artefactos.registrar_datos(mejor["resultado"]["entrenamiento"], pregunta, version_datos, carpeta, mejor["resultado"].get("objetivo"))
            artefactos.registrar_configuracion(args, {"fijos": busqueda["fijos"], "rejilla": busqueda["rejilla"]}, carpeta)
            artefactos.registrar_metricas({f"mejor_{metrica}": mejor["metricas"][metrica], "tiempo_busqueda_s": time.time() - inicio}, carpeta)
            artefactos.registrar_artefactos(carpeta)
        mlflow.set_tags({"mejor_hija": mejor["run_id"], "mejor_combinacion": mejor["etiqueta"]})

        with mlflow.start_run(run_id=mejor["run_id"], nested=True):
            mlflow.set_tags({"mlflow.runName": f"{pregunta}_{modelo}_mejor", "stage_of_work": "candidate", "mejor_de_busqueda": "true"})
            with tempfile.TemporaryDirectory() as temporal:
                train.registrar_artefactos_completos(mejor["resultado"], pregunta, mejor["h"], args, version_datos, Path(temporal), FUENTE)
                artefactos.registrar_artefactos(temporal)

    print("Búsqueda:", nombre, "(" + padre.info.run_id + ")", len(resultados), "combinaciones")
    print("Mejor combinación:", mejor["etiqueta"], "(" + mejor["run_id"] + ")", metrica, round(mejor["metricas"][metrica], 4))
    print("Tiempo:", round(time.time() - inicio, 1), "s")


if __name__ == "__main__":
    main()
