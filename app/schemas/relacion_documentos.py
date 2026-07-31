from pydantic import BaseModel, Field, field_validator

from app.settings import AJUSTES_MODULO


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

class RespuestaRelacionDocumentos(BaseModel):
    mensaje: str
    source_document_id: int
    destination_document_id: int
    folio_salida: str
    folio_entrada: str

