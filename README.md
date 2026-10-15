# TC5061-Proyecto-Equipo38

Propuesta y base reproducible del proyecto integrador de Operaciones de aprendizaje automático (TC5061) sobre los datos abiertos de [MiBici](https://mibici.net/es/datos-abiertos/), el sistema de bicicleta pública del Área Metropolitana de Guadalajara. Equipo 38.

Repositorio: https://github.com/nicoynurreta/TC5061-Proyecto-Equipo38

## Propósito

El proyecto responde tres preguntas sobre la operación de MiBici con un modelo de regresión, uno de clasificación y uno de *clustering*, y deja montada la base sobre la que se construyen las entregas siguientes: una ingesta reproducible y versionada de los viajes, un módulo de *features* reutilizable, un experimento base registrado en MLflow contra el que se medirá cualquier mejora y un flujo de trabajo en equipo con ramas y *Pull Requests*.

## Las tres preguntas

| # | Pregunta | Tarea | Qué se predice o agrupa | Quién lo usa y qué decide |
|---|---|---|---|---|
| P1 | ¿Cuántos viajes se iniciarán en una estación en un periodo futuro? | Regresión | Viajes iniciados por estación y día, con horizonte de un día | El operador del sistema, para dimensionar la flota y el personal de cada estación |
| P2 | ¿Una estación estará en riesgo de quedarse sin bicicletas o sin anclajes disponibles? | Clasificación | Riesgo por estación y hora para las dos horas siguientes | El equipo de rebalanceo, para decidir a qué estaciones mandar el camión en la siguiente hora |
| P3 | ¿Qué grupos de estaciones comparten patrones de uso y dónde se ubican en la ciudad? | *Clustering* | Grupos de estaciones según su perfil horario de salidas y llegadas en días hábiles y fines de semana | Planeación urbana y expansión del sistema, para decidir dónde ampliar o reubicar estaciones |

Los datos no incluyen el inventario de bicicletas por estación, así que el riesgo de P2 se aproxima con los viajes y la capacidad: una estación está en riesgo en una hora dada si, en la ventana de las dos horas siguientes, el flujo neto acumulado (llegadas menos salidas) alcanza la mitad de su capacidad en cualquiera de los dos sentidos, es decir, si tiende a llenarse o a vaciarse. La fracción y la ventana son parámetros de `config.py` (`UMBRAL_RIESGO` y `VENTANA_RIESGO_HORAS`) y se calibrarán en las siguientes entregas.

Por pregunta, el experimento base compara un *baseline* sencillo con un modelo candidato:

| # | *Baseline* | Modelo candidato | Métricas |
|---|---|---|---|
| P1 | Valor de hace siete días (ingenuo estacional) | `HistGradientBoostingRegressor` | `test_mae`, `test_rmse` (viajes por estación y día) |
| P2 | `DummyClassifier` estratificado y la regla "riesgo si hubo riesgo a la misma hora de la semana anterior" | Regresión logística balanceada en un `Pipeline` | `test_recall`, `test_precision`, `test_f1`, `test_pr_auc`, falsos positivos y falsos negativos |
| P3 | `KMeans` con k = 4 | `KMeans` con k elegido por silueta entre 3 y 8 | `train_silhouette`, `train_davies_bouldin` |

## Datos

- Fuente: portal de datos abiertos de MiBici, https://mibici.net/es/datos-abiertos/. Publica un archivo CSV de viajes por mes (`datos_abiertos_AAAA_MM.csv`) y la nomenclatura de estaciones (`nomenclatura_2026_09.csv`) con identificador, nombre, latitud, longitud y capacidad de cada estación. Las URL exactas de cada archivo quedan en `data/manifiesto.json`.
- Rango: los doce meses de 2025 (`FECHA_INICIO` y `FECHA_FIN` en `config.py`). Un año calendario completo cubre la estacionalidad semanal y anual, los doce archivos comparten las mismas columnas aunque cambian de codificación entre meses, y los meses de 2026 quedan como datos nuevos para las entregas siguientes.
- Tamaño real obtenido con la ingesta de los doce meses (`version_datos` `7aa5e436d887`): 12 archivos mensuales con 4,532,032 registros y 393.1 MB en CSV, más la nomenclatura con 484 estaciones. Después de la limpieza quedan 4,414,800 viajes válidos del 1 de enero al 31 de diciembre de 2025 (se descartan 117,226 viajes de menos de un minuto y 6 de más de 24 horas; no hay duplicados ni registros sin fecha o sin estación) entre 371 estaciones con viajes, todas presentes en la nomenclatura. `viajes.parquet` pesa 88.5 MB y la ingesta completa tarda alrededor de dos minutos.
- Variables originales que se usan: `Viaje_Id`, `Inicio_del_viaje`, `Fin_del_viaje`, `Origen_Id` y `Destino_Id` de los viajes; `id`, `name`, `latitude`, `longitude` y `dpcapacity` de la nomenclatura. La variable objetivo de P1 es el conteo de viajes iniciados por estación y día; la de P2 es la etiqueta de riesgo descrita arriba; P3 no tiene variable objetivo.
- Datos personales: `Usuario_Id`, `Genero` y `Año_de_nacimiento` se descartan en la ingesta y no llegan al Parquet, a las *features* ni a MLflow. Las condiciones de uso del portal están en sus [términos y condiciones](https://mibici.net/es/termino-y-condiciones/).
- Partición temporal: entrenamiento de enero a septiembre, validación en octubre y prueba en noviembre y diciembre de 2025 (`FIN_ENTRENAMIENTO` y `FIN_VALIDACION` en `config.py`). Todas las variables se calculan con información anterior al momento de la predicción.
- Versionado: `data/manifiesto.json` registra la URL, el tamaño en bytes y la suma de verificación SHA-256 de cada archivo crudo, el número de registros y la suma de cada Parquet, los descartes de la limpieza y la versión de los datos (`version_datos`, derivada de las sumas de los archivos crudos), que cada corrida registra en MLflow. El manifiesto sí se versiona en Git; los datos no.

## Estructura del repositorio

Generada con [Cookiecutter Data Science](https://cookiecutter-data-science.drivendata.org/) (`ccds`, con `include_code_scaffold` en Yes).

```
├── Makefile           <- comandos de conveniencia: make requirements, make data, make train, make test
├── MLproject          <- puntos de entrada para mlflow run (ingesta, p1, p2, p3)
├── python_env.yaml    <- versión de Python y dependencias para mlflow run
├── README.md
├── requirements.txt   <- dependencias con versión fija
├── pyproject.toml     <- metadatos del módulo mibici
├── data
│   ├── manifiesto.json <- versión de los datos (único archivo de data/ que se versiona)
│   ├── external
│   ├── interim
│   ├── processed      <- viajes.parquet y estaciones.parquet
│   └── raw            <- archivos CSV descargados del portal
├── models             <- modelos serializados y predicciones
├── notebooks          <- 1.0-mah-exploracion-mibici.ipynb, solo exploración
├── references         <- ML Canvas y diagrama de arquitectura
├── reports
│   └── figures        <- reservada para las figuras de las entregas siguientes; las gráficas de esta entrega son artefactos de MLflow
├── tests              <- pruebas con pytest
└── mibici
    ├── __init__.py
    ├── config.py      <- rutas, URL, rango de fechas, partición, umbrales, semilla y experimento
    ├── dataset.py     <- ingesta: descarga, normalización, Parquet y manifiesto
    ├── features.py    <- features por pregunta y partición temporal
    ├── plots.py       <- gráficas que se registran como artefactos
    └── modeling
        ├── train.py   <- experimento base: baseline y candidato por pregunta, registro en MLflow
        └── predict.py <- predicción con un modelo registrado en MLflow
```

`data/raw/`, `data/processed/`, `models/`, `mlruns/`, `mlartifacts/`, `mlflow.db` y los archivos `.env` están en `.gitignore`.

## Instalación

Probado con Python 3.14.2. Desde la raíz del repositorio:

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

En Linux o macOS el entorno se activa con `source venv/bin/activate`. `requirements.txt` fija la versión de cada dependencia e instala el módulo `mibici` en modo editable, así que `python -m mibici.dataset` y `python -m mibici.modeling.train` funcionan desde cualquier carpeta; los comandos de abajo suponen la raíz del repositorio.

## Ingesta

```
python -m mibici.dataset
```

Sin pasos manuales: descarga los doce archivos de viajes de 2025 y la nomenclatura de estaciones a `data/raw/`, normaliza los nombres de columnas a `snake_case` sin acentos, resuelve la codificación de cada archivo (los meses mezclan UTF-8 y Latin-1) y convierte las fechas a `datetime`, calcula la duración de cada viaje, descarta los viajes duplicados y los de duración negativa, menor a un minuto o mayor a 24 horas, elimina las columnas con datos personales, marca si cada estación aparece en la nomenclatura y escribe `data/processed/viajes.parquet`, `data/processed/estaciones.parquet` y `data/manifiesto.json`.

Opciones: `--meses 2025-11 2025-12` ingiere solo esos meses y `--forzar` vuelve a descargar los archivos que ya estén en `data/raw/`. Los archivos ya descargados se reutilizan, así que repetir el comando solo rehace la limpieza. La descarga completa pesa unos 390 MB.

## Experimento base

Las siete corridas del experimento `mibici-equipo38` se lanzan desde la raíz del repositorio con el código del módulo (`make train` las corre todas):

```
python -m mibici.modeling.train --pregunta p1 --modelo naive7 --nombre_corrida p1_baseline_naive7
python -m mibici.modeling.train --pregunta p1 --modelo hgb --nombre_corrida p1_hgb
python -m mibici.modeling.train --pregunta p2 --modelo dummy --nombre_corrida p2_baseline_dummy
python -m mibici.modeling.train --pregunta p2 --modelo regla_semana --nombre_corrida p2_baseline_regla_semana
python -m mibici.modeling.train --pregunta p2 --modelo regresion_logistica --nombre_corrida p2_regresion_logistica
python -m mibici.modeling.train --pregunta p3 --modelo kmeans --k 4 --nombre_corrida p3_kmeans_k4
python -m mibici.modeling.train --pregunta p3 --modelo kmeans --seleccionar_k --nombre_corrida p3_kmeans_silueta
```

Las corridas se registran en `mlflow.db` (SQLite) y sus artefactos en `mlruns/`, los dos en la raíz del repositorio y fuera de Git. La interfaz se abre con:

```
mlflow ui --backend-store-uri sqlite:///mlflow.db
```

y queda en http://127.0.0.1:5000. `python -m mibici.modeling.train --help` describe todos los argumentos (modelo, hiperparámetros, semilla, fechas de corte de la partición, umbral de riesgo, experimento y `tracking_uri`).

Cada corrida registra:

- Parámetros: `pregunta`, `modelo` y sus hiperparámetros, `semilla`, `fecha_inicio`, `fecha_fin`, `fin_entrenamiento`, `fin_validacion`, `version_datos` y `meses` del manifiesto, `umbral_riesgo` y `ventana_riesgo_horas` en P2, número de registros de cada conjunto y `repositorio`.
- Métricas con el prefijo del conjunto en que se calculan: `val_*` y `test_*` en P1 y P2, `train_*` en P3.
- Etiquetas: `equipo`, `pregunta`, `commit_git` (el commit con que se ejecutó) y `rama`.
- Artefactos: la gráfica de real contra predicho en P1, la matriz de confusión y la curva precisión-recall en P2, el mapa de grupos y los perfiles medios por grupo en P3, `metricas.json` y el manifiesto de datos; en los modelos de scikit-learn, el modelo con su firma.

### Resultados de la línea base

Corridas con `version_datos` `7aa5e436d887`, semilla 42 y la partición por defecto (entrenamiento del 1 de enero al 30 de septiembre, validación octubre, prueba noviembre y diciembre de 2025). P1 usa 95,035 registros estación-día de entrenamiento, 11,379 de validación y 22,399 de prueba; P2 usa 2,340,156, 273,230 y 536,089 registros estación-hora (1.81 % de positivos en entrenamiento con el umbral de 0.5); P3 agrupa 369 estaciones con 98 variables cada una.

| Corrida | Modelo | Métricas en prueba | Artefactos |
|---|---|---|---|
| `p1_baseline_naive7` | Valor de hace siete días | `test_mae` 7.28, `test_rmse` 12.67 | `real_vs_predicho.png` |
| `p1_hgb` | `HistGradientBoostingRegressor` (200 árboles, tasa 0.1) | `test_mae` 6.05, `test_rmse` 10.62 | `real_vs_predicho.png` |
| `p2_baseline_dummy` | `DummyClassifier` estratificado | `test_recall` 0.017, `test_precision` 0.012, `test_f1` 0.014, `test_pr_auc` 0.013 | `matriz_confusion.png`, `curva_precision_recall.png` |
| `p2_baseline_regla_semana` | Riesgo de la misma hora de la semana anterior | `test_recall` 0.320, `test_precision` 0.287, `test_f1` 0.303, `test_pr_auc` 0.101 | `matriz_confusion.png`, `curva_precision_recall.png` |
| `p2_regresion_logistica` | Regresión logística balanceada (C 1.0) | `test_recall` 0.839, `test_precision` 0.058, `test_f1` 0.108, `test_pr_auc` 0.207 | `matriz_confusion.png`, `curva_precision_recall.png` |
| `p3_kmeans_k4` | `KMeans`, k = 4 | `train_silhouette` 0.084, `train_davies_bouldin` 2.34 | `mapa_grupos.png`, `perfiles_grupos.png`, `grupos_estaciones.csv` |
| `p3_kmeans_silueta` | `KMeans`, k elegido por silueta entre 3 y 8 (k = 3) | `train_silhouette` 0.095, `train_davies_bouldin` 2.41 | `mapa_grupos.png`, `perfiles_grupos.png`, `grupos_estaciones.csv` |

Todas las corridas registran además `metricas.json` y `manifiesto.json`; las de scikit-learn guardan el modelo con su firma. En P1 el modelo candidato reduce el error absoluto medio de 7.28 a 6.05 viajes por estación y día respecto del baseline estacional. En P2 la regresión logística balanceada detecta 84 % de las horas en riesgo (1,080 falsos negativos de 6,718 positivos en prueba) a costa de 92,194 falsos positivos, mientras que la regla de la semana anterior equilibra ambos errores (recall 0.32, precisión 0.29); el umbral de decisión y el costo relativo de cada error se calibrarán en las siguientes entregas. En P3 la silueta es baja en todas las k (0.03 a 0.10), como es habitual con perfiles horarios de 96 dimensiones, y los grupos siguen siendo interpretables: estaciones de salida matutina en la periferia, estaciones de llegada vespertina en el centro, y un grupo pequeño de uso de fin de semana.

### Con MLflow Projects

`MLproject` declara los puntos de entrada `ingesta`, `p1`, `p2` y `p3`, para que cada etapa se pueda correr con un solo comando desde el entorno activado:

```
set MLFLOW_TRACKING_URI=sqlite:///mlflow.db
mlflow run . -e p1 -P modelo=naive7 -P nombre_corrida=p1_baseline_naive7 --experiment-name mibici-equipo38 --env-manager local
mlflow run . -e p3 -P k=4 -P nombre_corrida=p3_kmeans_k4 --experiment-name mibici-equipo38 --env-manager local
```

En Linux o macOS la variable se fija con `export`. El parámetro `nombre_corrida` fija el nombre de la corrida (por defecto `p1_hgb`, `p2_regresion_logistica` y `p3_kmeans_k4`) y `--experiment-name` debe ser `mibici-equipo38`, el experimento del proyecto. Con `--env-manager virtualenv`, MLflow crea el entorno a partir de `python_env.yaml`.

### Prueba rápida con un solo mes

Para comprobar la instalación sin descargar el año completo:

```
python -m mibici.dataset --meses 2025-12
python -m mibici.modeling.train --pregunta p3 --modelo kmeans --k 4 --fin_entrenamiento 2025-12-31 --nombre_corrida prueba_p3
python -m mibici.modeling.train --pregunta p1 --modelo naive7 --fin_entrenamiento 2025-12-24 --fin_validacion 2025-12-27 --nombre_corrida prueba_p1
```

Las fechas de corte se recorren porque la partición por defecto (enero a septiembre, octubre, noviembre y diciembre) supone el año completo.

## Flujo de trabajo con Git y GitHub

- GitHub Flow: `main` siempre está en estado entregable. Cada cambio nace en una rama corta creada desde `main`, se publica en GitHub, se abre un *Pull Request*, otro integrante lo revisa, se integra y la rama se borra.
- Rama principal protegida: `main` exige *Pull Request* y bloquea el *force push* y el borrado de la rama. En la fase de arranque (del 14 al 18 de octubre de 2026) la regla exige *Pull Request* sin un número mínimo de aprobaciones, para que la integración no se detenga mientras el equipo termina de incorporarse, y el propietario conserva la excepción de administrador; al cerrar la primera entrega se sube a una aprobación obligatoria por *Pull Request*. Los tres primeros *commits* (estructura generada con `ccds`, configuración inicial y este README) entraron directo a `main` antes de activar la protección.
- Solo integración con *merge commit* (*squash* y *rebase* desactivados en la configuración del repositorio), para que los *commits* de cada rama, que son los que etiquetan las corridas de MLflow en `commit_git`, queden en el historial de `main`.
- Ramas: `tipo/descripcion-corta` en minúsculas y sin acentos, por ejemplo `feat/ingesta`, `feat/features`, `feat/experimento-base`, `docs/referencias`, `fix/duracion-negativa`.
- *Commits*: [Conventional Commits](https://www.conventionalcommits.org/es/v1.0.0/) en español, con los tipos `feat`, `fix`, `docs`, `test`, `refactor` y `chore`; asunto en minúsculas, sin punto final y de no más de 72 caracteres, por ejemplo `feat: ingesta de viajes y nomenclatura de MiBici`.
- Cada integrante abre al menos un *Pull Request* y revisa al menos uno de otro integrante. Las revisiones se cruzan entre módulos vecinos del *pipeline*: quien escribe la ingesta revisa las *features* y quien escribe las *features* revisa la ingesta, de modo que cada uno conoce el módulo del que depende o al que alimenta; el integrador revisa los dos y abre sus propios *Pull Requests* (experimento base y referencias) para que el equipo los revise. Un *Pull Request* se integra después de la revisión; si el revisor asignado no puede hacerla antes del cierre, el administrador integra y lo deja anotado en la conversación del *Pull Request*.
- Ramas de la primera entrega, en el orden en que se integran a `main` porque cada una alimenta a la siguiente: `feat/ingesta` (`dataset.py`, manifiesto y pruebas), `feat/features` (`features.py`, pruebas y notebook de exploración), `feat/experimento-base` (`train.py`, `predict.py`, `plots.py`, `MLproject` y entorno) y `docs/referencias` (ML Canvas, diagrama de arquitectura y resultados del experimento base).
- Nada de datos de MiBici, modelos serializados, carpetas de MLflow ni credenciales en el historial: `.gitignore` los excluye y los *Pull Requests* se revisan también con ese criterio.

## Integrantes y roles

El trabajo se repartió por etapas del *pipeline*, que es la separación que propone la plantilla: cada integrante es responsable de un módulo con una interfaz definida (la ingesta entrega los Parquet y el manifiesto; las *features* reciben esos Parquet y entregan las tablas de entrenamiento; el experimento consume las tablas y registra las corridas) y revisa el módulo vecino.

| Integrante | Matrícula | Rol en el proyecto | Aportación en esta entrega |
|---|---|---|---|
| José Andrés Hernández Guerra | A01840564 | Datos e ingesta | Ingesta y versionado de los datos: `mibici/dataset.py`, `data/manifiesto.json` y `tests/test_dataset.py` (rama `feat/ingesta`); revisión del *Pull Request* de *features* |
| Miguel Angel Higuera López | A01451684 | *Features* y exploración | Módulo de *features* y exploración: `mibici/features.py`, `tests/test_features.py` y `notebooks/1.0-mah-exploracion-mibici.ipynb` (rama `feat/features`); revisión del *Pull Request* de ingesta |
| Nicolás Hernández Ynurreta García | A01284528 | Integración y MLOps | Estructura con `ccds`, configuración (`config.py`, dependencias con versión fija, `.gitignore`), README, experimento base en MLflow (`train.py`, `predict.py`, `plots.py`, `MLproject`), ML Canvas y diagrama de arquitectura, documento de la propuesta, revisión de los *Pull Requests* del equipo e integración |

El equipo quedó integrado por tres personas: la cuarta inscripción registrada en Canvas está inactiva.

## Buenas prácticas

| Ámbito | Práctica | Dónde se cumple en este repositorio |
|---|---|---|
| MLflow Tracking | Un experimento por proyecto y *runs* con nombre descriptivo | Experimento `mibici-equipo38` y `--nombre_corrida` obligatorio en los comandos documentados; `train.py` nombra cada corrida |
| MLflow Tracking | Registrar todo lo necesario para reproducir el *run* | Parámetros de `train.py`: rango de fechas, `version_datos` del manifiesto, semilla, modelo e hiperparámetros, fechas de corte de la partición |
| MLflow Tracking | Ligar cada *run* con el código y con la pregunta | Etiquetas `commit_git`, `rama`, `pregunta` y `equipo` que fija `train.py` |
| MLflow Tracking | Nombrar las métricas con el conjunto en que se calculan | `val_mae`, `test_mae`, `test_f1`, `train_silhouette`, etc. |
| MLflow Tracking | No registrar credenciales ni datos personales | Las columnas personales se descartan en `dataset.py`; ningún parámetro, etiqueta o artefacto las contiene |
| Estructura y código | Notebooks solo para exploración, con la convención de nombres de la plantilla | `notebooks/1.0-mah-exploracion-mibici.ipynb`; la lógica vive en `mibici/` |
| Estructura y código | Configuración en un solo lugar | `mibici/config.py`: rutas, URL, fechas, partición, umbrales, semilla, experimento y `tracking_uri` |
| Estructura y código | Dependencias con versión fija y entorno reproducible desde un clon limpio | `requirements.txt` con versiones fijas y la sección Instalación |
| Datos y Git | Ningún dato, modelo, carpeta de MLflow ni credencial en el historial | `.gitignore` (datos, Parquet, `mlruns/`, `mlartifacts/`, `mlflow.db`, `models/`, `.env`) y el historial de `main` |
| Datos y Git | Todo cambio entra a `main` por *Pull Request* revisado | Rama `main` protegida y pestaña de *Pull Requests* del repositorio |
