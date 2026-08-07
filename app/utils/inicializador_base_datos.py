from dataclasses import dataclass
from pathlib import Path

from app.utils.base_de_datos import BaseDatos, obtener_base_datos


DEPENDENCIAS_NATIVAS_SSM = (
    "dbo.orgProduct",
    "dbo.zvwFormulasListasPCocinar",
    "dbo.engUser",
    "dbo.engUserCayal",
    "dbo.engUserGroup",
    "dbo.docDocument",
    "dbo.docDocumentItem",
    "dbo.docDocumentWarehouseRelation",
    "dbo.engRefCombo",
    "dbo.engDocumentFolio",
    "dbo.orgSupplier",
    "dbo.orgBusinessEntity",
    "dbo.orgProductSupplier",
    "dbo.zvwEmpleadosCayalMenu",
    "dbo.zvwCrearDocumentoCayal",
    "dbo.zvwInsertarProductoCayal",
)

TABLAS_PROPIAS_MODULO = (
    "dbo.TransformacionesUsuario",
    "dbo.TransformacionesUsuarioDetalle",
    "dbo.TransformacionesUsuarioComponente",
    "dbo.ModuloCarnicoConfiguracionAuditoria",
    "dbo.ModuloCarnicoConfiguracionSeguridad",
    "dbo.ModuloCarnicoProductoConfigurado",
    "dbo.ModuloCarnicoProductoBitacora",
    "dbo.ModuloCarnicoTransformacionRegistro",
    "dbo.ModuloCarnicoCatalogoOculto",
    "dbo.ModuloAlmacenMarca",
)

COLUMNAS_ESENCIALES_MODULO = {
    "dbo.TransformacionesUsuario": (
        "id_transformacion_usuario",
        "nombre_transformacion",
        "producto_origen",
        "cantidad_base",
        "porcentaje_merma",
        "activa",
    ),
    "dbo.TransformacionesUsuarioDetalle": (
        "id_transformacion_usuario",
        "producto_resultante",
        "cantidad_resultante",
        "activa",
    ),
    "dbo.TransformacionesUsuarioComponente": (
        "id_transformacion_usuario",
        "producto_componente",
        "cantidad",
        "es_producto_base",
        "activa",
    ),
    "dbo.ModuloCarnicoConfiguracionAuditoria": (
        "id_auditoria",
        "accion",
        "usuario_nombre",
        "fecha",
    ),
    "dbo.ModuloCarnicoConfiguracionSeguridad": (
        "id_configuracion",
        "clave_firma",
        "fecha_creacion",
    ),
    "dbo.ModuloCarnicoProductoConfigurado": (
        "id_producto_carnico",
        "product_id",
        "nombre_producto",
        "unidad",
        "porcentaje_merma",
        "activo",
    ),
    "dbo.ModuloCarnicoProductoBitacora": (
        "id_bitacora",
        "accion",
        "usuario_confirmacion_nombre",
        "fecha",
    ),
    "dbo.ModuloCarnicoTransformacionRegistro": (
        "id_registro",
        "producto_salida_config_id",
        "producto_entrada_config_id",
        "cantidad_salida",
        "cantidad_entrada",
        "cantidad_merma",
        "porcentaje_merma",
        "fecha",
        "id_transformacion",
        "categoria_base",
    ),
    "dbo.ModuloCarnicoCatalogoOculto": (
        "product_id",
        "nombre",
        "linea",
        "activo",
        "usuario_id",
        "fecha",
    ),
    "dbo.ModuloAlmacenMarca": (
        "BrandID",
        "BrandName",
        "categoria",
        "activo",
    ),
}

RUTA_SCRIPT_SQL = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "inicializar_modulo_carnico.sql"
)


@dataclass(frozen=True)
class ReporteInicializacion:
    servidor: str
    base_datos: str
    tablas_creadas: tuple[str, ...]
    tablas_reutilizadas: tuple[str, ...]
    dependencias_validadas: int


