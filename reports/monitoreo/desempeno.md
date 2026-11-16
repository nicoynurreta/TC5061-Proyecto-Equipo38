# Monitoreo de P2: desempeño del modelo vigente en el periodo actual

Generado el 2026-11-15 02:53:02 con `python -m mibici.monitoreo.desempeno` sobre la tabla de monitoreo. Modelo: `mibici-equipo38-p2-riesgo` versión 1 (corrida `p2_hgb_mejor`), con su umbral de decisión de 0.92. El costo cuenta un falso positivo como 1 y un falso negativo como 5. Se reporta por mil horas-estación, que es el costo operativo del periodo, y frente a no alertar: el costo dividido entre lo que costaría no emitir ninguna alerta, que no depende de cuántas horas en riesgo tiene cada periodo y vale 1 cuando el modelo no aporta nada.

## Por conjunto

| Conjunto | Periodo | Filas | Horas en riesgo | Tasa de riesgo | Tasa de alertas | Recall | Precisión | F1 | PR-AUC | Falsos positivos | Falsos negativos | Costo | Costo por mil horas-estación | Costo frente a no alertar |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Referencia (dentro de la muestra) | 2025-01-01 a 2025-09-30 | 2,339,422 | 42,327 | 1.81 % | 1.87 % | 0.388 | 0.375 | 0.381 | 0.375 | 27,428 | 25,902 | 156,938 | 67.08 | 0.742 |
| Validación | 2025-10-01 a 2025-10-31 | 272,496 | 4,989 | 1.83 % | 1.94 % | 0.397 | 0.376 | 0.386 | 0.381 | 3,293 | 3,006 | 18,323 | 67.24 | 0.735 |
| Prueba | 2025-11-01 a 2025-12-31 | 536,089 | 6,718 | 1.25 % | 1.50 % | 0.376 | 0.315 | 0.343 | 0.334 | 5,487 | 4,189 | 26,432 | 49.31 | 0.787 |
| Actual | 2026-01-01 a 2026-06-30 | 1,622,169 | 18,196 | 1.12 % | 1.22 % | 0.354 | 0.325 | 0.339 | 0.311 | 13,378 | 11,753 | 72,143 | 44.47 | 0.793 |
| Evaluación | 2026-07-01 a 2026-09-30 | 1,001,082 | 10,232 | 1.02 % | 1.15 % | 0.366 | 0.327 | 0.345 | 0.334 | 7,721 | 6,483 | 40,136 | 40.09 | 0.785 |
| Confirmación | 2026-10-01 a 2026-10-31 | 346,775 | 4,947 | 1.43 % | 1.79 % | 0.380 | 0.304 | 0.337 | 0.329 | 4,312 | 3,068 | 19,652 | 56.67 | 0.795 |

## Por mes fuera del entrenamiento

Las dos últimas columnas son el cambio relativo frente a la prueba de 2025 (recall 0.376, costo frente a no alertar 0.787).

| Mes | Conjunto | Filas | Horas en riesgo | Tasa de riesgo | Tasa de alertas | Recall | Precisión | F1 | PR-AUC | Falsos positivos | Falsos negativos | Costo | Costo por mil horas-estación | Costo frente a no alertar | Cambio del recall | Cambio del costo frente a no alertar |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025-10 | Validación | 272,496 | 4,989 | 1.83 % | 1.94 % | 0.397 | 0.376 | 0.386 | 0.381 | 3,293 | 3,006 | 18,323 | 67.24 | 0.735 | +5.6 % | -6.7 % |
| 2025-11 | Prueba | 264,240 | 3,820 | 1.45 % | 1.61 % | 0.373 | 0.334 | 0.353 | 0.340 | 2,835 | 2,396 | 14,815 | 56.07 | 0.776 | -1.0 % | -1.4 % |
| 2025-12 | Prueba | 271,849 | 2,898 | 1.07 % | 1.38 % | 0.381 | 0.294 | 0.332 | 0.329 | 2,652 | 1,793 | 11,617 | 42.73 | 0.802 | +1.3 % | +1.9 % |
| 2026-01 | Actual | 275,280 | 3,162 | 1.15 % | 1.13 % | 0.332 | 0.339 | 0.335 | 0.317 | 2,050 | 2,112 | 12,610 | 45.81 | 0.798 | -11.8 % | +1.4 % |
| 2026-02 | Actual | 248,640 | 3,059 | 1.23 % | 1.40 % | 0.368 | 0.324 | 0.345 | 0.313 | 2,349 | 1,933 | 12,014 | 48.32 | 0.785 | -2.2 % | -0.2 % |
| 2026-03 | Actual | 275,280 | 3,469 | 1.26 % | 1.33 % | 0.360 | 0.341 | 0.350 | 0.321 | 2,409 | 2,221 | 13,514 | 49.09 | 0.779 | -4.4 % | -1.0 % |
| 2026-04 | Actual | 266,400 | 3,413 | 1.28 % | 1.40 % | 0.384 | 0.352 | 0.367 | 0.340 | 2,415 | 2,102 | 12,925 | 48.52 | 0.757 | +2.0 % | -3.7 % |
| 2026-05 | Actual | 275,409 | 2,499 | 0.91 % | 1.04 % | 0.370 | 0.323 | 0.345 | 0.328 | 1,941 | 1,574 | 9,811 | 35.62 | 0.785 | -1.7 % | -0.2 % |
| 2026-06 | Actual | 281,160 | 2,594 | 0.92 % | 1.07 % | 0.302 | 0.261 | 0.280 | 0.245 | 2,214 | 1,811 | 11,269 | 40.08 | 0.869 | -19.8 % | +10.4 % |
| 2026-07 | Evaluación | 321,370 | 2,827 | 0.88 % | 1.02 % | 0.368 | 0.319 | 0.342 | 0.341 | 2,222 | 1,786 | 11,152 | 34.70 | 0.789 | -2.2 % | +0.3 % |
| 2026-08 | Evaluación | 342,752 | 3,337 | 0.97 % | 1.02 % | 0.362 | 0.344 | 0.353 | 0.336 | 2,300 | 2,130 | 12,950 | 37.78 | 0.776 | -3.9 % | -1.4 % |
| 2026-09 | Evaluación | 336,960 | 4,068 | 1.21 % | 1.39 % | 0.369 | 0.319 | 0.342 | 0.327 | 3,199 | 2,567 | 16,034 | 47.58 | 0.788 | -2.0 % | +0.2 % |
| 2026-10 | Confirmación | 346,775 | 4,947 | 1.43 % | 1.79 % | 0.380 | 0.304 | 0.337 | 0.329 | 4,312 | 3,068 | 19,652 | 56.67 | 0.795 | +0.9 % | +1.0 % |

