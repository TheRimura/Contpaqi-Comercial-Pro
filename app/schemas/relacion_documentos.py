from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.settings import AJUSTES_MODULO


def convertir_pascal(nombre: str) -> str:
    return ''.join(
        'ID' if parte == 'id' else parte.capitalize()
        for parte in nombre.split('_')
    )


class ModeloRelacion(BaseModel):
    model_config = ConfigDict(
        alias_generator=convertir_pascal,
        populate_by_name=True,
        serialize_by_alias=True,
        extra='forbid',
    )


class CrearTransformacion(ModeloRelacion):
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

class RespuestaRelacionDocumentos(ModeloRelacion):
    mensaje: str
    source_document_id: int
    destination_document_id: int
    folio_salida: str
    folio_entrada: str


class LineaTransformacion(ModeloRelacion):
    category1: str
    total_productos: int = Field(ge=0)
    total_recetas: int = Field(ge=0)


class TransformacionPrecargada(ModeloRelacion):
    transformacion_id: int = Field(gt=0)
    nombre_transformacion: str
    producto_base_id: int = Field(gt=0)
    producto_base: str
    linea: str
    proveedor: str = ''


class ProductoBaseTransformacion(ModeloRelacion):
    producto_base: str
    product_id_base: int = Field(gt=0)
    total_resultantes: int = Field(ge=0)


class TransformacionDisponible(TransformacionPrecargada):
    proveedor: str = ''
    tiene_formula: bool = False
    origen_catalogo: bool = False


class FoliosTransformacion(ModeloRelacion):
    folio_salida: str
    folio_entrada: str


class RegistroHistorial(ModeloRelacion):
    relacion_id: int = Field(gt=0)
    documento_salida_id: int = Field(gt=0)
    documento_entrada_id: int = Field(gt=0)
    fecha: date
    fecha_hora: datetime
    folio_salida: str
    folio_entrada: str
    tablajero_id: int = Field(gt=0)
    usuario_erp_id: int = Field(gt=0)
    producto_base: str
    linea: str
    cantidad_base: float = Field(ge=0)
    producto_resultante: str
    cantidad_resultante: float = Field(ge=0)
    es_documento_lote: bool = False
    total_partidas: int = Field(ge=0)
    total_insumos: int = Field(ge=0)


class PaginaHistorial(ModeloRelacion):
    registros: list[RegistroHistorial]
    pagina: int = Field(ge=1)
    por_pagina: int = Field(ge=1)
    total_registros: int = Field(ge=0)
    total_paginas: int = Field(ge=0)


class ResumenHistorial(ModeloRelacion):
    transformaciones: int = Field(ge=0)
    kilos_procesados: float = Field(ge=0)
    merma_acumulada: float = Field(ge=0)
    rendimiento: float = Field(ge=0)


class PartidaDocumento(ModeloRelacion):
    product_id: int = Field(gt=0)
    category: str = ''
    product_key: str = ''
    product_name: str
    unit: str
    quantity: float = Field(ge=0)
    cost_price: float = Field(ge=0)
    total: float = Field(ge=0)


class DetalleHistorial(ModeloRelacion):
    relacion_id: int = Field(gt=0)
    documento_salida_id: int = Field(gt=0)
    documento_entrada_id: int = Field(gt=0)
    folio_salida: str
    folio_entrada: str
    fecha_hora: datetime
    tablajero_id: int = Field(gt=0)
    usuario_erp_id: int = Field(gt=0)
    salida: list[PartidaDocumento]
    entrada: list[PartidaDocumento]
    es_documento_lote: bool = False


class PartidaExportacion(ModeloRelacion):
    relacion_id: int = Field(gt=0)
    fecha_hora: datetime
    folio_salida: str
    folio_entrada: str
    tablajero_id: int = Field(gt=0)
    usuario_erp_id: int = Field(gt=0)
    tipo_documento: str
    folio_documento: str
    producto: str
    cantidad: float = Field(ge=0)
