# Validación de datos con DeepChecks

Reportes generados el 2026-10-30 08:40 con deepchecks 0.19.1 (`chequeos/validar_datos.py`) sobre las tablas que `python -m mibici.validacion --exportar` escribió en `data/interim/` el 2026-10-30 08:38:28 a partir de la versión de datos `7aa5e436d887`. Por suite hay un JSON (`to_json(with_display=False)`, versionado) y un HTML con las tablas y las gráficas de cada chequeo (`save_as_html(as_widget=False)`, fuera de Git por su tamaño). Las condiciones de cada chequeo son las que DeepChecks trae por defecto; ninguna se desactivó y los hallazgos se documentan tal como salen.

## Tablas validadas

P1 y P3 se validan completos. P2 se valida sobre una muestra sin reemplazo de 200,000 filas por conjunto (semilla 42, orden temporal conservado); las cifras de la etiqueta en la lectura de la deriva usan los conjuntos completos. Los viajes crudos son el archivo del portal del mes 2025-01 (`datos_abiertos_2025_01.csv`, latin-1) leído antes de `limpiar_viajes`, con los nombres de columna normalizados, las fechas convertidas, la duración calculada sin filtrar y sin las columnas personales (`usuario_id`, `genero`, `anio_nacimiento`), que la ingesta descarta y ningún reporte debe contener.

| Tabla | Filas | Columnas | Tamaño | Nota |
|---|---|---|---|---|
| `p1_entrenamiento.parquet` | 95,035 | 12 | 0.81 MB | completo |
| `p1_validacion.parquet` | 11,379 | 12 | 0.11 MB | completo, no entra a las suites |
| `p1_prueba.parquet` | 22,399 | 12 | 0.20 MB | completo |
| `p2_entrenamiento.parquet` | 200,000 | 20 | 2.20 MB | muestra de 2,339,422 filas |
| `p2_validacion.parquet` | 200,000 | 20 | 1.85 MB | muestra de 272,496 filas, no entra a las suites |
| `p2_prueba.parquet` | 200,000 | 20 | 1.93 MB | muestra de 536,089 filas |
| `p3_perfil.parquet` | 369 | 102 | 0.36 MB | completo |
| `viajes_crudos.parquet` | 380,184 | 6 | 8.07 MB | mes 2025-01 antes de la limpieza |

## Integridad de los viajes crudos

Suite `data_integrity` sobre los 380,184 viajes de 2025-01 tal como los publica el portal, con `viaje_id` como índice, `inicio` como fecha y `origen_id` y `destino_id` como categóricas.

Conteos de la tabla cruda frente a los descartes que `limpiar_viajes` aplica sobre ese mismo mes:

| Concepto | Tabla cruda | `limpiar_viajes` |
|---|---|---|
| Registros del mes | 380,184 | 380,184 |
| Faltantes en las cinco columnas necesarias (sin fecha o sin estación) | 0 | 0 |
| `viaje_id` duplicado | 0 | 0 |
| Duración negativa | 0 | 0 |
| Duración menor a 1 min | 9,282 (2.44 %) | 9,282 |
| Duración mayor a 24 h | 0 | 0 |
| Duración mínima y máxima observadas | 0.0 y 1028.4 min | límites 1 y 1,440 min |
| Viajes que conserva la limpieza | 370,902 | 370,902 |

| Chequeo | Condición | Estado | Detalle |
|---|---|---|---|
| Single Value in Column | Does not contain only a single value | Pasa | Passed for 6 relevant columns |
| Special Characters | Ratio of samples containing solely special character is less or equal to 0.1% | Pasa | Passed for 6 relevant columns |
| Mixed Nulls | Number of different null types is less or equal to 1 | Pasa | Passed for 6 relevant columns |
| Mixed Data Types | Rare data types in column are either more than 10% or less than 1% of the data | Pasa | 6 columns passed: found 0 columns with negligible types mix, and 6 columns without any types mix |
| String Mismatch | No string variants | Pasa | Passed for 1 relevant column |
| Data Duplicates | Duplicate data ratio is less or equal to 5% | Pasa | Found 0% duplicate data |
| String Length Out Of Bounds | Ratio of string length outliers is less or equal to 0% | Pasa | No relevant columns to check were found |
| Feature-Feature Correlation | Not more than 0 pairs are correlated above 0.9 | Pasa | All correlations are less than 0.9 except pairs [] |
| Outlier Sample Detection | Sin condición | Solo muestra | 0.60% de las muestras con probabilidad de atipicidad mayor o igual a 0.7 |
| Conflicting Labels - Train Dataset |  | No corre | Dataset does not contain a label column |
| Feature Label Correlation - Train Dataset |  | No corre | Dataset does not contain a label column |
| Identifier Label Correlation - Train Dataset |  | No corre | Dataset does not contain a label column |

