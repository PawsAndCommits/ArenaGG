"""Schemas compartidos."""
from pydantic import BaseModel, ConfigDict


class ModeloRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MensajeResponse(BaseModel):
    mensaje: str
