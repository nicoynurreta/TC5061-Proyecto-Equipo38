import argparse
import hashlib
import json
import re
import time
import unicodedata
from datetime import datetime

import pandas as pd
import requests

from mibici import config

ENCABEZADOS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
}
COLUMNAS_VIAJES = {
    "viaje_id": "viaje_id",
    "usuario_id": "usuario_id",
    "genero": "genero",
    "inicio_del_viaje": "inicio",
    "fin_del_viaje": "fin",
    "origen_id": "origen_id",
    "destino_id": "destino_id",
}
COLUMNAS_ESTACIONES = {
    "id": "estacion_id",
    "name": "nombre",
    "latitude": "latitud",
    "longitude": "longitud",
    "dpcapacity": "capacidad",
}
COLUMNAS_NECESARIAS = ["viaje_id", "inicio", "fin", "origen_id", "destino_id"]
COLUMNAS_PERSONALES = ["usuario_id", "genero", "anio_nacimiento"]


def normalizar_nombre(nombre):
    """Pasa un nombre de columna a snake_case sin acentos; el año de nacimiento se reconoce aunque venga mal codificado."""
    texto = unicodedata.normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^0-9a-zA-Z]+", "_", texto).strip("_").lower()
    if "nacimiento" in texto:
        return "anio_nacimiento"
    return texto


def normalizar_columnas(df, equivalencias):
    """Renombra las columnas de un DataFrame con los nombres que usa el proyecto."""
    df = df.rename(columns={columna: normalizar_nombre(columna) for columna in df.columns})
    return df.rename(columns=equivalencias)


def obtener_enlaces():
    """Lee la página de datos abiertos y devuelve la URL del archivo de viajes de cada mes (AAAA-MM)."""
    respuesta = requests.get(config.URL_DATOS_ABIERTOS, headers=ENCABEZADOS, timeout=60)
    respuesta.raise_for_status()
    patron = r'href="([^"]*datos_abiertos_(\d{4})_(\d{2})[^"]*\.csv)"'
    enlaces = {}
    for ruta, anio, mes in re.findall(patron, respuesta.text):
        enlaces.setdefault(f"{anio}-{mes}", requests.compat.urljoin(config.URL_DATOS_ABIERTOS, ruta))
    return enlaces


def descargar(url, destino, forzar=False):
    """Descarga un archivo a data/raw si todavía no está y devuelve su tamaño en bytes."""
    if destino.exists() and not forzar:
        return destino.stat().st_size
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(".part")
    with requests.get(url, headers=ENCABEZADOS, stream=True, timeout=120) as respuesta:
        respuesta.raise_for_status()
        with open(parcial, "wb") as archivo:
            for bloque in respuesta.iter_content(chunk_size=1 << 20):
                archivo.write(bloque)
    parcial.replace(destino)
    return destino.stat().st_size


