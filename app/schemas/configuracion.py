import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.settings import AJUSTES_MODULO


def convertir_pascal(nombre: str) -> str:
    return ''.join(
        'ID' if parte == 'id' else parte.capitalize()
        for parte in nombre.split('_')
    )


class ModeloConfiguracion(BaseModel):
    model_config = ConfigDict(
        alias_generator=convertir_pascal,
        populate_by_name=True,
        serialize_by_alias=True,
        extra='forbid',
    )


class ComponenteConfiguracionTransformacion(ModeloConfiguracion):
    producto_id: int = Field(gt=0)
    cantidad: float = Field(gt=0)
    unidad: str = Field(min_length=1, max_length=50)
    es_base: bool = False

    @field_validator('unidad')
    @classmethod
    def limpiar_unidad(cls, valor: str) -> str:
        return ' '.join(valor.split()).upper()

#LOS AJUSTES DEL MODULO POR KILOS NO DEBE DE CAMBIARSE AL MENOS QUE SEA AUTORIZADO

class CrearConfiguracionTransformacion(ModeloConfiguracion):
    nombre: str = Field(min_length=3, max_length=150)
    linea: str = Field(min_length=1, max_length=100)
    cantidad_base: float = Field(
        gt=0, le=AJUSTES_MODULO.maximo_kilos_por_transformacion
    )
    porcentaje_merma: float = Field(ge=0, lt=100)
    componentes: list[ComponenteConfiguracionTransformacion] = Field(
        min_length=1,
        max_length=100,
    )
    observaciones: str | None = Field(default=None, max_length=500)
    motivo_auditoria: str = Field(
        default='Configuración registrada desde el módulo',
        min_length=5,
        max_length=300,
    )


    @field_validator('nombre', 'linea')
    @classmethod
    def limpiar_texto(cls, valor: str) -> str:
        return ' '.join(valor.split())

    @model_validator(mode='after')
    def validar_componentes(self):
        if not AJUSTES_MODULO.transformacion_permite_merma_personalizada(
            self.nombre
        ):
            self.porcentaje_merma = (
                AJUSTES_MODULO.merma_tecnica_porcentaje
            )
        productos = [componente.producto_id for componente in self.componentes]
        if len(productos) != len(set(productos)):
            raise ValueError('No se puede agregar dos veces el mismo insumo.')
        bases = [componente for componente in self.componentes if componente.es_base]
        if len(bases) != 1:
            raise ValueError(
                'Debes marcar exactamente un componente como producto base.'
            )
        return self


class EventoAuditoriaConfiguracion(ModeloConfiguracion):
    accion: str = Field(min_length=3, max_length=30)
    configuracion_id: int | None = Field(default=None, gt=0)
    configuracion_nombre: str = Field(min_length=1, max_length=150)
    motivo: str = Field(min_length=5, max_length=300)
    valores_anteriores: dict | None = None
    valores_nuevos: dict | None = None

    @field_validator('accion')
    @classmethod
    def validar_accion(cls, valor: str) -> str:
        accion = valor.strip().upper()
        alias = {
            'CREO': 'CREAR',
            'EDITO': 'EDITAR',
            'ELIMINO': 'ELIMINAR',
        }
        accion = alias.get(accion, accion)
        if accion not in {'CREAR', 'EDITAR', 'ELIMINAR'}:
            raise ValueError('La acción de auditoría no es válida.')
        return accion

    @field_validator('configuracion_nombre', 'motivo')
    @classmethod
    def limpiar_texto_auditoria(cls, valor: str) -> str:
        return ' '.join(valor.split())


class OcultarProductoCatalogo(ModeloConfiguracion):
    producto_id: int
    es_configuracion: bool = False
    transformacion_id: int | None = Field(default=None, gt=0)
    nombre: str = Field(min_length=1, max_length=350)
    linea: str = Field(min_length=1, max_length=200)

    @field_validator('nombre', 'linea')
    @classmethod
    def limpiar_texto_ocultamiento(cls, valor: str) -> str:
        return ' '.join(valor.split())


class MensajeConfiguracion(ModeloConfiguracion):
    mensaje: str = Field(min_length=1, max_length=300)


class ConfiguracionCreada(ModeloConfiguracion):
    mensaje: str = Field(min_length=1, max_length=300)
    transformacion_id: int = Field(gt=0)


class ConfiguracionesCreadas(ModeloConfiguracion):
    mensaje: str = Field(min_length=1, max_length=300)
    transformaciones_ids: list[int] = Field(min_length=1, max_length=20)


class ProductoCatalogo(ModeloConfiguracion):
    product_id: int
    producto: str
    unidad: str
    fecha_creacion: datetime | None = None
    es_reciente: bool = False
    tiene_receta: bool = False
    es_configuracion: bool = False
    transformacion_id: int | None = None


class ProductoResultante(ModeloConfiguracion):
    product_id: int = Field(gt=0)
    producto: str
    unidad: str


class BaseSugerida(ModeloConfiguracion):
    producto_resultante_id: int | None = None
    producto_resultante: str
    producto_base_id: int = Field(gt=0)
    producto_base: str
    unidad: str


class ComponenteDisponible(ModeloConfiguracion):
    product_id: int = Field(gt=0)
    producto: str
    unidad: str
    cantidad_por_kilo: float = Field(ge=0)


class ComponenteFormula(ModeloConfiguracion):
    product_id: int = Field(gt=0)
    producto: str
    cantidad: float = Field(ge=0)
    unidad: str
    linea: str
    formula_id: int = Field(gt=0)
    formula: str


class RegistroAuditoria(ModeloConfiguracion):
    id_auditoria: int = Field(gt=0)
    configuracion_id: int | None = None
    configuracion_nombre: str
    accion: str
    usuario_id: int | None = None
    usuario_nombre: str
    motivo: str
    valores_anteriores: dict | None = None
    valores_nuevos: dict | None = None
    fecha: datetime

    @field_validator('valores_anteriores', 'valores_nuevos', mode='before')
    @classmethod
    def convertir_valores_json(cls, valor):
        if valor in (None, ''):
            return None
        if isinstance(valor, dict):
            return valor
        if isinstance(valor, str):
            try:
                convertido = json.loads(valor)
            except json.JSONDecodeError:
                return {'valor': valor}
            return convertido if isinstance(convertido, dict) else {
                'valor': convertido
            }
        return {'valor': valor}


class AuditoriaCreada(ModeloConfiguracion):
    auditoria_id: int = Field(gt=0)
