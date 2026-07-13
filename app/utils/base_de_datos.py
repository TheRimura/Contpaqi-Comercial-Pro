import json
import os
import secrets

from functools import cache
from platform import node
from typing import Optional

from cayal.comandos_base_datos import ComandosBaseDatos


_CLAVE_FIRMA_TEMPORAL = secrets.token_urlsafe(64)


class BaseDatos(ComandosBaseDatos):
    MODULO_ENTRADA = 202
    MODULO_SALIDA = 203

    MOVIMIENTOS_ENTRADA_RELACIONABLES = (
        0, 3, 5, 7, 13, 14, 16, 17, 19, 24, 26, 31,
    )
    MOVIMIENTOS_SALIDA_RELACIONABLES = (
        0, 2, 6, 8, 9, 10, 12, 13, 14, 21, 23, 28,
    )

    def __init__(self):
        super().__init__(servidor=node())
        self.base_de_datos = None

    # ----------------------------- SISTEMA -----------------------------
    def probar_conexion(self) -> bool:
        return int(self.fetchone("SELECT 1", ()) or 0) == 1

    def buscar_configuracion_seguridad(self) -> dict:
        duracion = int(os.getenv("SESSION_MAX_AGE", "28800"))
        nombre_cookie = os.getenv(
            "SESSION_COOKIE_NAME",
            "cayal_session",
        ).strip()
        clave_firma = os.getenv("SESSION_SECRET", "").strip()

        if duracion <= 0:
            raise RuntimeError(
                "SESSION_MAX_AGE debe ser mayor que cero."
            )

        if not nombre_cookie:
            raise RuntimeError(
                "SESSION_COOKIE_NAME no puede estar vacío."
            )

        return {
            "clave_firma": clave_firma or _CLAVE_FIRMA_TEMPORAL,
            "duracion_sesion_segundos": duracion,
            "nombre_cookie": nombre_cookie,
        }

    # ------------------------------ LOGIN ------------------------------
    def buscar_info_usuario_user_name(
        self,
        user_name: str,
    ) -> list[dict]:
        return self.fetchall(
            """
            SELECT
                U.UserID,
                U.UserGroupID,
                U.UserName,
                U.ReportAccess
            FROM dbo.engUser AS U
            WHERE U.DeletedOn IS NULL
              AND UPPER(LTRIM(RTRIM(U.UserName))) =
                  UPPER(LTRIM(RTRIM(?)))
            ORDER BY U.UserID
            """,
            (str(user_name).strip(),),
        )

    def buscar_hash_usuario(self, user_id: int):
        return self.fetchone(
            """
            SELECT UC.UserPassword
            FROM dbo.engUser AS U
            LEFT JOIN dbo.engUserCayal AS UC
                ON UC.UserID = U.UserID
            WHERE U.UserID = ?
              AND U.DeletedOn IS NULL
            """,
            (int(user_id),),
        )

    def buscar_hashes_grupo_maestro(self) -> list[dict]:
        return self.fetchall(
            """
            SELECT UC.UserPassword
            FROM dbo.engUser AS U
            INNER JOIN dbo.engUserGroup AS G
                ON G.UserGroupID = U.UserGroupID
            INNER JOIN dbo.engUserCayal AS UC
                ON UC.UserID = U.UserID
            WHERE U.DeletedOn IS NULL
              AND UC.UserPassword IS NOT NULL
              AND G.UserGroupID = (
                  SELECT TOP 1 G2.UserGroupID
                  FROM dbo.engUserGroup AS G2
                  WHERE EXISTS (
                      SELECT 1
                      FROM dbo.engUser AS U2
                      INNER JOIN dbo.engUserCayal AS UC2
                          ON UC2.UserID = U2.UserID
                      WHERE U2.UserGroupID = G2.UserGroupID
                        AND U2.DeletedOn IS NULL
                        AND UC2.UserPassword IS NOT NULL
                  )
                  ORDER BY G2.VersionSync, G2.UserGroupID
              )
            ORDER BY U.UserID
            """,
            (),
        )

    # ------------------------- DOCUMENTOS ERP -------------------------
    def documento_previamente_relacionado(
        self,
        document_id: int,
    ) -> bool:
        valor = self.fetchone(
            """
            SELECT CASE
                WHEN ISNULL(SourceDocumentID, 0) <> 0
                  OR ISNULL(DestinationDocumentID, 0) <> 0
                  OR ISNULL(Custom1, '') <> ''
                THEN 1
                ELSE 0
            END
            FROM dbo.docDocument
            WHERE DocumentID = ?
            """,
            (int(document_id),),
        )

        return int(valor or 0) == 1

    def buscar_folio_documento(self, document_id: int) -> str:
        valor = self.fetchone(
            """
            SELECT
                ISNULL(FolioPrefix, '') + ISNULL(Folio, '')
            FROM dbo.docDocument
            WHERE DocumentID = ?
              AND DeletedOn IS NULL
            """,
            (int(document_id),),
        )

        return str(valor or "")

    def buscar_tipo_movimiento_documento(
        self,
        document_id: int,
    ) -> int:
        valor = self.fetchone(
            """
            SELECT ISNULL(TRY_CONVERT(INT, CustomCbo), 0)
            FROM dbo.docDocument
            WHERE DocumentID = ?
              AND DeletedOn IS NULL
            """,
            (int(document_id),),
        )

        return int(valor or 0)

    def buscar_tipo_movimiento_modulo(
        self,
        module_id: int,
        incluir_todos: bool = False,
    ) -> list[dict]:
        module_id = int(module_id or 0)

        if module_id == self.MODULO_ENTRADA:
            grupo = "Tipo de entrada"
            movimientos = self.MOVIMIENTOS_ENTRADA_RELACIONABLES
        elif module_id == self.MODULO_SALIDA:
            grupo = "Tipo de salida"
            movimientos = self.MOVIMIENTOS_SALIDA_RELACIONABLES
        else:
            return []

        filtro = ""

        if not incluir_todos:
            movimientos_validos = (
                movimiento
                for movimiento in movimientos
                if movimiento != 0
            )
            ids_sql = ",".join(
                str(movimiento)
                for movimiento in movimientos_validos
            )
            filtro = f"AND ItemData IN ({ids_sql})"

        return self.fetchall(
            f"""
            SELECT ItemData, ItemValue
            FROM
            (
                SELECT ItemData, ItemValue
                FROM dbo.engRefCombo
                WHERE CboGroupName = ?
                  {filtro}

                UNION ALL

                SELECT
                    0 AS ItemData,
                    'NO CLASIFICADO' AS ItemValue
            ) AS Movimientos
            ORDER BY ItemValue
            """,
            (grupo,),
        )

    def buscar_tipos_movimiento_entrada(self) -> list[dict]:
        return self.buscar_tipo_movimiento_modulo(
            self.MODULO_ENTRADA
        )

    def buscar_tipos_movimiento_salida(self) -> list[dict]:
        return self.buscar_tipo_movimiento_modulo(
            self.MODULO_SALIDA
        )

    def buscar_documentos_disponibles(
        self,
        module_id: int,
    ) -> list[dict]:
        module_id = int(module_id or 0)

        if module_id == self.MODULO_ENTRADA:
            movimientos = self.MOVIMIENTOS_ENTRADA_RELACIONABLES
        elif module_id == self.MODULO_SALIDA:
            movimientos = self.MOVIMIENTOS_SALIDA_RELACIONABLES
        else:
            return []

        movimientos_sql = ",".join(
            str(movimiento)
            for movimiento in movimientos
        )

        return self.fetchall(
            f"""
            SELECT
                D.DocumentID,
                D.ModuleID,
                ISNULL(D.FolioPrefix, '') +
                    ISNULL(D.Folio, '') AS DocFolio,
                ISNULL(U.UserName, '') AS UserName,
                CAST(D.CreatedOn AS DATE) AS CreatedOn,
                ISNULL(
                    TRY_CONVERT(INT, D.CustomCbo),
                    0
                ) AS CustomCbo
            FROM dbo.docDocument AS D
            LEFT JOIN dbo.engUser AS U
                ON U.UserID = D.CreatedBy
            WHERE D.ModuleID = ?
              AND D.DeletedOn IS NULL
              AND D.CancelledOn IS NULL
              AND ISNULL(D.SourceDocumentID, 0) = 0
              AND ISNULL(D.DestinationDocumentID, 0) = 0
              AND ISNULL(D.Custom1, '') = ''
              AND ISNULL(
                    TRY_CONVERT(INT, D.CustomCbo),
                    0
                  ) IN ({movimientos_sql})
              AND CAST(D.CreatedOn AS DATE) =
                  CAST(GETDATE() AS DATE)
            ORDER BY D.CreatedOn DESC, D.DocumentID DESC
            """,
            (module_id,),
        )

    def buscar_documentos_relacionables(
        self,
        module_id: int,
    ) -> list[dict]:
        """
        Compatibilidad con el módulo puro.

        Recibe el módulo actual y devuelve documentos del módulo opuesto.
        """
        module_id = int(module_id or 0)

        if module_id == self.MODULO_ENTRADA:
            return self.buscar_documentos_disponibles(
                self.MODULO_SALIDA
            )

        if module_id == self.MODULO_SALIDA:
            return self.buscar_documentos_disponibles(
                self.MODULO_ENTRADA
            )

        return []

    def obtener_proveedores_documentos(self) -> list[dict]:
        return self.fetchall(
            """
            SELECT DISTINCT
                S.BusinessEntityID,
                E.OfficialName
            FROM dbo.docDocument AS D
            INNER JOIN dbo.orgBusinessEntity AS E
                ON E.BusinessEntityID = D.BusinessEntityID
            INNER JOIN dbo.orgSupplier AS S
                ON S.BusinessEntityID = E.BusinessEntityID
            WHERE S.DeletedOn IS NULL
              AND D.ModuleID = 152
              AND D.CancelledOn IS NULL
              AND D.DeletedOn IS NULL
              AND S.SupplierID IS NOT NULL
            ORDER BY E.OfficialName
            """,
            (),
        )

    def obtener_usuarios_fisicos(self) -> list[dict]:
        return self.fetchall(
            """
            SELECT
                UserID,
                OfficialName
            FROM dbo.zvwEmpleadosCayalMenu
            ORDER BY OfficialName
            """,
            (),
        )

    def obtener_relacion_documento(
        self,
        document_id: int,
    ) -> Optional[dict]:
        filas = self.fetchall(
            """
            SELECT TOP 1
                D.DocumentID,
                D.ModuleID,
                ISNULL(D.FolioPrefix, '') +
                    ISNULL(D.Folio, '') AS DocFolio,
                ISNULL(D.Custom1, '') AS FolioRelacionadoCustom1,
                ISNULL(D.SourceDocumentID, 0) AS SourceDocumentID,
                ISNULL(
                    D.DestinationDocumentID,
                    0
                ) AS DestinationDocumentID,
                ISNULL(
                    TRY_CONVERT(INT, D.CustomCbo),
                    0
                ) AS TipoMovimientoID,
                ISNULL(U.UserName, '') AS UserName,
                R.DocumentWarehouseRelationID,
                R.SupplierID,
                R.PhysicalUserID,
                R.MovementDate,
                R.ERPUserID,
                R.SourceBrandID,
                R.DestinationBrandID,
                ISNULL(PROV.OfficialName, '') AS SupplierName,
                ISNULL(EMP.OfficialName, '') AS PhysicalUserName,
                ISNULL(BS.BrandName, '') AS SourceBrandName,
                ISNULL(BD.BrandName, '') AS DestinationBrandName
            FROM dbo.docDocument AS D
            LEFT JOIN dbo.engUser AS U
                ON U.UserID = D.CreatedBy
            OUTER APPLY
            (
                SELECT TOP 1 Relacion.*
                FROM dbo.docDocumentWarehouseRelation AS Relacion
                WHERE Relacion.SourceDocumentID = D.DocumentID
                   OR Relacion.DestinationDocumentID = D.DocumentID
                ORDER BY
                    Relacion.DocumentWarehouseRelationID DESC
            ) AS R
            LEFT JOIN dbo.orgBusinessEntity AS PROV
                ON PROV.BusinessEntityID = R.SupplierID
            LEFT JOIN dbo.zvwEmpleadosCayalMenu AS EMP
                ON EMP.UserID = R.PhysicalUserID
            LEFT JOIN dbo.catBrand AS BS
                ON BS.BrandID = R.SourceBrandID
            LEFT JOIN dbo.catBrand AS BD
                ON BD.BrandID = R.DestinationBrandID
            WHERE D.DocumentID = ?
              AND D.DeletedOn IS NULL
            """,
            (int(document_id),),
        )

        return filas[0] if filas else None

    def relacionar_documentos_erp(
        self,
        source_document_id: int,
        destination_document_id: int,
        folio_source_document_id: str,
        folio_destination_document_id: str,
        tipo_movimiento_origen_id: int,
        tipo_movimiento_destino_id: int,
        proveedor_id: int,
        usuario_fisico_id: int,
        fecha_movimiento,
        user_id_erp: int,
        source_brand_id=None,
        destination_brand_id=None,
    ) -> None:
        self.command(
            """
            SET NOCOUNT ON;
            SET XACT_ABORT ON;
            BEGIN TRANSACTION;

            DECLARE @Origen INT = ?;
            DECLARE @Destino INT = ?;
            DECLARE @FolioOrigen NVARCHAR(125) = ?;
            DECLARE @FolioDestino NVARCHAR(125) = ?;
            DECLARE @TipoOrigen INT = ?;
            DECLARE @TipoDestino INT = ?;
            DECLARE @Proveedor INT = ?;
            DECLARE @UsuarioFisico INT = ?;
            DECLARE @Fecha DATE = ?;
            DECLARE @UsuarioERP INT = ?;
            DECLARE @MarcaOrigen INT = ?;
            DECLARE @MarcaDestino INT = ?;

            IF @Origen = @Destino
                THROW 50001,
                    'Los documentos no pueden ser el mismo.',
                    1;

            IF NOT EXISTS
            (
                SELECT 1
                FROM dbo.docDocument WITH (
                    UPDLOCK,
                    HOLDLOCK
                )
                WHERE DocumentID = @Origen
                  AND ModuleID = 203
                  AND DeletedOn IS NULL
                  AND CancelledOn IS NULL
                  AND ISNULL(SourceDocumentID, 0) = 0
                  AND ISNULL(DestinationDocumentID, 0) = 0
                  AND ISNULL(Custom1, '') = ''
            )
                THROW 50002,
                    'La salida ya fue relacionada o no está disponible.',
                    1;

            IF NOT EXISTS
            (
                SELECT 1
                FROM dbo.docDocument WITH (
                    UPDLOCK,
                    HOLDLOCK
                )
                WHERE DocumentID = @Destino
                  AND ModuleID = 202
                  AND DeletedOn IS NULL
                  AND CancelledOn IS NULL
                  AND ISNULL(SourceDocumentID, 0) = 0
                  AND ISNULL(DestinationDocumentID, 0) = 0
                  AND ISNULL(Custom1, '') = ''
            )
                THROW 50003,
                    'La entrada ya fue relacionada o no está disponible.',
                    1;

            IF EXISTS
            (
                SELECT 1
                FROM dbo.docDocumentWarehouseRelation WITH (
                    UPDLOCK,
                    HOLDLOCK
                )
                WHERE SourceDocumentID = @Origen
                   OR DestinationDocumentID = @Destino
            )
                THROW 50004,
                    'La relación ya existe.',
                    1;

            UPDATE dbo.docDocument
            SET
                DestinationDocumentID = @Destino,
                CustomCbo = @TipoOrigen,
                Custom1 = @FolioDestino
            WHERE DocumentID = @Origen
              AND ModuleID = 203;

            UPDATE dbo.docDocument
            SET
                SourceDocumentID = @Origen,
                CustomCbo = @TipoDestino,
                Custom1 = @FolioOrigen
            WHERE DocumentID = @Destino
              AND ModuleID = 202;

            INSERT INTO dbo.docDocumentWarehouseRelation
            (
                SourceDocumentID,
                DestinationDocumentID,
                SupplierID,
                PhysicalUserID,
                MovementDate,
                ERPUserID,
                SourceBrandID,
                DestinationBrandID,
                CreatedOn
            )
            VALUES
            (
                @Origen,
                @Destino,
                @Proveedor,
                @UsuarioFisico,
                @Fecha,
                @UsuarioERP,
                @MarcaOrigen,
                @MarcaDestino,
                GETDATE()
            );

            COMMIT TRANSACTION;
            """,
            (
                int(source_document_id),
                int(destination_document_id),
                folio_source_document_id,
                folio_destination_document_id,
                int(tipo_movimiento_origen_id),
                int(tipo_movimiento_destino_id),
                int(proveedor_id),
                int(usuario_fisico_id),
                fecha_movimiento,
                int(user_id_erp),
                source_brand_id,
                destination_brand_id,
            ),
        )

    def obtener_partidas_documento_erp(
        self,
        document_id: int,
    ) -> list[dict]:
        """
        Consulta directamente las partidas.

        No llama a buscar_partidas_documento() del paquete para evitar que un
        parámetro de un elemento sea enviado sin la coma de la tupla.
        """
        partidas = self.fetchall(
            """
            SELECT *
            FROM [dbo].[zvwBuscarPartidasDocumentoCayal-DocumentID](?)
            ORDER BY DocumentItemID
            """,
            (int(document_id),),
        )

        resultado = []

        for partida in partidas:
            cantidad = float(partida.get("Quantity") or 0)
            costo = float(
                partida.get("CostPrice")
                or partida.get("UnitPrice")
                or 0
            )
            total = float(
                partida.get("total")
                or partida.get("Total")
                or partida.get("Subtotal")
                or cantidad * costo
            )

            resultado.append(
                {
                    "ProductID": partida.get("ProductID"),
                    "Category": partida.get("Category1") or "",
                    "ProductKey": partida.get("ProductKey") or "",
                    "ProductName": partida.get("ProductName") or "",
                    "Quantity": cantidad,
                    "CostPrice": costo,
                    "total": total,
                }
            )

        return resultado

    def buscar_document_id_por_folio(
        self,
        folio: str,
        module_id: Optional[int] = None,
    ) -> int:
        if not folio:
            return 0

        valor = self.fetchone(
            """
            SELECT TOP 1
                DocumentID
            FROM dbo.docDocument
            WHERE DeletedOn IS NULL
              AND CancelledOn IS NULL
              AND UPPER(
                    LTRIM(
                        RTRIM(
                            ISNULL(FolioPrefix, '') +
                            ISNULL(Folio, '')
                        )
                    )
                  ) = UPPER(LTRIM(RTRIM(?)))
              AND (? IS NULL OR ModuleID = ?)
            ORDER BY DocumentID DESC
            """,
            (str(folio).strip(), module_id, module_id),
        )

        return int(valor or 0)

    # -------------------------- MODULO CARNICO -------------------------
    def asegurar_tablas_modulo_carnico(self) -> None:
        self.command(
            """
            IF OBJECT_ID(
                'dbo.ModuloCarnicoProductoConfigurado',
                'U'
            ) IS NULL
            BEGIN
                CREATE TABLE dbo.ModuloCarnicoProductoConfigurado (
                    id_producto_carnico INT IDENTITY(1,1) NOT NULL
                        CONSTRAINT PK_ModuloCarnicoProductoConfigurado
                        PRIMARY KEY,
                    product_id INT NULL,
                    clave NVARCHAR(50) NULL,
                    proveedor_id INT NULL,
                    proveedor_nombre NVARCHAR(150) NULL,
                    nombre_producto NVARCHAR(250) NOT NULL,
                    categoria NVARCHAR(100) NULL,
                    categoria_resultante NVARCHAR(150) NULL,
                    unidad NVARCHAR(50) NOT NULL
                        CONSTRAINT DF_MCPC_unidad DEFAULT 'KILO',
                    porcentaje_merma DECIMAL(9,4) NOT NULL
                        CONSTRAINT DF_MCPC_merma DEFAULT 0,
                    activo BIT NOT NULL
                        CONSTRAINT DF_MCPC_activo DEFAULT 1,
                    usuario_creacion BIGINT NULL,
                    usuario_actualizacion BIGINT NULL,
                    fecha_creacion DATETIME2 NOT NULL
                        CONSTRAINT DF_MCPC_fecha_creacion
                        DEFAULT SYSUTCDATETIME(),
                    fecha_actualizacion DATETIME2 NULL
                );
            END;

            IF OBJECT_ID(
                'dbo.ModuloCarnicoProductoBitacora',
                'U'
            ) IS NULL
            BEGIN
                CREATE TABLE dbo.ModuloCarnicoProductoBitacora (
                    id_bitacora INT IDENTITY(1,1) NOT NULL
                        CONSTRAINT PK_ModuloCarnicoProductoBitacora
                        PRIMARY KEY,
                    accion NVARCHAR(50) NOT NULL,
                    usuario_id BIGINT NULL,
                    usuario_confirmacion_nombre NVARCHAR(150) NOT NULL,
                    detalle NVARCHAR(500) NULL,
                    productos_json NVARCHAR(MAX) NULL,
                    fecha DATETIME2 NOT NULL
                        CONSTRAINT DF_MCPB_fecha DEFAULT SYSUTCDATETIME()
                );
            END;

            IF OBJECT_ID(
                'dbo.ModuloCarnicoTransformacionRegistro',
                'U'
            ) IS NULL
            BEGIN
                CREATE TABLE dbo.ModuloCarnicoTransformacionRegistro (
                    id_registro INT IDENTITY(1,1) NOT NULL
                        CONSTRAINT PK_ModuloCarnicoTransformacionRegistro
                        PRIMARY KEY,
                    producto_salida_config_id INT NOT NULL,
                    producto_entrada_config_id INT NOT NULL,
                    producto_salida_nombre NVARCHAR(250) NOT NULL,
                    producto_entrada_nombre NVARCHAR(250) NOT NULL,
                    cantidad_salida DECIMAL(18,4) NOT NULL,
                    cantidad_entrada DECIMAL(18,4) NOT NULL,
                    cantidad_merma DECIMAL(18,4) NOT NULL,
                    porcentaje_merma DECIMAL(9,4) NOT NULL,
                    usuario_id BIGINT NULL,
                    usuario_confirmacion_nombre NVARCHAR(150) NOT NULL,
                    observaciones NVARCHAR(300) NULL,
                    fecha DATETIME2 NOT NULL
                        CONSTRAINT DF_MCTR_fecha DEFAULT SYSUTCDATETIME()
                );
            END;
            """,
            (),
        )

    def buscar_productos_carnicos_configurados(
        self,
        incluir_inactivos: bool = True,
    ) -> list[dict]:
        self.asegurar_tablas_modulo_carnico()
        filtro = "" if incluir_inactivos else "WHERE activo = 1"

        return self.fetchall(
            f"""
            SELECT
                id_producto_carnico,
                product_id,
                clave,
                proveedor_id,
                proveedor_nombre,
                nombre_producto,
                categoria,
                categoria_resultante,
                unidad,
                porcentaje_merma,
                activo,
                usuario_creacion,
                usuario_actualizacion,
                fecha_creacion,
                fecha_actualizacion
            FROM dbo.ModuloCarnicoProductoConfigurado
            {filtro}
            ORDER BY
                activo DESC,
                categoria,
                nombre_producto
            """,
            (),
        )

    def registrar_bitacora_productos_carnicos(
        self,
        accion: str,
        usuario_id,
        usuario_confirmacion_nombre: str,
        detalle: str,
        productos,
    ) -> None:
        self.command(
            """
            INSERT INTO dbo.ModuloCarnicoProductoBitacora (
                accion,
                usuario_id,
                usuario_confirmacion_nombre,
                detalle,
                productos_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                accion,
                usuario_id,
                usuario_confirmacion_nombre,
                detalle,
                json.dumps(productos, ensure_ascii=False),
            ),
        )

    def guardar_productos_carnicos_configurados(
        self,
        productos: list[dict],
        usuario_id,
        usuario_confirmacion_nombre: str,
    ) -> None:
        self.asegurar_tablas_modulo_carnico()

        for producto in productos:
            id_configuracion = producto.get("id_configuracion")
            parametros = (
                producto.get("product_id"),
                producto.get("clave") or None,
                producto.get("proveedor_id"),
                producto.get("proveedor_nombre") or None,
                producto["nombre_producto"].strip(),
                producto.get("categoria") or None,
                producto.get("categoria_resultante") or None,
                producto.get("unidad") or "KILO",
                float(producto.get("porcentaje_merma") or 0),
                1 if producto.get("activo", True) else 0,
                usuario_id,
            )

            if id_configuracion:
                self.command(
                    """
                    UPDATE dbo.ModuloCarnicoProductoConfigurado
                    SET
                        product_id = ?,
                        clave = ?,
                        proveedor_id = ?,
                        proveedor_nombre = ?,
                        nombre_producto = ?,
                        categoria = ?,
                        categoria_resultante = ?,
                        unidad = ?,
                        porcentaje_merma = ?,
                        activo = ?,
                        usuario_actualizacion = ?,
                        fecha_actualizacion = SYSUTCDATETIME()
                    WHERE id_producto_carnico = ?
                    """,
                    (*parametros, int(id_configuracion)),
                )
            else:
                self.command(
                    """
                    INSERT INTO dbo.ModuloCarnicoProductoConfigurado (
                        product_id,
                        clave,
                        proveedor_id,
                        proveedor_nombre,
                        nombre_producto,
                        categoria,
                        categoria_resultante,
                        unidad,
                        porcentaje_merma,
                        activo,
                        usuario_creacion
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    parametros,
                )

        self.registrar_bitacora_productos_carnicos(
            accion="guardar",
            usuario_id=usuario_id,
            usuario_confirmacion_nombre=usuario_confirmacion_nombre,
            detalle="Configuracion de productos carnicos guardada",
            productos=productos,
        )

    def buscar_bitacora_productos_carnicos(
        self,
        limite: int = 50,
    ) -> list[dict]:
        self.asegurar_tablas_modulo_carnico()
        return self.fetchall(
            """
            SELECT TOP (?)
                id_bitacora,
                accion,
                usuario_id,
                usuario_confirmacion_nombre,
                detalle,
                productos_json,
                fecha
            FROM dbo.ModuloCarnicoProductoBitacora
            ORDER BY id_bitacora DESC
            """,
            (int(limite),),
        )

    def buscar_producto_carnico_configurado(
        self,
        id_configuracion: int,
    ) -> Optional[dict]:
        filas = self.fetchall(
            """
            SELECT TOP 1
                *
            FROM dbo.ModuloCarnicoProductoConfigurado
            WHERE id_producto_carnico = ?
              AND activo = 1
            """,
            (int(id_configuracion),),
        )
        return filas[0] if filas else None

    def registrar_transformacion_carnica(
        self,
        datos,
        usuario_id,
    ) -> int:
        self.asegurar_tablas_modulo_carnico()
        salida = self.buscar_producto_carnico_configurado(
            datos.producto_salida_config_id
        )
        entrada = self.buscar_producto_carnico_configurado(
            datos.producto_entrada_config_id
        )

        if not salida:
            raise ValueError("Selecciona un producto de salida activo.")
        if not entrada:
            raise ValueError("Selecciona un producto de entrada activo.")

        cantidad_salida = float(datos.cantidad_salida)
        cantidad_entrada = float(datos.cantidad_entrada)
        cantidad_merma = max(cantidad_salida - cantidad_entrada, 0)
        porcentaje_merma = (
            cantidad_merma / cantidad_salida * 100
            if cantidad_salida
            else 0
        )

        registro_id = self.fetchone(
            """
            INSERT INTO dbo.ModuloCarnicoTransformacionRegistro (
                producto_salida_config_id,
                producto_entrada_config_id,
                producto_salida_nombre,
                producto_entrada_nombre,
                cantidad_salida,
                cantidad_entrada,
                cantidad_merma,
                porcentaje_merma,
                usuario_id,
                usuario_confirmacion_nombre,
                observaciones
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);

            SELECT CONVERT(INT, SCOPE_IDENTITY());
            """,
            (
                int(datos.producto_salida_config_id),
                int(datos.producto_entrada_config_id),
                salida["nombre_producto"],
                entrada["nombre_producto"],
                cantidad_salida,
                cantidad_entrada,
                cantidad_merma,
                porcentaje_merma,
                usuario_id,
                datos.usuario_confirmacion_nombre,
                datos.observaciones,
            ),
        )
        return int(registro_id or 0)

    def buscar_transformaciones_carnicas(
        self,
        limite: int = 50,
    ) -> list[dict]:
        self.asegurar_tablas_modulo_carnico()
        return self.fetchall(
            """
            SELECT TOP (?)
                id_registro,
                producto_salida_config_id,
                producto_entrada_config_id,
                producto_salida_nombre,
                producto_entrada_nombre,
                cantidad_salida,
                cantidad_entrada,
                cantidad_merma,
                porcentaje_merma,
                usuario_id,
                usuario_confirmacion_nombre,
                observaciones,
                fecha
            FROM dbo.ModuloCarnicoTransformacionRegistro
            ORDER BY id_registro DESC
            """,
            (int(limite),),
        )

    def obtener_marcas_por_categoria(
        self,
        categoria: str,
    ) -> list[dict]:
        categoria = str(categoria or "").strip()

        if not categoria:
            return []

        return self.fetchall(
            """
            SELECT DISTINCT
                B.BrandID,
                B.BrandName
            FROM dbo.catProductBrandCategory AS C
            INNER JOIN dbo.catProductBrandCategoryRelation AS R
                ON R.ProductBrandCategoryID =
                   C.ProductBrandCategoryID
            INNER JOIN dbo.catBrand AS B
                ON B.BrandID = R.BrandID
            WHERE UPPER(
                    LTRIM(
                        RTRIM(C.ProductBrandCategoryName)
                    )
                  ) = UPPER(LTRIM(RTRIM(?)))
              AND C.DeletedOn IS NULL
              AND R.DeletedOn IS NULL
              AND B.DeletedOn IS NULL
            ORDER BY B.BrandName
            """,
            (categoria,),
        )

    def homologar_tipo_movimiento_documento(
        self,
        document_id: int,
    ) -> None:
        self.command(
            r"""
            DECLARE @DocumentID INT = ?;
            DECLARE @ModuleID INT;
            DECLARE @Custom1 NVARCHAR(125);
            DECLARE @Custom1Normalizado NVARCHAR(125);

            SELECT
                @ModuleID = ModuleID,
                @Custom1 = LTRIM(
                    RTRIM(
                        ISNULL(Custom1, '')
                    )
                )
            FROM dbo.docDocument
            WHERE DocumentID = @DocumentID;

            SET @Custom1Normalizado = UPPER(@Custom1);
            SET @Custom1Normalizado =
                REPLACE(@Custom1Normalizado, ' ', '');
            SET @Custom1Normalizado =
                REPLACE(@Custom1Normalizado, '-', '');
            SET @Custom1Normalizado =
                REPLACE(@Custom1Normalizado, '_', '');
            SET @Custom1Normalizado =
                REPLACE(@Custom1Normalizado, '.', '');
            SET @Custom1Normalizado =
                REPLACE(@Custom1Normalizado, '/', '');
            SET @Custom1Normalizado =
                REPLACE(@Custom1Normalizado, '\', '');
            SET @Custom1Normalizado =
                REPLACE(@Custom1Normalizado, CHAR(9), '');
            SET @Custom1Normalizado =
                REPLACE(@Custom1Normalizado, CHAR(10), '');
            SET @Custom1Normalizado =
                REPLACE(@Custom1Normalizado, CHAR(13), '');

            IF ISNULL(@Custom1Normalizado, '') = ''
                RETURN;

            DECLARE @EntradaDocumentID INT = 0;
            DECLARE @SalidaDocumentID INT = 0;

            IF @ModuleID = 202
            BEGIN
                SET @EntradaDocumentID = @DocumentID;

                SELECT TOP 1
                    @SalidaDocumentID = S.DocumentID
                FROM dbo.docDocument AS S
                WHERE S.ModuleID = 203
                  AND S.DeletedOn IS NULL
                  AND S.CancelledOn IS NULL
                  AND UPPER(
                        REPLACE(
                        REPLACE(
                        REPLACE(
                        REPLACE(
                        REPLACE(
                        REPLACE(
                        REPLACE(
                        REPLACE(
                        REPLACE(
                            ISNULL(S.FolioPrefix, '') +
                            ISNULL(S.Folio, ''),
                            ' ', ''),
                            '-', ''),
                            '_', ''),
                            '.', ''),
                            '/', ''),
                            '\', ''),
                            CHAR(9), ''),
                            CHAR(10), ''),
                            CHAR(13), '')
                      ) = @Custom1Normalizado
                ORDER BY S.DocumentID DESC;
            END
            ELSE IF @ModuleID = 203
            BEGIN
                SET @SalidaDocumentID = @DocumentID;

                SELECT TOP 1
                    @EntradaDocumentID = E.DocumentID
                FROM dbo.docDocument AS E
                WHERE E.ModuleID = 202
                  AND E.DeletedOn IS NULL
                  AND E.CancelledOn IS NULL
                  AND UPPER(
                        REPLACE(
                        REPLACE(
                        REPLACE(
                        REPLACE(
                        REPLACE(
                        REPLACE(
                        REPLACE(
                        REPLACE(
                        REPLACE(
                            ISNULL(E.FolioPrefix, '') +
                            ISNULL(E.Folio, ''),
                            ' ', ''),
                            '-', ''),
                            '_', ''),
                            '.', ''),
                            '/', ''),
                            '\', ''),
                            CHAR(9), ''),
                            CHAR(10), ''),
                            CHAR(13), '')
                      ) = @Custom1Normalizado
                ORDER BY E.DocumentID DESC;
            END
            ELSE
            BEGIN
                RETURN;
            END;

            IF ISNULL(@EntradaDocumentID, 0) = 0
               OR ISNULL(@SalidaDocumentID, 0) = 0
                RETURN;

            DECLARE @EntradaFolio NVARCHAR(125);
            DECLARE @SalidaFolio NVARCHAR(125);

            SELECT
                @EntradaFolio =
                    ISNULL(FolioPrefix, '') +
                    ISNULL(Folio, '')
            FROM dbo.docDocument
            WHERE DocumentID = @EntradaDocumentID
              AND ModuleID = 202;

            SELECT
                @SalidaFolio =
                    ISNULL(FolioPrefix, '') +
                    ISNULL(Folio, '')
            FROM dbo.docDocument
            WHERE DocumentID = @SalidaDocumentID
              AND ModuleID = 203;

            UPDATE dbo.docDocument
            SET
                SourceDocumentID = @SalidaDocumentID,
                DestinationDocumentID = 0,
                Custom1 = @SalidaFolio
            WHERE DocumentID = @EntradaDocumentID
              AND ModuleID = 202;

            UPDATE dbo.docDocument
            SET
                SourceDocumentID = 0,
                DestinationDocumentID = @EntradaDocumentID,
                Custom1 = @EntradaFolio
            WHERE DocumentID = @SalidaDocumentID
              AND ModuleID = 203;
            """,
            (int(document_id),),
        )


@cache
def obtener_base_datos() -> BaseDatos:
    return BaseDatos()
