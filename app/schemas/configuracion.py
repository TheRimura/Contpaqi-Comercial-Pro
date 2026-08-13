from pydantic import BaseModel, Field, field_validator, model_validator

from app.settings import AJUSTES_MODULO


class ComponenteConfiguracionTransformacion(BaseModel):
    producto_id: int = Field(gt=0)
    cantidad: float = Field(gt=0)
    unidad: str = Field(min_length=1, max_length=50)
    es_base: bool = False

    @field_validator('unidad')
    @classmethod
    def limpiar_unidad(cls, valor: str) -> str:
        return ' '.join(valor.split()).upper()

#LOS AJUSTES DEL MODULO POR KILOS NO DEBE DE CAMBIARSE AL MENOS QUE SEA AUTORIZADO

class CrearConfiguracionTransformacion(BaseModel):
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


class EventoAuditoriaConfiguracion(BaseModel):
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


class OcultarProductoCatalogo(BaseModel):
    producto_id: int
    es_configuracion: bool = False
    transformacion_id: int | None = Field(default=None, gt=0)
    nombre: str = Field(min_length=1, max_length=350)
    linea: str = Field(min_length=1, max_length=200)

    @field_validator('nombre', 'linea')
    @classmethod
    def limpiar_texto_ocultamiento(cls, valor: str) -> str:
        return ' '.join(valor.split())


class MensajeConfiguracion(BaseModel):
    mensaje: str = Field(min_length=1, max_length=300)


class ConfiguracionCreada(BaseModel):
    mensaje: str = Field(min_length=1, max_length=300)
    transformacion_id: int = Field(gt=0)


class ConfiguracionesCreadas(BaseModel):
    mensaje: str = Field(min_length=1, max_length=300)
    transformaciones_ids: list[int] = Field(min_length=1, max_length=20)
