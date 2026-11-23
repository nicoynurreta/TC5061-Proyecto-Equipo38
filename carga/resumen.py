"""Resume la prueba de carga: tabla por escalón con recursos, punto de degradación, variación entre repeticiones y gráficas."""
import argparse
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from carga import escalones
from mibici.monitoreo import formato

RAIZ = Path(__file__).resolve().parents[1]
REPETICION = re.compile(r"_r\d+$")
SERVICIOS = ["api", "mlflow", "locust"]
COLORES = {"p50_ms": "steelblue", "p95_ms": "darkorange", "p99_ms": "crimson", "api": "steelblue", "mlflow": "seagreen",
           "locust": "gray"}
ETIQUETAS = {"p50_ms": "p50", "p95_ms": "p95", "p99_ms": "p99"}
MARCADORES = ["x", "+", "1", "2"]
COLUMNAS_RECURSOS = ["escalon", "servicio", "lecturas", "cpu_media_pct", "cpu_max_pct", "mem_max_mib"]
RESOLUCION = 150


def leer_argumentos():
    parser = argparse.ArgumentParser(description="Resume los archivos de reports/carga en resumen.md, carga.json y tres gráficas.")
    parser.add_argument("--carpeta", default=str(RAIZ / "reports" / "carga"), help="carpeta con los archivos de las corridas")
    parser.add_argument("--figuras", default=str(RAIZ / "reports" / "figures"), help="carpeta donde se guardan las gráficas")
    parser.add_argument("--p95_objetivo_ms", type=float, default=500, help="latencia p95 que el servicio debe cumplir")
    parser.add_argument("--error_maximo", type=float, default=0.01, help="tasa de error admitida, como fracción")
    parser.add_argument("--cumplimiento", type=float, default=0.9, help="fracción mínima de la carga ofrecida que el servicio debe atender")
    return parser.parse_args()


def leer_json(ruta):
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else {}


def leer_corrida(carpeta, nombre):
    """Escalones, lecturas de recursos, escenario y sistema de una corrida."""
    carpeta = Path(carpeta)
    recursos = carpeta / f"{nombre}_recursos.csv"
    return {
        "nombre": nombre,
        "escalones": pd.read_csv(carpeta / f"{nombre}_escalones.csv"),
        "recursos": pd.read_csv(recursos) if recursos.is_file() else pd.DataFrame(columns=["epoch", "servicio", "cpu_pct", "mem_mib"]),
        "escenario": leer_json(carpeta / f"{nombre}_escenario.json"),
        "sistema": leer_json(carpeta / f"{nombre}_sistema.json"),
    }


def agregadas(corrida):
    tabla = corrida["escalones"]
    return tabla[tabla["nombre"] == escalones.AGREGADO].sort_values("escalon").reset_index(drop=True)


def nombre_base(nombre):
    """Nombre de la corrida sin el sufijo de repetición: un_proceso_r2 es una repetición de un_proceso."""
    return REPETICION.sub("", nombre)


def configuracion(corrida):
    """Procesos, CPU y, si se limitaron, peticiones simultáneas por proceso de una corrida, en una frase."""
    sistema = corrida["sistema"]
    procesos, hilos, cpus = sistema.get("procesos", "?"), sistema.get("hilos"), sistema.get("cpus")
    texto = f"{procesos} proceso{'s' if procesos != 1 else ''}, {'?' if cpus is None else format(cpus, 'g')} CPU"
    if hilos:
        texto += f", {hilos} {'petición' if hilos == 1 else 'peticiones'} a la vez por proceso"
    return texto


def orden(corrida):
    """Las corridas del escenario mixto primero, de menos a más recursos y cada una seguida de sus repeticiones; las que filtran tareas al final."""
    sistema = corrida["sistema"]
    return (bool(corrida["escenario"].get("etiquetas")), sistema.get("cpus", 0), sistema.get("procesos", 0), sistema.get("hilos", 0),
            nombre_base(corrida["nombre"]), corrida["nombre"])


