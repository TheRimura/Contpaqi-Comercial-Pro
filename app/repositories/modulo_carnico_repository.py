import unicodedata
from decimal import Decimal

from app.utils.base_de_datos import BaseDatos


class ModuloCarnicoRepository:
    FAMILIAS_CARNICAS = ("CERDO", "POLLO", "RES LOCAL")
    GRUPOS_CONFIGURACION = ("ADMIN", "DIRECCION", "JEFE DE PRODUCCION")

    def __init__(self, base_datos: BaseDatos):
        self.base_datos = base_datos

    @staticmethod
    def _numero(valor) -> float:
        if isinstance(valor, Decimal):
            return float(valor)
        return float(valor or 0)

    @staticmethod
    def _normalizar(valor) -> str:
        texto = str(valor or "").strip().upper()
        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(
            caracter
            for caracter in texto
            if not unicodedata.combining(caracter)
        )
        return " ".join(texto.split())

    def asegurar_tablas(self) -> None:
        self.base_datos.asegurar_tablas_modulo_carnico()
        self.base_datos.command(
            """
            IF OBJECT_ID('dbo.ModuloCarnicoUsuarioPermitido', 'U') IS NULL
            BEGIN
                CREATE TABLE dbo.ModuloCarnicoUsuarioPermitido (
                    id_permiso INT IDENTITY(1,1) NOT NULL
                        CONSTRAINT PK_ModuloCarnicoUsuarioPermitido
                        PRIMARY KEY,
                    usuario_id BIGINT NOT NULL,
                    activo BIT NOT NULL
                        CONSTRAINT DF_MCU_activo DEFAULT 1,
                    usuario_creacion BIGINT NULL,
                    fecha_creacion DATETIME2 NOT NULL
                        CONSTRAINT DF_MCU_fecha DEFAULT SYSUTCDATETIME()
                );
            END;

            IF OBJECT_ID('dbo.ModuloCarnicoTransformacionRegistro', 'U') IS NOT NULL
               AND COL_LENGTH('dbo.ModuloCarnicoTransformacionRegistro', 'id_transformacion') IS NULL
            BEGIN
                ALTER TABLE dbo.ModuloCarnicoTransformacionRegistro
                ADD id_transformacion INT NULL;
            END;

            IF OBJECT_ID('dbo.ModuloCarnicoTransformacionRegistro', 'U') IS NOT NULL
               AND COL_LENGTH('dbo.ModuloCarnicoTransformacionRegistro', 'categoria_base') IS NULL
            BEGIN
                ALTER TABLE dbo.ModuloCarnicoTransformacionRegistro
                ADD categoria_base NVARCHAR(100) NULL;
            END;

            IF OBJECT_ID('dbo.ModuloCarnicoSalidaRegistro', 'U') IS NULL
            BEGIN
                CREATE TABLE dbo.ModuloCarnicoSalidaRegistro (
                    id_salida INT IDENTITY(1,1) NOT NULL
                        CONSTRAINT PK_ModuloCarnicoSalidaRegistro
                        PRIMARY KEY,
                    producto_id INT NOT NULL,
                    producto_clave NVARCHAR(50) NULL,
                    producto_nombre NVARCHAR(250) NOT NULL,
                    categoria NVARCHAR(100) NULL,
                    cantidad FLOAT NOT NULL,
                    proveedor_nombre NVARCHAR(150) NOT NULL,
                    usuario_id BIGINT NULL,
                    usuario_responsable NVARCHAR(150) NOT NULL,
                    observaciones NVARCHAR(300) NULL,
                    fecha DATETIME2 NOT NULL
                        CONSTRAINT DF_MCSR_fecha DEFAULT SYSDATETIME()
                );
            END;
            """,
            (),
        )

    def usuario_puede_configurar(self, sesion: dict) -> bool:
        self.asegurar_tablas()
        user_id = int(sesion.get("user_id") or 0)
        user_group_id = int(sesion.get("user_group_id") or 0)

        if user_id <= 0:
            return False

        permitido = self.base_datos.fetchone(
            """
            SELECT TOP 1 1
            FROM dbo.ModuloCarnicoUsuarioPermitido
            WHERE usuario_id = ?
              AND activo = 1
            """,
            (user_id,),
        )
        if int(permitido or 0) == 1:
            return True

        grupo = self.base_datos.fetchone(
            """
            SELECT TOP 1 GroupName
            FROM dbo.engUserGroup
            WHERE UserGroupID = ?
            """,
            (user_group_id,),
        )
        grupo_normalizado = self._normalizar(grupo)
        return grupo_normalizado in self.GRUPOS_CONFIGURACION

    def serializar_producto_erp(self, fila: dict) -> dict:
        return {
            "product_id": int(fila["ProductID"]),
            "clave": fila.get("ProductKey") or "",
            "categoria": fila.get("Category1") or "",
            "opcion_creacion": fila.get("Category2") or "",
            "nombre_producto": fila.get("ProductName") or "",
            "unidad": fila.get("Unit") or "KILO",
            "proveedor_id": fila.get("proveedor_id"),
            "proveedor_nombre": fila.get("proveedor_nombre") or "",
            "texto": (
                f"{fila.get('ProductKey') or ''} - "
                f"{fila.get('ProductName') or ''}"
            ).strip(" -"),
        }

    def buscar_productos_erp(
        self,
        termino: str = "",
        limite: int = 15,
    ) -> list[dict]:
        termino = str(termino or "").strip()
        limite = max(1, min(int(limite or 15), 50))
        patron = f"%{termino}%"
        familias = ", ".join("?" for _ in self.FAMILIAS_CARNICAS)

        filas = self.base_datos.fetchall(
            f"""
            SELECT TOP (?)
                P.ProductID,
                P.ProductKey,
                P.Category1,
                P.Category2,
                P.ProductName,
                P.Unit,
                PR.proveedor_id,
                PR.proveedor_nombre
            FROM dbo.orgProduct AS P
            OUTER APPLY (
                SELECT TOP 1
                    D.BusinessEntityID AS proveedor_id,
                    BE.OfficialName AS proveedor_nombre
                FROM dbo.docDocumentItem AS DI
                INNER JOIN dbo.docDocument AS D
                    ON D.DocumentID = DI.DocumentID
                INNER JOIN dbo.orgBusinessEntity AS BE
                    ON BE.BusinessEntityID = D.BusinessEntityID
                INNER JOIN dbo.orgSupplier AS S
                    ON S.BusinessEntityID = BE.BusinessEntityID
                WHERE DI.ProductID = P.ProductID
                  AND DI.DeletedOn IS NULL
                  AND D.DeletedOn IS NULL
                  AND D.CancelledOn IS NULL
                  AND S.DeletedOn IS NULL
                  AND S.SupplierID IS NOT NULL
                ORDER BY
                    D.DateDocument DESC,
                    D.DocumentID DESC
            ) AS PR
            WHERE P.DiscontinuedOn IS NULL
              AND UPPER(ISNULL(P.Category1, '')) IN ({familias})
              AND (
                    ? = ''
                 OR P.ProductKey LIKE ?
                 OR P.ProductName LIKE ?
                 OR P.Category2 LIKE ?
              )
            ORDER BY
                CASE
                    WHEN P.ProductKey = ? THEN 0
                    WHEN P.ProductName LIKE ? THEN 1
                    ELSE 2
                END,
                P.Category1,
                P.Category2,
                P.ProductName
            """,
            (
                limite,
                *self.FAMILIAS_CARNICAS,
                termino,
                patron,
                patron,
                patron,
                termino,
                patron,
            ),
        )
        return [self.serializar_producto_erp(fila) for fila in filas]

    def obtener_producto_erp(self, product_id: int) -> dict | None:
        filas = self.base_datos.fetchall(
            """
            SELECT TOP 1
                ProductID,
                ProductKey,
                Category1,
                Category2,
                ProductName,
                Unit
            FROM dbo.orgProduct
            WHERE ProductID = ?
              AND DiscontinuedOn IS NULL
            """,
            (int(product_id),),
        )
        return filas[0] if filas else None

    def obtener_producto_base_de_receta(self, producto_entrada_id: int) -> int | None:
        fila = self.base_datos.fetchall(
            """
            SELECT TOP 1
                C.producto_componente
            FROM dbo.DetalleTransformaciones AS D
            INNER JOIN dbo.ComponentesTransformacion AS C
                ON C.id_transformacion = D.id_transformacion
            INNER JOIN dbo.Transformaciones AS T
                ON T.id_transformacion = D.id_transformacion
            WHERE D.producto_resultado = ?
              AND C.es_producto_base = 1
            ORDER BY
                T.fecha_creacion DESC,
                T.id_transformacion DESC
            """,
            (int(producto_entrada_id),),
        )
        if not fila:
            return None
        return int(fila[0].get("producto_componente") or 0) or None

    def buscar_producto_base_por_categoria(
        self,
        categoria: str,
        producto_entrada_id: int,
    ) -> int | None:
        categoria = self._normalizar(categoria)
        if not categoria:
            return None

        fila = self.base_datos.fetchall(
            """
            SELECT TOP 1
                ProductID
            FROM dbo.orgProduct
            WHERE DiscontinuedOn IS NULL
              AND UPPER(LTRIM(RTRIM(ISNULL(Category1, '')))) = ?
              AND ProductID <> ?
            ORDER BY ProductName
            """,
            (categoria, int(producto_entrada_id)),
        )
        if not fila:
            return None
        return int(fila[0].get("ProductID") or 0) or None

    def obtener_receta_producto(
        self,
        producto_entrada_id: int,
        cantidad_entrada: float = 1,
    ) -> list[dict]:
        cantidad_entrada = max(self._numero(cantidad_entrada), 0)
        filas = self.base_datos.fetchall(
            """
            WITH Ultima AS (
                SELECT TOP 1
                    D.id_transformacion,
                    D.cantidad_resultado
                FROM dbo.DetalleTransformaciones AS D
                INNER JOIN dbo.Transformaciones AS T
                    ON T.id_transformacion = D.id_transformacion
                WHERE D.producto_resultado = ?
                ORDER BY
                    T.fecha_creacion DESC,
                    T.id_transformacion DESC
            )
            SELECT
                C.producto_componente,
                C.cantidad,
                C.unidad,
                C.es_producto_base,
                U.cantidad_resultado,
                P.ProductKey,
                P.ProductName,
                P.Unit
            FROM Ultima AS U
            INNER JOIN dbo.ComponentesTransformacion AS C
                ON C.id_transformacion = U.id_transformacion
            LEFT JOIN dbo.orgProduct AS P
                ON P.ProductID = C.producto_componente
            ORDER BY
                C.es_producto_base DESC,
                P.ProductName
            """,
            (int(producto_entrada_id),),
        )
        if not filas:
            return []

        base_resultado = self._numero(filas[0].get("cantidad_resultado")) or 1
        factor = cantidad_entrada / base_resultado if cantidad_entrada else 1
        receta = []

        for fila in filas:
            cantidad = self._numero(fila.get("cantidad")) * factor
            receta.append({
                "product_id": int(fila.get("producto_componente") or 0),
                "clave": fila.get("ProductKey") or "",
                "nombre_producto": fila.get("ProductName") or "",
                "tipo": (
                    "Producto base"
                    if bool(fila.get("es_producto_base"))
                    else "Insumo"
                ),
                "unidad": fila.get("unidad") or fila.get("Unit") or "KILO",
                "cantidad": cantidad,
                "cantidad_base": self._numero(fila.get("cantidad")),
                "factor": factor,
            })

        return receta

    def registrar_transformacion(self, datos, sesion: dict) -> int:
        self.asegurar_tablas()
        entrada = self.obtener_producto_erp(datos.producto_entrada_id)

        if not entrada:
            raise ValueError("Selecciona una entrada valida del catalogo.")

        cantidad_entrada = self._numero(datos.cantidad_entrada)
        cantidad_merma = self._numero(datos.cantidad_merma)
        cantidad_salida = (
            self._numero(datos.cantidad_salida)
            if datos.cantidad_salida is not None
            else cantidad_entrada + cantidad_merma
        )
        categoria_base = (
            datos.categoria_base
            or entrada.get("Category1")
            or ""
        ).strip().upper()
        producto_salida_id = (
            int(datos.producto_salida_id)
            if datos.producto_salida_id
            else self.obtener_producto_base_de_receta(datos.producto_entrada_id)
            or self.buscar_producto_base_por_categoria(
                categoria_base,
                datos.producto_entrada_id,
            )
            or int(datos.producto_entrada_id)
        )
        salida = self.obtener_producto_erp(producto_salida_id)

        if not salida:
            raise ValueError("No se pudo resolver el producto base de la entrada.")

        porcentaje_merma = (
            cantidad_merma / cantidad_salida * 100
            if cantidad_salida
            else 0
        )
        usuario = datos.usuario_confirmacion_nombre.strip()
        usuario_id = int(sesion.get("user_id") or 0) or None

        registro_id = self.base_datos.fetchone(
            """
            INSERT INTO dbo.Transformaciones (
                producto_origen,
                cantidad_origen,
                usuario_responsable,
                fecha_creacion,
                producto_seleccionado,
                usuario_id,
                tipo_transformacion,
                porcentaje_merma_esperado,
                id_operacion,
                estado_erp,
                error_erp
            )
            VALUES (?, ?, ?, GETDATE(), ?, ?, ?, ?, NEWID(), ?, ?);

            SELECT CONVERT(INT, SCOPE_IDENTITY());
            """,
            (
                producto_salida_id,
                cantidad_salida,
                usuario,
                producto_salida_id,
                usuario_id,
                "producto_final",
                porcentaje_merma,
                "registrado",
                None,
            ),
        )
        id_transformacion = int(registro_id or 0)

        if id_transformacion <= 0:
            raise ValueError("No se pudo registrar la transformacion.")

        self.base_datos.command(
            """
            INSERT INTO dbo.DetalleTransformaciones (
                id_transformacion,
                producto_resultado,
                cantidad_resultado,
                unidad_resultado
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                id_transformacion,
                int(datos.producto_entrada_id),
                cantidad_entrada,
                entrada.get("Unit") or "KILO",
            ),
        )

        self.base_datos.command(
            """
            INSERT INTO dbo.ComponentesTransformacion (
                id_transformacion,
                producto_componente,
                cantidad,
                unidad,
                es_producto_base
            )
            VALUES (?, ?, ?, ?, 1)
            """,
            (
                id_transformacion,
                producto_salida_id,
                cantidad_salida,
                salida.get("Unit") or "KILO",
            ),
        )

        self.base_datos.command(
            """
            INSERT INTO dbo.ModuloCarnicoTransformacionRegistro (
                id_transformacion,
                producto_salida_config_id,
                producto_entrada_config_id,
                producto_salida_nombre,
                producto_entrada_nombre,
                categoria_base,
                cantidad_salida,
                cantidad_entrada,
                cantidad_merma,
                porcentaje_merma,
                usuario_id,
                usuario_confirmacion_nombre,
                observaciones
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id_transformacion,
                producto_salida_id,
                int(datos.producto_entrada_id),
                salida.get("ProductName") or "",
                entrada.get("ProductName") or "",
                categoria_base,
                cantidad_salida,
                cantidad_entrada,
                cantidad_merma,
                porcentaje_merma,
                usuario_id,
                usuario,
                datos.observaciones,
            ),
        )

        return id_transformacion

    def registrar_salida(self, datos, sesion: dict) -> int:
        self.asegurar_tablas()
        producto = self.obtener_producto_erp(datos.producto_salida_id)

        if not producto:
            raise ValueError("Selecciona un producto base valido del catalogo.")

        usuario_id = int(sesion.get("user_id") or 0) or None
        registro_id = self.base_datos.fetchone(
            """
            INSERT INTO dbo.ModuloCarnicoSalidaRegistro (
                producto_id,
                producto_clave,
                producto_nombre,
                categoria,
                cantidad,
                proveedor_nombre,
                usuario_id,
                usuario_responsable,
                observaciones
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);

            SELECT CONVERT(INT, SCOPE_IDENTITY());
            """,
            (
                int(datos.producto_salida_id),
                producto.get("ProductKey") or "",
                producto.get("ProductName") or "",
                producto.get("Category1") or "",
                self._numero(datos.cantidad_salida),
                datos.proveedor_nombre.strip(),
                usuario_id,
                datos.usuario_confirmacion_nombre.strip(),
                datos.observaciones,
            ),
        )
        return int(registro_id or 0)

    def listar_transformaciones(self, limite: int = 50) -> list[dict]:
        self.asegurar_tablas()
        filas = self.base_datos.fetchall(
            """
            SELECT TOP (?)
                T.id_transformacion,
                T.fecha_creacion,
                T.usuario_responsable,
                T.cantidad_origen,
                T.porcentaje_merma_esperado,
                T.estado_erp,
                T.error_erp,
                OS.ProductKey AS salida_clave,
                OS.ProductName AS salida_nombre,
                OS.Unit AS salida_unidad,
                DE.producto_resultado,
                DE.cantidad_resultado,
                DE.unidad_resultado,
                OE.ProductKey AS entrada_clave,
                OE.ProductName AS entrada_nombre,
                MC.cantidad_merma AS captura_merma,
                MC.observaciones AS captura_observaciones,
                MC.categoria_base AS captura_categoria_base
            FROM dbo.Transformaciones AS T
            OUTER APPLY (
                SELECT TOP 1
                    D.producto_resultado,
                    D.cantidad_resultado,
                    D.unidad_resultado
                FROM dbo.DetalleTransformaciones AS D
                WHERE D.id_transformacion = T.id_transformacion
                ORDER BY D.id_detalle
            ) AS DE
            OUTER APPLY (
                SELECT TOP 1
                    R.cantidad_merma,
                    R.observaciones,
                    R.categoria_base
                FROM dbo.ModuloCarnicoTransformacionRegistro AS R
                WHERE R.id_transformacion = T.id_transformacion
                ORDER BY R.id_registro DESC
            ) AS MC
            LEFT JOIN dbo.orgProduct AS OS
                ON OS.ProductID = T.producto_origen
            LEFT JOIN dbo.orgProduct AS OE
                ON OE.ProductID = DE.producto_resultado
            ORDER BY T.id_transformacion DESC
            """,
            (max(1, min(int(limite or 50), 200)),),
        )
        return [self.serializar_transformacion(fila) for fila in filas]

    def serializar_transformacion(self, fila: dict) -> dict:
        salida = self._numero(fila.get("cantidad_origen"))
        entrada = self._numero(fila.get("cantidad_resultado"))
        porcentaje = self._numero(fila.get("porcentaje_merma_esperado"))
        merma = (
            self._numero(fila.get("captura_merma"))
            if fila.get("captura_merma") is not None
            else salida * porcentaje / 100 if porcentaje else max(salida - entrada, 0)
        )
        rendimiento = entrada / salida * 100 if salida else 0
        fecha = fila.get("fecha_creacion")

        return {
            "id_registro": int(fila["id_transformacion"]),
            "producto_salida_nombre": fila.get("salida_nombre") or "",
            "producto_salida_clave": fila.get("salida_clave") or "",
            "producto_entrada_nombre": fila.get("entrada_nombre") or "",
            "producto_entrada_clave": fila.get("entrada_clave") or "",
            "cantidad_salida": salida,
            "cantidad_entrada": entrada,
            "cantidad_merma": merma,
            "porcentaje_merma": porcentaje,
            "rendimiento": rendimiento,
            "usuario_confirmacion_nombre": fila.get("usuario_responsable") or "",
            "estado": "Registrado",
            "observaciones": fila.get("captura_observaciones") or "",
            "fecha": fecha.isoformat() if hasattr(fecha, "isoformat") else str(fecha or ""),
            "tipo_movimiento": "Entrada",
            "proveedor_nombre": "",
            "categoria_base": (
                fila.get("captura_categoria_base")
                or fila.get("salida_nombre")
                or ""
            ),
        }

    def listar_salidas(self, limite: int = 50) -> list[dict]:
        self.asegurar_tablas()
        filas = self.base_datos.fetchall(
            """
            SELECT TOP (?)
                id_salida,
                producto_id,
                producto_clave,
                producto_nombre,
                categoria,
                cantidad,
                proveedor_nombre,
                usuario_responsable,
                observaciones,
                fecha
            FROM dbo.ModuloCarnicoSalidaRegistro
            ORDER BY id_salida DESC
            """,
            (max(1, min(int(limite or 50), 200)),),
        )
        return [self.serializar_salida(fila) for fila in filas]

    def serializar_salida(self, fila: dict) -> dict:
        fecha = fila.get("fecha")
        return {
            "id_registro": int(fila["id_salida"]),
            "tipo_movimiento": "Salida",
            "producto_salida_nombre": fila.get("producto_nombre") or "",
            "producto_salida_clave": fila.get("producto_clave") or "",
            "producto_entrada_nombre": "",
            "producto_entrada_clave": "",
            "cantidad_salida": self._numero(fila.get("cantidad")),
            "cantidad_entrada": 0,
            "cantidad_merma": 0,
            "porcentaje_merma": 0,
            "rendimiento": 0,
            "usuario_confirmacion_nombre": fila.get("usuario_responsable") or "",
            "proveedor_nombre": fila.get("proveedor_nombre") or "",
            "estado": "Registrado",
            "observaciones": fila.get("observaciones") or "",
            "fecha": fecha.isoformat() if hasattr(fecha, "isoformat") else str(fecha or ""),
            "categoria_base": fila.get("categoria") or "",
        }

    def listar_historial(self, limite: int = 50) -> list[dict]:
        limite = max(1, min(int(limite or 50), 200))
        registros = [
            *self.listar_transformaciones(limite),
            *self.listar_salidas(limite),
        ]
        registros.sort(key=lambda item: item.get("fecha") or "", reverse=True)
        return registros[:limite]

    def resumen_mensual(self) -> dict:
        self.asegurar_tablas()
        fila = self.base_datos.fetchall(
            """
            DECLARE @inicio DATE = DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1);
            DECLARE @fin DATE = DATEADD(MONTH, 1, @inicio);

            SELECT
                COUNT(*) AS total_transformaciones,
                SUM(ISNULL(T.cantidad_origen, 0)) AS kilos_salida,
                SUM(ISNULL(DE.cantidad_resultado, 0)) AS kilos_entrada,
                SUM(
                    CASE
                        WHEN ISNULL(T.porcentaje_merma_esperado, 0) > 0
                        THEN ISNULL(T.cantidad_origen, 0)
                             * ISNULL(T.porcentaje_merma_esperado, 0) / 100
                        ELSE
                            CASE
                                WHEN ISNULL(T.cantidad_origen, 0)
                                   - ISNULL(DE.cantidad_resultado, 0) > 0
                                THEN ISNULL(T.cantidad_origen, 0)
                                   - ISNULL(DE.cantidad_resultado, 0)
                                ELSE 0
                            END
                    END
                ) AS kilos_merma
            FROM dbo.Transformaciones AS T
            OUTER APPLY (
                SELECT SUM(cantidad_resultado) AS cantidad_resultado
                FROM dbo.DetalleTransformaciones AS D
                WHERE D.id_transformacion = T.id_transformacion
            ) AS DE
            WHERE T.fecha_creacion >= @inicio
              AND T.fecha_creacion < @fin
            """,
            (),
        )[0]

        salida = self._numero(fila.get("kilos_salida"))
        entrada = self._numero(fila.get("kilos_entrada"))
        merma = self._numero(fila.get("kilos_merma"))
        salidas = self.base_datos.fetchall(
            """
            DECLARE @inicio DATE = DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1);
            DECLARE @fin DATE = DATEADD(MONTH, 1, @inicio);

            SELECT
                COUNT(*) AS total_salidas,
                SUM(ISNULL(cantidad, 0)) AS kilos_salida_almacen
            FROM dbo.ModuloCarnicoSalidaRegistro
            WHERE fecha >= @inicio
              AND fecha < @fin
            """,
            (),
        )[0]
        total_transformaciones = int(fila.get("total_transformaciones") or 0)
        total_salidas = int(salidas.get("total_salidas") or 0)
        return {
            "total_transformaciones": total_transformaciones,
            "total_salidas": total_salidas,
            "total_movimientos": total_transformaciones + total_salidas,
            "kilos_salida": salida,
            "kilos_salida_almacen": self._numero(salidas.get("kilos_salida_almacen")),
            "kilos_entrada": entrada,
            "kilos_merma": merma,
            "rendimiento": entrada / salida * 100 if salida else 0,
        }
