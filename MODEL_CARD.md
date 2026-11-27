# Model Card: modelos de MiBici en producción

Tarjeta de los modelos que el proyecto integrador del Equipo 38 tiene en producción en el Model Registry de MLflow, en el formato de Mitchell et al. (2019). El modelo central es el de P2, el riesgo de que una estación se llene o se vacíe, porque es el que sirve la API y el que se monitorea; P1 y P3 se documentan con el mismo formato donde difieren. Todas las cifras salen del registry del equipo (`mlflow.db` y `mlartifacts/`, que no se versionan), de las corridas del experimento `mibici-equipo38` o de los reportes de `reports/`, y cada tabla dice de dónde viene.

Estado del registry al 27 de noviembre de 2026.

## Resumen

| Pregunta | Modelo registrado | Versión `champion` (producción) | Versión `challenger` | Métrica de decisión del `champion` | Cómo se sirve |
|---|---|---|---|---|---|
| P1, demanda diaria por estación (regresión) | `mibici-equipo38-p1-demanda` | 1, `HistGradientBoostingRegressor` | 2, `RandomForestRegressor` | `test_mae` 5.979 viajes por estación y día (*baseline* 7.275) | Por lotes con `python -m mibici.modeling.predict --pregunta p1` |
| P2, riesgo de llenado o vaciado en las dos horas siguientes (clasificación) | `mibici-equipo38-p2-riesgo` | 1, `HistGradientBoostingClassifier` balanceado con umbral fijo de 0.92 | 3, la misma receta reentrenada con datos hasta mayo de 2026, umbral 0.94 | `test_costo` 26,432 (*baseline* 28,170); recall 0.376, precisión 0.315, PR-AUC 0.334 | En línea con la API de FastAPI (`POST /predecir` y `POST /predecir/lote`) |
| P3, grupos de estaciones por perfil de uso (*clustering*) | `mibici-equipo38-p3-grupos` | 1, PCA de 10 componentes y `KMeans` con k = 4 | 2, `KMeans` con k = 3 | `train_silhouette` 0.085 y lectura operativa de los cuatro grupos | A mano, para planeación |

## 1. Detalles del modelo