def origen_de_tiempos(corrida):
    """Instante, en el reloj del anfitrión, en que empezó la prueba; None si la corrida no lo registró."""
    if "inicio_epoch" not in corrida["escenario"]:
        return None
    return corrida["escenario"]["inicio_epoch"] - corrida["sistema"].get("desfase_reloj_s", 0.0)


def recursos_por_escalon(corrida):
    """CPU media y máxima y memoria máxima de cada servicio en la ventana medida de cada escalón."""
    origen, recursos, filas = origen_de_tiempos(corrida), corrida["recursos"], []
    if origen is None or recursos.empty:
        return pd.DataFrame(columns=COLUMNAS_RECURSOS)
    for escalon in agregadas(corrida).itertuples():
        ventana = recursos[(recursos["epoch"] >= origen + escalon.inicio_s) & (recursos["epoch"] < origen + escalon.fin_s)]
        for servicio, lecturas in ventana.groupby("servicio"):
            filas.append({"escalon": int(escalon.escalon), "servicio": servicio, "lecturas": len(lecturas),
                          "cpu_media_pct": round(float(lecturas["cpu_pct"].mean()), 2), "cpu_max_pct": float(lecturas["cpu_pct"].max()),
                          "mem_max_mib": float(lecturas["mem_mib"].max())})
    return pd.DataFrame(filas, columns=COLUMNAS_RECURSOS)


def punto_de_degradacion(tabla, p95_objetivo_ms, error_maximo, cumplimiento):
    """Primer escalón que rompe el objetivo de latencia o el de errores, o que atiende menos carga de la que se le ofrece."""
    for escalon in tabla.itertuples():
        motivos = []
        if escalon.p95_ms > p95_objetivo_ms:
            motivos.append(f"p95 de {escalon.p95_ms:.0f} ms")
        if escalon.tasa_error > error_maximo:
            motivos.append(f"errores de {formato.porcentaje(escalon.tasa_error, 1)}")
        if escalon.rps < cumplimiento * escalon.usuarios:
            motivos.append(f"{escalon.rps:.1f} peticiones por segundo de {escalon.usuarios} ofrecidas")
        if motivos:
            return {"escalon": int(escalon.escalon), "usuarios": int(escalon.usuarios), "motivos": motivos}
    return None


def capacidad(tabla, degradacion):
    """Escalón de mayor rendimiento entre los anteriores a la degradación; None si el primero ya la rompe."""
    sanos = tabla if degradacion is None else tabla[tabla["escalon"] < degradacion["escalon"]]
    if sanos.empty:
        return None
    mejor = sanos.loc[sanos["rps"].idxmax()]
    return {clave: float(mejor[clave]) for clave in ["escalon", "usuarios", "rps", "predicciones_s", "p50_ms", "p95_ms", "p99_ms", "tasa_error"]}


def variacion(corrida, repeticiones):
    """Rendimiento y p95 de una corrida y de sus repeticiones, escalón por escalón, con la razón entre el p95 mayor y el menor."""
    juntas = agregadas(corrida)[["escalon", "usuarios"]].copy()
    for pasada in [corrida, *repeticiones]:
        datos = agregadas(pasada)[["escalon", "rps", "p95_ms"]].rename(
            columns={"rps": f"rps_{pasada['nombre']}", "p95_ms": f"p95_{pasada['nombre']}"})
        juntas = juntas.merge(datos, on="escalon", how="left")
    p95 = juntas[[columna for columna in juntas.columns if columna.startswith("p95_")]]
    juntas["p95_razon"] = p95.max(axis=1) / p95.min(axis=1).where(p95.min(axis=1) > 0)
    return juntas


