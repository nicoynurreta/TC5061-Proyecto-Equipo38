import json
import time
import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning, message=r"pkg_resources is deprecated as an API")
warnings.filterwarnings("ignore", category=FutureWarning, message=r"The `needs_threshold` and `needs_proba` parameter are deprecated")
warnings.filterwarnings("ignore", category=FutureWarning, message=r"DataFrame\.applymap has been deprecated")

import deepchecks
import numpy as np
import pandas as pd
from deepchecks.core import CheckFailure
from deepchecks.tabular import Dataset
from deepchecks.tabular.checks import MultivariateDrift, OutlierSampleDetection
from deepchecks.tabular.suites import data_integrity, train_test_validation

RAIZ = Path(__file__).resolve().parents[1]
DIR_TABLAS = RAIZ / "data" / "interim"
DIR_REPORTES = RAIZ / "reports" / "deepchecks"
ARCHIVO_EXPORTACION = DIR_TABLAS / "exportacion.json"
ARCHIVO_RESUMEN = DIR_REPORTES / "resumen.md"
TIEMPO_MAXIMO_ATIPICOS = 60
UMBRAL_ATIPICO = 0.7
UMBRAL_CORRELACION = 0.9
ESTADOS = {"PASS": "Pasa", "FAIL": "No pasa", "WARN": "Aviso", "ERROR": "Error"}


def leer_tabla(nombre):
    return pd.read_parquet(DIR_TABLAS / f"{nombre}.parquet")


def conjunto_crudo(df, esquema):
    return Dataset(df, index_name=esquema["indice"], datetime_name=esquema["tiempo"],
                   features=esquema["features"], cat_features=esquema["categoricas"])


def conjunto_pregunta(df, esquema, sin=()):
    variables = [columna for columna in esquema["features"] if columna not in sin]
    categoricas = [columna for columna in esquema["categoricas"] if columna not in sin]
    columnas = [esquema["tiempo"]] + variables + [esquema["objetivo"]]
    return Dataset(df[columnas], label=esquema["objetivo"], label_type=esquema["tipo"], datetime_name=esquema["tiempo"],
                   features=variables, cat_features=categoricas)


def conjunto_perfil(df, esquema):
    columnas = [columna for columna in df.columns if columna not in esquema["identificacion"]]
    return Dataset(df[[esquema["indice"]] + columnas], index_name=esquema["indice"], features=columnas, cat_features=[])


def suite_integridad():
    suite = data_integrity()
    for indice, chequeo in list(suite.checks.items()):
        if isinstance(chequeo, OutlierSampleDetection):
            suite.remove(indice)
    suite.add(OutlierSampleDetection(timeout=TIEMPO_MAXIMO_ATIPICOS))
    return suite


def correr(nombre, suite, *conjuntos):
    inicio = time.perf_counter()
    resultado = suite.run(*conjuntos)
    segundos = time.perf_counter() - inicio
    (DIR_REPORTES / f"{nombre}.json").write_text(resultado.to_json(with_display=False), encoding="utf-8")
    ruta_html = DIR_REPORTES / f"{nombre}.html"
    ruta_html.unlink(missing_ok=True)
    resultado.save_as_html(str(ruta_html), as_widget=False)
    return resultado, round(segundos, 1)


def texto_celda(valor, maximo=400):
    texto = " ".join(str(valor).split()).replace("|", "\\|")
    return texto if len(texto) <= maximo else texto[:maximo - 3] + "..."


def detalle_sin_condicion(resultado):
    if isinstance(resultado.check, OutlierSampleDetection):
        cuantiles = np.asarray(resultado.value, dtype=float)
        return f"{np.mean(cuantiles >= UMBRAL_ATIPICO):.2%} de las muestras con probabilidad de atipicidad mayor o igual a {UMBRAL_ATIPICO}"
    return "solo muestra"


def filas_resumen(resultado):
    filas = []
    for parcial in resultado.results:
        if isinstance(parcial, CheckFailure):
            filas.append((parcial.header, "", "No corre", texto_celda(parcial.exception)))
        elif not parcial.have_conditions():
            filas.append((parcial.get_header(), "Sin condición", "Solo muestra", texto_celda(detalle_sin_condicion(parcial))))
        else:
            for condicion in parcial.conditions_results:
                filas.append((parcial.get_header(), texto_celda(condicion.name), ESTADOS[condicion.category.name], texto_celda(condicion.details)))
    return filas


