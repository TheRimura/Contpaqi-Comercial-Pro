from dataclasses import dataclass

@dataclass(frozen=True)
class PermisosModulo:
    # Grupos de que pueden iniciar sesión y entrar al módulo.
    grupos_acceso_modulo: frozenset[int]
    # Grupos que pueden abrir el botón/pantalla Configuración.
    grupos_ver_configuracion: frozenset[int]
    # Grupos que pueden consultar las transformaciones realizadas.
    grupos_ver_historial: frozenset[int]
    # Grupos que pueden guardar nuevas configuraciones.
    grupos_crear_configuracion: frozenset[int]
    # Grupos que pueden registrar una transformación en SSM.
    grupos_registrar_transformaciones: frozenset[int]

    def __post_init__(self):
        if not self.grupos_acceso_modulo:
            raise ValueError("Debe existir al menos un grupo con acceso al módulo.")
        grupos_dependientes = (
            self.grupos_ver_configuracion
            | self.grupos_ver_historial
            | self.grupos_crear_configuracion
            | self.grupos_registrar_transformaciones
        )
        if not grupos_dependientes.issubset(self.grupos_acceso_modulo):
            raise ValueError(
                "Los grupos con permisos internos también deben tener acceso al módulo."
            )
        if not self.grupos_crear_configuracion.issubset(
            self.grupos_ver_configuracion
        ):
            raise ValueError(
                "Un grupo que crea configuraciones también debe poder ver Configuración."
            )

    def permite(self, grupo_id: int, permiso: str) -> bool:
        grupos_por_permiso = {
            "acceso_modulo": self.grupos_acceso_modulo,
            "ver_configuracion": self.grupos_ver_configuracion,
            "ver_historial": self.grupos_ver_historial,
            "crear_configuracion": self.grupos_crear_configuracion,
            "registrar_transformaciones": self.grupos_registrar_transformaciones,
        }
        if permiso not in grupos_por_permiso:
            raise ValueError(f"Permiso desconocido: {permiso}")
        return int(grupo_id or 0) in grupos_por_permiso[permiso]


@dataclass(frozen=True)
class AjustesModulo:
    merma_tecnica_porcentaje: float = 8.0
    transformaciones_por_pagina: int = 12
    productos_por_pagina: int = 12
    maximo_kilos_por_transformacion: float = 10_000.0

    def __post_init__(self):
        if not 0 <= self.merma_tecnica_porcentaje < 100:
            raise ValueError("La merma técnica debe estar entre 0 y 99.99%.")
        if not 4 <= self.transformaciones_por_pagina <= 60:
            raise ValueError("La paginación de transformaciones debe estar entre 4 y 60.")
        if not 4 <= self.productos_por_pagina <= 60:
            raise ValueError("La paginación de productos debe estar entre 4 y 60.")
        if self.maximo_kilos_por_transformacion <= 0:
            raise ValueError("El máximo de kilos debe ser mayor que cero.")

    @property
    def factor_rendimiento(self) -> float:
        return 1 - (self.merma_tecnica_porcentaje / 100)

# PERMISOS EDITABLES
# Para autorizar otro grupo, agréguelo dentro de las llaves. Ejemplo: {1, 3}.

PERMISOS_MODULO = PermisosModulo(
    grupos_acceso_modulo=frozenset({1,12}),
    grupos_ver_configuracion=frozenset({1}),
    grupos_ver_historial=frozenset({1}),
    grupos_crear_configuracion=frozenset({1}),
    grupos_registrar_transformaciones=frozenset({1,12}),
)


# Ajustes operativos permitidos. No agregue consultas SQL ni contraseñas aquí.
AJUSTES_MODULO = AjustesModulo()
