from pydantic import BaseModel, Field, field_validator, model_validator


class CrearConfiguracionTransformacion(BaseModel):
    nombre: str = Field(min_length=3, max_length=150)
    linea: str = Field(min_length=1, max_length=100)
    producto_base_id: int = Field(gt=0)
    producto_resultante_id: int = Field(gt=0)
    cantidad_base: float = Field(gt=0)
    cantidad_resultante: float = Field(gt=0)
    observaciones: str | None = Field(default=None, max_length=500)

    @field_validator('nombre', 'linea')
    @classmethod
    def limpiar_texto(cls, valor: str) -> str:
        return ' '.join(valor.split())

    @model_validator(mode='after')
    def validar_merma_tecnica(self):
        esperado = round(self.cantidad_base * 0.92, 3)
        if abs(self.cantidad_resultante - esperado) > 0.001:
            raise ValueError(
                'El resultado esperado debe respetar la merma técnica del 8%.'
            )
        return self
