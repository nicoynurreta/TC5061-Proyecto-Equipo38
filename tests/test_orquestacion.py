import importlib.util
import re
import shutil
import sqlite3
import subprocess

import pytest
import yaml

from mibici import config

RAIZ = config.RAIZ_PROYECTO
VARIABLE = re.compile(r"\$\{([A-Z_]+)(:-)?[^}]*\}")
PERMANENTES = ["mlflow", "api"]
PERFILES = {"registro": ["registro"], "siembra": ["siembra"], "locust": ["carga"]}
OBJETIVOS = ["sistema", "sistema-registro", "sistema-prueba", "sistema-estado", "sistema-abajo", "humo", "carga", "costo"]


@pytest.fixture(scope="module")
def compose():
    return yaml.safe_load((RAIZ / "docker-compose.yml").read_text(encoding="utf-8"))


def _version_fijada(archivo, paquete="mlflow"):
    for linea in (RAIZ / archivo).read_text(encoding="utf-8").splitlines():
        if linea.startswith(paquete + "=="):
            return linea.split("==", 1)[1].strip()
    return None


def _importar():
    especificacion = importlib.util.spec_from_file_location("importar", RAIZ / "servicios" / "mlflow" / "importar.py")
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def _base_de_prueba(ruta):
    conexion = sqlite3.connect(ruta)
    conexion.executescript(
        "create table runs (run_uuid text, lifecycle_stage text);"
        "create table model_versions (name text, version integer);"
        "create table registered_model_aliases (name text, alias text, version integer);"
        "insert into runs values ('a', 'active'), ('b', 'active'), ('c', 'deleted');"
        "insert into model_versions values ('mibici-equipo38-p2-riesgo', 1), ('mibici-equipo38-p2-riesgo', 2);"
        "insert into registered_model_aliases values ('mibici-equipo38-p2-riesgo', 'champion', 1);"
    )
    conexion.commit()
    conexion.close()


def test_sin_perfiles_el_sistema_son_el_servidor_de_mlflow_y_el_servicio(compose):
    servicios = compose["services"]
    assert sorted(nombre for nombre, servicio in servicios.items() if "profiles" not in servicio) == sorted(PERMANENTES)
    assert {nombre: servicios[nombre]["profiles"] for nombre in PERFILES} == PERFILES
    assert compose["name"] == "mibici"


def test_el_servicio_espera_a_mlflow_sano_y_carga_el_modelo_de_ese_servicio(compose):
    api = compose["services"]["api"]
    assert api["depends_on"]["mlflow"] == {"condition": "service_healthy"}
    assert api["environment"]["MLFLOW_TRACKING_URI"] == "http://mlflow:5000"
    assert api["environment"]["WEB_CONCURRENCY"] == "${API_PROCESOS:-1}" and api["environment"]["HILOS_PREDICCION"] == "${API_HILOS:-1}"
    assert "RUTA_MODELO" not in api["environment"]
    assert api["networks"] == compose["services"]["mlflow"]["networks"] == ["red"]
    assert compose["networks"]["red"]["driver"] == "bridge"


@pytest.mark.parametrize("nombre", PERMANENTES)
def test_los_servicios_permanentes_tienen_salud_reinicio_limites_y_rotacion_de_registros(compose, nombre):
    servicio = compose["services"][nombre]
    assert servicio["healthcheck"]["test"][0] == "CMD" and "/health" in servicio["healthcheck"]["test"][-1]
    assert {"interval", "timeout", "retries", "start_period"} <= set(servicio["healthcheck"])
    assert servicio["restart"] == "unless-stopped"
    assert "cpus" in servicio and "mem_limit" in servicio
    assert servicio["logging"]["options"]["max-size"] == "10m"
    assert servicio["cap_drop"] == ["ALL"] and servicio["security_opt"] == ["no-new-privileges:true"]


def test_los_pasos_de_preparacion_son_dependencias_opcionales_que_deben_terminar_bien(compose):
    servicios = compose["services"]
    opcional = {"condition": "service_completed_successfully", "required": False}
    assert servicios["mlflow"]["depends_on"]["registro"] == opcional
    assert servicios["api"]["depends_on"]["siembra"] == opcional
    assert servicios["siembra"]["depends_on"]["mlflow"] == {"condition": "service_healthy"}
    for nombre in ("registro", "siembra"):
        assert servicios[nombre]["restart"] == "no" and servicios[nombre]["healthcheck"] == {"disable": True}
    assert servicios["registro"]["image"] == servicios["mlflow"]["image"]
    assert servicios["siembra"]["image"] == servicios["api"]["image"]