def analizar(carpeta, p95_objetivo_ms=500, error_maximo=0.01, cumplimiento=0.9):
    """Lee todas las corridas de la carpeta y calcula su degradación, su capacidad, sus recursos y la variación con sus repeticiones."""
    nombres = sorted(archivo.name.removesuffix("_escalones.csv") for archivo in Path(carpeta).glob("*_escalones.csv"))
    if not nombres:
        raise FileNotFoundError(f"no hay archivos *_escalones.csv en {carpeta}; corre antes python -m carga.correr")
    leidas = sorted((leer_corrida(carpeta, nombre) for nombre in nombres), key=orden)
    corridas = {corrida["nombre"]: corrida for corrida in leidas}
    for nombre, corrida in corridas.items():
        corrida["degradacion"] = punto_de_degradacion(agregadas(corrida), p95_objetivo_ms, error_maximo, cumplimiento)
        corrida["capacidad"] = capacidad(agregadas(corrida), corrida["degradacion"])
        corrida["recursos_escalon"] = recursos_por_escalon(corrida)
        corrida["repeticiones"] = [otra for otra in corridas if otra != nombre and nombre_base(otra) == nombre]
    for corrida in corridas.values():
        repeticiones = [corridas[otra] for otra in corrida["repeticiones"]]
        corrida["variacion"] = variacion(corrida, repeticiones) if repeticiones else None
    return corridas


def por_configuracion(corridas):
    """Una fila por configuración con las medidas de su corrida y de sus repeticiones juntas."""
    filas = []
    for nombre, corrida in corridas.items():
        if nombre_base(nombre) != nombre:
            continue
        pasadas = [corrida, *(corridas[otra] for otra in corrida["repeticiones"])]
        topes = [pasada["capacidad"] for pasada in pasadas if pasada["capacidad"] is not None]
        filas.append({
            "corrida": nombre, "configuracion": configuracion(corrida), "tamano_lote": corrida["escenario"].get("tamano_lote"),
            "corridas": len(pasadas),
            "degradacion_usuarios": [None if pasada["degradacion"] is None else pasada["degradacion"]["usuarios"] for pasada in pasadas],
            "capacidad_rps": [tope["rps"] for tope in topes],
            "capacidad_mediana_rps": float(pd.Series([tope["rps"] for tope in topes]).median()) if topes else None,
            "predicciones_s": [tope["predicciones_s"] for tope in topes],
            "p95_ms": [tope["p95_ms"] for tope in topes],
            "rendimiento_maximo_rps": [float(agregadas(pasada)["rps"].max()) for pasada in pasadas],
            "error_ultimo_escalon": [float(agregadas(pasada)["tasa_error"].iloc[-1]) for pasada in pasadas],
            "arranque_s": [pasada["sistema"]["arranque_s"] for pasada in pasadas if "arranque_s" in pasada["sistema"]],
        })
    return filas


def intervalo(valores, decimales=1):
    """El valor si todos coinciden y el menor y el mayor si no; n. a. si no hay ninguno."""
    textos = [f"{valor:.{decimales}f}" for valor in sorted(valores)]
    if not textos:
        return "n. a."
    return textos[0] if textos[0] == textos[-1] else f"{textos[0]} a {textos[-1]}"


def tabla_configuraciones(corridas):
    """Tabla en Markdown con una fila por configuración: el menor y el mayor valor de cada medida entre sus corridas."""
    filas = []
    for fila in por_configuracion(corridas):
        puntos = [usuarios for usuarios in fila["degradacion_usuarios"] if usuarios is not None]
        degradacion = f"{intervalo(puntos, 0)} usuarios" if puntos else "ninguno"
        if puntos and len(puntos) < fila["corridas"]:
            degradacion += f"; ninguno en {fila['corridas'] - len(puntos)}"
        filas.append([f"`{fila['corrida']}`", fila["configuracion"], "?" if fila["tamano_lote"] is None else fila["tamano_lote"],
                      fila["corridas"], degradacion, intervalo(fila["capacidad_rps"]), formato.decimal(fila["capacidad_mediana_rps"], 1),
                      intervalo(fila["predicciones_s"]), intervalo(fila["p95_ms"], 0), intervalo(fila["rendimiento_maximo_rps"]),
                      intervalo([error * 100 for error in fila["error_ultimo_escalon"]]) + " %", intervalo(fila["arranque_s"])])
    return formato.tabla_markdown(["Corrida", "Configuración", "Estaciones por lote", "Corridas", "Punto de degradación",
                                   "Capacidad dentro del objetivo (peticiones/s)", "Mediana de la capacidad", "Predicciones/s en ese escalón",
                                   "p95 en ese escalón (ms)", "Rendimiento máximo (peticiones/s)", "Errores en el último escalón",
                                   "Arranque del servicio (s)"], filas)


