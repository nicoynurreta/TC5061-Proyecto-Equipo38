# Monitoreo de P2: drift entre la referencia y el periodo actual

Reporte generado el 2026-11-15 03:02:48 con Evidently 0.7.23 (`python -m mibici.monitoreo.drift`) sobre la tabla `data/interim/monitoreo_p2.parquet`, que `python -m mibici.monitoreo.datos --exportar` arma con las versiones de datos `7aa5e436d887` (2025) y `f396cd21ea7d` (periodo actual) y con las predicciones de `mibici-equipo38-p2-riesgo` versión 1 (corrida `p2_hgb_mejor`, umbral de decisión 0.92). El reporte interactivo de Evidently queda en `reports/monitoreo/evidently_p2.html` (fuera de Git por su tamaño) y sus métricas en `reports/monitoreo/evidently_p2.json`; las cifras de este resumen están también en `reports/monitoreo/drift.json`.

## Conjuntos

Cada fila es una estación en una hora, con las 13 variables de entrada de P2, la etiqueta de riesgo de las dos horas siguientes y la probabilidad y la clase que asigna el modelo vigente. La referencia es el conjunto de entrenamiento del modelo; el periodo actual es el que el modelo atendió después, sin reentrenarse.

| Conjunto | Periodo | Filas | Estaciones | Horas en riesgo | Tasa de riesgo | Alertas del modelo | Tasa de alertas |
|---|---|---|---|---|---|---|---|
| Referencia | 2025-01-01 a 2025-09-30 | 2,339,422 | 369 | 42,327 | 1.81 % | 43,853 | 1.87 % |
| Validación | 2025-10-01 a 2025-10-31 | 272,496 | 368 | 4,989 | 1.83 % | 5,276 | 1.94 % |
| Prueba | 2025-11-01 a 2025-12-31 | 536,089 | 368 | 6,718 | 1.25 % | 8,016 | 1.50 % |
| Actual | 2026-01-01 a 2026-06-30 | 1,622,169 | 412 | 18,196 | 1.12 % | 19,821 | 1.22 % |
| Evaluación | 2026-07-01 a 2026-09-30 | 1,001,082 | 469 | 10,232 | 1.02 % | 11,470 | 1.15 % |
| Confirmación | 2026-10-01 a 2026-10-31 | 346,775 | 469 | 4,947 | 1.43 % | 6,191 | 1.79 % |

## Drift por columna: referencia contra actual

Preset `DataDriftPreset` de Evidently con distancia de Wasserstein normalizada en las columnas numéricas y distancia de Jensen-Shannon en las categóricas; hay deriva en una columna cuando el estadístico alcanza 0.1 y en el conjunto cuando deriva al menos 50 % de las columnas. En las columnas binarias la media es la proporción de unos.

