#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_NAME = TC5061-Proyecto-Equipo38
PYTHON_VERSION = 3.14
PYTHON_INTERPRETER = python
ifeq ($(OS),Windows_NT)
PYTHON_DEEPCHECKS = .venv-deepchecks/Scripts/python.exe
else
PYTHON_DEEPCHECKS = .venv-deepchecks/bin/python
endif
EXPERIMENTO = mibici-equipo38
MLFLOW_RUN = $(PYTHON_INTERPRETER) -m mlflow run . --experiment-name $(EXPERIMENTO) --env-manager local

#################################################################################
# COMMANDS                                                                      #
#################################################################################


## Install Python dependencies
.PHONY: requirements
requirements:
	$(PYTHON_INTERPRETER) -m pip install -U pip
	$(PYTHON_INTERPRETER) -m pip install -r requirements.txt




## Delete all compiled Python files
.PHONY: clean
clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete


## Lint using ruff (use `make format` to do formatting)
.PHONY: lint
lint:
	ruff format --check
	ruff check

## Format source code with ruff
.PHONY: format
format:
	ruff check --fix
	ruff format



## Pruebas con pytest; no necesitan datos ni el entorno de DeepChecks (la prueba lenta se omite sola si falta data/processed)
.PHONY: test
test:
	$(PYTHON_INTERPRETER) -m pytest -q tests


## Set up Python interpreter environment
.PHONY: create_environment
create_environment:
	@bash -c "if [ ! -z `which virtualenvwrapper.sh` ]; then source `which virtualenvwrapper.sh`; mkvirtualenv $(PROJECT_NAME) --python=$(PYTHON_INTERPRETER); else mkvirtualenv.bat $(PROJECT_NAME) --python=$(PYTHON_INTERPRETER); fi"
	@echo ">>> New virtualenv created. Activate with:\nworkon $(PROJECT_NAME)"




#################################################################################
# PROJECT RULES                                                                 #
#################################################################################


## Servidor de tracking local con base de datos (requiere MLFLOW_TRACKING_URI=http://127.0.0.1:5000 en los demás comandos)
.PHONY: server
server:
	$(PYTHON_INTERPRETER) -m mlflow server --backend-store-uri sqlite:///mlflow.db --port 5000


## Ingesta de los datos de MiBici con el punto de entrada ingest del MLproject
.PHONY: ingest
ingest:
	$(MLFLOW_RUN) -e ingest


## Baseline de cada pregunta, relanzado desde el MLproject
.PHONY: baselines
baselines:
	$(MLFLOW_RUN) -e train -P question=p1 -P model=naive7 -P run_name=p1_baseline_naive7
	$(MLFLOW_RUN) -e train -P question=p2 -P model=dummy -P run_name=p2_baseline_dummy
	$(MLFLOW_RUN) -e train -P question=p2 -P model=regla_semana -P run_name=p2_baseline_regla_semana
	$(MLFLOW_RUN) -e train -P question=p3 -P model=kmeans -P k=4 -P run_name=p3_kmeans_k4


## Corridas candidatas de cada pregunta
.PHONY: candidatas
candidatas:
	$(MLFLOW_RUN) -e train -P question=p1 -P model=hgb -P run_name=p1_hgb
	$(MLFLOW_RUN) -e train -P question=p1 -P model=bosque -P run_name=p1_bosque
	$(MLFLOW_RUN) -e train -P question=p1 -P model=ridge -P run_name=p1_ridge
	$(MLFLOW_RUN) -e train -P question=p2 -P model=regresion_logistica -P run_name=p2_regresion_logistica
	$(MLFLOW_RUN) -e train -P question=p2 -P model=bosque -P run_name=p2_bosque
	$(MLFLOW_RUN) -e train -P question=p2 -P model=hgb -P run_name=p2_hgb
	$(MLFLOW_RUN) -e train -P question=p3 -P model=aglomerativo -P k=4 -P run_name=p3_aglomerativo_k4
	$(MLFLOW_RUN) -e train -P question=p3 -P model=kmeans_pca -P k=4 -P run_name=p3_kmeans_pca_k4


## Búsquedas de hiperparámetros con nested runs (la mejor hija queda como candidata pregunta_modelo_mejor)
.PHONY: busquedas
busquedas:
	$(MLFLOW_RUN) -e search -P question=p1 -P model=hgb -P run_name=p1_busqueda_hgb
	$(MLFLOW_RUN) -e search -P question=p2 -P model=hgb -P run_name=p2_busqueda_hgb
	$(MLFLOW_RUN) -e search -P question=p3 -P model=kmeans -P run_name=p3_busqueda_k


## Todas las corridas de la entrega en orden
.PHONY: corridas
corridas: baselines candidatas busquedas


## Registro de los modelos elegidos en el Model Registry (sustituir los identificadores de corrida)
.PHONY: registry
registry:
	$(PYTHON_INTERPRETER) -m mibici.modeling.registry --pregunta p1 --champion RUN_ID_P1 --challenger RUN_ID_P1_SEGUNDO
	$(PYTHON_INTERPRETER) -m mibici.modeling.registry --pregunta p2 --champion RUN_ID_P2 --challenger RUN_ID_P2_SEGUNDO
	$(PYTHON_INTERPRETER) -m mibici.modeling.registry --pregunta p3 --champion RUN_ID_P3 --challenger RUN_ID_P3_SEGUNDO
	$(PYTHON_INTERPRETER) -m mibici.modeling.registry --verificar


## Chequeos de datos y seguridad: tablas de data/interim, suites de DeepChecks (entorno .venv-deepchecks), bandit, pip-audit y búsqueda de secretos
.PHONY: chequeos
chequeos:
	$(PYTHON_INTERPRETER) -m mibici.validacion --exportar
	$(PYTHON_DEEPCHECKS) chequeos/validar_datos.py
	$(PYTHON_INTERPRETER) -m bandit -c pyproject.toml -r mibici -f txt --exit-zero
	$(PYTHON_INTERPRETER) -m bandit -c pyproject.toml -r mibici -q --severity-level medium
	$(PYTHON_INTERPRETER) -m pip_audit -r requirements.txt
	$(PYTHON_INTERPRETER) chequeos/secretos.py


## Pruebas y chequeos en un solo comando
.PHONY: verificar
verificar: test chequeos


#################################################################################
# Self Documenting Commands                                                     #
#################################################################################

.DEFAULT_GOAL := help

define PRINT_HELP_PYSCRIPT
import re, sys; \
lines = '\n'.join([line for line in sys.stdin]); \
matches = re.findall(r'\n## (.*)\n[\s\S]+?\n([a-zA-Z_-]+):', lines); \
print('Available rules:\n'); \
print('\n'.join(['{:25}{}'.format(*reversed(match)) for match in matches]))
endef
export PRINT_HELP_PYSCRIPT

help:
	@$(PYTHON_INTERPRETER) -c "${PRINT_HELP_PYSCRIPT}" < $(MAKEFILE_LIST)
