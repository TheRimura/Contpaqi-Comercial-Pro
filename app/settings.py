from dataclasses import dataclass


@dataclass(frozen=True)
class AjustesModulo:
    merma_tecnica_porcentaje: float = 8.0
    nombres_con_merma_configurable: tuple[str, ...] = (
        "MOLIDA",
        "MOLIDO",
    )
    transformaciones_por_pagina: int = 10
    productos_por_pagina: int = 10
    maximo_kilos_por_transformacion: float = 3_000.0
    maximo_intentos_login: int = 3
    ventana_intentos_login_segundos: int = 300

    def validar_ajustes_operativos(self) -> None:
        if not 0 <= self.merma_tecnica_porcentaje < 100:
            raise ValueError("La merma técnica debe estar entre 0 y 99.99%.")
        if not 4 <= self.transformaciones_por_pagina <= 60:
            raise ValueError(
                "La paginación de transformaciones debe estar entre 4 y 60."
            )
        if not 4 <= self.productos_por_pagina <= 60:
            raise ValueError(
                "La paginación de productos debe estar entre 4 y 60."
            )
        if self.maximo_kilos_por_transformacion <= 0:
            raise ValueError("El máximo de kilos debe ser mayor que cero.")
        if self.maximo_intentos_login < 3:
            raise ValueError("El límite de intentos de acceso debe ser al menos 3.")
        if self.ventana_intentos_login_segundos < 60:
            raise ValueError("La ventana de intentos debe ser al menos de 60 segundos.")

    @property
    def factor_rendimiento(self) -> float:
        return 1 - (self.merma_tecnica_porcentaje / 100)

    def transformacion_permite_merma_personalizada(
        self,
        nombre_transformacion: str,
    ) -> bool:
        nombre_normalizado = " ".join(
            str(nombre_transformacion or "").upper().split()
        )
        return any(
            palabra in nombre_normalizado
            for palabra in self.nombres_con_merma_configurable
        )


# AJUSTES EDITABLES DEL MÓDULO
AJUSTES_MODULO = AjustesModulo()
AJUSTES_MODULO.validar_ajustes_operativos()

@dataclass(frozen=True)
class PermisosModulo:
    """Grupos autorizados para cada operación del módulo."""

    grupos_acceso_modulo: frozenset[int]
    grupos_ver_configuracion: frozenset[int]
    grupos_ver_auditoria: frozenset[int]
    grupos_ver_historial: frozenset[int]
    grupos_crear_configuracion: frozenset[int]
    grupos_registrar_transformaciones: frozenset[int]
    grupos_eliminar_productos_catalogo: frozenset[int]


    def validar_coherencia_de_permisos(self) -> None:
        if not self.grupos_acceso_modulo:
            raise ValueError(
                "Debe existir al menos un grupo con acceso al módulo."
            )

        grupos_con_permisos_internos = (
            self.grupos_ver_configuracion
            | self.grupos_ver_auditoria
            | self.grupos_ver_historial
            | self.grupos_crear_configuracion
            | self.grupos_registrar_transformaciones
            | self.grupos_eliminar_productos_catalogo

        )
        if not grupos_con_permisos_internos.issubset(
            self.grupos_acceso_modulo
        ):
            raise ValueError(
                "Los grupos con permisos internos también deben tener "
                "acceso al módulo."
            )

        if not self.grupos_crear_configuracion.issubset(
            self.grupos_ver_configuracion
        ):
            raise ValueError(
                "Un grupo que crea configuraciones también debe poder "
                "ver Configuración."
            )
        if not self.grupos_ver_auditoria.issubset(
            self.grupos_ver_configuracion
        ):
            raise ValueError(
                "Un grupo que consulta auditoría también debe poder "
                "ver Configuración."
            )
        if not self.grupos_eliminar_productos_catalogo.issubset(
            self.grupos_ver_configuracion
        ):
            raise ValueError(
                "Un grupo que elimina productos del catálogo también debe "
                "poder ver Configuración."
            )

    def grupo_tiene_permiso(
        self,
        grupo_id: int,
        nombre_permiso: str,
    ) -> bool:
        grupos_autorizados_por_permiso = {
            "acceso_modulo": self.grupos_acceso_modulo,
            "ver_configuracion": self.grupos_ver_configuracion,
            "ver_auditoria": self.grupos_ver_auditoria,
            "ver_historial": self.grupos_ver_historial,
            "crear_configuracion": self.grupos_crear_configuracion,
            "registrar_transformaciones": (
                self.grupos_registrar_transformaciones
            ),
            "eliminar_productos_catalogo": (
                self.grupos_eliminar_productos_catalogo
            ),

        }
        if nombre_permiso not in grupos_autorizados_por_permiso:
            raise ValueError(
                f"Permiso desconocido: {nombre_permiso}"
            )
        return int(grupo_id or 0) in grupos_autorizados_por_permiso[
            nombre_permiso
        ]


# PERMISOS EDITABLES

PERMISOS_MODULO = PermisosModulo(
    grupos_acceso_modulo=frozenset({1,12}),
    grupos_ver_configuracion=frozenset({1,12}),
    grupos_ver_auditoria=frozenset({1,}),
    grupos_ver_historial=frozenset({1,12}),
    grupos_crear_configuracion=frozenset({1,}),
    grupos_registrar_transformaciones=frozenset({1,12}),
    grupos_eliminar_productos_catalogo=frozenset({1}),
)
PERMISOS_MODULO.validar_coherencia_de_permisos()