## Integridad del conjunto de entrenamiento de P1

Suite `data_integrity` sobre las 95,035 filas estación-día de entrenamiento de P1 con la etiqueta `salidas` declarada (regresión).

| Chequeo | Condición | Estado | Detalle |
|---|---|---|---|
| Feature-Feature Correlation | Not more than 0 pairs are correlated above 0.9 | No pasa | Correlation is greater than 0.9 for pairs [('rezago_14', 'rezago_7'), ('media_7', 'rezago_1'), ('media_7', 'rezago_7'), ('media_28', 'rezago_1'), ('media_28', 'rezago_7'), ('media_28', 'rezago_14'), ('media_28', 'media_7'), ('dia_semana', 'fin_de_semana')] |
| Single Value in Column | Does not contain only a single value | Pasa | Passed for 11 relevant columns |
| Special Characters | Ratio of samples containing solely special character is less or equal to 0.1% | Pasa | Passed for 11 relevant columns |
| Mixed Nulls | Number of different null types is less or equal to 1 | Pasa | Passed for 11 relevant columns |
| Mixed Data Types | Rare data types in column are either more than 10% or less than 1% of the data | Pasa | 11 columns passed: found 0 columns with negligible types mix, and 11 columns without any types mix |
| String Mismatch | No string variants | Pasa | Passed for 1 relevant column |
| Data Duplicates | Duplicate data ratio is less or equal to 5% | Pasa | Found 0% duplicate data |
| String Length Out Of Bounds | Ratio of string length outliers is less or equal to 0% | Pasa | No relevant columns to check were found |
| Feature Label Correlation | Features' Predictive Power Score is less than 0.8 | Pasa | Passed for 9 relevant columns |
| Identifier Label Correlation | Identifier columns PPS is less or equal to 0 | Pasa | Passed for 1 relevant column |
| Outlier Sample Detection | Sin condición | Solo muestra | 1.60% de las muestras con probabilidad de atipicidad mayor o igual a 0.7 |
| Conflicting Labels - Train Dataset |  | No corre | Check is irrelevant for regression tasks |

## Integridad del conjunto de entrenamiento de P2

Suite `data_integrity` sobre la muestra de 200,000 filas estación-hora de entrenamiento de P2 con la etiqueta `riesgo` declarada (binaria).

| Chequeo | Condición | Estado | Detalle |
|---|---|---|---|
| Conflicting Labels | Ambiguous sample ratio is less or equal to 0% | No pasa | Ratio of samples with conflicting labels: 0.65% |
| Feature-Feature Correlation | Not more than 0 pairs are correlated above 0.9 | No pasa | Correlation is greater than 0.9 for pairs [('dia_semana', 'fin_de_semana')] |
| Data Duplicates | Duplicate data ratio is less or equal to 5% | Aviso | Found 12.87% duplicate data |
| Single Value in Column | Does not contain only a single value | Pasa | Passed for 15 relevant columns |
| Special Characters | Ratio of samples containing solely special character is less or equal to 0.1% | Pasa | Passed for 15 relevant columns |
| Mixed Nulls | Number of different null types is less or equal to 1 | Pasa | Passed for 15 relevant columns |
| Mixed Data Types | Rare data types in column are either more than 10% or less than 1% of the data | Pasa | 15 columns passed: found 0 columns with negligible types mix, and 15 columns without any types mix |
| String Mismatch | No string variants | Pasa | Passed for 1 relevant column |
| String Length Out Of Bounds | Ratio of string length outliers is less or equal to 0% | Pasa | No relevant columns to check were found |
| Feature Label Correlation | Features' Predictive Power Score is less than 0.8 | Pasa | Passed for 13 relevant columns |
| Identifier Label Correlation | Identifier columns PPS is less or equal to 0 | Pasa | Passed for 1 relevant column |
| Outlier Sample Detection | Sin condición | Solo muestra | 1.90% de las muestras con probabilidad de atipicidad mayor o igual a 0.7 |

## Integridad del perfil de P3

