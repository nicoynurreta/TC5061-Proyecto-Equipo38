# A/B testing de P2: versión vigente contra versión reentrenada

Generado el 2026-11-15 08:57:15 con `python -m mibici.modeling.abtest` sobre la tabla de monitoreo (`data/interim/monitoreo_p2.parquet`). Las dos versiones se cargan del Model Registry (`mibici-equipo38-p2-riesgo`) y predicen las mismas horas-estación con el umbral de decisión que cada una lleva dentro.

|  | Versión | Alias al evaluar | Corrida | Entrenamiento | Umbral | Datos |
|---|---|---|---|---|---|---|
| A | 1 | champion | `p2_hgb_mejor` | 2025-01-01 a 2025-09-30 | 0.92 | `7aa5e436d887` |
| B | 3 | challenger | `p2_hgb_reentrenado` | 2025-01-01 a 2026-05-31 | 0.94 | `7aa5e436d887+f396cd21ea7d` |

## Regla de decisión

La versión B se promueve a champion solo si, sobre el conjunto de evaluación, se cumplen las dos condiciones: (1) el intervalo de confianza de 95 % de la diferencia de costo por mil horas-estación (B menos A), calculado por bootstrap de bloques de un día sobre la comparación pareada, queda completo por debajo de cero; y (2) el límite inferior del intervalo de 95 % de la diferencia de recall (B menos A) no baja de -0.01. Si alguna falla, el alias champion no se mueve y la versión B conserva el alias challenger.

## Comparación pareada en el conjunto de evaluación

Conjunto de evaluación: del 2026-07-01 al 2026-09-30, 1,001,082 horas-estación en 92 días, con 10,232 horas en riesgo (1.02 %). Ninguna de las dos versiones usó este periodo para entrenar ni para elegir su umbral. Las dos versiones dan la misma clase en 99.60 % de las filas. Los intervalos salen de 2,000 réplicas de bootstrap por bloques de un día (semilla 42), con los mismos días para las dos versiones en cada réplica. El costo cuenta un falso positivo como 1 y un falso negativo como 5.

| Métrica | A, versión 1 | B, versión 3 | B menos A | IC de 95 % de B menos A |
|---|---|---|---|---|
| Recall | 0.3664 | 0.3258 | -0.0406 | -0.0448 a -0.0358 |
| Precisión | 0.3269 | 0.4074 | +0.0805 | +0.0740 a +0.0871 |
| F1 | 0.3455 | 0.3621 | +0.0166 | +0.0117 a +0.0214 |
| PR-AUC | 0.3338 | 0.3474 | +0.0136 |  |
| Alertas | 11,470 | 8,184 | -3,286 |  |
| Falsos positivos | 7,721 | 4,850 | -2,871 |  |
| Falsos negativos | 6,483 | 6,898 | +415 |  |
| Costo | 40,136 | 39,340 | -796 |  |
| Costo por mil horas-estación | 40.09 | 39.30 | -0.80 | -1.08 a -0.51 |
| Costo frente a no alertar | 0.7845 | 0.7690 | -0.0156 |  |

Prueba de McNemar sobre los pares discordantes (una versión acierta y la otra no):

| Subconjunto | Solo acierta A | Solo acierta B | Prueba | Estadístico | Valor p |
|---|---|---|---|---|---|
| Todas las horas-estación (acierto de la clase) | 786 | 3,242 | ji cuadrada con corrección de continuidad | 1496.28 | menor que 0.001 |
| Horas en riesgo (recall) | 509 | 94 | ji cuadrada con corrección de continuidad | 284.24 | menor que 0.001 |
| Horas sin riesgo (falsas alertas) | 277 | 3,148 | ji cuadrada con corrección de continuidad | 2404.93 | menor que 0.001 |

## Simulación de tráfico dividido

Cada hora-estación del conjunto de evaluación se asigna al azar a una versión (50 % a B, semilla 42) y solo se cuenta la respuesta de la versión asignada, como ocurriría al repartir el tráfico del servicio. Entre paréntesis, el intervalo de 95 % por bootstrap de bloques de un día.

