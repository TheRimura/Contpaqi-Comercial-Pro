from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.routes import productos_carnicos


class ProductoCarnicoConfigurado(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_configuracion: int | None = Field(default=None, gt=0)
    product_id: int | None = Field(default=None, gt=0)
    clave: str | None = Field(default=None, max_length=60)
    proveedor_id: int | None = Field(default=None, gt=0)
    proveedor: str = Field(min_length=2, max_length=250)
    nombre: str = Field(min_length=1, max_length=250)
    categoria: str | None = Field(default=None, max_length=100)
    categoria_resultante: str | None = Field(default=None, max_length=150)
    unidad: str = Field(default="KILO", min_length=1, max_length=50)
    porcentaje_merma: Decimal = Field(default=0, ge=0, le=100)
    activo: bool = True


class GuardarProductosCarnicos(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usuario_confirmacion_nombre: str = Field(min_length=2, max_length=150)
    productos: list[ProductoCarnicoConfigurado] = Field(default_factory=list)