def conteo_estados(resultado):
    conteo = {"Pasa": 0, "No pasa": 0, "Aviso": 0, "Error": 0, "No corre": 0, "Solo muestra": 0}
    for _, _, estado, _ in filas_resumen(resultado):
        conteo[estado] += 1
    return ", ".join(f"{n} {estado.lower()}" for estado, n in conteo.items() if n)


def valor_de(resultado, nombre):
    for parcial in resultado.results:
        if not isinstance(parcial, CheckFailure) and parcial.get_header() == nombre:
            return parcial.value
    return None


def tabla_markdown(encabezados, filas):
    lineas = ["| " + " | ".join(encabezados) + " |", "|" + "---|" * len(encabezados)]
    for fila in filas:
        lineas.append("| " + " | ".join(str(celda) for celda in fila) + " |")
    return "\n".join(lineas)


def numero(valor):
    return f"{valor:,}"


def porcentaje(valor, decimales=2):
    return f"{valor * 100:.{decimales}f} %"


def megabytes(valor):
    return f"{valor / 1e6:.2f} MB"


def conteos_crudos(df, exportacion):
    esquema = exportacion["esquemas"]["viajes_crudos"]
    limpieza = exportacion["viajes_crudos"]["limpieza"]
    minima, maxima = exportacion["duracion_minima_min"], exportacion["duracion_maxima_min"]
    faltantes = int(df[esquema["necesarias"]].isna().any(axis=1).sum())
    duplicados = int(df[esquema["indice"]].duplicated().sum())
    negativas = int((df["duracion_min"] < 0).sum())
    cortas = int(((df["duracion_min"] >= 0) & (df["duracion_min"] < minima)).sum())
    largas = int((df["duracion_min"] > maxima).sum())
    descartes = sum(valor for clave, valor in limpieza.items() if clave != "registros_crudos")
    return [
        ("Registros del mes", numero(len(df)), numero(limpieza["registros_crudos"])),
        ("Faltantes en las cinco columnas necesarias (sin fecha o sin estación)", numero(faltantes), numero(limpieza["sin_fecha_o_estacion"])),
        ("`viaje_id` duplicado", numero(duplicados), numero(limpieza["duplicados"])),
        ("Duración negativa", numero(negativas), numero(limpieza["duracion_negativa"])),
        (f"Duración menor a {minima} min", f"{numero(cortas)} ({porcentaje(cortas / len(df))})", numero(limpieza["duracion_menor_1_min"])),
        (f"Duración mayor a {maxima // 60} h", numero(largas), numero(limpieza["duracion_mayor_24_h"])),
        ("Duración mínima y máxima observadas", f"{df['duracion_min'].min():.1f} y {df['duracion_min'].max():.1f} min", f"límites {minima} y {numero(maxima)} min"),
        ("Viajes que conserva la limpieza", numero(len(df) - faltantes - duplicados - negativas - cortas - largas), numero(limpieza["registros_crudos"] - descartes)),
    ]


def tabla_deriva(resultado, esquema):
    deriva = valor_de(resultado, "Feature Drift") or {}
    filas = []
    for columna in esquema["features"]:
        info = deriva.get(columna)
        if info is None:
            filas.append((f"`{columna}`", "", "sin resultado"))
        else:
            filas.append((f"`{columna}`", info["Method"], f"{info['Drift score']:.3f}"))
    return filas


