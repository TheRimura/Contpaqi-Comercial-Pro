from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProductoConfigurado(BaseModel):
    model_config = ConfigDict(extra="forbid")

    producto_id: int = Field(gt=0)
    cantidad: Decimal = Field(gt=0)
    unidad: str = Field(default="KILO", min_length=1, max_length=50)
    participa_balance: bool = True
    orden: int = Field(default=1, ge=1)

class CrearConfiguracionTransformacion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre_transformacion: str = Field(min_length=3, max_length=150)
    producto_origen_id: int = Field(gt=0)
    producto_formula_id: int | None = Field(default=None, gt=0)
    cantidad_base: Decimal = Field(gt=0)
    porcentaje_merma: Decimal | None = Field(default=None, ge=0, le=100)
    observaciones: str | None = Field(default=None, max_length=500)
    productos_resultantes: list[ProductoConfigurado] = Field(min_length=1)

    @model_validator(mode="after")
    def validar_productos(self):
        ids_resultantes = [
            producto.producto_id
            for producto in self.productos_resultantes
        ]

        if len(ids_resultantes) != len(set(ids_resultantes)):
            raise ValueError(
                "No se pueden repetir productos resultantes"
            )

        return self
