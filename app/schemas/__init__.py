from pydantic import BaseModel, ConfigDict, Field


class CredencialesAcceso(BaseModel):
    model_config = ConfigDict(extra='forbid')

    usuario: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


class SesionPublica(BaseModel):
    model_config = ConfigDict(extra='allow')

    acceso: bool
    user_id: int
    usuario: str
    user_group_id: int | None = None
    uso_llave_maestra: bool = False
    csrf: str | None = None
    mensaje: str | None = None


class SesionCerrada(BaseModel):
    model_config = ConfigDict(extra='forbid')

    acceso: bool = False
    mensaje: str