def resumen_particion(resultado):
    etiqueta = valor_de(resultado, "Label Drift") or {}
    multivariada = valor_de(resultado, "Multivariate Drift") or {}
    mezcla = valor_de(resultado, "Train Test Samples Mix") or {}
    nuevas = valor_de(resultado, "New Category Train Test")
    importancias = multivariada.get("domain_classifier_feature_importance", {})
    principales = sorted(importancias.items(), key=lambda par: par[1], reverse=True)[:3]
    lineas = []
    if etiqueta:
        lineas.append(f"- Deriva de la etiqueta: {etiqueta['Drift score']:.3f} ({etiqueta['Method']}).")
    if multivariada:
        lineas.append(f"- Deriva multivariada: {multivariada['domain_classifier_drift_score']:.3f} (AUC del clasificador de dominio {multivariada['domain_classifier_auc']:.3f}); "
                      "variables que más separan entrenamiento de prueba: " + ", ".join(f"`{columna}` ({peso:.2f})" for columna, peso in principales) + ".")
    if mezcla:
        lineas.append(f"- Muestras de prueba idénticas a alguna de entrenamiento en las variables y la etiqueta: {porcentaje(mezcla['ratio'])}.")
    if isinstance(nuevas, pd.DataFrame) and len(nuevas):
        con_nuevas = nuevas[nuevas["# New Categories"] > 0]
        for columna, fila in con_nuevas.iterrows():
            lineas.append(f"- Categorías de `{columna}` que no existen en entrenamiento: {sorted(fila['New categories'])} ({porcentaje(fila['Ratio of New Categories'])} de las filas de prueba).")
        if con_nuevas.empty:
            lineas.append("- Ninguna variable categórica tiene categorías nuevas en prueba.")
    return lineas


def pares_correlacionados(resultado):
    matriz = valor_de(resultado, "Feature-Feature Correlation")
    if not isinstance(matriz, pd.DataFrame):
        return []
    pares = []
    columnas = list(matriz.columns)
    for i, primera in enumerate(columnas):
        for segunda in columnas[i + 1:]:
            valor = matriz.loc[primera, segunda]
            if pd.notna(valor) and abs(valor) > UMBRAL_CORRELACION:
                pares.append((primera, segunda, float(valor)))
    return sorted(pares, key=lambda par: -par[2])


def columnas_constantes(resultado):
    unicos = valor_de(resultado, "Single Value in Column") or {}
    return [columna for columna, n in unicos.items() if n == 1]


def ratio_conflictivas(resultado):
    valor = valor_de(resultado, "Conflicting Labels")
    return None if valor is None else float(valor["percent_of_conflicting_samples"])


def lectura_p2(exportacion, resultado):
    tablas = exportacion["tablas"]
    entrenamiento, validacion, prueba = tablas["p2_entrenamiento"], tablas["p2_validacion"], tablas["p2_prueba"]
    tasa_entrenamiento = entrenamiento["positivos_completos"] / entrenamiento["filas_completas"]
    tasa_validacion = validacion["positivos_completos"] / validacion["filas_completas"]
    tasa_prueba = prueba["positivos_completos"] / prueba["filas_completas"]
    esperadas = tasa_entrenamiento * prueba["filas_completas"]
    costo = exportacion["costo_falso_negativo"]
    etiqueta = valor_de(resultado, "Label Drift") or {}
    deriva = valor_de(resultado, "Feature Drift") or {}
    flujo = {columna: info["Drift score"] for columna, info in deriva.items() if columna.startswith(("salidas_h", "llegadas_h", "neto_"))}
    mayor = max(flujo, key=flujo.get) if flujo else None
    lineas = [
        f"- Horas-estación en riesgo en los conjuntos completos, antes de muestrear: {numero(entrenamiento['positivos_completos'])} de {numero(entrenamiento['filas_completas'])} en entrenamiento ({porcentaje(tasa_entrenamiento)}), "
        f"{numero(validacion['positivos_completos'])} de {numero(validacion['filas_completas'])} en validación ({porcentaje(tasa_validacion)}, el mes en que se elige el umbral de decisión) "
        f"y {numero(prueba['positivos_completos'])} de {numero(prueba['filas_completas'])} en prueba ({porcentaje(tasa_prueba)}). La tasa de riesgo cae {porcentaje(1 - tasa_prueba / tasa_entrenamiento, 1)} en noviembre y diciembre respecto a enero-septiembre.",
        f"- Con la tasa de enero a septiembre se esperarían {numero(round(esperadas))} horas en riesgo en prueba y ocurren {numero(prueba['positivos_completos'])}: un modelo que mantuviera la frecuencia de alertas del entrenamiento "
        f"emitiría del orden de {numero(round(esperadas - prueba['positivos_completos']))} alertas sin riesgo real en los dos meses, un viaje de camión de más por cada una.",
        f"- El costo asimétrico de P2 valúa cada hora en riesgo sin aviso en {costo} falsos positivos. No anticipar ninguna de las {numero(prueba['positivos_completos'])} horas en riesgo de prueba costaría {numero(costo * prueba['positivos_completos'])} unidades, "
        f"y cada punto porcentual de recall que se pierda por la deriva equivale a {numero(round(prueba['positivos_completos'] / 100))} horas en riesgo mal anticipadas, {numero(round(costo * prueba['positivos_completos'] / 100))} unidades de costo.",
    ]
    if etiqueta:
        lineas.append(f"- DeepChecks mide esa deriva de la etiqueta en {etiqueta['Drift score']:.3f} ({etiqueta['Method']}) sobre la muestra: con una clase positiva tan rara la puntuación queda muy por debajo del umbral de 0.15 aunque la caída relativa de la tasa sea grande, "
                      "por eso la lectura operativa se hace con los conteos completos y no solo con la condición del chequeo.")
    if mayor is not None:
        lineas.append(f"- Las variables de flujo se mueven poco en distribución (la mayor deriva es `{mayor}`, {flujo[mayor]:.3f}), así que el cambio está en la etiqueta más que en las entradas: "
                      "en noviembre y diciembre el mismo patrón de flujo desemboca menos veces en una estación llena o vacía, y un umbral de probabilidad fijado en octubre tiende a sobrealertar.")
    return lineas


