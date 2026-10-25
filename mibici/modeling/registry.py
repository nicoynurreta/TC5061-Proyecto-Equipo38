import argparse
import os

import mlflow
import mlflow.pyfunc
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from mibici import config

NOMBRES = {
    "p1": "mibici-equipo38-p1-demanda",
    "p2": "mibici-equipo38-p2-riesgo",
    "p3": "mibici-equipo38-p3-grupos",
}
DESCRIPCIONES = {
    "p1": "P1, regresión: viajes iniciados por estación y día con horizonte de un día, para dimensionar flota y personal. "
          "Métrica de decisión: test_mae en viajes por estación y día, frente al baseline estacional de hace siete días.",
    "p2": "P2, clasificación: riesgo de que una estación se llene o se vacíe en las dos horas siguientes, para decidir a dónde "
          "mandar el camión de rebalanceo. Métrica de decisión: test_costo (falsos positivos más cinco veces los falsos negativos); "
          "el umbral de decisión forma parte del modelo.",
    "p3": "P3, clustering: grupos de estaciones por su perfil horario de salidas y llegadas, para planear expansión y reubicación. "
          "Métrica de decisión: train_silhouette junto con la lectura operativa de los grupos.",
}
ESQUEMA = "Alias champion: versión en producción, la que carga predict.py; challenger: la siguiente mejor candidata, lista para sustituirla."
METRICA_DECISION = {"p1": "test_mae", "p2": "test_costo", "p3": "train_silhouette"}


def leer_argumentos():
    parser = argparse.ArgumentParser(
        description="Registra las corridas elegidas de una pregunta en el Model Registry con su linaje y los alias champion y challenger, o verifica la carga de los modelos en producción."
    )
    parser.add_argument("--pregunta", choices=["p1", "p2", "p3"], help="pregunta cuyo modelo se registra")
    parser.add_argument("--champion", help="run_id de la corrida que pasa a producción")
    parser.add_argument("--challenger", default=None, help="run_id de la siguiente mejor corrida (opcional)")
    parser.add_argument("--verificar", action="store_true", help="carga models:/<nombre>@champion de las tres preguntas y predice con su ejemplo de entrada")
    parser.add_argument("--tracking_uri", default=os.environ.get("MLFLOW_TRACKING_URI", config.TRACKING_URI))
    args = parser.parse_args()
    if not args.verificar and not (args.pregunta and args.champion):
        parser.error("hacen falta --pregunta y --champion, o bien --verificar")
    return args


def linaje(cliente, corrida, pregunta):
    """Etiquetas de la versión: experimento, corrida de origen, commit, versión de los datos y métrica de decisión."""
    metrica = METRICA_DECISION[pregunta]
    etiquetas = {
        "experimento": cliente.get_experiment(corrida.info.experiment_id).name,
        "run_id": corrida.info.run_id,
        "corrida": corrida.info.run_name,
        "modelo": corrida.data.params.get("modelo", ""),
        "version_datos": corrida.data.params.get("version_datos", ""),
        "commit_git": corrida.data.tags.get("commit_git", ""),
        "rama": corrida.data.tags.get("rama", ""),
        "metrica_decision": metrica,
        metrica: str(round(corrida.data.metrics.get(metrica, float("nan")), 4)),
    }
    if "threshold" in corrida.data.params:
        etiquetas["threshold"] = corrida.data.params["threshold"]
    return etiquetas


def descripcion_version(cliente, corrida, pregunta):
    metrica = METRICA_DECISION[pregunta]
    parametros = corrida.data.params
    return (
        f"{parametros.get('modelo', 'modelo')} de la corrida {corrida.info.run_name} ({corrida.info.run_id[:8]}) del experimento "
        f"{cliente.get_experiment(corrida.info.experiment_id).name}; commit {corrida.data.tags.get('commit_git', '')[:7]}, "
        f"datos {parametros.get('version_datos', '')}; {metrica} {corrida.data.metrics.get(metrica, float('nan')):.4f}; "
        f"entrenamiento hasta {parametros.get('fin_entrenamiento', '')}, validación hasta {parametros.get('fin_validacion', '')} "
        f"y prueba después."
    )


def registrar_version(cliente, pregunta, run_id, alias):
    """Registra el modelo de una corrida bajo el nombre de la pregunta, con descripción, linaje y alias."""
    nombre = NOMBRES[pregunta]
    corrida = cliente.get_run(run_id)
    try:
        cliente.get_registered_model(nombre)
    except MlflowException:
        cliente.create_registered_model(
            nombre,
            tags={"equipo": config.EQUIPO, "pregunta": pregunta.upper(), "question": pregunta, "esquema": "aliases"},
            description=DESCRIPCIONES[pregunta] + " " + ESQUEMA,
        )
    version = mlflow.register_model(uri_del_modelo(corrida), nombre, tags=linaje(cliente, corrida, pregunta))
    cliente.update_model_version(nombre, version.version, description=descripcion_version(cliente, corrida, pregunta))
    cliente.set_registered_model_alias(nombre, alias, version.version)
    return nombre, str(version.version)


def uri_del_modelo(corrida):
    """URI del modelo registrado en la corrida: el último modelo que la corrida produjo."""
    salidas = getattr(corrida, "outputs", None)
    modelos = list(salidas.model_outputs) if salidas is not None else []
    if modelos:
        return f"models:/{modelos[-1].model_id}"
    return f"runs:/{corrida.info.run_id}/modelo"


def verificar(cliente, pregunta):
    """Carga el modelo en producción por nombre y alias y predice con el ejemplo de entrada guardado con el modelo."""
    nombre = NOMBRES[pregunta]
    uri = f"models:/{nombre}@champion"
    modelo = mlflow.pyfunc.load_model(uri)
    version = cliente.get_model_version_by_alias(nombre, "champion")
    ejemplo = modelo.metadata.load_input_example(uri)
    prediccion = modelo.predict(ejemplo)
    print(uri, "-> versión", version.version, "de la corrida", version.tags.get("corrida"), "(" + version.run_id + ")")
    print("  commit", version.tags.get("commit_git", "")[:7], "datos", version.tags.get("version_datos"),
          version.tags.get("metrica_decision"), version.tags.get(version.tags.get("metrica_decision", ""), ""))
    print("  predicción del ejemplo de entrada:", list(prediccion[:5]))
    return version


def main():
    args = leer_argumentos()
    mlflow.set_tracking_uri(args.tracking_uri)
    cliente = MlflowClient()
    if args.verificar:
        for pregunta in NOMBRES:
            verificar(cliente, pregunta)
        return
    nombre, version = registrar_version(cliente, args.pregunta, args.champion, "champion")
    print(nombre, "versión", version, "-> champion (corrida", args.champion + ")")
    if args.challenger:
        nombre, version = registrar_version(cliente, args.pregunta, args.challenger, "challenger")
        print(nombre, "versión", version, "-> challenger (corrida", args.challenger + ")")


if __name__ == "__main__":
    main()
