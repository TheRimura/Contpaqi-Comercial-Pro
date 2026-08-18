import unicodedata
from decimal import Decimal

import pyodbc

from cayal.comandos_base_datos import ComandosBaseDatos
from app.settings import AJUSTES_MODULO


class BaseDatos(ComandosBaseDatos):
    MODULO_ENTRADA = 202
    MODULO_SALIDA = 203

    MOVIMIENTOS_ENTRADA_RELACIONABLES = (
        0, 3, 5, 7, 13, 14, 16, 17, 19, 24, 26, 31,
    )
    MOVIMIENTOS_SALIDA_RELACIONABLES = (
        0, 2, 6, 8, 9, 10, 12, 13, 14, 21, 23, 28,
    )

    @staticmethod
    def _convertir_entero(valor: object | None, predeterminado: int = 0) -> int:
        if valor is None:
            return predeterminado
        if isinstance(valor, bool):
            return int(valor)
        if isinstance(valor, (int, float, Decimal, str)):
            try:
                return int(valor)
            except (TypeError, ValueError, OverflowError):
                return predeterminado
        return predeterminado

    @staticmethod
    def _convertir_texto(valor: object | None) -> str:
        if isinstance(valor, str):
            return valor
        if isinstance(valor, bytes):
            return valor.decode('utf-8', errors='replace')
        return ''

    def __init__(self):
        servidor = AJUSTES_MODULO.servidor_base_datos.strip()
        base_datos = AJUSTES_MODULO.nombre_base_datos.strip()
        super().__init__(servidor=servidor, base_de_datos=base_datos)
        conexion_heredada = getattr(
            self,
            '_BaseDatos__conexion_base_de_datos',
            None,
        )
        if not isinstance(conexion_heredada, str) or not conexion_heredada:
            raise RuntimeError(
                'El paquete cayal no inicializó una conexión válida.'
            )
        self._cadena_conexion_modulo: str = conexion_heredada
        self._tablas_modulo_verificadas = False
        self._tablas_relacion_verificadas = False
        self._tablas_configuracion_verificadas = False
        vista_oficial_formulas = super().fetchall(
            """
            SELECT OBJECT_ID(
                'dbo.vw_Cayal_FormulasProcesamiento'
            ) AS ObjectID
            """,
            (),
        )
        self._fuente_formulas = (
            'dbo.vw_Cayal_FormulasProcesamiento'
            if vista_oficial_formulas
            and vista_oficial_formulas[0].get('ObjectID')
            else 'dbo.zvwFormulasListasPCocinar'
        )
        contexto = super().fetchall(
            """
            SELECT
                CONVERT(NVARCHAR(128), SERVERPROPERTY('MachineName'))
                    AS MachineName,
                DB_NAME() AS DatabaseName,
                CONVERT(
                    NVARCHAR(128),
                    CONNECTIONPROPERTY('local_net_address')
                ) AS ServerAddress
            """,
            (),
        )
        if not contexto:
            raise RuntimeError(
                'No fue posible verificar el destino de la base de datos.'
            )
        destino = contexto[0]
        direccion = self._convertir_texto(
            destino.get('ServerAddress')
        ).strip()
        base_actual = self._convertir_texto(destino.get('DatabaseName')).strip()
        if base_actual.casefold() != AJUSTES_MODULO.nombre_base_datos.casefold():
            raise RuntimeError(
                'La conexión apunta a una base de datos no autorizada.'
            )
        if (
            not AJUSTES_MODULO.permitir_servidor_base_datos_remoto
            and direccion not in {'', '127.0.0.1', '::1'}
        ):
            raise RuntimeError(
                'Conexión remota bloqueada por seguridad. El módulo solo '
                'puede usar la instancia SQL local configurada.'
            )

    def fetchall(
            self,
            sql: str,
            params: tuple = (),
    ) -> list[dict]:
        return super().fetchall(sql, params)

    def command(
            self,
            sql: str,
            params: tuple = (),
    ) -> int | None:
        return super().command(sql, params)

    def fetchone(
            self,
            sql: str,
            params: tuple = (),
    ) -> object | None:
        with pyodbc.connect(self._cadena_conexion_modulo) as conexion:
            cursor = conexion.cursor()
            cursor.execute(sql, params)
            while True:
                if cursor.description is not None:
                    resultado = cursor.fetchone()
                    if resultado is not None:
                        return resultado[0]
                if not cursor.nextset():
                    return None

    # ----------------------------- SISTEMA -----------------------------
    def probar_conexion(self) -> bool:
        return self._convertir_entero(self.fetchone("SELECT 1", ())) == 1

    def buscar_configuracion_seguridad(self) -> dict:
        duracion = AJUSTES_MODULO.duracion_sesion_segundos
        nombre_cookie = AJUSTES_MODULO.nombre_cookie_sesion.strip()
        clave_firma = AJUSTES_MODULO.clave_firma_sesion.strip()

        if duracion <= 0:
            raise RuntimeError(
                "SESSION_MAX_AGE debe ser mayor que cero."
            )

        if not nombre_cookie:
            raise RuntimeError(
                "SESSION_COOKIE_NAME no puede estar vacío."
            )

        if not clave_firma:
            valor_clave_firma = self.fetchone(
                """
                IF OBJECT_ID(
                    'dbo.ModuloCarnicoConfiguracionSeguridad', 'U'
                ) IS NULL
                BEGIN
                    CREATE TABLE dbo.ModuloCarnicoConfiguracionSeguridad
                    (
                    id_configuracion TINYINT NOT NULL,
                        clave_firma NVARCHAR(200) NOT NULL,
                        fecha_creacion DATETIME2(0) NOT NULL
                            CONSTRAINT DF_ModuloCarnicoSeguridad_Fecha
                            DEFAULT SYSDATETIME()
                    );
                END;
                IF NOT EXISTS (
                    SELECT 1
                    FROM dbo.ModuloCarnicoConfiguracionSeguridad
                    WHERE id_configuracion = 1
                )
                BEGIN
                    INSERT dbo.ModuloCarnicoConfiguracionSeguridad
                        (id_configuracion, clave_firma) 
                    VALUES (
                        1,
                        CONVERT(NVARCHAR(36), NEWID())
                        + CONVERT(NVARCHAR(36), NEWID())
                        + CONVERT(NVARCHAR(36), NEWID())
                    );
                END;
                SELECT clave_firma
                FROM dbo.ModuloCarnicoConfiguracionSeguridad
                WHERE id_configuracion = 1;
                """,
                (),
            )
            if not isinstance(valor_clave_firma, str):
                raise RuntimeError(
                    "SQL Server no devolvió una clave de firma de sesión válida."
                )
            clave_firma = valor_clave_firma.strip()
            if not clave_firma:
                raise RuntimeError(
                    "La clave de firma almacenada en SQL Server está vacía."
                )

        return {
            "clave_firma": clave_firma,
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

        return self._convertir_entero(valor) == 1

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

        return self._convertir_texto(valor)

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

        return self._convertir_entero(valor)

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

        registros = self.fetchall(
            f"""
            SELECT ItemData, ItemValue
            FROM dbo.engRefCombo
            WHERE CboGroupName = ?
              {filtro}
            ORDER BY ItemValue
            """,
            (grupo,),
        )
        if not any(int(fila.get('ItemData') or 0) == 0 for fila in registros):
            registros.append({
                'ItemData': 0,
                'ItemValue': 'NO CLASIFICADO',
            })
        return sorted(
            registros,
            key=lambda fila: self._convertir_texto(fila.get('ItemValue')),
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

        if module_id not in (self.MODULO_ENTRADA, self.MODULO_SALIDA):
            return []

        return self.fetchall(
            """
            SELECT TOP (100)
                D.DocumentID,
                D.ModuleID,
                ISNULL(D.FolioPrefix, '') +
                    ISNULL(D.Folio, '') AS DocFolio,
                ISNULL(U.UserName, '') AS UserName,
                CAST(D.CreatedOn AS DATE) AS CreatedOn,
                CAST(D.DateDocument AS DATE) AS DateDocument,
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
            ORDER BY D.CreatedOn DESC, D.DocumentID DESC
            """,
            (module_id,),
        )

    def buscar_documentos_relacionables(
            self,
            module_id: int,
    ) -> list[dict]:
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

    def listar_lineas_transformacion(self) -> list[dict]:
        self.asegurar_tablas_modulo_carnico()
        filas = self.fetchall(
            f"""
            WITH ProductosModulo AS
            (
                SELECT P.ProductID, P.Category1
                FROM dbo.orgProduct AS P
                INNER JOIN dbo.ModuloCarnicoProductoConfigurado AS M
                    ON M.ProductID = P.ProductID
                   AND M.activo = 1
                WHERE P.Category1 IN ('CERDO', 'POLLO', 'RES LOCAL')
            ),
            RecetasPorLinea AS
            (
                SELECT
                    C.Category1,
                    COUNT(DISTINCT F.ProductID) AS TotalRecipes
                FROM {self._fuente_formulas} AS F
                INNER JOIN ProductosModulo AS C
                    ON C.ProductID = F.ComponenteID
                INNER JOIN ProductosModulo AS R
                    ON R.ProductID = F.ProductID
                GROUP BY C.Category1
            )
            SELECT
                P.Category1,
                COUNT(*) AS TotalProducts,
                ISNULL(R.TotalRecipes, 0) AS TotalRecipes
            FROM ProductosModulo AS P
            LEFT JOIN RecetasPorLinea AS R ON R.Category1 = P.Category1
            GROUP BY P.Category1, R.TotalRecipes
            ORDER BY P.Category1
            """,
            (),
        )
        return [
            {
                'Category1': fila.get('Category1'),
                'total_productos': int(fila.get('TotalProducts') or 0),
                'total_recetas': int(fila.get('TotalRecipes') or 0),
            }
            for fila in filas
        ]

    def listar_productos_base_transformacion(self, linea: str) -> list[dict]:
        self.asegurar_tablas_modulo_carnico()
        filas = self.fetchall(
            """
            SELECT
                P.Category2 AS ProductBase,
                COALESCE(
                    MIN(CASE
                        WHEN UPPER(LTRIM(RTRIM(P.ProductName))) =
                             UPPER(LTRIM(RTRIM(P.Category2)))
                        THEN P.ProductID
                    END),
                    MIN(P.ProductID)
                ) AS BaseProductID,
                COUNT(*) AS TotalResults
            FROM dbo.orgProduct AS P
            INNER JOIN dbo.ModuloCarnicoProductoConfigurado AS CatalogoModulo
                ON CatalogoModulo.product_id = P.ProductID
               AND CatalogoModulo.activo = 1
            WHERE UPPER(LTRIM(RTRIM(ISNULL(P.Category1, '')))) =
                  UPPER(LTRIM(RTRIM(?)))
              AND NULLIF(LTRIM(RTRIM(P.Category2)), '') IS NOT NULL
            GROUP BY P.Category2
            ORDER BY P.Category2
            """,
            (str(linea).strip(),),
        )
        return [
            {
                'ProductBase': fila.get('ProductBase'),
                'ProductBaseID': fila.get('BaseProductID'),
                'total_resultantes': fila.get('TotalResults'),
            }
            for fila in filas
        ]

    def listar_transformaciones_precargadas(self, linea: str) -> list[dict]:
        self.asegurar_tablas_modulo_carnico()
        self.asegurar_proveedor_transformaciones_usuario()
        filas = self.fetchall(
            """
            SELECT
                T.id_transformacion_usuario AS TransformationUserID,
                T.nombre_transformacion AS TransformationName,
                T.producto_origen AS BaseProductID,
                P.ProductName AS BaseProductName,
                P.Category1 AS ProductLine,
                ISNULL(E.OfficialName, '') AS SupplierName
            FROM dbo.TransformacionesUsuario AS T
            INNER JOIN dbo.orgProduct AS P
                ON P.ProductID = T.producto_origen
            LEFT JOIN dbo.orgSupplier AS S
                ON S.SupplierID = T.proveedor_id
            LEFT JOIN dbo.orgBusinessEntity AS E
                ON E.BusinessEntityID = S.BusinessEntityID
            INNER JOIN dbo.ModuloCarnicoProductoConfigurado AS CatalogoModulo
                ON CatalogoModulo.product_id = P.ProductID
               AND CatalogoModulo.activo = 1
            WHERE T.activa = 1
              AND UPPER(LTRIM(RTRIM(P.Category1))) =
                  UPPER(LTRIM(RTRIM(?)))
            ORDER BY T.nombre_transformacion
            """,
            (str(linea).strip(),),
        )
        return [
            {
                'transformacion_id': fila.get('TransformationUserID'),
                'nombre_transformacion': fila.get('TransformationName'),
                'producto_base_id': fila.get('BaseProductID'),
                'producto_base': fila.get('BaseProductName'),
                'linea': fila.get('ProductLine'),
                'proveedor': fila.get('SupplierName'),
            }
            for fila in filas
        ]

    def listar_transformaciones_disponibles(self) -> list[dict]:
        self.asegurar_tablas_modulo_carnico()
        filas = self.fetchall(
            f"""
            SELECT
                P.ProductID AS ProductID,
                P.ProductName AS ProductName,
                Base.ProductID AS BaseProductID,
                P.Category2 AS BaseProductName,
                P.Category1 AS ProductLine,
                CAST(CASE WHEN EXISTS
                (
                    SELECT 1
                    FROM {self._fuente_formulas} AS Formula
                    WHERE Formula.ProductID = P.ProductID
                ) THEN 1 ELSE 0 END AS BIT) AS HasFormula,
                CAST(1 AS BIT) AS IsCatalogSource
            FROM dbo.orgProduct AS P
            INNER JOIN dbo.ModuloCarnicoProductoConfigurado AS CatalogoModulo
                ON CatalogoModulo.product_id = P.ProductID
               AND CatalogoModulo.activo = 1
            OUTER APPLY
            (
                SELECT TOP 1 B.ProductID, B.ProductName
                FROM dbo.orgProduct AS B
                WHERE B.DiscontinuedOn IS NULL
                  AND B.ProductID <> P.ProductID
                  AND UPPER(LTRIM(RTRIM(REPLACE(B.ProductName, '.', '')))) <>
                      UPPER(LTRIM(RTRIM(REPLACE(P.ProductName, '.', ''))))
                  AND UPPER(LTRIM(RTRIM(ISNULL(B.Category1, '')))) =
                      UPPER(LTRIM(RTRIM(ISNULL(P.Category1, ''))))
                  AND UPPER(LTRIM(RTRIM(ISNULL(B.Category2, '')))) =
                      UPPER(LTRIM(RTRIM(ISNULL(P.Category2, ''))))
                ORDER BY
                    CASE WHEN UPPER(LTRIM(RTRIM(B.ProductName))) =
                              UPPER(LTRIM(RTRIM(P.Category2)))
                         THEN 0 ELSE 1 END,
                    B.ProductID
            ) AS Base
            WHERE UPPER(LTRIM(RTRIM(ISNULL(P.Category1, ''))))
                  IN ('CERDO', 'POLLO', 'RES LOCAL')
              AND NULLIF(LTRIM(RTRIM(P.Category2)), '') IS NOT NULL
              AND UPPER(LTRIM(RTRIM(P.ProductName))) <>
                  UPPER(LTRIM(RTRIM(P.Category2)))
              AND Base.ProductID IS NOT NULL
            ORDER BY P.Category1, P.Category2, P.ProductName
            """,
            (),
        )
        return [
            {
                'transformacionID': fila.get('ProductID'),
                'nombre_transformacion': fila.get('ProductName'),
                'producto_base_id': fila.get('BaseProductID'),
                'producto_base': fila.get('BaseProductName'),
                'linea': fila.get('ProductLine'),
                'tiene_formula': bool(fila.get('HasFormula')),
                'origen_catalogo': bool(fila.get('IsCatalogSource')),
            }
            for fila in filas
        ]

    @staticmethod
    def _palabras_clave_producto(nombre: str) -> set[str]:
        texto = unicodedata.normalize('NFKD', str(nombre or '').upper())
        texto = ''.join(
            caracter for caracter in texto
            if not unicodedata.combining(caracter)
        )
        palabras_ignoradas = {
            'A', 'AL', 'CON', 'DE', 'DEL', 'EL', 'EN', 'LA', 'LAS',
            'LOS', 'PARA', 'POR', 'Y', 'PZA', 'PIEZA', 'PIEZAS',
            'PAQUETE', 'CAJA', 'KG', 'KILO', 'KILOS',
        }
        palabras = ''.join(
            caracter if caracter.isalnum() else ' '
            for caracter in texto
        ).split()
        alias = {
            'ALA': 'ALA', 'ALAS': 'ALA', 'ALITA': 'ALA',
            'ALITAS': 'ALA', 'ALONE': 'ALA', 'ALONES': 'ALA',
            'PICANTE': 'PICANTE', 'PICANTES': 'PICANTE',
            'PICOSITA': 'PICANTE', 'PICOSITAS': 'PICANTE',
        }
        resultado = set()
        for palabra in palabras:
            if palabra in palabras_ignoradas:
                continue
            singular = (
                palabra[:-1]
                if palabra.endswith('S') and len(palabra) > 4
                else palabra
            )
            resultado.add(alias.get(palabra, alias.get(singular, singular)))
        return resultado

    @staticmethod
    def _nombre_producto_normalizado(nombre: str) -> str:
        texto = unicodedata.normalize('NFKD', str(nombre or '').upper())
        texto = ''.join(
            caracter for caracter in texto
            if not unicodedata.combining(caracter)
        )
        return ' '.join(
            ''.join(
                caracter if caracter.isalnum() else ' '
                for caracter in texto
            ).split()
        )

    @classmethod
    def _semejanza_nombre_producto(cls, esperado: str, candidato: str) -> float:
        nombre_esperado = cls._nombre_producto_normalizado(esperado)
        nombre_candidato = cls._nombre_producto_normalizado(candidato)
        if not nombre_esperado or not nombre_candidato:
            return 0.0
        palabras_esperadas = cls._palabras_clave_producto(nombre_esperado)
        palabras_candidatas = cls._palabras_clave_producto(nombre_candidato)
        if nombre_esperado == nombre_candidato:
            coincidencia_texto = 1.0
        elif (
                nombre_esperado in nombre_candidato
                or nombre_candidato in nombre_esperado
        ):
            coincidencia_texto = 0.85
        else:
            limite = min(len(nombre_esperado), len(nombre_candidato))
            comunes = 0
            for posicion in range(limite):
                if nombre_esperado[posicion] != nombre_candidato[posicion]:
                    break
                comunes += 1
            coincidencia_texto = comunes / max(
                len(nombre_esperado), len(nombre_candidato)
            )
        coincidencia_palabras = (
            len(palabras_esperadas & palabras_candidatas) /
            len(palabras_esperadas | palabras_candidatas)
            if palabras_esperadas and palabras_candidatas else 0.0
        )
        return max(coincidencia_texto, coincidencia_palabras)

    def buscar_producto_formula_relacionado(
            self,
            producto_resultante_id: int,
            nombre_resultante: str,
            linea: str,
    ) -> int:
        formula_directa = self.fetchone(
            f"""
            SELECT TOP 1 ProductID
            FROM {self._fuente_formulas}
            WHERE ProductID = ?
            """,
            (int(producto_resultante_id),),
        )
        if formula_directa is not None:
            if not isinstance(formula_directa, int):
                raise RuntimeError(
                    "el sistema devolvió un identificador de fórmula inválido."
                )
            return formula_directa

        candidatos = self.fetchall(
            f"""
            SELECT DISTINCT F.ProductID, F.Producto
            FROM {self._fuente_formulas} AS F
            WHERE EXISTS
            (
                SELECT 1
                FROM {self._fuente_formulas} AS ComponenteFormula
                INNER JOIN dbo.orgProduct AS Componente
                    ON Componente.ProductID = ComponenteFormula.ComponenteID
                   AND Componente.DiscontinuedOn IS NULL
                WHERE ComponenteFormula.ProductID = F.ProductID
                  AND UPPER(LTRIM(RTRIM(ISNULL(Componente.Category1, '')))) =
                      UPPER(LTRIM(RTRIM(?)))
            )
            """,
            (str(linea).strip(),),
        )
        palabras_resultante = self._palabras_clave_producto(
            nombre_resultante
        )
        palabras_genericas = {
            'CERDO', 'POLLO', 'RES', 'CARNE', 'PRODUCTO', 'FRESCO',
            'CONGELADA', 'CONGELADO', 'PREPARADA', 'PREPARADO',
        }
        coincidencias = []
        for candidato in candidatos:
            palabras_formula = self._palabras_clave_producto(
                candidato.get('Producto') or ''
            )
            comunes = palabras_resultante & palabras_formula
            comunes_distintivas = comunes - palabras_genericas
            cobertura = (
                len(comunes) / len(palabras_resultante)
                if palabras_resultante else 0
            )
            semejanza = self._semejanza_nombre_producto(
                nombre_resultante, candidato.get('Producto') or ''
            )
            coincidencia_suficiente = (
                    (len(comunes) >= 2 and cobertura >= 0.60)
                    or (comunes_distintivas and semejanza >= 0.40)
            )
            if coincidencia_suficiente:
                coincidencias.append((
                    len(comunes_distintivas),
                    cobertura,
                    semejanza,
                    -len(palabras_formula - palabras_resultante),
                    int(candidato['ProductID']),
                ))
        if not coincidencias:
            return 0
        coincidencias.sort(reverse=True)
        return coincidencias[0][4]

    def obtener_transformacion_catalogo(
            self, producto_resultante_id: int
    ) -> dict | None:
        disponibles = self.fetchall(
            f"""
            SELECT TOP 1
                P.ProductID AS transformacionID ,
                P.ProductName AS nombre_transformacion,
                P.ProductID AS producto_resultante_id,
                P.ProductName AS producto_resultante,
                P.Unit AS unidad_resultante,
                Base.Category1 AS linea,
                Base.Componente AS producto_base,
                Base.ComponenteID AS producto_base_id
            FROM dbo.orgProduct AS P
            CROSS APPLY
            (
                SELECT TOP 1
                    F.ComponenteID,
                    F.Componente,
                    C.Category1,
                    F.CantidadComp
                FROM {self._fuente_formulas} AS F
                INNER JOIN dbo.orgProduct AS C
                    ON C.ProductID = F.ComponenteID
                   AND C.DiscontinuedOn IS NULL
                WHERE F.ProductID = P.ProductID
                  AND F.ComponenteID <> P.ProductID
                  AND UPPER(LTRIM(RTRIM(REPLACE(F.Componente, '.', '')))) <>
                      UPPER(LTRIM(RTRIM(REPLACE(P.ProductName, '.', ''))))
                  AND UPPER(LTRIM(RTRIM(ISNULL(C.Category1, ''))))
                      IN ('CERDO', 'POLLO', 'RES LOCAL')
                ORDER BY
                    F.CantidadComp DESC,
                    F.IDComp,
                    F.ComponenteID
            ) AS Base
            WHERE P.ProductID = ?
              AND P.DiscontinuedOn IS NULL
              AND EXISTS
              (
                  SELECT 1
                  FROM {self._fuente_formulas} AS Formula
                  WHERE Formula.ProductID = P.ProductID
              )
            """,
            (int(producto_resultante_id),),
        )
        if not disponibles:
            disponibles = self.fetchall(
                """
                SELECT TOP 1
                    P.ProductID AS transformacion_id,
                    P.ProductName AS nombre_transformacion,
                    P.ProductID AS producto_resultante_id,
                    P.ProductName AS producto_resultante,
                    P.Unit AS unidad_resultante,
                    P.Category1 AS linea,
                    Base.ProductName AS producto_base,
                    Base.ProductID AS producto_base_id
                FROM dbo.orgProduct AS P
                OUTER APPLY
                (
                    SELECT TOP 1 B.ProductID, B.ProductName
                    FROM dbo.orgProduct AS B
                    WHERE B.DiscontinuedOn IS NULL
                      AND B.ProductID <> P.ProductID
                      AND UPPER(LTRIM(RTRIM(REPLACE(B.ProductName, '.', '')))) <>
                          UPPER(LTRIM(RTRIM(REPLACE(P.ProductName, '.', ''))))
                      AND UPPER(LTRIM(RTRIM(ISNULL(B.Category1, '')))) =
                          UPPER(LTRIM(RTRIM(ISNULL(P.Category1, ''))))
                      AND UPPER(LTRIM(RTRIM(ISNULL(B.Category2, '')))) =
                          UPPER(LTRIM(RTRIM(ISNULL(P.Category2, ''))))
                    ORDER BY
                        CASE WHEN UPPER(LTRIM(RTRIM(B.ProductName))) =
                                  UPPER(LTRIM(RTRIM(P.Category2)))
                             THEN 0 ELSE 1 END,
                        B.ProductID
                ) AS Base
                WHERE P.ProductID = ?
                  AND P.DiscontinuedOn IS NULL
                  AND UPPER(LTRIM(RTRIM(ISNULL(P.Category1, ''))))
                      IN ('CERDO', 'POLLO', 'RES LOCAL')
                  AND NULLIF(LTRIM(RTRIM(P.Category2)), '') IS NOT NULL
                  AND Base.ProductID IS NOT NULL
                """,
                (int(producto_resultante_id),),
            )
        if not disponibles or not disponibles[0].get('producto_base_id'):
            return None
        registro = disponibles[0]
        if int(registro['producto_base_id']) == int(producto_resultante_id):
            return None
        if (
                str(registro['producto_base']).strip(' .').upper()
                == str(registro['producto_resultante']).strip(' .').upper()
        ):
            return None
        producto_formula_id = self.buscar_producto_formula_relacionado(
            producto_resultante_id=int(producto_resultante_id),
            nombre_resultante=registro['nombre_transformacion'],
            linea=registro['linea'],
        )
        componentes_formula = (
            self.buscar_formula_producto_configuracion(producto_formula_id)
            if producto_formula_id else []
        )
        componentes_de_linea = [
            componente for componente in componentes_formula
            if str(componente.get('linea') or '').strip().upper() ==
               str(registro['linea'] or '').strip().upper()
        ]
        if componentes_de_linea:
            componente_base = max(
                componentes_de_linea,
                key=lambda componente: float(componente.get('cantidad') or 0),
            )
            registro['producto_base_id'] = int(componente_base['ProductID'])
            registro['producto_base'] = componente_base['producto']
        componentes = []
        base_en_formula = False
        for orden, componente in enumerate(componentes_formula, start=1):
            es_base = int(componente['product_id']) == int(registro['producto_base_id'])
            base_en_formula = base_en_formula or es_base
            componentes.append({
                'ProductID': int(componente['ProductID']),
                'producto': componente['producto'],
                'cantidad': float(componente['cantidad']),
                'unidad': componente.get('unidad') or 'KILO',
                'es_producto_base': es_base,
                'tipo_componente': 'PRODUCTO_BASE' if es_base else 'INSUMO',
                'orden': orden,
            })
        if not base_en_formula:
            componentes.insert(0, {
                'product_id': int(registro['producto_base_id']),
                'producto': registro['producto_base'],
                'cantidad': 1.0,
                'unidad': 'KILO',
                'es_producto_base': True,
                'tipo_componente': 'PRODUCTO_BASE',
                'orden': 0,
            })
        return {
            'transformacionID ': int(registro['transformacionID']),
            'nombre_transformacion': registro['nombre_transformacion'],
            'producto_base_id': int(registro['producto_base_id']),
            'producto_base': registro['producto_base'],
            'linea': registro['linea'],
            'porcentaje_merma': AJUSTES_MODULO.merma_tecnica_porcentaje,
            'origen_catalogo': True,
            'resultantes': [{
                'ProductID': int(registro['producto_resultante_id']),
                'producto_resultante': registro['producto_resultante'],
                'cantidad': AJUSTES_MODULO.factor_rendimiento,
                'unidad': registro.get('unidad_resultante') or 'KILO',
            }],
            'componentes': componentes,
        }

    def obtener_transformacion_precargada(
            self,
            transformacion_id: int,
    ) -> dict | None:
        encabezados = self.fetchall(
            """
            SELECT TOP 1
                T.id_transformacion_usuario AS transformacionID,
                T.nombre_transformacion,
                T.producto_origen AS producto_base_id,
                P.ProductName AS producto_base,
                P.Category1 AS linea,
                T.porcentaje_merma
            FROM dbo.TransformacionesUsuario AS T
            INNER JOIN dbo.orgProduct AS P
                ON P.ProductID = T.producto_origen
            WHERE T.id_transformacion_usuario = ?
              AND T.activa = 1
              AND P.DiscontinuedOn IS NULL
            """,
            (int(transformacion_id),),
        )
        if not encabezados:
            return None
        detalle = encabezados[0]
        if not AJUSTES_MODULO.transformacion_permite_merma_personalizada(
                detalle['nombre_transformacion']
        ):
            detalle['porcentaje_merma'] = (
                AJUSTES_MODULO.merma_tecnica_porcentaje
            )
        filas_resultantes = self.fetchall(
            """
            SELECT
                D.producto_resultante AS ProductID,
                P.ProductName AS ProductName,
                D.cantidad_resultante AS Quantity,
                D.unidad AS Unit
            FROM dbo.TransformacionesUsuarioDetalle AS D
            INNER JOIN dbo.orgProduct AS P
                ON P.ProductID = D.producto_resultante
            WHERE D.id_transformacion_usuario = ?
              AND D.activa = 1
            ORDER BY D.orden
            """,
            (int(transformacion_id),),
        )
        detalle['resultantes'] = [
            {
                'product_id': fila.get('ProductID'),
                'producto_resultante': fila.get('ProductName'),
                'cantidad': fila.get('Quantity'),
                'unidad': fila.get('Unit'),
            }
            for fila in filas_resultantes
        ]
        filas_componentes = self.fetchall(
            """
            SELECT
                C.producto_componente AS ProductID,
                P.ProductName AS ProductName,
                C.cantidad AS Quantity,
                C.unidad AS Unit,
                C.es_producto_base AS IsBaseProduct,
                C.tipo_componente AS ComponentType,
                C.orden AS SortOrder
            FROM dbo.TransformacionesUsuarioComponente AS C
            INNER JOIN dbo.orgProduct AS P
                ON P.ProductID = C.producto_componente
            WHERE C.id_transformacion_usuario = ?
              AND C.activa = 1
            ORDER BY C.orden
            """,
            (int(transformacion_id),),
        )
        detalle['componentes'] = [
            {
                'product_id': fila.get('ProductID'),
                'producto': fila.get('ProductName'),
                'cantidad': fila.get('Quantity'),
                'unidad': fila.get('Unit'),
                'es_producto_base': fila.get('IsBaseProduct'),
                'tipo_componente': fila.get('ComponentType'),
                'orden': fila.get('SortOrder'),
            }
            for fila in filas_componentes
        ]
        if not detalle['resultantes']:
            return None
        return detalle

    def listar_productos_resultantes_transformacion(
            self,
            linea: str,
            producto_base: str,
    ) -> list[dict]:
        filas = self.fetchall(
            """
            SELECT
                ProductID AS ProductID,
                ProductName AS ProductName,
                Unit AS Unit
            FROM dbo.orgProduct
            WHERE DiscontinuedOn IS NULL
              AND UPPER(LTRIM(RTRIM(ISNULL(Category1, '')))) =
                  UPPER(LTRIM(RTRIM(?)))
              AND UPPER(LTRIM(RTRIM(ISNULL(Category2, '')))) =
                  UPPER(LTRIM(RTRIM(?)))
            ORDER BY ProductName, ProductID
            """,
            (str(linea).strip(), str(producto_base).strip()),
        )
        return [
            {
                'product_id': fila.get('ProductID'),
                'producto_resultante': fila.get('ProductName'),
                'unidad': fila.get('Unit'),
            }
            for fila in filas
        ]

    def sugerir_documento_por_producto(
            self,
            module_id: int,
            product_id: int,
            cantidad: float | None = None,
    ) -> dict | None:
        filas = self.fetchall(
            """
            SELECT TOP 1
                D.DocumentID,
                D.ModuleID,
                ISNULL(D.FolioPrefix, '') + ISNULL(D.Folio, '') AS DocFolio,
                ISNULL(U.UserName, '') AS UserName,
                CAST(D.DateDocument AS DATE) AS DateDocument,
                DI.Quantity
            FROM dbo.docDocument AS D
            INNER JOIN dbo.docDocumentItem AS DI
                ON DI.DocumentID = D.DocumentID
               AND DI.DeletedOn IS NULL
            LEFT JOIN dbo.engUser AS U
                ON U.UserID = D.CreatedBy
            WHERE D.ModuleID = ?
              AND DI.ProductID = ?
              AND D.DeletedOn IS NULL
              AND D.CancelledOn IS NULL
              AND ISNULL(D.SourceDocumentID, 0) = 0
              AND ISNULL(D.DestinationDocumentID, 0) = 0
              AND ISNULL(D.Custom1, '') = ''
            ORDER BY
                CASE WHEN ? IS NULL THEN 0
                     ELSE ABS(ISNULL(DI.Quantity, 0) - ?) END,
                D.DateDocument DESC,
                D.DocumentID DESC
            """,
            (int(module_id), int(product_id), cantidad, cantidad),
        )
        return filas[0] if filas else None

    def validar_productos_transformacion(
            self,
            linea: str,
            producto_base_id: int,
            producto_resultante_id: int,
    ) -> dict | None:
        filas = self.fetchall(
            """
            SELECT TOP 1
                Base.Category1,
                Base.Category2,
                Base.ProductName AS ProductoBase,
                Resultado.ProductName AS ProductoResultante
            FROM dbo.orgProduct AS Base
            INNER JOIN dbo.orgProduct AS Resultado
                ON UPPER(LTRIM(RTRIM(Resultado.Category1))) =
                   UPPER(LTRIM(RTRIM(Base.Category1)))
               AND UPPER(LTRIM(RTRIM(Resultado.Category2))) =
                   UPPER(LTRIM(RTRIM(Base.Category2)))
            WHERE Base.ProductID = ?
              AND Resultado.ProductID = ?
              AND UPPER(LTRIM(RTRIM(Base.Category1))) =
                  UPPER(LTRIM(RTRIM(?)))
              AND Base.DiscontinuedOn IS NULL
              AND Resultado.DiscontinuedOn IS NULL
            """,
            (
                int(producto_base_id),
                int(producto_resultante_id),
                str(linea).strip(),
            ),
        )
        return filas[0] if filas else None

    def obtener_siguientes_folios_transformacion(self) -> dict:
        filas = self.fetchall(
            """
            SELECT
                F.ModuleID,
                F.Serie,
                CASE
                    WHEN COALESCE(MAX(TRY_CAST(D.Folio AS BIGINT)), 0) <
                         F.DocNumberFrom
                    THEN F.DocNumberFrom
                    ELSE COALESCE(MAX(TRY_CAST(D.Folio AS BIGINT)), 0) + 1
                END AS SiguienteFolio
            FROM dbo.engDocumentFolio AS F
            LEFT JOIN dbo.docDocument AS D
                ON D.ModuleID = F.ModuleID
            WHERE F.ModuleID IN (202, 203)
              AND F.DeletedOn IS NULL
            GROUP BY F.ModuleID, F.Serie, F.DocNumberFrom
            """,
            (),
        )
        por_modulo = {int(fila['ModuleID']): fila for fila in filas}
        salida = por_modulo.get(self.MODULO_SALIDA, {})
        entrada = por_modulo.get(self.MODULO_ENTRADA, {})
        return {
            'folio_salida': (
                f"{salida.get('Serie', 'SA')}"
                f"{salida.get('SiguienteFolio', '')}"
            ),
            'folio_entrada': (
                f"{entrada.get('Serie', 'EA')}"
                f"{entrada.get('SiguienteFolio', '')}"
            ),
        }

    def obtener_proveedores_producto(self, product_id: int) -> list[dict]:
        return self.fetchall(
            """
            SELECT DISTINCT
                S.SupplierID,
                S.BusinessEntityID,
                LTRIM(RTRIM(E.OfficialName)) AS OfficialName
            FROM dbo.orgProductSupplier AS PS
            INNER JOIN dbo.orgSupplier AS S
                ON S.SupplierID = PS.SupplierID
               AND S.DeletedOn IS NULL
            INNER JOIN dbo.orgBusinessEntity AS E
                ON E.BusinessEntityID = S.BusinessEntityID
            WHERE PS.ProductID = ?
              AND NULLIF(LTRIM(RTRIM(E.OfficialName)), '') IS NOT NULL
            ORDER BY OfficialName
            """,
            (int(product_id),),
        )

    def crear_documentos_transformacion(
            self,
            producto_base_id: int,
            producto_resultante_id: int,
            cantidad_base: float,
            cantidad_resultante: float,
            usuario_erp: int,
            usuario_fisico_id: int,
            tipo_movimiento_salida_id: int,
            tipo_movimiento_entrada_id: int,
            insumos: list[dict] | None = None,
    ) -> dict | None:
        insumos_validos = [
            (
                self._convertir_entero(insumo.get('producto_id')),
                float(insumo.get('cantidad') or 0),
            )
            for insumo in (insumos or [])
            if self._convertir_entero(insumo.get('producto_id')) > 0
            and float(insumo.get('cantidad') or 0) > 0
        ]
        valores_insumos = ', '.join('(?, ?)' for _ in insumos_validos)
        carga_insumos = (
            f'INSERT INTO @Insumos (producto_id, cantidad) VALUES '
            f'{valores_insumos};'
            if valores_insumos else ''
        )
        parametros_insumos = tuple(
            valor
            for insumo in insumos_validos
            for valor in insumo
        )
        relation_id = self.fetchone(
            f"""
            SET NOCOUNT ON;
            BEGIN TRY
                BEGIN TRANSACTION;

                DECLARE @LockResult INT;
                EXEC @LockResult = sys.sp_getapplock
                    @Resource = 'CAYAL_TRANSFORMACION_FOLIOS_202_203',
                    @LockMode = 'Exclusive',
                    @LockOwner = 'Transaction',
                    @LockTimeout = 15000;
                IF @LockResult < 0
                    THROW 50100, 'No fue posible reservar los folios.', 1;

                DECLARE @Salida TABLE (Documento INT);
                DECLARE @Entrada TABLE (Documento INT);
                DECLARE @ItemSalida TABLE (DocumentItemID BIGINT);
                DECLARE @ItemEntrada TABLE (DocumentItemID BIGINT);
                DECLARE @Insumos TABLE
                (
                    producto_id INT NOT NULL,
                    cantidad FLOAT NOT NULL
                );
                {carga_insumos}
                DECLARE @SalidaID INT;
                DECLARE @EntradaID INT;
                DECLARE @RelacionID INT;
                DECLARE @FolioSalida NVARCHAR(125);
                DECLARE @FolioEntrada NVARCHAR(125);

                INSERT INTO @Salida
                EXEC dbo.zvwCrearDocumentoCayal
                    0, 'SA', 0, 203, ?, 0, 0, 0, 0;
                SELECT @SalidaID = Documento FROM @Salida;

                INSERT INTO @Entrada
                EXEC dbo.zvwCrearDocumentoCayal
                    0, 'EA', 0, 202, ?, 0, 0, 0, 0;
                SELECT @EntradaID = Documento FROM @Entrada;

                IF ISNULL(@SalidaID, 0) = 0 OR ISNULL(@EntradaID, 0) = 0
                    THROW 50101, 'La base de datos no pudo crear los documentos.', 1;

                INSERT INTO @ItemSalida
                EXEC dbo.zvwInsertarProductoCayal
                    @SalidaID, ?, 2, ?, 0, 0, 0, 0, 203,
                    'Producto base de transformación';

                DECLARE @InsumoID INT;
                DECLARE @CantidadInsumo FLOAT;
                DECLARE cursor_insumos CURSOR LOCAL FAST_FORWARD FOR
                    SELECT producto_id, cantidad
                    FROM @Insumos;
                OPEN cursor_insumos;
                FETCH NEXT FROM cursor_insumos
                    INTO @InsumoID, @CantidadInsumo;
                WHILE @@FETCH_STATUS = 0
                BEGIN
                    INSERT INTO @ItemSalida
                    EXEC dbo.zvwInsertarProductoCayal
                        @SalidaID, @InsumoID, 2, @CantidadInsumo,
                        0, 0, 0, 0, 203,
                        'Insumo consumido en transformación';
                    FETCH NEXT FROM cursor_insumos
                        INTO @InsumoID, @CantidadInsumo;
                END;
                CLOSE cursor_insumos;
                DEALLOCATE cursor_insumos;

                INSERT INTO @ItemEntrada
                EXEC dbo.zvwInsertarProductoCayal
                    @EntradaID, ?, 2, ?, 0, 0, 0, 0, 202,
                    'Producto resultante de transformación';

                SELECT @FolioSalida =
                    ISNULL(FolioPrefix, '') + ISNULL(Folio, '')
                FROM dbo.docDocument WHERE DocumentID = @SalidaID;
                SELECT @FolioEntrada =
                    ISNULL(FolioPrefix, '') + ISNULL(Folio, '')
                FROM dbo.docDocument WHERE DocumentID = @EntradaID;

                IF @SalidaID = @EntradaID
                    THROW 50102, 'Los documentos no pueden ser el mismo.', 1;

                IF NOT EXISTS
                (
                    SELECT 1
                    FROM dbo.docDocument WITH (UPDLOCK, HOLDLOCK)
                    WHERE DocumentID = @SalidaID
                      AND ModuleID = 203
                      AND DeletedOn IS NULL
                      AND CancelledOn IS NULL
                      AND ISNULL(SourceDocumentID, 0) = 0
                      AND ISNULL(DestinationDocumentID, 0) = 0
                      AND ISNULL(Custom1, '') = ''
                )
                    THROW 50103, 'La salida no está disponible para relacionarse.', 1;

                IF NOT EXISTS
                (
                    SELECT 1
                    FROM dbo.docDocument WITH (UPDLOCK, HOLDLOCK)
                    WHERE DocumentID = @EntradaID
                      AND ModuleID = 202
                      AND DeletedOn IS NULL
                      AND CancelledOn IS NULL
                      AND ISNULL(SourceDocumentID, 0) = 0
                      AND ISNULL(DestinationDocumentID, 0) = 0
                      AND ISNULL(Custom1, '') = ''
                )
                    THROW 50104, 'La entrada no está disponible para relacionarse.', 1;

                IF EXISTS
                (
                    SELECT 1
                    FROM dbo.docDocumentWarehouseRelation WITH (UPDLOCK, HOLDLOCK)
                    WHERE SourceDocumentID = @SalidaID
                       OR DestinationDocumentID = @EntradaID
                )
                    THROW 50105, 'La relación entre documentos ya existe.', 1;

                UPDATE dbo.docDocument
                SET DestinationDocumentID = @EntradaID,
                    CustomCbo = ?,
                    Custom1 = @FolioEntrada
                WHERE DocumentID = @SalidaID AND ModuleID = 203;

                UPDATE dbo.docDocument
                SET SourceDocumentID = @SalidaID,
                    CustomCbo = ?,
                    Custom1 = @FolioSalida
                WHERE DocumentID = @EntradaID AND ModuleID = 202;

                INSERT INTO dbo.docDocumentWarehouseRelation
                (
                    SourceDocumentID, DestinationDocumentID,
                    SupplierID, PhysicalUserID, MovementDate,
                    ERPUserID, SourceBrandID, DestinationBrandID, CreatedOn
                )
                VALUES
                (
                    @SalidaID, @EntradaID,
                    0, ?, CAST(GETDATE() AS DATE),
                    ?, NULL, NULL, GETDATE()
                );
                SET @RelacionID = CONVERT(INT, SCOPE_IDENTITY());

                COMMIT TRANSACTION;
                SELECT @RelacionID;
            END TRY
            BEGIN CATCH
                IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
                THROW;
            END CATCH;
            """,
            parametros_insumos + (
                int(usuario_erp),
                int(usuario_erp),
                int(producto_base_id),
                float(cantidad_base),
                int(producto_resultante_id),
                float(cantidad_resultante),
                int(tipo_movimiento_salida_id),
                int(tipo_movimiento_entrada_id),
                int(usuario_fisico_id),
                int(usuario_erp),
            ),
        )
        if relation_id is None:
            return None
        if not isinstance(relation_id, int):
            raise RuntimeError(
                "El sistema devolvió un identificador de relación inválido."
            )
        filas = self.fetchall(
            """
            SELECT
                R.SourceDocumentID,
                R.DestinationDocumentID,
                ISNULL(S.FolioPrefix, '') + ISNULL(S.Folio, '') AS FolioSalida,
                ISNULL(E.FolioPrefix, '') + ISNULL(E.Folio, '') AS FolioEntrada
            FROM dbo.docDocumentWarehouseRelation AS R
            INNER JOIN dbo.docDocument AS S
                ON S.DocumentID = R.SourceDocumentID
            INNER JOIN dbo.docDocument AS E
                ON E.DocumentID = R.DestinationDocumentID
            WHERE R.DocumentWarehouseRelationID = ?
            """,
            (relation_id,),
        )
        return filas[0] if filas else None

    def obtener_proveedores_documentos(self) -> list[dict]:
        return self.fetchall(
            """
            SELECT
                S.BusinessEntityID,
                E.OfficialName
            FROM dbo.orgSupplier AS S
            INNER JOIN dbo.orgBusinessEntity AS E
                ON S.BusinessEntityID = E.BusinessEntityID
            WHERE S.DeletedOn IS NULL
              AND S.SupplierID IS NOT NULL
              AND NULLIF(LTRIM(RTRIM(E.OfficialName)), '') IS NOT NULL
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

    def listar_historial_transformaciones(
            self,
            limite: int = 10,
            pagina: int = 1,
            fecha_desde: str = '',
            fecha_hasta: str = '',
            transformacion: str = '',
    ) -> dict:
        return self._consultar_historial_transformaciones(
            limite=limite,
            pagina=pagina,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            transformacion=transformacion,
        )

    @staticmethod
    def _quitar_rango_presentacion(nombre: object | None) -> str:
        texto = BaseDatos._convertir_texto(nombre).strip()
        if not texto.endswith(')') or '(' not in texto:
            return texto
        apertura = texto.rfind('(')
        rango = texto[apertura + 1:-1].replace(' ', '')
        partes = rango.replace('+', '-').split('-')
        if not partes or any(not parte.isdigit() for parte in partes if parte):
            return texto
        prefijo = texto[:apertura].rstrip()
        if prefijo.endswith('1'):
            prefijo = prefijo[:-1].rstrip(' .')
        return prefijo or texto

    def _consultar_historial_transformaciones(
            self,
            limite: int = 10,
            pagina: int = 1,
            fecha_desde: str = '',
            fecha_hasta: str = '',
            transformacion: str = '',
    ) -> dict:
        limite = min(max(int(limite), 1), 50)
        pagina = max(int(pagina), 1)
        desplazamiento = (pagina - 1) * limite
        filas = self.fetchall(
            """
            WITH RelacionesFiltradas AS
            (
                SELECT
                    R.DocumentWarehouseRelationID AS relacion_id,
                    R.SourceDocumentID AS documento_salida_id,
                    R.DestinationDocumentID AS documento_entrada_id,
                    R.MovementDate AS fecha_movimiento,
                    R.CreatedOn AS fecha_hora,
                    R.PhysicalUserID AS tablajero_id,
                    R.ERPUserID AS usuario_erp_id,
                    ISNULL(S.FolioPrefix, '') + ISNULL(S.Folio, '') AS folio_salida,
                    ISNULL(E.FolioPrefix, '') + ISNULL(E.Folio, '') AS folio_entrada,
                    COUNT_BIG(*) OVER () AS total_registros
                FROM dbo.docDocumentWarehouseRelation AS R
                INNER JOIN dbo.docDocument AS S
                    ON S.DocumentID = R.SourceDocumentID
                   AND S.ModuleID = 203
                INNER JOIN dbo.docDocument AS E
                    ON E.DocumentID = R.DestinationDocumentID
                   AND E.ModuleID = 202
                WHERE S.DeletedOn IS NULL
                  AND E.DeletedOn IS NULL
                  AND TRY_CONVERT(INT, S.CustomCbo) = 2
                  AND TRY_CONVERT(INT, E.CustomCbo) = 5
                  AND (? = '' OR R.CreatedOn >= TRY_CONVERT(DATE, ?))
                  AND (
                        ? = ''
                        OR R.CreatedOn < DATEADD(DAY, 1, TRY_CONVERT(DATE, ?))
                      )
                  AND (
                        ? = ''
                        OR EXISTS
                        (
                            SELECT 1
                            FROM dbo.docDocumentItem AS DIFiltro
                            INNER JOIN dbo.orgProduct AS PFiltro
                                ON PFiltro.ProductID = DIFiltro.ProductID
                            WHERE DIFiltro.DocumentID = E.DocumentID
                              AND DIFiltro.DeletedOn IS NULL
                              AND UPPER(ISNULL(PFiltro.ProductName, '')) LIKE
                                  '%' + UPPER(?) + '%'
                        )
                      )
            ),
            Pagina AS
            (
                SELECT *
                FROM RelacionesFiltradas
                ORDER BY fecha_hora DESC, relacion_id DESC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            )
            SELECT
                RF.relacion_id,
                RF.documento_salida_id,
                RF.documento_entrada_id,
                COALESCE(
                    RF.fecha_movimiento,
                    CAST(RF.fecha_hora AS DATE)
                ) AS fecha,
                RF.fecha_hora,
                RF.folio_salida,
                RF.folio_entrada,
                RF.total_registros,
                RF.tablajero_id,
                RF.usuario_erp_id,
                CASE
                    WHEN ISNULL(Partidas.total_partidas, 0) > 1
                     AND ISNULL(PartidasEntrada.total_partidas, 0) > 1
                    THEN CONCAT(Partidas.total_partidas, ' productos')
                    ELSE ISNULL(Base.ProductName, '')
                END AS producto_base,
                ISNULL(Base.Category1, '') AS linea,
                CASE
                    WHEN ISNULL(Partidas.total_partidas, 0) > 1
                     AND ISNULL(PartidasEntrada.total_partidas, 0) > 1
                    THEN ISNULL(Partidas.cantidad_total, 0)
                    ELSE ISNULL(Base.Quantity, 0)
                END AS cantidad_base,
                CASE
                    WHEN ISNULL(Partidas.total_partidas, 0) > 1
                     AND ISNULL(PartidasEntrada.total_partidas, 0) > 1
                    THEN CONCAT(ISNULL(PartidasEntrada.total_partidas, 0), ' productos')
                    ELSE ISNULL(Resultado.ProductName, '')
                END AS producto_resultante,
                CASE
                    WHEN ISNULL(Partidas.total_partidas, 0) > 1
                     AND ISNULL(PartidasEntrada.total_partidas, 0) > 1
                    THEN ISNULL(PartidasEntrada.cantidad_total, 0)
                    ELSE ISNULL(Resultado.Quantity, 0)
                END AS cantidad_resultante,
                ISNULL(Partidas.total_partidas, 0) AS total_partidas_salida,
                CASE
                    WHEN ISNULL(Partidas.total_partidas, 0) > 1
                     AND ISNULL(PartidasEntrada.total_partidas, 0) > 1
                    THEN 1 ELSE 0
                END AS es_documento_lote
            FROM Pagina AS RF
            OUTER APPLY
            (
                SELECT TOP 1 P.ProductName, P.Category1, DI.Quantity
                FROM dbo.docDocumentItem AS DI
                INNER JOIN dbo.orgProduct AS P
                    ON P.ProductID = DI.ProductID
                WHERE DI.DocumentID = RF.documento_salida_id
                  AND DI.DeletedOn IS NULL
                ORDER BY
                    CASE WHEN DI.Comments LIKE 'Producto base%'
                         THEN 0 ELSE 1 END,
                    DI.DocumentItemID
            ) AS Base
            OUTER APPLY
            (
                SELECT TOP 1 P.ProductName, DI.Quantity
                FROM dbo.docDocumentItem AS DI
                INNER JOIN dbo.orgProduct AS P
                    ON P.ProductID = DI.ProductID
                WHERE DI.DocumentID = RF.documento_entrada_id
                  AND DI.DeletedOn IS NULL
                ORDER BY DI.DocumentItemID
            ) AS Resultado
            OUTER APPLY
            (
                SELECT
                    COUNT(*) AS total_partidas,
                    SUM(ISNULL(DI.Quantity, 0)) AS cantidad_total
                FROM dbo.docDocumentItem AS DI
                WHERE DI.DocumentID = RF.documento_salida_id
                  AND DI.DeletedOn IS NULL
            ) AS Partidas
            OUTER APPLY
            (
                SELECT
                    COUNT(*) AS total_partidas,
                    SUM(ISNULL(DI.Quantity, 0)) AS cantidad_total
                FROM dbo.docDocumentItem AS DI
                WHERE DI.DocumentID = RF.documento_entrada_id
                  AND DI.DeletedOn IS NULL
            ) AS PartidasEntrada
            ORDER BY
                RF.fecha_hora DESC,
                RF.relacion_id DESC
            """,
            (
                fecha_desde, fecha_desde,
                fecha_hasta, fecha_hasta,
                transformacion, transformacion,
                desplazamiento, limite,
            ),
        )
        total_registros = int(
            filas[0].get('total_registros', 0) if filas else 0
        )
        for fila in filas:
            fila.pop('total_registros', None)
            fila['producto_base'] = self._quitar_rango_presentacion(
                fila.get('producto_base')
            )
            fila['producto_resultante'] = self._quitar_rango_presentacion(
                fila.get('producto_resultante')
            )
            total_partidas = int(
                fila.pop('total_partidas_salida', 0) or 0
            )
            es_documento_lote = bool(fila.get('es_documento_lote'))
            fila['total_partidas'] = total_partidas
            fila['total_insumos'] = (
                0 if es_documento_lote else max(total_partidas - 1, 0)
            )
        total_paginas = max(
            (total_registros + limite - 1) // limite,
            1,
        )
        return {
            'registros': filas,
            'pagina': min(pagina, total_paginas),
            'por_pagina': limite,
            'total_registros': total_registros,
            'total_paginas': total_paginas,
        }

    def obtener_resumen_historial_transformaciones(
            self,
            fecha_desde: str = '',
            fecha_hasta: str = '',
            transformacion: str = '',
    ) -> dict[str, float | int]:
        filas = self.fetchall(
            """
            WITH RelacionesFiltradas AS
            (
                SELECT
                    R.DocumentWarehouseRelationID AS relacion_id,
                    R.SourceDocumentID AS documento_salida_id,
                    R.DestinationDocumentID AS documento_entrada_id
                FROM dbo.docDocumentWarehouseRelation AS R
                INNER JOIN dbo.docDocument AS S
                    ON S.DocumentID = R.SourceDocumentID
                   AND S.ModuleID = 203
                INNER JOIN dbo.docDocument AS E
                    ON E.DocumentID = R.DestinationDocumentID
                   AND E.ModuleID = 202
                WHERE S.DeletedOn IS NULL
                  AND E.DeletedOn IS NULL
                  AND TRY_CONVERT(INT, S.CustomCbo) = 2
                  AND TRY_CONVERT(INT, E.CustomCbo) = 5
                  AND (? = '' OR R.CreatedOn >= TRY_CONVERT(DATE, ?))
                  AND (
                        ? = ''
                        OR R.CreatedOn < DATEADD(DAY, 1, TRY_CONVERT(DATE, ?))
                      )
                  AND (
                        ? = ''
                        OR EXISTS
                        (
                            SELECT 1
                            FROM dbo.docDocumentItem AS DIFiltro
                            INNER JOIN dbo.orgProduct AS PFiltro
                                ON PFiltro.ProductID = DIFiltro.ProductID
                            WHERE DIFiltro.DocumentID = E.DocumentID
                              AND DIFiltro.DeletedOn IS NULL
                              AND UPPER(ISNULL(PFiltro.ProductName, '')) LIKE
                                  '%' + UPPER(?) + '%'
                        )
                      )
            ),
            PartidasSalida AS
            (
                SELECT
                    RF.relacion_id,
                    DI.Quantity,
                    COUNT_BIG(*) OVER (
                        PARTITION BY RF.relacion_id
                    ) AS total_partidas,
                    SUM(ISNULL(DI.Quantity, 0)) OVER (
                        PARTITION BY RF.relacion_id
                    ) AS cantidad_total,
                    ROW_NUMBER() OVER (
                        PARTITION BY RF.relacion_id
                        ORDER BY
                            CASE WHEN DI.Comments LIKE 'Producto base%'
                                 THEN 0 ELSE 1 END,
                            DI.DocumentItemID
                    ) AS numero_fila
                FROM RelacionesFiltradas AS RF
                INNER JOIN dbo.docDocumentItem AS DI
                    ON DI.DocumentID = RF.documento_salida_id
                   AND DI.DeletedOn IS NULL
            ),
            PartidasEntrada AS
            (
                SELECT
                    RF.relacion_id,
                    DI.Quantity,
                    COUNT_BIG(*) OVER (
                        PARTITION BY RF.relacion_id
                    ) AS total_partidas,
                    SUM(ISNULL(DI.Quantity, 0)) OVER (
                        PARTITION BY RF.relacion_id
                    ) AS cantidad_total,
                    ROW_NUMBER() OVER (
                        PARTITION BY RF.relacion_id
                        ORDER BY DI.DocumentItemID
                    ) AS numero_fila
                FROM RelacionesFiltradas AS RF
                INNER JOIN dbo.docDocumentItem AS DI
                    ON DI.DocumentID = RF.documento_entrada_id
                   AND DI.DeletedOn IS NULL
            ),
            Cantidades AS
            (
                SELECT
                    RF.relacion_id,
                    CASE
                        WHEN ISNULL(PS.total_partidas, 0) > 1
                         AND ISNULL(PE.total_partidas, 0) > 1
                        THEN ISNULL(PS.cantidad_total, 0)
                        ELSE ISNULL(PS.Quantity, 0)
                    END AS cantidad_base,
                    CASE
                        WHEN ISNULL(PS.total_partidas, 0) > 1
                         AND ISNULL(PE.total_partidas, 0) > 1
                        THEN ISNULL(PE.cantidad_total, 0)
                        ELSE ISNULL(PE.Quantity, 0)
                    END AS cantidad_resultante
                FROM RelacionesFiltradas AS RF
                LEFT JOIN PartidasSalida AS PS
                    ON PS.relacion_id = RF.relacion_id
                   AND PS.numero_fila = 1
                LEFT JOIN PartidasEntrada AS PE
                    ON PE.relacion_id = RF.relacion_id
                   AND PE.numero_fila = 1
            )
            SELECT
                COUNT_BIG(*) AS transformaciones,
                ISNULL(SUM(cantidad_base), 0) AS kilos_procesados,
                ISNULL(SUM(
                    CASE
                        WHEN cantidad_base > cantidad_resultante
                        THEN cantidad_base - cantidad_resultante
                        ELSE 0
                    END
                ), 0) AS merma_acumulada,
                CASE
                    WHEN ISNULL(SUM(cantidad_base), 0) > 0
                    THEN ISNULL(SUM(cantidad_resultante), 0)
                         / SUM(cantidad_base) * 100
                    ELSE 0
                END AS rendimiento
            FROM Cantidades
            """,
            (
                fecha_desde, fecha_desde,
                fecha_hasta, fecha_hasta,
                transformacion, transformacion,
            ),
        )
        if not filas:
            resumen: dict[str, float | int] = {
                'transformaciones': 0,
                'kilos_procesados': 0.0,
                'merma_acumulada': 0.0,
                'rendimiento': 0.0,
            }
        else:
            fila = filas[0]
            resumen = {
                'transformaciones': int(fila.get('transformaciones') or 0),
                'kilos_procesados': float(fila.get('kilos_procesados') or 0),
                'merma_acumulada': float(fila.get('merma_acumulada') or 0),
                'rendimiento': float(fila.get('rendimiento') or 0),
            }
        return dict(resumen)

    @staticmethod
    def invalidar_cache_historial() -> None:
        return None

    def listar_documentos_relacionados_exportacion(
            self,
            limite: int = 500,
    ) -> list[dict]:
        limite = min(max(int(limite), 1), 500)
        consulta = """
            WITH Relaciones AS
            (
                SELECT TOP (?)
                    R.DocumentWarehouseRelationID AS relacion_id,
                    R.SourceDocumentID AS documento_salida_id,
                    R.DestinationDocumentID AS documento_entrada_id,
                    R.CreatedOn AS fecha_hora,
                    ISNULL(S.FolioPrefix, '') + ISNULL(S.Folio, '') AS folio_salida,
                    ISNULL(E.FolioPrefix, '') + ISNULL(E.Folio, '') AS folio_entrada,
                    R.PhysicalUserID AS tablajero_id,
                    R.ERPUserID AS usuario_erp_id
                FROM dbo.docDocumentWarehouseRelation AS R
                INNER JOIN dbo.docDocument AS S
                    ON S.DocumentID = R.SourceDocumentID AND S.ModuleID = 203
                INNER JOIN dbo.docDocument AS E
                    ON E.DocumentID = R.DestinationDocumentID AND E.ModuleID = 202
                WHERE S.DeletedOn IS NULL
                  AND E.DeletedOn IS NULL
                  AND TRY_CONVERT(INT, S.CustomCbo) = 2
                  AND TRY_CONVERT(INT, E.CustomCbo) = 5
                ORDER BY R.CreatedOn DESC, R.DocumentWarehouseRelationID DESC
            )
            SELECT
                R.relacion_id, R.fecha_hora, R.folio_salida, R.folio_entrada,
                R.tablajero_id, R.usuario_erp_id,
                ? AS tipo_documento,
                CASE WHEN ? = 'SALIDA' THEN R.folio_salida ELSE R.folio_entrada END
                    AS folio_documento,
                DI.DocumentItemID AS PartidaID,
                ISNULL(P.ProductName, '') AS producto,
                ISNULL(DI.Quantity, 0) AS cantidad
            FROM Relaciones AS R
            INNER JOIN dbo.docDocumentItem AS DI
                ON DI.DocumentID = CASE WHEN ? = 'SALIDA'
                    THEN R.documento_salida_id ELSE R.documento_entrada_id END
               AND DI.DeletedOn IS NULL
            INNER JOIN dbo.orgProduct AS P ON P.ProductID = DI.ProductID
            ORDER BY R.fecha_hora DESC, R.relacion_id DESC, DI.DocumentItemID
        """
        salida = self.fetchall(consulta, (limite, 'SALIDA', 'SALIDA', 'SALIDA'))
        entrada = self.fetchall(consulta, (limite, 'ENTRADA', 'ENTRADA', 'ENTRADA'))
        orden = {'SALIDA': 1, 'ENTRADA': 2}
        registros = salida + entrada
        registros.sort(
            key=lambda fila: (
                fila.get('fecha_hora'),
                int(fila.get('relacion_id') or 0),
                -orden.get(self._convertir_texto(fila.get('tipo_documento')), 9),
                -int(fila.get('PartidaID') or 0),
            ),
            reverse=True,
        )
        return [
            {
                clave: valor
                for clave, valor in fila.items()
                if clave != 'PartidaID'
            }
            for fila in registros
        ]

    def obtener_detalle_historial_transformacion(
            self,
            relacion_id: int,
    ) -> dict | None:
        relaciones = self.fetchall(
            """
            SELECT TOP 1
                R.DocumentWarehouseRelationID AS relacion_id,
                R.SourceDocumentID AS documento_salida_id,
                R.DestinationDocumentID AS documento_entrada_id,
                ISNULL(S.FolioPrefix, '') + ISNULL(S.Folio, '') AS folio_salida,
                ISNULL(E.FolioPrefix, '') + ISNULL(E.Folio, '') AS folio_entrada,
                R.CreatedOn AS fecha_hora,
                R.PhysicalUserID AS tablajero_id,
                R.ERPUserID AS usuario_erp_id
            FROM dbo.docDocumentWarehouseRelation AS R
            INNER JOIN dbo.docDocument AS S
                ON S.DocumentID = R.SourceDocumentID
            INNER JOIN dbo.docDocument AS E
                ON E.DocumentID = R.DestinationDocumentID
            WHERE R.DocumentWarehouseRelationID = ?
              AND S.DeletedOn IS NULL
              AND E.DeletedOn IS NULL
            """,
            (int(relacion_id),),
        )
        if not relaciones:
            return None
        relacion = relaciones[0]

        relacion['salida'] = self.obtener_partidas_documento_erp(
            int(relacion['documento_salida_id'])
        )
        relacion['entrada'] = self.obtener_partidas_documento_erp(
            int(relacion['documento_entrada_id'])
        )
        relacion['es_documento_lote'] = (
            len(relacion['salida']) > 1
            and len(relacion['entrada']) > 1
        )
        return relacion

    def obtener_relacion_documento(
            self,
            document_id: int,
    ) -> dict | None:
        self.asegurar_tablas_relacion_documentos()
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
            LEFT JOIN dbo.ModuloAlmacenMarca AS BS
                ON BS.BrandID = R.SourceBrandID
            LEFT JOIN dbo.ModuloAlmacenMarca AS BD
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
        partidas = self.fetchall(
            """
            SELECT
                Partida.*,
                ISNULL(Producto.Category1, '') AS ProductCategory,
                ISNULL(Producto.Unit, '') AS ProductUnit
            FROM [dbo].[zvwBuscarPartidasDocumentoCayal-DocumentID](?) AS Partida
            LEFT JOIN dbo.orgProduct AS Producto
                ON Producto.ProductID = Partida.ProductID
            ORDER BY Partida.DocumentItemID
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
                    "Category": (
                            partida.get("Category1")
                            or partida.get("ProductCategory")
                            or ""
                    ),
                    "ProductKey": partida.get("ProductKey") or "",
                    "ProductName": partida.get("ProductName") or "",
                    "Unit": (
                        partida.get("Unit")
                        or partida.get("ProductUnit")
                        or "UNIDAD"
                    ),
                    "Quantity": cantidad,
                    "CostPrice": costo,
                    "total": total,
                }
            )

        return resultado

    def buscar_document_id_por_folio(
            self,
            folio: str,
            module_id: int | None = None,
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

        return self._convertir_entero(valor)

    # -------------------------- MODULO CARNICO -------------------------
    def asegurar_tablas_modulo_carnico(self) -> None:
        if self._tablas_modulo_verificadas:
            return
        if not self._tablas_modulo_verificadas:
            if self._tablas_modulo_verificadas:
                return
            self.command(
                """
            IF OBJECT_ID(
                'dbo.ModuloCarnicoProductoConfigurado',
                'U'
            ) IS NULL
            BEGIN
                CREATE TABLE dbo.ModuloCarnicoProductoConfigurado (
                    id_producto_carnico INT IDENTITY(1,1) NOT NULL,
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
                    id_bitacora INT IDENTITY(1,1) NOT NULL,
                    accion NVARCHAR(50) NOT NULL,
                    usuario_id BIGINT NULL,
                    usuario_confirmacion_nombre NVARCHAR(150) NOT NULL,
                    detalle NVARCHAR(500) NULL,
                    productos_json NVARCHAR(MAX) NULL,
                    fecha DATETIME2 NOT NULL
                        CONSTRAINT DF_MCPB_fecha DEFAULT SYSUTCDATETIME()
                );
            END;

            INSERT dbo.ModuloCarnicoProductoConfigurado
            (
                product_id, clave, nombre_producto, categoria, unidad,
                porcentaje_merma, activo, usuario_creacion
            )
            SELECT
                P.ProductID, CONVERT(NVARCHAR(50), P.ProductID),
                P.ProductName, P.Category1, ISNULL(P.Unit, 'KILO'),
                0, 1, NULL
            FROM dbo.orgProduct AS P
            WHERE P.DiscontinuedOn IS NULL
              AND UPPER(LTRIM(RTRIM(ISNULL(P.Category1, ''))))
                  IN ('CERDO', 'POLLO', 'RES LOCAL')
              AND NOT EXISTS
              (
                  SELECT 1
                  FROM dbo.ModuloCarnicoProductoConfigurado AS M
                  WHERE M.product_id = P.ProductID
              );

            IF OBJECT_ID(
                'dbo.ModuloCarnicoTransformacionRegistro',
                'U'
            ) IS NULL
            BEGIN
                CREATE TABLE dbo.ModuloCarnicoTransformacionRegistro (
                    id_registro INT IDENTITY(1,1) NOT NULL,
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
            self._tablas_modulo_verificadas = True

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
        del productos
        self.command(
            """
            INSERT INTO dbo.ModuloCarnicoProductoBitacora (
                accion,
                usuario_id,
                usuario_confirmacion_nombre,
                detalle
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                accion,
                usuario_id,
                usuario_confirmacion_nombre,
                detalle,
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

            if id_configuracion is not None:
                if not isinstance(id_configuracion, int):
                    raise ValueError(
                        "El identificador de la configuración debe ser entero."
                    )
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
                    (*parametros, id_configuracion),
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
    ) -> dict | None:
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
        return self._convertir_entero(registro_id)

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
        self.asegurar_tablas_relacion_documentos()
        return self.fetchall(
            """
            SELECT BrandID, BrandName
            FROM dbo.ModuloAlmacenMarca
            WHERE activo = 1
              AND (
                    UPPER(LTRIM(RTRIM(categoria))) = UPPER(LTRIM(RTRIM(?)))
                 OR NULLIF(LTRIM(RTRIM(categoria)), '') IS NULL
              )
            ORDER BY BrandName
            """,
            (categoria,),
        )

    def asegurar_tablas_relacion_documentos(self) -> None:
        if self._tablas_relacion_verificadas:
            return
        if not self._tablas_relacion_verificadas:
            if self._tablas_relacion_verificadas:
                return
            self.command(
                """
            IF OBJECT_ID('dbo.ModuloAlmacenMarca', 'U') IS NULL
            BEGIN
                CREATE TABLE dbo.ModuloAlmacenMarca (
                    BrandID INT IDENTITY(1,1) NOT NULL,
                    BrandName NVARCHAR(150) NOT NULL,
                    categoria NVARCHAR(150) NULL,
                    activo BIT NOT NULL
                        CONSTRAINT DF_ModuloAlmacenMarca_activo DEFAULT 1,
                    fecha_creacion DATETIME2 NOT NULL
                        CONSTRAINT DF_ModuloAlmacenMarca_fecha DEFAULT SYSDATETIME()
                );
            END;
                """,
                (),
            )
            self._tablas_relacion_verificadas = True

    def obtener_o_crear_marca_modulo(self, categoria: str, nombre: str) -> int:
        categoria = str(categoria or "").strip()
        nombre = " ".join(str(nombre or "").strip().split())
        if not nombre:
            return 0
        self.asegurar_tablas_relacion_documentos()
        self.command(
            """
            IF NOT EXISTS (
                SELECT 1
                FROM dbo.ModuloAlmacenMarca
                WHERE UPPER(LTRIM(RTRIM(BrandName))) = UPPER(LTRIM(RTRIM(?)))
                  AND UPPER(LTRIM(RTRIM(ISNULL(categoria, '')))) =
                      UPPER(LTRIM(RTRIM(?)))
            )
            BEGIN
                INSERT INTO dbo.ModuloAlmacenMarca (BrandName, categoria)
                VALUES (?, NULLIF(?, ''));
            END;
            """,
            (nombre, categoria, nombre, categoria),
        )
        valor = self.fetchone(
            """
            SELECT TOP 1 BrandID
            FROM dbo.ModuloAlmacenMarca
            WHERE UPPER(LTRIM(RTRIM(BrandName))) = UPPER(LTRIM(RTRIM(?)))
              AND UPPER(LTRIM(RTRIM(ISNULL(categoria, '')))) =
                  UPPER(LTRIM(RTRIM(?)))
            ORDER BY BrandID
            """,
            (nombre, categoria),
        )
        return self._convertir_entero(valor)

    def homologar_tipo_movimiento_documento(
            self,
            document_id: int,
    ) -> None:
        documentos = self.fetchall(
            """
            SELECT TOP (1)
                ModuleID,
                TRY_CONVERT(INT, CustomCbo) AS MovementTypeID,
                NULLIF(LTRIM(RTRIM(ISNULL(Comments, ''))), '') AS Comments
            FROM dbo.docDocument
            WHERE DocumentID = ?
              AND DeletedOn IS NULL
              AND CancelledOn IS NULL
            """,
            (int(document_id),),
        )
        if not documentos:
            return

        documento = documentos[0]
        modulo = int(documento.get('ModuleID') or 0)
        numero_movimiento = int(documento.get('MovementTypeID') or 0)
        if modulo not in (self.MODULO_ENTRADA, self.MODULO_SALIDA):
            return
        if numero_movimiento <= 0:
            return

        tipo = 'entrada' if modulo == self.MODULO_ENTRADA else 'salida'
        super().clasificar_movimiento_almacen(
            int(document_id),
            tipo,
            numero_movimiento,
            documento.get('Comments'),
        )

    # ---------------- CONFIGURACION DE TRANSFORMACIONES ----------------
    def asegurar_proveedor_transformaciones_usuario(self) -> None:
        if self._tablas_configuracion_verificadas:
            return
        if not self._tablas_configuracion_verificadas:
            if self._tablas_configuracion_verificadas:
                return
            self.command(
                """
            IF OBJECT_ID('dbo.TransformacionesUsuario', 'U') IS NOT NULL
               AND COL_LENGTH('dbo.TransformacionesUsuario', 'proveedor_id') IS NULL
            BEGIN
                ALTER TABLE dbo.TransformacionesUsuario
                ADD proveedor_id INT NULL;
            END;

            IF OBJECT_ID(
                'dbo.ModuloCarnicoConfiguracionAuditoria',
                'U'
            ) IS NULL
            BEGIN
                CREATE TABLE dbo.ModuloCarnicoConfiguracionAuditoria (
                    id_auditoria INT IDENTITY(1,1) NOT NULL,
                    configuracion_id INT NULL,
                    configuracion_nombre NVARCHAR(150) NOT NULL,
                    accion NVARCHAR(30) NOT NULL,
                    usuario_id BIGINT NULL,
                    usuario_nombre NVARCHAR(150) NOT NULL,
                    motivo NVARCHAR(300) NOT NULL,
                    valores_anteriores_json NVARCHAR(MAX) NULL,
                    valores_nuevos_json NVARCHAR(MAX) NULL,
                    fecha DATETIME2 NOT NULL
                        CONSTRAINT DF_MCCA_fecha DEFAULT SYSDATETIME()
                );
            END;
                """,
                (),
            )
            self._tablas_configuracion_verificadas = True

    def registrar_auditoria_configuracion(
            self,
            configuracion_id,
            configuracion_nombre: str,
            accion: str,
            usuario_id,
            usuario_nombre: str,
            motivo: str,
            valores_anteriores=None,
            valores_nuevos=None,
    ) -> int:
        self.asegurar_proveedor_transformaciones_usuario()
        valores_anteriores_texto = (
            valores_anteriores if isinstance(valores_anteriores, str) else None
        )
        valores_nuevos_texto = (
            valores_nuevos if isinstance(valores_nuevos, str) else None
        )
        return self._convertir_entero(self.fetchone(
            """
            INSERT dbo.ModuloCarnicoConfiguracionAuditoria (
                configuracion_id, configuracion_nombre, accion,
                usuario_id, usuario_nombre, motivo,
                valores_anteriores_json, valores_nuevos_json
            )
            OUTPUT INSERTED.id_auditoria
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                configuracion_id,
                configuracion_nombre,
                accion,
                usuario_id,
                usuario_nombre,
                motivo,
                valores_anteriores_texto,
                valores_nuevos_texto,
            ),
        ))
    def listar_auditoria_configuraciones(
            self,
            limite: int = 100,
    ) -> list[dict]:
        self.asegurar_proveedor_transformaciones_usuario()
        registros = self.fetchall(
            """
            SELECT TOP (?)
                id_auditoria, configuracion_id, configuracion_nombre,
                accion, usuario_id, usuario_nombre, motivo,
                valores_anteriores_json, valores_nuevos_json, fecha
            FROM dbo.ModuloCarnicoConfiguracionAuditoria
            ORDER BY fecha DESC, id_auditoria DESC
            """,
            (int(limite),),
        )
        return [
            {
                **{
                    clave: valor
                    for clave, valor in registro.items()
                    if clave not in {
                        'valores_anteriores_json',
                        'valores_nuevos_json',
                    }
                },
                'valores_anteriores': registro.get(
                    'valores_anteriores_json'
                ),
                'valores_nuevos': registro.get('valores_nuevos_json'),
            }
            for registro in registros
        ]

    def buscar_productos_base_configuracion(
            self, linea: str, termino: str = ''
    ) -> list[dict]:
        self.asegurar_tablas_modulo_carnico()
        linea_limpia = self._nombre_producto_normalizado(linea)
        texto = ' '.join(str(termino or '').strip().split())
        texto_busqueda = f'{texto}%'
        parametros = (linea_limpia, texto, texto_busqueda)
        configuraciones = self.fetchall(
            """
            SELECT
                -T.id_transformacion_usuario AS ProductID,
                T.nombre_transformacion AS ProductName,
                CAST('TRANSFORMACION' AS NVARCHAR(50)) AS Unit,
                T.fecha_creacion AS CreatedAt,
                CAST(CASE WHEN T.fecha_creacion >= DATEADD(DAY, -30, GETDATE())
                     THEN 1 ELSE 0 END AS BIT) AS IsRecent,
                CAST(1 AS BIT) AS HasRecipe,
                CAST(1 AS BIT) AS IsConfiguration,
                T.id_transformacion_usuario AS TransformationUserID
            FROM dbo.TransformacionesUsuario AS T
            INNER JOIN dbo.orgProduct AS Base
                ON Base.ProductID = T.producto_origen
            INNER JOIN dbo.ModuloCarnicoProductoConfigurado AS CatalogoModulo
                ON CatalogoModulo.product_id = Base.ProductID
               AND CatalogoModulo.activo = 1
            WHERE T.activa = 1
              AND Base.Category1 = ?
              AND (? = '' OR T.nombre_transformacion LIKE ?)
            """,
            parametros,
        )
        productos = self.fetchall(
            f"""
            SELECT
                P.ProductID AS ProductID,
                P.ProductName AS ProductName,
                CAST(ISNULL(P.Unit, 'KILO') AS NVARCHAR(50)) AS Unit,
                P.CreatedOn AS CreatedAt,
                CAST(CASE WHEN P.CreatedOn >= DATEADD(DAY, -30, GETDATE())
                     THEN 1 ELSE 0 END AS BIT) AS IsRecent,
                CAST(CASE WHEN EXISTS
                (
                    SELECT 1 FROM {self._fuente_formulas} AS F
                    WHERE F.ComponenteID = P.ProductID
                ) THEN 1 ELSE 0 END AS BIT) AS HasRecipe,
                CAST(0 AS BIT) AS IsConfiguration,
                CAST(NULL AS INT) AS TransformationUserID
            FROM dbo.orgProduct AS P
            INNER JOIN dbo.ModuloCarnicoProductoConfigurado AS CatalogoModulo
                ON CatalogoModulo.product_id = P.ProductID
               AND CatalogoModulo.activo = 1
            WHERE P.Category1 = ?
              AND (? = '' OR P.ProductName LIKE ?)
            """,
            parametros,
        )
        return [
            {
                'product_id': int(fila.get('ProductID') or 0),
                'producto': self._convertir_texto(fila.get('ProductName')),
                'unidad': self._convertir_texto(fila.get('Unit')),
                'fecha_creacion': fila.get('CreatedAt'),
                'es_reciente': bool(fila.get('IsRecent')),
                'tiene_receta': bool(fila.get('HasRecipe')),
                'es_configuracion': bool(fila.get('IsConfiguration')),
                'transformacion_id': fila.get('TransformationUserID'),
            }
            for fila in (configuraciones + productos)[:200]
        ]

    def ocultar_producto_catalogo(
            self,
            producto_id: int,
            es_configuracion: bool,
            transformacion_id: int | None,
            nombre: str,
            linea: str,
            usuario_id: int,
            usuario_nombre: str,
    ) -> None:
        if es_configuracion:
            if not transformacion_id:
                raise ValueError('La configuración seleccionada no es válida.')
            self.command(
                """
                UPDATE dbo.TransformacionesUsuario
                SET activa = 0
                WHERE id_transformacion_usuario = ?
                  AND activa = 1
                """,
                (int(transformacion_id),),
            )
            configuracion_id = int(transformacion_id)
        else:
            if int(producto_id) <= 0:
                raise ValueError('El producto seleccionado no es válido.')
            ocultado = self.fetchone(
                """
                UPDATE dbo.ModuloCarnicoProductoConfigurado
                SET activo = 0,
                    usuario_actualizacion = ?,
                    fecha_actualizacion = SYSDATETIME()
                OUTPUT INSERTED.product_id
                WHERE product_id = ?
                  AND activo = 1;
                """,
                (
                    int(usuario_id), int(producto_id),
                ),
            )
            if ocultado is None:
                raise ValueError(
                    'El producto ya está oculto o no está disponible.'
                )
            configuracion_id = -int(producto_id)
        self.registrar_auditoria_configuracion(
            configuracion_id=configuracion_id,
            configuracion_nombre=nombre,
            accion='ELIMINAR',
            usuario_id=usuario_id,
            usuario_nombre=usuario_nombre,
            motivo='Producto ocultado desde el catálogo',
            valores_anteriores={'visible': True, 'linea': linea},
            valores_nuevos={
                'visible': False,
                'producto_id': int(producto_id),
                'es_configuracion': bool(es_configuracion),
            },
        )

    def buscar_productos_resultantes_configuracion(
            self, linea: str, termino: str = ''
    ) -> list[dict]:
        linea_limpia = self._nombre_producto_normalizado(linea)
        texto = str(termino or '').strip()
        filas = self.fetchall(
            f"""
            SELECT DISTINCT TOP (100)
                F.ProductID AS ProductID,
                F.Producto AS ProductName,
                ISNULL(R.Unit, 'KILO') AS Unit
            FROM {self._fuente_formulas} AS F
            INNER JOIN dbo.orgProduct AS C
                ON C.ProductID = F.ComponenteID
               AND C.DiscontinuedOn IS NULL
            INNER JOIN dbo.orgProduct AS R
                ON R.ProductID = F.ProductID
               AND R.DiscontinuedOn IS NULL
            WHERE C.Category1 = ?
              AND (? = '' OR F.Producto LIKE ?)
            """,
            (linea_limpia, texto, f'{texto}%'),
        )
        return [
            {
                'product_id': int(fila.get('ProductID') or 0),
                'producto': self._convertir_texto(fila.get('ProductName')),
                'unidad': self._convertir_texto(fila.get('Unit')) or 'KILO',
            }
            for fila in filas
        ]

    def buscar_base_sugerida_configuracion(
            self, linea: str, nombre_transformacion: str
    ) -> dict | None:
        nombre = str(nombre_transformacion or '').strip()
        linea_normalizada = self._nombre_producto_normalizado(linea)
        if len(nombre) < 3:
            return None
        formula_exacta = self.fetchall(
            f"""
            SELECT TOP 1
                F.ProductID AS ResultProductID,
                F.Producto AS ResultProduct,
                F.ComponenteID AS BaseProductID,
                F.Componente AS BaseProduct,
                ISNULL(P.Unit, 'KILO') AS Unit
            FROM {self._fuente_formulas} AS F
            INNER JOIN dbo.orgProduct AS P
                ON P.ProductID = F.ComponenteID
               AND P.DiscontinuedOn IS NULL
            WHERE F.Producto = ?
              AND P.Category1 = ?
            ORDER BY
                CAST(F.CantidadComp AS DECIMAL(18,6)) DESC,
                F.IDComp,
                F.ComponenteID
            """,
            (nombre, linea_normalizada),
        )
        if formula_exacta:
            fila = formula_exacta[0]
            return {
                'producto_resultante_id': fila.get('ResultProductID'),
                'producto_resultante': fila.get('ResultProduct'),
                'producto_base_id': fila.get('BaseProductID'),
                'producto_base': fila.get('BaseProduct'),
                'unidad': fila.get('Unit') or 'KILO',
            }

        productos_linea = self.fetchall(
            """
            SELECT ProductID, ProductName, Category2,
                   ISNULL(Unit, 'KILO') AS Unit
            FROM dbo.orgProduct
            WHERE DiscontinuedOn IS NULL
               AND Category1 = ?
              AND NULLIF(LTRIM(RTRIM(Category2)), '') IS NOT NULL
            """,
            (linea_normalizada,),
        )
        resultados_ordenados = sorted(
            (
                (
                    self._semejanza_nombre_producto(
                        nombre, str(producto.get('ProductName') or '')
                    ),
                    producto,
                )
                for producto in productos_linea
            ),
            key=lambda elemento: elemento[0],
            reverse=True,
        )
        if resultados_ordenados and resultados_ordenados[0][0] >= 0.60:
            resultado = resultados_ordenados[0][1]
            categoria_padre = resultado.get('Category2') or ''
            candidatos_base = []
            for producto in productos_linea:
                if int(str(producto.get('ProductID') or 0)) == int(
                    str(resultado.get('ProductID') or 0)
                ):
                    continue
                semejanza_categoria = self._semejanza_nombre_producto(
                    str(categoria_padre),
                    str(producto.get('ProductName') or ''),
                )
                semejanza_autorreferencia = self._semejanza_nombre_producto(
                    str(producto.get('Category2') or ''),
                    str(producto.get('ProductName') or ''),
                )
                palabras_padre = self._palabras_clave_producto(
                    str(categoria_padre)
                )
                palabras_producto = self._palabras_clave_producto(
                    str(producto.get('ProductName') or '')
                )
                if palabras_padre & palabras_producto:
                    candidatos_base.append((
                        semejanza_autorreferencia,
                        semejanza_categoria,
                        -int(str(producto.get('ProductID') or 0)),
                        producto,
                    ))
            if candidatos_base:
                candidatos_base.sort(
                    key=lambda elemento: elemento[:3], reverse=True
                )
                base = candidatos_base[0][3]
                return {
                    'producto_resultante_id': int(
                        str(resultado.get('ProductID') or 0)
                    ),
                    'producto_resultante': resultado['ProductName'],
                    'producto_base_id': int(
                        str(base.get('ProductID') or 0)
                    ),
                    'producto_base': base['ProductName'],
                    'unidad': base.get('Unit') or 'KILO',
                }

        filas = self.fetchall(
            """
            SELECT TOP 1
                Resultado.ProductID AS ResultProductID,
                Resultado.ProductName AS ResultProductName,
                Base.ProductID AS BaseProductID,
                Base.ProductName AS BaseProductName,
                ISNULL(Base.Unit, 'KILO') AS Unit
            FROM dbo.orgProduct AS Resultado
            CROSS APPLY
            (
                SELECT TOP 1
                    ProductoBase.ProductID,
                    ProductoBase.ProductName,
                    ProductoBase.Unit
                FROM dbo.orgProduct AS ProductoBase
                WHERE ProductoBase.DiscontinuedOn IS NULL
                  AND ProductoBase.ProductID <> Resultado.ProductID
                  AND UPPER(LTRIM(RTRIM(ISNULL(ProductoBase.Category1, '')))) =
                      UPPER(LTRIM(RTRIM(ISNULL(Resultado.Category1, ''))))
                  AND (
                        UPPER(LTRIM(RTRIM(ProductoBase.ProductName))) =
                            UPPER(LTRIM(RTRIM(Resultado.Category2)))
                        OR UPPER(LTRIM(RTRIM(ISNULL(ProductoBase.Category2, '')))) =
                            UPPER(LTRIM(RTRIM(Resultado.Category2)))
                      )
                ORDER BY
                    CASE WHEN UPPER(LTRIM(RTRIM(ProductoBase.ProductName))) =
                                   UPPER(LTRIM(RTRIM(Resultado.Category2)))
                         THEN 0 ELSE 1 END,
                    ProductoBase.ProductID
            ) AS Base
            WHERE Resultado.DiscontinuedOn IS NULL
              AND UPPER(LTRIM(RTRIM(ISNULL(Resultado.Category1, '')))) =
                  UPPER(LTRIM(RTRIM(?)))
              AND NULLIF(LTRIM(RTRIM(Resultado.Category2)), '') IS NOT NULL
              AND Resultado.ProductName LIKE '%' + ? + '%'
            ORDER BY
                CASE WHEN UPPER(LTRIM(RTRIM(Resultado.ProductName))) =
                           UPPER(LTRIM(RTRIM(?)))
                     THEN 0
                     WHEN UPPER(Resultado.ProductName) LIKE UPPER(?) + '%'
                     THEN 1 ELSE 2 END,
                Resultado.ProductName
            """,
            (str(linea).strip(), nombre, nombre, nombre),
        )
        if filas:
            fila = filas[0]
            return {
                'producto_resultante_id': fila.get('ResultProductID'),
                'producto_resultante': fila.get('ResultProductName'),
                'producto_base_id': fila.get('BaseProductID'),
                'producto_base': fila.get('BaseProductName'),
                'unidad': fila.get('Unit') or 'KILO',
            }

        palabras_buscadas = self._palabras_clave_producto(nombre)
        candidatos = self.fetchall(
            """
            SELECT
                ProductID,
                ProductName,
                Category2,
                ISNULL(Unit, 'KILO') AS Unit
            FROM dbo.orgProduct
            WHERE DiscontinuedOn IS NULL
              AND UPPER(LTRIM(RTRIM(ISNULL(Category1, '')))) =
                  UPPER(LTRIM(RTRIM(?)))
              AND NULLIF(LTRIM(RTRIM(Category2)), '') IS NOT NULL
            """,
            (str(linea).strip(),),
        )
        resultados_probables = []
        for candidato in candidatos:
            palabras_producto = self._palabras_clave_producto(
                str(candidato.get('ProductName') or '')
            )
            comunes = palabras_buscadas & palabras_producto
            cobertura = (
                len(comunes) / len(palabras_buscadas)
                if palabras_buscadas else 0
            )
            if comunes and cobertura >= 0.60:
                resultados_probables.append((
                    cobertura,
                    len(comunes),
                    -len(palabras_producto - palabras_buscadas),
                    -int(str(candidato.get('ProductID') or 0)),
                    candidato,
                ))
        if resultados_probables:
            resultados_probables.sort(
                key=lambda coincidencia: coincidencia[:4],
                reverse=True,
            )
            resultado = resultados_probables[0][4]
            producto_formula_id = self.buscar_producto_formula_relacionado(
                int(str(resultado.get('ProductID') or 0)),
                str(resultado.get('ProductName') or ''),
                linea,
            )
            if producto_formula_id:
                componentes_formula = (
                    self.buscar_formula_producto_configuracion(
                        int(str(producto_formula_id))
                    )
                )
                componentes_linea = [
                    componente for componente in componentes_formula
                    if str(componente.get('linea') or '').strip().upper() ==
                       str(linea).strip().upper()
                ]
                if componentes_linea:
                    base_formula = max(
                        componentes_linea,
                        key=lambda componente: float(
                            componente.get('cantidad') or 0
                        ),
                    )
                    return {
                        'producto_resultante_id': int(
                            str(resultado.get('ProductID') or 0)
                        ),
                        'producto_resultante': resultado['ProductName'],
                        'producto_base_id': int(
                            str(base_formula.get('productID') or 0)
                        ),
                        'productBase': base_formula['producto'],
                        'unidad': base_formula.get('unidad') or 'KILO',
                    }
        bases_probables = []
        for candidato in candidatos:
            palabras_producto = self._palabras_clave_producto(
                str(candidato.get('ProductName') or '')
            )
            palabras_categoria = self._palabras_clave_producto(
                str(candidato.get('Category2') or '')
            )
            comunes_nombre = palabras_buscadas & palabras_producto
            if not comunes_nombre or not palabras_producto:
                continue
            semejanza_base = (
                len(palabras_producto & palabras_categoria) /
                len(palabras_producto | palabras_categoria)
                if palabras_categoria else 0
            )
            if semejanza_base < 0.60:
                continue
            bases_probables.append((
                semejanza_base,
                len(comunes_nombre),
                -len(palabras_producto - palabras_buscadas),
                -int(str(candidato.get('ProductID') or 0)),
                candidato,
            ))
        if not bases_probables:
            return None
        bases_probables.sort(
            key=lambda coincidencia: coincidencia[:4],
            reverse=True,
        )
        base = bases_probables[0][4]
        return {
            'producto_resultante_id': None,
            'producto_resultante': nombre,
            'producto_base_id': int(str(base.get('ProductID') or 0)),
            'producto_base': base['ProductName'],
            'unidad': base.get('unidad') or 'KILO',
        }

    def buscar_componentes_configuracion(self, linea: str) -> list[dict]:
        linea_normalizada = self._nombre_producto_normalizado(linea)
        productos_linea = self.fetchall(
            """
            SELECT TOP (500)
                P.ProductID AS ProductID,
                P.ProductName AS ProductName,
                ISNULL(P.Unit, 'KILO') AS Unit,
                CAST(0 AS DECIMAL(18,8)) AS QuantityPerKilo
            FROM dbo.orgProduct AS P
            WHERE P.DiscontinuedOn IS NULL
              AND P.Category1 = ?
            """,
            (linea_normalizada,),
        )
        productos_formula = self.fetchall(
            f"""
            WITH FormulaEvaluada AS
            (
                SELECT
                    F.ProductID,
                    F.ComponenteID,
                    CAST(F.CantidadComp AS DECIMAL(18,8)) AS Quantity,
                    FormulaBase.BaseQuantity
                FROM {self._fuente_formulas} AS F
                CROSS APPLY
                (
                    SELECT TOP (1)
                        CAST(BF.CantidadComp AS DECIMAL(18,8)) AS BaseQuantity
                    FROM {self._fuente_formulas} AS BF
                    INNER JOIN dbo.orgProduct AS Base
                        ON Base.ProductID = BF.ComponenteID
                       AND Base.DiscontinuedOn IS NULL
                    WHERE BF.ProductID = F.ProductID
                      AND Base.Category1 = ?
                    ORDER BY BF.IDComp
                ) AS FormulaBase
            ),
            Proporciones AS
            (
                SELECT
                    ComponenteID AS ProductID,
                    CAST(AVG(
                        Quantity / NULLIF(BaseQuantity, 0)
                    ) AS DECIMAL(18,8)) AS QuantityPerKilo
                FROM FormulaEvaluada
                WHERE Quantity > 0 AND BaseQuantity > 0
                GROUP BY ComponenteID
            )
            SELECT TOP (500)
                P.ProductID AS ProductID,
                P.ProductName AS ProductName,
                ISNULL(P.Unit, 'KILO') AS Unit,
                ISNULL(Proporcion.QuantityPerKilo, 0) AS QuantityPerKilo
            FROM dbo.orgProduct AS P
            INNER JOIN Proporciones AS Proporcion
                ON Proporcion.ProductID = P.ProductID
            WHERE P.DiscontinuedOn IS NULL
            """,
            (linea_normalizada,),
        )
        por_producto = {}
        for fila in productos_linea + productos_formula:
            producto = {
                'product_id': int(fila.get('ProductID') or 0),
                'producto': self._convertir_texto(fila.get('ProductName')),
                'unidad': self._convertir_texto(fila.get('Unit')) or 'KILO',
                'cantidad_por_kilo': float(
                    fila.get('QuantityPerKilo') or 0
                ),
            }
            por_producto[producto['product_id']] = producto
        return sorted(
            por_producto.values(),
            key=lambda elemento: self._convertir_texto(
                elemento.get('producto')
            ),
        )[:500]

    def buscar_formula_producto_configuracion(
            self, producto_id: int
    ) -> list[dict]:
        formula_id = int(producto_id)
        tiene_formula_directa = self.fetchone(
            f"""
            SELECT TOP 1 ProductID
            FROM {self._fuente_formulas}
            WHERE ProductID = ?
            """,
            (formula_id,),
        )
        if not tiene_formula_directa:
            producto = self.fetchall(
                """
                SELECT TOP 1 ProductName, ISNULL(Category1, '') AS Category1
                FROM dbo.orgProduct
                WHERE ProductID = ? AND DiscontinuedOn IS NULL
                """,
                (formula_id,),
            )
            if not producto:
                return []
            formula_id = self.buscar_producto_formula_relacionado(
                formula_id,
                producto[0]['ProductName'],
                producto[0]['Category1'],
            )
            if not formula_id:
                return []

        filas = self.fetchall(
            f"""
            SELECT
                F.ComponenteID AS ProductID,
                F.Componente AS ProductName,
                CAST(F.CantidadComp AS DECIMAL(18,6)) AS Quantity,
                ISNULL(P.Unit, 'KILO') AS Unit,
                ISNULL(P.Category1, '') AS ProductLine
            FROM {self._fuente_formulas} AS F
            INNER JOIN dbo.orgProduct AS P
                ON P.ProductID = F.ComponenteID
               AND P.DiscontinuedOn IS NULL
            WHERE F.ProductID = ?
            ORDER BY F.IDComp, F.ComponenteID
            """,
            (formula_id,),
        )
        return [
            {
                'product_id': int(fila.get('ProductID') or 0),
                'producto': self._convertir_texto(fila.get('ProductName')),
                'cantidad': float(fila.get('Quantity') or 0),
                'unidad': self._convertir_texto(fila.get('Unit')) or 'KILO',
                'linea': self._convertir_texto(fila.get('ProductLine')),
            }
            for fila in filas
        ]

    def buscar_formulas_relacionadas_configuracion(
            self, producto_id: int
    ) -> list[dict]:
        formulas = self.fetchall(
            f"""
            SELECT DISTINCT
                F.ProductID AS FormulaID,
                F.Producto AS FormulaName
            FROM {self._fuente_formulas} AS F
            INNER JOIN dbo.orgProduct AS Resultado
                ON Resultado.ProductID = F.ProductID
               AND Resultado.DiscontinuedOn IS NULL
            WHERE F.ProductID = ?
            ORDER BY F.Producto, F.ProductID
            """,
            (int(producto_id),),
        )
        formulas = [
            {
                'formula_id': int(fila.get('FormulaID') or 0),
                'formula': self._convertir_texto(fila.get('FormulaName')),
            }
            for fila in formulas
        ]
        if not formulas:
            producto = self.fetchall(
                """
                SELECT TOP 1
                    ProductName,
                    ISNULL(Category1, '') AS Category1
                FROM dbo.orgProduct
                WHERE ProductID = ?
                  AND DiscontinuedOn IS NULL
                """,
                (int(producto_id),),
            )
            if producto:
                formula_id = self.buscar_producto_formula_relacionado(
                    int(producto_id),
                    producto[0]['ProductName'],
                    producto[0]['Category1'],
                )
                if formula_id:
                    nombre_formula = self.fetchone(
                        f"""
                        SELECT TOP 1 Producto
                        FROM {self._fuente_formulas}
                        WHERE ProductID = ?
                        """,
                        (int(formula_id),),
                    )
                    formulas = [{
                        'formula_id': int(formula_id),
                        'formula': (
                                nombre_formula
                                or producto[0]['ProductName']
                        ),
                    }]

        return [
            {
                **formula,
                'componentes': self.buscar_formula_producto_configuracion(
                    int(str(formula.get('formula_id') or 0))
                ),
            }
            for formula in formulas
        ]

    def listar_componentes_formulas_configuracion(
            self, producto_id: int
    ) -> list[dict]:
        return [
            {
                **componente,
                'formula_id': int(formula['formula_id']),
                'formula': self._convertir_texto(formula['formula']),
            }
            for formula in self.buscar_formulas_relacionadas_configuracion(
                producto_id
            )
            for componente in formula['componentes']
        ]

    def eliminar_configuraciones_incompletas(
            self,
            transformaciones_ids: list[int],
    ) -> None:
        """Revierte configuraciones nuevas cuando falla un guardado por lote."""
        ids = sorted({
            int(transformacion_id)
            for transformacion_id in transformaciones_ids
            if int(transformacion_id) > 0
        })
        if not ids:
            return
        marcadores = ', '.join('?' for _ in ids)
        parametros = tuple(ids) * 4
        self.fetchone(
            f"""
            BEGIN TRANSACTION;
            BEGIN TRY
                DELETE A
                FROM dbo.ModuloCarnicoConfiguracionAuditoria AS A
                WHERE A.configuracion_id IN ({marcadores});
                DELETE C
                FROM dbo.TransformacionesUsuarioComponente AS C
                WHERE C.id_transformacion_usuario IN ({marcadores});
                DELETE D
                FROM dbo.TransformacionesUsuarioDetalle AS D
                WHERE D.id_transformacion_usuario IN ({marcadores});
                DELETE T
                FROM dbo.TransformacionesUsuario AS T
                WHERE T.id_transformacion_usuario IN ({marcadores});
                COMMIT TRANSACTION;
                SELECT 1;
            END TRY
            BEGIN CATCH
                IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
                THROW;
            END CATCH
            """,
            parametros,
        )
    def crear_configuracion_transformacion(
            self,
            datos,
            usuario_id: int,
            usuario_nombre: str = 'Usuario',
    ) -> int:
        self.asegurar_proveedor_transformaciones_usuario()
        linea_normalizada = self._nombre_producto_normalizado(datos.linea)
        nombre_normalizado = str(datos.nombre or '').strip()
        producto_resultante_id = self.fetchone(
            f"""
            SELECT TOP 1 F.ProductID
            FROM {self._fuente_formulas} AS F
                INNER JOIN dbo.orgProduct AS Componente
                    ON Componente.ProductID = F.ComponenteID
                   AND Componente.DiscontinuedOn IS NULL
                INNER JOIN dbo.orgProduct AS Resultado
                    ON Resultado.ProductID = F.ProductID
                   AND Resultado.DiscontinuedOn IS NULL
                WHERE Componente.Category1 = ?
                  AND F.Producto = ?
            """,
            (linea_normalizada, nombre_normalizado),
        )
        if not producto_resultante_id:
            producto_resultante_id = self.fetchone(
                """
                SELECT TOP 1 ProductID
                FROM dbo.orgProduct
                WHERE DiscontinuedOn IS NULL
                  AND UPPER(LTRIM(RTRIM(ISNULL(Category1, '')))) =
                      UPPER(LTRIM(RTRIM(?)))
                  AND UPPER(LTRIM(RTRIM(ProductName))) =
                      UPPER(LTRIM(RTRIM(?)))
                ORDER BY ProductID
                """,
                (datos.linea, datos.nombre),
            )
        componentes_ids = [
            int(componente.producto_id)
            for componente in datos.componentes
        ]
        marcadores_componentes = ', '.join('?' for _ in componentes_ids)
        marcados_base = [
            componente
            for componente in datos.componentes
            if componente.es_base
        ]
        producto_base_id = int(marcados_base[0].producto_id)
        productos_validos = self.fetchall(
            f"""
            SELECT ProductID, ISNULL(Category1, '') AS Category1
            FROM dbo.orgProduct
            WHERE DiscontinuedOn IS NULL
              AND ProductID IN ({marcadores_componentes})
            """,
            tuple(componentes_ids),
        )
        if len(productos_validos) != len(componentes_ids):
            raise ValueError('Uno de los insumos no existe o está inactivo en el sistema.')
        producto_base = next(
            producto for producto in productos_validos
            if int(producto['ProductID']) == producto_base_id
        )
        if (
                str(producto_base.get('Category1') or '').strip().upper()
                != datos.linea.strip().upper()
        ):
            raise ValueError(
                'El componente marcado como base no pertenece a la línea.'
            )
        if not producto_resultante_id:
            sugerencia = self.buscar_base_sugerida_configuracion(
                datos.linea, datos.nombre
            )
            producto_resultante_id = (
                sugerencia.get('producto_resultante_id')
                if sugerencia else None
            )
        producto_resultante_id = self._convertir_entero(
            producto_resultante_id,
            producto_base_id,
        )
        if self.fetchone(
                """SELECT TOP 1 T.id_transformacion_usuario
                   FROM dbo.TransformacionesUsuario T
                   INNER JOIN dbo.orgProduct Base
                     ON Base.ProductID=T.producto_origen
                   WHERE T.activa=1
                     AND T.nombre_transformacion
                     AND Base.Category 1""",
                (datos.nombre, datos.linea),
        ):
            raise ValueError(
                'Ya existe una configuración activa con ese nombre en la línea.'
            )

        componentes = [
            {
                'product_id': int(componente.producto_id),
                'cantidad': float(componente.cantidad),
                'unidad': componente.unidad,
                'es_base': bool(componente.es_base),
                'orden': orden,
            }
            for orden, componente in enumerate(datos.componentes, start=1)
        ]
        valores_componentes = ', '.join(
            '(?, ?, ?, ?, ?)' for _ in componentes
        )
        parametros_componentes = tuple(
            valor
            for componente in componentes
            for valor in (
                componente['productID'],
                componente['cantidad'],
                componente['unidad'],
                int(componente['es_base']),
                componente['orden'],
            )
        )
        cantidad_resultante = round(
            float(datos.cantidad_base) *
            (1 - float(datos.porcentaje_merma) / 100),
            3,
        )
        transformacion_id = self._convertir_entero(self.fetchone(
            f"""
            BEGIN TRANSACTION;
            BEGIN TRY
                INSERT dbo.TransformacionesUsuario
                    (nombre_transformacion, producto_origen, producto_formula,
                     cantidad_base, porcentaje_merma, proveedorID, usuario_creacion,
                     activa, observaciones)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?);
                DECLARE @id INT=CONVERT(INT,SCOPE_IDENTITY());
                INSERT dbo.TransformacionesUsuarioDetalle
                    (id_transformacion_usuario, producto_resultante,
                     cantidad_resultante, unidad, participa_balance, orden, activa)
                VALUES (@id, ?, ?, 'KILO', 1, 1, 1);
                INSERT dbo.TransformacionesUsuarioComponente
                    (id_transformacion_usuario, producto_componente, cantidad,
                     unidad, es_producto_base, tipo_componente,
                     participa_balance, orden, activa)
                SELECT @id, productIS, cantidad, unidad, es_base,
                       IIF(es_base=1,'PRODUCTO_BASE','INSUMO'), es_base, orden, 1
                 FROM (VALUES {valores_componentes}) AS Componentes
                     (productID, cantidad, unidad, es_base, orden);
                COMMIT TRANSACTION;
                SELECT @id;
            END TRY
            BEGIN CATCH
                IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
                THROW;
            END CATCH
            """,
            (
                datos.nombre, producto_base_id,
                producto_resultante_id, float(datos.cantidad_base),
                float(datos.porcentaje_merma),
                None, int(usuario_id), datos.observaciones,
                producto_resultante_id,
                cantidad_resultante,
            ) + parametros_componentes,
        ))
        try:
            self.registrar_auditoria_configuracion(
                configuracion_id=transformacion_id,
                configuracion_nombre=datos.nombre,
                accion='CREAR',
                usuario_id=usuario_id,
                usuario_nombre=usuario_nombre,
                motivo=datos.motivo_auditoria,
                valores_nuevos={
                    'linea': datos.linea,
                    'nombre': datos.nombre,
                    'cantidad_base': float(datos.cantidad_base),
                    'porcentaje_merma': float(datos.porcentaje_merma),
                    'componentes': componentes,
                },
            )
        except Exception:
            self.eliminar_configuraciones_incompletas([transformacion_id])
            raise
        return transformacion_id


def obtener_base_datos() -> BaseDatos:
    return BaseDatos()