def sha256_archivo(ruta):
    """Suma de verificación SHA-256 de un archivo, leído por bloques."""
    resumen = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        for bloque in iter(lambda: archivo.read(1 << 20), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


def leer_csv(ruta):
    """Lee un CSV del portal probando UTF-8 y, si falla, Latin-1; devuelve el DataFrame y la codificación."""
    try:
        return pd.read_csv(ruta, encoding="utf-8"), "utf-8"
    except UnicodeDecodeError:
        return pd.read_csv(ruta, encoding="latin-1"), "latin-1"


def limpiar_viajes(df):
    """Normaliza columnas y tipos de un mes de viajes, quita los datos personales y descarta registros inválidos."""
    df = normalizar_columnas(df, COLUMNAS_VIAJES)
    faltantes = [columna for columna in COLUMNAS_NECESARIAS if columna not in df.columns]
    if faltantes:
        raise ValueError(f"faltan columnas en el archivo de viajes: {faltantes}")
    conteo = {"registros_crudos": len(df)}
    df = df.drop(columns=[columna for columna in COLUMNAS_PERSONALES if columna in df.columns])
    df["viaje_id"] = pd.to_numeric(df["viaje_id"], errors="coerce")
    df["inicio"] = pd.to_datetime(df["inicio"], errors="coerce")
    df["fin"] = pd.to_datetime(df["fin"], errors="coerce")
    df["origen_id"] = pd.to_numeric(df["origen_id"], errors="coerce")
    df["destino_id"] = pd.to_numeric(df["destino_id"], errors="coerce")
    sin_datos = df[COLUMNAS_NECESARIAS].isna().any(axis=1)
    conteo["sin_fecha_o_estacion"] = int(sin_datos.sum())
    df = df[~sin_datos]
    duplicados = df["viaje_id"].duplicated()
    conteo["duplicados"] = int(duplicados.sum())
    df = df[~duplicados].copy()
    df["duracion_min"] = (df["fin"] - df["inicio"]).dt.total_seconds() / 60
    negativos = df["duracion_min"] < 0
    cortos = (df["duracion_min"] >= 0) & (df["duracion_min"] < config.DURACION_MINIMA_MIN)
    largos = df["duracion_min"] > config.DURACION_MAXIMA_MIN
    conteo["duracion_negativa"] = int(negativos.sum())
    conteo["duracion_menor_1_min"] = int(cortos.sum())
    conteo["duracion_mayor_24_h"] = int(largos.sum())
    df = df[~(negativos | cortos | largos)]
    df = df.astype({"viaje_id": "int64", "origen_id": "int32", "destino_id": "int32", "duracion_min": "float32"})
    return df[COLUMNAS_NECESARIAS + ["duracion_min"]].reset_index(drop=True), conteo


def leer_estaciones(ruta):
    """Lee la nomenclatura de estaciones con los nombres y tipos del proyecto."""
    df, codificacion = leer_csv(ruta)
    df = normalizar_columnas(df, COLUMNAS_ESTACIONES)
    df["nombre"] = df["nombre"].astype(str).str.strip()
    df = df.astype({"estacion_id": "int32", "latitud": "float64", "longitud": "float64", "capacidad": "int32"})
    df = df[list(COLUMNAS_ESTACIONES.values())].sort_values("estacion_id").reset_index(drop=True)
    return df, codificacion


def marcar_estaciones(viajes, estaciones):
    """Marca si el origen y el destino de cada viaje aparecen en la nomenclatura vigente."""
    conocidas = set(estaciones["estacion_id"])
    viajes["origen_conocido"] = viajes["origen_id"].isin(conocidas)
    viajes["destino_conocido"] = viajes["destino_id"].isin(conocidas)
    return viajes


def escribir_manifiesto(meses, crudos, procesados, limpieza, resumen):
    """Escribe data/manifiesto.json; la versión de los datos sale de las sumas SHA-256 de los archivos crudos."""
    sumas = sorted(archivo["sha256"] for archivo in crudos)
    manifiesto = {
        "version_datos": hashlib.sha256("".join(sumas).encode()).hexdigest()[:12],
        "generado": datetime.now().isoformat(timespec="seconds"),
        "fuente": config.URL_DATOS_ABIERTOS,
        "meses": meses,
        "resumen": resumen,
        "limpieza": limpieza,
        "archivos_crudos": crudos,
        "archivos_procesados": procesados,
    }
    config.ARCHIVO_MANIFIESTO.parent.mkdir(parents=True, exist_ok=True)
    with open(config.ARCHIVO_MANIFIESTO, "w", encoding="utf-8") as archivo:
        json.dump(manifiesto, archivo, indent=2, ensure_ascii=False)
    return manifiesto


def leer_argumentos():
    parser = argparse.ArgumentParser(
        description="Descarga, limpia y versiona los viajes de MiBici y la nomenclatura de estaciones."
    )
    parser.add_argument("--meses", nargs="+", default=config.MESES, metavar="AAAA-MM",
                        help="meses a ingerir (por defecto el rango de config.py, %s a %s)" % (config.MESES[0], config.MESES[-1]))
    parser.add_argument("--forzar", action="store_true",
                        help="vuelve a descargar los archivos que ya estén en data/raw")
    return parser.parse_args()


def main():
    args = leer_argumentos()
    inicio = time.time()
    enlaces = obtener_enlaces()
    faltan = [mes for mes in args.meses if mes not in enlaces]
    if faltan:
        raise SystemExit(f"el portal no publica estos meses: {faltan}")
    config.DIR_DATOS_CRUDOS.mkdir(parents=True, exist_ok=True)
    config.DIR_DATOS_PROCESADOS.mkdir(parents=True, exist_ok=True)

    crudos, partes, limpieza = [], [], {}
    for mes in args.meses:
        url = enlaces[mes]
        ruta = config.DIR_DATOS_CRUDOS / url.rsplit("/", 1)[-1]
        tamano = descargar(url, ruta, args.forzar)
        df, codificacion = leer_csv(ruta)
        viajes_mes, conteo = limpiar_viajes(df)
        crudos.append({"archivo": ruta.name, "url": url, "bytes": tamano, "sha256": sha256_archivo(ruta),
                       "codificacion": codificacion, "registros": conteo["registros_crudos"]})
        for clave, valor in conteo.items():
            limpieza[clave] = limpieza.get(clave, 0) + valor
        partes.append(viajes_mes)
        print(mes, codificacion, conteo["registros_crudos"], "registros,", len(viajes_mes), "viajes válidos")

    ruta_nomenclatura = config.DIR_DATOS_CRUDOS / config.URL_NOMENCLATURA.rsplit("/", 1)[-1]
    tamano = descargar(config.URL_NOMENCLATURA, ruta_nomenclatura, args.forzar)
    estaciones, codificacion = leer_estaciones(ruta_nomenclatura)
    crudos.append({"archivo": ruta_nomenclatura.name, "url": config.URL_NOMENCLATURA, "bytes": tamano,
                   "sha256": sha256_archivo(ruta_nomenclatura), "codificacion": codificacion, "registros": len(estaciones)})

    viajes = pd.concat(partes, ignore_index=True)
    duplicados = viajes["viaje_id"].duplicated()
    limpieza["duplicados_entre_meses"] = int(duplicados.sum())
    viajes = viajes[~duplicados].sort_values("inicio").reset_index(drop=True)
    viajes = marcar_estaciones(viajes, estaciones)
    viajes.to_parquet(config.ARCHIVO_VIAJES, index=False)
    estaciones.to_parquet(config.ARCHIVO_ESTACIONES, index=False)

    procesados = []
    for ruta, registros in [(config.ARCHIVO_VIAJES, len(viajes)), (config.ARCHIVO_ESTACIONES, len(estaciones))]:
        procesados.append({"archivo": ruta.name, "registros": registros, "bytes": ruta.stat().st_size, "sha256": sha256_archivo(ruta)})
    resumen = {
        "viajes": len(viajes),
        "fecha_inicio": str(viajes["inicio"].min().date()),
        "fecha_fin": str(viajes["inicio"].max().date()),
        "estaciones_en_nomenclatura": len(estaciones),
        "estaciones_con_viajes": int(pd.concat([viajes["origen_id"], viajes["destino_id"]]).nunique()),
        "viajes_con_estacion_fuera_de_nomenclatura": int((~(viajes["origen_conocido"] & viajes["destino_conocido"])).sum()),
    }
    manifiesto = escribir_manifiesto(args.meses, crudos, procesados, limpieza, resumen)

    print("Meses:", len(args.meses))
    print("Viajes válidos:", len(viajes))
    print("Estaciones con viajes:", resumen["estaciones_con_viajes"], "de", len(estaciones), "en la nomenclatura")
    print("Descartados:", {clave: valor for clave, valor in limpieza.items() if clave != "registros_crudos"})
    print("Versión de los datos:", manifiesto["version_datos"])
    print("Tiempo:", round(time.time() - inicio, 1), "s")


if __name__ == "__main__":
    main()