def test_el_registry_vive_en_volumenes_con_nombre_y_el_servicio_no_escribe_en_disco(compose):
    servicios = compose["services"]
    assert servicios["mlflow"]["volumes"] == ["mlflow_datos:/mlflow/datos", "mlflow_artefactos:/mlflow/artefactos"]
    assert set(compose["volumes"]) == {"mlflow_datos", "mlflow_artefactos"}
    assert "volumes" not in servicios["api"]
    assert servicios["api"]["read_only"] is True and servicios["api"]["tmpfs"] == ["/tmp"]
    origenes = [volumen["source"] for volumen in servicios["registro"]["volumes"] if isinstance(volumen, dict)]
    assert origenes == ["./mlflow.db", "./mlartifacts"]
    assert all(volumen["read_only"] and volumen["bind"] == {"create_host_path": False}
               for volumen in servicios["registro"]["volumes"] if isinstance(volumen, dict))


def test_los_puertos_solo_se_publican_en_el_anfitrion_local(compose):
    puertos = [puerto for servicio in compose["services"].values() for puerto in servicio.get("ports", [])]
    assert len(puertos) == 2 and all(puerto.startswith("127.0.0.1:") for puerto in puertos)


def test_toda_variable_del_compose_tiene_valor_por_defecto_y_esta_en_env_example():
    texto = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")
    usadas = {coincidencia.group(1) for coincidencia in VARIABLE.finditer(texto)}
    assert usadas and all(coincidencia.group(2) for coincidencia in VARIABLE.finditer(texto))
    documentadas = {linea.split("=", 1)[0] for linea in (RAIZ / ".env.example").read_text(encoding="utf-8").splitlines()
                    if linea.strip() and not linea.startswith("#")}
    assert usadas == documentadas - {"MLFLOW_TRACKING_URI"}


def test_el_servidor_de_mlflow_usa_la_version_fijada_en_el_proyecto(compose):
    version = _version_fijada("servicios/mlflow/requirements.txt")
    assert version is not None
    assert version == _version_fijada("requirements.txt") == _version_fijada("requirements-api.txt")
    assert compose["services"]["mlflow"]["image"] == f"mibici-mlflow:{version}"
    contenedor = (RAIZ / "servicios" / "mlflow" / "Containerfile").read_text(encoding="utf-8")
    assert "USER registro" in contenedor and "HEALTHCHECK" in contenedor


def test_el_generador_de_carga_ataca_al_servicio_por_la_red_interna(compose):
    locust = compose["services"]["locust"]
    assert locust["depends_on"]["api"] == {"condition": "service_healthy"}
    assert locust["command"][locust["command"].index("--host") + 1] == "http://api:8000"
    assert "--headless" in locust["command"] and "--html" in locust["command"] and "--csv" in locust["command"]
    assert "./carga:/mnt/carga:ro" in locust["volumes"] and "ports" not in locust


def test_el_makefile_tiene_los_objetivos_del_sistema():
    makefile = (RAIZ / "Makefile").read_text(encoding="utf-8")
    assert [objetivo for objetivo in OBJETIVOS if f"\n.PHONY: {objetivo}\n{objetivo}:" not in makefile] == []
    assert "compose up --build --wait" in makefile


def test_importar_copia_la_base_y_los_artefactos_y_resume_el_registry(tmp_path):
    importar = _importar()
    origen = tmp_path / "origen"
    (origen / "mlartifacts" / "1" / "models").mkdir(parents=True)
    (origen / "mlartifacts" / "1" / "models" / "model.skops").write_bytes(b"x" * 10)
    _base_de_prueba(origen / "mlflow.db")
    base, artefactos = tmp_path / "datos" / "mlflow.db", tmp_path / "artefactos"
    (corridas, versiones, alias), archivos, tamano = importar.importar(origen, base, artefactos)
    assert (corridas, versiones, archivos, tamano) == (2, 2, 1, 10)
    assert alias == [("mibici-equipo38-p2-riesgo", "champion", 1)]
    assert base.is_file() and not base.with_suffix(".importando").exists()
    assert (artefactos / "1" / "models" / "model.skops").read_bytes() == b"x" * 10
    assert importar.importar(origen, base, artefactos)[1] == 1


def test_importar_avisa_si_el_clon_no_tiene_registry(tmp_path):
    importar = _importar()
    with pytest.raises(FileNotFoundError, match="mlflow.db"):
        importar.importar(tmp_path, tmp_path / "mlflow.db", tmp_path / "artefactos")
    assert not (tmp_path / "mlflow.db").exists()


def test_docker_compose_acepta_el_archivo_con_todos_los_perfiles():
    docker = shutil.which("docker")
    if docker is None or subprocess.run([docker, "compose", "version"], capture_output=True).returncode != 0:
        pytest.skip("docker compose no está disponible")
    orden = [docker, "compose", "-f", str(RAIZ / "docker-compose.yml"), "--profile", "registro", "--profile", "siembra",
             "--profile", "carga", "config", "--services"]
    resultado = subprocess.run(orden, capture_output=True, text=True, cwd=RAIZ)
    assert resultado.returncode == 0, resultado.stderr
    assert sorted(resultado.stdout.split()) == ["api", "locust", "mlflow", "registro", "siembra"]