def tabla_escalones(corrida, objetivo):
    """Tabla en Markdown de una corrida: carga, latencia, errores y recursos del servicio por escalón."""
    recursos = corrida["recursos_escalon"]
    filas = []
    for escalon in agregadas(corrida).itertuples():
        api = recursos[(recursos["escalon"] == escalon.escalon) & (recursos["servicio"] == "api")]
        cpu = f"{api['cpu_media_pct'].iloc[0]:.0f} % y {api['cpu_max_pct'].iloc[0]:.0f} %" if len(api) else "sin lecturas"
        memoria = f"{api['mem_max_mib'].iloc[0]:.0f}" if len(api) else "sin lecturas"
        marca = " (sobre el objetivo)" if escalon.p95_ms > objetivo else ""
        filas.append([int(escalon.escalon), int(escalon.usuarios), formato.numero(escalon.peticiones), f"{escalon.rps:.1f}",
                      f"{escalon.predicciones_s:.1f}", f"{escalon.p50_ms:.0f}", f"{escalon.p95_ms:.0f}{marca}", f"{escalon.p99_ms:.0f}",
                      f"{escalon.max_ms:.0f}", formato.porcentaje(escalon.tasa_error), cpu, memoria])
    return formato.tabla_markdown(["Escalón", "Usuarios", "Peticiones medidas", "Peticiones/s", "Predicciones/s", "p50 (ms)", "p95 (ms)",
                                   "p99 (ms)", "Máximo (ms)", "Errores", "CPU del servicio, media y máxima",
                                   "Memoria máxima del servicio (MiB)"], filas)


def tabla_endpoints(corrida):
    """Tabla en Markdown con el rendimiento, la mediana y el p95 de cada endpoint por escalón."""
    tabla = corrida["escalones"]
    nombres = sorted(nombre for nombre in tabla["nombre"].unique() if nombre != escalones.AGREGADO)
    filas = []
    for escalon, grupo in tabla[tabla["nombre"] != escalones.AGREGADO].groupby("escalon"):
        fila = [int(escalon), int(grupo["usuarios"].iloc[0])]
        for nombre in nombres:
            dato = grupo[grupo["nombre"] == nombre]
            fila += ([f"{dato['rps'].iloc[0]:.1f}", f"{dato['p50_ms'].iloc[0]:.0f}", f"{dato['p95_ms'].iloc[0]:.0f}"] if len(dato)
                     else ["0.0", "sin peticiones", "sin peticiones"])
        filas.append(fila)
    encabezados = ["Escalón", "Usuarios"] + [texto for nombre in nombres
                                             for texto in (f"`{nombre}` por segundo", f"`{nombre}` p50 (ms)", f"`{nombre}` p95 (ms)")]
    return formato.tabla_markdown(encabezados, filas)


def tabla_recursos(corrida):
    """Tabla en Markdown con la CPU y la memoria de cada contenedor por escalón."""
    recursos = corrida["recursos_escalon"]
    filas = []
    for escalon in agregadas(corrida).itertuples():
        fila = [int(escalon.escalon), int(escalon.usuarios)]
        for servicio in SERVICIOS:
            dato = recursos[(recursos["escalon"] == escalon.escalon) & (recursos["servicio"] == servicio)]
            fila += ([f"{dato['cpu_media_pct'].iloc[0]:.1f} %", f"{dato['cpu_max_pct'].iloc[0]:.1f} %", f"{dato['mem_max_mib'].iloc[0]:.0f}"]
                     if len(dato) else ["sin lecturas"] * 3)
        filas.append(fila)
    encabezados = ["Escalón", "Usuarios"] + [f"{servicio}, {dato}" for servicio in SERVICIOS
                                             for dato in ("CPU media", "CPU máxima", "memoria máxima (MiB)")]
    return formato.tabla_markdown(encabezados, filas)


