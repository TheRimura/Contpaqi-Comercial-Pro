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


class CrearConfiguracionTransformacion(BaseModel):
    nombre: str = Field(min_length=3, max_length=150)
    linea: str = Field(min_length=1, max_length=100)
    proveedor_id: int = Field(gt=0)
    cantidad_base: float = Field(
        gt=0, le=AJUSTES_MODULO.maximo_kilos_por_transformacion
    )
    porcentaje_merma: float = Field(ge=0, lt=100)
    componentes: list[ComponenteConfiguracionTransformacion] = Field(
        min_length=1,
        max_length=100,
    )
    observaciones: str | None = Field(default=None, max_length=500)

    @field_validator('nombre', 'linea')
    @classmethod
    def limpiar_texto(cls, valor: str) -> str:
        return ' '.join(valor.split())

    @model_validator(mode='after')
    def validar_componentes(self):
        productos = [componente.producto_id for componente in self.componentes]
        if len(productos) != len(set(productos)):
            raise ValueError('No se puede agregar dos veces el mismo insumo.')
        bases = [componente for componente in self.componentes if componente.es_base]
        if len(bases) != 1:
            raise ValueError(
                'Debes marcar exactamente un componente como producto base.'
            )
        return self
