import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Body, Depends, FastAPI, HTTPException

from api import esquemas, modelo

registro = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def ciclo_de_vida(aplicacion):
    """Carga el modelo una sola vez al arrancar; si falla, los endpoints responden 503 hasta reiniciar."""
    try:
        aplicacion.state.modelo = modelo.cargar()
        registro.info("modelo %s versión %s cargado desde %s", modelo.NOMBRE, aplicacion.state.modelo["version"],
                      aplicacion.state.modelo["origen"])
    except Exception as error:
        aplicacion.state.modelo = None
        registro.error("el modelo %s no se pudo cargar: %s", modelo.NOMBRE, error)
    yield


app = FastAPI(
    title="MiBici, riesgo por estación (P2)",
    description="Servicio de predicción del proyecto MiBici del equipo 38: expone el modelo en producción de la "
                "pregunta P2 (riesgo de que una estación se llene o se vacíe en las dos horas siguientes), cargado "
                "por nombre y alias desde el Model Registry de MLflow.",
    version="1.0",
    lifespan=ciclo_de_vida,
    swagger_ui_parameters={"docExpansion": "full", "defaultModelRendering": "model"},
)
app.state.modelo = None


def modelo_cargado():
    """El modelo en memoria; 503 mientras no haya cargado."""
    if app.state.modelo is None:
        raise HTTPException(status_code=503, detail=f"el modelo {modelo.NOMBRE} no está cargado")
    return app.state.modelo


Modelo = Annotated[dict, Depends(modelo_cargado)]


@app.get("/health", response_model=esquemas.Salud)
def salud(cargado: Modelo):
    """200 solo cuando el modelo está cargado y listo para predecir."""
    return esquemas.Salud(estado="ok", modelo=cargado["nombre"], version=cargado["version"])


@app.get("/metadata", response_model=esquemas.Metadata)
def metadata(cargado: Modelo):
    """Nombre, versión y alias del modelo, columnas de su firma y versión de MLflow."""
    return modelo.metadata(cargado)


@app.post("/predecir", response_model=esquemas.RespuestaRiesgo)
def predecir(peticion: esquemas.PeticionRiesgo, cargado: Modelo):
    """Riesgo y probabilidad de una estación en la hora t para las dos horas siguientes."""
    return modelo.predecir(cargado, [peticion])[0]


@app.post("/predecir/lote", response_model=list[esquemas.RespuestaRiesgo])
def predecir_lote(peticiones: Annotated[list[esquemas.PeticionRiesgo], Body(min_length=1)], cargado: Modelo):
    """Una predicción por petición, en el mismo orden; sirve para todas las estaciones de una hora."""
    return modelo.predecir(cargado, peticiones)