def tabla_variacion(corrida):
    """Tabla en Markdown con el rendimiento y el p95 de la corrida y de cada repetición por escalón."""
    pasadas = [corrida["nombre"], *corrida["repeticiones"]]
    filas = [[int(fila["escalon"]), int(fila["usuarios"])] + [formato.decimal(fila[f"rps_{pasada}"], 1) for pasada in pasadas]
             + [formato.decimal(fila[f"p95_{pasada}"], 0) for pasada in pasadas] + [formato.decimal(fila["p95_razon"], 1)]
             for _, fila in corrida["variacion"].iterrows()]
    encabezados = (["Escalón", "Usuarios"] + [f"Peticiones/s, `{pasada}`" for pasada in pasadas]
                   + [f"p95 (ms), `{pasada}`" for pasada in pasadas] + ["p95 mayor entre p95 menor"])
    return formato.tabla_markdown(encabezados, filas)


def tabla_hilos(diagnostico):
    """Tabla en Markdown del diagnóstico de concurrencia de carga/hilos.py."""
    filas = [[fila["hilos"], f"{fila['predicciones_s']:.1f}", formato.decimal(fila.get("cpu_ms_por_prediccion"), 1),
              "n. a." if "cpu_sistema_pct" not in fila else f"{fila['cpu_sistema_pct']:.0f} %", fila.get("periodos_frenados", "n. a.")]
             for fila in diagnostico["filas"]]
    return formato.tabla_markdown(["Hilos que predicen a la vez", "Predicciones/s", "CPU por predicción (ms)",
                                   "CPU en llamadas al sistema", "Periodos frenados por el límite de CPU"], filas)


def texto_degradacion(corrida):
    degradacion, tope = corrida["degradacion"], corrida["capacidad"]
    if degradacion is None:
        return f"Ningún escalón rompe el objetivo; el de mayor rendimiento atiende {tope['rps']:.1f} peticiones por segundo."
    frase = f"Punto de degradación: escalón {degradacion['escalon']}, {degradacion['usuarios']} usuarios ({'; '.join(degradacion['motivos'])})."
    if tope is None:
        return frase + " Ningún escalón anterior cumple el objetivo."
    return (frase + f" Capacidad dentro del objetivo: {tope['rps']:.1f} peticiones por segundo con {tope['usuarios']:.0f} usuarios "
            f"(p95 de {tope['p95_ms']:.0f} ms).")


def tabla_resumen(corridas):
    """Tabla en Markdown con una fila por corrida: configuración, degradación, capacidad y rendimiento máximo."""
    filas = []
    for nombre, corrida in corridas.items():
        degradacion, tope, tabla = corrida["degradacion"], corrida["capacidad"], agregadas(corrida)
        filas.append([f"`{nombre}`", configuracion(corrida), corrida["escenario"].get("tamano_lote", "?"),
                      "ninguno" if degradacion is None else f"{degradacion['usuarios']} usuarios",
                      "ninguna" if tope is None else f"{tope['rps']:.1f}", "n. a." if tope is None else f"{tope['predicciones_s']:.1f}",
                      "n. a." if tope is None else f"{tope['p95_ms']:.0f}", f"{tabla['rps'].max():.1f}",
                      formato.porcentaje(float(tabla["tasa_error"].iloc[-1]), 1), corrida["sistema"].get("arranque_s", "?")])
    return formato.tabla_markdown(["Corrida", "Configuración", "Estaciones por lote", "Punto de degradación",
                                   "Capacidad dentro del objetivo (peticiones/s)", "Predicciones/s en ese escalón", "p95 en ese escalón (ms)",
                                   "Rendimiento máximo (peticiones/s)", "Errores en el último escalón", "Arranque del servicio (s)"], filas)


