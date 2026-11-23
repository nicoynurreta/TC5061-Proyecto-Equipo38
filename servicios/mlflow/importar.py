"""Copia el registry del equipo (mlflow.db y mlartifacts/) a los volúmenes del servicio de MLflow."""
import shutil
import sqlite3
import sys
from pathlib import Path

ORIGEN = Path("/origen")
BASE = Path("/mlflow/datos/mlflow.db")
ARTEFACTOS = Path("/mlflow/artefactos")


def contenido(base):
    """Corridas, versiones registradas y alias de una base de MLflow."""
    conexion = sqlite3.connect(base)
    try:
        corridas = conexion.execute("select count(*) from runs where lifecycle_stage = 'active'").fetchone()[0]
        versiones = conexion.execute("select count(*) from model_versions").fetchone()[0]
        alias = conexion.execute("select name, alias, version from registered_model_aliases order by name, alias").fetchall()
    finally:
        conexion.close()
    return corridas, versiones, alias


def importar(origen=ORIGEN, base=BASE, artefactos=ARTEFACTOS):
    """Copia la base y los artefactos; la base llega con otro nombre y se renombra al final para no dejarla a medias."""
    base_origen = Path(origen) / "mlflow.db"
    artefactos_origen = Path(origen) / "mlartifacts"
    if not base_origen.is_file() or not artefactos_origen.is_dir():
        raise FileNotFoundError("faltan mlflow.db o mlartifacts/ en la raíz del repositorio")
    base = Path(base)
    base.parent.mkdir(parents=True, exist_ok=True)
    temporal = base.with_suffix(".importando")
    shutil.copyfile(base_origen, temporal)
    temporal.replace(base)
    shutil.copytree(artefactos_origen, artefactos, dirs_exist_ok=True)
    archivos = [archivo for archivo in Path(artefactos).rglob("*") if archivo.is_file()]
    return contenido(base), len(archivos), sum(archivo.stat().st_size for archivo in archivos)


def main():
    try:
        (corridas, versiones, alias), archivos, tamano = importar()
    except FileNotFoundError as error:
        print("no hay registry que importar:", error)
        return 1
    print(f"registry importado: {corridas} corridas, {versiones} versiones registradas, {archivos} artefactos ({tamano / 1e6:.1f} MB)")
    for nombre, etiqueta, version in alias:
        print(f"  {nombre}@{etiqueta} -> versión {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
