class ErrorIntegracionERP(RuntimeError):
    pass


class IntegracionMovimientosERP:
    def __init__(self, base_datos):
        self._base_datos = base_datos

    @staticmethod
    def _nombres_movimientos(configuracion):
        return (
            configuracion["movimiento_salida"],
            configuracion["movimiento_entrada"],
        )

    @staticmethod
    def _partidas_salida(datos):
        return [(datos.producto_origen_id, datos.cantidad_origen)]

    @staticmethod
    def _partidas_entrada(datos):
        return [
            (producto.producto_id, producto.cantidad)
            for producto in datos.productos_resultantes
        ]

    def _crear_documento(
        self,
        tipo,
        nombre_movimiento,
        usuario_id,
        almacen_id,
        comentario,
    ):
        movimiento = self._base_datos.buscar_tipo_movimiento(
            tipo,
            nombre_movimiento,
        )
        documento_id = self._base_datos.crear_movimiento_de_almacen(
            tipo,
            movimiento["id"],
            usuario_id,
            almacen_id,
            comentario,
        )

        if not documento_id:
            raise ErrorIntegracionERP(
                f"No fue posible crear el documento de {tipo}"
            )

        self._base_datos.configurar_almacen_documento(
            documento_id,
            almacen_id,
        )
        return documento_id

    def _insertar_partidas(
        self,
        documento_id,
        partidas,
        almacen_id,
        modulo_id,
        comentario,
    ):
        productos_existentes = {
            fila["ProductID"]
            for fila in self._base_datos.buscar_partidas_documento(
                documento_id,
                filtro=["ProductID"],
            )
        }

        for producto_id, cantidad in partidas:
            if producto_id in productos_existentes:
                continue

            self._base_datos.insertar_partida_movimiento(
                documento_id=documento_id,
                producto_id=producto_id,
                almacen_id=almacen_id,
                cantidad=cantidad,
                modulo_id=modulo_id,
                comentario=comentario,
            )

        productos_esperados = {
            producto_id
            for producto_id, _ in partidas
        }
        productos_registrados = {
            fila["ProductID"]
            for fila in self._base_datos.buscar_partidas_documento(
                documento_id,
                filtro=["ProductID"],
            )
        }

        if productos_registrados != productos_esperados:
            raise ErrorIntegracionERP(
                "Las partidas del documento no coinciden "
                "con la transformacion"
            )

    def procesar(self, transformacion_id, datos):
        configuracion = (
            self._base_datos.buscar_configuracion_transformaciones()
        )
        almacen_id = configuracion["almacen_id"]
        nombre_salida, nombre_entrada = self._nombres_movimientos(configuracion)
        comentario = (
            f"Transformacion {transformacion_id} creada por "
            f"{datos.usuario_nombre or datos.usuario_id}"
        )
        registro = self._base_datos.buscar_transformacion_por_operacion(
            datos.id_operacion
        )
        documento_salida = (
            registro["documento_salida"]
            if registro
            else None
        )
        documento_entrada = (
            registro["documento_entrada"]
            if registro
            else None
        )

        try:
            if not documento_salida:
                documento_salida = self._crear_documento(
                    tipo="salida",
                    nombre_movimiento=nombre_salida,
                    usuario_id=datos.usuario_id,
                    almacen_id=almacen_id,
                    comentario=comentario,
                )
                self._base_datos.actualizar_integracion_erp(
                    transformacion_id,
                    documento_salida=documento_salida,
                    estado="procesando",
                )

            self._insertar_partidas(
                documento_id=documento_salida,
                partidas=self._partidas_salida(datos),
                almacen_id=almacen_id,
                modulo_id=configuracion["modulo_salida"],
                comentario=comentario,
            )

            if not documento_entrada:
                documento_entrada = self._crear_documento(
                    tipo="entrada",
                    nombre_movimiento=nombre_entrada,
                    usuario_id=datos.usuario_id,
                    almacen_id=almacen_id,
                    comentario=comentario,
                )
                self._base_datos.actualizar_integracion_erp(
                    transformacion_id,
                    documento_entrada=documento_entrada,
                    estado="procesando",
                )

            self._insertar_partidas(
                documento_id=documento_entrada,
                partidas=self._partidas_entrada(datos),
                almacen_id=almacen_id,
                modulo_id=configuracion["modulo_entrada"],
                comentario=comentario,
            )

            self._base_datos.relacionar_documentos(
                documento_salida,
                destino=documento_entrada,
            )
            self._base_datos.relacionar_documentos(
                documento_entrada,
                origen=documento_salida,
            )
            self._base_datos.registrar_recalculo_si_pendiente(
                documento_salida,
                datos.id_operacion,
            )
            self._base_datos.registrar_recalculo_si_pendiente(
                documento_entrada,
                datos.id_operacion,
            )
            self._base_datos.actualizar_integracion_erp(
                transformacion_id,
                documento_salida=documento_salida,
                documento_entrada=documento_entrada,
                estado="pendiente_afectacion",
                error=None,
            )
        except Exception as error:
            self._base_datos.actualizar_integracion_erp(
                transformacion_id,
                documento_salida=documento_salida,
                documento_entrada=documento_entrada,
                estado="error",
                error=str(error)[:500],
            )
            raise ErrorIntegracionERP(
                "La transformacion se guardo, pero no fue posible "
                "completar sus movimientos en el ERP"
            ) from error

        return {
            "documento_salida": documento_salida,
            "folio_salida": self._base_datos.buscar_folio_documento(
                documento_salida
            ),
            "documento_entrada": documento_entrada,
            "folio_entrada": self._base_datos.buscar_folio_documento(
                documento_entrada
            ),
            "almacen_id": almacen_id,
            "almacen": configuracion["almacen"],
            "estado": "pendiente_afectacion",
        }
