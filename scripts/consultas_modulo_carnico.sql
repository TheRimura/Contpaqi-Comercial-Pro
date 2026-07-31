/* ================================================================
   1. RELACIONES DE DOCUMENTOS DE TRANSFORMACIÓN
   FechaRegistro se presenta sin fracciones de segundo.
   ================================================================ */
SELECT
    R.DocumentWarehouseRelationID AS IdRelacion,
    R.SourceDocumentID AS IdSalida,
    ISNULL(S.FolioPrefix, '') + ISNULL(S.Folio, '') AS FolioSalida,
    R.DestinationDocumentID AS IdEntrada,
    ISNULL(E.FolioPrefix, '') + ISNULL(E.Folio, '') AS FolioEntrada,
    CONVERT(DATETIME2(0), R.CreatedOn) AS FechaRegistro,
    R.PhysicalUserID AS TablajeroID,
    ISNULL(Empleado.OfficialName, '') AS Tablajero,
    R.ERPUserID AS UsuarioERPID,
    ISNULL(U.UserName, '') AS UsuarioERP
FROM dbo.docDocumentWarehouseRelation AS R
INNER JOIN dbo.docDocument AS S
    ON S.DocumentID = R.SourceDocumentID
   AND S.ModuleID = 203
INNER JOIN dbo.docDocument AS E
    ON E.DocumentID = R.DestinationDocumentID
   AND E.ModuleID = 202
LEFT JOIN dbo.engUser AS U
    ON U.UserID = R.ERPUserID
OUTER APPLY (
    SELECT TOP 1 EMP.OfficialName
    FROM dbo.zvwEmpleadosCayalMenu AS EMP
    WHERE EMP.UserID = R.PhysicalUserID
    ORDER BY EMP.OfficialName
) AS Empleado
WHERE S.DeletedOn IS NULL
  AND E.DeletedOn IS NULL
  AND TRY_CONVERT(INT, S.CustomCbo) = 2
  AND TRY_CONVERT(INT, E.CustomCbo) = 5
ORDER BY
    R.CreatedOn DESC,
    R.DocumentWarehouseRelationID DESC;


/* ================================================================
   2. HISTORIAL DETALLADO DE TRANSFORMACIONES
   ================================================================ */
SELECT
    R.DocumentWarehouseRelationID AS IdRelacion,
    CONVERT(DATETIME2(0), R.CreatedOn) AS FechaRegistro,

    ISNULL(S.FolioPrefix, '') + ISNULL(S.Folio, '') AS FolioSalida,
    ISNULL(Base.ProductName, '') AS ProductoBase,
    CAST(
        ROUND(ISNULL(Base.Quantity, 0), 2)
        AS DECIMAL(18,2)
    ) AS KilosSalida,

    ISNULL(E.FolioPrefix, '') + ISNULL(E.Folio, '') AS FolioEntrada,
    ISNULL(Resultado.ProductName, '') AS ProductoResultante,
    CAST(
        ROUND(ISNULL(Resultado.Quantity, 0), 2)
        AS DECIMAL(18,2)
    ) AS KilosEntrada,

    CAST(
        ROUND(
            ISNULL(Base.Quantity, 0) -
            ISNULL(Resultado.Quantity, 0),
            2
        ) AS DECIMAL(18,2)
    ) AS KilosMerma,

    CAST(
        ROUND(
            CASE
                WHEN ISNULL(Base.Quantity, 0) > 0
                THEN (
                    (
                        ISNULL(Base.Quantity, 0) -
                        ISNULL(Resultado.Quantity, 0)
                    ) / Base.Quantity
                ) * 100
                ELSE 0
            END,
            2
        ) AS DECIMAL(9,2)
    ) AS PorcentajeMerma,

    ISNULL(Empleado.OfficialName, '') AS Tablajero,
    ISNULL(U.UserName, '') AS UsuarioERP
FROM dbo.docDocumentWarehouseRelation AS R
INNER JOIN dbo.docDocument AS S
    ON S.DocumentID = R.SourceDocumentID
   AND S.ModuleID = 203
INNER JOIN dbo.docDocument AS E
    ON E.DocumentID = R.DestinationDocumentID
   AND E.ModuleID = 202
LEFT JOIN dbo.engUser AS U
    ON U.UserID = R.ERPUserID
OUTER APPLY (
    SELECT TOP 1
        P.ProductName,
        DI.Quantity
    FROM dbo.docDocumentItem AS DI
    INNER JOIN dbo.orgProduct AS P
        ON P.ProductID = DI.ProductID
    WHERE DI.DocumentID = S.DocumentID
      AND DI.DeletedOn IS NULL
    ORDER BY
        CASE
            WHEN DI.Comments LIKE 'Producto base%' THEN 0
            ELSE 1
        END,
        DI.DocumentItemID
) AS Base
OUTER APPLY (
    SELECT TOP 1
        P.ProductName,
        DI.Quantity
    FROM dbo.docDocumentItem AS DI
    INNER JOIN dbo.orgProduct AS P
        ON P.ProductID = DI.ProductID
    WHERE DI.DocumentID = E.DocumentID
      AND DI.DeletedOn IS NULL
    ORDER BY DI.DocumentItemID
) AS Resultado
OUTER APPLY (
    SELECT TOP 1 EMP.OfficialName
    FROM dbo.zvwEmpleadosCayalMenu AS EMP
    WHERE EMP.UserID = R.PhysicalUserID
    ORDER BY EMP.OfficialName
) AS Empleado
WHERE S.DeletedOn IS NULL
  AND E.DeletedOn IS NULL
  AND TRY_CONVERT(INT, S.CustomCbo) = 2
  AND TRY_CONVERT(INT, E.CustomCbo) = 5
ORDER BY
    R.CreatedOn DESC,
    R.DocumentWarehouseRelationID DESC;


/* ================================================================
   3. CONFIGURACIONES ACTIVAS DE TRANSFORMACIÓN
   ================================================================ */
SELECT
    T.id_transformacion_usuario AS TransformacionID,
    P.Category1 AS Linea,
    T.nombre_transformacion AS Transformacion,
    T.producto_origen AS ProductoBaseID,
    P.ProductName AS ProductoBase,
    T.cantidad_base AS KilosRegistrados,
    T.porcentaje_merma AS MermaEsperada,
    T.activa,
    T.usuario_creacion
FROM dbo.TransformacionesUsuario AS T
INNER JOIN dbo.orgProduct AS P
    ON P.ProductID = T.producto_origen
WHERE T.activa = 1
  AND P.DiscontinuedOn IS NULL
ORDER BY
    P.Category1,
    T.nombre_transformacion;
