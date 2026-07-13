from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class CrearRelacionDocumentos(BaseModel):
    source_document_id: int = Field(gt=0)
    destination_document_id: int = Field(gt=0)
    tipo_movimiento: str = Field(min_length=1, max_length=150)
    proveedor_id: int = Field(gt=0)
    usuario_fisico_id: int = Field(gt=0)
    fecha_movimiento: date
    source_brand_id: Optional[int] = Field(default=None, gt=0)
    destination_brand_id: Optional[int] = Field(default=None, gt=0)

    @field_validator('tipo_movimiento')
    @classmethod
    def limpiar_movimiento(cls, valor: str) -> str:
        return ' '.join(valor.split())

    @model_validator(mode='after')
    def validar_documentos_distintos(self):
        if self.source_document_id == self.destination_document_id:
            raise ValueError('La entrada y la salida no pueden ser el mismo documento.')
        return self


class RespuestaRelacionDocumentos(BaseModel):
    mensaje: str
    source_document_id: int
    destination_document_id: int
    folio_salida: str
    folio_entrada: str