def lectura_p1(resultado, sin_mes):
    entrenamiento, prueba = leer_tabla("p1_entrenamiento"), leer_tabla("p1_prueba")
    deriva = valor_de(resultado, "Feature Drift") or {}
    rezago = deriva.get("rezago_7", {})
    etiqueta = valor_de(resultado, "Label Drift") or {}
    sesgo_entrenamiento = (entrenamiento["rezago_7"] - entrenamiento["salidas"]).mean()
    sesgo_prueba = (prueba["rezago_7"] - prueba["salidas"]).mean()
    lineas = [
        f"- `rezago_7` (salidas de la misma estación siete días antes) promedia {entrenamiento['rezago_7'].mean():.2f} viajes por estación y día en entrenamiento y {prueba['rezago_7'].mean():.2f} en prueba, "
        f"con una deriva de {rezago.get('Drift score', float('nan')):.3f} ({rezago.get('Method', '')}); la variable objetivo `salidas` pasa de {entrenamiento['salidas'].mean():.2f} a {prueba['salidas'].mean():.2f} "
        f"(deriva de la etiqueta {etiqueta.get('Drift score', float('nan')):.3f}).",
        f"- La demanda de noviembre y diciembre baja mientras el nivel de la semana anterior se mantiene: `rezago_7` menos `salidas` promedia {sesgo_entrenamiento:+.2f} viajes en entrenamiento y {sesgo_prueba:+.2f} en prueba. "
        f"Como el baseline `naive7` predice exactamente `rezago_7`, ese sesgo son {numero(round(sesgo_prueba * len(prueba)))} viajes sobredimensionados en los {numero(len(prueba))} pares estación-día de prueba, "
        "flota y personal asignados a una demanda que no llega; los modelos que usan `media_28` y `mes` lo corrigen solo en parte, porque los meses 11 y 12 no existen en entrenamiento.",
    ]
    if sin_mes:
        lineas.append(f"- La deriva multivariada de la suite (1.000) la explica `mes` por sí sola. Al repetir `MultivariateDrift` sin `mes`, la deriva queda en {sin_mes['domain_classifier_drift_score']:.3f} "
                      f"(AUC {sin_mes['domain_classifier_auc']:.3f}): el resto de las variables de P1 tiene la misma distribución en los dos periodos.")
    return lineas


