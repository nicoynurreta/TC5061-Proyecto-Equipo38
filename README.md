# TC5061-Proyecto-Equipo38

Proyecto integrador de Operaciones de aprendizaje automático (TC5061) sobre los datos abiertos de [MiBici](https://mibici.net/es/datos-abiertos/), el sistema de bicicleta pública del Área Metropolitana de Guadalajara. Equipo 38.

Repositorio: https://github.com/nicoynurreta/TC5061-Proyecto-Equipo38

## Propósito

El proyecto responde tres preguntas sobre la operación de MiBici con un modelo de regresión, uno de clasificación y uno de *clustering*. La primera entrega dejó la base: ingesta reproducible y versionada de los viajes, módulo de *features*, experimento base en MLflow y flujo de trabajo con ramas y *Pull Requests*. La segunda entrega convierte el repositorio en un [MLflow Project](https://mlflow.org/docs/latest/ml/projects/) que se ejecuta con un solo comando, compara varias candidatas por pregunta contra ese experimento base (con una búsqueda de hiperparámetros organizada como *nested runs*), guarda en cada corrida los artefactos que respaldan su resultado y deja el mejor modelo de cada pregunta registrado y en producción en el [Model Registry](https://mlflow.org/docs/latest/ml/model-registry/).

## Las tres preguntas

| # | Pregunta | Tarea | Qué se predice o agrupa | Quién lo usa y qué decide |
|---|---|---|---|---|
| P1 | ¿Cuántos viajes se iniciarán en una estación en un periodo futuro? | Regresión | Viajes iniciados por estación y día, con horizonte de un día | El operador del sistema, para dimensionar la flota y el personal de cada estación |
| P2 | ¿Una estación estará en riesgo de quedarse sin bicicletas o sin anclajes disponibles? | Clasificación | Riesgo por estación y hora para las dos horas siguientes | El equipo de rebalanceo, para decidir a qué estaciones mandar el camión en la siguiente hora |
| P3 | ¿Qué grupos de estaciones comparten patrones de uso y dónde se ubican en la ciudad? | *Clustering* | Grupos de estaciones según su perfil horario de salidas y llegadas en días hábiles y fines de semana | Planeación urbana y expansión del sistema, para decidir dónde ampliar o reubicar estaciones |

Los datos no incluyen el inventario de bicicletas por estación, así que el riesgo de P2 se aproxima con los viajes y la capacidad: una estación está en riesgo en una hora dada si, en la ventana de las dos horas siguientes, el flujo neto acumulado (llegadas menos salidas) alcanza la mitad de su capacidad en cualquiera de los dos sentidos, es decir, si tiende a llenarse o a vaciarse. La fracción y la ventana son parámetros de `config.py` (`UMBRAL_RIESGO` y `VENTANA_RIESGO_HORAS`).

Por pregunta, el experimento compara el *baseline* de la primera entrega con varias candidatas y una búsqueda de hiperparámetros:

| # | *Baseline* | Candidatas | Búsqueda con *nested runs* | Métricas |
|---|---|---|---|---|
| P1 | Valor de hace siete días (`naive7`) | `hgb` (`HistGradientBoostingRegressor`), `bosque` (`RandomForestRegressor`), `ridge` (regresión lineal regularizada con día y mes codificados) y la mejor hija de la búsqueda | `learning_rate` {0.05, 0.1, 0.2} por `max_depth` {4, 8, sin límite} con 300 árboles | `val_mae`, `val_rmse`, `test_mae`, `test_rmse` (viajes por estación y día) |
| P2 | `dummy` (`DummyClassifier` estratificado) y `regla_semana` (riesgo si hubo riesgo a la misma hora de la semana anterior) | `regresion_logistica` balanceada, `bosque` (`RandomForestClassifier` balanceado), `hgb` (`HistGradientBoostingClassifier` balanceado) y la mejor hija de la búsqueda | `learning_rate` {0.05, 0.1} por `max_depth` {4, 8, sin límite} con 200 árboles | `recall`, `precision`, `f1`, `pr_auc`, falsos positivos, falsos negativos y `costo` (falsos positivos más cinco veces los falsos negativos), en validación y en prueba |
| P3 | `kmeans` con k = 4 | `aglomerativo` (ward, k = 4), `kmeans_pca` (PCA a 10 componentes y k = 4) y la mejor hija de la búsqueda | k de 3 a 8 con `kmeans` | `train_silhouette`, `train_davies_bouldin`, `train_inercia` (en el espacio escalado de las 98 variables, para que las tres candidatas sean comparables) |

Todas las corridas registran además `tiempo_entrenamiento_s`, `tiempo_inferencia_s` y `tamano_modelo_mb`, que son el costo de entrenar y de servir cada candidata. En P2 el umbral de decisión sobre la probabilidad (`threshold`) no es 0.5: cada candidata lo elige con el conjunto de validación como el valor que minimiza el costo esperado de los errores, con un falso negativo (una estación que se queda sin servicio sin aviso) valuado en cinco falsos positivos (un viaje de camión de más), y el umbral queda dentro del modelo registrado (`FixedThresholdClassifier` de scikit-learn), de modo que `predict` ya lo aplica. `COSTO_FALSO_NEGATIVO` también vive en `config.py`.

## Datos

- Fuente: portal de datos abiertos de MiBici, https://mibici.net/es/datos-abiertos/. Publica un archivo CSV de viajes por mes (`datos_abiertos_AAAA_MM.csv`) y la nomenclatura de estaciones (`nomenclatura_2026_09.csv`) con identificador, nombre, latitud, longitud y capacidad de cada estación. Las URL exactas de cada archivo quedan en `data/manifiesto.json`.
- Rango: los doce meses de 2025 (`FECHA_INICIO` y `FECHA_FIN` en `config.py`). Un año calendario completo cubre la estacionalidad semanal y anual, los doce archivos comparten las mismas columnas aunque cambian de codificación entre meses, y los meses de 2026 quedan como datos nuevos para las entregas siguientes.
- Tamaño real obtenido con la ingesta de los doce meses (`version_datos` `7aa5e436d887`): 12 archivos mensuales con 4,532,032 registros y 393.1 MB en CSV, más la nomenclatura con 484 estaciones. Después de la limpieza quedan 4,414,800 viajes válidos del 1 de enero al 31 de diciembre de 2025 (se descartan 117,226 viajes de menos de un minuto y 6 de más de 24 horas; no hay duplicados ni registros sin fecha o sin estación) entre 371 estaciones con viajes, todas presentes en la nomenclatura. `viajes.parquet` pesa 88.5 MB y la ingesta completa tarda alrededor de dos minutos.
- Variables originales que se usan: `Viaje_Id`, `Inicio_del_viaje`, `Fin_del_viaje`, `Origen_Id` y `Destino_Id` de los viajes; `id`, `name`, `latitude`, `longitude` y `dpcapacity` de la nomenclatura. La variable objetivo de P1 es el conteo de viajes iniciados por estación y día; la de P2 es la etiqueta de riesgo descrita arriba; P3 no tiene variable objetivo.
- Datos personales: `Usuario_Id`, `Genero` y `Año_de_nacimiento` se descartan en la ingesta y no llegan al Parquet, a las *features*, a los artefactos ni a MLflow. Las condiciones de uso del portal están en sus [términos y condiciones](https://mibici.net/es/termino-y-condiciones/).
- Partición temporal: entrenamiento de enero a septiembre, validación en octubre y prueba en noviembre y diciembre de 2025 (`FIN_ENTRENAMIENTO` y `FIN_VALIDACION` en `config.py`). Es la misma partición de la primera entrega, con las mismas métricas, para que la comparación contra el *baseline* sea válida. Todas las variables se calculan con información anterior al momento de la predicción.
- Versionado: `data/manifiesto.json` registra la URL, el tamaño en bytes y la suma de verificación SHA-256 de cada archivo crudo, el número de registros y la suma de cada Parquet, los descartes de la limpieza y la versión de los datos (`version_datos`, derivada de las sumas de los archivos crudos). Cada corrida registra esa versión como parámetro, guarda el manifiesto como artefacto y registra el conjunto de entrenamiento con `mlflow.log_input`. El manifiesto sí se versiona en Git; los datos no.

## Estructura del repositorio

Generada con [Cookiecutter Data Science](https://cookiecutter-data-science.drivendata.org/) (`ccds`, con `include_code_scaffold` en Yes).

```
├── Makefile           <- make server, ingest, baselines, candidatas, busquedas, corridas, registry, test
├── MLproject          <- puntos de entrada ingest, train y search para mlflow run
├── python_env.yaml    <- versión de Python y dependencias con versión fija para mlflow run
├── README.md
├── requirements.txt   <- dependencias con versión fija
├── pyproject.toml     <- metadatos del módulo mibici
├── data
│   ├── manifiesto.json <- versión de los datos (único archivo de data/ que se versiona)
│   ├── external
│   ├── interim
│   ├── processed      <- viajes.parquet y estaciones.parquet
│   └── raw            <- archivos CSV descargados del portal
├── models             <- predicciones de predict.py
├── notebooks          <- 1.0-mah-exploracion-mibici.ipynb, solo exploración
├── references         <- ML Canvas y diagrama de arquitectura
├── reports
│   └── figures        <- reservada para las figuras de las entregas siguientes; las gráficas son artefactos de MLflow
├── tests              <- pruebas con pytest
└── mibici
    ├── __init__.py
    ├── config.py      <- rutas, URL, rango de fechas, partición, umbrales, semilla, experimento, hiperparámetros y rejillas
    ├── dataset.py     <- ingesta: descarga, normalización, Parquet y manifiesto
    ├── features.py    <- features por pregunta y partición temporal
    ├── plots.py       <- gráficas que se registran como artefactos
    └── modeling
        ├── artefactos.py <- artefactos de cada corrida: plots/, data/, config/, log_input y modelo con firma
        ├── train.py      <- baseline o candidata de una pregunta, con sus métricas y artefactos
        ├── search.py     <- búsqueda de hiperparámetros con nested runs
        ├── registry.py   <- registro en el Model Registry con linaje y alias
        └── predict.py    <- predicción con el modelo en producción (models:/<nombre>@champion)
```

`data/raw/`, `data/processed/`, `models/`, `mlruns/`, `mlartifacts/`, `mlflow.db` y los archivos `.env` están en `.gitignore`: ni datos, ni base de datos de MLflow, ni modelos serializados entran al historial.

## Instalación

Probado con Python 3.14.2. Desde la raíz del repositorio:

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

En Linux o macOS el entorno se activa con `source venv/bin/activate`. `requirements.txt` fija la versión de cada dependencia e instala el módulo `mibici` en modo editable. Las pruebas se corren con `python -m pytest tests`.

## Servidor de tracking

El Model Registry necesita un almacén respaldado por una base de datos, así que las corridas no se registran en archivos sino en un servidor local con SQLite. Desde la raíz del repositorio, en una terminal propia:

```
mlflow server --backend-store-uri sqlite:///mlflow.db --port 5000
```

La base queda en `mlflow.db` y los artefactos en `mlartifacts/`, los dos en la raíz y fuera de Git. En la terminal donde se lanzan las corridas se apunta al servidor:

```
set MLFLOW_TRACKING_URI=http://127.0.0.1:5000
```

(en Linux o macOS, `export MLFLOW_TRACKING_URI=http://127.0.0.1:5000`). La interfaz queda en http://127.0.0.1:5000. Si la variable no está definida, `train.py` usa `mlflow.db` en la raíz como almacén directo, que sirve para probar pero no para el registro de modelos.

## MLflow Project

`MLproject` declara el entorno (`python_env.yaml`, con las mismas versiones fijas de `requirements.txt`) y tres puntos de entrada. Los valores por defecto de rutas, fechas, semilla, umbrales e hiperparámetros viven solo en `config.py`: los parámetros del proyecto que llegan vacíos los toma de ahí.

| Punto de entrada | Comando | Parámetros |
|---|---|---|
| `ingest` | `python -m mibici.dataset` | `months`: meses `AAAA-MM` separados por comas; vacío ingiere los doce meses de `config.MESES` |
| `train` | `python -m mibici.modeling.train` | `question` (`p1`, `p2` o `p3`) y `model`, obligatorios; `run_name` (por defecto `pregunta_modelo`); los hiperparámetros se pasan como parámetros adicionales con el mismo `-P` (`n_estimators`, `learning_rate`, `max_depth`, `min_samples_leaf`, `C`, `max_iter`, `alpha`, `k`, `componentes` y `threshold`) y los que no se pasan toman los valores de `config.HIPERPARAMETROS` (`max_depth=sin_limite` quita el límite; `threshold` se elige en validación si no se pasa) |
| `search` | `python -m mibici.modeling.search` | `question` y `model`, obligatorios (`hgb` en P1 y P2, `kmeans` en P3); `run_name` (por defecto `pregunta_busqueda_modelo`). La rejilla vive en `config.BUSQUEDAS` |

Todas las corridas se lanzan con `mlflow run` desde la raíz, con `--experiment-name mibici-equipo38` (el experimento del proyecto, el mismo de la primera entrega) y un gestor de entornos:

- `--env-manager local` ejecuta el proyecto con el entorno activado, el de `requirements.txt`. Es el modo con que se lanzaron todas las corridas de esta entrega, en Windows.
- `--env-manager uv` crea un entorno aislado a partir de `python_env.yaml` (Python 3.14.2 y las dependencias fijas) con [uv](https://docs.astral.sh/uv/) y corre el punto de entrada dentro de él; hace falta `uv` instalado (`pip install uv`). Con MLflow 3.16.1 y uv 0.13.5 el comando `mlflow run . -e train -P question=p1 -P model=naive7 --experiment-name mibici-equipo38 --env-manager uv` termina con el mismo resultado que en modo local.

El parámetro `-P run_name=...` fija el nombre de la corrida. Un `-P` con un hiperparámetro que el modelo no usa detiene la corrida con un mensaje, para que ningún valor se quede sin efecto en silencio.

## Ingesta

```
mlflow run . -e ingest --experiment-name mibici-equipo38 --env-manager local
```

Sin pasos manuales: descarga los doce archivos de viajes de 2025 y la nomenclatura de estaciones a `data/raw/`, normaliza los nombres de columnas a `snake_case` sin acentos, resuelve la codificación de cada archivo (los meses mezclan UTF-8 y Latin-1) y convierte las fechas a `datetime`, calcula la duración de cada viaje, descarta los viajes duplicados y los de duración negativa, menor a un minuto o mayor a 24 horas, elimina las columnas con datos personales, marca si cada estación aparece en la nomenclatura y escribe `data/processed/viajes.parquet`, `data/processed/estaciones.parquet` y `data/manifiesto.json`.

Para probar con un solo mes, `-P months=2025-12`; con varios, `-P months=2025-11,2025-12`. Los archivos ya descargados se reutilizan. El comando directo `python -m mibici.dataset` (con `--meses 2025-11 2025-12` y `--forzar`) sigue disponible.

## Corridas de la entrega

Con el servidor levantado y `MLFLOW_TRACKING_URI` apuntando a él, las corridas de esta entrega son las siguientes (`make corridas` las lanza todas en orden):

```
mlflow run . -e train -P question=p1 -P model=naive7 -P run_name=p1_baseline_naive7 --experiment-name mibici-equipo38 --env-manager local
mlflow run . -e train -P question=p2 -P model=dummy -P run_name=p2_baseline_dummy --experiment-name mibici-equipo38 --env-manager local
mlflow run . -e train -P question=p2 -P model=regla_semana -P run_name=p2_baseline_regla_semana --experiment-name mibici-equipo38 --env-manager local
mlflow run . -e train -P question=p3 -P model=kmeans -P k=4 -P run_name=p3_kmeans_k4 --experiment-name mibici-equipo38 --env-manager local

mlflow run . -e train -P question=p1 -P model=hgb -P run_name=p1_hgb --experiment-name mibici-equipo38 --env-manager local
mlflow run . -e train -P question=p1 -P model=bosque -P run_name=p1_bosque --experiment-name mibici-equipo38 --env-manager local
mlflow run . -e train -P question=p1 -P model=ridge -P run_name=p1_ridge --experiment-name mibici-equipo38 --env-manager local
mlflow run . -e train -P question=p2 -P model=regresion_logistica -P run_name=p2_regresion_logistica --experiment-name mibici-equipo38 --env-manager local
mlflow run . -e train -P question=p2 -P model=bosque -P run_name=p2_bosque --experiment-name mibici-equipo38 --env-manager local
mlflow run . -e train -P question=p2 -P model=hgb -P run_name=p2_hgb --experiment-name mibici-equipo38 --env-manager local
mlflow run . -e train -P question=p3 -P model=aglomerativo -P k=4 -P run_name=p3_aglomerativo_k4 --experiment-name mibici-equipo38 --env-manager local
mlflow run . -e train -P question=p3 -P model=kmeans_pca -P k=4 -P run_name=p3_kmeans_pca_k4 --experiment-name mibici-equipo38 --env-manager local

mlflow run . -e search -P question=p1 -P model=hgb -P run_name=p1_busqueda_hgb --experiment-name mibici-equipo38 --env-manager local
mlflow run . -e search -P question=p2 -P model=hgb -P run_name=p2_busqueda_hgb --experiment-name mibici-equipo38 --env-manager local
mlflow run . -e search -P question=p3 -P model=kmeans -P run_name=p3_busqueda_k --experiment-name mibici-equipo38 --env-manager local
```

Los cuatro primeros comandos relanzan los *baselines* de la primera entrega desde el MLflow Project (mismas métricas, etiquetas nuevas); los ocho siguientes son las candidatas y los tres últimos las búsquedas. Cualquier hiperparámetro se cambia desde la línea de comandos, por ejemplo `mlflow run . -e train -P question=p1 -P model=hgb -P n_estimators=300 -P learning_rate=0.05 -P max_depth=8 -P run_name=p1_hgb_lr005 --experiment-name mibici-equipo38 --env-manager local`.

Cada corrida registra:

- Parámetros: `pregunta`, `modelo` y sus hiperparámetros, `semilla`, `fecha_inicio`, `fecha_fin`, `meses` y `version_datos` del manifiesto, `fin_entrenamiento`, `fin_validacion`, `repositorio`, los registros de cada conjunto y, en P2, `umbral_riesgo`, `ventana_riesgo_horas`, `costo_falso_negativo`, `threshold` y `threshold_origen` (`validacion` o `argumento`).
- Métricas con el prefijo del conjunto en que se calculan (`val_*`, `test_*`, `train_*`) más `tiempo_entrenamiento_s`, `tiempo_inferencia_s` y `tamano_modelo_mb`.
- Etiquetas para filtrar y comparar en la interfaz: `question` (`p1`, `p2`, `p3`), `model_family`, `stage_of_work` (`baseline`, `search` o `candidate`), además de `equipo`, `pregunta`, `commit_git` (el commit con que se ejecutó, también en `mlflow.source.git.commit`) y `rama`.

La búsqueda (`search.py`) abre una corrida padre por búsqueda y una hija por combinación de la rejilla, en el mismo proceso y con los conjuntos construidos una sola vez. Cada hija registra sus hiperparámetros, sus métricas y `metricas.json`; el padre registra la rejilla, la métrica de cada combinación (`val_mae`, `val_costo` o `train_silhouette`, con un paso por hija), la tabla `data/resultados_busqueda.csv` y la gráfica `plots/resultados_busqueda.png`. La mejor hija queda con los artefactos completos, el nombre `pregunta_modelo_mejor` y la etiqueta `stage_of_work=candidate`, para compararla con las demás candidatas sin volver a entrenarla.

## Artefactos de cada corrida

Las corridas candidatas y los *baselines* guardan, en subcarpetas:

- `plots/`: real contra predicho y residuales en P1; matriz de confusión y curva precisión-recall con el umbral elegido en P2; mapa de estaciones y perfiles horarios por grupo en P3.
- `data/`: `manifiesto.json` de la ingesta (la versión de los datos) y, en P3, `grupos_estaciones.csv` con el grupo de cada estación. El conjunto de entrenamiento se registra además con `mlflow.log_input` (nombre `mibici_<pregunta>_entrenamiento`, digest igual a `version_datos`), de modo que la pestaña de datasets de la corrida muestra su esquema y su tamaño.
- `config/`: `config.json` con las constantes de `config.py`, `argumentos.json` con los argumentos e hiperparámetros con que se ejecutó la corrida y copia de `python_env.yaml`.
- `metricas.json` y el modelo bajo `modelo`, con su firma y un ejemplo de entrada (`mlflow.sklearn.log_model`). En P2 el modelo guardado es el `Pipeline` envuelto en `FixedThresholdClassifier` con el umbral elegido.

Ningún artefacto contiene datos de usuarios: la ingesta descarta las columnas personales y las tablas de entrenamiento solo tienen conteos por estación y hora o día.

## Model Registry

El modelo elegido de cada pregunta se registra con `registry.py`, que toma el modelo de la corrida, crea el modelo registrado si no existe (con su descripción) y agrega una versión con el linaje en etiquetas: `experimento`, `run_id`, `corrida`, `commit_git`, `rama`, `version_datos`, `modelo`, la métrica de decisión con su valor y, en P2, `threshold`. La descripción de cada versión repite la corrida de origen, el commit, la versión de los datos, la métrica y la partición.

| Pregunta | Modelo registrado | Métrica de decisión |
|---|---|---|
| P1 | `mibici-equipo38-p1-demanda` | `test_mae` (viajes por estación y día) |
| P2 | `mibici-equipo38-p2-riesgo` | `test_costo` (falsos positivos más cinco veces los falsos negativos) |
| P3 | `mibici-equipo38-p3-grupos` | `train_silhouette` y lectura operativa de los grupos |

```
python -m mibici.modeling.registry --pregunta p1 --champion <run_id> --challenger <run_id>
python -m mibici.modeling.registry --pregunta p2 --champion <run_id> --challenger <run_id>
python -m mibici.modeling.registry --pregunta p3 --champion <run_id> --challenger <run_id>
python -m mibici.modeling.registry --verificar
```

Esquema de ciclo de vida: alias, no etapas. Las etapas `Staging`, `Production` y `Archived` están marcadas como obsoletas desde MLflow 2.9; los alias son nombres que apuntan a una versión y se mueven sin crear versiones nuevas, así que promover o revertir un modelo es cambiar a qué versión apunta el alias. `champion` es la versión en producción, la que carga `predict.py`; `challenger` es la siguiente mejor candidata, lista para sustituir al `champion` si lo supera en la siguiente evaluación. `--verificar` carga `models:/<nombre>@champion` de las tres preguntas con `mlflow.pyfunc.load_model` y predice con el ejemplo de entrada guardado con el modelo.

`predict.py` usa el modelo en producción por nombre y alias, sin identificadores de corrida:

```
python -m mibici.modeling.predict --pregunta p1
python -m mibici.modeling.predict --pregunta p2
python -m mibici.modeling.predict --pregunta p3
```

Calcula las predicciones del conjunto de prueba, las guarda en `models/predicciones_<pregunta>.csv` e imprime las métricas de prueba, que coinciden con las de la corrida de origen (en P2 porque el umbral va dentro del modelo). Con `--modelo_uri runs:/<run_id>/modelo` o `models:/<nombre>@challenger` se evalúa otra versión.

## Resultados de la segunda entrega

Treinta y seis corridas en el experimento `mibici-equipo38` lanzadas con los comandos de arriba el 22 de octubre de 2026 (`version_datos` `7aa5e436d887`, semilla 42, partición de la propuesta): cuatro *baselines*, diez candidatas (siete de `train` y las tres mejores hijas de las búsquedas), tres corridas padre y veintiuna hijas. Métricas en prueba (noviembre y diciembre de 2025); el umbral de P2 se eligió en validación con el costo de los errores (un falso negativo vale cinco falsos positivos).

| Pregunta | Corrida | Modelo e hiperparámetros | Métricas en prueba | Entrenamiento, inferencia, tamaño |
|---|---|---|---|---|
| P1 | `p1_baseline_naive7` | Valor de hace siete días | `test_mae` 7.275, `test_rmse` 12.67 | 0 s, 0 s, 0 MB |
| P1 | `p1_hgb` | HGB lr 0.1, 200 árboles, sin límite | `test_mae` 6.052, `test_rmse` 10.62 | 0.6 s, 0.02 s, 0.4 MB |
| P1 | `p1_bosque` | RandomForest 300 árboles, hoja mínima 5 | `test_mae` 5.927, `test_rmse` 10.22 | 16.3 s, 0.30 s, 414 MB |
| P1 | `p1_ridge` | Ridge alpha 1 con día y mes codificados | `test_mae` 6.256, `test_rmse` 10.54 | 0.2 s, 0.02 s, 0.003 MB |
| P1 | `p1_hgb_mejor` (mejor de 9 hijas) | HGB lr 0.05, 300 árboles, profundidad 4 | `test_mae` 5.979, `test_rmse` 10.45 | 0.9 s, 0.06 s, 0.5 MB |
| P2 | `p2_baseline_dummy` | Estratificado | `test_costo` 42,594, `test_f1` 0.014, `test_pr_auc` 0.013 | 2.2 s, 0.27 s, 0.003 MB |
| P2 | `p2_baseline_regla_semana` | Riesgo de la misma hora de la semana anterior | `test_costo` 28,170, recall 0.320, precisión 0.287, `test_pr_auc` 0.101 | 0 s, 0 s, 0 MB |
| P2 | `p2_regresion_logistica` | Logística balanceada C 1, umbral 0.92 | `test_costo` 29,369, recall 0.373, precisión 0.232, `test_pr_auc` 0.207 | 22.6 s, 0.31 s, 0.004 MB |
| P2 | `p2_bosque` | RandomForest balanceado 200 árboles, hoja mínima 50, umbral 0.88 | `test_costo` 26,854, recall 0.383, precisión 0.296, `test_pr_auc` 0.328 | 222 s, 3.5 s, 192 MB |
| P2 | `p2_hgb` y `p2_hgb_mejor` (mejor de 6 hijas) | HGB balanceado lr 0.1, 200 árboles, sin límite, umbral 0.92 | `test_costo` 26,432, recall 0.377, precisión 0.316, `test_f1` 0.343, `test_pr_auc` 0.334 | 55 s, 2.9 s, 0.7 MB |
| P3 | `p3_kmeans_k4` | KMeans k = 4 | `train_silhouette` 0.084, `train_davies_bouldin` 2.34 | 0.3 s, 0.01 s, 0.01 MB |
| P3 | `p3_aglomerativo_k4` | Ward k = 4 | `train_silhouette` 0.071, `train_davies_bouldin` 2.40 | 0.2 s, sin `predict`, 0.01 MB |
| P3 | `p3_kmeans_pca_k4` | PCA 10 componentes y KMeans k = 4 | `train_silhouette` 0.085, `train_davies_bouldin` 2.33 | 0.4 s, 0.01 s, 0.02 MB |
| P3 | `p3_kmeans_mejor` (mejor de 6 hijas, k de 3 a 8) | KMeans k = 3 | `train_silhouette` 0.095, `train_davies_bouldin` 2.41 | 0.3 s, 0.01 s, 0.01 MB |

Modelos en producción:

| Modelo registrado | Versión 1 (`champion`) | Versión 2 (`challenger`) | Por qué |
|---|---|---|---|
| `mibici-equipo38-p1-demanda` | `p1_hgb_mejor` | `p1_bosque` | El bosque gana 0.05 viajes de MAE (0.9 %) con un modelo 800 veces más pesado y 17 veces más lento de entrenar; la diferencia no cambia ninguna decisión de flota |
| `mibici-equipo38-p2-riesgo` | `p2_hgb_mejor` | `p2_bosque` | Menor costo de los errores en validación y en prueba, mejor PR-AUC y 270 veces menos pesado que el bosque; la regresión logística no supera a la regla con este criterio |
| `mibici-equipo38-p3-grupos` | `p3_kmeans_pca_k4` | `p3_kmeans_mejor` | k = 4 conserva la lectura operativa de los cuatro perfiles con la mejor silueta entre las candidatas de k = 4; k = 3 es la partición que prefiere la silueta y queda pendiente de validar con planeación |

Para reproducir el modelo elegido de cada pregunta como corrida independiente:

```
mlflow run . -e train -P question=p1 -P model=hgb -P n_estimators=300 -P learning_rate=0.05 -P max_depth=4 -P run_name=p1_hgb_mejor --experiment-name mibici-equipo38 --env-manager local
mlflow run . -e train -P question=p2 -P model=hgb -P run_name=p2_hgb --experiment-name mibici-equipo38 --env-manager local
mlflow run . -e train -P question=p3 -P model=kmeans_pca -P k=4 -P run_name=p3_kmeans_pca_k4 --experiment-name mibici-equipo38 --env-manager local
```

## Flujo de trabajo con Git y GitHub

- GitHub Flow: `main` siempre está en estado entregable. Cada cambio nace en una rama corta creada desde `main`, se publica en GitHub, se abre un *Pull Request*, otro integrante lo revisa, se integra y la rama se borra.
- Rama principal protegida: `main` exige *Pull Request* con una aprobación y bloquea el *force push* y el borrado de la rama. Los tres primeros *commits* (estructura generada con `ccds`, configuración inicial y README) entraron directo a `main` antes de activar la protección; desde entonces todo entra por *Pull Request*.
- Solo integración con *merge commit* (*squash* y *rebase* desactivados en la configuración del repositorio), para que los *commits* de cada rama, que son los que etiquetan las corridas de MLflow en `commit_git`, queden en el historial de `main`.
- Ramas: `tipo/descripcion-corta` en minúsculas y sin acentos, por ejemplo `feat/ingesta`, `feat/mlflow-project-registry`, `fix/features-particion-perfiles`.
- *Commits*: [Conventional Commits](https://www.conventionalcommits.org/es/v1.0.0/) en español, con los tipos `feat`, `fix`, `docs`, `test`, `refactor` y `chore`; asunto en minúsculas, sin punto final y de no más de 72 caracteres, por ejemplo `feat: búsqueda de hiperparámetros con nested runs`.
- Cada integrante abre al menos un *Pull Request* y revisa al menos uno de otro integrante; las revisiones se cruzan en anillo.
- Primera entrega, en el orden en que se integraron: `feat/ingesta` (`dataset.py`, manifiesto y pruebas), `feat/features` (`features.py`, pruebas y notebook de exploración), `feat/experimento-base` (`train.py`, `predict.py`, `plots.py`, `MLproject` y entorno) y `docs/referencias` (ML Canvas, diagrama de arquitectura y resultados del experimento base).
- Segunda entrega, en el orden en que se integran porque la primera rama consume lo que deja la segunda: `feat/model-registry` (`registry.py`, `predict.py` con carga por alias y `tests/test_registry.py`), `feat/mlflow-project-registry` (`MLproject`, `python_env.yaml`, `Makefile`, `artefactos.py`, `train.py`, `search.py`, pruebas y este README) y `fix/features-particion-perfiles` (corrección de `features.py` señalada en la revisión de la primera entrega: en P2 se excluyen de entrenamiento y validación las horas cuya ventana objetivo cruza el corte siguiente y en P3 los perfiles se alinean sobre la unión de estaciones con salidas y llegadas; entra después de las corridas de esta entrega para que sus `commit_git` reproduzcan exactamente lo que se midió, y se aplica en la siguiente iteración de los modelos).
- Nada de datos de MiBici, modelos serializados, carpetas de MLflow ni credenciales en el historial: `.gitignore` los excluye y los *Pull Requests* se revisan también con ese criterio.

## Integrantes y roles

El trabajo se repartió por etapas del *pipeline*, que es la separación que propone la plantilla: cada integrante es responsable de un módulo con una interfaz definida y revisa el módulo vecino.

| Integrante | Matrícula | Rol en el proyecto | Primera entrega | Segunda entrega |
|---|---|---|---|---|
| José Andrés Hernández Guerra | A01840564 | Datos e ingesta; Model Registry | `mibici/dataset.py`, `data/manifiesto.json` y `tests/test_dataset.py` (rama `feat/ingesta`); revisión del *Pull Request* de *features* | `mibici/modeling/registry.py`, `mibici/modeling/predict.py` y `tests/test_registry.py` (rama `feat/model-registry`); revisión del *Pull Request* del MLflow Project |
| Miguel Angel Higuera López | A01451684 | *Features* y exploración | `mibici/features.py`, `tests/test_features.py` y `notebooks/1.0-mah-exploracion-mibici.ipynb` (rama `feat/features`); revisión del *Pull Request* de ingesta | Corrección de la partición de P2 y de los perfiles de P3 en `mibici/features.py` con sus pruebas (rama `fix/features-particion-perfiles`); revisión del *Pull Request* del Model Registry |
| Nicolás Hernández Ynurreta García | A01284528 | Integración y MLOps | Estructura con `ccds`, configuración, README, experimento base en MLflow, ML Canvas y diagrama, documento de la propuesta, revisión e integración | `MLproject`, `python_env.yaml`, `Makefile`, `artefactos.py`, `train.py`, `search.py` y sus pruebas (rama `feat/mlflow-project-registry`); corridas de la entrega, selección y registro de los modelos, reporte, revisión de los *Pull Requests* del equipo e integración |

El equipo quedó integrado por tres personas: la cuarta inscripción registrada en Canvas está inactiva.

## Buenas prácticas

| Ámbito | Práctica | Dónde se cumple en este repositorio |
|---|---|---|
| MLflow Projects | Proyecto ejecutable con un solo comando y entorno declarado | `MLproject` con `ingest`, `train` y `search`; `python_env.yaml` con las versiones de `requirements.txt` |
| MLflow Tracking | Un experimento por proyecto y *runs* con nombre descriptivo | Experimento `mibici-equipo38` y `run_name` en cada comando; `train.py` y `search.py` nombran cada corrida |
| MLflow Tracking | Registrar todo lo necesario para reproducir el *run* | Parámetros de rango de fechas, `version_datos`, semilla, modelo e hiperparámetros, partición; `config/` con las constantes y los argumentos |
| MLflow Tracking | Ligar cada *run* con el código, la pregunta y la etapa del trabajo | Etiquetas `commit_git`, `rama`, `question`, `pregunta`, `model_family`, `stage_of_work` y `equipo` |
| MLflow Tracking | Nombrar las métricas con el conjunto en que se calculan | `val_mae`, `test_mae`, `test_costo`, `train_silhouette`, etc. |
| MLflow Tracking | Búsquedas organizadas como *nested runs* | `search.py`: una corrida padre por búsqueda y una hija por combinación |
| Artefactos | Modelo con firma y ejemplo de entrada, versión de los datos, gráficas y configuración, en subcarpetas | `artefactos.py`: `plots/`, `data/`, `config/`, `log_input` y `modelo` |
| Model Registry | Nombre claro, descripción, linaje y versión en producción por alias | `registry.py`: `mibici-equipo38-p<N>-...`, etiquetas de versión y alias `champion` y `challenger` |
| Datos | No registrar credenciales ni datos personales | Las columnas personales se descartan en `dataset.py`; ningún parámetro, etiqueta o artefacto las contiene |
| Estructura y código | Notebooks solo para exploración; configuración en un solo lugar | `notebooks/`; `mibici/config.py` |
| Estructura y código | Dependencias con versión fija y entorno reproducible desde un clon limpio | `requirements.txt`, `python_env.yaml` y la sección Instalación |
| Datos y Git | Ningún dato, modelo, base de datos de MLflow ni credencial en el historial | `.gitignore` (datos, Parquet, `mlruns/`, `mlartifacts/`, `mlflow.db`, `models/`, `.env`) |
| Datos y Git | Todo cambio entra a `main` por *Pull Request* revisado | Rama `main` protegida con una aprobación y pestaña de *Pull Requests* del repositorio |
