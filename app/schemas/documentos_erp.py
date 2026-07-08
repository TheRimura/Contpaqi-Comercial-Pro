from datetime import date

from pydantic import BaseModel, Field


class CrearRelacionDocumentosERP(BaseModel):
    source_document_id: int = Field(gt=0)
    destination_document_id: int = Field(gt=0)
    tipo_movimiento_origen_id: int = Field(default=0, ge=0)
    tipo_movimiento_destino_id: int = Field(default=0, ge=0)
    tipo_movimiento_texto: str | None = Field(default=None, max_length=120)
    proveedor_id: int = Field(gt=0)
    usuario_fisico_id: int = Field(gt=0)
    fecha_movimiento: date | None = None
    folio_source_document_id: str | None = Field(default=None, max_length=125)
    folio_destination_document_id: str | None = Field(
        default=None,
        max_length=125,
    )
    source_brand_id: int | None = Field(default=None, ge=1)
    destination_brand_id: int | None = Field(default=None, ge=1)