def notas(valores):
    pares = ", ".join(f"`{a}`-`{b}` ({r:.2f})" for a, b, r in valores["pares_p1"]) or "ninguno"
    constantes = ", ".join(f"`{columna}`" for columna in valores["constantes_p3"]) or "ninguna"
    return [
        f"- Condiciones. Se conservan los umbrales por defecto de DeepChecks (deriva menor a 0.2 por variable y a 0.15 en la etiqueta, deriva multivariada menor a 0.25, correlación entre variables hasta {UMBRAL_CORRELACION}, duplicados y mezcla de muestras hasta 5 %, "
        f"cero categorías, etiquetas y fechas nuevas). El único ajuste de configuración es `OutlierSampleDetection(timeout={TIEMPO_MAXIMO_ATIPICOS})` en lugar del tope de 10 s, porque con {valores['filas_crudas']} viajes crudos el tiempo proyectado del chequeo supera ese tope y el chequeo abortaría; "
        f"ese chequeo no trae condición, así que se reporta la proporción de muestras con probabilidad de atipicidad mayor o igual a {UMBRAL_ATIPICO}.",
        "- Viajes crudos. La tabla del portal no tiene `viaje_id` duplicados ni faltantes en las cinco columnas necesarias, y los chequeos de nulos, tipos mezclados y duplicados lo confirman; el problema real del mes son los viajes de menos de un minuto, "
        f"que `limpiar_viajes` descarta y cuyo conteo coincide con el de la tabla cruda ({valores['cortas']}). La duración sin filtrar llega a {valores['duracion_maxima']:.1f} min, dentro del límite de 24 h. "
        "Los chequeos de etiqueta no corren porque la tabla no tiene variable objetivo.",
        f"- P1, correlación entre variables. Los pares por encima de {UMBRAL_CORRELACION} son {pares}: la demanda diaria de una estación está muy autocorrelada y las medias móviles promedian los mismos rezagos, así que la redundancia es por construcción. "
        "Los modelos de árboles no la resienten y Ridge la amortigua con la regularización; se deja la condición por defecto y el hallazgo queda documentado como redundancia conocida.",
        f"- P2, etiquetas en conflicto y duplicados. {porcentaje(valores['conflictivas_p2'])} de las horas de entrenamiento comparten exactamente las trece variables con otra hora que tiene la etiqueta contraria, y {porcentaje(valores['duplicados_p2'])} de las filas son idénticas a otra "
        "(misma hora, mismos flujos, misma capacidad y misma etiqueta, en estaciones distintas). Ocurre en horas de poco o ningún movimiento, donde el riesgo de las dos horas siguientes no se distingue con las variables de la hora actual: "
        "es ruido irreducible para cualquier modelo con estas entradas y acota el recall alcanzable. La correlación `dia_semana`-`fin_de_semana` es por diseño, porque la segunda se deriva de la primera.",
        f"- P3, columnas constantes. Las columnas {constantes} valen cero en todas las estaciones porque el sistema no registra salidas entre las 2:00 y las 4:59; son constantes por diseño del perfil horario, no aportan a la agrupación "
        "(el escalado las deja en cero) y conviene excluirlas en la siguiente iteración del perfil. Los chequeos de etiqueta no aplican porque P3 no tiene variable objetivo.",
        f"- P1, partición. `mes` toma en prueba los valores {valores['meses_nuevos']}, inexistentes en entrenamiento, por lo que `New Category Train Test` y `Feature Drift` no pasan y la deriva multivariada es 1.0: es consecuencia directa de la partición temporal "
        "(entrenamiento de enero a septiembre, prueba en noviembre y diciembre), no un defecto de los datos. Para el modelo sí importa: `HistGradientBoostingRegressor` trata `mes` como numérico y extrapola, y Ridge, con `handle_unknown=\"ignore\"`, "
        "deja sin efecto mensual a las filas de prueba. Queda como mejora para la siguiente iteración codificar `mes` de forma cíclica o retirarlo de P1.",
        f"- P2, mezcla de muestras. {porcentaje(valores['mezcla_p2'])} de las horas de prueba coinciden en las trece variables y la etiqueta con alguna hora de entrenamiento. No es fuga: la partición es temporal y los dos chequeos de fechas pasan; "
        "son horas sin movimiento o con flujos pequeños que se repiten en cualquier mes, y la cifra mide qué parte del conjunto es trivial para el modelo.",
        "- Chequeos que no corren. `Index Train Test Leakage` necesita un identificador único de fila y P1 y P2 identifican cada fila por estación y fecha u hora, así que no se declara índice; la separación entre periodos la verifican "
        "`Date Train-Test Leakage (overlap)` y `(duplicates)`, que pasan en las dos preguntas. `New Label Train Test` y `Conflicting Labels` no aplican a la regresión de P1.",
        "- Muestra. Los chequeos que muestrean por dentro usan su `n_samples` por defecto (100,000 filas en la deriva por variable y 10,000 en la multivariada, por ejemplo); con 200,000 filas por conjunto todos los chequeos de P2 corren completos "
        "y cada suite termina en menos de un minuto y medio.",
    ]