def reporte(corridas, argumentos, diagnostico=None):
    """Resumen en Markdown de todas las corridas y, si existe, del diagnóstico de concurrencia."""
    lineas = [
        "# Prueba de carga del servicio de predicción",
        "",
        f"Generado el {datetime.now():%Y-%m-%d %H:%M} con `python -m carga.resumen` a partir de los archivos de `reports/carga/`. "
        f"Objetivo de servicio: p95 de hasta {argumentos.p95_objetivo_ms:g} ms, errores de hasta {formato.porcentaje(argumentos.error_maximo, 1)} "
        f"y al menos {formato.porcentaje(argumentos.cumplimiento, 0)} de la carga ofrecida atendida. Cada usuario simulado intenta una tarea por "
        "segundo, así que los usuarios de un escalón son también las peticiones por segundo que se le ofrecen al servicio. Las corridas cuyo "
        "nombre termina en `_r` y un número son repeticiones de la corrida del mismo nombre.",
        "",
        "## Resumen por configuración",
        "",
        "Cada fila junta una corrida con sus repeticiones y da el menor y el mayor valor de cada medida entre ellas.",
        "",
        tabla_configuraciones(corridas),
        "",
        "## Resumen por corrida",
        "",
        tabla_resumen(corridas),
    ]
    if diagnostico:
        lineas += [
            "",
            "## Diagnóstico de concurrencia",
            "",
            f"`python -m carga.correr --diagnostico` dentro de un contenedor del servicio con {diagnostico.get('cpus', 1):g} CPU: el modelo "
            f"`{diagnostico['modelo']}` versión {diagnostico['version']} predice la petición de ejemplo sin pasar por HTTP, "
            f"{diagnostico['segundos']:g} s por medición.",
            "",
            tabla_hilos(diagnostico),
        ]
    for nombre, corrida in corridas.items():
        sistema, escenario = corrida["sistema"], corrida["escenario"]
        modelo = sistema.get("modelo") or {}
        lineas += [
            "",
            f"## Corrida `{nombre}`",
            "",
            f"{configuracion(corrida)} y {sistema.get('memoria', '?')} de memoria; modelo `{modelo.get('nombre', '?')}` versión "
            f"{modelo.get('version', '?')} (alias `{modelo.get('alias', '?')}`); arranque del servicio en {sistema.get('arranque_s', '?')} s; "
            f"escalones de {escenario.get('duracion_s', '?')} s con {escenario.get('calentamiento_s', '?')} s de calentamiento descartados; "
            f"lotes de {escenario.get('tamano_lote', '?')} estaciones; fecha {str(sistema.get('fecha', '?')).replace('T', ' ')}.",
            "",
            texto_degradacion(corrida),
            "",
            tabla_escalones(corrida, argumentos.p95_objetivo_ms),
            "",
            tabla_endpoints(corrida),
            "",
            tabla_recursos(corrida),
        ]
        if corrida["variacion"] is not None:
            lineas += ["", "Variación frente a sus repeticiones:", "", tabla_variacion(corrida)]
    return "\n".join(lineas) + "\n"


def principales(corridas):
    """Corridas del escenario mixto que van a las gráficas: las que no son repetición ni usan un filtro de tareas."""
    return [corrida for nombre, corrida in corridas.items() if nombre_base(nombre) == nombre and not corrida["escenario"].get("etiquetas")]


