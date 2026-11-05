from pydantic import BaseModel, ConfigDict, Field, model_validator

EJEMPLO = {
    "estacion_id": 2, "salidas_h0": 0, "llegadas_h0": 4, "salidas_h1": 1, "llegadas_h1": 2, "salidas_h2": 0,
    "llegadas_h2": 1, "neto_3h": 6, "neto_futuro_semana_anterior": 0, "riesgo_semana_anterior": 0,
    "hora_dia": 0, "dia_semana": 5, "fin_de_semana": 1, "capacidad": 15,
}


class PeticionRiesgo(BaseModel):
    """Variables de una estación en la hora t, con los nombres de la firma del modelo de P2."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [EJEMPLO]})

    estacion_id: int | None = Field(default=None, ge=1, description="Identificador de la estación; solo se devuelve en la respuesta")
    salidas_h0: int = Field(ge=0, description="Salidas de la estación en la hora t")
    llegadas_h0: int = Field(ge=0, description="Llegadas a la estación en la hora t")
    salidas_h1: int = Field(ge=0, description="Salidas en la hora t-1")
    llegadas_h1: int = Field(ge=0, description="Llegadas en la hora t-1")
    salidas_h2: int = Field(ge=0, description="Salidas en la hora t-2")
    llegadas_h2: int = Field(ge=0, description="Llegadas en la hora t-2")
    neto_3h: int = Field(description="Llegadas menos salidas acumuladas de las horas t, t-1 y t-2")
    neto_futuro_semana_anterior: int = Field(description="Flujo neto de las dos horas siguientes a la misma hora de la semana anterior")
    riesgo_semana_anterior: int = Field(ge=0, le=1, description="Etiqueta de riesgo de la misma hora de la semana anterior")
    hora_dia: int = Field(ge=0, le=23, description="Hora del día, de 0 a 23")
    dia_semana: int = Field(ge=0, le=6, description="Día de la semana, de 0 (lunes) a 6 (domingo)")
    fin_de_semana: int = Field(ge=0, le=1, description="1 cuando dia_semana es 5 o 6")
    capacidad: int = Field(gt=0, description="Anclajes de la estación")

    @model_validator(mode="after")
    def variables_derivadas_coherentes(self):
        """neto_3h y fin_de_semana se derivan de las otras variables igual que en features.py."""
        neto = sum(getattr(self, f"llegadas_h{k}") - getattr(self, f"salidas_h{k}") for k in range(3))
        if self.neto_3h != neto:
            raise ValueError(f"neto_3h debe ser llegadas menos salidas de las tres horas, {neto}")
        if self.fin_de_semana != int(self.dia_semana >= 5):
            raise ValueError("fin_de_semana debe ser 1 solo cuando dia_semana es 5 o 6")
        return self


class ModeloServido(BaseModel):
    """Identidad del modelo que produjo la predicción, tal como está en el Model Registry."""

    model_config = ConfigDict(extra="forbid")

    nombre: str
    version: str | None
    alias: str | None


class RespuestaRiesgo(BaseModel):
    """Riesgo de que la estación se llene o se vacíe en las dos horas siguientes."""

    model_config = ConfigDict(extra="forbid")

    estacion_id: int | None
    riesgo: int = Field(ge=0, le=1, description="1 si la estación está en riesgo; es probabilidad >= umbral")
    probabilidad: float = Field(ge=0, le=1, description="Probabilidad de riesgo que estima el modelo")
    umbral: float = Field(gt=0, lt=1, description="Umbral de decisión que viaja dentro del modelo")
    modelo: ModeloServido


class ColumnaFirma(BaseModel):
    nombre: str
    tipo: str


class Metadata(BaseModel):
    """Modelo cargado, columnas de su firma en el orden del entrenamiento y versión de MLflow."""

    nombre: str
    version: str | None
    alias: str | None
    origen: str
    run_id: str
    umbral: float
    columnas: list[ColumnaFirma]
    mlflow: str


class Salud(BaseModel):
    estado: str
    modelo: str
    version: str | None