- Desarrollo: Equipo 38 de Operaciones de aprendizaje automático (TC5061), Tecnológico de Monterrey. Los integrantes y sus aportes están en el [README](README.md#equipo-y-aportes).
- Tipo: modelos de scikit-learn 1.9.1 con Python 3.14.2, registrados con el *flavor* `mlflow.sklearn`, serializados con `skops` y guardados con su firma y un ejemplo de entrada. Las versiones de octubre se registraron con MLflow 3.16.1 y la versión 3 de P2 con MLflow 3.17.2, que es la del servidor del sistema.
- Ciclo de vida: alias, no etapas (todas las versiones tienen `current_stage` en `None`). `champion` es la versión en producción, la que cargan la API y `predict.py` con `models:/<nombre>@champion`; `challenger` es la siguiente candidata. Promover o revertir es mover el alias, sin crear versiones nuevas.
- Linaje: `mibici/modeling/registry.py` registra cada versión con las etiquetas `experimento`, `run_id`, `corrida`, `commit_git`, `rama`, `version_datos`, `modelo`, `metrica_decision` y su valor (y `threshold` en P2), y repite la corrida, el commit, los datos y la partición en la descripción de la versión. Cada corrida guarda además `config/` con las constantes y argumentos, `data/manifiesto.json` y el conjunto de entrenamiento con `mlflow.log_input`.
- Licencia y datos: el código es un trabajo académico; los datos son los datos abiertos de MiBici, sujetos a los [términos y condiciones](https://mibici.net/es/termino-y-condiciones/) del portal.

### Versiones y linaje

Del registry real (`registered_models`, `model_versions`, sus etiquetas y las corridas de origen). Todas las corridas son del experimento `mibici-equipo38`, con semilla 42; las fechas son hora del centro de México.

| Modelo y versión | Alias | Registrada | Corrida (`run_id`) | Algoritmo e hiperparámetros | Datos (`version_datos`) | Commit y rama de origen |
|---|---|---|---|---|---|---|
| `mibici-equipo38-p1-demanda` v1 | `champion` | 22 oct 2026 | `p1_hgb_mejor` (`2dc9201d1dcc4f06b70b072c5f74214b`), mejor hija de la búsqueda `p1_busqueda_hgb` | `HistGradientBoostingRegressor`, `learning_rate` 0.05, 300 iteraciones, `max_depth` 4 | `7aa5e436d887` | `bf9e9a3`, `feat/mlflow-project-registry` (PR #5) |
| `mibici-equipo38-p1-demanda` v2 | `challenger` | 22 oct 2026 | `p1_bosque` (`b6c002546bb84310aef209017f03a990`) | `RandomForestRegressor`, 300 árboles, `min_samples_leaf` 5 | `7aa5e436d887` | `bf9e9a3`, `feat/mlflow-project-registry` |
| `mibici-equipo38-p2-riesgo` v1 | `champion` | 22 oct 2026 | `p2_hgb_mejor` (`59bb5baa6e9f45d1b35a99646fd44986`), mejor hija de la búsqueda `p2_busqueda_hgb` | `HistGradientBoostingClassifier` con `class_weight="balanced"`, `learning_rate` 0.1, 200 iteraciones, sin límite de profundidad, dentro de `FixedThresholdClassifier` con umbral 0.92 elegido en validación | `7aa5e436d887` | `bf9e9a3`, `feat/mlflow-project-registry` |
| `mibici-equipo38-p2-riesgo` v2 | sin alias (`alias_anterior=challenger`, `relevada_por=3`) | 22 oct 2026 | `p2_bosque` (`e799ac8936184423968a97fc10506f39`) | `RandomForestClassifier` balanceado, 200 árboles, `min_samples_leaf` 50, umbral 0.88 | `7aa5e436d887` | `bf9e9a3`, `feat/mlflow-project-registry` |
| `mibici-equipo38-p2-riesgo` v3 | `challenger` | 15 nov 2026 | `p2_hgb_reentrenado` (`d504bab23035431e94f0bd1cf3482693`) | La receta de la v1 (`receta_de_la_version=1`) con datos de 2025-01-01 a 2026-05-31, umbral 0.94 elegido con junio de 2026 | `7aa5e436d887+f396cd21ea7d` | `6b5fdbf`, `feat/monitoreo-drift` (PR #14) |
| `mibici-equipo38-p3-grupos` v1 | `champion` | 22 oct 2026 | `p3_kmeans_pca_k4` (`8114cfc0d6964e319bb0aca7fac5871e`) | `StandardScaler`, PCA de 10 componentes y `KMeans` con k = 4 | `7aa5e436d887` | `bf9e9a3`, `feat/mlflow-project-registry` |
| `mibici-equipo38-p3-grupos` v2 | `challenger` | 22 oct 2026 | `p3_kmeans_mejor` (`bffea648191349bf85d23a3fbaad1d2d`), mejor hija de `p3_busqueda_k` | `KMeans` con k = 3 | `7aa5e436d887` | `bf9e9a3`, `feat/mlflow-project-registry` |

Las versiones 1 y 3 de P2 llevan además las etiquetas del A/B (`abtest_run_id` de la corrida `p2_abtest_v1_v3` y, en la 3, `abtest_decision` con «mantener la versión vigente»), y la 3 las de su origen (`entrega`, `origen=reentrenamiento`, `periodo_entrenamiento`, `periodo_validacion` y `periodo_evaluacion`).

### Arquitectura del modelo de P2

`Pipeline` de scikit-learn con un `ColumnTransformer` (`StandardScaler` sobre once columnas y `OneHotEncoder` sobre `hora_dia` y `dia_semana`) y el `HistGradientBoostingClassifier`, envuelto en `FixedThresholdClassifier(FrozenEstimator(...))`: el umbral viaja dentro del modelo registrado, así que `predict` ya devuelve la decisión y lo que se despliega es exactamente lo que se evaluó. Pesa 0.70 MB, tardó 60.7 s en ajustarse con 2.3 millones de filas y 2.6 s en predecir las 536,089 de prueba (métricas `tamano_modelo_mb`, `tiempo_entrenamiento_s` y `tiempo_inferencia_s` de la corrida).

Entradas (las 13 columnas de la firma, `float32`, en este orden): `salidas_h0`, `llegadas_h0`, `salidas_h1`, `llegadas_h1`, `salidas_h2`, `llegadas_h2` (salidas y llegadas de la estación en la hora t y en las dos anteriores), `neto_3h` (llegadas menos salidas de esas tres horas), `neto_futuro_semana_anterior` y `riesgo_semana_anterior` (flujo de las dos horas siguientes y etiqueta a la misma hora de la semana anterior), `hora_dia`, `dia_semana`, `fin_de_semana` y `capacidad` (anclajes). Salida: `riesgo` (0 o 1) y `probabilidad`; la API agrega el umbral y el nombre, la versión y el alias del modelo que respondió.

## 2. Uso previsto

### Usos primarios

- P2: apoyar al equipo de rebalanceo de MiBici en la decisión de cada hora, a qué estaciones mandar el camión porque en las dos horas siguientes tienden a llenarse o a vaciarse. Una alerta prioriza una visita; no la ordena.
- P1: estimar los viajes que iniciarán en cada estación al día siguiente para dimensionar flota y personal.
- P3: describir qué estaciones comparten un perfil horario de uso, como insumo de planeación para ampliar o reubicar estaciones.

### Usuarios previstos

El operador del sistema y su equipo de rebalanceo (P1 y P2) y el área de planeación (P3), con conocimiento de la operación para revisar cada recomendación.

### Fuera de alcance

- Decidir sin revisión humana. Con el umbral de 0.92, cerca de dos de cada tres alertas de P2 no corresponden a un riesgo real (precisión 0.315 en prueba) y casi dos de cada tres horas en riesgo no se anticipan (recall 0.376).
- Conocer el inventario de bicicletas o de anclajes libres: los datos abiertos no lo publican y la etiqueta de P2 es una aproximación con los viajes y la capacidad (sección 6).
- Evaluar, perfilar o tomar decisiones sobre personas usuarias. Los modelos no reciben datos personales y predicen por estación.
- Horizontes distintos a los entrenados (más de dos horas en P2, más de un día en P1), otros sistemas de bicicleta o datos que no se calculen con `mibici/features.py`.
- Condiciones fuera de lo que vio el entrenamiento: la API acepta cualquier `capacidad` mayor que cero, pero el entrenamiento solo tuvo estaciones de 11 a 39 anclajes y hasta 205 salidas por hora.

## 3. Factores

### Factores relevantes

- Antigüedad de la estación. El sistema pasó de 369 estaciones en el entrenamiento de P2 a 469 en el tercer trimestre de 2026; las estaciones nuevas tienen poco historial de flujo y muy pocas horas en riesgo.
- Hora del día, día de la semana y fin de semana: el riesgo se concentra en ciertas horas, y por eso son entradas del modelo.
- Temporada: la tasa de horas en riesgo cambia de un mes a otro (de 1.81 % en el entrenamiento a 1.25 % en noviembre y diciembre de 2025 y 0.88 % en julio de 2026).
- Capacidad de la estación, que define cuándo un flujo neto es riesgo.
- Zona de la ciudad, que se relaciona con el tipo de uso (los grupos de P3).

### Factores de evaluación

Se evaluó P2 por periodo (cada mes de octubre de 2025 a octubre de 2026) y por antigüedad de la estación (estaciones de la referencia contra estaciones abiertas después), en `reports/monitoreo/desempeno.md`. No se desagregó por zona, por capacidad ni por hora del día; queda como recomendación (sección 11).

## 4. Métricas

| Pregunta | Métrica de decisión | Otras métricas | Por qué |
|---|---|---|---|
| P1 | `test_mae`, viajes por estación y día | `test_rmse`, y las mismas en validación | El error absoluto se lee directo como bicicletas o personas de más o de menos por estación |
| P2 | `test_costo` = falsos positivos + 5 × falsos negativos | Recall, precisión, F1, PR-AUC, costo por mil horas-estación y costo frente a no alertar | Una estación que se queda sin servicio sin aviso (falso negativo) se valúa en cinco viajes de camión de más (falso positivo); `COSTO_FALSO_NEGATIVO` vive en `mibici/config.py` |
| P3 | `train_silhouette` | `train_davies_bouldin` e inercia, en el espacio escalado de las 98 variables | No hay etiqueta; la silueta compara la separación de los grupos y la decisión final se toma con su lectura operativa |

- Umbral de decisión de P2. No es 0.5: se elige en validación como el valor de 0.01 a 0.99 que minimiza el costo (`elegir_umbral` en `mibici/modeling/train.py`) y queda dentro del modelo. Para la v1 resultó 0.92 con octubre de 2025.
- Costo frente a no alertar. Es el costo dividido entre el de no emitir ninguna alerta (5 por cada hora en riesgo). Vale 1 cuando el modelo no aporta nada y no depende de cuántas horas en riesgo tiene el periodo, por eso es la métrica que se compara entre meses.
- Variación. En el A/B, los intervalos de 95 % salen de 2,000 réplicas de *bootstrap* por bloques de un día con los mismos días para las dos versiones, y la diferencia de aciertos se prueba con McNemar sobre los pares discordantes.

## 5. Datos de evaluación

| Conjunto | Periodo | Horas-estación | Horas en riesgo | Uso |
|---|---|---|---|---|
| Validación | Octubre de 2025 | 273,230 | 4,989 (1.83 %) | Elegir el umbral de la v1 |
| Prueba | Noviembre y diciembre de 2025 | 536,089 | 6,718 (1.25 %) | Comparar candidatas y *baselines*; métrica de decisión del registro |
| Actual | Enero a junio de 2026 | 1,622,169 | 18,196 (1.12 %) | Periodo en producción contra el que se mide el *drift* |
| Evaluación | Julio a septiembre de 2026 | 1,001,082 | 10,232 (1.02 %) | Conjunto del A/B: ninguna versión lo usó para entrenar ni para elegir su umbral |
| Confirmación | Octubre de 2026 | 346,775 | 4,947 (1.43 %) | Último mes publicado; fuera de la regla del A/B |

Los periodos de 2026 vienen de la ingesta del periodo actual (`data/manifiesto_actual.json`, `version_datos` `f396cd21ea7d`): diez meses con 3,997,597 registros, de los que quedan 3,840,981 viajes válidos con la misma `limpiar_viajes` de 2025. P1 se evalúa en los mismos dos meses de prueba (22,399 pares estación-día) y P3 no tiene conjunto de prueba.

## 6. Datos de entrenamiento

- Fuente: [datos abiertos de MiBici](https://mibici.net/es/datos-abiertos/), el sistema de bicicleta pública del Área Metropolitana de Guadalajara. Viajes de los doce meses de 2025 (4,532,032 registros en 393.1 MB) y la nomenclatura de 484 estaciones con su ubicación y capacidad. `data/manifiesto.json` guarda la URL, el tamaño y la suma SHA-256 de cada archivo; la versión de los datos es `7aa5e436d887`.
- Limpieza: quedan 4,414,800 viajes válidos entre 371 estaciones; se descartan 117,226 viajes de menos de un minuto y 6 de más de 24 horas. `Usuario_Id`, `Genero` y `Año_de_nacimiento` se eliminan en la ingesta.
- Partición temporal: entrenamiento del 1 de enero al 30 de septiembre de 2025, validación en octubre y prueba en noviembre y diciembre. Todas las variables usan información anterior al momento de la predicción.
- Etiqueta de P2: una estación está en riesgo en la hora t si en la ventana de las dos horas siguientes el flujo neto acumulado (llegadas menos salidas) alcanza la mitad de su capacidad en cualquiera de los dos sentidos (`UMBRAL_RIESGO = 0.5` y `VENTANA_RIESGO_HORAS = 2`). Es una aproximación: sin inventario por estación, mide la tendencia a llenarse o vaciarse, no el evento.
- Tamaños registrados en las corridas: P2 con 2,340,156 horas-estación de entrenamiento y 42,327 en riesgo (1.81 %); P1 con 95,035 pares estación-día; P3 con 369 estaciones con al menos 100 viajes y 98 variables (proporción de salidas y llegadas por hora en días hábiles y en fin de semana, volumen y proporción de salidas).
- Corrección posterior: la rama `fix/features-particion-perfiles` (PR #6) excluye las horas cuya ventana de dos horas cruza el corte siguiente; se integró después de las corridas para que su `commit_git` reproduzca lo que se midió. Con el código actual el entrenamiento de P2 tiene 2,339,422 filas y la validación 272,496 (734 menos en cada uno), con las mismas 42,327 horas en riesgo; es la referencia que usa el monitoreo.
- Versión 3 de P2: 4,488,274 horas-estación del 1 de enero de 2025 al 31 de mayo de 2026 (69,636 en riesgo, 1.55 %) y validación con las 280,336 de junio de 2026.

## 7. Análisis cuantitativo

### P2 en la prueba de 2025

Métricas de las corridas del experimento (noviembre y diciembre de 2025, 6,718 horas en riesgo). No alertar nunca costaría 33,590.

| Corrida | Modelo | Recall | Precisión | PR-AUC | Falsos positivos | Falsos negativos | `test_costo` | Costo frente a no alertar |
|---|---|---|---|---|---|---|---|---|
| `p2_baseline_dummy` | Estratificado | | | 0.013 | | | 42,594 | 1.268 |
| `p2_baseline_regla_semana` | Riesgo de la misma hora de la semana anterior | 0.320 | 0.287 | 0.101 | | | 28,170 | 0.839 |
| `p2_regresion_logistica` | Logística balanceada, umbral 0.92 | 0.373 | 0.232 | 0.207 | | | 29,369 | 0.874 |
| `p2_bosque` (v2) | Bosque balanceado, umbral 0.88 | 0.383 | 0.296 | 0.328 | 6,129 | 4,145 | 26,854 | 0.799 |
| `p2_hgb_mejor` (v1, `champion`) | HGB balanceado, umbral 0.92 | 0.376 | 0.315 | 0.334 | 5,487 | 4,189 | 26,432 | 0.787 |

El `champion` cuesta 6.2 % menos que la regla de la semana anterior y 37.9 % menos que el *baseline* estratificado, con la mejor PR-AUC; frente al bosque, cuesta 422 menos y pesa unas 275 veces menos (0.70 contra 191.9 MB). En validación (octubre de 2025) tuvo recall 0.397, precisión 0.376 y costo 18,323.

### P2 en producción, 2026

`reports/monitoreo/desempeno.md`, versión 1 con su umbral de 0.92.

| Conjunto | Recall | Precisión | PR-AUC | Costo por mil horas-estación | Costo frente a no alertar |
|---|---|---|---|---|---|
| Prueba de 2025 | 0.376 | 0.315 | 0.334 | 49.31 | 0.787 |
| Actual (enero a junio de 2026) | 0.354 | 0.325 | 0.311 | 44.47 | 0.793 |
| Evaluación (julio a septiembre de 2026) | 0.366 | 0.327 | 0.334 | 40.09 | 0.785 |
| Confirmación (octubre de 2026) | 0.380 | 0.304 | 0.329 | 56.67 | 0.795 |

Mes a mes, el costo frente a no alertar queda entre 0.757 y 0.802 de noviembre de 2025 a octubre de 2026, salvo junio de 2026: recall 0.302 (19.8 % menos que en la prueba), precisión 0.261, PR-AUC 0.245 y costo frente a no alertar 0.869 (10.4 % más). Enero de 2026 perdió 11.8 % de recall con el costo casi intacto (0.798).

### P2 por antigüedad de la estación

| Conjunto | Estaciones | Número | Horas en riesgo | Recall | Precisión | Costo frente a no alertar |
|---|---|---|---|---|---|---|
| Actual | De la referencia | 368 | 18,152 (1.14 %) | 0.355 | 0.326 | 0.792 |
| Actual | Nuevas | 44 | 44 (0.19 %) | 0.182 | 0.151 | 1.023 |
| Evaluación | De la referencia | 368 | 9,908 (1.22 %) | 0.368 | 0.328 | 0.783 |
| Evaluación | Nuevas | 101 | 324 (0.17 %) | 0.321 | 0.294 | 0.833 |
| Confirmación | De la referencia | 367 | 4,628 (1.70 %) | 0.381 | 0.304 | 0.793 |
| Confirmación | Nuevas | 102 | 319 (0.43 %) | 0.361 | 0.296 | 0.811 |

En las estaciones nuevas el modelo rinde peor: de enero a junio cuesta más que no alertar (1.023), y la brecha se cierra conforme acumulan historial (0.833 de julio a septiembre y 0.811 en octubre). Las estaciones nuevas pasaron de 1.45 % de las horas-estación en el primer semestre a 18.9 % en el tercer trimestre.

### P1 y P3

| Pregunta | Corrida | Métricas de prueba o de entrenamiento | Comparación |
|---|---|---|---|
| P1 | `p1_hgb_mejor` (v1, `champion`) | `test_mae` 5.979 y `test_rmse` 10.445 (validación: 5.259 y 9.014); 0.51 MB y 0.9 s de ajuste | 17.8 % menos MAE que el valor de hace siete días (`naive7`, 7.275). El bosque (v2) logra 5.926, 0.9 % menos, con un modelo de 414 MB y 17 veces más tiempo de ajuste |
| P3 | `p3_kmeans_pca_k4` (v1, `champion`) | `train_silhouette` 0.085, `train_davies_bouldin` 2.330; grupos de 142, 92, 120 y 15 estaciones | Mejor silueta entre las candidatas con k = 4 (`kmeans` 0.084 y aglomerativo 0.071). k = 3 (v2) llega a 0.095, pero pierde la lectura de los cuatro perfiles y queda pendiente de validar con planeación |

## 8. Monitoreo

El modelo de P2 se vigila con los datos que el portal publica después del entrenamiento (`mibici/monitoreo/`, punto de entrada `monitor` del `MLproject`, reportes en `reports/monitoreo/`).

### Drift con Evidently

- Configuración: Evidently 0.7.23 sobre 16 columnas (las 13 entradas, la etiqueta `riesgo` y la probabilidad y la clase del modelo), con distancia de Wasserstein normalizada en las diez numéricas y de Jensen-Shannon en las seis categóricas. Una columna deriva cuando su estadístico llega a 0.1 y el conjunto deriva cuando lo hace al menos la mitad de las columnas (8 de 16). Con millones de filas una prueba de hipótesis rechazaría la igualdad en todo, así que se usa una distancia con umbral fijo en el código.
- Referencia contra el semestre actual (enero a junio de 2026): 0 de 16 columnas con deriva; las mayores son `neto_3h` (0.082), `probabilidad` (0.079) y `neto_futuro_semana_anterior` (0.078). Las comparaciones de control (mismos meses de 2025 contra 2026, solo estaciones de la referencia y cambio de temporada dentro de 2025) tampoco marcan deriva.
- Mes a mes: mayo de 2026 es el primer mes con deriva del conjunto (8 de 16: las seis de flujo, `neto_3h` y `probabilidad`), agosto la repite con 9 y octubre queda en 7. `capacidad` cruza el umbral desde septiembre por la expansión del sistema.
- Objetivo y predicción: la tasa de horas en riesgo cae de 1.81 % a 1.12 % (38 % menos) y el modelo la acompaña (alertas de 1.87 % a 1.22 %). Evidently la mide en 0.020 porque la distancia de una clase rara queda pequeña, así que el objetivo se vigila con la tasa y con el desempeño, no solo con el veredicto.
- *Data drift* o *concept drift*: con estratos de 0.1 de probabilidad, 94 % de la caída de la tasa en el semestre se explica por la mezcla de entradas y la misma probabilidad conserva la misma frecuencia de riesgo (25.6 % en el estrato más alto en la prueba y 26.1 % en el semestre). En octubre de 2026 el efecto condicional va en sentido contrario (-0.126 puntos), el indicio de *concept drift* que se sigue.

### A/B testing entre versiones

`mibici/modeling/abtest.py` compara la v1 (`champion`) contra la v3 (`challenger`) en las mismas 1,001,082 horas-estación de julio a septiembre de 2026, con una regla escrita antes de registrar la v3: B se promueve solo si el intervalo de 95 % de la diferencia de costo por mil horas-estación queda completo bajo cero y el límite inferior del intervalo de la diferencia de recall no baja de -0.01.

| Métrica | v1 | v3 | v3 menos v1 (IC de 95 %) |
|---|---|---|---|
| Recall | 0.3664 | 0.3258 | -0.0406 (-0.0448 a -0.0358) |
| Precisión | 0.3269 | 0.4074 | +0.0805 (+0.0740 a +0.0871) |
| PR-AUC | 0.3338 | 0.3474 | +0.0136 |
| Falsos positivos y negativos | 7,721 y 6,483 | 4,850 y 6,898 | -2,871 y +415 |
| Costo por mil horas-estación | 40.09 | 39.30 | -0.80 (-1.08 a -0.51) |

Decisión: la condición de costo se cumple y la de recall no, así que `champion` sigue en la v1 y la v3 conserva `challenger` (corrida `p2_abtest_v1_v3`; las dos versiones quedaron anotadas). McNemar confirma que las diferencias no son azar (valor p menor que 0.001), la simulación con tráfico dividido al 50 % da el mismo signo (-1.72 por mil, IC de -3.31 a -0.18) y octubre de 2026 lo sostiene (-1.06 por mil y recall -0.0542). El análisis posterior muestra que la v3 ordena mejor las horas y que su pérdida de recall viene del umbral, elegido con un solo mes atípico (junio de 2026): con el umbral que iguala el recall de la v1 (0.9279) cuesta 0.79 menos por mil horas-estación.

### Regla de Continuous Training

Cada mes, cuando el portal publica el mes anterior, se corre `monitor`. Cualquiera de estos disparadores lanza el reentrenamiento (`reentrenar`) con la receta del `champion`:

1. Deriva del conjunto en el reporte mensual de Evidently: al menos 8 de las 16 columnas sobre 0.1 (ocurrió en mayo y agosto de 2026).
2. Costo frente a no alertar del mes más de 5 % por encima del de la prueba, es decir, sobre 0.826 (solo junio de 2026, con 0.869).
3. Estaciones que el modelo no vio en su entrenamiento con más de 5 % de las horas-estación del mes (1.45 % en el primer semestre y 18.9 % en el tercer trimestre de 2026).

La nueva versión entra como `challenger`, se compara con `abtest` sobre los meses siguientes y solo la regla mueve el alias (`-P promote=1`); la versión anterior conserva su registro para revertir con un comando. La tasa de riesgo sola no es disparador, porque cayó 38 % sin que el modelo perdiera desempeño. Para el siguiente candidato, el umbral se elige con tres meses de validación en lugar de uno.

## 9. Costo (FinOps)

`mibici/finops/costo.py` calcula el costo por inferencia con la capacidad medida en la prueba de carga con Locust (`reports/carga/`) y el precio por hora de la instancia, que llega como parámetro: precio por hora / (inferencias por segundo dentro del objetivo × 3,600). Objetivo de servicio: p95 de hasta 500 ms y errores de hasta 1 %. Precios de AWS bajo demanda en el norte de Virginia consultados el 18 de noviembre de 2026: t3.small (2 vCPU y 2 GiB) a 0.0208 dólares por hora y c6a.large (2 vCPU y 4 GiB) a 0.0765.

| Concepto | Valor medido | Fuente |
|---|---|---|
| Capacidad con un proceso, 1 CPU y una petición a la vez (`API_HILOS=1`, la configuración por omisión) | 20 a 30 peticiones por segundo dentro del objetivo, p95 de 108 a 313 ms, sin errores con 60 usuarios | `reports/carga/resumen.md` |
| Misma CPU con los 40 hilos de Starlette | 8 a 15 peticiones por segundo | `reports/carga/resumen.md` |
| Memoria del servicio | 217 a 252 MiB de 1 GiB con un proceso | `reports/carga/resumen.md` |
| Costo por millón de predicciones a plena capacidad en t3.small | 0.13 a 0.20 dólares con `API_HILOS=1`; 0.0015 a 0.0031 con lotes de 472 estaciones | `reports/carga/costo.md` |
| Instancia t3.small siempre encendida | 15.18 dólares al mes, 44.07 por millón de predicciones con la demanda real (472 por hora) | `reports/carga/costo.md` |
| Encendido solo para la predicción de cada hora | 0.25 a 0.34 dólares al mes, 97.7 % a 98.3 % menos | `reports/carga/costo.md` |
| Reentrenamiento de la v3 | 95.5 s de ajuste con 4.5 millones de filas y un modelo de 0.66 MB | Corrida `p2_hgb_reentrenado` |

La demanda real de MiBici (una predicción por estación y hora) ocupa entre 0.003 % y 1.1 % de lo que el sistema atiende, así que el costo lo decide el tiempo ocioso, no la inferencia. Las decisiones que sostienen el costo: una petición a la vez por proceso, el lote de la hora completa en `/predecir/lote`, la instancia de 2 GiB (el sistema completo usa de 0.65 a 0.92 GiB) y el servidor de MLflow sin consumidores de trabajos (de 1,005 a unos 430 MiB). Reentrenar cuesta poco frente a evaluar.

## 10. Consideraciones éticas

- Datos personales: la ingesta descarta `Usuario_Id`, `Genero` y `Año_de_nacimiento`, y ninguna tabla, artefacto, parámetro ni etiqueta los contiene. Las tablas de entrenamiento son conteos agregados por estación y hora o día, y ningún modelo toma decisiones sobre personas.
- Equidad territorial: el modelo decide a qué estaciones llega primero el camión. Las estaciones nuevas, que suelen estar en las zonas de expansión, tienen menos historial y peor desempeño (recall 0.182 contra 0.355 en el primer semestre de 2026). Una operación que siguiera solo las alertas atendería peor a esas zonas; por eso las estaciones nuevas son un disparador de reentrenamiento y se reportan por separado.
- Asimetría de costos: la proporción de cinco falsos positivos por un falso negativo es un supuesto operativo, no una medición. Fija el umbral (0.92) y con él cuántas horas en riesgo quedan sin aviso; si la operación valora distinto el servicio perdido, el umbral debe recalcularse con `COSTO_FALSO_NEGATIVO`.
- Etiqueta aproximada: el riesgo se infiere del flujo neto contra la mitad de la capacidad, no del inventario real. Una alerta indica tendencia, no certeza, y el equipo de rebalanceo conserva la decisión.
- Transparencia y trazabilidad: cada respuesta de la API dice qué modelo, versión, alias y umbral la produjeron, y cada versión del registry se rastrea hasta su corrida, su commit y su versión de datos.
- Uso de datos abiertos: se respetan los términos del portal de MiBici y los datos no se redistribuyen en el repositorio.

## 11. Advertencias y recomendaciones

- La precisión y el recall de P2 están acotados por los datos: 0.65 % de las horas de la muestra de entrenamiento comparten las trece variables con otra hora de etiqueta contraria (`reports/deepchecks/resumen.md`). Es ruido irreducible con estas entradas; mejorar requiere variables nuevas (inventario, clima, eventos), no otro algoritmo.
- P1 trata `mes` como numérico y la prueba (noviembre y diciembre) tiene meses que el entrenamiento no vio; conviene codificarlo de forma cíclica o retirarlo en la siguiente iteración.
- La silueta de P3 (0.085) indica grupos poco separados: sirven como resumen de perfiles para planeación, no como categorías naturales. Seis columnas del perfil son constantes (sin salidas de 2:00 a 4:59) y conviene excluirlas.
- Elegir el umbral con un solo mes lo vuelve sensible a meses atípicos, como mostró la v3; en el siguiente ciclo se usan tres meses.
- Desagregar el desempeño de P2 por zona (por ejemplo con los grupos de P3), por capacidad y por hora del día, y validar la etiqueta contra el inventario real si el operador lo comparte.
- Repetir la prueba de carga en una máquina dedicada: se corrió en un portátil de uso general y el p95 de un mismo escalón varió hasta catorce veces entre repeticiones.

## Referencias

Mitchell, M., Wu, S., Zaldivar, A., Barnes, P., Vasserman, L., Hutchinson, B., Spitzer, E., Raji, I. D., & Gebru, T. (2019). Model cards for model reporting. *Proceedings of the Conference on Fairness, Accountability, and Transparency*, 220-229. https://doi.org/10.1145/3287560.3287596
