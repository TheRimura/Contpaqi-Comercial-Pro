from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

class CrearRelacionDocumentos(BaseModel):
    source_document_id: int = Field(
        gt=0,
        description="DocumentID de la salida, modulo 203"
    )
    destination_document_id: int = Field(
        gt=0,
        description="DocumentID de la salida, modulo 202"
    )
    tipo_movimiento: str = Field(min_length=1, max_length=150)
    proveedor_id: int = Field(gt=0)
    usuario_fisico_id: int = Field(gt=0)
    fecha_movimiento: date
    source_band_id: Optional[int]= Field(default=None)
    destination_band_id: Optional[int]= Field(default=None, gt=0)

    @field_validator("Tipo_movimiento")
    @classmethod
    def limpiar_tipo_movimiento(cls, valor: str) -> str:
        valor_limpio = "".join(str(valor).split())

        if not valor_limpio:
            raise ValueError("Selecciona un tipo de movimiento.")

        return valor_limpio

class RespuestaRelacionDocumentos(BaseModel):
    mensaje: str
    source_document_id: int
    destination_document_id: int
    folio_salida: str
    folio_entrada: str 