| Columna | Papel | Prueba | Estadístico | Umbral | Veredicto | Media en referencia | Media en actual | Cambio relativo |
|---|---|---|---|---|---|---|---|---|
| `salidas_h0` | entrada | Distancia de Wasserstein normalizada | 0.061 | 0.1 | Sin deriva | 1.387 | 1.240 | -10.6 % |
| `llegadas_h0` | entrada | Distancia de Wasserstein normalizada | 0.055 | 0.1 | Sin deriva | 1.387 | 1.240 | -10.6 % |
| `salidas_h1` | entrada | Distancia de Wasserstein normalizada | 0.061 | 0.1 | Sin deriva | 1.387 | 1.240 | -10.6 % |
| `llegadas_h1` | entrada | Distancia de Wasserstein normalizada | 0.055 | 0.1 | Sin deriva | 1.387 | 1.240 | -10.6 % |
| `salidas_h2` | entrada | Distancia de Wasserstein normalizada | 0.061 | 0.1 | Sin deriva | 1.387 | 1.240 | -10.6 % |
| `llegadas_h2` | entrada | Distancia de Wasserstein normalizada | 0.056 | 0.1 | Sin deriva | 1.387 | 1.240 | -10.6 % |
| `neto_3h` | entrada | Distancia de Wasserstein normalizada | 0.082 | 0.1 | Sin deriva | -0.000 | 0.001 | n. a. |
| `neto_futuro_semana_anterior` | entrada | Distancia de Wasserstein normalizada | 0.078 | 0.1 | Sin deriva | 0.000 | -0.000 | n. a. |
| `riesgo_semana_anterior` | entrada | Distancia de Jensen-Shannon | 0.021 | 0.1 | Sin deriva | 0.018 | 0.011 | -38.5 % |
| `hora_dia` | entrada | Distancia de Jensen-Shannon | 0.000 | 0.1 | Sin deriva | n. a. | n. a. | n. a. |
| `dia_semana` | entrada | Distancia de Jensen-Shannon | 0.004 | 0.1 | Sin deriva | n. a. | n. a. | n. a. |
| `fin_de_semana` | entrada | Distancia de Jensen-Shannon | 0.001 | 0.1 | Sin deriva | 0.286 | 0.287 | +0.4 % |
| `capacidad` | entrada | Distancia de Wasserstein normalizada | 0.006 | 0.1 | Sin deriva | 16.937 | 16.940 | +0.0 % |
| `riesgo` | objetivo | Distancia de Jensen-Shannon | 0.020 | 0.1 | Sin deriva | 0.018 | 0.011 | -38.0 % |
| `probabilidad` | predicción | Distancia de Wasserstein normalizada | 0.079 | 0.1 | Sin deriva | 0.200 | 0.178 | -11.0 % |
| `prediccion` | predicción | Distancia de Jensen-Shannon | 0.019 | 0.1 | Sin deriva | 0.019 | 0.012 | -34.8 % |

Columnas con deriva: 0 de 16 (0.0 %); deriva del conjunto según Evidently: no.

## Comparaciones de control

El mismo preset sobre tres pares de conjuntos que aíslan el origen de la deriva: los mismos meses del año en la referencia y en el periodo actual (quita la estacionalidad), el periodo actual restringido a las estaciones que existían en la referencia (quita la expansión del sistema) y la referencia contra la prueba de 2025 (la deriva que el modelo ya enfrentó al evaluarse, solo por cambio de temporada).

| Columna | Referencia contra actual | Mismos meses un año después | Solo estaciones de la referencia | Referencia contra prueba de 2025 |
|---|---|---|---|---|
| `salidas_h0` | 0.061 | 0.070 | 0.057 | 0.037 |
| `llegadas_h0` | 0.055 | 0.063 | 0.051 | 0.034 |
| `salidas_h1` | 0.061 | 0.070 | 0.057 | 0.037 |
| `llegadas_h1` | 0.055 | 0.063 | 0.051 | 0.034 |
| `salidas_h2` | 0.061 | 0.070 | 0.057 | 0.037 |
| `llegadas_h2` | 0.056 | 0.063 | 0.051 | 0.034 |
| `neto_3h` | 0.082 | 0.088 | 0.079 | 0.058 |
| `neto_futuro_semana_anterior` | 0.078 | 0.083 | 0.074 | 0.032 |
| `riesgo_semana_anterior` | 0.021 | 0.023 | 0.020 | 0.011 |
| `hora_dia` | 0.000 | 0.001 | 0.000 | 0.002 |
| `dia_semana` | 0.004 | 0.007 | 0.004 | 0.018 |
| `fin_de_semana` | 0.001 | 0.000 | 0.001 | 0.008 |
| `capacidad` | 0.006 | 0.007 | 0.002 | 0.003 |
| `riesgo` | 0.020 | 0.023 | 0.020 | 0.016 |
| `probabilidad` | 0.079 | 0.085 | 0.073 | 0.048 |
| `prediccion` | 0.019 | 0.021 | 0.018 | 0.010 |
| Columnas con deriva | 0 de 16 | 0 de 16 | 0 de 16 | 0 de 16 |

## Drift por mes del periodo actual

Estadístico de cada columna en cada mes contra la referencia; el asterisco marca los que alcanzan el umbral de 0.1.

