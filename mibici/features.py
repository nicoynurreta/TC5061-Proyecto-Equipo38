import numpy as np
import pandas as pd

from mibici import config

OBJETIVO_P1 = "salidas"
COLUMNAS_P1 = ["rezago_1", "rezago_7", "rezago_14", "media_7", "media_28", "dia_semana", "mes", "fin_de_semana", "capacidad"]
OBJETIVO_P2 = "riesgo"
COLUMNAS_P2 = ["salidas_h0", "llegadas_h0", "salidas_h1", "llegadas_h1", "salidas_h2", "llegadas_h2", "neto_3h",
               "neto_futuro_semana_anterior", "riesgo_semana_anterior", "hora_dia", "dia_semana", "fin_de_semana", "capacidad"]
CATEGORICAS_P2 = ["hora_dia", "dia_semana"]


def particion_temporal(df, columna, fin_entrenamiento=config.FIN_ENTRENAMIENTO, fin_validacion=config.FIN_VALIDACION):
    """Parte un DataFrame en entrenamiento, validación y prueba con dos fechas de corte.

    Los tres conjuntos son bloques consecutivos en el tiempo: entrenamiento hasta
    fin_entrenamiento, validación hasta fin_validacion y prueba de ahí en adelante.
    Así el modelo nunca se evalúa con un periodo anterior al que usó para aprender,
    que es la fuga de información que produciría una división aleatoria de registros
    que son series de tiempo por estación.
    """
    fecha = pd.to_datetime(df[columna])
    corte_entrenamiento = pd.Timestamp(fin_entrenamiento) + pd.Timedelta(days=1)
    corte_validacion = pd.Timestamp(fin_validacion) + pd.Timedelta(days=1)
    entrenamiento = df[fecha < corte_entrenamiento]
    validacion = df[(fecha >= corte_entrenamiento) & (fecha < corte_validacion)]
    prueba = df[fecha >= corte_validacion]
    return entrenamiento, validacion, prueba


def _completar_malla(conteos, columna_tiempo, frecuencia, fin):
    rangos = conteos.groupby("estacion_id")[columna_tiempo].agg(["min", "max"])
    tiempos = pd.date_range(conteos[columna_tiempo].min(), fin, freq=frecuencia)
    malla = pd.MultiIndex.from_product([rangos.index, tiempos], names=["estacion_id", columna_tiempo])
    completo = conteos.set_index(["estacion_id", columna_tiempo]).reindex(malla, fill_value=0).reset_index()
    completo = completo.merge(rangos, left_on="estacion_id", right_index=True)
    dentro = (completo[columna_tiempo] >= completo["min"]) & (completo[columna_tiempo] <= completo["max"])
    return completo[dentro].drop(columns=["min", "max"]).reset_index(drop=True)


def viajes_por_estacion_y_dia(viajes):
    """Cuenta los viajes iniciados por estación y día: la variable objetivo de P1.

    La serie de cada estación se completa con ceros entre su primer y su último día
    con viajes, porque un día sin salidas también es demanda observada y los rezagos
    necesitan una serie diaria continua por estación.
    """
    fecha = viajes["inicio"].dt.normalize().rename("fecha")
    diario = viajes.groupby([viajes["origen_id"].rename("estacion_id"), fecha]).size().rename("salidas").reset_index()
    fin = viajes["inicio"].max().normalize()
    return _completar_malla(diario, "fecha", "D", fin)


def construir_features_p1(diario, estaciones):
    """Construye las variables de P1 para predecir las salidas de cada estación un día adelante.

    Para el día t solo entran valores de t-1 hacia atrás: los rezagos de 1, 7 y 14 días,
    las medias móviles de 7 y 28 días que terminan en t-1, el día de la semana y el mes
    de t (se conocen de antemano) y la capacidad de la estación. Los rezagos de 7 y 14
    días captan la estacionalidad semanal del uso, las medias suavizan el nivel reciente
    y la capacidad acota el volumen que una estación puede mover.
    """
    df = diario.sort_values(["estacion_id", "fecha"]).reset_index(drop=True).copy()
    grupo = df.groupby("estacion_id")["salidas"]
    df["rezago_1"] = grupo.shift(1)
    df["rezago_7"] = grupo.shift(7)
    df["rezago_14"] = grupo.shift(14)
    df["media_7"] = grupo.transform(lambda s: s.shift(1).rolling(7, min_periods=1).mean())
    df["media_28"] = grupo.transform(lambda s: s.shift(1).rolling(28, min_periods=1).mean())
    df["dia_semana"] = df["fecha"].dt.dayofweek
    df["mes"] = df["fecha"].dt.month
    df["fin_de_semana"] = (df["dia_semana"] >= 5).astype(int)
    df = df.merge(estaciones[["estacion_id", "capacidad"]], on="estacion_id", how="left")
    return df.dropna(subset=["rezago_14"]).reset_index(drop=True)