Suite `data_integrity` sobre el perfil de 369 estaciones con 98 variables numéricas y `estacion_id` como índice.

| Chequeo | Condición | Estado | Detalle |
|---|---|---|---|
| Single Value in Column | Does not contain only a single value | No pasa | Found 6 out of 99 columns with a single value: ['salidas_habil_02', 'salidas_habil_03', 'salidas_habil_04', 'salidas_finde_02', 'salidas_finde_03', 'salidas_finde_04'] |
| Special Characters | Ratio of samples containing solely special character is less or equal to 0.1% | Pasa | Passed for 99 relevant columns |
| Mixed Nulls | Number of different null types is less or equal to 1 | Pasa | Passed for 99 relevant columns |
| Mixed Data Types | Rare data types in column are either more than 10% or less than 1% of the data | Pasa | 99 columns passed: found 0 columns with negligible types mix, and 99 columns without any types mix |
| String Mismatch | No string variants | Pasa | Passed for 1 relevant column |
| Data Duplicates | Duplicate data ratio is less or equal to 5% | Pasa | Found 0% duplicate data |
| String Length Out Of Bounds | Ratio of string length outliers is less or equal to 0% | Pasa | No relevant columns to check were found |
| Feature-Feature Correlation | Not more than 0 pairs are correlated above 0.9 | Pasa | All correlations are less than 0.9 except pairs [] |
| Outlier Sample Detection | Sin condición | Solo muestra | 0.00% de las muestras con probabilidad de atipicidad mayor o igual a 0.7 |
| Conflicting Labels - Train Dataset |  | No corre | Dataset does not contain a label column |
| Feature Label Correlation - Train Dataset |  | No corre | Dataset does not contain a label column |
| Identifier Label Correlation - Train Dataset |  | No corre | Dataset does not contain a label column |

## Entrenamiento contra prueba de P1

Suite `train_test_validation` entre las 95,035 filas de entrenamiento y las 22,399 de prueba de P1.

| Chequeo | Condición | Estado | Detalle |
|---|---|---|---|
| New Category Train Test | Ratio of samples with a new category is less or equal to 0% | No pasa | Found 1 features with ratio of new categories above threshold: {'mes': '100%'} |
| Feature Drift | categorical drift score < 0.2 and numerical drift score < 0.2 | No pasa | Failed for 1 out of 9 columns. Found 1 categorical columns with Cramer's V above threshold: {'mes': '1'} |
| Multivariate Drift | Drift value is less than 0.25 | No pasa | Found drift value of: 1, corresponding to a domain classifier AUC of: 1 |
| Datasets Size Comparison | Test-Train size ratio is greater than 0.01 | Pasa | Test-Train size ratio is 0.24 |
| String Mismatch Comparison | No new variants allowed in test data | Pasa | No relevant columns to check were found |
| Date Train-Test Leakage (duplicates) | Date leakage ratio is less or equal to 0% | Pasa | No leaked dates found |
| Date Train-Test Leakage (overlap) | Date leakage ratio is less or equal to 0% | Pasa | No leaked dates found |
| Train Test Samples Mix | Percentage of test data samples that appear in train data is less or equal to 5% | Pasa | No samples mix found |
| Feature Label Correlation Change | Train-Test features' Predictive Power Score difference is less than 0.2 | Pasa | Passed for 9 relevant columns |
| Feature Label Correlation Change | Train features' Predictive Power Score is less than 0.7 | Pasa | Passed for 9 relevant columns |
| Label Drift | Label drift score < 0.15 | Pasa | Label's drift score Kolmogorov-Smirnov is 0.04 |
| New Label Train Test |  | No corre | Check is irrelevant for regression tasks |
| Index Train Test Leakage |  | No corre | Dataset does not contain an index |

Deriva por variable entre entrenamiento y prueba:

| Variable | Método | Puntuación |
|---|---|---|
| `rezago_1` | Kolmogorov-Smirnov | 0.037 |
| `rezago_7` | Kolmogorov-Smirnov | 0.015 |
| `rezago_14` | Kolmogorov-Smirnov | 0.012 |
| `media_7` | Kolmogorov-Smirnov | 0.034 |
| `media_28` | Kolmogorov-Smirnov | 0.014 |
| `dia_semana` | Cramer's V | 0.024 |
| `mes` | Cramer's V | 1.000 |
| `fin_de_semana` | Kolmogorov-Smirnov | 0.009 |
| `capacidad` | Kolmogorov-Smirnov | 0.003 |