| Columna | 2026-01 | 2026-02 | 2026-03 | 2026-04 | 2026-05 | 2026-06 | 2026-07 | 2026-08 | 2026-09 | 2026-10 |
|---|---|---|---|---|---|---|---|---|---|---|
| `salidas_h0` | 0.05 | 0.04 | 0.03 | 0.05 | 0.11 * | 0.08 | 0.10 | 0.12 * | 0.02 | 0.15 * |
| `llegadas_h0` | 0.05 | 0.04 | 0.02 | 0.04 | 0.11 * | 0.07 | 0.09 | 0.11 * | 0.02 | 0.14 * |
| `salidas_h1` | 0.05 | 0.04 | 0.03 | 0.05 | 0.11 * | 0.08 | 0.10 | 0.12 * | 0.02 | 0.14 * |
| `llegadas_h1` | 0.05 | 0.04 | 0.02 | 0.04 | 0.11 * | 0.07 | 0.09 | 0.11 * | 0.02 | 0.14 * |
| `salidas_h2` | 0.05 | 0.04 | 0.03 | 0.05 | 0.11 * | 0.08 | 0.10 | 0.12 * | 0.02 | 0.14 * |
| `llegadas_h2` | 0.05 | 0.04 | 0.02 | 0.04 | 0.10 * | 0.08 | 0.09 | 0.11 * | 0.02 | 0.14 * |
| `neto_3h` | 0.07 | 0.07 | 0.06 | 0.06 | 0.11 * | 0.12 * | 0.12 * | 0.11 * | 0.08 | 0.04 |
| `neto_futuro_semana_anterior` | 0.10 | 0.04 | 0.07 | 0.06 | 0.09 | 0.11 * | 0.11 * | 0.12 * | 0.08 | 0.04 |
| `riesgo_semana_anterior` | 0.02 | 0.01 | 0.02 | 0.02 | 0.02 | 0.03 | 0.03 | 0.03 | 0.02 | 0.01 |
| `hora_dia` | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| `dia_semana` | 0.04 | 0.00 | 0.04 | 0.04 | 0.04 | 0.04 | 0.04 | 0.04 | 0.04 | 0.04 |
| `fin_de_semana` | 0.00 | 0.00 | 0.00 | 0.02 | 0.03 | 0.01 | 0.02 | 0.03 | 0.02 | 0.00 |
| `capacidad` | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.03 | 0.08 | 0.10 | 0.10 * | 0.10 * |
| `riesgo` | 0.02 | 0.02 | 0.02 | 0.02 | 0.03 | 0.03 | 0.03 | 0.03 | 0.02 | 0.01 |
| `probabilidad` | 0.09 | 0.05 | 0.05 | 0.06 | 0.12 * | 0.11 * | 0.13 * | 0.16 * | 0.05 | 0.06 |
| `prediccion` | 0.02 | 0.01 | 0.02 | 0.01 | 0.02 | 0.02 | 0.03 | 0.03 | 0.01 | 0.00 |
| Columnas con deriva | 0 | 0 | 0 | 0 | 8 | 3 | 3 | 9 | 1 | 7 |

El primer mes con deriva del conjunto, es decir, con al menos 50 % de las columnas sobre el umbral, es 2026-05 (8 de 16: `salidas_h0`, `llegadas_h0`, `salidas_h1`, `llegadas_h1`, `salidas_h2`, `llegadas_h2`, `neto_3h`, `probabilidad`). El reporte de Evidently de ese mes contra la referencia queda en `reports/monitoreo/evidently_p2_alerta.html` y sus métricas en `reports/monitoreo/evidently_p2_alerta.json`.

## Objetivo y predicción

- La tasa de horas en riesgo pasa de 1.81 % en la referencia a 1.12 % en el periodo actual (-38.0 %). Con la tasa de la referencia se esperarían 29,350 horas en riesgo en las 1,622,169 filas del periodo actual y ocurren 18,196.
- El modelo vigente alerta en 1.87 % de las horas de la referencia y en 1.22 % de las del periodo actual; por cada hora en riesgo observada emite 1.04 alertas en la referencia y 1.09 en el periodo actual.
- Estaciones: 369 en la referencia y 412 en el periodo actual; 44 son nuevas y aportan 23,577 filas (1.45 %). Estaciones de la referencia sin actividad en el periodo actual: 1.
- Tasa de riesgo en el periodo actual: 1.14 % en las estaciones de la referencia y 0.19 % en las nuevas.

## Calidad de los datos

