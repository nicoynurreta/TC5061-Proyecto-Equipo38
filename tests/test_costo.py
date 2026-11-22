import csv
import json
import sys

import pytest

from mibici.finops import costo

COLUMNAS = ["escalon", "usuarios", "inicio_s", "fin_s", "ventana_s", "nombre", "peticiones", "fallos", "tasa_error", "rps",
            "predicciones_s", "media_ms", "p50_ms", "p95_ms", "p99_ms", "max_ms"]
INICIO = 1_000_000.0


def _escalon(numero, usuarios, rps, p95, tasa_error=0.0, predicciones_s=None, nombre=costo.AGREGADO):
    return {"escalon": numero, "usuarios": usuarios, "inicio_s": (numero - 1) * 60 + 10, "fin_s": numero * 60, "ventana_s": 50,
            "nombre": nombre, "peticiones": int(rps * 50), "fallos": int(rps * 50 * tasa_error), "tasa_error": tasa_error, "rps": rps,
            "predicciones_s": rps * 1.5 if predicciones_s is None else predicciones_s, "media_ms": p95 / 2, "p50_ms": p95 / 2,
            "p95_ms": p95, "p99_ms": p95 * 1.2, "max_ms": p95 * 2}


def _escribir_corrida(carpeta, nombre, escalones, recursos=(), procesos=1, cpus=1.0, arranque=20.0, desfase=0.0):
    with open(carpeta / f"{nombre}_escalones.csv", "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(escalones)
    with open(carpeta / f"{nombre}_recursos.csv", "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=["epoch", "servicio", "cpu_pct", "mem_mib", "mem_limite_mib"])
        escritor.writeheader()
        escritor.writerows(recursos)
    (carpeta / f"{nombre}_escenario.json").write_text(json.dumps({"inicio_epoch": INICIO, "tamano_lote": 3, "etiquetas": []}), encoding="utf-8")
    sistema = {"procesos": procesos, "cpus": cpus, "memoria": "1g", "arranque_s": arranque, "desfase_reloj_s": desfase}
    (carpeta / f"{nombre}_sistema.json").write_text(json.dumps(sistema), encoding="utf-8")


def _lectura(segundo, servicio, cpu, memoria, desfase=0.0):
    return {"epoch": INICIO - desfase + segundo, "servicio": servicio, "cpu_pct": cpu, "mem_mib": memoria, "mem_limite_mib": 1024}


def test_el_costo_por_inferencia_es_el_precio_por_hora_entre_las_inferencias_por_hora():
    assert costo.costo_por_inferencia(0.36, 100) == pytest.approx(1e-6)
    assert costo.costo_por_inferencia(0.0208, 40) == pytest.approx(0.0208 / 144_000)
    assert costo.costo_por_inferencia(0.36, 0) is None


def test_la_capacidad_es_el_escalon_de_mayor_rendimiento_que_cumple_el_objetivo():
    filas = [_escalon(1, 10, 10, 60), _escalon(2, 20, 20, 90), _escalon(3, 40, 38, 420), _escalon(4, 60, 41, 2300),
             _escalon(2, 20, 99, 10, nombre="/health")]
    mejor = costo.capacidad_sostenida(filas, 500, 0.01)
    assert (mejor["escalon"], mejor["usuarios"], mejor["rps"]) == (3, 40, 38)
    assert costo.capacidad_sostenida(filas, 100, 0.01)["escalon"] == 2
    assert costo.capacidad_sostenida(filas, 50, 0.01) is None


def test_la_capacidad_no_cuenta_los_escalones_que_siguen_al_primero_que_rompe_el_objetivo():
    filas = [_escalon(1, 10, 10, 60), _escalon(2, 20, 20, 900), _escalon(3, 40, 39, 80)]
    assert costo.capacidad_sostenida(filas, 500, 0.01)["escalon"] == 1
    con_errores = [_escalon(1, 10, 10, 60), _escalon(2, 20, 20, 70, tasa_error=0.02), _escalon(3, 40, 39, 80)]
    assert costo.capacidad_sostenida(con_errores, 500, 0.01)["escalon"] == 1
    assert costo.capacidad_sostenida(con_errores, 500, 0.02)["escalon"] == 3
    assert costo.capacidad_sostenida([{**_escalon(1, 10, 0, 0), "peticiones": 0}], 500, 0.01) is None


def test_las_peticiones_de_prediccion_no_cuentan_las_de_salud():
    filas = [_escalon(1, 40, 40, 300, predicciones_s=60), _escalon(1, 40, 24, 280, predicciones_s=24, nombre="/predecir"),
             _escalon(1, 40, 12, 320, predicciones_s=36, nombre="/predecir/lote"), _escalon(1, 40, 4, 30, predicciones_s=0, nombre="/health")]
    capacidad = costo.capacidad_sostenida(filas, 500, 0.01)
    assert capacidad["rps"] == 40 and capacidad["peticiones_prediccion_s"] == 36 and capacidad["predicciones_s"] == 60
    assert costo.capacidad_sostenida(filas[:1], 500, 0.01)["peticiones_prediccion_s"] == 40


def test_la_sensibilidad_recalcula_la_capacidad_con_cada_objetivo_de_latencia(tmp_path):
    _escribir_corrida(tmp_path, "un_proceso", [_escalon(1, 10, 10, 60), _escalon(2, 20, 20, 300), _escalon(3, 40, 38, 900)])
    corrida = costo.analizar_corrida(tmp_path, "un_proceso", 500, 0.01, [250, 1000, 50])
    assert [punto["p95_objetivo_ms"] for punto in corrida["sensibilidad"]] == [50, 250, 500, 1000]
    assert [punto["rps"] for punto in corrida["sensibilidad"]] == [None, 10, 20, 38]
    fila = costo.costos_de_la_corrida(corrida, costo.leer_instancia("referencia:2:2:0.036"), 472, 0)
    segun_objetivo = fila["costo_por_prediccion_segun_objetivo"]
    assert list(segun_objetivo) == ["50", "250", "500", "1000"] and segun_objetivo["50"] is None
    assert segun_objetivo["1000"] == pytest.approx(0.036 / (38 * 1.5 * 3600)) and segun_objetivo["500"] == fila["costo_por_prediccion"]


def test_los_recursos_se_miden_solo_en_la_ventana_del_escalon():
    lecturas = [_lectura(5, "api", 300, 900), _lectura(75, "api", 80, 250), _lectura(100, "api", 100, 260),
                _lectura(110, "mlflow", 1, 400), _lectura(120, "api", 999, 999)]
    uso = costo.uso_de_recursos(lecturas, INICIO + 70, INICIO + 120)
    assert uso["api"] == {"lecturas": 2, "cpu_media_pct": 90.0, "cpu_max_pct": 100, "mem_max_mib": 260, "mem_limite_mib": 1024}
    assert uso["mlflow"]["lecturas"] == 1 and list(uso) == ["api", "mlflow"]
    assert costo.uso_de_recursos(lecturas, INICIO + 500, INICIO + 600) == {}


def test_la_instancia_se_lee_del_argumento_y_rechaza_valores_invalidos():
    assert costo.leer_instancia("t3.small:2:2:0.0208") == {"nombre": "t3.small", "vcpu": 2.0, "memoria_gib": 2.0, "precio_hora": 0.0208}
    for texto in ("t3.small:2:2", "t3.small:2:2:0", "t3.small:dos:2:0.02", "t3.small:2:-1:0.02"):
        with pytest.raises(ValueError):
            costo.leer_instancia(texto)


def test_los_segundos_activos_suman_el_arranque_y_el_tiempo_de_atender_la_demanda():
    assert costo.segundos_activos(472, 944, 30) == pytest.approx(30.5)
    assert costo.segundos_activos(472, 0, 30) is None


def test_analizar_calcula_capacidad_recursos_y_costos_de_cada_corrida(tmp_path):
    escalones = [_escalon(1, 10, 10, 60), _escalon(2, 20, 20, 90), _escalon(3, 40, 40, 400), _escalon(4, 60, 42, 2500)]
    recursos = [_lectura(150, "api", 90, 300, desfase=2), _lectura(170, "api", 100, 310, desfase=2),
                _lectura(160, "mlflow", 2, 400, desfase=2), _lectura(200, "api", 250, 800, desfase=2)]
    _escribir_corrida(tmp_path, "un_proceso", escalones, recursos, desfase=2)
    instancia = costo.leer_instancia("referencia:2:2:0.036")
    resultado = costo.analizar(tmp_path, [instancia], demanda_hora=472, descuento=0.25)
    corrida = resultado["corridas"][0]
    assert corrida["corrida"] == "un_proceso" and corrida["capacidad"]["escalon"] == 3
    assert corrida["recursos"]["api"] == {"lecturas": 2, "cpu_media_pct": 95.0, "cpu_max_pct": 100, "mem_max_mib": 310, "mem_limite_mib": 1024}
    fila = resultado["costos"][0]
    assert fila["cumple_objetivo"] and fila["peticiones_hora"] == 144_000 and fila["predicciones_hora"] == 216_000
    assert fila["costo_por_peticion"] == pytest.approx(0.036 / 144_000)
    assert fila["costo_por_prediccion"] == pytest.approx(0.036 / 216_000)
    assert fila["utilizacion_real"] == pytest.approx(472 / 216_000)
    assert fila["siempre_encendido"]["costo_por_prediccion"] == pytest.approx(0.036 / 472)
    assert fila["siempre_encendido"]["costo_mes"] == pytest.approx(0.036 * 730)
    assert fila["con_compromiso"]["costo_hora"] == pytest.approx(0.027)
    activos = 20 + 472 / 60
    assert fila["encendido_por_hora"]["segundos_activos"] == pytest.approx(activos, abs=0.01)
    assert fila["encendido_por_hora"]["costo_por_prediccion"] == pytest.approx(0.036 * activos / 3600 / 472)
    assert fila["encendido_por_hora"]["ahorro"] == pytest.approx(1 - activos / 3600)
    assert fila["cpu_pico_nucleos"] == pytest.approx(1.02) and fila["memoria_pico_gib"] == pytest.approx(710 / 1024, abs=0.001)
    assert fila["cabe"] is True
    assert costo.costos_de_la_corrida(corrida, costo.leer_instancia("chica:1:0.5:0.01"), 472, 0)["cabe"] is False


def test_una_corrida_que_no_cumple_el_objetivo_no_tiene_costo(tmp_path):
    _escribir_corrida(tmp_path, "saturada", [_escalon(1, 50, 30, 4000)])
    resultado = costo.analizar(tmp_path, [costo.leer_instancia("referencia:2:2:0.036")])
    assert resultado["corridas"][0]["capacidad"] is None and resultado["corridas"][0]["recursos"] == {}
    assert resultado["costos"][0]["cumple_objetivo"] is False and "costo_por_peticion" not in resultado["costos"][0]
    assert "ningún escalón cumple el objetivo" in costo.reporte(resultado)


def test_sin_archivos_de_la_prueba_de_carga_avisa(tmp_path):
    with pytest.raises(FileNotFoundError, match="escalones"):
        costo.analizar(tmp_path, [costo.leer_instancia("referencia:2:2:0.036")])


def test_main_escribe_el_reporte_y_el_json(tmp_path, monkeypatch, capsys):
    _escribir_corrida(tmp_path, "un_proceso", [_escalon(1, 10, 10, 60), _escalon(2, 20, 20, 90)], [_lectura(80, "api", 50, 300)])
    _escribir_corrida(tmp_path, "dos_procesos", [_escalon(1, 10, 10, 50), _escalon(2, 20, 20, 60)], procesos=2, cpus=2.0)
    salida = tmp_path / "salida"
    monkeypatch.setattr(sys, "argv", ["costo", "--carpeta", str(tmp_path), "--instancia", "referencia:2:2:0.036",
                                      "--instancia", "alterna:2:4:0.05", "--descuento", "0.3", "--salida", str(salida)])
    assert costo.main() == 0
    texto = capsys.readouterr().out
    assert texto == (salida / "costo.md").read_text(encoding="utf-8")
    assert "## Costo a plena capacidad" in texto and "Con compromiso (30 % menos)" in texto and "`dos_procesos`" in texto
    assert "p95 de hasta 250 ms" in texto and "p95 de hasta 2000 ms" in texto and "Ahorro frente a siempre encendida" in texto
    guardado = json.loads((salida / "costo.json").read_text(encoding="utf-8"))
    assert [corrida["corrida"] for corrida in guardado["corridas"]] == ["un_proceso", "dos_procesos"]
    assert [costo["instancia"] for costo in guardado["costos"]] == ["referencia", "referencia", "alterna", "alterna"]
    assert len(guardado["costos"]) == 4 and guardado["supuestos"]["descuento_por_compromiso"] == 0.3
    monkeypatch.setattr(sys, "argv", ["costo", "--carpeta", str(tmp_path), "--instancia", "mal_escrita"])
    assert costo.main() == 1
