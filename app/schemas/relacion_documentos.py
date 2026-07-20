from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.settings import AJUSTES_MODULO


class CrearRelacionDocumentos(BaseModel):
    source_document_id: int = Field(gt=0)
    destination_document_id: int = Field(gt=0)
    tipo_movimiento: str = Field(min_length=1, max_length=150)
    proveedor_id: int = Field(default=0, ge=0)
    usuario_fisico_id: int = Field(default=0, ge=0)
    fecha_movimiento: date
    source_brand_id: Optional[int] = Field(default=None, gt=0)
    destination_brand_id: Optional[int] = Field(default=None, gt=0)
    marca_nombre: Optional[str] = Field(default=None, max_length=150)

    @field_validator('tipo_movimiento')
    @classmethod
    def limpiar_movimiento(cls, valor: str) -> str:
        return ' '.join(valor.split())

    @model_validator(mode='after')
    def validar_documentos_distintos(self):
        if self.source_document_id == self.destination_document_id:
            raise ValueError('La entrada y la salida tiene que relacionarse .')
        return self


class CrearTransformacion(BaseModel):
    transformacion_config_id: int = Field(default=0, ge=0)
    linea: str = Field(min_length=1, max_length=100)
    producto_base_id: int = Field(gt=0)
    producto_resultante_id: int = Field(gt=0)
    cantidad_base: float = Field(
        gt=0, le=AJUSTES_MODULO.maximo_kilos_por_transformacion
    )
    cantidad_resultante: float = Field(
        gt=0, le=AJUSTES_MODULO.maximo_kilos_por_transformacion
    )
    usuario_fisico_id: int = Field(gt=0)

    @field_validator('linea')
    @classmethod
    def limpiar_linea(cls, valor: str) -> str:
        return ' '.join(valor.split()).upper()

    @model_validator(mode='after')
    def validar_rendimiento(self):
        esperado = round(
            self.cantidad_base * AJUSTES_MODULO.factor_rendimiento,
            3,
        )
        if abs(self.cantidad_resultante - esperado) > 0.001:
            raise ValueError(
                'El peso resultante no corresponde a la merma técnica '
                f'del {AJUSTES_MODULO.merma_tecnica_porcentaje:g}%.'
            )
        return self


class RespuestaRelacionDocumentos(BaseModel):
    mensaje: str
    source_document_id: int
    destination_document_id: int
    folio_salida: str
    folio_entrada: str
