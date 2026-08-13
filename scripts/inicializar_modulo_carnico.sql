SET NOCOUNT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID('dbo.TransformacionesUsuario', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.TransformacionesUsuario
        (
            id_transformacion_usuario INT IDENTITY(1,1) NOT NULL,
            nombre_transformacion NVARCHAR(150) NOT NULL,
            producto_origen INT NOT NULL,
            producto_formula INT NULL,
            cantidad_base DECIMAL(18,3) NOT NULL,
            porcentaje_merma DECIMAL(5,2) NULL,
            usuario_creacion BIGINT NOT NULL,
            fecha_creacion DATETIME2(0) NOT NULL
                CONSTRAINT DF_TransformacionesUsuario_fecha DEFAULT SYSDATETIME(),
            usuario_actualizacion BIGINT NULL,
            fecha_actualizacion DATETIME2(0) NULL,
            activa BIT NOT NULL
                CONSTRAINT DF_TransformacionesUsuario_activa DEFAULT 1,
            observaciones NVARCHAR(500) NULL,
            proveedor_id INT NULL,
            proveedor_nombre NVARCHAR(250) NULL
        );
    END;

    IF COL_LENGTH('dbo.TransformacionesUsuario', 'proveedor_id') IS NULL
        ALTER TABLE dbo.TransformacionesUsuario ADD proveedor_id INT NULL;
    IF COL_LENGTH('dbo.TransformacionesUsuario', 'proveedor_nombre') IS NULL
        ALTER TABLE dbo.TransformacionesUsuario
            ADD proveedor_nombre NVARCHAR(250) NULL;

    IF OBJECT_ID('dbo.TransformacionesUsuarioDetalle', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.TransformacionesUsuarioDetalle
        (
            id_detalle_usuario INT IDENTITY(1,1) NOT NULL,
            id_transformacion_usuario INT NOT NULL,
            producto_resultante INT NOT NULL,
            cantidad_resultante DECIMAL(18,6) NOT NULL,
            unidad NVARCHAR(50) NOT NULL
                CONSTRAINT DF_TUD_unidad DEFAULT 'KILO',
            participa_balance BIT NOT NULL
                CONSTRAINT DF_TUD_balance DEFAULT 1,
            orden INT NOT NULL CONSTRAINT DF_TUD_orden DEFAULT 1,
            activa BIT NOT NULL CONSTRAINT DF_TUD_activa DEFAULT 1
        );
    END;

    IF OBJECT_ID('dbo.TransformacionesUsuarioComponente', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.TransformacionesUsuarioComponente
        (
            id_componente_usuario INT IDENTITY(1,1) NOT NULL,
            id_transformacion_usuario INT NOT NULL,
            producto_componente INT NOT NULL,
            cantidad DECIMAL(18,6) NOT NULL,
            unidad NVARCHAR(50) NOT NULL,
            es_producto_base BIT NOT NULL
                CONSTRAINT DF_TUC_base DEFAULT 0,
            tipo_componente NVARCHAR(30) NOT NULL
                CONSTRAINT DF_TUC_tipo DEFAULT 'INSUMO',
            participa_balance BIT NOT NULL
                CONSTRAINT DF_TUC_balance DEFAULT 0,
            orden INT NOT NULL CONSTRAINT DF_TUC_orden DEFAULT 1,
            activa BIT NOT NULL CONSTRAINT DF_TUC_activa DEFAULT 1,
            fecha_creacion DATETIME NOT NULL
                CONSTRAINT DF_TUC_fecha DEFAULT GETDATE()
        );
    END;

    IF OBJECT_ID('dbo.ModuloCarnicoConfiguracionAuditoria', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.ModuloCarnicoConfiguracionAuditoria
        (
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

    IF OBJECT_ID('dbo.ModuloCarnicoConfiguracionSeguridad', 'U') IS NULL
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
        SELECT 1 FROM dbo.ModuloCarnicoConfiguracionSeguridad
        WHERE id_configuracion = 1
    )
    BEGIN
        INSERT dbo.ModuloCarnicoConfiguracionSeguridad
            (id_configuracion, clave_firma)
        VALUES
        (
            1,
            CONVERT(NVARCHAR(36), NEWID())
            + CONVERT(NVARCHAR(36), NEWID())
            + CONVERT(NVARCHAR(36), NEWID())
        );
    END;

    IF OBJECT_ID('dbo.ModuloCarnicoProductoConfigurado', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.ModuloCarnicoProductoConfigurado
        (
            id_producto_carnico INT IDENTITY(1,1) NOT NULL,
            product_id INT NULL,
            clave NVARCHAR(60) NULL,
            proveedor_id INT NULL,
            proveedor_nombre NVARCHAR(250) NULL,
            nombre_producto NVARCHAR(250) NOT NULL,
            categoria NVARCHAR(100) NULL,
            categoria_resultante NVARCHAR(150) NULL,
            unidad NVARCHAR(50) NOT NULL
                CONSTRAINT DF_MCPC_unidad DEFAULT 'KILO',
            porcentaje_merma DECIMAL(9,4) NOT NULL
                CONSTRAINT DF_MCPC_merma DEFAULT 0,
            activo BIT NOT NULL CONSTRAINT DF_MCPC_activo DEFAULT 1,
            usuario_creacion BIGINT NULL,
            usuario_actualizacion BIGINT NULL,
            fecha_creacion DATETIME2 NOT NULL
                CONSTRAINT DF_MCPC_fecha_creacion DEFAULT SYSDATETIME(),
            fecha_actualizacion DATETIME2 NULL
        );
    END;

    IF OBJECT_ID('dbo.ModuloCarnicoProductoBitacora', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.ModuloCarnicoProductoBitacora
        (
            id_bitacora INT IDENTITY(1,1) NOT NULL,
            accion NVARCHAR(60) NOT NULL,
            usuario_id BIGINT NULL,
            usuario_confirmacion_nombre NVARCHAR(150) NOT NULL,
            detalle NVARCHAR(500) NULL,
            productos_json NVARCHAR(MAX) NULL,
            fecha DATETIME2 NOT NULL
                CONSTRAINT DF_MCPB_fecha DEFAULT SYSDATETIME()
        );
    END;

    INSERT dbo.ModuloCarnicoProductoConfigurado
    (
        product_id, clave, nombre_producto, categoria, unidad,
        porcentaje_merma, activo, usuario_creacion
    )
    SELECT
        P.ProductID, CONVERT(NVARCHAR(60), P.ProductID),
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

    IF OBJECT_ID('dbo.ModuloCarnicoTransformacionRegistro', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.ModuloCarnicoTransformacionRegistro
        (
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
                CONSTRAINT DF_MCTR_fecha DEFAULT SYSUTCDATETIME(),
            id_transformacion INT NULL,
            categoria_base NVARCHAR(100) NULL
        );
    END;

    IF COL_LENGTH('dbo.ModuloCarnicoTransformacionRegistro', 'id_transformacion') IS NULL
        ALTER TABLE dbo.ModuloCarnicoTransformacionRegistro
            ADD id_transformacion INT NULL;
    IF COL_LENGTH('dbo.ModuloCarnicoTransformacionRegistro', 'categoria_base') IS NULL
        ALTER TABLE dbo.ModuloCarnicoTransformacionRegistro
            ADD categoria_base NVARCHAR(100) NULL;

    IF OBJECT_ID('dbo.ModuloAlmacenMarca', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.ModuloAlmacenMarca
        (
            BrandID INT IDENTITY(1,1) NOT NULL,
            BrandName NVARCHAR(150) NOT NULL,
            categoria NVARCHAR(150) NULL,
            activo BIT NOT NULL
                CONSTRAINT DF_ModuloAlmacenMarca_activo DEFAULT 1,
            fecha_creacion DATETIME2 NOT NULL
                CONSTRAINT DF_ModuloAlmacenMarca_fecha DEFAULT SYSDATETIME()
        );
    END;

    IF OBJECT_ID('dbo.ModuloCarnicoCatalogoOculto', 'U') IS NOT NULL
    BEGIN
        INSERT INTO dbo.ModuloCarnicoConfiguracionAuditoria
        (
            configuracion_id, configuracion_nombre, accion,
            usuario_id, usuario_nombre, motivo,
            valores_anteriores_json, valores_nuevos_json, fecha
        )
        SELECT
            -O.product_id, O.nombre, 'ELIMINAR', O.usuario_id,
            'MIGRACION', 'Ocultamiento migrado a tabla privada del módulo',
            NULL, NULL, O.fecha
        FROM dbo.ModuloCarnicoCatalogoOculto AS O
        WHERE O.activo = 1
          AND NOT EXISTS
          (
              SELECT 1
              FROM dbo.ModuloCarnicoConfiguracionAuditoria AS A
              WHERE A.configuracion_id = -O.product_id
          );

        UPDATE C
        SET C.activo = 0,
            C.fecha_actualizacion = O.fecha
        FROM dbo.ModuloCarnicoProductoConfigurado AS C
        INNER JOIN dbo.ModuloCarnicoCatalogoOculto AS O
            ON O.product_id = C.product_id
           AND O.activo = 1;

        INSERT dbo.ModuloCarnicoProductoConfigurado
        (
            product_id, nombre_producto, categoria, unidad,
            porcentaje_merma, activo, usuario_creacion,
            fecha_creacion, fecha_actualizacion
        )
        SELECT
            P.ProductID, P.ProductName, P.Category1, ISNULL(P.Unit, 'KILO'),
            0, 0, O.usuario_id, O.fecha, O.fecha
        FROM dbo.ModuloCarnicoCatalogoOculto AS O
        INNER JOIN dbo.orgProduct AS P ON P.ProductID = O.product_id
        WHERE O.activo = 1
          AND NOT EXISTS
          (
              SELECT 1
              FROM dbo.ModuloCarnicoProductoConfigurado AS C
              WHERE C.product_id = O.product_id
          );
    END;


    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
