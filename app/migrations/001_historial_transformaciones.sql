SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF COL_LENGTH('dbo.Transformaciones', 'producto_seleccionado') IS NULL
BEGIN
    ALTER TABLE dbo.Transformaciones
        ADD producto_seleccionado INT NULL;
END;

IF COL_LENGTH('dbo.Transformaciones', 'usuario_id') IS NULL
BEGIN
    ALTER TABLE dbo.Transformaciones
        ADD usuario_id INT NULL;
END;

IF COL_LENGTH('dbo.Transformaciones', 'tipo_transformacion') IS NULL
BEGIN
    ALTER TABLE dbo.Transformaciones
        ADD tipo_transformacion VARCHAR(30) NULL;
END;

IF COL_LENGTH('dbo.Transformaciones', 'porcentaje_merma_esperado') IS NULL
BEGIN
    ALTER TABLE dbo.Transformaciones
        ADD porcentaje_merma_esperado FLOAT NULL;
END;

IF COL_LENGTH('dbo.Transformaciones', 'id_operacion') IS NULL
BEGIN
    ALTER TABLE dbo.Transformaciones
        ADD id_operacion UNIQUEIDENTIFIER NULL;
END;

IF COL_LENGTH('dbo.DetalleTransformaciones', 'unidad_resultado') IS NULL
BEGIN
    ALTER TABLE dbo.DetalleTransformaciones
        ADD unidad_resultado VARCHAR(30) NULL;
END;

EXEC (
    'UPDATE dbo.Transformaciones
     SET producto_seleccionado = producto_origen
     WHERE producto_seleccionado IS NULL'
);

EXEC (
    'UPDATE dbo.Transformaciones
     SET tipo_transformacion = CASE
         WHEN (
             SELECT COUNT(*)
             FROM dbo.DetalleTransformaciones AS D
             WHERE D.id_transformacion =
                   Transformaciones.id_transformacion
         ) = 1
         AND EXISTS (
             SELECT 1
             FROM dbo.DetalleTransformaciones AS D
             WHERE D.id_transformacion =
                   Transformaciones.id_transformacion
               AND D.producto_resultado =
                   Transformaciones.producto_origen
         )
         THEN ''producto_final''
         ELSE ''receta_configurada''
     END
     WHERE tipo_transformacion IS NULL'
);

EXEC (
    'UPDATE dbo.Transformaciones
     SET id_operacion = NEWID()
     WHERE id_operacion IS NULL'
);

EXEC (
    'UPDATE dbo.DetalleTransformaciones
     SET unidad_resultado = ''KILO''
     WHERE unidad_resultado IS NULL'
);

IF NOT EXISTS (
    SELECT 1
    FROM sys.default_constraints
    WHERE parent_object_id = OBJECT_ID('dbo.Transformaciones')
      AND name = 'DF_Transformaciones_id_operacion'
)
BEGIN
    EXEC (
        'ALTER TABLE dbo.Transformaciones
         ADD CONSTRAINT DF_Transformaciones_id_operacion
         DEFAULT NEWID() FOR id_operacion'
    );
END;

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.Transformaciones')
      AND name = 'UX_Transformaciones_id_operacion'
)
BEGIN
    EXEC (
        'CREATE UNIQUE INDEX UX_Transformaciones_id_operacion
         ON dbo.Transformaciones(id_operacion)
         WHERE id_operacion IS NOT NULL'
    );
END;

IF OBJECT_ID('dbo.ComponentesTransformacion', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.ComponentesTransformacion (
        id_componente INT IDENTITY(1, 1) NOT NULL,
        id_transformacion INT NOT NULL,
        producto_componente INT NOT NULL,
        cantidad FLOAT NOT NULL,
        unidad VARCHAR(30) NOT NULL,
        es_producto_base BIT NOT NULL
            CONSTRAINT DF_ComponentesTransformacion_base DEFAULT 0,
        CONSTRAINT PK_ComponentesTransformacion
            PRIMARY KEY (id_componente),
        CONSTRAINT FK_ComponentesTransformacion_transformacion
            FOREIGN KEY (id_transformacion)
            REFERENCES dbo.Transformaciones(id_transformacion),
        CONSTRAINT FK_ComponentesTransformacion_producto
            FOREIGN KEY (producto_componente)
            REFERENCES dbo.orgProduct(ProductID),
        CONSTRAINT CK_ComponentesTransformacion_cantidad
            CHECK (cantidad > 0)
    );

    CREATE INDEX IX_ComponentesTransformacion_transformacion
        ON dbo.ComponentesTransformacion(id_transformacion);
END;

IF NOT EXISTS (
    SELECT 1
    FROM sys.foreign_keys
    WHERE parent_object_id = OBJECT_ID('dbo.ComponentesTransformacion')
      AND name = 'FK_ComponentesTransformacion_producto'
)
BEGIN
    ALTER TABLE dbo.ComponentesTransformacion
        ADD CONSTRAINT FK_ComponentesTransformacion_producto
        FOREIGN KEY (producto_componente)
        REFERENCES dbo.orgProduct(ProductID);
END;

COMMIT TRANSACTION;
