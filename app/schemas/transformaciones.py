from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ProductoResultante(BaseModel):
    producto_id: int = Field(gt=0)
    cantidad: Decimal = Field(gt=0)


class CrearTransformacion(BaseModel):
    producto_origen_id: int = Field(gt=0)
    cantidad_origen: Decimal = Field(gt=0)
    productos_resultantes: list[ProductoResultante] = Field(min_length=1)
    producto_base_formula_id: int | None = Field(default=None, gt=0)

    usuario_id: int | None = Field(default=None, gt=0)
    usuario_nombre: str | None = Field(default=None, max_length=100)
    tipo_transformacion: Literal[
        "receta_configurada",
        "producto_final",
    ] = "receta_configurada"
    producto_ya_transformado: bool = False
    peso_merma: Decimal = Field(default=Decimal("0"), ge=0)
    porcentaje_merma_esperado: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    observaciones_merma: str | None = Field(default=None, max_length=250)

    @model_validator(mode="after")
    def calcular_merma(self):
        if self.producto_ya_transformado:
            self.tipo_transformacion = "producto_final"

        self.producto_ya_transformado = (
            self.tipo_transformacion == "producto_final"
        )

        if self.tipo_transformacion == "producto_final":
            if len(self.productos_resultantes) != 1:
                raise ValueError(
                    "Un producto final solo puede registrarse con una salida"
                )

            producto_resultante = self.productos_resultantes[0]

            if producto_resultante.producto_id != self.producto_origen_id:
                raise ValueError(
                    "El producto final debe salir con el mismo producto"
                )

        total_resultante = sum(
            producto.cantidad
            for producto in self.productos_resultantes
        )
        merma_calculada = self.cantidad_origen - total_resultante

        if merma_calculada < 0:
            raise ValueError(
                "Los productos resultantes no pueden superar "
                "la cantidad de origen"
            )

        self.peso_merma = merma_calculada
        return self