| Brazo | Horas-estación | Horas en riesgo | Recall | Precisión | Costo por mil horas-estación |
|---|---|---|---|---|---|
| A, versión 1 | 500,340 | 5,154 | 0.3622 | 0.3239 | 40.64 |
| B, versión 3 | 500,742 | 5,078 | 0.3279 | 0.4072 | 38.92 |
| B menos A |  |  | -0.0344 (-0.0505 a -0.0186) | +0.0833 (+0.0665 a +0.0995) | -1.72 (-3.31 a -0.18) |

## Por mes

| Mes | Conjunto | Horas-estación | Horas en riesgo | Recall A | Recall B | Precisión A | Precisión B | Costo por mil A | Costo por mil B | B menos A |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-07 | Evaluación | 321,370 | 2,827 | 0.3682 | 0.3329 | 0.3190 | 0.4115 | 34.70 | 33.53 | -1.17 |
| 2026-08 | Evaluación | 342,752 | 3,337 | 0.3617 | 0.3221 | 0.3442 | 0.4226 | 37.78 | 37.28 | -0.50 |
| 2026-09 | Evaluación | 336,960 | 4,068 | 0.3690 | 0.3240 | 0.3194 | 0.3931 | 47.58 | 46.85 | -0.74 |
| 2026-10 | Confirmación | 346,775 | 4,947 | 0.3798 | 0.3257 | 0.3035 | 0.3823 | 56.67 | 55.61 | -1.06 |

## Confirmación fuera de la regla

Misma comparación pareada sobre el tramo posterior al conjunto de evaluación, del 2026-10-01 al 2026-10-31 (346,775 horas-estación en 31 días, 4,947 en riesgo). No entra en la regla; muestra si la diferencia se sostiene un mes después.

| Métrica | A, versión 1 | B, versión 3 | B menos A | IC de 95 % de B menos A |
|---|---|---|---|---|
| Recall | 0.3798 | 0.3257 | -0.0542 | -0.0638 a -0.0439 |
| Precisión | 0.3035 | 0.3823 | +0.0788 | +0.0691 a +0.0880 |
| F1 | 0.3374 | 0.3517 | +0.0143 | +0.0057 a +0.0222 |
| PR-AUC | 0.3288 | 0.3387 | +0.0099 |  |
| Alertas | 6,191 | 4,214 | -1,977 |  |
| Falsos positivos | 4,312 | 2,603 | -1,709 |  |
| Falsos negativos | 3,068 | 3,336 | +268 |  |
| Costo | 19,652 | 19,283 | -369 |  |
| Costo por mil horas-estación | 56.67 | 55.61 | -1.06 | -1.74 a -0.41 |
| Costo frente a no alertar | 0.7945 | 0.7796 | -0.0149 |  |

## Decisión

- Condición 1, costo: el intervalo de la diferencia de costo por mil horas-estación va de -1.08 a -0.51; se cumple.
- Condición 2, recall: el límite inferior de la diferencia de recall es -0.0448 frente al margen de -0.01; no se cumple.
- Resultado de la regla: mantener la versión A. El alias champion se queda en la versión 1 y la versión 3 conserva el alias challenger.

## Análisis posterior a la decisión: B con el recall de A

Este apartado no cambia la decisión. Separa lo que aporta el reentrenamiento de lo que cambia el umbral: se busca el umbral con que la versión B alcanza el recall de la versión A en el conjunto de evaluación (0.9279, frente a 0.94 con que está registrada) y se repite la comparación pareada con ese umbral. En la evaluación el umbral se eligió con sus propias etiquetas, así que esa fila es optimista; en la confirmación el umbral ya estaba fijo. Entre paréntesis, el intervalo de 95 % de la diferencia de costo por mil horas-estación.

| Conjunto | Recall A | Recall B | Precisión A | Precisión B | Alertas A | Alertas B | Costo por mil A | Costo por mil B | B menos A |
|---|---|---|---|---|---|---|---|---|---|
| Evaluación | 0.3664 | 0.3664 | 0.3269 | 0.3510 | 11,470 | 10,682 | 40.09 | 39.31 | -0.79 (-1.03 a -0.56) |
| Confirmación | 0.3798 | 0.3723 | 0.3035 | 0.3258 | 6,191 | 5,654 | 56.67 | 55.76 | -0.91 (-1.44 a -0.39) |