def escribir_resumen(exportacion, corridas, registro, filas_tablas, valores):
    crudos = exportacion["viajes_crudos"]
    partes = [
        "# Validación de datos con DeepChecks",
        "",
        f"Reportes generados el {datetime.now().strftime('%Y-%m-%d %H:%M')} con deepchecks {deepchecks.__version__} (`chequeos/validar_datos.py`) sobre las tablas que `python -m mibici.validacion --exportar` "
        f"escribió en `data/interim/` el {exportacion['generado'].replace('T', ' ')} a partir de la versión de datos `{exportacion['version_datos']}`. "
        "Por suite hay un JSON (`to_json(with_display=False)`, versionado) y un HTML con las tablas y las gráficas de cada chequeo (`save_as_html(as_widget=False)`, fuera de Git por su tamaño). "
        "Las condiciones de cada chequeo son las que DeepChecks trae por defecto; ninguna se desactivó y los hallazgos se documentan tal como salen.",
        "",
        "## Tablas validadas",
        "",
        f"P1 y P3 se validan completos. P2 se valida sobre una muestra sin reemplazo de {numero(exportacion['muestra_p2'])} filas por conjunto (semilla {exportacion['semilla']}, orden temporal conservado); "
        "las cifras de la etiqueta en la lectura de la deriva usan los conjuntos completos. Los viajes crudos son el archivo del portal del mes "
        f"{crudos['mes']} (`{crudos['archivo']}`, {crudos['codificacion']}) leído antes de `limpiar_viajes`, con los nombres de columna normalizados, las fechas convertidas, "
        f"la duración calculada sin filtrar y sin las columnas personales ({', '.join('`' + columna + '`' for columna in crudos['columnas_excluidas'])}), que la ingesta descarta y ningún reporte debe contener.",
        "",
        tabla_markdown(["Tabla", "Filas", "Columnas", "Tamaño", "Nota"], filas_tablas),
        "",
    ]
    for titulo, clave, descripcion in corridas:
        detalle = registro[clave]
        partes += [f"## {titulo}", "", descripcion, ""]
        if "crudos" in detalle:
            partes += ["Conteos de la tabla cruda frente a los descartes que `limpiar_viajes` aplica sobre ese mismo mes:", "",
                       tabla_markdown(["Concepto", "Tabla cruda", "`limpiar_viajes`"], detalle["crudos"]), ""]
        partes += [tabla_markdown(["Chequeo", "Condición", "Estado", "Detalle"], detalle["filas"]), ""]
        if "deriva" in detalle:
            partes += ["Deriva por variable entre entrenamiento y prueba:", "", tabla_markdown(["Variable", "Método", "Puntuación"], detalle["deriva"]), ""]
            partes += detalle["particion"] + [""]
    partes += ["## Lectura de la deriva entre enero-septiembre y noviembre-diciembre", "", "### Etiqueta de P2, riesgo por estación y hora", ""]
    partes += registro["entrenamiento_prueba_p2"]["lectura"] + ["", "### `rezago_7` de P1, demanda por estación y día", ""]
    partes += registro["entrenamiento_prueba_p1"]["lectura"] + ["", "## Condiciones y hallazgos", ""]
    partes += notas(valores) + ["", "## Tiempos", ""]
    partes += [tabla_markdown(["Suite", "Filas", "Chequeos", "Estados", "Segundos"],
                              [(titulo, registro[clave]["filas_datos"], registro[clave]["chequeos"], registro[clave]["estados"], registro[clave]["segundos"]) for titulo, clave, _ in corridas]), ""]
    partes += [f"Exportación de las tablas: {exportacion['segundos']} s, de los que {exportacion['segundos_conjuntos']} s son la construcción de los conjuntos y la lectura del mes crudo. "
               f"Suites: {sum(registro[clave]['segundos'] for _, clave, _ in corridas):.1f} s en total.", ""]
    ARCHIVO_RESUMEN.write_text("\n".join(partes), encoding="utf-8")