def flujo_por_estacion_y_hora(viajes, estaciones):
    """Cuenta las salidas y las llegadas de cada estación en cada hora, sin huecos.

    Las salidas se asignan a la estación de origen por la hora de inicio y las llegadas
    a la de destino por la hora de fin. Solo entran estaciones con capacidad registrada,
    porque la etiqueta de P2 compara el flujo neto con la capacidad, y la serie de cada
    estación se completa con ceros entre su primera y su última hora con movimiento.
    """
    con_capacidad = estaciones.loc[estaciones["capacidad"] > 0, "estacion_id"]
    salidas = viajes.groupby([viajes["origen_id"].rename("estacion_id"), viajes["inicio"].dt.floor("h").rename("hora")])
    llegadas = viajes.groupby([viajes["destino_id"].rename("estacion_id"), viajes["fin"].dt.floor("h").rename("hora")])
    conteos = pd.concat([salidas.size().rename("salidas"), llegadas.size().rename("llegadas")], axis=1)
    conteos = conteos.fillna(0).astype("int32").reset_index()
    conteos = conteos[conteos["estacion_id"].isin(con_capacidad)]
    fin = viajes["inicio"].max().normalize() + pd.Timedelta(hours=23)
    horario = _completar_malla(conteos, "hora", "h", fin)
    return horario.astype({"salidas": "int32", "llegadas": "int32"})


def etiquetar_riesgo(horario, estaciones, umbral=config.UMBRAL_RIESGO, ventana=config.VENTANA_RIESGO_HORAS):
    """Etiqueta el riesgo de P2 con el flujo neto de las siguientes horas frente a la capacidad.

    El portal no publica el inventario de bicicletas, así que el riesgo se aproxima con lo
    que sí se observa: si en las `ventana` horas posteriores a la hora t el flujo neto
    acumulado (llegadas menos salidas) alcanza `umbral` veces la capacidad, la estación
    tiende a llenarse (sin anclajes) o a vaciarse (sin bicicletas). La etiqueta de t mira
    las horas t+1 a t+ventana, que es lo que el equipo de rebalanceo quiere anticipar al
    terminar la hora t; las variables de entrada solo usan la hora t y anteriores.
    """
    df = horario.sort_values(["estacion_id", "hora"]).reset_index(drop=True).copy()
    df["neto"] = df["llegadas"] - df["salidas"]
    grupo = df.groupby("estacion_id")["neto"]
    df["neto_futuro"] = sum(grupo.shift(-k) for k in range(1, ventana + 1))
    df = df.merge(estaciones[["estacion_id", "capacidad"]], on="estacion_id", how="left")
    df = df.dropna(subset=["neto_futuro"]).reset_index(drop=True)
    df["riesgo"] = (df["neto_futuro"].abs() >= umbral * df["capacidad"]).astype(int)
    return df


def construir_features_p2(etiquetado):
    """Construye las variables de P2 en la hora t con información de t hacia atrás.

    Salidas y llegadas de la hora t y de las dos anteriores, flujo neto acumulado de
    las últimas tres horas, el flujo neto que tuvo la misma ventana objetivo una semana
    antes y su etiqueta de riesgo (ya ocurrieron, así que no filtran el futuro), la hora
    del día, el día de la semana y la capacidad. Las horas recientes dicen hacia dónde
    se mueve la estación y la semana anterior aporta la estacionalidad horaria.
    """
    df = etiquetado.sort_values(["estacion_id", "hora"]).reset_index(drop=True).copy()
    grupo = df.groupby("estacion_id")
    for k in range(3):
        df[f"salidas_h{k}"] = grupo["salidas"].shift(k)
        df[f"llegadas_h{k}"] = grupo["llegadas"].shift(k)
    df["neto_3h"] = sum(grupo["neto"].shift(k) for k in range(3))
    df["neto_futuro_semana_anterior"] = grupo["neto_futuro"].shift(24 * 7)
    df["riesgo_semana_anterior"] = grupo["riesgo"].shift(24 * 7)
    df["hora_dia"] = df["hora"].dt.hour
    df["dia_semana"] = df["hora"].dt.dayofweek
    df["fin_de_semana"] = (df["dia_semana"] >= 5).astype(int)
    df = df.dropna(subset=["riesgo_semana_anterior"]).reset_index(drop=True)
    return df.astype({columna: "float32" for columna in COLUMNAS_P2})


