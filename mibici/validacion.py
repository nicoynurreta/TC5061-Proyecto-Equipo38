import argparse
import json
import time
from datetime import datetime

import pandas as pd

from mibici import config, dataset, features

ARCHIVO_EXPORTACION = config.DIR_DATOS_INTERMEDIOS / "exportacion.json"
MUESTRA_P2 = 200000
MES_CRUDO = config.MESES[0]
CATEGORICAS_P1 = ["dia_semana", "mes"]
ESQUEMAS = {
    "viajes_crudos": {"indice": "viaje_id", "tiempo": "inicio", "features": ["origen_id", "destino_id", "duracion_min"],
                      "categoricas": ["origen_id", "destino_id"], "necesarias": dataset.COLUMNAS_NECESARIAS},
    "p1": {"tiempo": "fecha", "objetivo": features.OBJETIVO_P1, "tipo": "regression",
           "features": features.COLUMNAS_P1, "categoricas": CATEGORICAS_P1},
    "p2": {"tiempo": "hora", "objetivo": features.OBJETIVO_P2, "tipo": "binary",
           "features": features.COLUMNAS_P2, "categoricas": features.CATEGORICAS_P2},
    "p3": {"indice": "estacion_id", "identificacion": ["estacion_id", "nombre", "latitud", "longitud"]},
}


def muestrear(df, filas, semilla):
    """Muestra sin reemplazo en el orden original del conjunto; completo si tiene menos filas que las pedidas."""
    if len(df) <= filas:
        return df
    return df.sample(n=filas, random_state=semilla).sort_index()


def particiones(pregunta, conjuntos):
    """Nombra las particiones de entrenamiento, validación y prueba de una pregunta."""
    nombres = [f"{pregunta}_entrenamiento", f"{pregunta}_validacion", f"{pregunta}_prueba"]
    return dict(zip(nombres, conjuntos))


def viajes_crudos(mes, forzar=False):
    """Lee los viajes de un mes tal como los publica el portal, antes de limpiar_viajes, y cuenta lo que la limpieza descartaría."""
    enlaces = dataset.obtener_enlaces()
    if mes not in enlaces:
        raise SystemExit(f"el portal no publica el mes {mes}")
    url = enlaces[mes]
    ruta = config.DIR_DATOS_CRUDOS / url.rsplit("/", 1)[-1]
    tamano = dataset.descargar(url, ruta, forzar)
    df, codificacion = dataset.leer_csv(ruta)
    _, conteo = dataset.limpiar_viajes(df)
    df = dataset.normalizar_columnas(df, dataset.COLUMNAS_VIAJES)
    df = df.drop(columns=[columna for columna in dataset.COLUMNAS_PERSONALES if columna in df.columns])
    df["inicio"] = pd.to_datetime(df["inicio"], errors="coerce")
    df["fin"] = pd.to_datetime(df["fin"], errors="coerce")
    df["duracion_min"] = (df["fin"] - df["inicio"]).dt.total_seconds() / 60
    detalle = {"mes": mes, "archivo": ruta.name, "url": url, "bytes": tamano, "codificacion": codificacion,
               "columnas_excluidas": dataset.COLUMNAS_PERSONALES, "limpieza": conteo}
    return df, detalle


def escribir(tablas, carpeta):
    """Escribe cada tabla en Parquet y devuelve filas, columnas, bytes y segundos por tabla."""
    registro = {}
    for nombre, df in tablas.items():
        inicio = time.perf_counter()
        ruta = carpeta / f"{nombre}.parquet"
        df.to_parquet(ruta, index=False)
        registro[nombre] = {"archivo": ruta.name, "filas": len(df), "columnas": len(df.columns),
                            "bytes": ruta.stat().st_size, "segundos": round(time.perf_counter() - inicio, 2)}
    return registro


