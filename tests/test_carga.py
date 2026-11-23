import ast
import csv
import json
import sys
import time

import pandas as pd
import pytest

from api import esquemas
from carga import correr, escalones, hilos, muestreador, resumen
from mibici import config

EJEMPLOS = config.RAIZ_PROYECTO / "api" / "ejemplos"
LOTE = json.loads((EJEMPLOS / "peticion_lote.json").read_text(encoding="utf-8"))
LINEA = ('{"BlockIO":"0B / 0B","CPUPerc":"97.52%","Container":"3f2a","ID":"3f2a","MemPerc":"22.46%",'
         '"MemUsage":"230MiB / 1GiB","Name":"mibici-api-1","NetIO":"1.2MB / 3.4kB","PIDs":"22"}')
INICIO = 2_000_000.0


def _muestras(escalon, duracion, cuantas, milisegundos, nombre="/predecir", exito=True, desde=10.0):
    paso = (duracion - desde) / cuantas
    return [((escalon - 1) * duracion + desde + posicion * paso, nombre, milisegundos, exito) for posicion in range(cuantas)]


def _corrida(carpeta, nombre, p95, rps, desfase=0.0, etiquetas=(), cpu=(50, 100, 100), hilos=0):
    filas = []
    for numero, (usuarios, latencia, ritmo) in enumerate(zip([10, 20, 40], p95, rps), start=1):
        fila = dict.fromkeys(escalones.COLUMNAS, 0)
        fila.update(escalon=numero, usuarios=usuarios, inicio_s=(numero - 1) * 60 + 10, fin_s=numero * 60, ventana_s=50,
                    nombre=escalones.AGREGADO, peticiones=int(ritmo * 50), rps=ritmo, predicciones_s=ritmo * 1.5, media_ms=latencia / 2,
                    p50_ms=latencia / 2, p95_ms=latencia, p99_ms=latencia * 1.2, max_ms=latencia * 2)
        filas += [fila, {**fila, "nombre": "/predecir", "rps": ritmo * 0.6}, {**fila, "nombre": "/predecir/lote", "rps": ritmo * 0.3}]
    escalones.escribir(carpeta / f"{nombre}_escalones.csv", filas)
    lecturas = [{"epoch": INICIO - desfase + (numero - 1) * 60 + segundo, "hora": "00:00:00", "contenedor": f"mibici-{servicio}-1",
                 "servicio": servicio, "cpu_pct": uso if servicio == "api" else 1.0, "mem_mib": 250 + numero, "mem_limite_mib": 1024,
                 "mem_pct": 25.0, "red_entrada_mb": 0, "red_salida_mb": 0, "pids": 3}
                for numero, uso in enumerate(cpu, start=1) for segundo in (5, 20, 40) for servicio in ("api", "mlflow")]
    with open(carpeta / f"{nombre}_recursos.csv", "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=muestreador.COLUMNAS)
        escritor.writeheader()
        escritor.writerows(lecturas)
    escenario = {"inicio_epoch": INICIO, "duracion_s": 60, "calentamiento_s": 10, "tamano_lote": 3, "etiquetas": list(etiquetas)}
    (carpeta / f"{nombre}_escenario.json").write_text(json.dumps(escenario), encoding="utf-8")
    sistema = {"procesos": 1, "cpus": 1.0, "memoria": "1g", "hilos": hilos, "arranque_s": 20.0, "desfase_reloj_s": desfase,
               "fecha": "2026-11-18T10:00:00",
               "modelo": {"nombre": "mibici-equipo38-p2-riesgo", "version": "1", "alias": "champion"}}
    (carpeta / f"{nombre}_sistema.json").write_text(json.dumps(sistema), encoding="utf-8")


def test_leer_escalones_acepta_espacios_y_deja_el_valor_por_defecto_si_viene_vacio():
    assert escalones.leer_escalones("5, 10,20", [1]) == [5, 10, 20]
    assert escalones.leer_escalones("", [2, 4]) == [2, 4] and escalones.leer_escalones(None, (2, 4)) == [2, 4]
    with pytest.raises(ValueError):
        escalones.leer_escalones("5,diez", [1])


def test_armar_lote_repite_los_ejemplos_con_estaciones_distintas_y_peticiones_validas():
    assert escalones.armar_lote(LOTE, len(LOTE)) == LOTE
    lote = escalones.armar_lote(LOTE, 472)
    assert len(lote) == 472 and len({fila["estacion_id"] for fila in lote}) == 472
    assert {(fila["hora_dia"], fila["dia_semana"]) for fila in lote} == {(16, 1)}
    for fila in lote[:7]:
        esquemas.PeticionRiesgo.model_validate(fila)
    assert escalones.armar_lote(LOTE, 1) == LOTE[:1]


def test_percentil_usa_el_rango_mas_cercano():
    valores = [float(valor) for valor in range(1, 101)]
    assert (escalones.percentil(valores, 0.50), escalones.percentil(valores, 0.95), escalones.percentil(valores, 0.99)) == (50, 95, 99)
    assert escalones.percentil(valores, 1.0) == 100 and escalones.percentil(valores, 0.0) == 1
    assert escalones.percentil([7.0], 0.95) == 7.0 and escalones.percentil([], 0.95) == 0.0


def test_resumir_descarta_el_calentamiento_y_separa_escalones_y_endpoints():
    muestras = (_muestras(1, 60, 100, 20.0) + _muestras(1, 60, 50, 40.0, "/predecir/lote") + _muestras(1, 60, 9, 900.0, desde=0.5)[:9]
                + _muestras(2, 60, 200, 30.0) + _muestras(2, 60, 50, 5000.0, exito=False) + [(125.0, "/predecir", 1.0, True)])
    filas = escalones.resumir(muestras, [10, 20], 60, 10, {"/predecir": 1, "/predecir/lote": 3})
    assert [(fila["escalon"], fila["nombre"]) for fila in filas] == [(1, "Agregado"), (1, "/predecir"), (1, "/predecir/lote"),
                                                                     (2, "Agregado"), (2, "/predecir")]
    primero, _, lote, segundo, _ = filas
    assert (primero["usuarios"], primero["inicio_s"], primero["fin_s"], primero["ventana_s"]) == (10, 10, 60, 50)
    assert primero["peticiones"] == 150 + sum(1 for segundo_, *_ in _muestras(1, 60, 9, 900.0, desde=0.5) if segundo_ >= 10)
    assert lote["peticiones"] == 50 and lote["rps"] == 1.0 and lote["predicciones_s"] == 3.0 and lote["p95_ms"] == 40.0
    assert segundo["peticiones"] == 250 and segundo["fallos"] == 50 and segundo["tasa_error"] == 0.2
    assert segundo["rps"] == 5.0 and segundo["predicciones_s"] == 4.0
    assert (segundo["p50_ms"], segundo["p95_ms"], segundo["max_ms"]) == (30.0, 5000.0, 5000.0)


def test_resumir_deja_en_cero_un_escalon_sin_peticiones_y_escribir_guarda_las_columnas(tmp_path):
    filas = escalones.resumir(_muestras(1, 30, 10, 15.0, desde=5.0), [5, 10], 30, 5)
    assert len(filas) == 3 and filas[2]["nombre"] == "Agregado" and filas[2]["peticiones"] == 0 and filas[2]["p95_ms"] == 0.0
    assert filas[0]["predicciones_s"] == 0.0
    escalones.escribir(tmp_path / "x_escalones.csv", filas)
    tabla = pd.read_csv(tmp_path / "x_escalones.csv")
    assert list(tabla.columns) == escalones.COLUMNAS and tabla["peticiones"].tolist() == [10, 10, 0]


def test_a_bytes_entiende_las_unidades_de_docker_stats():
    assert muestreador.a_bytes("0B") == 0 and muestreador.a_bytes("1.2kB") == 1200 and muestreador.a_bytes(" 3.4MB ") == 3.4e6
    assert muestreador.a_bytes("230MiB") == 230 * 2**20 and muestreador.a_bytes("7.487GiB") == pytest.approx(7.487 * 2**30)
    assert muestreador.a_bytes("1e+03kB") == 1e6 and muestreador.a_bytes("1e+03MiB") == 1000 * 2**20
    with pytest.raises(KeyError):
        muestreador.a_bytes("5 bananas")
    with pytest.raises(ValueError):
        muestreador.a_bytes("--")


def test_interpretar_convierte_una_lectura_y_descarta_lo_que_no_es_del_sistema():
    fila = muestreador.interpretar(LINEA, 1_700_000_000.0)
    assert list(fila) == muestreador.COLUMNAS
    assert (fila["contenedor"], fila["servicio"], fila["cpu_pct"], fila["mem_mib"], fila["mem_limite_mib"]) == ("mibici-api-1", "api", 97.52, 230.0, 1024.0)
    assert (fila["mem_pct"], fila["red_entrada_mb"], fila["red_salida_mb"], fila["pids"]) == (22.46, 1.2, 0.003, 22)
    assert muestreador.interpretar(LINEA.replace("mibici-api-1", "otro-proyecto-db-1"), 0.0) is None
    assert muestreador.interpretar(LINEA.replace("97.52%", "--").replace("230MiB / 1GiB", "-- / --"), 0.0) is None
    assert muestreador.interpretar(LINEA.replace("1.2MB", "1e+03kB"), 0.0)["red_entrada_mb"] == 1.0
    assert muestreador.interpretar(LINEA.replace("1.2MB", "mucho"), 0.0) is None
    assert muestreador.servicio("mibici-locust-run-3f2a9c") == "locust" and muestreador.servicio("mibici-mlflow-1") == "mlflow"


def test_muestrear_escribe_una_fila_por_contenedor_en_cada_lectura(tmp_path, monkeypatch):
    lecturas = iter([[muestreador.interpretar(LINEA, 1.0)], [], [muestreador.interpretar(LINEA, 2.0)] * 2])
    monkeypatch.setattr(muestreador.shutil, "which", lambda motor: motor)
    monkeypatch.setattr(muestreador, "leer_una_vez", lambda motor, proyecto: next(lecturas, []))
    salida = tmp_path / "carpeta" / "recursos.csv"
    assert muestreador.muestrear(salida, intervalo=0.01, duracion=0.2) == 2
    tabla = pd.read_csv(salida)
    assert list(tabla.columns) == muestreador.COLUMNAS and tabla["epoch"].tolist() == [1.0, 2.0, 2.0]
    monkeypatch.setattr(muestreador.shutil, "which", lambda motor: None)
    with pytest.raises(FileNotFoundError):
        muestreador.muestrear(salida, duracion=0.1)


def test_la_degradacion_es_el_primer_escalon_que_rompe_la_latencia_los_errores_o_la_carga_atendida():
    tabla = pd.DataFrame({"escalon": [1, 2, 3], "usuarios": [10, 20, 40], "p95_ms": [80.0, 300.0, 2400.0], "tasa_error": [0.0, 0.0, 0.0],
                          "rps": [10.0, 19.8, 31.0], "predicciones_s": [15.0, 29.7, 46.5], "p50_ms": [30.0, 90.0, 900.0],
                          "p99_ms": [100.0, 400.0, 3000.0]})
    degradacion = resumen.punto_de_degradacion(tabla, 500, 0.01, 0.9)
    assert (degradacion["escalon"], degradacion["usuarios"]) == (3, 40) and len(degradacion["motivos"]) == 2
    assert resumen.capacidad(tabla, degradacion)["rps"] == 19.8
    assert resumen.punto_de_degradacion(tabla, 5000, 0.01, 0.5) is None
    assert resumen.capacidad(tabla, None)["usuarios"] == 40
    con_errores = tabla.assign(tasa_error=[0.05, 0.0, 0.0])
    assert resumen.punto_de_degradacion(con_errores, 500, 0.01, 0.9)["escalon"] == 1
    assert resumen.capacidad(con_errores, resumen.punto_de_degradacion(con_errores, 500, 0.01, 0.9)) is None


def test_analizar_alinea_los_recursos_con_los_escalones_y_compara_con_la_repeticion(tmp_path):
    _corrida(tmp_path, "un_proceso", p95=[80, 300, 2400], rps=[10, 19.8, 31], desfase=3.0, cpu=(30, 70, 100))
    _corrida(tmp_path, "un_proceso_r2", p95=[88, 330, 2000], rps=[10, 19.6, 32])
    _corrida(tmp_path, "lote_hora", p95=[90, 95, 99], rps=[10, 20, 40], etiquetas=["lote"])
    _corrida(tmp_path, "un_proceso_en_serie", p95=[40, 50, 60], rps=[10, 20, 40], hilos=1)
    corridas = resumen.analizar(tmp_path)
    assert list(corridas) == ["un_proceso", "un_proceso_r2", "un_proceso_en_serie", "lote_hora"]
    assert resumen.configuracion(corridas["un_proceso"]) == "1 proceso, 1 CPU"
    assert resumen.configuracion(corridas["un_proceso_en_serie"]) == "1 proceso, 1 CPU, 1 petición a la vez por proceso"
    principal = corridas["un_proceso"]
    assert principal["degradacion"]["escalon"] == 3 and principal["capacidad"]["usuarios"] == 20
    recursos = principal["recursos_escalon"]
    api = recursos[recursos["servicio"] == "api"].set_index("escalon")
    assert api["lecturas"].tolist() == [2, 2, 2] and api["cpu_media_pct"].tolist() == [30.0, 70.0, 100.0]
    assert api["mem_max_mib"].tolist() == [251.0, 252.0, 253.0]
    cambio = principal["variacion"].set_index("escalon")
    assert principal["repeticiones"] == ["un_proceso_r2"] and corridas["un_proceso_r2"]["repeticiones"] == []
    assert cambio.loc[1, "p95_razon"] == pytest.approx(1.10) and cambio.loc[3, "p95_razon"] == pytest.approx(1.20)
    assert (cambio.loc[2, "rps_un_proceso"], cambio.loc[2, "rps_un_proceso_r2"]) == (19.8, 19.6)
    assert corridas["un_proceso_r2"]["variacion"] is None and corridas["lote_hora"]["degradacion"] is None
    assert [corrida["nombre"] for corrida in resumen.principales(corridas)] == ["un_proceso", "un_proceso_en_serie"]
    assert "p95 (ms), `un_proceso_r2`" in resumen.tabla_variacion(principal)
    assert resumen.nombre_base("un_proceso_r3") == "un_proceso" and resumen.nombre_base("un_proceso_en_serie") == "un_proceso_en_serie"
    juntas = resumen.por_configuracion(corridas)
    assert [fila["corrida"] for fila in juntas] == ["un_proceso", "un_proceso_en_serie", "lote_hora"]
    assert (juntas[0]["corridas"], juntas[0]["degradacion_usuarios"], juntas[0]["capacidad_rps"]) == (2, [40, 40], [19.8, 19.6])
    assert juntas[0]["capacidad_mediana_rps"] == pytest.approx(19.7) and juntas[0]["rendimiento_maximo_rps"] == [31.0, 32.0]
    assert juntas[2]["degradacion_usuarios"] == [None] and juntas[2]["capacidad_rps"] == [40.0]
    tabla = resumen.tabla_configuraciones(corridas)
    assert "| `un_proceso` | 1 proceso, 1 CPU | 3 | 2 | 40 usuarios | 19.6 a 19.8 | 19.7 | 29.4 a 29.7 | 300 a 330 | 31.0 a 32.0 | 0.0 % | 20.0 |" in tabla
    assert "| `lote_hora` | 1 proceso, 1 CPU | 3 | 1 | ninguno | 40.0 | 40.0 | 60.0 | 99 | 40.0 | 0.0 % | 20.0 |" in tabla
    assert resumen.intervalo([]) == "n. a." and resumen.intervalo([15, 10, 20], 0) == "10 a 20" and resumen.intervalo([8.0, 8.04]) == "8.0"


def test_main_escribe_el_resumen_el_json_y_las_tres_graficas(tmp_path, monkeypatch, capsys):
    _corrida(tmp_path, "un_proceso", p95=[80, 300, 2400], rps=[10, 19.8, 31])
    _corrida(tmp_path, "dos_procesos", p95=[60, 90, 200], rps=[10, 20, 39.9])
    diagnostico = {"modelo": "mibici-equipo38-p2-riesgo", "version": "1", "segundos": 8, "cpus": 1.0,
                   "filas": [{"hilos": 1, "predicciones_s": 40.8, "cpu_ms_por_prediccion": 24.6, "cpu_sistema_pct": 0.0, "periodos_frenados": 4},
                             {"hilos": 4, "predicciones_s": 9.6}]}
    (tmp_path / "hilos.json").write_text(json.dumps(diagnostico), encoding="utf-8")
    figuras = tmp_path / "figuras"
    monkeypatch.setattr(sys, "argv", ["resumen", "--carpeta", str(tmp_path), "--figuras", str(figuras)])
    assert resumen.main() == 0
    texto = capsys.readouterr().out
    assert texto == (tmp_path / "resumen.md").read_text(encoding="utf-8")
    assert "Punto de degradación: escalón 3, 40 usuarios" in texto and "Ningún escalón rompe el objetivo" in texto
    assert "## Diagnóstico de concurrencia" in texto and "| 1 | 40.8 | 24.6 | 0 % | 4 |" in texto and "| 4 | 9.6 | n. a. | n. a. | n. a. |" in texto
    assert "## Resumen por configuración" in texto and "## Resumen por corrida" in texto
    completo = json.loads((tmp_path / "carga.json").read_text(encoding="utf-8"))
    guardado = completo["corridas"]
    assert guardado["un_proceso"]["capacidad"]["rps"] == 19.8 and len(guardado["dos_procesos"]["escalones"]) == 9
    assert sorted(fila["corrida"] for fila in completo["configuraciones"]) == ["dos_procesos", "un_proceso"]
    assert sorted(archivo.name for archivo in figuras.iterdir()) == ["carga_latencia.png", "carga_recursos.png", "carga_rendimiento.png"]
    monkeypatch.setattr(sys, "argv", ["resumen", "--carpeta", str(tmp_path / "vacia"), "--figuras", str(figuras)])
    assert resumen.main() == 1


def test_el_locustfile_define_tres_tareas_ponderadas_y_la_subida_por_escalones():
    arbol = ast.parse((config.RAIZ_PROYECTO / "carga" / "locustfile.py").read_text(encoding="utf-8"))
    clases = {nodo.name: nodo for nodo in arbol.body if isinstance(nodo, ast.ClassDef)}
    assert [base.id for base in clases["Operador"].bases] == ["FastHttpUser"]
    assert [base.id for base in clases["Escalones"].bases] == ["LoadTestShape"]
    tareas = {funcion.name: [ast.unparse(decorador) for decorador in funcion.decorator_list]
              for funcion in clases["Operador"].body if isinstance(funcion, ast.FunctionDef) and funcion.decorator_list}
    assert tareas == {"predecir": ["tag('individual')", "task(PESOS['individual'])"],
                      "predecir_lote": ["tag('lote')", "task(PESOS['lote'])"], "salud": ["tag('salud')", "task(PESOS['salud'])"]}
    assert [funcion.name for funcion in clases["Escalones"].body if isinstance(funcion, ast.FunctionDef)] == ["tick"]


def test_medir_cuenta_las_predicciones_de_todos_los_hilos_y_la_cpu_del_contenedor(tmp_path):
    llamadas = []
    contador = tmp_path / "cpu.stat"

    def anotar(usados):
        contador.write_text(f"usage_usec {usados}\nuser_usec {usados * 3 // 4}\nsystem_usec {usados // 4}\nnr_throttled {usados // 1000}\n",
                            encoding="utf-8")

    def predecir():
        llamadas.append(1)
        anotar(2000 * len(llamadas))

    anotar(0)
    fila = hilos.medir(predecir, 1, 0.2, contador)
    assert fila["hilos"] == 1 and fila["predicciones"] == len(llamadas) > 0
    assert fila["cpu_ms_por_prediccion"] == 2.0 and fila["cpu_sistema_pct"] == 25.0
    assert fila["periodos_frenados"] == 2 * len(llamadas)
    varios = hilos.medir(lambda: time.sleep(0.01), 4, 0.2, tmp_path / "no_existe")
    assert varios["hilos"] == 4 and set(varios) == {"hilos", "predicciones", "predicciones_s"}
    assert varios["predicciones"] >= 4 and hilos.uso_de_cpu(tmp_path / "no_existe") == {}


def test_las_corridas_comparan_uno_y_dos_procesos_con_los_mismos_escalones():
    uno, dos, lote = (correr.CORRIDAS[nombre] for nombre in ("un_proceso", "dos_procesos", "lote_hora"))
    assert (uno["procesos"], uno["cpus"], dos["procesos"], dos["cpus"]) == (1, "1.0", 2, "2.0")
    assert uno["escalones"] == dos["escalones"] and uno["duracion"] == dos["duracion"] and uno["tamano_lote"] == dos["tamano_lote"] == len(LOTE)
    assert lote["etiquetas"] == ["lote"] and lote["tamano_lote"] == correr.ESTACIONES