## Descomposición del cambio de la tasa de riesgo

Cambio de la tasa de horas en riesgo de cada conjunto del periodo actual frente a la prueba de 2025, separado por estratos de 0.1 de la probabilidad que asigna el modelo. El efecto de mezcla es la parte del cambio que se explica porque las horas caen en otros estratos (cambian las entradas: data drift); el efecto condicional es la parte que se explica porque dentro del mismo estrato la frecuencia de riesgo ya es otra (cambia la relación entre entradas y objetivo: concept drift). Los dos efectos suman el cambio.

| Conjunto | Tasa en la prueba de 2025 | Tasa en el conjunto | Cambio | Efecto de mezcla | Efecto condicional | Parte de mezcla | Parte condicional |
|---|---|---|---|---|---|---|---|
| Actual | 1.253 % | 1.122 % | -0.131 pp | -0.124 pp | -0.007 pp | 94 % | 6 % |
| Evaluación | 1.253 % | 1.022 % | -0.231 pp | -0.173 pp | -0.058 pp | 75 % | 25 % |
| Confirmación | 1.253 % | 1.427 % | +0.173 pp | +0.300 pp | -0.126 pp | 173 % | -73 % |

Estratos de probabilidad, prueba de 2025 contra actual:

| Probabilidad | Peso en la prueba | Peso en el conjunto | Tasa de riesgo en la prueba | Tasa de riesgo en el conjunto | Horas en riesgo en la prueba | Horas en riesgo en el conjunto |
|---|---|---|---|---|---|---|
| 0.0 a 0.1 | 61.14 % | 62.39 % | 0.03 % | 0.03 % | 1.5 % | 1.5 % |
| 0.1 a 0.2 | 9.42 % | 9.38 % | 0.28 % | 0.24 % | 2.1 % | 2.0 % |
| 0.2 a 0.3 | 5.73 % | 5.65 % | 0.49 % | 0.51 % | 2.3 % | 2.6 % |
| 0.3 a 0.4 | 4.51 % | 4.45 % | 0.78 % | 0.80 % | 2.8 % | 3.2 % |
| 0.4 a 0.5 | 3.59 % | 3.47 % | 1.28 % | 1.20 % | 3.7 % | 3.7 % |
| 0.5 a 0.6 | 3.44 % | 3.31 % | 1.52 % | 1.77 % | 4.2 % | 5.2 % |
| 0.6 a 0.7 | 3.23 % | 3.12 % | 2.56 % | 2.63 % | 6.6 % | 7.3 % |
| 0.7 a 0.8 | 3.23 % | 3.14 % | 4.35 % | 4.13 % | 11.2 % | 11.5 % |
| 0.8 a 0.9 | 3.56 % | 3.30 % | 7.65 % | 7.28 % | 21.7 % | 21.4 % |
| 0.9 a 1.0 | 2.15 % | 1.78 % | 25.60 % | 26.06 % | 43.9 % | 41.5 % |

Estratos de probabilidad, prueba de 2025 contra evaluación:

| Probabilidad | Peso en la prueba | Peso en el conjunto | Tasa de riesgo en la prueba | Tasa de riesgo en el conjunto | Horas en riesgo en la prueba | Horas en riesgo en el conjunto |
|---|---|---|---|---|---|---|
| 0.0 a 0.1 | 61.14 % | 64.58 % | 0.03 % | 0.02 % | 1.5 % | 1.3 % |
| 0.1 a 0.2 | 9.42 % | 8.96 % | 0.28 % | 0.22 % | 2.1 % | 1.9 % |
| 0.2 a 0.3 | 5.73 % | 5.29 % | 0.49 % | 0.44 % | 2.3 % | 2.3 % |
| 0.3 a 0.4 | 4.51 % | 4.07 % | 0.78 % | 0.68 % | 2.8 % | 2.7 % |
| 0.4 a 0.5 | 3.59 % | 3.22 % | 1.28 % | 0.96 % | 3.7 % | 3.0 % |
| 0.5 a 0.6 | 3.44 % | 3.07 % | 1.52 % | 1.59 % | 4.2 % | 4.8 % |
| 0.6 a 0.7 | 3.23 % | 2.91 % | 2.56 % | 2.33 % | 6.6 % | 6.6 % |
| 0.7 a 0.8 | 3.23 % | 2.95 % | 4.35 % | 3.84 % | 11.2 % | 11.1 % |
| 0.8 a 0.9 | 3.56 % | 3.23 % | 7.65 % | 7.26 % | 21.7 % | 22.9 % |
| 0.9 a 1.0 | 2.15 % | 1.71 % | 25.60 % | 25.85 % | 43.9 % | 43.3 % |

Estratos de probabilidad, prueba de 2025 contra confirmación:

| Probabilidad | Peso en la prueba | Peso en el conjunto | Tasa de riesgo en la prueba | Tasa de riesgo en el conjunto | Horas en riesgo en la prueba | Horas en riesgo en el conjunto |
|---|---|---|---|---|---|---|
| 0.0 a 0.1 | 61.14 % | 57.59 % | 0.03 % | 0.04 % | 1.5 % | 1.6 % |
| 0.1 a 0.2 | 9.42 % | 8.99 % | 0.28 % | 0.23 % | 2.1 % | 1.5 % |
| 0.2 a 0.3 | 5.73 % | 5.63 % | 0.49 % | 0.45 % | 2.3 % | 1.8 % |
| 0.3 a 0.4 | 4.51 % | 4.61 % | 0.78 % | 0.69 % | 2.8 % | 2.2 % |
| 0.4 a 0.5 | 3.59 % | 3.92 % | 1.28 % | 1.04 % | 3.7 % | 2.9 % |
| 0.5 a 0.6 | 3.44 % | 3.85 % | 1.52 % | 1.48 % | 4.2 % | 4.0 % |
| 0.6 a 0.7 | 3.23 % | 3.87 % | 2.56 % | 2.56 % | 6.6 % | 7.0 % |
| 0.7 a 0.8 | 3.23 % | 4.03 % | 4.35 % | 3.45 % | 11.2 % | 9.7 % |
| 0.8 a 0.9 | 3.56 % | 4.78 % | 7.65 % | 7.06 % | 21.7 % | 23.7 % |
| 0.9 a 1.0 | 2.15 % | 2.72 % | 25.60 % | 23.97 % | 43.9 % | 45.7 % |

## Estaciones de la referencia y estaciones nuevas

Mismas métricas en cada conjunto del periodo actual, separando las estaciones que existían en el entrenamiento del modelo de las que se abrieron después.

| Conjunto | Estaciones | Número de estaciones | Filas | Horas en riesgo | Tasa de riesgo | Tasa de alertas | Recall | Precisión | F1 | PR-AUC | Falsos positivos | Falsos negativos | Costo | Costo por mil horas-estación | Costo frente a no alertar |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Actual | Estaciones de la referencia | 368 | 1,598,592 | 18,152 | 1.14 % | 1.24 % | 0.355 | 0.326 | 0.339 | 0.312 | 13,333 | 11,717 | 71,918 | 44.99 | 0.792 |
| Actual | Estaciones nuevas | 44 | 23,577 | 44 | 0.19 % | 0.22 % | 0.182 | 0.151 | 0.165 | 0.090 | 45 | 36 | 225 | 9.54 | 1.023 |
| Evaluación | Estaciones de la referencia | 368 | 811,717 | 9,908 | 1.22 % | 1.37 % | 0.368 | 0.328 | 0.347 | 0.338 | 7,471 | 6,263 | 38,786 | 47.78 | 0.783 |
| Evaluación | Estaciones nuevas | 101 | 189,365 | 324 | 0.17 % | 0.19 % | 0.321 | 0.294 | 0.307 | 0.197 | 250 | 220 | 1,350 | 7.13 | 0.833 |
| Confirmación | Estaciones de la referencia | 367 | 272,013 | 4,628 | 1.70 % | 2.13 % | 0.381 | 0.304 | 0.338 | 0.335 | 4,038 | 2,864 | 18,358 | 67.49 | 0.793 |
| Confirmación | Estaciones nuevas | 102 | 74,762 | 319 | 0.43 % | 0.52 % | 0.361 | 0.296 | 0.325 | 0.230 | 274 | 204 | 1,294 | 17.31 | 0.811 |