def _objeto_existe(base_datos: BaseDatos, nombre: str) -> bool:
    return bool(
        base_datos.fetchone(
            "SELECT OBJECT_ID(?)",
            (nombre,),
        )
    )


def _obtener_contexto(base_datos: BaseDatos) -> tuple[str, str]:
    filas = base_datos.fetchall(
        """
        SELECT
            CONVERT(NVARCHAR(128), SERVERPROPERTY('ServerName')) AS servidor,
            DB_NAME() AS base_datos
        """,
        (),
    )
    if not filas:
        raise RuntimeError(
            "SQL Server no devolvió el nombre del servidor y la base de datos."
        )
    return str(filas[0]["servidor"]), str(filas[0]["base_datos"])


def _validar_dependencias_nativas(base_datos: BaseDatos) -> None:
    faltantes = [
        nombre
        for nombre in DEPENDENCIAS_NATIVAS_SSM
        if not _objeto_existe(base_datos, nombre)
    ]
    if faltantes:
        detalle = ", ".join(faltantes)
        raise RuntimeError(
            "La base de datos no contiene objetos nativos requeridos por "
            f"SSM: {detalle}. No se crearán sustitutos incompatibles."
        )



def _validar_columnas_modulo(base_datos: BaseDatos) -> None:
    faltantes = []
    for tabla, columnas in COLUMNAS_ESENCIALES_MODULO.items():
        for columna in columnas:
            existe = base_datos.fetchone(
                "SELECT COL_LENGTH(?, ?)",
                (tabla, columna),
            )
            if existe is None:
                faltantes.append(f"{tabla}.{columna}")
    if faltantes:
        raise RuntimeError(
            "La estructura del módulo quedó incompleta. Faltan: "
            + ", ".join(faltantes)
        )


def inicializar_base_datos_modulo(
    base_datos: BaseDatos | None = None,
) -> ReporteInicializacion:
    base_datos = base_datos or obtener_base_datos()
    if not base_datos.probar_conexion():
        raise RuntimeError("No fue posible conectar con SQL Server.")

    servidor, nombre_base_datos = _obtener_contexto(base_datos)
    _validar_dependencias_nativas(base_datos)

    existentes_antes = {
        tabla
        for tabla in TABLAS_PROPIAS_MODULO
        if _objeto_existe(base_datos, tabla)
    }
    if not RUTA_SCRIPT_SQL.is_file():
        raise RuntimeError(
            f"No se encontró el script de instalación: {RUTA_SCRIPT_SQL}"
        )

    try:
        base_datos.command(
            RUTA_SCRIPT_SQL.read_text(encoding="utf-8"),
            (),
        )
    except Exception as error:
        raise RuntimeError(
            "No fue posible instalar o actualizar las tablas del módulo. "
            "Verifique que la cuenta de SQL Server tenga permisos de "
            "CREATE TABLE, ALTER y CREATE INDEX. "
            f"Detalle original: {error}"
        ) from error

    faltantes_despues = [
        tabla
        for tabla in TABLAS_PROPIAS_MODULO
        if not _objeto_existe(base_datos, tabla)
    ]
    if faltantes_despues:
        raise RuntimeError(
            "No fue posible crear las tablas del módulo: "
            + ", ".join(faltantes_despues)
        )
    _validar_columnas_modulo(base_datos)

    creadas = tuple(
        tabla
        for tabla in TABLAS_PROPIAS_MODULO
        if tabla not in existentes_antes
    )
    reutilizadas = tuple(
        tabla
        for tabla in TABLAS_PROPIAS_MODULO
        if tabla in existentes_antes
    )
    return ReporteInicializacion(
        servidor=servidor,
        base_datos=nombre_base_datos,
        tablas_creadas=creadas,
        tablas_reutilizadas=reutilizadas,
        dependencias_validadas=len(DEPENDENCIAS_NATIVAS_SSM),
    )