- Deriva de la etiqueta: 0.041 (Kolmogorov-Smirnov).
- Deriva multivariada: 1.000 (AUC del clasificador de dominio 1.000); variables que más separan entrenamiento de prueba: `mes` (1.00), `rezago_1` (0.00), `rezago_7` (0.00).
- Muestras de prueba idénticas a alguna de entrenamiento en las variables y la etiqueta: 0.00 %.
- Categorías de `mes` que no existen en entrenamiento: [11, 12] (100.00 % de las filas de prueba).

## Entrenamiento contra prueba de P2

Suite `train_test_validation` entre las muestras de 200,000 filas de entrenamiento y 200,000 de prueba de P2.

| Chequeo | Condición | Estado | Detalle |
|---|---|---|---|
| Train Test Samples Mix | Percentage of test data samples that appear in train data is less or equal to 5% | No pasa | Percent of test data samples that appear in train data: 37.65% |
| Datasets Size Comparison | Test-Train size ratio is greater than 0.01 | Pasa | Test-Train size ratio is 1 |
| New Label Train Test | Number of new label values is less or equal to 0 | Pasa | Found 0 new labels in test data: [] |
| New Category Train Test | Ratio of samples with a new category is less or equal to 0% | Pasa | Passed for 2 relevant features |
| String Mismatch Comparison | No new variants allowed in test data | Pasa | No relevant columns to check were found |
| Date Train-Test Leakage (duplicates) | Date leakage ratio is less or equal to 0% | Pasa | No leaked dates found |
| Date Train-Test Leakage (overlap) | Date leakage ratio is less or equal to 0% | Pasa | No leaked dates found |
| Feature Label Correlation Change | Train-Test features' Predictive Power Score difference is less than 0.2 | Pasa | Passed for 13 relevant columns |
| Feature Label Correlation Change | Train features' Predictive Power Score is less than 0.7 | Pasa | Passed for 13 relevant columns |
| Feature Drift | categorical drift score < 0.2 and numerical drift score < 0.2 | Pasa | Passed for 13 columns out of 13 columns. Found column "dia_semana" has the highest categorical drift score: 0.03 Found column "llegadas_h2" has the highest numerical drift score: 0.02 |
| Label Drift | Label drift score < 0.15 | Pasa | Label's drift score Cramer's V is 0.02 |
| Multivariate Drift | Drift value is less than 0.25 | Pasa | Found drift value of: 0.05, corresponding to a domain classifier AUC of: 0.53 |
| Index Train Test Leakage |  | No corre | Dataset does not contain an index |

Deriva por variable entre entrenamiento y prueba:

| Variable | Método | Puntuación |
|---|---|---|
| `salidas_h0` | Kolmogorov-Smirnov | 0.015 |
| `llegadas_h0` | Kolmogorov-Smirnov | 0.015 |
| `salidas_h1` | Kolmogorov-Smirnov | 0.019 |
| `llegadas_h1` | Kolmogorov-Smirnov | 0.017 |
| `salidas_h2` | Kolmogorov-Smirnov | 0.019 |
| `llegadas_h2` | Kolmogorov-Smirnov | 0.020 |
| `neto_3h` | Kolmogorov-Smirnov | 0.016 |
| `neto_futuro_semana_anterior` | Kolmogorov-Smirnov | 0.009 |
| `riesgo_semana_anterior` | Kolmogorov-Smirnov | 0.003 |
| `hora_dia` | Cramer's V | 0.000 |
| `dia_semana` | Cramer's V | 0.030 |
| `fin_de_semana` | Kolmogorov-Smirnov | 0.015 |
| `capacidad` | Kolmogorov-Smirnov | 0.004 |