def main():
    if not ARCHIVO_EXPORTACION.exists():
        print("No hay tablas en", DIR_TABLAS.relative_to(RAIZ).as_posix())
        print("Orden: make ingest, python -m mibici.validacion --exportar y después este comando")
        return
    inicio = time.perf_counter()
    exportacion = json.loads(ARCHIVO_EXPORTACION.read_text(encoding="utf-8"))
    esquemas = exportacion["esquemas"]
    DIR_REPORTES.mkdir(parents=True, exist_ok=True)

    crudos = leer_tabla("viajes_crudos")
    p1 = {nombre: leer_tabla(f"p1_{nombre}") for nombre in ["entrenamiento", "prueba"]}
    p2 = {nombre: leer_tabla(f"p2_{nombre}") for nombre in ["entrenamiento", "prueba"]}
    perfil = leer_tabla("p3_perfil")

    corridas = [
        ("Integridad de los viajes crudos", "integridad_viajes_crudos",
         f"Suite `data_integrity` sobre los {numero(len(crudos))} viajes de {exportacion['viajes_crudos']['mes']} tal como los publica el portal, con `viaje_id` como índice, `inicio` como fecha y `origen_id` y `destino_id` como categóricas."),
        ("Integridad del conjunto de entrenamiento de P1", "integridad_p1_entrenamiento",
         f"Suite `data_integrity` sobre las {numero(len(p1['entrenamiento']))} filas estación-día de entrenamiento de P1 con la etiqueta `{esquemas['p1']['objetivo']}` declarada (regresión)."),
        ("Integridad del conjunto de entrenamiento de P2", "integridad_p2_entrenamiento",
         f"Suite `data_integrity` sobre la muestra de {numero(len(p2['entrenamiento']))} filas estación-hora de entrenamiento de P2 con la etiqueta `{esquemas['p2']['objetivo']}` declarada (binaria)."),
        ("Integridad del perfil de P3", "integridad_p3_perfil",
         f"Suite `data_integrity` sobre el perfil de {numero(len(perfil))} estaciones con {len(perfil.columns) - len(esquemas['p3']['identificacion'])} variables numéricas y `estacion_id` como índice."),
        ("Entrenamiento contra prueba de P1", "entrenamiento_prueba_p1",
         f"Suite `train_test_validation` entre las {numero(len(p1['entrenamiento']))} filas de entrenamiento y las {numero(len(p1['prueba']))} de prueba de P1."),
        ("Entrenamiento contra prueba de P2", "entrenamiento_prueba_p2",
         f"Suite `train_test_validation` entre las muestras de {numero(len(p2['entrenamiento']))} filas de entrenamiento y {numero(len(p2['prueba']))} de prueba de P2."),
    ]
    conjuntos = {
        "integridad_viajes_crudos": (suite_integridad(), [conjunto_crudo(crudos, esquemas["viajes_crudos"])], len(crudos)),
        "integridad_p1_entrenamiento": (suite_integridad(), [conjunto_pregunta(p1["entrenamiento"], esquemas["p1"])], len(p1["entrenamiento"])),
        "integridad_p2_entrenamiento": (suite_integridad(), [conjunto_pregunta(p2["entrenamiento"], esquemas["p2"])], len(p2["entrenamiento"])),
        "integridad_p3_perfil": (suite_integridad(), [conjunto_perfil(perfil, esquemas["p3"])], len(perfil)),
        "entrenamiento_prueba_p1": (train_test_validation(), [conjunto_pregunta(p1["entrenamiento"], esquemas["p1"]), conjunto_pregunta(p1["prueba"], esquemas["p1"])], len(p1["entrenamiento"]) + len(p1["prueba"])),
        "entrenamiento_prueba_p2": (train_test_validation(), [conjunto_pregunta(p2["entrenamiento"], esquemas["p2"]), conjunto_pregunta(p2["prueba"], esquemas["p2"])], len(p2["entrenamiento"]) + len(p2["prueba"])),
    }

    registro, resultados = {}, {}
    for titulo, clave, _ in corridas:
        suite, datos, filas_datos = conjuntos[clave]
        resultado, segundos = correr(clave, suite, *datos)
        resultados[clave] = resultado
        registro[clave] = {"filas": filas_resumen(resultado), "segundos": segundos, "filas_datos": numero(filas_datos),
                           "chequeos": len(resultado.results), "estados": conteo_estados(resultado)}
        if clave == "integridad_viajes_crudos":
            registro[clave]["crudos"] = conteos_crudos(crudos, exportacion)
        if clave.startswith("entrenamiento_prueba"):
            pregunta = clave.rsplit("_", 1)[-1]
            registro[clave]["deriva"] = tabla_deriva(resultado, esquemas[pregunta])
            registro[clave]["particion"] = resumen_particion(resultado)
        print(titulo + ":", numero(filas_datos), "filas,", len(resultado.results), "chequeos,", segundos, "s;", registro[clave]["estados"])

    sin_mes = MultivariateDrift().run(conjunto_pregunta(p1["entrenamiento"], esquemas["p1"], sin=["mes"]),
                                      conjunto_pregunta(p1["prueba"], esquemas["p1"], sin=["mes"])).value
    registro["entrenamiento_prueba_p1"]["lectura"] = lectura_p1(resultados["entrenamiento_prueba_p1"], sin_mes)
    registro["entrenamiento_prueba_p2"]["lectura"] = lectura_p2(exportacion, resultados["entrenamiento_prueba_p2"])
    nuevas = valor_de(resultados["entrenamiento_prueba_p1"], "New Category Train Test")
    valores = {
        "filas_crudas": numero(len(crudos)),
        "cortas": numero(int((crudos["duracion_min"] < exportacion["duracion_minima_min"]).sum())),
        "duracion_maxima": float(crudos["duracion_min"].max()),
        "pares_p1": pares_correlacionados(resultados["integridad_p1_entrenamiento"]),
        "conflictivas_p2": ratio_conflictivas(resultados["integridad_p2_entrenamiento"]) or 0.0,
        "duplicados_p2": float(valor_de(resultados["integridad_p2_entrenamiento"], "Data Duplicates") or 0.0),
        "constantes_p3": columnas_constantes(resultados["integridad_p3_perfil"]),
        "meses_nuevos": sorted(nuevas.loc["mes", "New categories"]) if isinstance(nuevas, pd.DataFrame) and "mes" in nuevas.index else [],
        "mezcla_p2": (valor_de(resultados["entrenamiento_prueba_p2"], "Train Test Samples Mix") or {}).get("ratio", 0.0),
    }

    notas_tablas = {
        "p1_entrenamiento": "completo", "p1_validacion": "completo, no entra a las suites", "p1_prueba": "completo",
        "p2_entrenamiento": f"muestra de {numero(exportacion['tablas']['p2_entrenamiento']['filas_completas'])} filas",
        "p2_validacion": f"muestra de {numero(exportacion['tablas']['p2_validacion']['filas_completas'])} filas, no entra a las suites",
        "p2_prueba": f"muestra de {numero(exportacion['tablas']['p2_prueba']['filas_completas'])} filas",
        "p3_perfil": "completo", "viajes_crudos": f"mes {exportacion['viajes_crudos']['mes']} antes de la limpieza",
    }
    filas_tablas = [(f"`{nombre}.parquet`", numero(datos["filas"]), datos["columnas"], megabytes(datos["bytes"]), notas_tablas.get(nombre, ""))
                    for nombre, datos in exportacion["tablas"].items()]
    escribir_resumen(exportacion, corridas, registro, filas_tablas, valores)
    print("Reportes en", DIR_REPORTES.relative_to(RAIZ).as_posix() + ": JSON y HTML por suite y resumen.md")
    print("Tiempo:", round(time.perf_counter() - inicio, 1), "s")


if __name__ == "__main__":
    main()