def exportar(args):
    """Escribe en data/interim las particiones de P1, la muestra de P2, el perfil de P3 y un mes de viajes crudos."""
    if not (config.ARCHIVO_VIAJES.exists() and config.ARCHIVO_ESTACIONES.exists()):
        print("No hay datos procesados en", config.DIR_DATOS_PROCESADOS.relative_to(config.RAIZ_PROYECTO).as_posix())
        print("Genera los datos con make ingest (o mlflow run . -e ingest --experiment-name", config.EXPERIMENTO, "--env-manager local) y vuelve a correr este comando")
        return
    inicio = time.time()
    config.DIR_DATOS_INTERMEDIOS.mkdir(parents=True, exist_ok=True)
    viajes = pd.read_parquet(config.ARCHIVO_VIAJES)
    estaciones = pd.read_parquet(config.ARCHIVO_ESTACIONES)
    with open(config.ARCHIVO_MANIFIESTO, encoding="utf-8") as archivo:
        manifiesto = json.load(archivo)

    tablas = particiones("p1", features.conjuntos_p1(viajes, estaciones))
    completos = {}
    for nombre, conjunto in particiones("p2", features.conjuntos_p2(viajes, estaciones)).items():
        completos[nombre] = {"filas_completas": len(conjunto), "positivos_completos": int(conjunto[features.OBJETIVO_P2].sum())}
        tablas[nombre] = muestrear(conjunto, args.muestra, args.semilla)
        completos[nombre]["positivos"] = int(tablas[nombre][features.OBJETIVO_P2].sum())
    tablas["p3_perfil"] = features.conjunto_p3(viajes, estaciones)
    tablas["viajes_crudos"], crudos = viajes_crudos(args.mes, args.forzar)
    segundos_conjuntos = round(time.time() - inicio, 1)

    registro = escribir(tablas, config.DIR_DATOS_INTERMEDIOS)
    for nombre, valores in completos.items():
        registro[nombre].update(valores)
    exportacion = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "version_datos": manifiesto["version_datos"],
        "fin_entrenamiento": config.FIN_ENTRENAMIENTO,
        "fin_validacion": config.FIN_VALIDACION,
        "muestra_p2": args.muestra,
        "semilla": args.semilla,
        "umbral_riesgo": config.UMBRAL_RIESGO,
        "ventana_riesgo_horas": config.VENTANA_RIESGO_HORAS,
        "costo_falso_negativo": config.COSTO_FALSO_NEGATIVO,
        "duracion_minima_min": config.DURACION_MINIMA_MIN,
        "duracion_maxima_min": config.DURACION_MAXIMA_MIN,
        "esquemas": ESQUEMAS,
        "tablas": registro,
        "viajes_crudos": crudos,
        "segundos_conjuntos": segundos_conjuntos,
        "segundos": round(time.time() - inicio, 1),
    }
    with open(ARCHIVO_EXPORTACION, "w", encoding="utf-8") as archivo:
        json.dump(exportacion, archivo, indent=2, ensure_ascii=False)

    for nombre, valores in registro.items():
        print(nombre + ":", valores["filas"], "filas,", valores["columnas"], "columnas,", round(valores["bytes"] / 1e6, 2), "MB")
    for nombre, valores in completos.items():
        print(nombre, "completo:", valores["filas_completas"], "filas,", valores["positivos_completos"], "positivos")
    print("Viajes crudos:", crudos["mes"], crudos["codificacion"], crudos["limpieza"])
    print("Tiempo:", exportacion["segundos"], "s")


def listar():
    """Muestra las tablas que ya están en data/interim o el orden de los pasos si todavía no existen."""
    if not ARCHIVO_EXPORTACION.exists():
        print("No hay tablas exportadas en", config.DIR_DATOS_INTERMEDIOS.relative_to(config.RAIZ_PROYECTO).as_posix())
        print("Orden: make ingest, python -m mibici.validacion --exportar y después chequeos/validar_datos.py")
        return
    with open(ARCHIVO_EXPORTACION, encoding="utf-8") as archivo:
        exportacion = json.load(archivo)
    print("Exportación del", exportacion["generado"], "con versión de datos", exportacion["version_datos"])
    for nombre, valores in exportacion["tablas"].items():
        print(nombre + ":", valores["filas"], "filas,", round(valores["bytes"] / 1e6, 2), "MB")


def leer_argumentos():
    parser = argparse.ArgumentParser(
        description="Exporta a data/interim las tablas que validan los chequeos de DeepChecks (chequeos/validar_datos.py)."
    )
    parser.add_argument("--exportar", action="store_true",
                        help="escribe las particiones de P1, la muestra de P2, el perfil de P3 y un mes de viajes crudos")
    parser.add_argument("--muestra", type=int, default=MUESTRA_P2,
                        help="filas por conjunto en la muestra de P2 (por defecto %(default)s)")
    parser.add_argument("--semilla", type=int, default=config.SEMILLA,
                        help="semilla de la muestra (por defecto %(default)s)")
    parser.add_argument("--mes", default=MES_CRUDO, metavar="AAAA-MM",
                        help="mes de viajes crudos que se exporta antes de la limpieza (por defecto %(default)s)")
    parser.add_argument("--forzar", action="store_true",
                        help="vuelve a descargar el archivo del mes aunque ya esté en data/raw")
    return parser.parse_args()


def main():
    args = leer_argumentos()
    if args.exportar:
        exportar(args)
    else:
        listar()


if __name__ == "__main__":
    main()
