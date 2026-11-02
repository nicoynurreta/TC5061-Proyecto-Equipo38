import re
import shutil
import subprocess

import pytest

from mibici import config

ENTRADAS_GITIGNORE = ["data/raw/*", "data/interim/*", "data/processed/*", "*.csv", "*.parquet", "mlruns/",
                      "mlartifacts/", "mlflow.db", "models/*", "*.pkl", "*.joblib", ".env"]
RUTAS_IGNORADAS = ["data/raw/datos_abiertos_2025_01.csv", "data/processed/viajes.parquet", "mlruns/0/meta.yaml",
                   "mlartifacts/1/modelo/model.pkl", "mlflow.db", "models/predicciones_p1.csv", "modelo.joblib", ".env"]
EXTENSIONES_FUERA = (".csv", ".parquet", ".pkl", ".joblib", ".skops", ".db", ".env")
URL = re.compile(r"https?://[^\s\"'<>)\]]+")
REFERENCIAS = ("os.environ", "os.getenv", "$", "%", "<", "{")
PATRONES = {
    "contrasenas": re.compile(r"(password|passwd|contrasena|contraseña)\s*[=:]\s*[\"']?([^\s\"']{4,})", re.IGNORECASE),
    "tokens": re.compile(r"(api[_-]?key|apikey|secret[_-]?key|client[_-]?secret|access[_-]?token|auth[_-]?token|token|bearer)"
                         r"\s*[=:]\s*[\"']?(?=[^\s\"']*\d)([A-Za-z0-9_\-./+=]{8,})", re.IGNORECASE),
    "llaves_de_proveedores": re.compile(r"AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,}"
                                        r"|AIza[0-9A-Za-z_\-]{35}|xox[baprs]-[A-Za-z0-9\-]{10,}|sk-[A-Za-z0-9_\-]{20,}|hf_[A-Za-z0-9]{30,}"),
    "llaves_privadas": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY( BLOCK)?-----"),
    "url_con_credenciales": re.compile(r"[a-z][a-z0-9+.\-]*://[^/\s:@]+:[^/\s@]+@"),
}
CADENA_LARGA = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")
HEXADECIMAL_64 = re.compile(r"[0-9a-f]{64}")
ZLIB_BASE64 = re.compile(r"e[AFJN]")


def _git(*argumentos):
    ejecutable = shutil.which("git")
    if ejecutable is None:
        pytest.skip("git no está disponible")
    resultado = subprocess.run([ejecutable, *argumentos], capture_output=True, cwd=config.RAIZ_PROYECTO)
    return resultado.returncode, resultado.stdout.decode("utf-8", errors="replace")


def _archivos_versionados():
    codigo, salida = _git("ls-files", "-z")
    if codigo != 0:
        pytest.skip("la raíz del proyecto no es un repositorio de git")
    return [ruta for ruta in salida.split("\0") if ruta]


def _lineas_de_texto(ruta):
    archivo = config.RAIZ_PROYECTO / ruta
    if not archivo.is_file():
        return []
    contenido = archivo.read_bytes()
    if b"\0" in contenido[:8192]:
        return []
    return contenido.decode("utf-8", errors="replace").splitlines()


def _permitida(ruta, linea, cadena):
    if ruta == "data/manifiesto.json":
        return "\"sha256\"" in linea and HEXADECIMAL_64.fullmatch(cadena) is not None
    if ruta.endswith(".ipynb"):
        return cadena.startswith("iVBORw0KGgo")
    return ruta.startswith("reports/deepchecks/") and ruta.endswith(".json") and ZLIB_BASE64.match(cadena) is not None


def _categorias(ruta, linea):
    encontradas = []
    for nombre in ("contrasenas", "tokens"):
        for coincidencia in PATRONES[nombre].finditer(linea):
            if not coincidencia.group(2).startswith(REFERENCIAS):
                encontradas.append(nombre)
    for nombre in ("llaves_de_proveedores", "llaves_privadas", "url_con_credenciales"):
        if PATRONES[nombre].search(linea):
            encontradas.append(nombre)
    for coincidencia in CADENA_LARGA.finditer(URL.sub("", linea)):
        if not _permitida(ruta, linea, coincidencia.group()):
            encontradas.append("cadena_larga")
    return encontradas


def test_gitignore_excluye_datos_modelos_mlflow_y_entorno():
    lineas = [linea.strip() for linea in (config.RAIZ_PROYECTO / ".gitignore").read_text(encoding="utf-8").splitlines()]
    assert [entrada for entrada in ENTRADAS_GITIGNORE if entrada not in lineas] == []


def test_git_ignora_las_rutas_de_datos_modelos_y_entorno():
    assert [ruta for ruta in RUTAS_IGNORADAS if _git("check-ignore", "-q", ruta)[0] != 0] == []


def test_env_example_documenta_la_variable_de_tracking():
    ejemplo = config.RAIZ_PROYECTO / ".env.example"
    assert ejemplo.is_file()
    variables = [linea.split("=", 1)[0] for linea in ejemplo.read_text(encoding="utf-8").splitlines()
                 if linea.strip() and not linea.startswith("#")]
    assert "MLFLOW_TRACKING_URI" in variables


def test_ningun_dato_modelo_ni_env_esta_versionado():
    versionados = _archivos_versionados()
    assert [ruta for ruta in versionados if ruta.endswith(EXTENSIONES_FUERA)] == []
    assert "mlflow.db" not in versionados and ".env" not in versionados


def test_archivos_versionados_sin_secretos():
    hallazgos = []
    for ruta in _archivos_versionados():
        for numero, linea in enumerate(_lineas_de_texto(ruta), start=1):
            hallazgos.extend((ruta, numero, categoria) for categoria in _categorias(ruta, linea))
    assert hallazgos == []
