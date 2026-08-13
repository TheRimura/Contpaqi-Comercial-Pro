import json
import os
import re
import unicodedata
from copy import deepcopy
from difflib import SequenceMatcher
from functools import cache
from platform import node
from threading import RLock
from time import monotonic

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

    def __init__(self):
        servidor = os.getenv('CAYAL_DB_SERVER', '').strip() or node()
        base_datos = (
            os.getenv('CAYAL_DB_NAME', '').strip()
            or AJUSTES_MODULO.nombre_base_datos
        )
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
        self._cache_resumen_historial: dict[
            tuple[str, str, str], tuple[float, dict[str, float | int]]
        ] = {}
        self._cache_paginas_historial: dict[
            tuple[int, int, str, str, str], tuple[float, dict]
        ] = {}
        self._bloqueo_cache_historial = RLock()
        self._bloqueo_estructura = RLock()
        self._tablas_modulo_verificadas = False
        self._tablas_relacion_verificadas = False
        self._tablas_configuracion_verificadas = False
        contexto = super().fetchall(
            """
            SELECT
                CONVERT(NVARCHAR(128), SERVERPROPERTY('MachineName'))
                    AS maquina,
                DB_NAME() AS base_datos,
                CONVERT(
                    NVARCHAR(128),
                    CONNECTIONPROPERTY('local_net_address')
                ) AS direccion_servidor
            """,
            (),
        )
        if not contexto:
            raise RuntimeError(
                'No fue posible verificar el destino de la base de datos.'
            )
        destino = contexto[0]
        direccion = str(destino.get('direccion_servidor') or '').strip()
        base_actual = str(destino.get('base_datos') or '').strip()
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
            key=lambda fila: str(fila.get('ItemValue') or ''),
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
        return self.fetchall(
            """
            WITH ProductosModulo AS
            (
                SELECT P.ProductID, P.Category1
                FROM dbo.orgProduct AS P
                INNER JOIN dbo.ModuloCarnicoProductoConfigurado AS M
                    ON M.product_id = P.ProductID
                   AND M.activo = 1
                WHERE UPPER(LTRIM(RTRIM(ISNULL(P.Category1, ''))))
                    IN ('CERDO', 'POLLO', 'RES LOCAL')
            ),
            RecetasPorLinea AS
            (
                SELECT
                    C.Category1,
                    COUNT(DISTINCT F.ProductID) AS total_recetas
                FROM dbo.zvwFormulasListasPCocinar AS F
                INNER JOIN ProductosModulo AS C
                    ON C.ProductID = F.ComponenteID
                INNER JOIN ProductosModulo AS R
                    ON R.ProductID = F.ProductID
                GROUP BY C.Category1
            )
            SELECT
                P.Category1,
                COUNT(*) AS total_productos,
                ISNULL(MAX(R.total_recetas), 0) AS total_recetas
            FROM ProductosModulo AS P
            LEFT JOIN RecetasPorLinea AS R ON R.Category1 = P.Category1
            GROUP BY P.Category1
            ORDER BY P.Category1
            """,
            (),
        )

    def listar_productos_base_transformacion(self, linea: str) -> list[dict]:
        self.asegurar_tablas_modulo_carnico()
        return self.fetchall(
            """
            SELECT
                P.Category2 AS producto_base,
                COALESCE(
                    MIN(CASE
                        WHEN UPPER(LTRIM(RTRIM(P.ProductName))) =
                             UPPER(LTRIM(RTRIM(P.Category2)))
                        THEN P.ProductID
                    END),
                    MIN(P.ProductID)
                ) AS product_id_base,
                COUNT(*) AS total_resultantes
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

    def listar_transformaciones_precargadas(self, linea: str) -> list[dict]:
        self.asegurar_tablas_modulo_carnico()
        self.asegurar_proveedor_transformaciones_usuario()
        return self.fetchall(
            """
            SELECT
                T.id_transformacion_usuario AS transformacion_id,
                T.nombre_transformacion,
                T.producto_origen AS producto_base_id,
                P.ProductName AS producto_base,
                P.Category1 AS linea,
                ISNULL(E.OfficialName, '') AS proveedor
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

    def listar_transformaciones_disponibles(self) -> list[dict]:
        self.asegurar_tablas_modulo_carnico()
        return self.fetchall(
            """
            SELECT
                P.ProductID AS transformacion_id,
                P.ProductName AS nombre_transformacion,
                Base.ProductID AS producto_base_id,
                P.Category2 AS producto_base,
                P.Category1 AS linea,
                CAST(CASE WHEN EXISTS
                (
                    SELECT 1
                    FROM dbo.zvwFormulasListasPCocinar AS Formula
                    WHERE Formula.ProductID = P.ProductID
                ) THEN 1 ELSE 0 END AS BIT) AS tiene_formula,
                CAST(1 AS BIT) AS origen_catalogo
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
        palabras = re.findall(r'[A-Z0-9]+', texto)
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
        return ' '.join(re.findall(r'[A-Z0-9]+', texto))

    @classmethod
    def _semejanza_nombre_producto(cls, esperado: str, candidato: str) -> float:
        nombre_esperado = cls._nombre_producto_normalizado(esperado)
        nombre_candidato = cls._nombre_producto_normalizado(candidato)
        if not nombre_esperado or not nombre_candidato:
            return 0.0
        palabras_esperadas = cls._palabras_clave_producto(nombre_esperado)
        palabras_candidatas = cls._palabras_clave_producto(nombre_candidato)
        coincidencia_texto = SequenceMatcher(
            None, nombre_esperado, nombre_candidato
        ).ratio()
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
            """
            SELECT TOP 1 ProductID
            FROM dbo.zvwFormulasListasPCocinar
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
            """
            SELECT DISTINCT F.ProductID, F.Producto
            FROM dbo.zvwFormulasListasPCocinar AS F
            WHERE EXISTS
            (
                SELECT 1
                FROM dbo.zvwFormulasListasPCocinar AS ComponenteFormula
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
            """
            SELECT TOP 1
                P.ProductID AS transformacion_id,
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
                FROM dbo.zvwFormulasListasPCocinar AS F
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
                  FROM dbo.zvwFormulasListasPCocinar AS Formula
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
            registro['producto_base_id'] = int(componente_base['product_id'])
            registro['producto_base'] = componente_base['producto']
        componentes = []
        base_en_formula = False
        for orden, componente in enumerate(componentes_formula, start=1):
            es_base = int(componente['product_id']) == int(registro['producto_base_id'])
            base_en_formula = base_en_formula or es_base
            componentes.append({
                'product_id': int(componente['product_id']),
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
            'transformacion_id': int(registro['transformacion_id']),
            'nombre_transformacion': registro['nombre_transformacion'],
            'producto_base_id': int(registro['producto_base_id']),
            'producto_base': registro['producto_base'],
            'linea': registro['linea'],
            'porcentaje_merma': AJUSTES_MODULO.merma_tecnica_porcentaje,
            'origen_catalogo': True,
            'resultantes': [{
                'product_id': int(registro['producto_resultante_id']),
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
                T.id_transformacion_usuario AS transformacion_id,
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
        detalle['resultantes'] = self.fetchall(
            """
            SELECT
                D.producto_resultante AS product_id,
                P.ProductName AS producto_resultante,
                D.cantidad_resultante AS cantidad,
                D.unidad
            FROM dbo.TransformacionesUsuarioDetalle AS D
            INNER JOIN dbo.orgProduct AS P
                ON P.ProductID = D.producto_resultante
            WHERE D.id_transformacion_usuario = ?
              AND D.activa = 1
            ORDER BY D.orden
            """,
            (int(transformacion_id),),
        )
        detalle['componentes'] = self.fetchall(
            """
            SELECT
                C.producto_componente AS product_id,
                P.ProductName AS producto,
                C.cantidad,
                C.unidad,
                C.es_producto_base,
                C.tipo_componente,
                C.orden
            FROM dbo.TransformacionesUsuarioComponente AS C
            INNER JOIN dbo.orgProduct AS P
                ON P.ProductID = C.producto_componente
            WHERE C.id_transformacion_usuario = ?
              AND C.activa = 1
            ORDER BY C.orden
            """,
            (int(transformacion_id),),
        )
        if not detalle['resultantes']:
            return None
        return detalle

    def listar_productos_resultantes_transformacion(
            self,
            linea: str,
            producto_base: str,
    ) -> list[dict]:
        return self.fetchall(
            """
            SELECT
                ProductID AS product_id,
                ProductName AS producto_resultante,
                Unit AS unidad
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
        relation_id = self.fetchone(
            """
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
                DECLARE @Insumos NVARCHAR(MAX) = ?;
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
                    FROM OPENJSON(@Insumos)
                    WITH
                    (
                        producto_id INT '$.producto_id',
                        cantidad FLOAT '$.cantidad'
                    );
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
            (
                json.dumps(insumos or [], ensure_ascii=False),
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
        clave_cache = (
            int(limite),
            int(pagina),
            fecha_desde.strip(),
            fecha_hasta.strip(),
            transformacion.strip().casefold(),
        )
        with self._bloqueo_cache_historial:
            pagina_cache = self._cache_paginas_historial.get(clave_cache)
            if pagina_cache and monotonic() - pagina_cache[0] < 15:
                return deepcopy(pagina_cache[1])
            resultado = self._consultar_historial_transformaciones(
                limite=limite,
                pagina=pagina,
                fecha_desde=fecha_desde,
                fecha_hasta=fecha_hasta,
                transformacion=transformacion,
            )
            self._cache_paginas_historial[clave_cache] = (
                monotonic(),
                resultado,
            )
            return deepcopy(resultado)

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
                    R.ERPUserID AS usuario_id,
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
                ISNULL(U.UserName, '') AS usuario,
                ISNULL(Empleado.OfficialName, '') AS tablajero,
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
            LEFT JOIN dbo.engUser AS U
                ON U.UserID = RF.usuario_id
            OUTER APPLY
            (
                SELECT TOP 1 EMP.OfficialName
                FROM dbo.zvwEmpleadosCayalMenu AS EMP
                WHERE EMP.UserID = RF.tablajero_id
                ORDER BY EMP.OfficialName
            ) AS Empleado
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
        patron_rango = re.compile(
            r"\s*\.?\s*1\s*\(\s*\d+\s*(?:-\s*\d+|\+)\s*\)\s*$",
            re.IGNORECASE,
        )
        total_registros = int(
            filas[0].get('total_registros', 0) if filas else 0
        )
        for fila in filas:
            fila.pop('total_registros', None)
            fila['producto_base'] = patron_rango.sub(
                '', str(fila.get('producto_base') or '')
            ).strip()
            fila['producto_resultante'] = patron_rango.sub(
                '', str(fila.get('producto_resultante') or '')
            ).strip()
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
        clave_cache = (
            fecha_desde.strip(),
            fecha_hasta.strip(),
            transformacion.strip().casefold(),
        )
        resumen_cache = self._cache_resumen_historial.get(clave_cache)
        if resumen_cache and monotonic() - resumen_cache[0] < 60:
            return dict(resumen_cache[1])
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
        self._cache_resumen_historial[clave_cache] = (monotonic(), resumen)
        return dict(resumen)

    def invalidar_cache_historial(self) -> None:
        with self._bloqueo_cache_historial:
            self._cache_resumen_historial.clear()
            self._cache_paginas_historial.clear()

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
                    ISNULL(U.UserName, '') AS usuario,
                    ISNULL(Empleado.OfficialName, '') AS tablajero
                FROM dbo.docDocumentWarehouseRelation AS R
                INNER JOIN dbo.docDocument AS S
                    ON S.DocumentID = R.SourceDocumentID AND S.ModuleID = 203
                INNER JOIN dbo.docDocument AS E
                    ON E.DocumentID = R.DestinationDocumentID AND E.ModuleID = 202
                LEFT JOIN dbo.engUser AS U ON U.UserID = R.ERPUserID
                OUTER APPLY
                (
                    SELECT TOP 1 EMP.OfficialName
                    FROM dbo.zvwEmpleadosCayalMenu AS EMP
                    WHERE EMP.UserID = R.PhysicalUserID
                    ORDER BY EMP.OfficialName
                ) AS Empleado
                WHERE S.DeletedOn IS NULL
                  AND E.DeletedOn IS NULL
                  AND TRY_CONVERT(INT, S.CustomCbo) = 2
                  AND TRY_CONVERT(INT, E.CustomCbo) = 5
                ORDER BY R.CreatedOn DESC, R.DocumentWarehouseRelationID DESC
            )
            SELECT
                R.relacion_id, R.fecha_hora, R.folio_salida, R.folio_entrada,
                R.usuario, R.tablajero,
                ? AS tipo_documento,
                CASE WHEN ? = 'SALIDA' THEN R.folio_salida ELSE R.folio_entrada END
                    AS folio_documento,
                DI.DocumentItemID AS partida_id,
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
                -orden.get(str(fila.get('tipo_documento')), 9),
                -int(fila.get('partida_id') or 0),
            ),
            reverse=True,
        )
        for fila in registros:
            fila.pop('partida_id', None)
        return registros

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
                ISNULL(U.UserName, '') AS usuario,
                ISNULL(Empleado.OfficialName, '') AS tablajero
            FROM dbo.docDocumentWarehouseRelation AS R
            INNER JOIN dbo.docDocument AS S
                ON S.DocumentID = R.SourceDocumentID
            INNER JOIN dbo.docDocument AS E
                ON E.DocumentID = R.DestinationDocumentID
            LEFT JOIN dbo.engUser AS U
                ON U.UserID = R.ERPUserID
            OUTER APPLY
            (
                SELECT TOP 1 EMP.OfficialName
                FROM dbo.zvwEmpleadosCayalMenu AS EMP
                WHERE EMP.UserID = R.PhysicalUserID
                ORDER BY EMP.OfficialName
            ) AS Empleado
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
        """
        Consulta directamente las partidas.

        No llama a buscar_partidas_documento() del paquete para evitar que un
        parámetro de un elemento sea enviado sin la coma de la tupla.
        """
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

        return int(valor or 0)

    # -------------------------- MODULO CARNICO -------------------------
    def asegurar_tablas_modulo_carnico(self) -> None:
        if self._tablas_modulo_verificadas:
            return
        with self._bloqueo_estructura:
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
        with self._bloqueo_estructura:
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
        return int(valor or 0)

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

    # ---------------- CONFIGURACION DE TRANSFORMACIONES ----------------
    def asegurar_proveedor_transformaciones_usuario(self) -> None:
        if self._tablas_configuracion_verificadas:
            return
        with self._bloqueo_estructura:
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
        return int(self.fetchone(
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
                (
                    json.dumps(valores_anteriores, ensure_ascii=False)
                    if valores_anteriores is not None else None
                ),
                (
                    json.dumps(valores_nuevos, ensure_ascii=False)
                    if valores_nuevos is not None else None
                ),
            ),
        ) or 0)

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
        for registro in registros:
            for campo in (
                    'valores_anteriores_json',
                    'valores_nuevos_json',
            ):
                texto = registro.pop(campo, None)
                try:
                    registro[campo.removesuffix('_json')] = (
                        json.loads(texto) if texto else None
                    )
                except (TypeError, ValueError):
                    registro[campo.removesuffix('_json')] = None
        return registros

    def buscar_productos_base_configuracion(
            self, linea: str, termino: str = ''
    ) -> list[dict]:
        self.asegurar_tablas_modulo_carnico()
        texto = str(termino or '').strip()
        parametros = (str(linea).strip(), texto, texto)
        configuraciones = self.fetchall(
            """
            SELECT
                -T.id_transformacion_usuario AS product_id,
                T.nombre_transformacion AS producto,
                CAST('TRANSFORMACION' AS NVARCHAR(50)) AS unidad,
                T.fecha_creacion,
                CAST(CASE WHEN T.fecha_creacion >= DATEADD(DAY, -30, GETDATE())
                     THEN 1 ELSE 0 END AS BIT) AS es_reciente,
                CAST(1 AS BIT) AS tiene_receta,
                CAST(1 AS BIT) AS es_configuracion,
                T.id_transformacion_usuario AS transformacion_id
            FROM dbo.TransformacionesUsuario AS T
            INNER JOIN dbo.orgProduct AS Base
                ON Base.ProductID = T.producto_origen
            INNER JOIN dbo.ModuloCarnicoProductoConfigurado AS CatalogoModulo
                ON CatalogoModulo.product_id = Base.ProductID
               AND CatalogoModulo.activo = 1
            WHERE T.activa = 1
              AND UPPER(LTRIM(RTRIM(ISNULL(Base.Category1, '')))) =
                  UPPER(LTRIM(RTRIM(?)))
              AND (? = '' OR T.nombre_transformacion LIKE '%' + ? + '%')
            ORDER BY T.nombre_transformacion
            """,
            parametros,
        )
        productos = self.fetchall(
            """
            SELECT
                P.ProductID AS product_id,
                P.ProductName AS producto,
                CAST(ISNULL(P.Unit, 'KILO') AS NVARCHAR(50)) AS unidad,
                P.CreatedOn AS fecha_creacion,
                CAST(CASE WHEN P.CreatedOn >= DATEADD(DAY, -30, GETDATE())
                     THEN 1 ELSE 0 END AS BIT) AS es_reciente,
                CAST(CASE WHEN EXISTS
                (
                    SELECT 1 FROM dbo.zvwFormulasListasPCocinar AS F
                    WHERE F.ComponenteID = P.ProductID
                ) THEN 1 ELSE 0 END AS BIT) AS tiene_receta,
                CAST(0 AS BIT) AS es_configuracion,
                CAST(NULL AS INT) AS transformacion_id
            FROM dbo.orgProduct AS P
            INNER JOIN dbo.ModuloCarnicoProductoConfigurado AS CatalogoModulo
                ON CatalogoModulo.product_id = P.ProductID
               AND CatalogoModulo.activo = 1
            WHERE UPPER(LTRIM(RTRIM(ISNULL(P.Category1, '')))) =
                  UPPER(LTRIM(RTRIM(?)))
              AND (? = '' OR P.ProductName LIKE '%' + ? + '%')
            ORDER BY P.ProductName
            """,
            parametros,
        )
        return (configuraciones + productos)[:200]

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
                WHERE product_id = ?
                  AND activo = 1;

                SELECT CASE WHEN @@ROWCOUNT > 0 THEN ? ELSE NULL END;
                """,
                (
                    int(usuario_id), int(producto_id), int(producto_id),
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
        texto = str(termino or '').strip()
        return self.fetchall(
            """
            SELECT TOP (100)
                F.ProductID AS product_id,
                MAX(F.Producto) AS producto,
                MAX(ISNULL(R.Unit, 'KILO')) AS unidad
            FROM dbo.zvwFormulasListasPCocinar AS F
            INNER JOIN dbo.orgProduct AS C
                ON C.ProductID = F.ComponenteID
               AND C.DiscontinuedOn IS NULL
            LEFT JOIN dbo.orgProduct AS R ON R.ProductID = F.ProductID
            WHERE UPPER(LTRIM(RTRIM(ISNULL(C.Category1, '')))) =
                  UPPER(LTRIM(RTRIM(?)))
              AND (? = '' OR F.Producto LIKE '%' + ? + '%')
            GROUP BY F.ProductID
            ORDER BY MAX(F.Producto)
            """,
            (str(linea).strip(), texto, texto),
        )

    def buscar_base_sugerida_configuracion(
            self, linea: str, nombre_transformacion: str
    ) -> dict | None:
        nombre = str(nombre_transformacion or '').strip()
        if len(nombre) < 3:
            return None
        formula_exacta = self.fetchall(
            """
            SELECT TOP 1
                F.ProductID AS producto_resultante_id,
                F.Producto AS producto_resultante,
                F.ComponenteID AS producto_base_id,
                F.Componente AS producto_base,
                ISNULL(P.Unit, 'KILO') AS unidad
            FROM dbo.zvwFormulasListasPCocinar AS F
            INNER JOIN dbo.orgProduct AS P
                ON P.ProductID = F.ComponenteID
               AND P.DiscontinuedOn IS NULL
            WHERE UPPER(LTRIM(RTRIM(F.Producto))) =
                  UPPER(LTRIM(RTRIM(?)))
              AND UPPER(LTRIM(RTRIM(ISNULL(P.Category1, '')))) =
                  UPPER(LTRIM(RTRIM(?)))
            ORDER BY
                CAST(F.CantidadComp AS DECIMAL(18,6)) DESC,
                F.IDComp,
                F.ComponenteID
            """,
            (nombre, str(linea).strip()),
        )
        if formula_exacta:
            return formula_exacta[0]

        # Category1 define la línea, Category2 el producto padre y
        # ProductName el producto resultante. Primero localizamos el resultado
        # tolerando errores pequeños de captura y después resolvemos su padre.
        productos_linea = self.fetchall(
            """
            SELECT ProductID, ProductName, Category2,
                   ISNULL(Unit, 'KILO') AS unidad
            FROM dbo.orgProduct
            WHERE DiscontinuedOn IS NULL
              AND UPPER(LTRIM(RTRIM(ISNULL(Category1, '')))) =
                  UPPER(LTRIM(RTRIM(?)))
              AND NULLIF(LTRIM(RTRIM(Category2)), '') IS NOT NULL
            """,
            (str(linea).strip(),),
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
                    'unidad': base.get('unidad') or 'KILO',
                }

        filas = self.fetchall(
            """
            SELECT TOP 1
                Resultado.ProductID AS producto_resultante_id,
                Resultado.ProductName AS producto_resultante,
                Base.ProductID AS producto_base_id,
                Base.ProductName AS producto_base,
                ISNULL(Base.Unit, 'KILO') AS unidad
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
            return filas[0]

        palabras_buscadas = self._palabras_clave_producto(nombre)
        candidatos = self.fetchall(
            """
            SELECT
                ProductID,
                ProductName,
                Category2,
                ISNULL(Unit, 'KILO') AS unidad
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
                            str(base_formula.get('product_id') or 0)
                        ),
                        'producto_base': base_formula['producto'],
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
        linea_normalizada = str(linea).strip().upper()
        productos_linea = self.fetchall(
            """
            SELECT TOP (500)
                P.ProductID AS product_id,
                P.ProductName AS producto,
                ISNULL(P.Unit, 'KILO') AS unidad,
                CAST(0 AS DECIMAL(18,8)) AS cantidad_por_kilo
            FROM dbo.orgProduct AS P
            WHERE P.DiscontinuedOn IS NULL
              AND P.Category1 = ?
            ORDER BY P.ProductName
            """,
            (linea_normalizada,),
        )
        productos_formula = self.fetchall(
            """
            WITH FormulaEvaluada AS
            (
                SELECT
                    F.ProductID,
                    F.ComponenteID,
                    CAST(F.CantidadComp AS DECIMAL(18,8)) AS cantidad,
                    MAX(CASE WHEN Base.Category1 = ?
                        THEN CAST(F.CantidadComp AS DECIMAL(18,8))
                    END) OVER (PARTITION BY F.ProductID) AS cantidad_base
                FROM dbo.zvwFormulasListasPCocinar AS F
                INNER JOIN dbo.orgProduct AS Base
                    ON Base.ProductID = F.ComponenteID
                   AND Base.DiscontinuedOn IS NULL
            ),
            Proporciones AS
            (
                SELECT
                    ComponenteID AS producto_id,
                    CAST(AVG(
                        cantidad / NULLIF(cantidad_base, 0)
                    ) AS DECIMAL(18,8)) AS cantidad_por_kilo
                FROM FormulaEvaluada
                WHERE cantidad > 0 AND cantidad_base > 0
                GROUP BY ComponenteID
            )
            SELECT TOP (500)
                P.ProductID AS product_id,
                P.ProductName AS producto,
                ISNULL(P.Unit, 'KILO') AS unidad,
                ISNULL(Proporcion.cantidad_por_kilo, 0) AS cantidad_por_kilo
            FROM dbo.orgProduct AS P
            INNER JOIN Proporciones AS Proporcion
                ON Proporcion.producto_id = P.ProductID
            WHERE P.DiscontinuedOn IS NULL
            ORDER BY P.ProductName
            """,
            (linea_normalizada,),
        )
        por_producto = {
            int(producto['product_id']): producto
            for producto in productos_linea
        }
        for producto in productos_formula:
            por_producto[int(producto['product_id'])] = producto
        return sorted(
            por_producto.values(),
            key=lambda producto: str(producto.get('producto') or ''),
        )[:500]

    def buscar_formula_producto_configuracion(
            self, producto_id: int
    ) -> list[dict]:
        formula_id = int(producto_id)
        tiene_formula_directa = self.fetchone(
            """
            SELECT TOP 1 ProductID
            FROM dbo.zvwFormulasListasPCocinar
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

        return self.fetchall(
            """
            SELECT
                F.ComponenteID AS product_id,
                F.Componente AS producto,
                CAST(F.CantidadComp AS DECIMAL(18,6)) AS cantidad,
                ISNULL(P.Unit, 'KILO') AS unidad,
                ISNULL(P.Category1, '') AS linea
            FROM dbo.zvwFormulasListasPCocinar AS F
            INNER JOIN dbo.orgProduct AS P
                ON P.ProductID = F.ComponenteID
               AND P.DiscontinuedOn IS NULL
            WHERE F.ProductID = ?
            ORDER BY F.IDComp, F.ComponenteID
            """,
            (formula_id,),
        )

    def buscar_formulas_relacionadas_configuracion(
            self, producto_id: int
    ) -> list[dict]:
        formulas = self.fetchall(
            """
            SELECT DISTINCT
                F.ProductID AS formula_id,
                F.Producto AS formula
            FROM dbo.zvwFormulasListasPCocinar AS F
            INNER JOIN dbo.orgProduct AS Resultado
                ON Resultado.ProductID = F.ProductID
               AND Resultado.DiscontinuedOn IS NULL
            WHERE F.ProductID = ?
            ORDER BY F.Producto, F.ProductID
            """,
            (int(producto_id),),
        )
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
                        """
                        SELECT TOP 1 Producto
                        FROM dbo.zvwFormulasListasPCocinar
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
        ids_json = json.dumps(ids)
        self.fetchone(
            """
            BEGIN TRANSACTION;
            BEGIN TRY
                DELETE A
                FROM dbo.ModuloCarnicoConfiguracionAuditoria AS A
                WHERE A.configuracion_id IN (
                    SELECT TRY_CONVERT(INT, [value]) FROM OPENJSON(?)
                );
                DELETE C
                FROM dbo.TransformacionesUsuarioComponente AS C
                WHERE C.id_transformacion_usuario IN (
                    SELECT TRY_CONVERT(INT, [value]) FROM OPENJSON(?)
                );
                DELETE D
                FROM dbo.TransformacionesUsuarioDetalle AS D
                WHERE D.id_transformacion_usuario IN (
                    SELECT TRY_CONVERT(INT, [value]) FROM OPENJSON(?)
                );
                DELETE T
                FROM dbo.TransformacionesUsuario AS T
                WHERE T.id_transformacion_usuario IN (
                    SELECT TRY_CONVERT(INT, [value]) FROM OPENJSON(?)
                );
                COMMIT TRANSACTION;
                SELECT 1;
            END TRY
            BEGIN CATCH
                IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
                THROW;
            END CATCH
            """,
            (ids_json, ids_json, ids_json, ids_json),
        )
    def crear_configuracion_transformacion(
            self,
            datos,
            usuario_id: int,
            usuario_nombre: str = 'Usuario',
    ) -> int:
        self.asegurar_proveedor_transformaciones_usuario()
        producto_resultante_id = self.fetchone(
            """
            SELECT TOP 1 F.ProductID
            FROM dbo.zvwFormulasListasPCocinar AS F
                INNER JOIN dbo.orgProduct AS Componente
                    ON Componente.ProductID = F.ComponenteID
                   AND Componente.DiscontinuedOn IS NULL
                INNER JOIN dbo.orgProduct AS Resultado
                    ON Resultado.ProductID = F.ProductID
                   AND Resultado.DiscontinuedOn IS NULL
                WHERE UPPER(LTRIM(RTRIM(ISNULL(Componente.Category1, '')))) =
                      UPPER(LTRIM(RTRIM(?)))
                  AND UPPER(LTRIM(RTRIM(F.Producto))) =
                      UPPER(LTRIM(RTRIM(?)))
            GROUP BY F.ProductID
            ORDER BY F.ProductID
            """,
            (datos.linea, datos.nombre),
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
        marcados_base = [
            componente
            for componente in datos.componentes
            if componente.es_base
        ]
        producto_base_id = int(marcados_base[0].producto_id)
        productos_validos = self.fetchall(
            """
            SELECT ProductID, ISNULL(Category1, '') AS Category1
            FROM dbo.orgProduct
            WHERE DiscontinuedOn IS NULL
              AND ProductID IN (
                  SELECT TRY_CONVERT(INT, [value]) FROM OPENJSON(?)
              )
            """,
            (json.dumps(componentes_ids),),
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
        producto_resultante_id = int(
            str(producto_resultante_id or producto_base_id)
        )
        if self.fetchone(
                """SELECT TOP 1 T.id_transformacion_usuario
                   FROM dbo.TransformacionesUsuario T
                   INNER JOIN dbo.orgProduct Base
                     ON Base.ProductID=T.producto_origen
                   WHERE T.activa=1
                     AND UPPER(LTRIM(RTRIM(T.nombre_transformacion))) =
                         UPPER(LTRIM(RTRIM(?)))
                     AND UPPER(LTRIM(RTRIM(ISNULL(Base.Category1, '')))) =
                         UPPER(LTRIM(RTRIM(?)))""",
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
        cantidad_resultante = round(
            float(datos.cantidad_base) *
            (1 - float(datos.porcentaje_merma) / 100),
            3,
        )
        transformacion_id = int(self.fetchone(
            """
            BEGIN TRANSACTION;
            BEGIN TRY
                INSERT dbo.TransformacionesUsuario
                    (nombre_transformacion, producto_origen, producto_formula,
                     cantidad_base, porcentaje_merma, proveedor_id, usuario_creacion,
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
                SELECT @id, product_id, cantidad, unidad, es_base,
                       IIF(es_base=1,'PRODUCTO_BASE','INSUMO'), es_base, orden, 1
                FROM OPENJSON(?) WITH
                    (product_id INT, cantidad DECIMAL(18,6), unidad NVARCHAR(50),
                     es_base BIT, orden INT);
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
                json.dumps(componentes, ensure_ascii=False),
            ),
        ) or 0)
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


@cache
def obtener_base_datos() -> BaseDatos:
    return BaseDatos()