- Deriva de la etiqueta: 0.022 (Cramer's V).
- Deriva multivariada: 0.054 (AUC del clasificador de dominio 0.527); variables que más separan entrenamiento de prueba: `neto_3h` (0.64), `hora_dia` (0.32), `salidas_h2` (0.04).
- Muestras de prueba idénticas a alguna de entrenamiento en las variables y la etiqueta: 37.65 %.
- Ninguna variable categórica tiene categorías nuevas en prueba.

## Lectura de la deriva entre enero-septiembre y noviembre-diciembre

### Etiqueta de P2, riesgo por estación y hora

- Horas-estación en riesgo en los conjuntos completos, antes de muestrear: 42,327 de 2,339,422 en entrenamiento (1.81 %), 4,989 de 272,496 en validación (1.83 %, el mes en que se elige el umbral de decisión) y 6,718 de 536,089 en prueba (1.25 %). La tasa de riesgo cae 30.7 % en noviembre y diciembre respecto a enero-septiembre.
- Con la tasa de enero a septiembre se esperarían 9,699 horas en riesgo en prueba y ocurren 6,718: un modelo que mantuviera la frecuencia de alertas del entrenamiento emitiría del orden de 2,981 alertas sin riesgo real en los dos meses, un viaje de camión de más por cada una.
- El costo asimétrico de P2 valúa cada hora en riesgo sin aviso en 5 falsos positivos. No anticipar ninguna de las 6,718 horas en riesgo de prueba costaría 33,590 unidades, y cada punto porcentual de recall que se pierda por la deriva equivale a 67 horas en riesgo mal anticipadas, 336 unidades de costo.
- DeepChecks mide esa deriva de la etiqueta en 0.022 (Cramer's V) sobre la muestra: con una clase positiva tan rara la puntuación queda muy por debajo del umbral de 0.15 aunque la caída relativa de la tasa sea grande, por eso la lectura operativa se hace con los conteos completos y no únicamente con la condición del chequeo.
- Las variables de flujo se mueven poco en distribución (la mayor deriva es `llegadas_h2`, 0.020), así que el cambio está en la etiqueta más que en las entradas: en noviembre y diciembre el mismo patrón de flujo desemboca menos veces en una estación llena o vacía, y un umbral de probabilidad fijado en octubre tiende a sobrealertar.

### `rezago_7` de P1, demanda por estación y día

- `rezago_7` (salidas de la misma estación siete días antes) promedia 33.26 viajes por estación y día en entrenamiento y 32.91 en prueba, con una deriva de 0.015 (Kolmogorov-Smirnov); la variable objetivo `salidas` pasa de 33.31 a 31.10 (deriva de la etiqueta 0.041).
- La demanda de noviembre y diciembre baja mientras el nivel de la semana anterior se mantiene: `rezago_7` menos `salidas` promedia -0.05 viajes en entrenamiento y +1.81 en prueba. Como el baseline `naive7` predice exactamente `rezago_7`, ese sesgo son 40,560 viajes sobredimensionados en los 22,399 pares estación-día de prueba, flota y personal asignados a una demanda que no llega; los modelos que usan `media_28` y `mes` lo corrigen solo en parte, porque los meses 11 y 12 no existen en entrenamiento.
- La deriva multivariada de la suite (1.000) la explica `mes` por sí sola. Al repetir `MultivariateDrift` sin `mes`, la deriva queda en 0.128 (AUC 0.564): el resto de las variables de P1 tiene la misma distribución en los dos periodos.

## Condiciones y hallazgos

- Condiciones. Se conservan los umbrales por defecto de DeepChecks (deriva menor a 0.2 por variable y a 0.15 en la etiqueta, deriva multivariada menor a 0.25, correlación entre variables hasta 0.9, duplicados y mezcla de muestras hasta 5 %, cero categorías, etiquetas y fechas nuevas). El único ajuste de configuración es `OutlierSampleDetection(timeout=60)` en lugar del tope de 10 s, porque con 380,184 viajes crudos el tiempo proyectado del chequeo supera ese tope y el chequeo abortaría; ese chequeo no trae condición, así que se reporta la proporción de muestras con probabilidad de atipicidad mayor o igual a 0.7.
- Viajes crudos. La tabla del portal no tiene `viaje_id` duplicados ni faltantes en las cinco columnas necesarias, y los chequeos de nulos, tipos mezclados y duplicados lo confirman; el problema real del mes son los viajes de menos de un minuto, que `limpiar_viajes` descarta y cuyo conteo coincide con el de la tabla cruda (9,282). La duración sin filtrar llega a 1028.4 min, dentro del límite de 24 h. Los chequeos de etiqueta no corren porque la tabla no tiene variable objetivo.
- P1, correlación entre variables. Los pares por encima de 0.9 son `fin_de_semana`-`dia_semana` (1.00), `media_7`-`media_28` (0.99), `rezago_7`-`rezago_14` (0.92), `rezago_1`-`media_7` (0.92), `rezago_7`-`media_7` (0.92), `rezago_7`-`media_28` (0.91), `rezago_14`-`media_28` (0.91), `rezago_1`-`media_28` (0.91): la demanda diaria de una estación está muy autocorrelada y las medias móviles promedian los mismos rezagos, así que la redundancia es por construcción. Los modelos de árboles no la resienten y Ridge la amortigua con la regularización; se deja la condición por defecto y el hallazgo queda documentado como redundancia conocida.
- P2, etiquetas en conflicto y duplicados. 0.65 % de las horas de entrenamiento comparten exactamente las trece variables con otra hora que tiene la etiqueta contraria, y 12.87 % de las filas son idénticas a otra (misma hora, mismos flujos, misma capacidad y misma etiqueta, en estaciones distintas). Ocurre en horas de poco o ningún movimiento, donde el riesgo de las dos horas siguientes no se distingue con las variables de la hora actual: es ruido irreducible para cualquier modelo con estas entradas y acota el recall alcanzable. La correlación `dia_semana`-`fin_de_semana` es por diseño, porque la segunda se deriva de la primera.
- P3, columnas constantes. Las columnas `salidas_habil_02`, `salidas_habil_03`, `salidas_habil_04`, `salidas_finde_02`, `salidas_finde_03`, `salidas_finde_04` valen cero en todas las estaciones porque el sistema no registra salidas entre las 2:00 y las 4:59; son constantes por diseño del perfil horario, no aportan a la agrupación (el escalado las deja en cero) y conviene excluirlas en la siguiente iteración del perfil. Los chequeos de etiqueta no aplican porque P3 no tiene variable objetivo.
- P1, partición. `mes` toma en prueba los valores [11, 12], inexistentes en entrenamiento, por lo que `New Category Train Test` y `Feature Drift` no pasan y la deriva multivariada es 1.0: es consecuencia directa de la partición temporal (entrenamiento de enero a septiembre, prueba en noviembre y diciembre), no un defecto de los datos. Para el modelo sí importa: `HistGradientBoostingRegressor` trata `mes` como numérico y extrapola, y Ridge, con `handle_unknown="ignore"`, deja sin efecto mensual a las filas de prueba. Queda como mejora para la siguiente iteración codificar `mes` de forma cíclica o retirarlo de P1.
- P2, mezcla de muestras. 37.65 % de las horas de prueba coinciden en las trece variables y la etiqueta con alguna hora de entrenamiento. No es fuga: la partición es temporal y los dos chequeos de fechas pasan; son horas sin movimiento o con flujos pequeños que se repiten en cualquier mes, y la cifra mide qué parte del conjunto es trivial para el modelo.
- Chequeos que no corren. `Index Train Test Leakage` necesita un identificador único de fila y P1 y P2 identifican cada fila por estación y fecha u hora, así que no se declara índice; la separación entre periodos la verifican `Date Train-Test Leakage (overlap)` y `(duplicates)`, que pasan en las dos preguntas. `New Label Train Test` y `Conflicting Labels` no aplican a la regresión de P1.
- Muestra. Los chequeos que muestrean por dentro usan su `n_samples` por defecto (100,000 filas en la deriva por variable y 10,000 en la multivariada, por ejemplo); con 200,000 filas por conjunto todos los chequeos de P2 corren completos y cada suite termina en menos de un minuto y medio.

## Tiempos

| Suite | Filas | Chequeos | Estados | Segundos |
|---|---|---|---|---|
| Integridad de los viajes crudos | 380,184 | 12 | 8 pasa, 3 no corre, 1 solo muestra | 6.5 |
| Integridad del conjunto de entrenamiento de P1 | 95,035 | 12 | 9 pasa, 1 no pasa, 1 no corre, 1 solo muestra | 4.9 |
| Integridad del conjunto de entrenamiento de P2 | 200,000 | 12 | 8 pasa, 2 no pasa, 1 aviso, 1 solo muestra | 40.2 |
| Integridad del perfil de P3 | 369 | 12 | 7 pasa, 1 no pasa, 3 no corre, 1 solo muestra | 0.4 |
| Entrenamiento contra prueba de P1 | 117,434 | 12 | 8 pasa, 3 no pasa, 2 no corre | 29.2 |
| Entrenamiento contra prueba de P2 | 400,000 | 12 | 11 pasa, 1 no pasa, 1 no corre | 39.5 |

Exportación de las tablas: 12.6 s, de los que 11.9 s son la construcción de los conjuntos y la lectura del mes crudo. Suites: 120.7 s en total.