def perfiles_por_estacion(viajes, estaciones, viajes_minimos=config.VIAJES_MINIMOS_PERFIL):
    """Construye el perfil de uso de cada estación para agruparlas en P3.

    Para cada estación: la fracción de sus salidas y de sus llegadas que cae en cada hora
    del día, separando días hábiles y fines de semana (2 x 2 x 24 = 96 valores, cada bloque
    de 48 suma 1), más el volumen total en escala logarítmica y la proporción de salidas
    sobre el total. Los perfiles normalizados dicen cuándo se usa la estación (zona
    habitacional, de trabajo o de ocio) sin que el tamaño domine; el volumen y la
    proporción dicen cuánto y en qué sentido. Entran las estaciones con coordenadas y
    al menos `viajes_minimos` viajes en el periodo.
    """
    def bloque(ids, tiempos, nombre):
        tipo = np.where(tiempos.dt.dayofweek >= 5, "finde", "habil")
        tabla = pd.crosstab(ids.rename("estacion_id"), [pd.Series(tipo, index=ids.index, name="tipo"), tiempos.dt.hour.rename("hora")])
        columnas = pd.MultiIndex.from_product([["habil", "finde"], range(24)])
        tabla = tabla.reindex(columns=columnas, fill_value=0)
        tabla.columns = [f"{nombre}_{tipo_dia}_{hora:02d}" for tipo_dia, hora in tabla.columns]
        return tabla

    salidas = bloque(viajes["origen_id"], viajes["inicio"], "salidas")
    llegadas = bloque(viajes["destino_id"], viajes["fin"], "llegadas")
    total_salidas = salidas.sum(axis=1)
    total_llegadas = llegadas.sum(axis=1).reindex(total_salidas.index, fill_value=0)
    llegadas = llegadas.reindex(total_salidas.index, fill_value=0)
    perfil = pd.concat([salidas.div(total_salidas, axis=0), llegadas.div(total_llegadas.replace(0, np.nan), axis=0)], axis=1).fillna(0)
    total = total_salidas + total_llegadas
    perfil["log_viajes"] = np.log1p(total)
    perfil["proporcion_salidas"] = total_salidas / total
    perfil = perfil[total >= viajes_minimos]
    columnas = ["estacion_id", "nombre", "latitud", "longitud"]
    return estaciones[columnas].merge(perfil, left_on="estacion_id", right_index=True).reset_index(drop=True)


def conjuntos_p1(viajes, estaciones, fin_entrenamiento=config.FIN_ENTRENAMIENTO, fin_validacion=config.FIN_VALIDACION):
    """Arma las features de P1 y las parte en entrenamiento, validación y prueba."""
    datos = construir_features_p1(viajes_por_estacion_y_dia(viajes), estaciones)
    return particion_temporal(datos, "fecha", fin_entrenamiento, fin_validacion)


def conjuntos_p2(viajes, estaciones, umbral=config.UMBRAL_RIESGO, ventana=config.VENTANA_RIESGO_HORAS,
                 fin_entrenamiento=config.FIN_ENTRENAMIENTO, fin_validacion=config.FIN_VALIDACION):
    """Arma las features y la etiqueta de P2 y las parte en entrenamiento, validación y prueba."""
    etiquetado = etiquetar_riesgo(flujo_por_estacion_y_hora(viajes, estaciones), estaciones, umbral, ventana)
    datos = construir_features_p2(etiquetado)
    return particion_temporal(datos, "hora", fin_entrenamiento, fin_validacion)


def conjunto_p3(viajes, estaciones, fin_entrenamiento=config.FIN_ENTRENAMIENTO):
    """Arma los perfiles de P3 solo con los viajes del periodo de entrenamiento."""
    corte = pd.Timestamp(fin_entrenamiento) + pd.Timedelta(days=1)
    return perfiles_por_estacion(viajes[viajes["inicio"] < corte], estaciones)
