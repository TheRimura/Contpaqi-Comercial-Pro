from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class ProductoCarnicoConfig(BaseModel):
    id_configuracion: int | None = Field(default=None, ge=1)
    product_id: int | None = Field(default=None, ge=1)
    clave: str | None = Field(default=None, max_length=50)
    proveedor_id: int | None = Field(default=None, ge=1)
    proveedor_nombre: str | None = Field(default=None, max_length=150)
    nombre_producto: str = Field(min_length=1, max_length=250)
    categoria: str | None = Field(default=None, max_length=100)
    categoria_resultante: str | None = Field(default=None, max_length=150)
    unidad: str = Field(default="KILO", min_length=1, max_length=50)
    porcentaje_merma: Decimal = Field(default=0, ge=0, le=100)
    activo: bool = True

    @model_validator(mode="after")
    def validar_proveedor_activo(self):
        if self.activo and not (self.proveedor_nombre or "").strip():
            raise ValueError(
                "El proveedor es obligatorio para productos activos."
            )
        return self


class GuardarProductosCarnicos(BaseModel):
    usuario_confirmacion_nombre: str = Field(min_length=1, max_length=150)
    productos: list[ProductoCarnicoConfig] = Field(default_factory=list)


class RegistrarTransformacionCarnica(BaseModel):
    producto_salida_id: int | None = Field(default=None, gt=0)
    producto_entrada_id: int = Field(gt=0)
    categoria_base: str | None = Field(default=None, max_length=100)
    cantidad_salida: Decimal | None = Field(default=None, gt=0)
    cantidad_entrada: Decimal = Field(gt=0, le=999)
    cantidad_merma: Decimal = Field(default=0, ge=0)
    usuario_confirmacion_nombre: str = Field(min_length=1, max_length=150)
    observaciones: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validar_balance(self):
        if self.cantidad_salida is None:
            return self

        if self.cantidad_entrada > self.cantidad_salida:
            raise ValueError(
                "La entrada no puede ser mayor que la salida."
            )
        if self.cantidad_merma > self.cantidad_salida:
            raise ValueError(
                "La merma no puede ser mayor que la salida."
            )
        return self


class RegistrarSalidaCarnica(BaseModel):
    producto_salida_id: int = Field(gt=0)
    cantidad_salida: Decimal = Field(gt=0)
    proveedor_nombre: str = Field(min_length=1, max_length=150)
    usuario_confirmacion_nombre: str = Field(min_length=1, max_length=150)
    observaciones: str | None = Field(default=None, max_length=300)