def rejilla(paneles, alto, filas_por_panel=1):
    """Figura con dos columnas de paneles (una si solo hay uno) y los ejes de cada panel."""
    columnas = min(2, paneles)
    filas = math.ceil(paneles / columnas)
    figura, ejes = plt.subplots(filas * filas_por_panel, columnas, figsize=(6.4 * columnas, alto * filas * filas_por_panel), squeeze=False)
    for sobrante in range(paneles, filas * columnas):
        for fila in range(filas_por_panel):
            ejes[(sobrante // columnas) * filas_por_panel + fila][sobrante % columnas].set_visible(False)
    return figura, [[ejes[(panel // columnas) * filas_por_panel + fila][panel % columnas] for fila in range(filas_por_panel)]
                    for panel in range(paneles)]


def grafica_latencia(corridas, objetivo, ruta):
    """Latencia p50, p95 y p99 contra usuarios de cada corrida, con el p95 de sus repeticiones y el objetivo."""
    elegidas = principales(corridas)
    figura, paneles = rejilla(len(elegidas), 4.2)
    for (eje,), corrida in zip(paneles, elegidas):
        tabla = agregadas(corrida)
        posiciones = list(range(len(tabla)))
        for columna in ("p50_ms", "p95_ms", "p99_ms"):
            eje.plot(posiciones, tabla[columna], marker="o", color=COLORES[columna], label=ETIQUETAS[columna])
        for marcador, nombre in zip(MARCADORES, corrida["repeticiones"]):
            otra = agregadas(corridas[nombre])
            eje.plot(range(len(otra)), otra["p95_ms"], marker=marcador, linestyle=":", color=COLORES["p95_ms"],
                     label=f"p95, repetición {nombre.rsplit('_r', 1)[1]}")
        eje.axhline(objetivo, color="gray", linestyle="--", linewidth=1, label=f"Objetivo de p95 ({objetivo:g} ms)")
        if corrida["degradacion"] is not None:
            eje.axvspan(corrida["degradacion"]["escalon"] - 1.5, len(tabla) - 0.5, color="crimson", alpha=0.07)
        eje.set_yscale("log")
        eje.set_ylim(10, 10000)
        eje.set_xticks(posiciones)
        eje.set_xticklabels(tabla["usuarios"].astype(int))
        eje.set_xlabel("Usuarios concurrentes (una tarea por segundo cada uno)")
        eje.set_ylabel("Latencia (ms, escala logarítmica)")
        eje.set_title(configuracion(corrida), fontsize=10)
        eje.grid(alpha=0.3, which="both")
        eje.legend(fontsize=7, loc="upper left")
    figura.suptitle("Latencia del servicio por escalón de usuarios (zona sombreada: desde el punto de degradación)")
    figura.tight_layout()
    figura.savefig(ruta, dpi=RESOLUCION)
    plt.close(figura)
    return ruta


def grafica_rendimiento(corridas, ruta):
    """Peticiones por segundo atendidas contra las ofrecidas y tasa de error de cada corrida."""
    elegidas = principales(corridas)
    figura, paneles = rejilla(len(elegidas), 4.2)
    for (eje,), corrida in zip(paneles, elegidas):
        tabla = agregadas(corrida)
        posiciones = list(range(len(tabla)))
        eje.bar(posiciones, tabla["rps"], color="steelblue", width=0.6, label="Peticiones por segundo atendidas")
        eje.plot(posiciones, tabla["usuarios"], color="black", linestyle="--", marker=".", label="Peticiones por segundo ofrecidas")
        for marcador, nombre in zip(MARCADORES, corrida["repeticiones"]):
            otra = agregadas(corridas[nombre])
            eje.scatter(range(len(otra)), otra["rps"], marker=marcador, color="darkorange", zorder=3,
                        label=f"Atendidas, repetición {nombre.rsplit('_r', 1)[1]}")
        errores = eje.twinx()
        errores.plot(posiciones, tabla["tasa_error"] * 100, color="crimson", marker="s", linewidth=1, label="Tasa de error")
        errores.set_ylim(0, 100)
        errores.set_ylabel("Tasa de error (%)")
        eje.set_xticks(posiciones)
        eje.set_xticklabels(tabla["usuarios"].astype(int))
        eje.set_xlabel("Usuarios concurrentes (una tarea por segundo cada uno)")
        eje.set_ylabel("Peticiones por segundo")
        eje.set_title(configuracion(corrida), fontsize=10)
        eje.grid(axis="y", alpha=0.3)
        lineas, textos = eje.get_legend_handles_labels()
        lineas_error, textos_error = errores.get_legend_handles_labels()
        eje.legend(lineas + lineas_error, textos + textos_error, fontsize=7, loc="upper left")
    figura.suptitle("Rendimiento y errores por escalón de usuarios")
    figura.tight_layout()
    figura.savefig(ruta, dpi=RESOLUCION)
    plt.close(figura)
    return ruta


def grafica_recursos(corridas, ruta):
    """CPU y memoria de cada contenedor a lo largo de la prueba, con los cambios de escalón."""
    elegidas = [corrida for corrida in principales(corridas) if origen_de_tiempos(corrida) is not None]
    if not elegidas:
        return None
    figura, paneles = rejilla(len(elegidas), 2.9, filas_por_panel=2)
    for (eje_cpu, eje_memoria), corrida in zip(paneles, elegidas):
        origen, recursos, tabla = origen_de_tiempos(corrida), corrida["recursos"], agregadas(corrida)
        duracion = corrida["escenario"]["duracion_s"]
        durante = recursos[(recursos["epoch"] >= origen - 5) & (recursos["epoch"] <= origen + duracion * len(tabla) + 5)]
        for servicio in SERVICIOS:
            lecturas = durante[durante["servicio"] == servicio]
            eje_cpu.plot(lecturas["epoch"] - origen, lecturas["cpu_pct"], color=COLORES[servicio], label=servicio)
            eje_memoria.plot(lecturas["epoch"] - origen, lecturas["mem_mib"], color=COLORES[servicio], label=servicio)
        for escalon in tabla.itertuples():
            inicio = (escalon.escalon - 1) * duracion
            eje_cpu.axvline(inicio, color="gray", linewidth=0.6, linestyle=":")
            eje_memoria.axvline(inicio, color="gray", linewidth=0.6, linestyle=":")
            eje_cpu.annotate(f"{int(escalon.usuarios)}", (inicio + duracion / 2, 1.02), xycoords=("data", "axes fraction"), ha="center", fontsize=7)
        eje_cpu.set_title(configuracion(corrida), fontsize=10, pad=16)
        eje_cpu.set_ylabel("CPU (% de un núcleo)")
        eje_memoria.set_ylabel("Memoria (MiB)")
        eje_memoria.set_xlabel("Segundos desde el inicio de la prueba")
        eje_cpu.grid(alpha=0.3)
        eje_memoria.grid(alpha=0.3)
        eje_cpu.legend(fontsize=7, loc="upper left", ncol=3)
    figura.suptitle("Recursos de los contenedores durante la prueba, con docker stats (sobre cada panel, usuarios de cada escalón)")
    figura.tight_layout(rect=(0, 0, 1, 0.98))
    figura.savefig(ruta, dpi=RESOLUCION)
    plt.close(figura)
    return ruta


def a_json(corridas, diagnostico=None):
    """Versión serializable de las corridas y del diagnóstico para carga.json."""
    salida = {"diagnostico_de_hilos": diagnostico or None, "configuraciones": por_configuracion(corridas), "corridas": {}}
    for nombre, corrida in corridas.items():
        salida["corridas"][nombre] = {
            "configuracion": configuracion(corrida), "sistema": corrida["sistema"], "escenario": corrida["escenario"],
            "degradacion": corrida["degradacion"], "capacidad": corrida["capacidad"], "repeticiones": corrida["repeticiones"],
            "escalones": json.loads(corrida["escalones"].to_json(orient="records")),
            "recursos_por_escalon": json.loads(corrida["recursos_escalon"].to_json(orient="records")),
            "variacion": None if corrida["variacion"] is None else json.loads(corrida["variacion"].to_json(orient="records")),
        }
    return salida


def main():
    argumentos = leer_argumentos()
    try:
        corridas = analizar(argumentos.carpeta, argumentos.p95_objetivo_ms, argumentos.error_maximo, argumentos.cumplimiento)
    except FileNotFoundError as error:
        print(error)
        return 1
    carpeta, figuras = Path(argumentos.carpeta), Path(argumentos.figuras)
    figuras.mkdir(parents=True, exist_ok=True)
    diagnostico = leer_json(carpeta / "hilos.json")
    texto = reporte(corridas, argumentos, diagnostico)
    (carpeta / "resumen.md").write_text(texto, encoding="utf-8")
    (carpeta / "carga.json").write_text(json.dumps(a_json(corridas, diagnostico), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if principales(corridas):
        grafica_latencia(corridas, argumentos.p95_objetivo_ms, figuras / "carga_latencia.png")
        grafica_rendimiento(corridas, figuras / "carga_rendimiento.png")
        grafica_recursos(corridas, figuras / "carga_recursos.png")
    print(texto, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
