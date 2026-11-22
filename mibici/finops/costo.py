"""Costo por inferencia del servicio de predicción a partir de la prueba de carga, del uso de recursos y del precio de una instancia."""
import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

from mibici.monitoreo import formato

AGREGADO = "Agregado"
SEGUNDOS_POR_HORA = 3600
HORAS_POR_MES = 730
MARGEN_MEMORIA = 1.3


def leer_argumentos():
    parser = argparse.ArgumentParser(
        description="Estima el costo por inferencia con los CSV de la prueba de carga (escalones y recursos) y el precio por hora de una o varias instancias."
    )
    parser.add_argument("--carpeta", default="reports/carga", help="carpeta con los archivos <corrida>_escalones.csv y <corrida>_recursos.csv")
    parser.add_argument("--instancia", action="append", required=True,
                        help="instancia de referencia como nombre:vcpu:memoria_gib:precio_hora en dólares; se puede repetir")
    parser.add_argument("--p95_objetivo_ms", type=float, default=500, help="latencia p95 que el servicio debe cumplir")
    parser.add_argument("--objetivos_alternos", default="250,1000,2000", help="otros objetivos de p95, en ms y separados por comas, para la sensibilidad")
    parser.add_argument("--error_maximo", type=float, default=0.01, help="tasa de error admitida, como fracción")
    parser.add_argument("--demanda_hora", type=float, default=472, help="predicciones que la operación necesita por hora")
    parser.add_argument("--descuento", type=float, default=0.0, help="descuento por compromiso de uso, como fracción del precio bajo demanda")
    parser.add_argument("--salida", default="", help="carpeta donde se escriben costo.json y costo.md; por defecto la de --carpeta")
    return parser.parse_args()


