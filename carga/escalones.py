"""Estadísticas por escalón de la prueba de carga, a partir de las peticiones que registra el locustfile."""
import csv
import math

AGREGADO = "Agregado"
COLUMNAS = ["escalon", "usuarios", "inicio_s", "fin_s", "ventana_s", "nombre", "peticiones", "fallos", "tasa_error", "rps",
            "predicciones_s", "media_ms", "p50_ms", "p95_ms", "p99_ms", "max_ms"]


def leer_escalones(texto, por_defecto):
    """Usuarios de cada escalón a partir de una lista separada por comas; vacío deja los valores por defecto."""
    valores = [int(parte) for parte in (texto or "").replace(" ", "").split(",") if parte]
    return valores or list(por_defecto)


def armar_lote(ejemplo, tamano):
    """Lote del tamaño pedido que repite en ciclo las estaciones de ejemplo, con un identificador distinto en cada fila."""
    primero = ejemplo[0]["estacion_id"]
    return [{**ejemplo[posicion % len(ejemplo)], "estacion_id": primero + posicion} for posicion in range(tamano)]


def percentil(ordenados, fraccion):
    """Percentil por rango más cercano de una lista ya ordenada; 0 si está vacía."""
    if not ordenados:
        return 0.0
    return ordenados[min(len(ordenados) - 1, max(0, math.ceil(fraccion * len(ordenados)) - 1))]


def fila(escalon, usuarios, inicio, fin, nombre, muestras):
    """Fila de un endpoint (o del agregado) en un escalón; cada muestra es (milisegundos, éxito, predicciones que entrega)."""
    ventana = fin - inicio
    tiempos = sorted(milisegundos for milisegundos, _, _ in muestras)
    fallos = sum(1 for _, exito, _ in muestras if not exito)
    predicciones = sum(cuantas for _, exito, cuantas in muestras if exito)
    return {
        "escalon": escalon, "usuarios": usuarios, "inicio_s": inicio, "fin_s": fin, "ventana_s": ventana, "nombre": nombre,
        "peticiones": len(tiempos), "fallos": fallos, "tasa_error": round(fallos / len(tiempos), 6) if tiempos else 0.0,
        "rps": round(len(tiempos) / ventana, 3) if ventana else 0.0,
        "predicciones_s": round(predicciones / ventana, 3) if ventana else 0.0,
        "media_ms": round(sum(tiempos) / len(tiempos), 2) if tiempos else 0.0,
        "p50_ms": round(percentil(tiempos, 0.50), 2), "p95_ms": round(percentil(tiempos, 0.95), 2),
        "p99_ms": round(percentil(tiempos, 0.99), 2), "max_ms": round(tiempos[-1], 2) if tiempos else 0.0,
    }


def resumir(muestras, usuarios, duracion, calentamiento, predicciones=None):
    """Una fila por escalón y endpoint, más la agregada, con las peticiones que empezaron después del calentamiento del escalón.

    Cada muestra es (segundo de inicio desde el arranque de la prueba, nombre, milisegundos, éxito). El calentamiento descarta
    los primeros segundos de cada escalón, cuando los usuarios nuevos todavía se están creando; predicciones dice cuántas
    predicciones entrega una petición correcta de cada endpoint.
    """
    predicciones = predicciones or {}
    por_escalon = [{} for _ in usuarios]
    for segundo, nombre, milisegundos, exito in muestras:
        escalon = int(segundo // duracion)
        if not 0 <= escalon < len(usuarios) or segundo - escalon * duracion < calentamiento:
            continue
        por_escalon[escalon].setdefault(nombre, []).append((milisegundos, exito, predicciones.get(nombre, 0)))
    filas = []
    for escalon, (cuantos, endpoints) in enumerate(zip(usuarios, por_escalon), start=1):
        inicio, fin = (escalon - 1) * duracion + calentamiento, escalon * duracion
        todas = [muestra for nombre in endpoints for muestra in endpoints[nombre]]
        filas.append(fila(escalon, cuantos, inicio, fin, AGREGADO, todas))
        filas.extend(fila(escalon, cuantos, inicio, fin, nombre, endpoints[nombre]) for nombre in sorted(endpoints))
    return filas


def escribir(ruta, filas):
    """Guarda las filas de resumir en un CSV con las columnas de COLUMNAS."""
    with open(ruta, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(filas)