Resumen `DataSummaryPreset` de Evidently sobre las mismas columnas en los dos conjuntos:

| Concepto | Referencia | Actual |
|---|---|---|
| Filas | 2,339,422 | 1,622,169 |
| Filas duplicadas en las columnas del reporte | 1,036,050 | 745,259 |
| Filas vacías | 0 | 0 |
| Valores faltantes | 0 | 0 |
| Columnas constantes | 0 | 0 |
| Columnas casi constantes | 3 | 3 |
| Columnas duplicadas | 0 | 0 |

| Columna numérica | Rango en referencia | Rango en actual | Desviación en referencia | Desviación en actual | Faltantes |
|---|---|---|---|---|---|
| `salidas_h0` | 0 a 205 | 0 a 147 | 2.489 | 2.370 | 0 |
| `llegadas_h0` | 0 a 210 | 0 a 151 | 2.645 | 2.427 | 0 |
| `salidas_h1` | 0 a 205 | 0 a 147 | 2.489 | 2.370 | 0 |
| `llegadas_h1` | 0 a 210 | 0 a 151 | 2.645 | 2.427 | 0 |
| `salidas_h2` | 0 a 205 | 0 a 147 | 2.489 | 2.369 | 0 |
| `llegadas_h2` | 0 a 210 | 0 a 151 | 2.645 | 2.426 | 0 |
| `neto_3h` | -117 a 166 | -140 a 106 | 4.145 | 3.508 | 0 |
| `neto_futuro_semana_anterior` | -101 a 132 | -119 a 86 | 3.129 | 2.677 | 0 |
| `capacidad` | 11 a 39 | 11 a 39 | 4.165 | 4.140 | 0 |
| `probabilidad` | 0 a 1 | 0 a 1 | 0.277 | 0.260 | 0 |

Archivos crudos del portal y descartes de la limpieza (`data/manifiesto.json` y `data/manifiesto_actual.json`); el porcentaje es sobre los registros crudos:

| Concepto | 2025 | Periodo actual |
|---|---|---|
| Meses | 12 | 10 |
| Registros crudos | 4,532,032 | 3,997,597 |
| Viajes válidos | 4,414,800 (97.41 %) | 3,840,981 (96.08 %) |
| `viaje_id` duplicado | 0 (0.00 %) | 758 (0.02 %) |
| Sin fecha o sin estación | 0 (0.00 %) | 0 (0.00 %) |
| Duración negativa | 0 (0.00 %) | 0 (0.00 %) |
| Duración menor a 1 min | 117,226 (2.59 %) | 155,845 (3.90 %) |
| Duración mayor a 24 h | 6 (0.00 %) | 13 (0.00 %) |
| Estaciones con viajes | 371 | 472 |
| Viajes con estación fuera de la nomenclatura | 0 (0.00 %) | 3,869 (0.10 %) |

| Mes | Codificación | Registros crudos | Viajes válidos | `viaje_id` duplicado | Duración menor a 1 min | Duración mayor a 24 h |
|---|---|---|---|---|---|---|
| 2026-01 | latin-1 | 357,180 | 346,645 | 0 | 10,535 (2.95 %) | 0 |
| 2026-02 | utf-8 | 333,756 | 319,059 | 0 | 14,696 (4.40 %) | 1 |
| 2026-03 | utf-8 | 376,243 | 364,815 | 0 | 11,427 (3.04 %) | 1 |
| 2026-04 | utf-8 | 351,851 | 341,716 | 0 | 10,135 (2.88 %) | 0 |
| 2026-05 | utf-8 | 315,895 | 305,117 | 0 | 10,777 (3.41 %) | 1 |
| 2026-06 | utf-8 | 355,303 | 337,572 | 0 | 17,725 (4.99 %) | 6 |
| 2026-07 | utf-8 | 388,257 | 371,629 | 0 | 16,627 (4.28 %) | 1 |
| 2026-08 | utf-8 | 393,524 | 376,321 | 0 | 17,203 (4.37 %) | 0 |
| 2026-09 | utf-8 | 490,056 | 470,348 | 758 | 18,949 (3.87 %) | 1 |
| 2026-10 | utf-8 | 635,532 | 607,759 | 0 | 27,771 (4.37 %) | 2 |
