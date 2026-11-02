"""Busca contraseñas, tokens, llaves y cadenas sospechosas en el historial completo de Git y en los archivos versionados."""
import argparse
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
URL = re.compile(r"https?://[^\s\"'<>)\]]+")
REFERENCIAS = ("os.environ", "os.getenv", "$", "%", "<", "{")
PATRONES = {
    "contraseñas": re.compile(r"(password|passwd|contrasena|contraseña)\s*[=:]\s*[\"']?([^\s\"']{4,})", re.IGNORECASE),
    "tokens y llaves de API": re.compile(r"(api[_-]?key|apikey|secret[_-]?key|client[_-]?secret|access[_-]?token|auth[_-]?token|token|bearer)"
                                         r"\s*[=:]\s*[\"']?(?=[^\s\"']*\d)([A-Za-z0-9_\-./+=]{8,})", re.IGNORECASE),
    "llaves de proveedores": re.compile(r"AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,}"
                                        r"|AIza[0-9A-Za-z_\-]{35}|xox[baprs]-[A-Za-z0-9\-]{10,}|sk-[A-Za-z0-9_\-]{20,}|hf_[A-Za-z0-9]{30,}"),
    "llaves privadas": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY( BLOCK)?-----"),
    "URL con credenciales": re.compile(r"[a-z][a-z0-9+.\-]*://[^/\s:@]+:[^/\s@]+@"),
    "cadenas largas": re.compile(r"[A-Za-z0-9+/]{40,}={0,2}"),
}
HEXADECIMAL_64 = re.compile(r"[0-9a-f]{64}")
ZLIB_BASE64 = re.compile(r"e[AFJN]")


def leer_argumentos():
    parser = argparse.ArgumentParser(description="Busca secretos en el historial de Git y en los archivos versionados del repositorio.")
    parser.add_argument("--salida", default="",
                        help="archivo donde además se guarda el resumen, por ejemplo reports/seguridad/secretos.txt")
    return parser.parse_args()


def ejecutar(git, *argumentos):
    """Corre git en la raíz del repositorio y devuelve su salida como texto."""
    resultado = subprocess.run([git, *argumentos], capture_output=True, check=True, cwd=RAIZ)
    return resultado.stdout.decode("utf-8", errors="replace")


def lista_blanca(ruta, linea, cadena):
    """Motivo por el que una cadena larga se acepta; None cuando no hay motivo."""
    if ruta == "data/manifiesto.json" and "\"sha256\"" in linea and HEXADECIMAL_64.fullmatch(cadena):
        return "sumas SHA-256 del manifiesto de datos"
    if ruta.endswith(".ipynb") and cadena.startswith("iVBORw0KGgo"):
        return "imágenes PNG de las salidas de la libreta"
    if ruta.startswith("reports/deepchecks/") and ruta.endswith(".json") and ZLIB_BASE64.match(cadena):
        return "tablas comprimidas de los reportes de DeepChecks"
    return None


def revisar_linea(ruta, linea):
    """Categorías de secreto presentes en una línea y motivos de lista blanca de sus cadenas largas."""
    hallazgos, permitidas = [], []
    for categoria in ("contraseñas", "tokens y llaves de API"):
        for coincidencia in PATRONES[categoria].finditer(linea):
            if not coincidencia.group(2).startswith(REFERENCIAS):
                hallazgos.append(categoria)
    for categoria in ("llaves de proveedores", "llaves privadas", "URL con credenciales"):
        if PATRONES[categoria].search(linea):
            hallazgos.append(categoria)
    for coincidencia in PATRONES["cadenas largas"].finditer(URL.sub("", linea)):
        motivo = lista_blanca(ruta, linea, coincidencia.group())
        if motivo is None:
            hallazgos.append("cadenas largas")
        else:
            permitidas.append(motivo)
    return hallazgos, permitidas


def lineas_del_historial(git):
    """Líneas agregadas en todos los commits de todas las ramas, con el commit y el archivo al que pertenecen."""
    commit, archivo, previa = "", "", ""
    for linea in ejecutar(git, "log", "--no-color", "-p", "--all", "--format=commit %H").splitlines():
        if linea.startswith("commit ") and len(linea) == 47:
            commit = linea[7:14]
        elif linea.startswith("+++ ") and previa.startswith("--- "):
            archivo = linea[6:] if linea.startswith("+++ b/") else ""
        elif linea.startswith("+"):
            yield commit, archivo, linea[1:]
        previa = linea


def archivos_versionados(git):
    """Archivos versionados con sus líneas de texto; None en los binarios."""
    for ruta in ejecutar(git, "ls-files", "-z").split("\0"):
        archivo = RAIZ / ruta
        if not ruta or not archivo.is_file():
            continue
        contenido = archivo.read_bytes()
        if b"\0" in contenido[:8192]:
            yield ruta, None
        else:
            yield ruta, contenido.decode("utf-8", errors="replace").splitlines()


def main():
    args = leer_argumentos()
    git = shutil.which("git")
    if git is None:
        raise SystemExit("git no está disponible en el PATH")
    conteos = {categoria: [0, 0] for categoria in PATRONES}
    permitidas = {}
    detalles = []
    lineas_historial = 0
    for commit, archivo, linea in lineas_del_historial(git):
        lineas_historial += 1
        hallazgos, motivos = revisar_linea(archivo, linea)
        for categoria in hallazgos:
            conteos[categoria][0] += 1
            detalles.append(f"historial, commit {commit}, {archivo}: {categoria}")
        for motivo in motivos:
            permitidas.setdefault(motivo, [0, 0])[0] += 1
    total, binarios = 0, 0
    for ruta, lineas in archivos_versionados(git):
        total += 1
        if lineas is None:
            binarios += 1
            continue
        for numero, linea in enumerate(lineas, start=1):
            hallazgos, motivos = revisar_linea(ruta, linea)
            for categoria in hallazgos:
                conteos[categoria][1] += 1
                detalles.append(f"archivo {ruta}:{numero}: {categoria}")
            for motivo in motivos:
                permitidas.setdefault(motivo, [0, 0])[1] += 1
    commits = ejecutar(git, "rev-list", "--all", "--count").strip()
    actual = ejecutar(git, "rev-parse", "--short", "HEAD").strip()
    rama = ejecutar(git, "rev-parse", "--abbrev-ref", "HEAD").strip()
    renglones = [
        "Búsqueda de secretos en el repositorio",
        "Fecha: " + datetime.now().strftime("%Y-%m-%d %H:%M") + " (hora local)",
        f"Commit: {actual} ({rama})",
        f"Historial: {commits} commits en todas las ramas, {lineas_historial} líneas agregadas revisadas",
        f"Archivos versionados: {total}, {total - binarios} de texto revisados línea por línea y {binarios} binarios omitidos",
    ]
    for categoria, (en_historial, en_archivos) in conteos.items():
        renglones.append(f"{categoria}: {en_historial} en el historial, {en_archivos} en los archivos")
    for motivo, (en_historial, en_archivos) in permitidas.items():
        renglones.append(f"lista blanca, {motivo}: {en_historial} en el historial, {en_archivos} en los archivos")
    if detalles:
        renglones.append(f"Resultado: {len(detalles)} hallazgos por revisar")
        renglones.extend("  " + detalle for detalle in detalles)
    else:
        renglones.append("Resultado: sin secretos en el historial ni en los archivos versionados")
    texto = "\n".join(renglones) + "\n"
    print(texto, end="")
    if args.salida:
        destino = Path(args.salida)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(texto, encoding="utf-8")
    return 1 if detalles else 0


if __name__ == "__main__":
    sys.exit(main())