def numero(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return valor


def leer_csv(ruta):
    """Filas de un CSV con los valores numéricos ya convertidos."""
    with open(ruta, newline="", encoding="utf-8") as archivo:
        return [{clave: numero(valor) for clave, valor in fila.items()} for fila in csv.DictReader(archivo)]


def leer_json(ruta):
    ruta = Path(ruta)
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else {}


def leer_instancia(texto):
    """Instancia de referencia a partir de nombre:vcpu:memoria_gib:precio_hora."""
    partes = texto.split(":")
    if len(partes) != 4:
        raise ValueError(f"la instancia debe escribirse como nombre:vcpu:memoria_gib:precio_hora y llegó {texto!r}")
    nombre, vcpu, memoria, precio = partes
    instancia = {"nombre": nombre, "vcpu": float(vcpu), "memoria_gib": float(memoria), "precio_hora": float(precio)}
    if min(instancia["vcpu"], instancia["memoria_gib"], instancia["precio_hora"]) <= 0:
        raise ValueError(f"vcpu, memoria y precio deben ser positivos en {texto!r}")
    return instancia


def capacidad_sostenida(filas, p95_objetivo_ms, error_maximo):
    """Escalón de mayor rendimiento que cumple el objetivo, sin contar los que siguen al primero que lo rompe; None si ninguno cumple.

    Al escalón se le agregan las peticiones de predicción por segundo: las de los endpoints que entregan predicciones, sin las de salud.
    """
    mejor = None
    for fila in sorted((fila for fila in filas if fila["nombre"] == AGREGADO), key=lambda fila: fila["escalon"]):
        if not fila["peticiones"] or fila["p95_ms"] > p95_objetivo_ms or fila["tasa_error"] > error_maximo:
            break
        if mejor is None or fila["rps"] > mejor["rps"]:
            mejor = fila
    if mejor is None:
        return None
    de_prediccion = [fila["rps"] for fila in filas
                     if fila["escalon"] == mejor["escalon"] and fila["nombre"] != AGREGADO and fila["predicciones_s"] > 0]
    return {**mejor, "peticiones_prediccion_s": round(sum(de_prediccion), 3) if de_prediccion else mejor["rps"]}


def uso_de_recursos(recursos, inicio, fin):
    """CPU media y máxima y memoria máxima de cada servicio entre dos instantes del reloj del anfitrión."""
    por_servicio = {}
    for fila in recursos:
        if inicio <= fila["epoch"] < fin:
            por_servicio.setdefault(fila["servicio"], []).append(fila)
    return {
        servicio: {
            "lecturas": len(filas),
            "cpu_media_pct": round(sum(fila["cpu_pct"] for fila in filas) / len(filas), 2),
            "cpu_max_pct": max(fila["cpu_pct"] for fila in filas),
            "mem_max_mib": max(fila["mem_mib"] for fila in filas),
            "mem_limite_mib": max(fila["mem_limite_mib"] for fila in filas),
        }
        for servicio, filas in sorted(por_servicio.items())
    }


def costo_por_inferencia(precio_hora, por_segundo):
    """Dólares por inferencia de una instancia que sostiene por_segundo inferencias: precio por hora entre inferencias por hora."""
    return precio_hora / (por_segundo * SEGUNDOS_POR_HORA) if por_segundo else None


def segundos_activos(demanda_hora, predicciones_s, arranque_s):
    """Segundos de cada hora que la instancia necesita encendida si solo arranca, atiende la demanda de la hora y se apaga."""
    return arranque_s + demanda_hora / predicciones_s if predicciones_s else None


def analizar_corrida(carpeta, nombre, p95_objetivo_ms, error_maximo, objetivos_alternos=()):
    """Capacidad dentro del objetivo, sensibilidad a otros objetivos de latencia y recursos de una corrida de la prueba de carga."""
    carpeta = Path(carpeta)
    escalones = leer_csv(carpeta / f"{nombre}_escalones.csv")
    escenario = leer_json(carpeta / f"{nombre}_escenario.json")
    sistema = leer_json(carpeta / f"{nombre}_sistema.json")
    capacidad = capacidad_sostenida(escalones, p95_objetivo_ms, error_maximo)
    recursos = {}
    archivo_recursos = carpeta / f"{nombre}_recursos.csv"
    if capacidad is not None and archivo_recursos.is_file() and "inicio_epoch" in escenario:
        origen = escenario["inicio_epoch"] - sistema.get("desfase_reloj_s", 0.0)
        recursos = uso_de_recursos(leer_csv(archivo_recursos), origen + capacidad["inicio_s"], origen + capacidad["fin_s"])
    sensibilidad = []
    for objetivo in sorted({p95_objetivo_ms, *objetivos_alternos}):
        alcanzada = capacidad_sostenida(escalones, objetivo, error_maximo)
        sensibilidad.append({"p95_objetivo_ms": objetivo, "usuarios": alcanzada and alcanzada["usuarios"], "rps": alcanzada and alcanzada["rps"],
                             "peticiones_prediccion_s": alcanzada and alcanzada["peticiones_prediccion_s"],
                             "predicciones_s": alcanzada and alcanzada["predicciones_s"]})
    return {
        "corrida": nombre, "procesos": sistema.get("procesos"), "cpus": sistema.get("cpus"), "hilos": sistema.get("hilos", 0),
        "memoria": sistema.get("memoria"), "arranque_s": sistema.get("arranque_s"), "tamano_lote": escenario.get("tamano_lote"),
        "etiquetas": escenario.get("etiquetas", []), "capacidad": capacidad, "sensibilidad": sensibilidad, "recursos": recursos,
    }


def orden(corrida):
    """Las corridas del escenario mixto primero, de menos a más recursos; las que filtran tareas al final."""
    return (bool(corrida["etiquetas"]), corrida["cpus"] or 0, corrida["procesos"] or 0, corrida["hilos"] or 0, corrida["corrida"])


def costos_de_la_corrida(corrida, instancia, demanda_hora, descuento):
    """Costo a plena capacidad y con la demanda real de una corrida sobre una instancia de referencia."""
    capacidad = corrida["capacidad"]
    precio = instancia["precio_hora"]
    cpu = sum(servicio["cpu_max_pct"] for servicio in corrida["recursos"].values()) / 100
    memoria = sum(servicio["mem_max_mib"] for servicio in corrida["recursos"].values()) / 1024
    fila = {
        "corrida": corrida["corrida"], "instancia": instancia["nombre"], "precio_hora": precio,
        "cpu_pico_nucleos": round(cpu, 3), "memoria_pico_gib": round(memoria, 3),
        "ocupacion_cpu": round(cpu / instancia["vcpu"], 4), "ocupacion_memoria": round(memoria / instancia["memoria_gib"], 4),
        "cabe": bool(corrida["recursos"]) and cpu <= instancia["vcpu"] and memoria * MARGEN_MEMORIA <= instancia["memoria_gib"],
    }
    if capacidad is None:
        return {**fila, "cumple_objetivo": False}
    activos = segundos_activos(demanda_hora, capacidad["predicciones_s"], corrida["arranque_s"] or 0.0)
    por_hora_apagando = precio * activos / SEGUNDOS_POR_HORA if activos is not None else None
    return {
        **fila, "cumple_objetivo": True,
        "peticiones_hora": capacidad["peticiones_prediccion_s"] * SEGUNDOS_POR_HORA,
        "predicciones_hora": capacidad["predicciones_s"] * SEGUNDOS_POR_HORA,
        "costo_por_peticion": costo_por_inferencia(precio, capacidad["peticiones_prediccion_s"]),
        "costo_por_prediccion": costo_por_inferencia(precio, capacidad["predicciones_s"]),
        "costo_por_prediccion_segun_objetivo": {
            f"{punto['p95_objetivo_ms']:g}": costo_por_inferencia(precio, punto["predicciones_s"]) if punto["predicciones_s"] else None
            for punto in corrida["sensibilidad"]},
        "utilizacion_real": demanda_hora / (capacidad["predicciones_s"] * SEGUNDOS_POR_HORA) if capacidad["predicciones_s"] else None,
        "siempre_encendido": {"costo_hora": precio, "costo_mes": precio * HORAS_POR_MES, "costo_por_prediccion": precio / demanda_hora},
        "con_compromiso": {"costo_hora": precio * (1 - descuento), "costo_mes": precio * (1 - descuento) * HORAS_POR_MES,
                           "costo_por_prediccion": precio * (1 - descuento) / demanda_hora},
        "encendido_por_hora": None if por_hora_apagando is None else {
            "segundos_activos": round(activos, 2), "costo_hora": por_hora_apagando, "costo_mes": por_hora_apagando * HORAS_POR_MES,
            "costo_por_prediccion": por_hora_apagando / demanda_hora, "ahorro": 1 - activos / SEGUNDOS_POR_HORA},
    }


def analizar(carpeta, instancias, p95_objetivo_ms=500, error_maximo=0.01, demanda_hora=472, descuento=0.0, objetivos_alternos=()):
    """Reúne todas las corridas de la carpeta con su capacidad, sus recursos y su costo sobre cada instancia."""
    nombres = [archivo.name.removesuffix("_escalones.csv") for archivo in Path(carpeta).glob("*_escalones.csv")]
    if not nombres:
        raise FileNotFoundError(f"no hay archivos *_escalones.csv en {carpeta}; corre antes la prueba de carga")
    corridas = sorted((analizar_corrida(carpeta, nombre, p95_objetivo_ms, error_maximo, objetivos_alternos) for nombre in nombres), key=orden)
    costos = [costos_de_la_corrida(corrida, instancia, demanda_hora, descuento) for instancia in instancias for corrida in corridas]
    return {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "supuestos": {"p95_objetivo_ms": p95_objetivo_ms, "objetivos_alternos_ms": sorted(objetivos_alternos), "error_maximo": error_maximo,
                      "demanda_hora": demanda_hora, "descuento_por_compromiso": descuento, "horas_por_mes": HORAS_POR_MES,
                      "margen_memoria": MARGEN_MEMORIA},
        "instancias": instancias, "corridas": corridas, "costos": costos,
    }


def dolares(valor, por=1, decimales=4):
    """Dólares con decimales fijos; por multiplica antes de dar formato (un millón de inferencias, por ejemplo)."""
    return "sin dato" if valor is None else f"{valor * por:,.{decimales}f}"


def tabla_capacidad(resultado):
    filas = []
    for corrida in resultado["corridas"]:
        capacidad, api = corrida["capacidad"], corrida["recursos"].get("api", {})
        configuracion = [f"`{corrida['corrida']}`", corrida["procesos"], formato.decimal(corrida["cpus"], 0), corrida["hilos"] or "40"]
        if capacidad is None:
            filas.append(configuracion + ["ningún escalón cumple el objetivo"] + [""] * 8)
            continue
        cpu = f"{api['cpu_media_pct']:.0f} % y {api['cpu_max_pct']:.0f} %" if api else "sin lecturas"
        filas.append(configuracion + [f"{capacidad['usuarios']:g}", f"{capacidad['rps']:.1f}", f"{capacidad['peticiones_prediccion_s']:.1f}",
                                      f"{capacidad['predicciones_s']:.1f}", f"{capacidad['p50_ms']:.0f}", f"{capacidad['p95_ms']:.0f}",
                                      formato.porcentaje(capacidad["tasa_error"]), cpu, f"{api['mem_max_mib']:.0f}" if api else "sin lecturas"])
    return formato.tabla_markdown(
        ["Corrida", "Procesos", "CPU", "Peticiones a la vez por proceso", "Usuarios", "Peticiones/s", "Peticiones de predicción/s",
         "Predicciones/s", "p50 (ms)", "p95 (ms)", "Errores", "CPU del servicio, media y máxima", "Memoria máxima del servicio (MiB)"], filas)


def tabla_sensibilidad(resultado):
    supuestos = resultado["supuestos"]
    objetivos = sorted({supuestos["p95_objetivo_ms"], *supuestos["objetivos_alternos_ms"]})
    filas = [[f"`{corrida['corrida']}`"] + [formato.decimal(punto["predicciones_s"], 1) if punto["predicciones_s"] else "no cumple"
                                            for punto in corrida["sensibilidad"]]
             for corrida in resultado["corridas"]]
    return formato.tabla_markdown(["Corrida"] + [f"p95 de hasta {objetivo:g} ms" for objetivo in objetivos], filas)


def tabla_plena_capacidad(resultado):
    filas = [[costo["instancia"], f"{costo['precio_hora']:g}", f"`{costo['corrida']}`", formato.numero(costo["peticiones_hora"]),
              dolares(costo["costo_por_peticion"], 1e6), formato.numero(costo["predicciones_hora"]), dolares(costo["costo_por_prediccion"], 1e6),
              f"{costo['cpu_pico_nucleos']:.2f}", f"{costo['memoria_pico_gib']:.2f}", "sí" if costo["cabe"] else "no"]
             for costo in resultado["costos"] if costo["cumple_objetivo"]]
    return formato.tabla_markdown(["Instancia", "USD por hora", "Corrida", "Peticiones de predicción por hora", "USD por millón de peticiones",
                                   "Predicciones por hora", "USD por millón de predicciones", "Suma de los picos de CPU (núcleos)",
                                   "Suma de los picos de memoria (GiB)", "Cabe en la instancia"], filas)


def tabla_siempre_encendido(resultado):
    supuestos = resultado["supuestos"]
    filas = []
    for instancia in resultado["instancias"]:
        precio, descuento = instancia["precio_hora"], supuestos["descuento_por_compromiso"]
        filas.append([instancia["nombre"], "Bajo demanda", dolares(precio), dolares(precio * supuestos["horas_por_mes"], decimales=2),
                      dolares(precio / supuestos["demanda_hora"], 1e6, 2)])
        if descuento:
            filas.append([instancia["nombre"], f"Con compromiso ({formato.porcentaje(descuento, 0)} menos)", dolares(precio * (1 - descuento)),
                          dolares(precio * (1 - descuento) * supuestos["horas_por_mes"], decimales=2),
                          dolares(precio * (1 - descuento) / supuestos["demanda_hora"], 1e6, 2)])
    return formato.tabla_markdown(["Instancia", "Precio", "USD por hora", "USD al mes", "USD por millón de predicciones"], filas)


def tabla_encendido_por_hora(resultado):
    filas = [[costo["instancia"], f"`{costo['corrida']}`", formato.porcentaje(costo["utilizacion_real"], 3),
              f"{costo['encendido_por_hora']['segundos_activos']:.1f}", dolares(costo["encendido_por_hora"]["costo_mes"], decimales=2),
              dolares(costo["encendido_por_hora"]["costo_por_prediccion"], 1e6, 2), formato.porcentaje(costo["encendido_por_hora"]["ahorro"], 1)]
             for costo in resultado["costos"] if costo["cumple_objetivo"] and costo["encendido_por_hora"] is not None]
    return formato.tabla_markdown(["Instancia", "Corrida", "Utilización si quedara siempre encendida", "Segundos encendida por hora", "USD al mes",
                                   "USD por millón de predicciones", "Ahorro frente a siempre encendida"], filas)


def reporte(resultado):
    """Tablas en Markdown de la capacidad, la sensibilidad al objetivo, el costo a plena capacidad y el costo con la demanda real."""
    supuestos = resultado["supuestos"]
    return "\n".join([
        "# Costo por inferencia del servicio de predicción",
        "",
        f"Generado el {resultado['generado'].replace('T', ' ')} con `python -m mibici.finops.costo` a partir de los CSV de `reports/carga/`. "
        f"Objetivo de servicio: p95 de hasta {supuestos['p95_objetivo_ms']:g} ms y errores de hasta "
        f"{formato.porcentaje(supuestos['error_maximo'], 1)}. Demanda de la operación: {supuestos['demanda_hora']:g} predicciones por hora. "
        "Los precios son por hora de instancia, en dólares, y llegan como parámetro.",
        "",
        "## Capacidad dentro del objetivo",
        "",
        "Escalón de mayor rendimiento de cada corrida antes del primero que rompe el objetivo, con la CPU y la memoria del servicio en ese escalón.",
        "",
        tabla_capacidad(resultado),
        "",
        "Predicciones por segundo que cada corrida sostiene según el objetivo de p95:",
        "",
        tabla_sensibilidad(resultado),
        "",
        "## Costo a plena capacidad",
        "",
        "Costo por inferencia = precio por hora de la instancia / (inferencias por segundo sostenidas dentro del objetivo x 3,600). "
        "Una petición de predicción es una llamada a `/predecir` o a `/predecir/lote`; una predicción es una estación en una hora. "
        f"El sistema cabe en la instancia si la suma de los picos de CPU de sus contenedores no pasa de sus vCPU y la de memoria, con un margen de "
        f"{formato.porcentaje(supuestos['margen_memoria'] - 1, 0)}, no pasa de su memoria.",
        "",
        tabla_plena_capacidad(resultado),
        "",
        f"## Costo con la demanda real ({supuestos['demanda_hora']:g} predicciones por hora)",
        "",
        f"Siempre encendida, la instancia cuesta su precio por hora sin importar cuánto se use: costo por predicción = precio por hora / demanda "
        f"por hora. El mes tiene {supuestos['horas_por_mes']} horas.",
        "",
        tabla_siempre_encendido(resultado),
        "",
        "Encendida solo para atender la demanda de cada hora, la instancia arranca, predice y se apaga: paga (arranque del servicio + demanda / "
        "predicciones por segundo) segundos de cada hora.",
        "",
        tabla_encendido_por_hora(resultado),
    ]) + "\n"


def main():
    args = leer_argumentos()
    try:
        instancias = [leer_instancia(texto) for texto in args.instancia]
        alternos = [float(valor) for valor in args.objetivos_alternos.split(",") if valor.strip()]
        resultado = analizar(args.carpeta, instancias, args.p95_objetivo_ms, args.error_maximo, args.demanda_hora, args.descuento, alternos)
    except (ValueError, FileNotFoundError) as error:
        print(error)
        return 1
    salida = Path(args.salida or args.carpeta)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "costo.json").write_text(json.dumps(resultado, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    texto = reporte(resultado)
    (salida / "costo.md").write_text(texto, encoding="utf-8")
    print(texto, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
