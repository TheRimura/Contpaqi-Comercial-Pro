const API_RELACIONES = "/api/relaciones-documentos";
const AJUSTES_INTERFAZ = document.body?.dataset || {};
const MERMA_TECNICA_PORCENTAJE = Number(AJUSTES_INTERFAZ.mermaTecnica || 8);
const MAXIMO_KILOS_TRANSFORMACION = Number(AJUSTES_INTERFAZ.maximoKilos || 3000);
let catalogos = { movimientos: [], proveedores: [], usuarios_fisicos: [] };
let documentos = { salida: [], entrada: [] };
let partidasEntrada = [];
let datosCargados = false;
let transformacionPreparada = false;
let detalleTransformacionSeleccionada = null;
let insumosTransformacionCalculados = [];
let transformacionesDisponibles = [];
let transformacionCatalogoActualId = "";
let lineaTransformacionSeleccionada = "";
let temporizadorVistaPreviaTransformacion = null;
let transformacionesLineaActual = [];
let paginaTransformacionesActual = 1;
const TRANSFORMACIONES_POR_PAGINA = Number(AJUSTES_INTERFAZ.transformacionesPorPagina || 12);
const API_CONFIGURACION = "/api/configuracion";
const SUFIJO_USUARIO_LOCAL = AJUSTES_INTERFAZ.usuarioId || "anonimo";
const CLAVE_CONFIGURACIONES_NUEVAS = `cayal-configuraciones-nuevas-${SUFIJO_USUARIO_LOCAL}`;
const CLAVE_BORRADOR_CONFIGURACION = `cayal-borrador-configuracion-v1-${SUFIJO_USUARIO_LOCAL}`;
const CLAVE_BORRADOR_TRANSFORMACION = `cayal-borrador-transformacion-v1-${SUFIJO_USUARIO_LOCAL}`;
let componentesConfiguracion = [];
let productosConfiguracionDisponibles = [];
let lineaCatalogoActual = "";
let temporizadorCatalogo = null;
let productosCatalogoActual = [];
let productosCatalogoSinFiltrar = [];
let productoCatalogoSeleccionadoId = 0;
let modoEliminacionCatalogo = false;
let controladorCargaComponentesConfiguracion = null;
let paginaCatalogoActual = 1;
let configuracionesPendientes = [];
let indiceConfiguracionEnEdicion = -1;
let proporcionesInsumosConfiguracion = new Map();
let cantidadFormulaBaseConfiguracion = 0;
const PRODUCTOS_POR_PAGINA = Number(AJUSTES_INTERFAZ.productosPorPagina || 12);
const HISTORIAL_POR_PAGINA = 10;
let paginaHistorialActual = 1;
let totalPaginasHistorial = 1;
let totalRegistrosHistorial = 0;
let registrosHistorialActual = [];
let historialCargadoDesdeServidor = false;
let registrosAuditoriaConfiguracion = [];

function guardarLocal(clave, datos) {
    try {
        localStorage.setItem(clave, JSON.stringify({
            version: 1,
            guardado_en: new Date().toISOString(),
            datos,
        }));
    } catch (error) {
        console.warn("No fue posible guardar el borrador local.", error);
    }
}

function leerLocal(clave) {
    try {
        const registro = JSON.parse(localStorage.getItem(clave) || "null");
        return registro?.version === 1 ? registro.datos : null;
    } catch (_) {
        localStorage.removeItem(clave);
        return null;
    }
}

function eliminarLocal(clave) {
    try { localStorage.removeItem(clave); } catch (_) { /* sin almacenamiento */ }
}

function guardarBorradorConfiguracion() {
    const formulario = document.getElementById("form-nueva-configuracion");
    if (!formulario) return;
    const datos = {
        abierta: !formulario.classList.contains("hidden"),
        linea: document.getElementById("config-linea")?.value || "",
        nombre: document.getElementById("config-nombre")?.value || "",
        cantidad_base: document.getElementById("config-cantidad-base")?.value || "",
        porcentaje_merma: document.getElementById("config-merma")?.value || "",
        observaciones: document.getElementById("config-observaciones")?.value || "",
        componentes: componentesConfiguracion,
        pendientes: configuracionesPendientes,
        indice_edicion: indiceConfiguracionEnEdicion,
    };
    const tieneDatos = datos.abierta || datos.linea || datos.nombre
        || datos.cantidad_base || datos.componentes.length || datos.pendientes.length;
    if (tieneDatos) guardarLocal(CLAVE_BORRADOR_CONFIGURACION, datos);
    else eliminarLocal(CLAVE_BORRADOR_CONFIGURACION);
}

function guardarBorradorTransformacion() {
    if (!detalleTransformacionSeleccionada) return;
    guardarLocal(CLAVE_BORRADOR_TRANSFORMACION, {
        detalle: detalleTransformacionSeleccionada,
        linea: lineaTransformacionSeleccionada,
        catalogo_id: transformacionCatalogoActualId,
        movimiento: document.getElementById("tipo-movimiento")?.value || "",
        kilos: document.getElementById("cantidad-base-transformacion")?.value || "",
        tablajero: document.getElementById("tablajero-transformacion")?.value || "",
    });
}

function limpiarNombreProducto(nombre) {
    return String(nombre || "")
        .replace(/^[.\s]+/, "")
        .replace(/\s*\.?\s*1\s*\(\s*\d+\s*(?:-\s*\d+|\+)\s*\)\s*$/i, "")
        .trim();
}

function validarKilosTransformacion(mostrarError = true) {
    const entrada = document.getElementById("cantidad-base-transformacion");
    const kilos = Number(entrada?.value || 0);
    const valido = Number.isFinite(kilos)
        && kilos > 0
        && kilos <= MAXIMO_KILOS_TRANSFORMACION;
    if (entrada) {
        entrada.setCustomValidity(
            valido
                ? ""
                : `La cantidad debe ser mayor que 0 y no exceder ${MAXIMO_KILOS_TRANSFORMACION.toLocaleString("es-MX")} kg.`
        );
    }
    if (!valido && mostrarError) {
        mostrarMensaje(
            `La cantidad debe ser mayor que 0 y no exceder ${MAXIMO_KILOS_TRANSFORMACION.toLocaleString("es-MX")} kg.`
        );
    }
    return valido;
}

function convertirCantidadParaMostrar(cantidad, unidad = "KILO", decimales = 2) {
    const valor = Number(cantidad || 0);
    const unidadNormalizada = String(unidad || "KILO").trim().toUpperCase();
    const estaEnKilos = ["KILO", "KILOS", "KG"].includes(unidadNormalizada);
    if (estaEnKilos && valor > 0 && valor <= 0.9) {
        return {
            cantidad: valor.toFixed(3),
            unidad: "GRAMOS",
        };
    }
    return {
        cantidad: valor.toFixed(decimales),
        unidad: unidad || "KILO",
    };
}

function formatearPesoHistorial(kilos) {
    const valor = Math.max(Number(kilos || 0), 0);
    if (valor >= 1000) {
        return `${(valor / 1000).toFixed(2)} T`;
    }
    if (valor > 0 && valor < 1) {
        return `${(valor * 1000).toFixed(2)} gramos`;
    }
    return `${valor.toFixed(2)} kg`;
}

function separarPesoHistorial(kilos) {
    const texto = formatearPesoHistorial(kilos);
    const separador = texto.lastIndexOf(" ");
    return {
        valor: texto.slice(0, separador),
        unidad: texto.slice(separador + 1),
    };
}

function llenarConfigSelect(elemento, registros, placeholder) {
    elemento.replaceChildren(new Option(placeholder, ""));
    registros.forEach((registro) => {
        const opcion = new Option(limpiarNombreProducto(registro.producto), String(registro.product_id));
        opcion.dataset.unidad = registro.unidad || "KILO";
        elemento.appendChild(opcion);
    });
    elemento.disabled = registros.length === 0;
}

function mensajeConfiguracion(texto, tipo = "error") {
    const mensaje = document.getElementById("mensaje-configuracion");
    mensaje.textContent = texto;
    mensaje.className = `message visible ${tipo}`;
}

function normalizarIdentificadorCatalogo(valor) {
    return String(valor || "").trim().toLocaleUpperCase("es-MX");
}

function obtenerConfiguracionesNuevas() {
    try {
        const registros = JSON.parse(
            localStorage.getItem(CLAVE_CONFIGURACIONES_NUEVAS) || "[]"
        );
        return Array.isArray(registros) ? registros : [];
    } catch (_) {
        return [];
    }
}

function guardarConfiguracionesNuevas(registros) {
    try {
        localStorage.setItem(
            CLAVE_CONFIGURACIONES_NUEVAS,
            JSON.stringify(registros.slice(-30))
        );
    } catch (_) {
        // La actualización del catálogo continúa aunque el navegador no guarde datos.
    }
}

function registrarNotificacionesConfiguraciones(configuraciones) {
    const anteriores = obtenerConfiguracionesNuevas();
    configuraciones.forEach((configuracion) => {
        const linea = normalizarIdentificadorCatalogo(configuracion.linea);
        const nombre = normalizarIdentificadorCatalogo(configuracion.nombre);
        const repetida = anteriores.some(
            (registro) => registro.linea === linea && registro.nombre === nombre
        );
        if (!repetida) {
            anteriores.push({ linea, nombre, fecha: new Date().toISOString() });
        }
    });
    guardarConfiguracionesNuevas(anteriores);
}

function aplicarNotificacionesConfiguraciones() {
    const nuevas = obtenerConfiguracionesNuevas();
    const lineasNuevas = new Set(nuevas.map((registro) => registro.linea));
    document.querySelectorAll(".configuration-line").forEach((boton) => {
        const tieneNuevas = lineasNuevas.has(
            normalizarIdentificadorCatalogo(boton.dataset.linea)
        );
        boton.classList.toggle("has-new-configuration", tieneNuevas);
        boton.title = tieneNuevas
            ? "Esta línea tiene una transformación nueva"
            : "";
    });
    document.querySelectorAll(".configuration-relation").forEach((tarjeta) => {
        const esNueva = nuevas.some(
            (registro) =>
                registro.linea === normalizarIdentificadorCatalogo(tarjeta.dataset.linea)
                && registro.nombre === normalizarIdentificadorCatalogo(tarjeta.dataset.nombre)
        );
        tarjeta.classList.toggle("recently-created", esNueva);
        tarjeta.querySelector(".new-configuration-badge")?.remove();
        if (esNueva) {
            const insignia = document.createElement("span");
            insignia.className = "new-configuration-badge";
            insignia.textContent = "Nueva";
            tarjeta.appendChild(insignia);
        }
    });
}

function marcarNotificacionesLineaComoVistas(linea) {
    const lineaNormalizada = normalizarIdentificadorCatalogo(linea);
    guardarConfiguracionesNuevas(
        obtenerConfiguracionesNuevas().filter(
            (registro) => registro.linea !== lineaNormalizada
        )
    );
    document.querySelectorAll(".configuration-line").forEach((boton) => {
        if (normalizarIdentificadorCatalogo(boton.dataset.linea) === lineaNormalizada) {
            boton.classList.remove("has-new-configuration");
            boton.title = "";
        }
    });
}

async function abrirDetalleProductoCatalogo(producto) {
    const modal = document.getElementById("modal-detalle-producto");
    const cuerpo = document.getElementById("detalle-producto-componentes");
    document.getElementById("titulo-detalle-producto").textContent = limpiarNombreProducto(producto.producto);
    document.getElementById("mensaje-detalle-producto").textContent = "Cargando ingredientes...";
    cuerpo.replaceChildren();
    modal.classList.remove("hidden");
    try {
        let detalle;
        if (producto.es_configuracion && producto.transformacion_id) {
            const configuracion = await solicitarJson(
                `${API_RELACIONES}/transformacion/precargadas/${producto.transformacion_id}`
            );
            detalle = (configuracion.componentes || []).map((componente) => ({
                ...componente,
                formula_id: Number(producto.transformacion_id),
                formula: producto.producto,
            }));
        } else {
            detalle = await solicitarJson(
                `${API_CONFIGURACION}/formula/${producto.product_id}`
            );
        }
        const formulasAgrupadas = new Map();
        (Array.isArray(detalle) ? detalle : []).forEach((componente) => {
            const formulaId = Number(componente.formula_id || producto.product_id);
            if (!formulasAgrupadas.has(formulaId)) {
                formulasAgrupadas.set(formulaId, {
                    formula_id: formulaId,
                    formula: componente.formula || producto.producto,
                    componentes: [],
                });
            }
            formulasAgrupadas.get(formulaId).componentes.push(componente);
        });
        const formulas = Array.isArray(detalle)
            ? [...formulasAgrupadas.values()]
            : (detalle["formulas"] || []);
        document.getElementById("mensaje-detalle-producto").textContent = formulas.length
            ? `${formulas.length} fórmula${formulas.length === 1 ? "" : "s"} propia${formulas.length === 1 ? "" : "s"} registrada${formulas.length === 1 ? "" : "s"} en el sistema.`
            : "Este producto no tiene ingredientes registrados.";
        formulas.forEach((formula) => {
            const encabezado = document.createElement("tr");
            encabezado.className = "formula-group-row";
            const titulo = document.createElement("td");
            titulo.colSpan = 3;
            titulo.textContent = limpiarNombreProducto(formula.formula);
            encabezado.appendChild(titulo);
            cuerpo.appendChild(encabezado);

            (formula.componentes || []).forEach((componente) => {
                const fila = document.createElement("tr");
                const cantidadVisual = convertirCantidadParaMostrar(
                    componente.cantidad,
                    componente.unidad
                );
                [
                    limpiarNombreProducto(componente.producto),
                    cantidadVisual.cantidad,
                    cantidadVisual.unidad,
                ].forEach((valor) => {
                    const celda = document.createElement("td");
                    celda.textContent = valor;
                    fila.appendChild(celda);
                });
                cuerpo.appendChild(fila);
            });
        });
    } catch (error) {
        document.getElementById("mensaje-detalle-producto").textContent = error.message;
    }
}

function limpiarMensajeConfiguracion() {
    const mensaje = document.getElementById("mensaje-configuracion");
    mensaje.textContent = "";
    mensaje.className = "message";
}

function renderizarPaginaCatalogo() {
    const lista = document.getElementById("lista-productos-catalogo");
    const paginacion = document.getElementById("paginacion-productos-catalogo");
    lista.replaceChildren();
    if (!productosCatalogoActual.length) {
        lista.innerHTML = '<p class="catalog-loading">No se encontraron productos.</p>';
        paginacion.classList.add("hidden");
        return;
    }
    const totalPaginas = Math.ceil(productosCatalogoActual.length / PRODUCTOS_POR_PAGINA);
    paginaCatalogoActual = Math.min(Math.max(paginaCatalogoActual, 1), totalPaginas);
    const inicio = (paginaCatalogoActual - 1) * PRODUCTOS_POR_PAGINA;
    productosCatalogoActual
        .slice(inicio, inicio + PRODUCTOS_POR_PAGINA)
        .forEach((producto) => {
            const fila = document.createElement("button");
            fila.type = "button";
            fila.className = "catalog-product";
            fila.classList.toggle("catalog-configuration", Boolean(producto.es_configuracion));
            fila.dataset.productoId = String(producto.product_id);
            const nombre = document.createElement("strong");
            nombre.textContent = limpiarNombreProducto(producto.producto);
            const unidad = document.createElement("span");
            unidad.textContent = producto.es_configuracion
                ? "TRANSFORMACIÓN"
                : (producto.unidad || "SIN UNIDAD");
            const esNueva = obtenerConfiguracionesNuevas().some(
                (registro) =>
                    registro.linea === normalizarIdentificadorCatalogo(lineaCatalogoActual)
                    && registro.nombre === normalizarIdentificadorCatalogo(producto.producto)
            );
            if (esNueva) {
                fila.classList.add("recently-created");
                unidad.textContent = "NUEVA TRANSFORMACIÓN";
            }
            fila.append(nombre, unidad);
            fila.addEventListener("click", async () => {
                if (modoEliminacionCatalogo) {
                    const confirmado = await solicitarConfirmacionEliminarProductoCatalogo(
                        producto
                    );
                    if (confirmado) {
                        try {
                            await ocultarProductoCatalogo(producto);
                        } catch (error) {
                            mensajeConfiguracion(error.message);
                        }
                    }
                    return;
                }
                productoCatalogoSeleccionadoId = Number(producto.product_id);
                document.querySelectorAll(".catalog-product").forEach((elemento) => {
                    elemento.classList.toggle("selected", elemento === fila);
                });
            });
            fila.addEventListener("dblclick", () => {
                if (!modoEliminacionCatalogo) {
                    void abrirDetalleProductoCatalogo(producto);
                }
            });
            lista.appendChild(fila);
        });
    document.getElementById("catalogo-pagina-actual").textContent =
        `Página ${paginaCatalogoActual} de ${totalPaginas}`;
    document.getElementById("catalogo-pagina-anterior").disabled = paginaCatalogoActual === 1;
    document.getElementById("catalogo-pagina-siguiente").disabled = paginaCatalogoActual === totalPaginas;
    paginacion.classList.toggle("hidden", totalPaginas <= 1);
}

function cambiarPaginaCatalogo(cambio) {
    paginaCatalogoActual += cambio;
    renderizarPaginaCatalogo();
    document.getElementById("catalogo-productos").scrollIntoView({ behavior: "smooth", block: "start" });
}

function actualizarUnidadesCatalogo() {
    const selector = document.getElementById("filtro-unidad-catalogo");
    const seleccion = selector.value;
    const unidades = [...new Set(
        productosCatalogoSinFiltrar
            .map((producto) => String(producto.unidad || "SIN UNIDAD").trim().toUpperCase())
            .filter(Boolean)
    )].sort();
    selector.replaceChildren(new Option("Todas las unidades", ""));
    unidades.forEach((unidad) => selector.appendChild(new Option(unidad, unidad)));
    selector.value = unidades.includes(seleccion) ? seleccion : "";
}

function aplicarFiltrosCatalogo() {
    const termino = document.getElementById("buscar-producto-catalogo")
        .value.trim().toLocaleUpperCase("es-MX");
    const unidad = document.getElementById("filtro-unidad-catalogo").value;
    const receta = document.getElementById("filtro-receta-catalogo").value;
    const antiguedad = document.getElementById("filtro-antiguedad-catalogo").value;
    productosCatalogoActual = productosCatalogoSinFiltrar.filter((producto) => {
        const coincideNombre = !termino || String(producto.producto || "")
            .toLocaleUpperCase("es-MX").includes(termino);
        const unidadProducto = String(producto.unidad || "SIN UNIDAD").trim().toUpperCase();
        const coincideUnidad = !unidad || unidadProducto === unidad;
        const tieneReceta = Boolean(producto.tiene_receta);
        const coincideReceta = (
            !receta
            || (receta === "CON_RECETA" && tieneReceta)
            || (receta === "SIN_RECETA" && !tieneReceta)
        );
        const coincideAntiguedad = (
            !antiguedad
            || (antiguedad === "RECIENTES" && Boolean(producto.es_reciente))
        );
        return coincideNombre && coincideUnidad && coincideReceta && coincideAntiguedad;
    });
    paginaCatalogoActual = 1;
    renderizarPaginaCatalogo();
    document.getElementById("catalogo-productos-total").textContent =
        `${productosCatalogoActual.length} de ${productosCatalogoSinFiltrar.length} productos`;
    const filtrosActivos = [unidad, receta, antiguedad].filter(Boolean).length;
    const contador = document.getElementById("total-filtros-catalogo");
    contador.textContent = String(filtrosActivos);
    contador.classList.toggle("hidden", filtrosActivos === 0);
}

function limpiarFiltrosCatalogo() {
    document.getElementById("buscar-producto-catalogo").value = "";
    document.getElementById("filtro-unidad-catalogo").value = "";
    document.getElementById("filtro-receta-catalogo").value = "";
    document.getElementById("filtro-antiguedad-catalogo").value = "";
    aplicarFiltrosCatalogo();
}

function alternarFiltrosCatalogo() {
    const panel = document.getElementById("filtros-catalogo");
    const boton = document.getElementById("mostrar-filtros-catalogo");
    const abrir = panel.classList.contains("hidden");
    panel.classList.toggle("hidden", !abrir);
    boton.setAttribute("aria-expanded", String(abrir));
}

async function cargarProductosCatalogo(linea) {
    lineaCatalogoActual = linea;
    const panel = document.getElementById("catalogo-productos");
    const lista = document.getElementById("lista-productos-catalogo");
    panel.classList.remove("hidden");
    document.getElementById("configuraciones-guardadas").classList.add("hidden");
    document.getElementById("catalogo-productos-titulo").textContent = linea;
    document.getElementById("catalogo-productos-total").textContent = "";
    lista.innerHTML = '<p class="catalog-loading">Consultando productos...</p>';
    document.getElementById("paginacion-productos-catalogo").classList.add("hidden");
    document.querySelectorAll(".configuration-line").forEach((boton) => {
        boton.classList.toggle("active", boton.dataset.linea === linea);
    });
    try {
        productosCatalogoSinFiltrar = await solicitarJson(
            `${API_CONFIGURACION}/productos-base?linea=${encodeURIComponent(linea)}`
        );
        productoCatalogoSeleccionadoId = 0;
        actualizarUnidadesCatalogo();
        aplicarFiltrosCatalogo();
    } catch (error) {
        productosCatalogoActual = [];
        productosCatalogoSinFiltrar = [];
        document.getElementById("paginacion-productos-catalogo").classList.add("hidden");
        const mensaje = document.createElement("p");
        mensaje.className = "catalog-loading catalog-error";
        mensaje.textContent = error.message;
        lista.replaceChildren(mensaje);
    }
}

async function ocultarProductoCatalogo(producto) {
    const productoId = Number(producto?.product_id);
    if (!modoEliminacionCatalogo || !productoId) return;
    await solicitarJson(`${API_CONFIGURACION}/catalogo/ocultar`, {
        method: "POST",
        body: JSON.stringify({
            producto_id: productoId,
            es_configuracion: Boolean(producto.es_configuracion),
            transformacion_id: producto.transformacion_id || null,
            nombre: limpiarNombreProducto(producto.producto),
            linea: lineaCatalogoActual,
        }),
    });
    productosCatalogoActual = productosCatalogoActual.filter(
        (producto) => Number(producto.product_id) !== productoId
    );
    productosCatalogoSinFiltrar = productosCatalogoSinFiltrar.filter(
        (registro) => Number(registro.product_id) !== productoId
    );
    const identificadorOculto = producto.es_configuracion
        ? Number(producto.transformacion_id || 0)
        : productoId;
    transformacionesDisponibles = transformacionesDisponibles.filter(
        (registro) => Number(registro.transformacion_id) !== identificadorOculto
    );
    transformacionesLineaActual = transformacionesLineaActual.filter(
        (registro) => Number(registro.transformacion_id) !== identificadorOculto
    );
    productoCatalogoSeleccionadoId = 0;
    actualizarUnidadesCatalogo();
    aplicarFiltrosCatalogo();
}

function solicitarConfirmacionEliminarProductoCatalogo(producto) {
    return new Promise((resolve) => {
        const modal = document.getElementById("modal-confirmar-eliminacion-producto");
        const botonConfirmar = document.getElementById("confirmar-eliminacion-producto");
        const botonCancelar = document.getElementById("cancelar-eliminacion-producto");
        document.getElementById("nombre-producto-a-eliminar").textContent =
            limpiarNombreProducto(producto?.producto) || "Producto seleccionado";

        const cerrar = (confirmado = false) => {
            modal.classList.add("hidden");
            document.body.classList.remove("modal-open");
            botonConfirmar.removeEventListener("click", confirmar);
            botonCancelar.removeEventListener("click", cancelar);
            resolve(confirmado);
        };
        const confirmar = () => cerrar(true);
        const cancelar = () => cerrar();

        botonConfirmar.addEventListener("click", confirmar);
        botonCancelar.addEventListener("click", cancelar);
        modal.classList.remove("hidden");
        document.body.classList.add("modal-open");
        botonCancelar.focus();
    });
}

function formatearFechaAuditoria(valor) {
    if (!valor) return "Sin fecha";
    const fecha = new Date(valor);
    return Number.isNaN(fecha.getTime())
        ? String(valor)
        : fecha.toLocaleString("es-MX", {
            dateStyle: "short",
            timeStyle: "short",
        });
}

function crearResumenValoresAuditoria(datos) {
    const contenedor = document.createElement("div");
    contenedor.className = "audit-readable-values";
    if (!datos || typeof datos !== "object") {
        contenedor.textContent = "No aplica";
        return contenedor;
    }
    const etiquetas = {
        linea: "Línea cárnica",
        nombre: "Nombre",
        cantidad_base: "Kilos registrados",
        porcentaje_merma: "Merma esperada",
        producto_base: "Producto base",
        producto_resultante_id: "Producto resultante",
        total_componentes: "Total de componentes",
        visible: "Visible en el catálogo",
        product_id: "Producto",
        componentes: "Productos e insumos",
    };
    Object.entries(datos).forEach(([clave, valor]) => {
        const fila = document.createElement("div");
        const etiqueta = document.createElement("span");
        etiqueta.textContent = etiquetas[clave] || clave.replaceAll("_", " ");
        const contenido = document.createElement("strong");
        if (clave === "porcentaje_merma" && Number.isFinite(Number(valor))) {
            contenido.textContent = `${Number(valor).toFixed(2)}%`;
        } else if (clave === "cantidad_base" && Number.isFinite(Number(valor))) {
            contenido.textContent = `${Number(valor).toFixed(2)} kg`;
        } else if (clave === "visible") {
            contenido.textContent = valor ? "Sí" : "No";
        } else if (Array.isArray(valor)) {
            contenido.textContent = valor.length
                ? `${valor.length} elemento${valor.length === 1 ? "" : "s"}`
                : "Sin elementos";
            if (valor.length) {
                const lista = document.createElement("ul");
                valor.forEach((elemento) => {
                    const item = document.createElement("li");
                    if (elemento && typeof elemento === "object") {
                        const cantidad = Number(elemento.cantidad || 0);
                        item.textContent = [
                            elemento.es_base ? "Producto base" : "Insumo",
                            elemento.producto || `Producto ${elemento.product_id || ""}`,
                            cantidad ? `${cantidad.toFixed(3)} ${elemento.unidad || ""}` : "",
                        ].filter(Boolean).join(" · ");
                    } else {
                        item.textContent = String(elemento);
                    }
                    lista.appendChild(item);
                });
                fila.append(etiqueta, contenido, lista);
                contenedor.appendChild(fila);
                return;
            }
        } else {
            contenido.textContent = String(valor ?? "No registrado");
        }
        fila.append(etiqueta, contenido);
        contenedor.appendChild(fila);
    });
    return contenedor;
}

function abrirDetalleAuditoria(registro) {
    const modal = document.getElementById("modal-detalle-auditoria");
    const contenido = document.getElementById("detalle-auditoria-contenido");
    document.getElementById("titulo-detalle-auditoria").textContent =
        registro.configuracion_nombre;
    contenido.replaceChildren();

    const resumen = document.createElement("div");
    resumen.className = "audit-detail-summary";
    [
        ["Acción", registro.accion],
        ["Usuario", registro.usuario_nombre],
        ["Fecha", formatearFechaAuditoria(registro.fecha)],
        ["Motivo", registro.motivo],
    ].forEach(([etiqueta, valor]) => {
        const bloque = document.createElement("div");
        const pequeno = document.createElement("small");
        pequeno.textContent = etiqueta;
        const fuerte = document.createElement("strong");
        fuerte.textContent = valor || "No registrado";
        bloque.append(pequeno, fuerte);
        resumen.appendChild(bloque);
    });

    const valores = document.createElement("div");
    valores.className = "audit-values-grid";
    [
        ["Valores anteriores", registro.valores_anteriores],
        ["Valores nuevos", registro.valores_nuevos],
    ].forEach(([titulo, datos]) => {
        const bloque = document.createElement("section");
        bloque.className = "audit-values";
        const encabezado = document.createElement("strong");
        encabezado.textContent = titulo;
        bloque.append(encabezado, crearResumenValoresAuditoria(datos));
        valores.appendChild(bloque);
    });
    contenido.append(resumen, valores);
    modal.classList.remove("hidden");
    document.body.classList.add("modal-open");
}

function renderizarAuditoriaConfiguracion() {
    const cuerpo = document.getElementById("filas-auditoria-configuracion");
    const total = document.getElementById("auditoria-total-registros");
    cuerpo.replaceChildren();
    if (total) {
        total.textContent =
            `${registrosAuditoriaConfiguracion.length} movimiento${registrosAuditoriaConfiguracion.length === 1 ? "" : "s"}`;
    }
    if (!registrosAuditoriaConfiguracion.length) {
        const fila = document.createElement("tr");
        const celda = document.createElement("td");
        celda.colSpan = 5;
        celda.className = "empty-table-cell";
        celda.textContent = "Todavía no hay cambios registrados.";
        fila.appendChild(celda);
        cuerpo.appendChild(fila);
        return;
    }
    registrosAuditoriaConfiguracion.forEach((registro) => {
        const fila = document.createElement("tr");
        const valores = [
            formatearFechaAuditoria(registro.fecha),
            registro.usuario_nombre,
            registro.accion,
            registro.configuracion_nombre,
        ];
        valores.forEach((valor, indice) => {
            const celda = document.createElement("td");
            if (indice === 2) {
                const insignia = document.createElement("span");
                insignia.className = `audit-action ${registro.accion}`;
                insignia.textContent = valor;
                celda.appendChild(insignia);
            } else {
                celda.textContent = valor || "—";
            }
            fila.appendChild(celda);
        });
        const acciones = document.createElement("td");
        const ver = document.createElement("button");
        ver.type = "button";
        ver.className = "button-outline";
        ver.textContent = "Ver detalle";
        ver.addEventListener("click", () => abrirDetalleAuditoria(registro));
        acciones.appendChild(ver);
        fila.appendChild(acciones);
        cuerpo.appendChild(fila);
    });
}

async function abrirAuditoriaConfiguracion() {
    mostrarVistaModulo("auditoria");
    document.getElementById("filas-auditoria-configuracion").innerHTML =
        '<tr><td colspan="5" class="empty-table-cell">Consultando auditoría...</td></tr>';
    try {
        registrosAuditoriaConfiguracion = await solicitarJson(
            `${API_CONFIGURACION}/auditoria?limite=100`
        );
        renderizarAuditoriaConfiguracion();
    } catch (error) {
        const cuerpo = document.getElementById("filas-auditoria-configuracion");
        const fila = document.createElement("tr");
        const celda = document.createElement("td");
        celda.colSpan = 5;
        celda.className = "empty-table-cell";
        celda.textContent = error.message;
        fila.appendChild(celda);
        cuerpo.replaceChildren(fila);
    }
}

function volverDesdeAuditoriaConfiguracion() {
    mostrarVistaModulo("configuracion");
}

function activarEliminacionCatalogo() {
    modoEliminacionCatalogo = true;
    productoCatalogoSeleccionadoId = 0;
    document.querySelectorAll(".catalog-product").forEach((producto) => {
        producto.classList.remove("selected");
    });
    document.getElementById("catalogo-productos").classList.add("delete-mode");
    document.getElementById("eliminar-producto-catalogo").classList.add("active");
    document.getElementById("eliminar-producto-catalogo").textContent = "Eliminando";
    document.getElementById("cancelar-eliminacion-catalogo").classList.remove("hidden");
    document.getElementById("ayuda-interaccion-catalogo").textContent =
        "Selecciona los productos que deseas ocultar. Presiona Cancelar para terminar.";
}

function cancelarEliminacionCatalogo() {
    modoEliminacionCatalogo = false;
    const panelCatalogo = document.getElementById("catalogo-productos");
    if (panelCatalogo) panelCatalogo.classList.remove("delete-mode");
    const eliminar = document.getElementById("eliminar-producto-catalogo");
    if (eliminar) {
        eliminar.classList.remove("active");
        eliminar.textContent = "Eliminar";
    }
    const botonCancelar = document.getElementById("cancelar-eliminacion-catalogo");
    if (botonCancelar) botonCancelar.classList.add("hidden");
    const ayuda = document.getElementById("ayuda-interaccion-catalogo");
    if (ayuda) ayuda.textContent = "Un clic selecciona el producto; doble clic muestra sus insumos.";
}

function cerrarCatalogoProductos() {
    cancelarEliminacionCatalogo();
    document.getElementById("catalogo-productos").classList.add("hidden");
    document.getElementById("configuraciones-guardadas").classList.remove("hidden");
    document.getElementById("buscar-producto-catalogo").value = "";
    document.getElementById("filtro-unidad-catalogo").value = "";
    document.getElementById("filtro-receta-catalogo").value = "";
    document.getElementById("filtro-antiguedad-catalogo").value = "";
    document.getElementById("filtros-catalogo").classList.add("hidden");
    document.getElementById("mostrar-filtros-catalogo").setAttribute("aria-expanded", "false");
    document.querySelectorAll(".configuration-line").forEach((boton) => boton.classList.remove("active"));
    lineaCatalogoActual = "";
    productosCatalogoActual = [];
    productosCatalogoSinFiltrar = [];
    productoCatalogoSeleccionadoId = 0;
    paginaCatalogoActual = 1;
}

async function cargarProductosConfiguracion() {
    const linea = document.getElementById("config-linea").value;
    const selector = document.getElementById("config-insumo-producto");
    const botonAsignar = document.getElementById("ir-asignar-insumos");
    cancelarCargaComponentesConfiguracion();
    cerrarAsignacionInsumosConfiguracion();
    document.getElementById("campo-config-insumo-producto").classList.add("hidden");
    componentesConfiguracion = [];
    proporcionesInsumosConfiguracion = new Map();
    cantidadFormulaBaseConfiguracion = 0;
    productosConfiguracionDisponibles = [];
    renderizarComponentesConfiguracion();
    if (!linea) {
        llenarConfigSelect(selector, [], "Selecciona primero una línea");
        botonAsignar.textContent = "Agregar insumos";
        document.getElementById("config-nombres-disponibles").replaceChildren();
        return;
    }
    try {
        botonAsignar.textContent = "Agregar insumos";
        llenarConfigSelect(selector, [], "Abre la asignación para consultar productos");
        const resultantes = await solicitarJson(
            `${API_CONFIGURACION}/productos-resultantes?linea=${encodeURIComponent(linea)}`
        );
        const nombres = document.getElementById("config-nombres-disponibles");
        nombres.replaceChildren();
        resultantes.forEach((producto) => {
            const opcion = document.createElement("option");
            opcion.value = producto.producto;
            nombres.appendChild(opcion);
        });
        limpiarMensajeConfiguracion();
    } catch (error) {
        mensajeConfiguracion(error.message);
    }
}

function recalcularCantidadesInsumosConfiguracion() {
    const kilos = Number(document.getElementById("config-cantidad-base").value || 0);
    componentesConfiguracion.forEach((componente) => {
        if (componente.es_base) {
            componente.cantidad = kilos;
            return;
        }
        if (Number(componente.cantidad_por_kilo || 0) > 0) {
            componente.cantidad = Number(
                (kilos * Number(componente.cantidad_por_kilo)).toFixed(6)
            );
            return;
        }
        const cantidadFormula = Number(
            componente.cantidad_formula
            || proporcionesInsumosConfiguracion.get(Number(componente.producto_id))
            || 0
        );
        if (cantidadFormula > 0 && cantidadFormulaBaseConfiguracion > 0) {
            componente.cantidad = Number(
                (kilos * cantidadFormula / cantidadFormulaBaseConfiguracion).toFixed(6)
            );
        }
    });

    const selector = document.getElementById("config-insumo-producto");
    const proporcionFormula = Number(
        proporcionesInsumosConfiguracion.get(Number(selector?.value || 0)) || 0
    );
    const productoSeleccionado = productosConfiguracionDisponibles.find(
        (producto) => Number(producto.product_id) === Number(selector?.value || 0)
    );
    const proporcionPorKilo = Number(
        productoSeleccionado?.cantidad_por_kilo || 0
    );
    const campoCantidad = document.getElementById("config-insumo-cantidad");
    const unidadCantidad = document.getElementById("config-insumo-unidad");
    const etiquetaCantidad = document.getElementById("config-insumo-cantidad-etiqueta");
    if (campoCantidad) {
        const usaFormula = (
            proporcionFormula > 0 && cantidadFormulaBaseConfiguracion > 0
        );
        const tieneProporcion = kilos > 0 && (usaFormula || proporcionPorKilo > 0);
        const cantidadCalculada = usaFormula
            ? kilos * proporcionFormula / cantidadFormulaBaseConfiguracion
            : kilos * proporcionPorKilo;
        const cantidadVisual = convertirCantidadParaMostrar(
            cantidadCalculada,
            productoSeleccionado?.unidad || "KILO"
        );
        campoCantidad.readOnly = true;
        campoCantidad.placeholder = tieneProporcion
            ? "Según los kilos"
            : (productoSeleccionado ? "Sin proporción en el sistema" : "Selecciona un insumo");
        if (tieneProporcion) {
            campoCantidad.value = cantidadVisual.cantidad.replace(/,/g, "");
        } else {
            campoCantidad.value = "";
        }
        if (etiquetaCantidad) {
            etiquetaCantidad.textContent = "Cantidad automática";
        }
        if (unidadCantidad) {
            unidadCantidad.textContent = cantidadCalculada > 0
                ? cantidadVisual.unidad
                : (productoSeleccionado?.unidad || "kg");
        }
    }
    renderizarComponentesConfiguracion();
}

async function cargarProporcionesFormulaConfiguracion() {
    const linea = document.getElementById("config-linea").value;
    const nombre = document.getElementById("config-nombre").value.trim();
    proporcionesInsumosConfiguracion = new Map();
    cantidadFormulaBaseConfiguracion = 0;
    if (!linea || nombre.length < 3) return false;

    const sugerencia = await solicitarJson(
        `${API_CONFIGURACION}/base-sugerida?linea=${encodeURIComponent(linea)}&nombre=${encodeURIComponent(nombre)}`
    );
    if (!sugerencia?.producto_resultante_id || !sugerencia?.producto_base_id) {
        return false;
    }
    const registros = await solicitarJson(
        `${API_CONFIGURACION}/formula/${Number(sugerencia.producto_resultante_id)}`
    );
    const formulaId = Number(sugerencia.producto_resultante_id);
    const formulaExacta = registros.filter(
        (componente) => Number(componente.formula_id) === formulaId
    );
    const componentesFormula = formulaExacta.length ? formulaExacta : registros;
    componentesFormula.forEach((componente) => {
        const productoId = Number(componente.product_id);
        const cantidad = Number(componente.cantidad || 0);
        if (productoId > 0 && cantidad > 0) {
            proporcionesInsumosConfiguracion.set(productoId, cantidad);
        }
    });
    cantidadFormulaBaseConfiguracion = Number(
        proporcionesInsumosConfiguracion.get(Number(sugerencia.producto_base_id)) || 0
    );
    if (cantidadFormulaBaseConfiguracion <= 0) {
        const componentesCarnicos = componentesFormula.filter(
            (componente) =>
                String(componente.linea || "").trim().toUpperCase() ===
                String(linea).trim().toUpperCase()
        );
        cantidadFormulaBaseConfiguracion = componentesCarnicos.reduce(
            (mayor, componente) => Math.max(mayor, Number(componente.cantidad || 0)),
            0
        );
    }
    if (cantidadFormulaBaseConfiguracion <= 0) return false;

    const base = componentesConfiguracion.find((componente) => componente.es_base);
    if (base) base.cantidad_formula = cantidadFormulaBaseConfiguracion;
    recalcularCantidadesInsumosConfiguracion();
    return true;
}

async function cargarComponentesParaAsignacion() {
    const linea = document.getElementById("config-linea").value;
    const selector = document.getElementById("config-insumo-producto");
    const boton = document.getElementById("ir-asignar-insumos");
    if (!linea) {
        mensajeConfiguracion("Selecciona primero una línea cárnica.");
        return false;
    }
    if (productosConfiguracionDisponibles.length) return true;

    controladorCargaComponentesConfiguracion?.abort();
    const controlador = new AbortController();
    controladorCargaComponentesConfiguracion = controlador;
    const temporizador = window.setTimeout(() => controlador.abort(), 12000);
    boton.classList.add("active");
    boton.textContent = "Cancelar carga de insumos";
    try {
        productosConfiguracionDisponibles = await solicitarJson(
            `${API_CONFIGURACION}/componentes?linea=${encodeURIComponent(linea)}`,
            { signal: controlador.signal }
        );
        llenarConfigSelect(
            selector,
            productosConfiguracionDisponibles,
            "Selecciona un producto o insumo"
        );
        if (!productosConfiguracionDisponibles.length) {
            mensajeConfiguracion("Esta línea no tiene productos disponibles en el sistema.");
            return false;
        }
        limpiarMensajeConfiguracion();
        return true;
    } catch (error) {
        productosConfiguracionDisponibles = [];
        llenarConfigSelect(selector, [], "No se pudieron cargar los productos");
        mensajeConfiguracion(
            error.name === "AbortError"
                ? "La consulta de productos tardó demasiado. Presiona nuevamente para reintentar."
                : error.message
        );
        return false;
    } finally {
        window.clearTimeout(temporizador);
        if (controladorCargaComponentesConfiguracion === controlador) {
            controladorCargaComponentesConfiguracion = null;
        }
        boton.classList.remove("active");
        boton.textContent = "Agregar insumos";
    }
}

async function agregarBaseSugeridaConfiguracion() {
    const linea = document.getElementById("config-linea").value;
    const nombre = document.getElementById("config-nombre").value.trim();
    if (!linea || nombre.length < 3 || !productosConfiguracionDisponibles.length) {
        return false;
    }
    try {
        const sugerencia = await solicitarJson(
            `${API_CONFIGURACION}/base-sugerida?linea=${encodeURIComponent(linea)}&nombre=${encodeURIComponent(nombre)}`
        );
        if (!sugerencia?.producto_base_id) return false;

        const baseExistente = componentesConfiguracion.find(
            (componente) => componente.es_base
        );
        if (baseExistente) {
            if (!baseExistente.es_sugerido) return true;
            if (
                Number(baseExistente.producto_id) ===
                Number(sugerencia.producto_base_id)
            ) {
                baseExistente.cantidad =
                    Number(document.getElementById("config-cantidad-base").value) ||
                    baseExistente.cantidad;
                renderizarComponentesConfiguracion();
                return true;
            }
            componentesConfiguracion = componentesConfiguracion.filter(
                (componente) => componente !== baseExistente
            );
        }

        const producto = productosConfiguracionDisponibles.find(
            (registro) =>
                Number(registro.product_id) === Number(sugerencia.producto_base_id)
        );
        if (!producto) return false;

        componentesConfiguracion.push({
            producto_id: Number(producto.product_id),
            producto: limpiarNombreProducto(producto.producto),
            cantidad: Number(document.getElementById("config-cantidad-base").value) || 1,
            unidad: producto.unidad || sugerencia.unidad || "KILO",
            es_base: true,
            es_sugerido: true,
        });
        renderizarComponentesConfiguracion();
        limpiarMensajeConfiguracion();
        return true;
    } catch (error) {
        console.error("No fue posible sugerir el producto base.", error);
        return false;
    }
}

function cancelarCargaComponentesConfiguracion() {
    controladorCargaComponentesConfiguracion?.abort();
    controladorCargaComponentesConfiguracion = null;
    const boton = document.getElementById("ir-asignar-insumos");
    if (boton) {
        boton.classList.remove("active");
        boton.textContent = "Agregar insumos";
    }
}

function cerrarAsignacionInsumosConfiguracion() {
    const seccion = document.getElementById("config-formula");
    const boton = document.getElementById("ir-asignar-insumos");
    if (!seccion || !boton) return;
    seccion.classList.add("hidden");
    boton.classList.remove("active");
    boton.textContent = "Agregar insumos";
    boton.setAttribute("aria-expanded", "false");
}

async function alternarAsignacionInsumosConfiguracion() {
    const seccion = document.getElementById("config-formula");
    const boton = document.getElementById("ir-asignar-insumos");
    const selector = document.getElementById("config-insumo-producto");
    if (controladorCargaComponentesConfiguracion) {
        cancelarCargaComponentesConfiguracion();
        productosConfiguracionDisponibles = [];
        llenarConfigSelect(selector, [], "Carga de productos cancelada");
        limpiarMensajeConfiguracion();
        return;
    }
    if (!seccion.classList.contains("hidden")) {
        cerrarAsignacionInsumosConfiguracion();
        boton.focus();
        return;
    }
    limpiarMensajeConfiguracion();
    if (!(await cargarComponentesParaAsignacion())) return;
    const baseRelacionada = await agregarBaseSugeridaConfiguracion();
    if (baseRelacionada) {
        await cargarProporcionesFormulaConfiguracion();
    }
    document.getElementById("campo-config-insumo-producto").classList.remove("hidden");
    if (baseRelacionada) {
        document.getElementById("config-insumo-tipo").value = "INSUMO";
    }
    if (!baseRelacionada) {
        mensajeConfiguracion(
            "No fue posible relacionar automáticamente el producto base. Revisa la línea y el nombre de la transformación."
        );
    }
    seccion.classList.remove("hidden");
    boton.classList.add("active");
    boton.textContent = "Ocultar insumos";
    boton.setAttribute("aria-expanded", "true");
    seccion.scrollIntoView({ behavior: "smooth", block: "start" });
    window.setTimeout(() => selector.focus(), 350);
}

function renderizarComponentesConfiguracion() {
    const cuerpo = document.getElementById("config-componentes");
    cuerpo.replaceChildren();
    if (!componentesConfiguracion.length) {
        const fila = document.createElement("tr");
        const celda = document.createElement("td");
        celda.colSpan = 5;
        celda.className = "empty-table-cell";
        celda.textContent = "Aún no agregas ingredientes.";
        fila.appendChild(celda);
        cuerpo.appendChild(fila);
        return;
    }
    componentesConfiguracion.forEach((componente) => {
        const fila = document.createElement("tr");
        const cantidadVisual = convertirCantidadParaMostrar(
            componente.cantidad,
            componente.unidad
        );
        [
            componente.producto,
            componente.es_base ? "Producto base" : "Insumo",
            cantidadVisual.cantidad,
            cantidadVisual.unidad,
        ].forEach((valor) => {
            const celda = document.createElement("td");
            celda.textContent = valor;
            fila.appendChild(celda);
        });
        const acciones = document.createElement("td");
        const quitar = document.createElement("button");
        quitar.type = "button";
        quitar.className = "button-outline button-compact";
        quitar.textContent = "Quitar";
        quitar.addEventListener("click", () => {
            componentesConfiguracion = componentesConfiguracion.filter(
                (elemento) => elemento.producto_id !== componente.producto_id
            );
            renderizarComponentesConfiguracion();
            guardarBorradorConfiguracion();
        });
        acciones.appendChild(quitar);
        fila.appendChild(acciones);
        cuerpo.appendChild(fila);
    });
}

function agregarComponenteConfiguracion() {
    const selector = document.getElementById("config-insumo-producto");
    const productoId = Number(selector.value || 0);
    const producto = productosConfiguracionDisponibles.find(
        (registro) => Number(registro.product_id) === productoId
    );
    const cantidadFormula = Number(
        proporcionesInsumosConfiguracion.get(productoId) || 0
    );
    const cantidadPorKilo = Number(producto?.cantidad_por_kilo || 0);
    const kilos = Number(document.getElementById("config-cantidad-base").value || 0);
    const usaFormula = (
        kilos > 0
        && cantidadFormula > 0
        && cantidadFormulaBaseConfiguracion > 0
    );
    const cantidadAutomatica = Number((
        usaFormula
            ? kilos * cantidadFormula / cantidadFormulaBaseConfiguracion
            : kilos * cantidadPorKilo
    ).toFixed(6));
    const esBase = document.getElementById("config-insumo-tipo").value === "BASE";
    const cantidad = esBase
        ? kilos
        : cantidadAutomatica;
    if (!producto || cantidad <= 0 || kilos <= 0) {
        mensajeConfiguracion(
            !producto
                ? "Selecciona un producto o insumo."
                : cantidadFormula <= 0 && cantidadPorKilo <= 0
                ? "El insumo seleccionado no tiene una proporción registrada en el sistema para esta transformación."
                : "Selecciona un insumo y captura kilos válidos para la transformación."
        );
        return;
    }
    if (componentesConfiguracion.some((componente) => componente.producto_id === productoId)) {
        mensajeConfiguracion("Ese producto ya forma parte de la transformación.");
        return;
    }
    if (esBase) {
        componentesConfiguracion.forEach((componente) => { componente.es_base = false; });
    }
    componentesConfiguracion.push({
        producto_id: productoId,
        producto: limpiarNombreProducto(producto.producto),
        cantidad,
        cantidad_formula: cantidadFormula,
        cantidad_por_kilo: usaFormula ? null : cantidadPorKilo,
        unidad: producto.unidad || "KILO",
        es_base: esBase,
    });
    selector.value = "";
    document.getElementById("config-insumo-cantidad").value = "";
    document.getElementById("config-insumo-cantidad").readOnly = true;
    document.getElementById("config-insumo-cantidad").placeholder = "Selecciona un insumo";
    document.getElementById("config-insumo-cantidad-etiqueta").textContent = "Cantidad automática";
    document.getElementById("config-insumo-tipo").value = "INSUMO";
    document.getElementById("config-insumo-unidad").textContent = "kg";
    limpiarMensajeConfiguracion();
    renderizarComponentesConfiguracion();
    guardarBorradorConfiguracion();
}

function abrirNuevaConfiguracion() {
    const formulario = document.getElementById("form-nueva-configuracion");
    formulario.classList.remove("hidden");
    document.getElementById("boton-nueva-configuracion").disabled = true;
    document.getElementById("config-linea").focus();
    formulario.scrollIntoView({ behavior: "smooth", block: "nearest" });
    guardarBorradorConfiguracion();
}

function transformacionPermiteMermaPersonalizada(nombre) {
    const nombreNormalizado = String(nombre || "").trim().toUpperCase();
    return nombreNormalizado.includes("MOLIDA")
        || nombreNormalizado.includes("MOLIDO");
}

function actualizarCampoMermaConfiguracion() {
    const nombre = document.getElementById("config-nombre").value;
    const campo = document.getElementById("campo-config-merma");
    const entrada = document.getElementById("config-merma");
    const permitePersonalizar = transformacionPermiteMermaPersonalizada(nombre);
    campo.classList.toggle("hidden", !permitePersonalizar);
    entrada.disabled = !permitePersonalizar;
    if (!permitePersonalizar) {
        entrada.value = String(MERMA_TECNICA_PORCENTAJE);
    }
}

function nuevaConfiguracionTieneDatos() {
    const linea = document.getElementById("config-linea").value;
    const nombre = document.getElementById("config-nombre").value.trim();
    const kilos = Number(document.getElementById("config-cantidad-base").value || 0);
    const merma = Number(document.getElementById("config-merma").value);
    const mermaFueModificada = transformacionPermiteMermaPersonalizada(nombre)
        && Number.isFinite(merma)
        && Math.abs(merma - MERMA_TECNICA_PORCENTAJE) > 0.0001;

    return Boolean(
        linea
        || nombre
        || kilos > 0
        || mermaFueModificada
        || componentesConfiguracion.length
        || configuracionesPendientes.length
        || indiceConfiguracionEnEdicion >= 0
    );
}

function cerrarConfirmacionCancelacionConfiguracion() {
    document.getElementById("modal-cancelar-configuracion").classList.add("hidden");
    document.body.classList.remove("modal-open");
}

function solicitarCancelacionNuevaConfiguracion() {
    if (!nuevaConfiguracionTieneDatos()) {
        cerrarNuevaConfiguracion();
        return;
    }

    document.getElementById("modal-cancelar-configuracion").classList.remove("hidden");
    document.body.classList.add("modal-open");
    document.getElementById("continuar-configuracion").focus();
}

function confirmarCancelacionNuevaConfiguracion() {
    cerrarConfirmacionCancelacionConfiguracion();
    cerrarNuevaConfiguracion();
}

function cerrarNuevaConfiguracion() {
    cancelarCargaComponentesConfiguracion();
    const formulario = document.getElementById("form-nueva-configuracion");
    formulario.reset();
    componentesConfiguracion = [];
    configuracionesPendientes = [];
    restablecerModoEdicionConfiguracion();
    productosConfiguracionDisponibles = [];
    llenarConfigSelect(document.getElementById("config-insumo-producto"), [], "Selecciona primero una línea");
    cerrarAsignacionInsumosConfiguracion();
    document.getElementById("campo-config-insumo-producto").classList.add("hidden");
    renderizarComponentesConfiguracion();
    renderizarConfiguracionesPendientes();
    limpiarMensajeConfiguracion();
    formulario.classList.add("hidden");
    eliminarLocal(CLAVE_BORRADOR_CONFIGURACION);
    document.getElementById("boton-nueva-configuracion").disabled = false;
    document.getElementById("boton-nueva-configuracion").focus();
}

function construirConfiguracionActual() {
    const formulario = document.getElementById("form-nueva-configuracion");
    if (!formulario.reportValidity()) return null;
    if (!componentesConfiguracion.length) {
        mensajeConfiguracion("Agrega por lo menos un producto o insumo.");
        return null;
    }
    if (componentesConfiguracion.filter((componente) => componente.es_base).length !== 1) {
        mensajeConfiguracion("Marca exactamente un ingrediente como producto base.");
        return null;
    }
    return {
        nombre: document.getElementById("config-nombre").value.trim(),
        linea: document.getElementById("config-linea").value,
        cantidad_base: Number(document.getElementById("config-cantidad-base").value),
        porcentaje_merma: transformacionPermiteMermaPersonalizada(
            document.getElementById("config-nombre").value
        )
            ? Number(document.getElementById("config-merma").value)
            : MERMA_TECNICA_PORCENTAJE,
        componentes: componentesConfiguracion.map((componente) => ({
            producto_id: componente.producto_id,
            producto: componente.producto,
            cantidad: componente.cantidad,
            unidad: componente.unidad,
            es_base: componente.es_base,
            cantidad_formula: componente.cantidad_formula || null,
            cantidad_por_kilo: componente.cantidad_por_kilo || null,
        })),
        observaciones: document.getElementById("config-observaciones").value.trim() || null,
    };
}

function renderizarConfiguracionesPendientes() {
    const panel = document.getElementById("configuraciones-pendientes");
    const lista = document.getElementById("lista-configuraciones-pendientes");
    panel.classList.toggle("hidden", !configuracionesPendientes.length);
    lista.replaceChildren();
    configuracionesPendientes.forEach((configuracion, indice) => {
        const base = configuracion.componentes.find((componente) => componente.es_base);
        const insumos = configuracion.componentes.filter(
            (componente) => !componente.es_base
        );
        const tarjeta = document.createElement("details");
        tarjeta.className = "configuration-capture-card";

        const resumen = document.createElement("summary");
        const numero = document.createElement("span");
        numero.className = "configuration-capture-number";
        numero.textContent = String(indice + 1);
        const identidad = document.createElement("div");
        identidad.className = "configuration-capture-identity";
        const nombre = document.createElement("strong");
        nombre.textContent = configuracion.nombre;
        const linea = document.createElement("small");
        linea.textContent = configuracion.linea;
        identidad.append(nombre, linea);
        const datos = document.createElement("div");
        datos.className = "configuration-capture-summary";
        const pesoVisual = convertirCantidadParaMostrar(
            configuracion.cantidad_base,
            "KILO"
        );
        [
            ["Producto base", base?.producto || "Sin base"],
            ["Peso", `${pesoVisual.cantidad} ${pesoVisual.unidad}`],
            ["Insumos", String(insumos.length)],
        ].forEach(([etiqueta, valor]) => {
            const bloque = document.createElement("span");
            const rotulo = document.createElement("small");
            const contenido = document.createElement("strong");
            rotulo.textContent = etiqueta;
            contenido.textContent = valor;
            bloque.append(rotulo, contenido);
            datos.appendChild(bloque);
        });
        const indicador = document.createElement("span");
        indicador.className = "configuration-capture-chevron";
        indicador.setAttribute("aria-hidden", "true");
        indicador.textContent = "⌄";
        resumen.append(numero, identidad, datos, indicador);

        const detalle = document.createElement("div");
        detalle.className = "configuration-capture-detail";
        const componentes = document.createElement("div");
        componentes.className = "configuration-capture-components";
        configuracion.componentes.forEach((componente) => {
            const renglon = document.createElement("div");
            const tipo = document.createElement("span");
            const producto = document.createElement("strong");
            const cantidad = document.createElement("b");
            tipo.textContent = componente.es_base ? "Producto base" : "Insumo";
            producto.textContent = componente.producto;
            const cantidadVisual = convertirCantidadParaMostrar(
                componente.cantidad,
                componente.unidad
            );
            cantidad.textContent = `${cantidadVisual.cantidad} ${cantidadVisual.unidad}`;
            renglon.append(tipo, producto, cantidad);
            componentes.appendChild(renglon);
        });
        const acciones = document.createElement("div");
        acciones.className = "configuration-capture-actions";
        const editar = document.createElement("button");
        editar.type = "button";
        editar.className = "button-outline button-compact";
        editar.textContent = "Editar captura";
        editar.addEventListener("click", () => editarConfiguracionPendiente(indice));
        const quitar = document.createElement("button");
        quitar.type = "button";
        quitar.className = "button-outline button-compact";
        quitar.textContent = "Quitar captura";
        quitar.addEventListener("click", () => {
            configuracionesPendientes.splice(indice, 1);
            renderizarConfiguracionesPendientes();
            guardarBorradorConfiguracion();
        });
        acciones.append(editar, quitar);
        detalle.append(componentes, acciones);
        tarjeta.append(resumen, detalle);
        lista.appendChild(tarjeta);
    });
    document.getElementById("total-configuraciones-pendientes").textContent =
        `${configuracionesPendientes.length} transformación${configuracionesPendientes.length === 1 ? "" : "es"}`;
}

function restablecerModoEdicionConfiguracion() {
    indiceConfiguracionEnEdicion = -1;
    const boton = document.getElementById("agregar-configuracion-lote");
    if (boton) boton.textContent = "Agregar otra";
}

function limpiarCapturaConfiguracion() {
    document.getElementById("config-nombre").value = "";
    document.getElementById("config-cantidad-base").value = "";
    document.getElementById("config-merma").value = String(MERMA_TECNICA_PORCENTAJE);
    actualizarCampoMermaConfiguracion();
    document.getElementById("config-observaciones").value = "";
    componentesConfiguracion = [];
    proporcionesInsumosConfiguracion = new Map();
    cantidadFormulaBaseConfiguracion = 0;
    restablecerModoEdicionConfiguracion();
    cerrarAsignacionInsumosConfiguracion();
    renderizarComponentesConfiguracion();
    document.getElementById("config-nombre").focus();
}

async function editarConfiguracionPendiente(indice) {
    const configuracion = configuracionesPendientes[indice];
    if (!configuracion) return;

    indiceConfiguracionEnEdicion = indice;
    document.getElementById("config-linea").value = configuracion.linea;
    await cargarProductosConfiguracion();
    indiceConfiguracionEnEdicion = indice;
    document.getElementById("config-nombre").value = configuracion.nombre;
    document.getElementById("config-cantidad-base").value = configuracion.cantidad_base;
    document.getElementById("config-merma").value = configuracion.porcentaje_merma;
    actualizarCampoMermaConfiguracion();
    document.getElementById("config-observaciones").value = configuracion.observaciones || "";

    await cargarComponentesParaAsignacion();
    componentesConfiguracion = configuracion.componentes.map((componente) => ({
        ...componente,
    }));
    await cargarProporcionesFormulaConfiguracion();
    renderizarComponentesConfiguracion();
    document.getElementById("campo-config-insumo-producto").classList.remove("hidden");
    document.getElementById("config-formula").classList.remove("hidden");
    const botonInsumos = document.getElementById("ir-asignar-insumos");
    botonInsumos.classList.add("active");
    botonInsumos.textContent = "Ocultar insumos";
    botonInsumos.setAttribute("aria-expanded", "true");
    document.getElementById("agregar-configuracion-lote").textContent = "Guardar edición";
    mensajeConfiguracion(
        `Editando captura ${indice + 1}. Revisa los datos y guarda la edición.`,
        "success"
    );
    document.getElementById("config-nombre").scrollIntoView({
        behavior: "smooth",
        block: "center",
    });
}

function solicitarConfirmacionEdicionConfiguracion(configuracion) {
    return new Promise((resolve) => {
        const modal = document.getElementById("modal-confirmar-edicion-configuracion");
        const confirmar = document.getElementById("confirmar-edicion-configuracion");
        const cancelar = document.getElementById("cancelar-edicion-configuracion");
        document.getElementById("nombre-configuracion-a-editar").textContent =
            configuracion.nombre;

        const cerrar = (aceptada) => {
            modal.classList.add("hidden");
            document.body.classList.remove("modal-open");
            confirmar.removeEventListener("click", aceptar);
            cancelar.removeEventListener("click", rechazar);
            resolve(aceptada);
        };
        const aceptar = () => cerrar(true);
        const rechazar = () => cerrar(false);
        confirmar.addEventListener("click", aceptar);
        cancelar.addEventListener("click", rechazar);
        modal.classList.remove("hidden");
        document.body.classList.add("modal-open");
        cancelar.focus();
    });
}

async function guardarEdicionConfiguracionPendiente() {
    const configuracion = construirConfiguracionActual();
    if (!configuracion || indiceConfiguracionEnEdicion < 0) return false;
    const repetida = configuracionesPendientes.some(
        (pendiente, indice) =>
            indice !== indiceConfiguracionEnEdicion
            && pendiente.linea.toUpperCase() === configuracion.linea.toUpperCase()
            && pendiente.nombre.toUpperCase() === configuracion.nombre.toUpperCase()
    );
    if (repetida) {
        mensajeConfiguracion("Esa transformación ya está en la lista por guardar.");
        return false;
    }
    if (!(await solicitarConfirmacionEdicionConfiguracion(configuracion))) {
        return false;
    }
    const indiceEditado = indiceConfiguracionEnEdicion;
    configuracionesPendientes[indiceEditado] = configuracion;
    renderizarConfiguracionesPendientes();
    limpiarCapturaConfiguracion();
    guardarBorradorConfiguracion();
    mensajeConfiguracion(
        `La captura ${indiceEditado + 1} se actualizó correctamente.`,
        "success"
    );
    return true;
}

function agregarConfiguracionPendiente() {
    const configuracion = construirConfiguracionActual();
    if (!configuracion) return false;
    const repetida = configuracionesPendientes.some(
        (pendiente) =>
            pendiente.linea.toUpperCase() === configuracion.linea.toUpperCase()
            && pendiente.nombre.toUpperCase() === configuracion.nombre.toUpperCase()
    );
    if (repetida) {
        mensajeConfiguracion("Esa transformación ya está en la lista por guardar.");
        return false;
    }
    configuracionesPendientes.push(configuracion);
    renderizarConfiguracionesPendientes();
    limpiarCapturaConfiguracion();
    guardarBorradorConfiguracion();
    mensajeConfiguracion(
        "Transformación agregada. Puedes capturar otra o guardar todas.",
        "success"
    );
    return true;
}

async function guardarNuevaConfiguracion(evento) {
    evento?.preventDefault();
    const boton = document.getElementById("guardar-configuracion");
    const hayCapturaActual = Boolean(
        document.getElementById("config-nombre").value.trim()
        || document.getElementById("config-cantidad-base").value
        || componentesConfiguracion.length
    );
    if (hayCapturaActual) {
        const capturaLista = indiceConfiguracionEnEdicion >= 0
            ? await guardarEdicionConfiguracionPendiente()
            : agregarConfiguracionPendiente();
        if (!capturaLista) return;
    }
    if (!configuracionesPendientes.length) {
        mensajeConfiguracion("Captura o agrega por lo menos una transformación.");
        return;
    }
    boton.disabled = true;
    boton.textContent = "Guardando todas...";
    const configuracionesGuardadas = configuracionesPendientes.map(
        (configuracion) => ({ ...configuracion })
    );
    try {
        await solicitarJson(`${API_CONFIGURACION}/transformaciones/lote`, {
            method: "POST",
            body: JSON.stringify(configuracionesPendientes.map((configuracion) => ({
                ...configuracion,
                componentes: configuracion.componentes.map((componente) => ({
                    producto_id: componente.producto_id,
                    cantidad: componente.cantidad,
                    unidad: componente.unidad,
                    es_base: componente.es_base,
                })),
            }))),
        });
        registrarNotificacionesConfiguraciones(configuracionesGuardadas);
        configuracionesPendientes = [];
        eliminarLocal(CLAVE_BORRADOR_CONFIGURACION);
        renderizarConfiguracionesPendientes();
        mensajeConfiguracion(
            "Las configuraciones se guardaron y ya están disponibles en el catálogo.",
            "success"
        );
        window.setTimeout(() => window.location.reload(), 900);
    } catch (error) {
        mensajeConfiguracion(error.message);
        boton.disabled = false;
        boton.textContent = "Guardar todas";
    }
}

function iniciarPaginaConfiguracion() {
    const formulario = document.getElementById("form-nueva-configuracion");
    if (formulario) {
        document.getElementById("boton-nueva-configuracion").addEventListener("click", abrirNuevaConfiguracion);
        document.getElementById("cancelar-nueva-configuracion").addEventListener(
            "click",
            solicitarCancelacionNuevaConfiguracion
        );
        document.getElementById("continuar-configuracion").addEventListener(
            "click",
            cerrarConfirmacionCancelacionConfiguracion
        );
        document.getElementById("confirmar-cancelacion-configuracion").addEventListener(
            "click",
            confirmarCancelacionNuevaConfiguracion
        );
        document.getElementById("config-linea").addEventListener("change", cargarProductosConfiguracion);
        document.getElementById("config-nombre").addEventListener(
            "input",
            actualizarCampoMermaConfiguracion
        );
        document.getElementById("config-nombre").addEventListener("change", async () => {
            actualizarCampoMermaConfiguracion();
            if (!document.getElementById("config-formula").classList.contains("hidden")) {
                const baseRelacionada = await agregarBaseSugeridaConfiguracion();
                document.getElementById("campo-config-insumo-producto").classList.remove("hidden");
                if (baseRelacionada) {
                    document.getElementById("config-insumo-tipo").value = "INSUMO";
                    await cargarProporcionesFormulaConfiguracion();
                }
            }
        });
        actualizarCampoMermaConfiguracion();
        document.getElementById("config-cantidad-base").addEventListener(
            "input",
            recalcularCantidadesInsumosConfiguracion
        );
        document.getElementById("ir-asignar-insumos").addEventListener(
            "click",
            alternarAsignacionInsumosConfiguracion
        );
        document.getElementById("config-insumo-producto").addEventListener("change", (evento) => {
            const producto = productosConfiguracionDisponibles.find(
                (registro) => Number(registro.product_id) === Number(evento.target.value)
            );
            document.getElementById("config-insumo-unidad").textContent =
                producto?.unidad || "kg";
            document.getElementById("config-insumo-cantidad").value = "";
            if (!producto) {
                limpiarMensajeConfiguracion();
                recalcularCantidadesInsumosConfiguracion();
                return;
            }
            recalcularCantidadesInsumosConfiguracion();
            if (
                producto
                && (
                    proporcionesInsumosConfiguracion.has(Number(producto.product_id))
                    || Number(producto.cantidad_por_kilo || 0) > 0
                )
            ) {
                limpiarMensajeConfiguracion();
            }
        });
        document.getElementById("agregar-config-insumo").addEventListener("click", agregarComponenteConfiguracion);
        document.getElementById("agregar-configuracion-lote").addEventListener(
            "click",
            async () => {
                if (indiceConfiguracionEnEdicion >= 0) {
                    await guardarEdicionConfiguracionPendiente();
                    return;
                }
                agregarConfiguracionPendiente();
            }
        );
        document.getElementById("guardar-configuracion").addEventListener(
            "click",
            guardarNuevaConfiguracion
        );
        formulario.addEventListener("submit", guardarNuevaConfiguracion);
        formulario.addEventListener("input", guardarBorradorConfiguracion);
        formulario.addEventListener("change", guardarBorradorConfiguracion);
    }
    document.getElementById("boton-auditoria-configuracion")?.addEventListener(
        "click",
        abrirAuditoriaConfiguracion
    );
    document.getElementById("actualizar-auditoria-configuracion")?.addEventListener(
        "click",
        abrirAuditoriaConfiguracion
    );
    document.getElementById("volver-configuracion-auditoria")?.addEventListener(
        "click",
        volverDesdeAuditoriaConfiguracion
    );
    document.getElementById("cerrar-detalle-auditoria")?.addEventListener(
        "click",
        () => {
            document.getElementById("modal-detalle-auditoria").classList.add("hidden");
            document.body.classList.remove("modal-open");
        }
    );
    document.querySelectorAll(".configuration-line").forEach((boton) => {
        boton.addEventListener("click", async () => {
            cancelarEliminacionCatalogo();
            document.getElementById("buscar-producto-catalogo").value = "";
            await cargarProductosCatalogo(boton.dataset.linea);
            marcarNotificacionesLineaComoVistas(boton.dataset.linea);
        });
    });
    aplicarNotificacionesConfiguraciones();
    document.getElementById("cerrar-catalogo-productos").addEventListener("click", cerrarCatalogoProductos);
    document.getElementById("eliminar-producto-catalogo")?.addEventListener(
        "click",
        activarEliminacionCatalogo
    );
    document.getElementById("cancelar-eliminacion-catalogo")?.addEventListener(
        "click",
        cancelarEliminacionCatalogo
    );
    document.getElementById("cerrar-detalle-producto").addEventListener("click", () => {
        document.getElementById("modal-detalle-producto").classList.add("hidden");
    });
    document.getElementById("catalogo-pagina-anterior").addEventListener("click", () => cambiarPaginaCatalogo(-1));
    document.getElementById("catalogo-pagina-siguiente").addEventListener("click", () => cambiarPaginaCatalogo(1));
    document.getElementById("buscar-producto-catalogo").addEventListener("input", () => {
        window.clearTimeout(temporizadorCatalogo);
        temporizadorCatalogo = window.setTimeout(() => {
            if (lineaCatalogoActual) aplicarFiltrosCatalogo();
        }, 250);
    });
    document.getElementById("filtro-unidad-catalogo").addEventListener(
        "change",
        aplicarFiltrosCatalogo
    );
    document.getElementById("filtro-receta-catalogo").addEventListener(
        "change",
        aplicarFiltrosCatalogo
    );
    document.getElementById("filtro-antiguedad-catalogo").addEventListener(
        "change",
        aplicarFiltrosCatalogo
    );
    document.getElementById("mostrar-filtros-catalogo").addEventListener(
        "click",
        alternarFiltrosCatalogo
    );
    document.getElementById("limpiar-filtros-catalogo").addEventListener(
        "click",
        limpiarFiltrosCatalogo
    );
}

function normalizarRegistroHistorial(registro) {
    const entrada = Number(registro["cantidad_base"] || 0);
    const salida = Number(registro["cantidad_resultante"] || 0);
    const merma = Math.max(entrada - salida, 0);
    const porcentajeMerma = entrada > 0 ? merma / entrada * 100 : 0;
    return { ...registro, entrada, salida, merma, porcentajeMerma };
}

function crearFilaHistorial(registroOriginal) {
    const registro = normalizarRegistroHistorial(registroOriginal);
    const fila = document.createElement("tr");
    fila.className = "history-row";
    fila.dataset.relacionId = String(registro["relacion_id"]);
    fila.tabIndex = 0;
    fila.title = "Ver documentos relacionados";
    const fecha = registro["fecha_hora"] ? new Date(registro["fecha_hora"]) : null;
    const fechaTexto = fecha && !Number.isNaN(fecha.getTime())
        ? fecha.toLocaleDateString("es-MX")
        : "Sin fecha";
    const horaTexto = fecha && !Number.isNaN(fecha.getTime())
        ? fecha.toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit" })
        : "";
    fila.innerHTML = `
        <td><span class="history-date"></span><small></small></td>
        <td><strong></strong><small></small></td>
        <td><strong></strong><small class="history-origin-detail"></small></td>
        <td class="history-number">${formatearPesoHistorial(registro.entrada)}</td>
        <td class="history-number">${formatearPesoHistorial(registro.salida)}</td>
        <td class="history-number"><strong>${formatearPesoHistorial(registro.merma)}</strong><small>${registro.porcentajeMerma.toFixed(1)}%</small></td>
        <td><strong></strong></td>
        <td><span class="history-folios"></span></td>
        <td><span class="history-status">Relacionado</span></td>`;
    fila.children[0].querySelector("span").textContent = fechaTexto;
    fila.children[0].querySelector("small").textContent = horaTexto;
    fila.children[1].querySelector("strong").textContent = registro["tablajero"] || "No registrado";
    fila.children[1].querySelector("small").textContent = registro["usuario"] || "Sin usuario";
    fila.children[2].querySelector("strong").textContent = limpiarNombreProducto(registro["producto_base"]) || "No disponible";
    const detalleOrigen = fila.children[2].querySelector(".history-origin-detail");
    if (registro["es_documento_lote"]) {
        detalleOrigen.textContent = "Movimiento por lote";
    } else if (Number(registro["total_insumos"] || 0)) {
        detalleOrigen.textContent = `${Number(registro["total_insumos"])} insumos`;
    } else {
        detalleOrigen.remove();
    }
    fila.children[6].querySelector("strong").textContent = limpiarNombreProducto(registro["producto_resultante"]) || "No disponible";
    fila.children[7].querySelector("span").textContent = `${registro["folio_salida"] || "Sin folio"} → ${registro["folio_entrada"] || "Sin folio"}`;
    const abrir = () => void abrirDetalleHistorial(Number(registro["relacion_id"]));
    fila.addEventListener("click", abrir);
    fila.addEventListener("keydown", (evento) => {
        if (evento.key === "Enter" || evento.key === " ") {
            evento.preventDefault();
            abrir();
        }
    });
    return fila;
}

function renderizarFilasHistorial() {
    const cuerpo = document.getElementById("filas-historial");
    if (!cuerpo) return;
    cuerpo.replaceChildren();
    registrosHistorialActual.forEach((registro) => {
        cuerpo.appendChild(crearFilaHistorial(registro));
    });
    if (!registrosHistorialActual.length) {
        const fila = document.createElement("tr");
        fila.innerHTML = '<td colspan="9" class="history-empty">No se encontraron transformaciones con estos filtros.</td>';
        cuerpo.appendChild(fila);
    }
    renderizarPaginaHistorial();
}

function actualizarResumenHistorial(resumenServidor = null) {
    const datos = registrosHistorialActual.map(normalizarRegistroHistorial);
    const kilos = resumenServidor
        ? Number(resumenServidor.kilos_procesados || 0)
        : datos.reduce((total, registro) => total + registro.entrada, 0);
    const salida = datos.reduce((total, registro) => total + registro.salida, 0);
    const merma = resumenServidor
        ? Number(resumenServidor.merma_acumulada || 0)
        : Math.max(kilos - salida, 0);
    const rendimiento = resumenServidor
        ? Number(resumenServidor.rendimiento || 0)
        : (kilos > 0 ? salida / kilos * 100 : 0);
    const pesoProcesado = separarPesoHistorial(kilos);
    const mermaAcumulada = separarPesoHistorial(merma);
    const valores = {
        "historial-kpi-transformaciones": String(
            resumenServidor?.transformaciones ?? totalRegistrosHistorial
        ),
        "historial-kpi-kilos": pesoProcesado.valor,
        "historial-kpi-kilos-unidad": pesoProcesado.unidad,
        "historial-kpi-merma": mermaAcumulada.valor,
        "historial-kpi-merma-unidad": mermaAcumulada.unidad,
        "historial-kpi-rendimiento": rendimiento.toFixed(1),
    };
    Object.entries(valores).forEach(([id, valor]) => {
        const elemento = document.getElementById(id);
        if (elemento) elemento.textContent = valor;
    });
}

function renderizarPaginaHistorial() {
    const paginacion = document.getElementById("paginacion-historial");
    if (!paginacion) return;

    paginaHistorialActual = Math.min(
        Math.max(paginaHistorialActual, 1),
        totalPaginasHistorial
    );

    document.getElementById("historial-pagina-actual").textContent =
        `Página ${paginaHistorialActual} de ${totalPaginasHistorial} (${totalRegistrosHistorial} registros)`;
    document.getElementById("historial-pagina-anterior").disabled = paginaHistorialActual <= 1;
    document.getElementById("historial-pagina-siguiente").disabled =
        paginaHistorialActual >= totalPaginasHistorial;
    paginacion.classList.toggle("hidden", totalPaginasHistorial <= 1);
}

function cambiarPaginaHistorial(desplazamiento) {
    const paginaNueva = paginaHistorialActual + desplazamiento;
    if (paginaNueva < 1 || paginaNueva > totalPaginasHistorial) return;
    paginaHistorialActual = paginaNueva;
    void consultarHistorialFiltrado({ actualizarResumen: false });
}

function fechaLocalISO(fecha = new Date()) {
    const anio = fecha.getFullYear();
    const mes = String(fecha.getMonth() + 1).padStart(2, "0");
    const dia = String(fecha.getDate()).padStart(2, "0");
    return `${anio}-${mes}-${dia}`;
}

function configurarRangoFechasHistorial() {
    const fechaDesde = document.getElementById("historial-fecha-desde");
    const fechaHasta = document.getElementById("historial-fecha-hasta");
    if (!fechaDesde || !fechaHasta) return;

    const fechaActual = fechaLocalISO();
    const hoy = new Date();
    const inicioMes = fechaLocalISO(
        new Date(hoy.getFullYear(), hoy.getMonth(), 1)
    );
    fechaDesde.value = fechaActual;
    fechaDesde.max = fechaActual;
    fechaHasta.max = fechaActual;
    if (!fechaHasta.value || fechaHasta.value > fechaActual) {
        fechaHasta.value = inicioMes;
    }
    fechaHasta.setCustomValidity("");
}

function rangoFechasHistorialValido() {
    const fechaDesde = document.getElementById("historial-fecha-desde");
    const fechaHasta = document.getElementById("historial-fecha-hasta");
    if (!fechaDesde || !fechaHasta) return true;

    const rangoValido = !fechaHasta.value || fechaHasta.value <= fechaDesde.value;
    fechaHasta.setCustomValidity(
        rangoValido ? "" : "La fecha Hasta debe ser igual o anterior a la fecha Desde."
    );
    if (!rangoValido) fechaHasta.reportValidity();
    return rangoValido;
}

function conectarControlesHistorial() {
    configurarRangoFechasHistorial();
    document.getElementById("exportar-historial")?.addEventListener(
        "click",
        exportarHistorialExcel
    );
    document.getElementById("historial-pagina-anterior")?.addEventListener(
        "click",
        () => cambiarPaginaHistorial(-1)
    );
    document.getElementById("historial-pagina-siguiente")?.addEventListener(
        "click",
        () => cambiarPaginaHistorial(1)
    );
    document.getElementById("mostrar-filtros-historial")?.addEventListener("click", () => {
        const panel = document.getElementById("filtros-historial");
        const abrir = panel.classList.contains("hidden");
        panel.classList.toggle("hidden", !abrir);
        document.getElementById("mostrar-filtros-historial")
            .setAttribute("aria-expanded", String(abrir));
    });
    document.getElementById("filtros-historial")?.addEventListener("submit", (evento) => {
        evento.preventDefault();
        if (!rangoFechasHistorialValido()) return;
        paginaHistorialActual = 1;
        void consultarHistorialFiltrado();
    });
    document.getElementById("limpiar-filtros-historial")?.addEventListener("click", () => {
        document.getElementById("filtros-historial").reset();
        configurarRangoFechasHistorial();
        paginaHistorialActual = 1;
        void consultarHistorialFiltrado();
    });
}

async function actualizarHistorialDesdeServidor() {
    if (!document.getElementById("vista-historial")) return;
    paginaHistorialActual = 1;
    await consultarHistorialFiltrado();
}

function parametrosFiltrosHistorial() {
    const parametros = new URLSearchParams({
        pagina: String(paginaHistorialActual),
        limite: String(HISTORIAL_POR_PAGINA),
    });
    const desdeVisual = document.getElementById("historial-fecha-desde")?.value;
    const hastaVisual = document.getElementById("historial-fecha-hasta")?.value;
    const transformacion = document.getElementById("historial-transformacion")?.value?.trim();

    // En pantalla el rango se recorre desde hoy hacia una fecha anterior.
    // SQL espera primero la fecha menor y después la fecha mayor.
    if (hastaVisual) parametros.set("fecha_desde", hastaVisual);
    if (desdeVisual) parametros.set("fecha_hasta", desdeVisual);
    if (transformacion) parametros.set("transformacion", transformacion);
    return parametros;
}

async function consultarHistorialFiltrado({ actualizarResumen = true } = {}) {
    const cuerpo = document.getElementById("filas-historial");
    if (!cuerpo) return;
    cuerpo.innerHTML = '<tr><td colspan="9" class="history-empty">Consultando movimientos...</td></tr>';
    try {
        const parametros = parametrosFiltrosHistorial();
        const respuesta = await solicitarJson(
            `${API_RELACIONES}/historial?${parametros.toString()}`
        );
        registrosHistorialActual = Array.isArray(respuesta)
            ? respuesta
            : (respuesta.registros || []);
        totalRegistrosHistorial = Number(
            respuesta.total_registros ?? registrosHistorialActual.length
        );
        totalPaginasHistorial = Math.max(Number(respuesta.total_paginas || 1), 1);
        paginaHistorialActual = Number(respuesta.pagina || paginaHistorialActual);
        historialCargadoDesdeServidor = true;
        renderizarFilasHistorial();
        const resumen = document.getElementById("resumen-filtros-historial");
        const filtrosAplicados = [...parametros.keys()].filter(
            (nombre) => !["limite", "pagina"].includes(nombre)
        ).length;
        resumen.textContent = filtrosAplicados
            ? `${totalRegistrosHistorial} registros encontrados con ${filtrosAplicados} ${filtrosAplicados === 1 ? "filtro" : "filtros"}.`
            : `${totalRegistrosHistorial} transformaciones disponibles.`;
        resumen.classList.remove("hidden");
        if (actualizarResumen) {
            const parametrosResumen = new URLSearchParams(parametros);
            parametrosResumen.delete("pagina");
            parametrosResumen.delete("limite");
            void solicitarJson(
                `${API_RELACIONES}/historial-resumen?${parametrosResumen.toString()}`
            ).then(actualizarResumenHistorial).catch((error) => {
                console.warn("No fue posible actualizar los indicadores del historial.", error);
            });
        }
    } catch (error) {
        registrosHistorialActual = [];
        const fila = document.createElement("tr");
        const celda = document.createElement("td");
        celda.colSpan = 9;
        celda.className = "history-empty";
        celda.textContent = error.message;
        fila.appendChild(celda);
        cuerpo.replaceChildren(fila);
    }
}

function crearDocumentoDetalleHistorial(titulo, folio, partidas, tipo, esDocumentoLote = false) {
    const partidasDocumento = Array.isArray(partidas) ? partidas : [];
    const tarjeta = document.createElement("article");
    tarjeta.className = `history-detail-document history-detail-${tipo}`;
    const encabezado = document.createElement("header");
    const identidad = document.createElement("div");
    identidad.className = "history-detail-document-identity";
    const paso = document.createElement("span");
    paso.className = "history-detail-step";
    paso.textContent = tipo === "out" ? "1" : "2";
    const textos = document.createElement("div");
    const etiqueta = document.createElement("small");
    etiqueta.textContent = titulo;
    const folioElemento = document.createElement("strong");
    folioElemento.textContent = folio || "Sin folio";
    textos.append(etiqueta, folioElemento);
    identidad.append(paso, textos);
    const totalPartidas = document.createElement("span");
    totalPartidas.className = "history-detail-item-count";
    totalPartidas.textContent = `${partidasDocumento.length} partida${partidasDocumento.length === 1 ? "" : "s"}`;
    encabezado.append(identidad, totalPartidas);
    tarjeta.appendChild(encabezado);

    const tabla = document.createElement("table");
    tabla.className = "registration-table";
    tabla.innerHTML = "<thead><tr><th>Producto</th><th>Cantidad</th></tr></thead>";
    const cuerpo = document.createElement("tbody");
    partidasDocumento.forEach((partida) => {
        const fila = document.createElement("tr");
        const producto = document.createElement("td");
        producto.textContent = limpiarNombreProducto(partida.ProductName) || "Producto";
        const cantidad = document.createElement("td");
        const cantidadVisual = convertirCantidadParaMostrar(
            partida.Quantity,
            partida.Unit || "UNIDAD"
        );
        cantidad.textContent = `${cantidadVisual.cantidad} ${cantidadVisual.unidad}`;
        fila.append(producto, cantidad);
        cuerpo.appendChild(fila);
    });
    if (!cuerpo.children.length) {
        const fila = document.createElement("tr");
        const vacio = document.createElement("td");
        vacio.colSpan = 2;
        vacio.className = "empty-table-cell";
        vacio.textContent = "El documento no tiene partidas disponibles.";
        fila.appendChild(vacio);
        cuerpo.appendChild(fila);
    }
    tabla.appendChild(cuerpo);
    const envoltura = document.createElement("div");
    envoltura.className = "registration-table-wrap";
    envoltura.appendChild(tabla);
    tarjeta.appendChild(envoltura);

    const total = document.createElement("footer");
    const etiquetaTotal = document.createElement("span");
    etiquetaTotal.textContent = esDocumentoLote ? "Peso total del lote:" : "Total del documento:";
    const cantidadTotalElemento = document.createElement("strong");
    const todasEnKilos = partidasDocumento.every((partida) =>
        ["KILO", "KILOS", "KG"].includes(String(partida.Unit || "").trim().toUpperCase())
    );
    if (todasEnKilos) {
        const cantidadTotal = partidasDocumento.reduce(
            (acumulado, partida) => acumulado + Number(partida.Quantity || 0),
            0
        );
        cantidadTotalElemento.textContent = formatearPesoHistorial(cantidadTotal);
    } else {
        cantidadTotalElemento.textContent = `${partidasDocumento.length} partidas con unidades diferentes`;
    }
    total.append(etiquetaTotal, cantidadTotalElemento);
    tarjeta.appendChild(total);
    return tarjeta;
}

function crearConexionDetalleHistorial() {
    const conexion = document.createElement("div");
    conexion.className = "history-detail-connector";
    const flecha = document.createElement("span");
    flecha.textContent = "→";
    flecha.setAttribute("aria-hidden", "true");
    const etiqueta = document.createElement("small");
    etiqueta.textContent = "Relacionado";
    conexion.append(flecha, etiqueta);
    return conexion;
}

async function abrirDetalleHistorial(relacionId) {
    const modal = document.getElementById("modal-detalle-historial");
    const contenido = document.getElementById("detalle-historial-contenido");
    contenido.innerHTML = '<p class="catalog-loading">Cargando...</p>';
    modal.classList.remove("hidden");
    try {
        const detalle = await solicitarJson(`${API_RELACIONES}/historial/${relacionId}`);
        document.getElementById("titulo-detalle-historial").textContent =
            `${detalle.folio_salida} → ${detalle.folio_entrada}`;
        const elementos = [];
        if (detalle.es_documento_lote) {
            const aviso = document.createElement("div");
            aviso.className = "history-batch-notice";
            aviso.innerHTML = "<strong>Movimiento por lote</strong>";
            elementos.push(aviso);
        }
        elementos.push(
            crearDocumentoDetalleHistorial("Documento de salida", detalle.folio_salida, detalle.salida, "out", detalle.es_documento_lote),
            crearConexionDetalleHistorial(),
            crearDocumentoDetalleHistorial("Documento de entrada", detalle.folio_entrada, detalle.entrada, "in", detalle.es_documento_lote)
        );
        contenido.replaceChildren(...elementos);
    } catch (error) {
        contenido.replaceChildren();
        const mensaje = document.createElement("p");
        mensaje.className = "catalog-loading catalog-error";
        mensaje.textContent = error.message;
        contenido.appendChild(mensaje);
    }
}

function escaparXml(valor) {
    return String(valor || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&apos;");
}

async function exportarHistorialExcel() {
    const boton = document.getElementById("exportar-historial");
    if (boton) {
        boton.disabled = true;
        boton.textContent = "Preparando archivo...";
    }

    try {
        const partidasDisponibles = await solicitarJson(
            `${API_RELACIONES}/historial/exportacion`
        );
        const relacionesVisibles = new Set(
            registrosHistorialActual.map(
                (registro) => Number(registro["relacion_id"])
            )
        );
        const partidas = historialCargadoDesdeServidor
            ? partidasDisponibles.filter(
                (partida) => relacionesVisibles.has(Number(partida.relacion_id))
            )
            : partidasDisponibles;
        if (!Array.isArray(partidas) || !partidas.length) {
            mostrarMensaje("No hay documentos relacionados para exportar.");
            return;
        }

        const relaciones = new Map();
        partidas.forEach((partida) => {
            const id = Number(partida.relacion_id || 0);
            if (!relaciones.has(id)) {
                relaciones.set(id, {
                    fecha_hora: partida.fecha_hora,
                    folio_salida: partida.folio_salida || "",
                    folio_entrada: partida.folio_entrada || "",
                    usuario: partida.usuario || "",
                    tablajero: partida.tablajero || "",
                    partidas: [],
                });
            }
            relaciones.get(id).partidas.push(partida);
        });

        const atributoEstilo = "ss:StyleID";
        const atributoCombinacion = "ss:MergeAcross";
        const atributoTipo = "ss:Type";
        const celdaTexto = (valor, estilo = "Dato", combinadas = 0) =>
            `<Cell ${atributoEstilo}="${estilo}"${combinadas ? ` ${atributoCombinacion}="${combinadas}"` : ""}><Data ${atributoTipo}="String">${escaparXml(valor)}</Data></Cell>`;
        const celdaNumero = (valor, estilo = "Cantidad") =>
            `<Cell ${atributoEstilo}="${estilo}"><Data ${atributoTipo}="Number">${Number(valor || 0).toFixed(2)}</Data></Cell>`;
        const celdaVacia = (estilo = "Dato") =>
            `<Cell ${atributoEstilo}="${estilo}"><Data ${atributoTipo}="String"></Data></Cell>`;
        const fechaTexto = (valor) => {
            const fecha = valor ? new Date(valor) : null;
            return fecha && !Number.isNaN(fecha.getTime())
                ? fecha.toLocaleString("es-MX")
                : "Sin fecha";
        };

        const bloques = [...relaciones.values()].map((relacion) => {
            const salidas = relacion.partidas.filter(
                (partida) => String(partida.tipo_documento).toUpperCase() === "SALIDA"
            );
            const entradas = relacion.partidas.filter(
                (partida) => String(partida.tipo_documento).toUpperCase() === "ENTRADA"
            );
            const totalFilas = Math.max(salidas.length, entradas.length);
            const totalSalida = salidas.reduce(
                (total, partida) => total + Number(partida.cantidad || 0), 0
            );
            const totalEntrada = entradas.reduce(
                (total, partida) => total + Number(partida.cantidad || 0), 0
            );
            const merma = totalSalida - totalEntrada;
            const porcentajeMerma = totalSalida > 0
                ? merma / totalSalida * 100
                : 0;
            const filasPartidas = Array.from({ length: totalFilas }, (_, indice) => {
                const salida = salidas[indice];
                const entrada = entradas[indice];
                const celdasSalida = salida
                    ? `${celdaTexto(salida.folio_documento || relacion.folio_salida, "DatoCentrado")}${celdaTexto(limpiarNombreProducto(salida.producto) || "Producto", "Dato")}${celdaNumero(salida.cantidad)}${celdaTexto("kg", "DatoCentrado")}`
                    : Array.from({ length: 4 }, () => celdaVacia()).join("");
                const celdasEntrada = entrada
                    ? `${celdaTexto(entrada.folio_documento || relacion.folio_entrada, "DatoCentrado")}${celdaTexto(limpiarNombreProducto(entrada.producto) || "Producto", "Dato")}${celdaNumero(entrada.cantidad)}${celdaTexto("kg", "DatoCentrado")}`
                    : Array.from({ length: 4 }, () => celdaVacia()).join("");
                return `<Row ss:Height="18">${celdasSalida}${celdaVacia("Separador")}${celdasEntrada}</Row>`;
            }).join("");
            return `
   <Row ss:Height="21">${celdaTexto(`RELACIÓN: ${relacion.folio_salida} → ${relacion.folio_entrada}   |   Fecha: ${fechaTexto(relacion.fecha_hora)}   |   Responsable: ${relacion.tablajero || "No registrado"}`, "Relacion", 8)}</Row>
   <Row ss:Height="18">${["FOLIO REF.", "MATERIA PRIMA (SALIDA)", "CANT.", "UND."].map((valor) => celdaTexto(valor, "EncabezadoSalida")).join("")}${celdaVacia("Separador")}${["FOLIO REF.", "PRODUCTO RESULTANTE (ENTRADA)", "CANT.", "UND."].map((valor) => celdaTexto(valor, "EncabezadoEntrada")).join("")}</Row>
    ${filasPartidas}
   <Row ss:Height="19">${celdaTexto("TOTAL:", "TotalEtiqueta", 1)}${celdaNumero(totalSalida, "TotalCantidad")}${celdaTexto("kg", "TotalUnidad")}${celdaVacia("Separador")}${celdaTexto("TOTAL:", "TotalEtiqueta", 1)}${celdaNumero(totalEntrada, "TotalCantidad")}${celdaTexto("kg", "TotalUnidad")}</Row>
   <Row ss:Height="17">${celdaTexto(`Merma / desperdicio del proceso: ${merma.toFixed(2)} kg (${porcentajeMerma.toFixed(1)}%)`, "NotaMerma", 8)}</Row>
   <Row ss:Height="11"/>`;
        }).join("");

        const xml = `<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Styles>
  <Style ss:ID="Default" ss:Name="Normal"><Font ss:FontName="Segoe UI" ss:Size="9" ss:Color="#334155"/><Alignment ss:Vertical="Center"/></Style>
  <Style ss:ID="Marca"><Font ss:FontName="Segoe UI" ss:Bold="1" ss:Size="12" ss:Color="#0F172A"/></Style>
  <Style ss:ID="TituloReporte"><Font ss:FontName="Segoe UI" ss:Bold="1" ss:Size="10" ss:Color="#64748B"/><Alignment ss:Horizontal="Right"/></Style>
  <Style ss:ID="Subtitulo"><Font ss:FontName="Segoe UI" ss:Size="8" ss:Color="#64748B"/><Borders><Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/></Borders></Style>
  <Style ss:ID="Relacion"><Font ss:FontName="Segoe UI" ss:Bold="1" ss:Size="9" ss:Color="#0F172A"/><Interior ss:Color="#F8FAFC" ss:Pattern="Solid"/><Borders><Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/><Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/><Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/><Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/></Borders></Style>
  <Style ss:ID="EncabezadoSalida"><Font ss:FontName="Segoe UI" ss:Bold="1" ss:Size="8" ss:Color="#991B1B"/><Interior ss:Color="#FEF2F2" ss:Pattern="Solid"/><Borders><Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/></Borders><Alignment ss:WrapText="1"/></Style>
  <Style ss:ID="EncabezadoEntrada"><Font ss:FontName="Segoe UI" ss:Bold="1" ss:Size="8" ss:Color="#065F46"/><Interior ss:Color="#ECFDF5" ss:Pattern="Solid"/><Borders><Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/></Borders><Alignment ss:WrapText="1"/></Style>
  <Style ss:ID="Dato"><Borders><Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/></Borders><Alignment ss:Vertical="Center" ss:WrapText="1"/></Style>
  <Style ss:ID="DatoCentrado"><Borders><Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/></Borders><Alignment ss:Horizontal="Center" ss:Vertical="Center"/></Style>
  <Style ss:ID="Cantidad"><Borders><Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/></Borders><NumberFormat ss:Format="#,##0.00"/><Alignment ss:Horizontal="Right"/></Style>
  <Style ss:ID="Separador"><Interior ss:Color="#FFFFFF" ss:Pattern="Solid"/></Style>
  <Style ss:ID="TotalEtiqueta"><Font ss:Bold="1" ss:Color="#0F172A"/><Borders><Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/><Border ss:Position="Bottom" ss:LineStyle="Double" ss:Weight="2" ss:Color="#0F172A"/></Borders><Alignment ss:Horizontal="Right"/></Style>
  <Style ss:ID="TotalCantidad"><Font ss:Bold="1" ss:Color="#0F172A"/><Borders><Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/><Border ss:Position="Bottom" ss:LineStyle="Double" ss:Weight="2" ss:Color="#0F172A"/></Borders><NumberFormat ss:Format="#,##0.00"/><Alignment ss:Horizontal="Right"/></Style>
  <Style ss:ID="TotalUnidad"><Font ss:Bold="1" ss:Color="#0F172A"/><Borders><Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/><Border ss:Position="Bottom" ss:LineStyle="Double" ss:Weight="2" ss:Color="#0F172A"/></Borders><Alignment ss:Horizontal="Center"/></Style>
  <Style ss:ID="NotaMerma"><Font ss:FontName="Segoe UI" ss:Italic="1" ss:Size="8" ss:Color="#64748B"/><Alignment ss:Horizontal="Right"/></Style>
 </Styles>
 <Worksheet ss:Name="Historial Trazabilidad">
  <Table>
   <Column ss:Width="105"/><Column ss:Width="190"/><Column ss:Width="72"/><Column ss:Width="45"/><Column ss:Width="15"/><Column ss:Width="105"/><Column ss:Width="190"/><Column ss:Width="72"/><Column ss:Width="45"/>
   <Row ss:Height="23">${celdaTexto("CARNES CAYAL", "Marca", 3)}<Cell ss:Index="6" ss:StyleID="TituloReporte" ss:MergeAcross="3"><Data ss:Type="String">HISTORIAL DE TRAZABILIDAD</Data></Cell></Row>
   <Row ss:Height="18">${celdaTexto(`Reporte de transformación cárnica · Generado el ${new Date().toLocaleDateString("es-MX")} · ${relaciones.size} relaciones`, "Subtitulo", 8)}</Row>
   <Row ss:Height="10"/>
   ${bloques}
  </Table>
  <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel"><Selected/><FreezePanes/><FrozenNoSplit/><SplitHorizontal>2</SplitHorizontal><TopRowBottomPane>2</TopRowBottomPane><ProtectObjects>False</ProtectObjects><ProtectScenarios>False</ProtectScenarios></WorksheetOptions>
 </Worksheet>
</Workbook>`;
        const archivo = new Blob(
            [xml],
            { type: "application/vnd.ms-excel;charset=utf-8" }
        );
        const enlace = document.createElement("a");
        const fecha = new Date().toISOString().slice(0, 10);
        enlace.href = URL.createObjectURL(archivo);
        enlace.download = `trazabilidad_transformaciones_${fecha}.xls`;
        document.body.appendChild(enlace);
        enlace.click();
        enlace.remove();
        window.setTimeout(() => URL.revokeObjectURL(enlace.href), 1000);
    } catch (error) {
        mostrarMensaje(error.message);
    } finally {
        if (boton) {
            boton.disabled = false;
            boton.textContent = "Exportar documentos";
        }
    }
}

async function solicitarJson(url, opciones = {}) {
    const csrf = document.cookie
        .split("; ")
        .find((cookie) => cookie.startsWith("cayal_csrf="))
        ?.split("=")
        .slice(1)
        .join("=");
    const respuesta = await fetch(url, {
        credentials: "same-origin",
        headers: {
            "Content-Type": "application/json",
            ...(csrf ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {}),
            ...(opciones.headers || {}),
        },
        ...opciones,
    });
    let datos;
    try { datos = await respuesta.json(); } catch (_) { datos = {}; }
    if (respuesta.status === 401 && !document.getElementById("loginPage")) {
        window.location.assign("/");
        throw new Error("La sesión terminó.");
    }
    if (!respuesta.ok) {
        const detalle = Array.isArray(datos.detail)
            ? datos.detail.map((item) => item.msg).join(" ")
            : datos.detail || "No fue posible completar la operación.";
        const error = new Error(detalle);
        error.status = respuesta.status;
        throw error;
    }
    return datos;
}

function mostrarMensaje(texto, tipo = "error") {
    const elemento = document.getElementById("mensaje-relacion");
    if (!elemento) return;
    elemento.textContent = texto;
    elemento.className = `message visible ${tipo}`;
}

function limpiarMensaje() {
    const elemento = document.getElementById("mensaje-relacion");
    if (elemento) {
        elemento.textContent = "";
        elemento.className = "message";
    }
}

function llenarSelect(id, registros, valorCampo, textoCampo, placeholder) {
    const select = document.getElementById(id);
    select.replaceChildren();
    const inicial = document.createElement("option");
    inicial.value = "";
    inicial.textContent = placeholder;
    select.appendChild(inicial);
    registros.forEach((registro) => {
        const opcion = document.createElement("option");
        opcion.value = registro[valorCampo];
        opcion.textContent = typeof textoCampo === "function"
            ? textoCampo(registro)
            : registro[textoCampo];
        select.appendChild(opcion);
    });
}

function formatoNumero(valor, decimales = 2) {
    return Number(valor || 0).toLocaleString("es-MX", {
        minimumFractionDigits: decimales,
        maximumFractionDigits: decimales,
    });
}

function renderizarPartidas(tipo, partidas) {
    const contenedor = document.getElementById(`partidas-${tipo}`);
    const resumen = document.getElementById(`resumen-${tipo}`);
    contenedor.replaceChildren();
    if (!partidas.length) {
        resumen.textContent = "El documento no contiene partidas disponibles.";
        resumen.className = "document-summary empty";
        return;
    }
    const tabla = document.createElement("table");
    tabla.innerHTML = "<thead><tr><th>Producto</th><th>Cantidad</th></tr></thead>";
    const cuerpo = document.createElement("tbody");
    let cantidad = 0;
    partidas.forEach((partida) => {
        cantidad += Number(partida.Quantity || 0);
        const fila = document.createElement("tr");
        [
            limpiarNombreProducto(partida.ProductName) || "—",
            formatoNumero(partida.Quantity),
        ].forEach((texto) => {
            const celda = document.createElement("td");
            celda.textContent = texto;
            fila.appendChild(celda);
        });
        cuerpo.appendChild(fila);
    });
    tabla.appendChild(cuerpo);
    contenedor.appendChild(tabla);
    resumen.textContent = `${partidas.length} partidas · ${formatoNumero(cantidad)} unidades`;
    resumen.className = "document-summary";
}

async function cargarPartidas(tipo) {
    const select = document.getElementById(`documento-${tipo}`);
    const documentId = Number(select.value || 0);
    const contenedor = document.getElementById(`partidas-${tipo}`);
    if (!documentId) {
        contenedor.replaceChildren();
        const resumen = document.getElementById(`resumen-${tipo}`);
        resumen.textContent = "Selecciona un documento para revisar sus partidas.";
        resumen.className = "document-summary empty";
        if (tipo === "entrada") {
            partidasEntrada = [];
            document.getElementById("lista-marcas").replaceChildren();
        }
        return;
    }
    try {
        const partidas = await solicitarJson(`${API_RELACIONES}/documentos/${documentId}/partidas`);
        renderizarPartidas(tipo, partidas);
        if (tipo === "entrada") {
            partidasEntrada = partidas;
            await cargarMarcas();
        }
        limpiarMensaje();
    } catch (error) {
        mostrarMensaje(error.message);
    }
}

async function cargarMarcas() {
    const categorias = [...new Set(partidasEntrada.map((p) => p.Category).filter(Boolean))];
    const respuestas = await Promise.all(
        categorias.map((categoria) => solicitarJson(`${API_RELACIONES}/marcas?categoria=${encodeURIComponent(categoria)}`)),
    );
    const mapa = new Map();
    respuestas.flat().forEach((marca) => mapa.set(Number(marca["BrandID"]), marca));
    const lista = document.getElementById("lista-marcas");
    lista.replaceChildren();
    [...mapa.values()].forEach((marca) => {
        const opcion = document.createElement("option");
        opcion.value = marca.BrandName;
        lista.appendChild(opcion);
    });
}

function actualizarCamposAnalisis() {
    const opcion = document.getElementById("tipo-movimiento").selectedOptions[0];
    const esAnalisis = Number(opcion?.dataset.entrada || 0) === 24
        && Number(opcion?.dataset.salida || 0) === 21;
    document.getElementById("campos-analisis").classList.toggle("hidden", !esAnalisis);
    ["proveedor", "marca", "usuario-fisico"].forEach((id) => {
        document.getElementById(id).required = esAnalisis;
    });
}

function esTransformacion() {
    const opcion = document.getElementById("tipo-movimiento").selectedOptions[0];
    return Number(opcion?.dataset.entrada || 0) === 5
        && Number(opcion?.dataset.salida || 0) === 2;
}

function configurarApartadoMovimiento() {
    const opcion = document.getElementById("tipo-movimiento").selectedOptions[0];
    const entradaId = Number(opcion?.dataset.entrada || 0);
    const apartados = {
        17: ["Academia", "Relaciona los documentos de salida y entrada correspondientes al movimiento Academia."],
        24: ["Análisis", "Relaciona ambos documentos y registra proveedor, marca, tablajero y fecha de lote."],
        19: ["Calakmul", "Relaciona la salida y entrada generadas para el movimiento Calakmul."],
        3: ["Cruce", "Comprueba las partidas de ambos documentos antes de registrar el cruce."],
        14: ["Inventario", "Relaciona los documentos que respaldan el ajuste o movimiento de inventario."],
        16: ["Kila", "Relaciona la salida y entrada correspondientes al movimiento Kila."],
        13: ["Koben", "Relaciona la salida y entrada correspondientes al movimiento Koben."],
        7: ["Preparados", "Comprueba y relaciona los documentos del movimiento de productos preparados."],
        26: ["Transformación de listas para cocinar", "Relaciona la salida y entrada del movimiento de listas para cocinar."],
        5: ["Transformación"],
        31: ["Traspaso de almacén", "Relaciona y verifica los documentos correspondientes al traspaso de almacén."],
    };
    const [titulo, descripcion] = apartados[entradaId] || [
        opcion?.textContent || "Relacionar documentos",
        "Selecciona los documentos y comprueba sus partidas antes de guardar.",
    ];
    document.getElementById("etiqueta-movimiento-seleccionado").textContent = "Movimiento seleccionado";
    document.getElementById("titulo-movimiento-seleccionado").textContent = titulo;
    document.getElementById("descripcion-movimiento-seleccionado").textContent = descripcion;
}

function limpiarVistaPreviaTransformacion() {
    transformacionPreparada = false;
    renderizarPartidas("salida", []);
    renderizarPartidas("entrada", []);
    document.getElementById("resumen-salida").textContent = "Se completará automáticamente al seleccionar la transformación.";
    document.getElementById("resumen-entrada").textContent = "Se completará automáticamente al seleccionar la transformación.";
    document.getElementById("panel-documentos").classList.remove("hidden");
    document.getElementById("resumen-registro-transformacion").classList.add("hidden");
}

function aplicarPresentacionMovimientoSeleccionado() {
    const transformacion = esTransformacion();
    const opcion = document.getElementById("tipo-movimiento").selectedOptions[0];
    const esAnalisis = Number(opcion?.dataset.entrada || 0) === 24
        && Number(opcion?.dataset.salida || 0) === 21;
    configurarApartadoMovimiento();
    document.getElementById("espacio-transformacion").classList.toggle("transformation-mode", transformacion);
    document.getElementById("datos-transformacion").classList.toggle("hidden", !transformacion);
    document.getElementById("panel-documentos").classList.remove("hidden");
    document.getElementById("datos-movimiento-fisico").classList.toggle("hidden", !esAnalisis);
    document.getElementById("documento-salida").disabled = transformacion;
    document.getElementById("documento-entrada").disabled = transformacion;
    document.getElementById("tablajero-transformacion").disabled = !transformacion;
    document.getElementById("tablajero-transformacion").required = transformacion;
    document.getElementById("resumen-registro-transformacion").classList.add("hidden");
    document.getElementById("boton-guardar").textContent = transformacion
        ? "Registrar transformación"
        : "Relacionar documentos";
    return transformacion;
}

async function prepararMovimientoSeleccionado() {
    const transformacion = aplicarPresentacionMovimientoSeleccionado();
    if (!transformacion) return;
    limpiarVistaPreviaTransformacion();
    const lineas = await solicitarJson(`${API_RELACIONES}/transformacion/lineas`);
    llenarSelect("linea-transformacion", lineas, "Category1", "Category1", "Selecciona una línea");
    llenarSelect("transformacion-precargada", [], "transformacion_id", "nombre_transformacion", "Selecciona una transformación");
    llenarSelect("base-transformacion", [], "product_id_base", "producto_base", "Selecciona un producto base");
    llenarSelect("resultante-transformacion", [], "product_id", "producto_resultante", "Selecciona un producto resultante");
    document.getElementById("base-transformacion").disabled = true;
    document.getElementById("resultante-transformacion").disabled = true;
    document.getElementById("transformacion-precargada").disabled = true;
    detalleTransformacionSeleccionada = null;
    calcularInsumosTransformacion();
    actualizarMermaTransformacion();
}

async function cargarBasesTransformacion() {
    limpiarVistaPreviaTransformacion();
    const linea = document.getElementById("linea-transformacion").value;
    const selector = document.getElementById("transformacion-precargada");
    document.getElementById("resumen-registro-transformacion").classList.add("hidden");
    document.getElementById("documento-salida").value = "";
    document.getElementById("documento-entrada").value = "";
    detalleTransformacionSeleccionada = null;
    llenarSelect("base-transformacion", [], "product_id_base", "producto_base", "Se completa automáticamente");
    llenarSelect("resultante-transformacion", [], "product_id", "producto_resultante", "Selecciona un producto resultante");
    calcularInsumosTransformacion();
    if (!linea) {
        llenarSelect("transformacion-precargada", [], "transformacion_id", "nombre_transformacion", "Selecciona una transformación");
        selector.disabled = true;
        return;
    }
    try {
        const transformaciones = await solicitarJson(`${API_RELACIONES}/transformacion/precargadas?linea=${encodeURIComponent(linea)}`);
        llenarSelect("transformacion-precargada", transformaciones, "transformacion_id", "nombre_transformacion", "Selecciona una transformación");
        selector.disabled = false;
        if (!transformaciones.length) {
            mostrarMensaje("Esta línea aún no tiene transformaciones precargadas en Configuración.");
        }
    } catch (error) { mostrarMensaje(error.message); }
}

async function cargarTransformacionPrecargada() {
    limpiarVistaPreviaTransformacion();
    const transformacionId = Number(document.getElementById("transformacion-precargada").value || 0);
    detalleTransformacionSeleccionada = null;
    if (!transformacionId) {
        llenarSelect("base-transformacion", [], "product_id_base", "producto_base", "Se completa automáticamente");
        llenarSelect("resultante-transformacion", [], "product_id", "producto_resultante", "Se completa automáticamente");
        calcularInsumosTransformacion();
        return;
    }
    try {
        const detalle = await solicitarJson(`${API_RELACIONES}/transformacion/precargadas/${transformacionId}`);
        detalleTransformacionSeleccionada = detalle;
        llenarSelect("base-transformacion", [{ product_id_base: detalle.producto_base_id, producto_base: detalle.producto_base }], "product_id_base", "producto_base", "Producto base");
        document.getElementById("base-transformacion").value = String(detalle.producto_base_id);
        const resultantes = Array.isArray(detalle["resultantes"])
            ? detalle["resultantes"]
            : [];
        if (!resultantes.length) {
            throw new Error("La transformación no tiene productos resultantes configurados.");
        }
        llenarSelect("resultante-transformacion", resultantes, "product_id", "producto_resultante", "Producto resultante");
        document.getElementById("resultante-transformacion").value = String(resultantes[0]["product_id"]);
        actualizarMermaTransformacion();
        calcularInsumosTransformacion();
        limpiarMensaje();
    } catch (error) { mostrarMensaje(error.message); }
}

function calcularInsumosTransformacion() {
    insumosTransformacionCalculados = [];
    if (!detalleTransformacionSeleccionada || !validarKilosTransformacion(false)) {
        return;
    }
    const componentes = detalleTransformacionSeleccionada.componentes || [];
    const baseReceta = componentes.find((componente) => componente["es_producto_base"]);
    const kilos = Number(document.getElementById("cantidad-base-transformacion").value || 0);
    const factor = Number(baseReceta?.cantidad || 0) > 0
        ? kilos / Number(baseReceta.cantidad)
        : 1;
    insumosTransformacionCalculados = componentes
        .filter((componente) => !componente["es_producto_base"])
        .map((componente) => ({
            ...componente,
            cantidad_calculada: Number(componente.cantidad || 0) * factor,
        }));
}

function actualizarMermaTransformacion() {
    const base = Number(document.getElementById("cantidad-base-transformacion").value || 0);
    if (!validarKilosTransformacion(false)) {
        document.getElementById("cantidad-resultante-transformacion").value = "";
        const pesoAproximadoInvalido = document.getElementById("peso-aproximado-transformacion");
        if (pesoAproximadoInvalido) pesoAproximadoInvalido.textContent = "0.00";
        return { merma: 0, porcentaje: 0, nivelNormal: false };
    }
    const porcentajeMerma = Number(
        detalleTransformacionSeleccionada?.porcentaje_merma ??
        MERMA_TECNICA_PORCENTAJE
    );
    const factorRendimiento = 1 - (porcentajeMerma / 100);
    const resultante = base * factorRendimiento;
    document.getElementById("cantidad-resultante-transformacion").value = resultante.toFixed(2);
    const pesoAproximado = document.getElementById("peso-aproximado-transformacion");
    if (pesoAproximado) pesoAproximado.textContent = resultante.toFixed(2);
    const merma = base * (porcentajeMerma / 100);
    const porcentaje = base > 0 ? porcentajeMerma : 0;
    const nivelNormal = porcentaje <= MERMA_TECNICA_PORCENTAJE;
    const etiquetaMerma = document.getElementById("merma-transformacion-activa");
    if (etiquetaMerma) etiquetaMerma.textContent = `Merma: ${porcentajeMerma.toFixed(1)}%`;
    return { merma, porcentaje, nivelNormal };
}

async function localizarDocumentosTransformacion() {
    const baseId = Number(document.getElementById("base-transformacion").value || 0);
    const resultanteId = Number(document.getElementById("resultante-transformacion").value || 0);
    const cantidadBase = Number(document.getElementById("cantidad-base-transformacion").value || 0);
    const cantidadResultante = Number(document.getElementById("cantidad-resultante-transformacion").value || 0);
    const tablajero = document.getElementById("tablajero-transformacion");
    if (
        !detalleTransformacionSeleccionada
        || !baseId
        || !resultanteId
        || baseId === resultanteId
        || !validarKilosTransformacion()
        || cantidadResultante <= 0
    ) {
        mostrarMensaje("No fue posible preparar la transformación. Revisa los kilos e inténtalo nuevamente.");
        return;
    }
    try {
        const folios = await solicitarJson(`${API_RELACIONES}/transformacion/folios-siguientes`);
        const nombreBase = limpiarNombreProducto(document.getElementById("base-transformacion").selectedOptions[0]?.textContent) || "Producto base";
        const nombreResultante = limpiarNombreProducto(document.getElementById("resultante-transformacion").selectedOptions[0]?.textContent) || "Producto resultante";
        const partidasSalida = [
            { ProductKey: "BASE", ProductName: nombreBase, Quantity: cantidadBase, CostPrice: 0, total: 0 },
            ...insumosTransformacionCalculados.map((insumo) => ({
                ProductKey: "INSUMO",
                ProductName: insumo.producto,
                Quantity: insumo.cantidad_calculada,
                CostPrice: 0,
                total: 0,
            })),
        ];
        renderizarPartidas("salida", partidasSalida);
        renderizarPartidas("entrada", [{ ProductKey: "POR GENERAR", ProductName: nombreResultante, Quantity: cantidadResultante, CostPrice: 0, total: 0 }]);
        document.getElementById("documento-salida").innerHTML = '<option value="">Se generará al registrar</option>';
        document.getElementById("documento-entrada").innerHTML = '<option value="">Se generará al registrar</option>';
        document.getElementById("panel-documentos").classList.remove("hidden");
        const fecha = new Date();
        document.getElementById("resumen-folios-transformacion").textContent =
            `${folios.folio_salida} → ${folios.folio_entrada}`;
        document.getElementById("resumen-fecha-transformacion").textContent =
            fecha.toLocaleDateString("es-MX");
        document.getElementById("resumen-usuario-transformacion").textContent =
            document.getElementById("form-relacion").dataset.usuario || "Usuario activo";
        document.getElementById("resumen-tablajero-transformacion").textContent =
            tablajero.value
                ? tablajero.selectedOptions[0]?.textContent
                : "Pendiente de seleccionar";
        const evaluacionMerma = actualizarMermaTransformacion();
        document.getElementById("resumen-nivel-merma").textContent = evaluacionMerma.nivelNormal
            ? `NORMAL · ${evaluacionMerma.porcentaje.toFixed(2)}%`
            : `FUERA DE NIVEL · ${evaluacionMerma.porcentaje.toFixed(2)}%`;
        document.getElementById("resumen-registro-transformacion").classList.remove("hidden");
        document.getElementById("boton-guardar").textContent = "Registrar transformación";
        transformacionPreparada = Boolean(tablajero.value);
        if (transformacionPreparada) {
            mostrarMensaje("La relación esta Preparada.", "success");
        } else {
            mostrarMensaje("Selecciona el tablajero responsable para completar la relación.");
        }
    } catch (error) {
        limpiarVistaPreviaTransformacion();
        mostrarMensaje(error.message);
    }
}

async function cargarDatos() {
    try {
        const [datosCatalogos, salidas, entradas] = await Promise.all([
            solicitarJson(`${API_RELACIONES}/catalogos`),
            solicitarJson(`${API_RELACIONES}/documentos-disponibles/203`),
            solicitarJson(`${API_RELACIONES}/documentos-disponibles/202`),
        ]);
        catalogos = datosCatalogos;
        documentos = { salida: salidas, entrada: entradas };
        datosCargados = true;
        llenarSelect("documento-salida", salidas, "DocumentID", (d) => `${d.DocFolio} · ${d.UserName} · ${d.DateDocument || d.CreatedOn}`, "Selecciona una salida");
        llenarSelect("documento-entrada", entradas, "DocumentID", (d) => `${d.DocFolio} · ${d.UserName} · ${d.DateDocument || d.CreatedOn}`, "Selecciona una entrada");
        llenarSelect("proveedor", catalogos.proveedores, "BusinessEntityID", "OfficialName", "Selecciona proveedor");
        llenarSelect("usuario-fisico", catalogos.usuarios_fisicos, "UserID", "OfficialName", "Selecciona tablajero");
        llenarSelect("tablajero-transformacion", catalogos.usuarios_fisicos, "UserID", "OfficialName", "Selecciona un tablajero");
        const movimiento = document.getElementById("tipo-movimiento");
        movimiento.innerHTML = '<option value="">Selecciona el movimiento</option>';
        catalogos.movimientos.forEach((registro) => {
            const opcion = document.createElement("option");
            opcion.value = registro.ItemValue;
            opcion.textContent = registro.ItemValue;
            opcion.dataset.entrada = registro.EntradaID;
            opcion.dataset.salida = registro.SalidaID;
            movimiento.appendChild(opcion);
        });
        limpiarMensaje();
    } catch (error) {
        mostrarMensaje(error.message);
    }
}

async function solicitarTipoMovimiento() {
    const boton = document.getElementById("boton-iniciar-captura");
    boton.disabled = true;
    boton.textContent = "Preparando...";
    try {
        if (!datosCargados) await cargarDatos();
        if (!datosCargados) return;
        const lineasConfiguradas = await solicitarJson(
            `${API_RELACIONES}/transformacion/lineas`
        );
        const respuestasTransformaciones = await Promise.all(
            lineasConfiguradas.map((registro) =>
                solicitarJson(
                    `${API_RELACIONES}/transformacion/precargadas?linea=${encodeURIComponent(registro.Category1)}`
                )
            )
        );
        const configuracionesGuardadas = respuestasTransformaciones
            .flat()
            .map((registro) => ({ ...registro, origen_catalogo: false }));
        const productosCatalogo = await solicitarJson(
            `${API_RELACIONES}/transformacion/disponibles`
        );
        const clavesConfiguradas = new Set(
            configuracionesGuardadas.map((registro) =>
                `${registro.linea}|${registro.nombre_transformacion}`.toUpperCase()
            )
        );
        transformacionesDisponibles = [
            ...configuracionesGuardadas,
            ...productosCatalogo.filter((registro) =>
                !clavesConfiguradas.has(
                    `${registro.linea}|${registro.nombre_transformacion}`.toUpperCase()
                )
            ),
        ];
        const movimientosPermitidos = catalogos.movimientos.filter((registro) =>
            Number(registro.EntradaID) === 5 && Number(registro.SalidaID) === 2
        );
        llenarSelect(
            "movimiento-inicial", movimientosPermitidos,
            "ItemValue", "ItemValue", "Selecciona el movimiento"
        );
        const lineas = [...new Set(
            lineasConfiguradas
                .map((registro) => registro.Category1)
                .filter(Boolean)
        )].sort((a, b) => a.localeCompare(b, "es"));
        renderizarTiposTransformacion(lineas);
        document.getElementById("movimiento-inicial").value = "";
        document.getElementById("linea-inicial").value = "";
        document.getElementById("campo-linea-inicial").classList.add("hidden");
        document.getElementById("continuar-inicio-captura").disabled = true;
        document.getElementById("modal-iniciar-captura").classList.remove("hidden");
        document.body.classList.add("modal-open");
        document.getElementById("movimiento-inicial").focus();
    } catch (error) {
        mostrarMensaje(error.message);
    } finally {
        boton.disabled = false;
        boton.textContent = "Iniciar captura";
    }
}

function renderizarTiposTransformacion(lineas) {
    const contenedor = document.getElementById("opciones-linea-inicial");
    const selector = document.getElementById("linea-inicial");
    contenedor.replaceChildren();
    selector.value = "";
    lineas.forEach((linea) => {
        const boton = document.createElement("button");
        boton.type = "button";
        boton.className = "transformation-type-option";
        boton.textContent = linea;
        boton.setAttribute("aria-pressed", "false");
        boton.addEventListener("click", () => {
            selector.value = linea;
            contenedor.querySelectorAll(".transformation-type-option").forEach((opcion) => {
                const seleccionada = opcion === boton;
                opcion.classList.toggle("active", seleccionada);
                opcion.setAttribute("aria-pressed", String(seleccionada));
            });
            actualizarInicioCaptura();
        });
        contenedor.appendChild(boton);
    });
}

function actualizarInicioCaptura() {
    const movimiento = document.getElementById("movimiento-inicial").value;
    const campoLinea = document.getElementById("campo-linea-inicial");
    campoLinea.classList.toggle("hidden", !movimiento);
    if (!movimiento) {
        document.getElementById("linea-inicial").value = "";
        document.querySelectorAll(".transformation-type-option").forEach((opcion) => {
            opcion.classList.remove("active");
            opcion.setAttribute("aria-pressed", "false");
        });
    }
    document.getElementById("continuar-inicio-captura").disabled = !(
        movimiento && document.getElementById("linea-inicial").value
    );
}

function cerrarInicioCaptura() {
    document.getElementById("modal-iniciar-captura").classList.add("hidden");
    document.body.classList.remove("modal-open");
}

async function continuarInicioCaptura() {
    const movimiento = document.getElementById("movimiento-inicial").value;
    const linea = document.getElementById("linea-inicial").value;
    if (!movimiento || !linea) return;
    const boton = document.getElementById("continuar-inicio-captura");
    boton.disabled = true;
    boton.textContent = "Abriendo...";
    try {
        lineaTransformacionSeleccionada = linea;
        document.getElementById("tipo-movimiento").value = movimiento;
        actualizarCamposAnalisis();
        cerrarInicioCaptura();
        document.getElementById("panel-inicio").classList.add("hidden");
        const formulario = document.getElementById("form-relacion");
        formulario.classList.remove("hidden");
        await prepararMovimientoSeleccionado();
        document.getElementById("linea-transformacion").value = linea;

        const tablajero = document.getElementById("tablajero-transformacion");
        tablajero.value = "";
        tablajero.disabled = false;
        transformacionCatalogoActualId = "";
        document.getElementById("linea-seleccionada-sencilla").textContent = linea;
        document.getElementById("transformacion-seleccionada-sencilla").textContent = "Sin seleccionar";
        document.getElementById("cantidad-base-transformacion").disabled = true;
        document.getElementById("boton-cambiar-transformacion").textContent = "Seleccionar";
        await abrirCambioTransformacion();
        formulario.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
        mostrarMensaje(error.message);
    } finally {
        boton.textContent = "Continuar";
        actualizarInicioCaptura();
    }
}

async function abrirCambioTransformacion() {
    const panel = document.getElementById("selector-cambio-transformacion");
    panel.classList.remove("hidden");
    document.body.classList.add("modal-open");
    document.getElementById("lista-transformaciones-alternativas").innerHTML =
        '<p class="transformation-option-empty">Consultando transformaciones...</p>';
    document.getElementById("paginacion-transformaciones").classList.add("hidden");
    try {
        if (!transformacionesDisponibles.length) {
            const lineasConfiguradas = await solicitarJson(
                `${API_RELACIONES}/transformacion/lineas`
            );
            const respuestasTransformaciones = await Promise.all(
                lineasConfiguradas.map((registro) =>
                    solicitarJson(
                        `${API_RELACIONES}/transformacion/precargadas?linea=${encodeURIComponent(registro.Category1)}`
                    )
                )
            );
            const configuracionesGuardadas = respuestasTransformaciones
                .flat()
                .map((registro) => ({ ...registro, origen_catalogo: false }));
            const productosCatalogo = await solicitarJson(
                `${API_RELACIONES}/transformacion/disponibles`
            );
            const clavesConfiguradas = new Set(
                configuracionesGuardadas.map((registro) =>
                    `${registro.linea}|${registro.nombre_transformacion}`.toUpperCase()
                )
            );
            transformacionesDisponibles = [
                ...configuracionesGuardadas,
                ...productosCatalogo.filter((registro) =>
                    !clavesConfiguradas.has(
                        `${registro.linea}|${registro.nombre_transformacion}`.toUpperCase()
                    )
                ),
            ];
        }
        transformacionesLineaActual = transformacionesDisponibles.filter(
            (registro) => registro.linea === lineaTransformacionSeleccionada
        );
        const indiceActual = transformacionesLineaActual.findIndex(
            (registro) => String(registro.transformacion_id) === transformacionCatalogoActualId
        );
        paginaTransformacionesActual = indiceActual >= 0
            ? Math.floor(indiceActual / TRANSFORMACIONES_POR_PAGINA) + 1
            : 1;
        renderizarPaginaTransformaciones();
        if (!transformacionesLineaActual.length) {
            mostrarMensaje(`No hay transformaciones configuradas para ${lineaTransformacionSeleccionada}.`);
        } else {
            document.querySelector(".transformation-option")?.focus();
            limpiarMensaje();
        }
    } catch (error) { mostrarMensaje(error.message); }
}

function renderizarPaginaTransformaciones() {
    const lista = document.getElementById("lista-transformaciones-alternativas");
    const paginacion = document.getElementById("paginacion-transformaciones");
    lista.replaceChildren();
    if (!transformacionesLineaActual.length) {
        lista.innerHTML = '<p class="transformation-option-empty">No hay transformaciones disponibles.</p>';
        paginacion.classList.add("hidden");
        return;
    }
    const totalPaginas = Math.ceil(
        transformacionesLineaActual.length / TRANSFORMACIONES_POR_PAGINA
    );
    paginaTransformacionesActual = Math.min(
        Math.max(paginaTransformacionesActual, 1), totalPaginas
    );
    const inicio = (paginaTransformacionesActual - 1) * TRANSFORMACIONES_POR_PAGINA;
    transformacionesLineaActual
        .slice(inicio, inicio + TRANSFORMACIONES_POR_PAGINA)
        .forEach((transformacion) => {
            const boton = document.createElement("button");
            boton.type = "button";
            boton.className = "transformation-option";
            boton.textContent = limpiarNombreProducto(transformacion.nombre_transformacion);
            boton.classList.toggle(
                "active",
                String(transformacion.transformacion_id) === transformacionCatalogoActualId
            );
            boton.addEventListener("click", () =>
                seleccionarTransformacionAlternativa(transformacion)
            );
            lista.appendChild(boton);
        });
    document.getElementById("transformacion-pagina-actual").textContent =
        `Página ${paginaTransformacionesActual} de ${totalPaginas}`;
    document.getElementById("transformacion-pagina-anterior").disabled =
        paginaTransformacionesActual === 1;
    document.getElementById("transformacion-pagina-siguiente").disabled =
        paginaTransformacionesActual === totalPaginas;
    paginacion.classList.toggle("hidden", totalPaginas <= 1);
}

function cambiarPaginaTransformaciones(cambio) {
    paginaTransformacionesActual += cambio;
    renderizarPaginaTransformaciones();
}

function cerrarCambioTransformacion() {
    document.getElementById("selector-cambio-transformacion").classList.add("hidden");
    document.body.classList.remove("modal-open");
}

async function seleccionarTransformacionAlternativa(seleccionada) {
    if (!seleccionada) return;
    try {
        limpiarVistaPreviaTransformacion();
        const rutaDetalle = seleccionada.origen_catalogo
            ? `${API_RELACIONES}/transformacion/catalogo/${seleccionada.transformacion_id}`
            : `${API_RELACIONES}/transformacion/precargadas/${seleccionada.transformacion_id}`;
        const detalle = await solicitarJson(
            rutaDetalle
        );
        detalleTransformacionSeleccionada = detalle;
        const lineaDetalle = String(
            detalle.linea
            || seleccionada.linea
            || lineaTransformacionSeleccionada
            || ""
        ).trim();
        lineaTransformacionSeleccionada = lineaDetalle;
        const selectorLinea = document.getElementById("linea-transformacion");
        if (
            lineaDetalle
            && !Array.from(selectorLinea.options).some(
                (opcion) => opcion.value === lineaDetalle
            )
        ) {
            selectorLinea.appendChild(new Option(lineaDetalle, lineaDetalle));
        }
        selectorLinea.value = lineaDetalle;
        llenarSelect(
            "base-transformacion",
            [{ product_id_base: detalle.producto_base_id, producto_base: detalle.producto_base }],
            "product_id_base", "producto_base", "Producto base"
        );
        document.getElementById("base-transformacion").value = String(detalle.producto_base_id);
        const resultantes = Array.isArray(detalle["resultantes"])
            ? detalle["resultantes"]
            : [];
        if (!resultantes.length) {
            throw new Error("La transformación no tiene productos resultantes configurados.");
        }
        llenarSelect(
            "resultante-transformacion", resultantes,
            "product_id", "producto_resultante", "Producto resultante"
        );
        document.getElementById("resultante-transformacion").value = String(resultantes[0]["product_id"]);
        const configuracionId = seleccionada.origen_catalogo
            ? 0
            : Number(seleccionada.transformacion_id);
        llenarSelect(
            "transformacion-precargada",
            [{
                transformacion_id: configuracionId,
                nombre_transformacion: detalle.nombre_transformacion,
            }],
            "transformacion_id", "nombre_transformacion", "Transformación"
        );
        document.getElementById("transformacion-precargada").value =
            String(configuracionId);
        actualizarMermaTransformacion();
        calcularInsumosTransformacion();
        document.getElementById("linea-seleccionada-sencilla").textContent = lineaDetalle;
        document.getElementById("transformacion-seleccionada-sencilla").textContent = limpiarNombreProducto(seleccionada.nombre_transformacion);
        transformacionCatalogoActualId = String(seleccionada.transformacion_id);
        document.getElementById("cantidad-base-transformacion").disabled = false;
        document.getElementById("boton-cambiar-transformacion").textContent = "Cambiar";
        cerrarCambioTransformacion();
        await localizarDocumentosTransformacion();
        guardarBorradorTransformacion();
        document.getElementById("cantidad-base-transformacion").focus();
        document.getElementById("cantidad-base-transformacion").select();
        limpiarMensaje();
    } catch (error) { mostrarMensaje(error.message); }
}

function volverAlInicio() {
    eliminarLocal(CLAVE_BORRADOR_TRANSFORMACION);
    window.clearTimeout(temporizadorVistaPreviaTransformacion);
    detalleTransformacionSeleccionada = null;
    insumosTransformacionCalculados = [];
    transformacionPreparada = false;
    transformacionCatalogoActualId = "";
    lineaTransformacionSeleccionada = "";
    document.getElementById("form-relacion").classList.add("hidden");
    const inicio = document.getElementById("panel-inicio");
    inicio.classList.remove("hidden");
    limpiarMensaje();
    inicio.scrollIntoView({ behavior: "smooth", block: "start" });
}

function limpiarFormulario() {
    eliminarLocal(CLAVE_BORRADOR_TRANSFORMACION);
    document.getElementById("form-relacion").reset();
    document.getElementById("fecha-movimiento").valueAsDate = new Date();
    renderizarPartidas("salida", []);
    renderizarPartidas("entrada", []);
    document.getElementById("resumen-salida").textContent = "Selecciona un documento para revisar sus partidas.";
    document.getElementById("resumen-entrada").textContent = "Selecciona un documento para revisar sus partidas.";
    partidasEntrada = [];
    transformacionPreparada = false;
    document.getElementById("resumen-registro-transformacion").classList.add("hidden");
    document.getElementById("boton-guardar").textContent = "Relacionar documentos";
    actualizarCamposAnalisis();
    limpiarMensaje();
}

function solicitarConfirmacionRegistro() {
    return new Promise((resolve) => {
        const modal = document.getElementById("modal-confirmar-registro");
        const botonAceptar = document.getElementById("confirmar-registro-transformacion");
        const botonCancelar = document.getElementById("cancelar-registro-transformacion");
        const productoSalida = limpiarNombreProducto(document.getElementById("base-transformacion").selectedOptions[0]?.textContent) || "Producto consumido";
        const productoEntrada = limpiarNombreProducto(document.getElementById("resultante-transformacion").selectedOptions[0]?.textContent) || "Producto obtenido";
        const cantidadSalida = Number(document.getElementById("cantidad-base-transformacion").value || 0);
        const cantidadEntrada = Number(document.getElementById("cantidad-resultante-transformacion").value || 0);
        const linea = document.getElementById("linea-transformacion").value || "Sin línea";
        const transformacion = limpiarNombreProducto(
            document.getElementById("transformacion-precargada").selectedOptions[0]?.textContent
        ) || "Sin transformación";
        const tablajero = document.getElementById("tablajero-transformacion");
        const porcentajeMerma = Number(
            detalleTransformacionSeleccionada?.porcentaje_merma
            ?? MERMA_TECNICA_PORCENTAJE
        );
        const folios = document.getElementById("resumen-folios-transformacion").textContent || "Por generar";

        document.getElementById("confirmacion-producto-salida").textContent = productoSalida;
        document.getElementById("confirmacion-producto-entrada").textContent = productoEntrada;
        document.getElementById("confirmacion-cantidad-salida").textContent = `${cantidadSalida.toFixed(2)} kg`;
        document.getElementById("confirmacion-cantidad-entrada").textContent = `${cantidadEntrada.toFixed(2)} kg`;
        document.getElementById("confirmacion-linea").textContent = linea;
        document.getElementById("confirmacion-transformacion").textContent = transformacion;
        document.getElementById("confirmacion-tablajero").textContent =
            tablajero.selectedOptions[0]?.textContent || "Sin tablajero";
        document.getElementById("confirmacion-merma").textContent =
            `${porcentajeMerma.toFixed(2)}%`;
        document.getElementById("confirmacion-folios").textContent = folios;

        const panelInsumos = document.getElementById("confirmacion-insumos-panel");
        const listaInsumos = document.getElementById("confirmacion-lista-insumos");
        listaInsumos.replaceChildren();
        insumosTransformacionCalculados.forEach((insumo) => {
            const fila = document.createElement("div");
            fila.className = "confirmation-supply";
            const nombre = document.createElement("span");
            const cantidad = document.createElement("strong");
            const cantidadVisual = convertirCantidadParaMostrar(
                insumo.cantidad_calculada,
                insumo.unidad
            );
            nombre.textContent = limpiarNombreProducto(insumo.producto);
            cantidad.textContent = `${cantidadVisual.cantidad} ${cantidadVisual.unidad}`;
            fila.append(nombre, cantidad);
            listaInsumos.appendChild(fila);
        });
        panelInsumos.classList.toggle("hidden", !insumosTransformacionCalculados.length);
        document.getElementById("confirmacion-total-insumos").textContent =
            `${insumosTransformacionCalculados.length} insumo${insumosTransformacionCalculados.length === 1 ? "" : "s"}`;

        const cerrar = (confirmado) => {
            modal.classList.add("hidden");
            document.body.classList.remove("modal-open");
            botonAceptar.removeEventListener("click", confirmar);
            botonCancelar.removeEventListener("click", cancelar);
            resolve(confirmado);
        };
        const confirmar = () => cerrar(true);
        const cancelar = () => cerrar(false);

        botonAceptar.addEventListener("click", confirmar);
        botonCancelar.addEventListener("click", cancelar);
        modal.classList.remove("hidden");
        document.body.classList.add("modal-open");
        botonAceptar.focus();
    });
}

async function guardarRelacion(evento) {
    evento.preventDefault();
    const formulario = evento.currentTarget;
    if (!formulario.reportValidity()) return;
    const boton = document.getElementById("boton-guardar");
    const registrandoTransformacion = esTransformacion();
    const lineaTransformacion = String(
        document.getElementById("linea-transformacion")?.value
        || detalleTransformacionSeleccionada?.linea
        || lineaTransformacionSeleccionada
        || ""
    ).trim();
    if (registrandoTransformacion && !transformacionPreparada) {
        mostrarMensaje("Primero prepara la relación de transformación.");
        return;
    }
    if (registrandoTransformacion && !lineaTransformacion) {
        mostrarMensaje("No se pudo identificar la línea de la transformación. Selecciona nuevamente el producto.");
        return;
    }
    if (registrandoTransformacion && !(await solicitarConfirmacionRegistro())) {
        return;
    }
    boton.disabled = true;
    boton.textContent = registrandoTransformacion ? "Registrando..." : "Relacionando...";
    const opcionMovimiento = document.getElementById("tipo-movimiento").selectedOptions[0];
    const esAnalisis = Number(opcionMovimiento?.dataset.entrada || 0) === 24
        && Number(opcionMovimiento?.dataset.salida || 0) === 21;
    const payload = registrandoTransformacion ? {
        transformacion_config_id: Number(document.getElementById("transformacion-precargada").value),
        linea: lineaTransformacion,
        producto_base_id: Number(document.getElementById("base-transformacion").value),
        producto_resultante_id: Number(document.getElementById("resultante-transformacion").value),
        cantidad_base: Number(document.getElementById("cantidad-base-transformacion").value),
        cantidad_resultante: Number(document.getElementById("cantidad-resultante-transformacion").value),
        usuario_fisico_id: Number(document.getElementById("tablajero-transformacion").value),
    } : {
        source_document_id: Number(document.getElementById("documento-salida").value),
        destination_document_id: Number(document.getElementById("documento-entrada").value),
        tipo_movimiento: document.getElementById("tipo-movimiento").value,
        proveedor_id: esAnalisis ? Number(document.getElementById("proveedor").value) : 0,
        usuario_fisico_id: esAnalisis ? Number(document.getElementById("usuario-fisico").value) : 0,
        fecha_movimiento: document.getElementById("fecha-movimiento").value,
        destination_brand_id: null,
        marca_nombre: esAnalisis ? document.getElementById("marca").value.trim() : null,
        source_brand_id: null,
    };
    try {
        const respuesta = await solicitarJson(
            registrandoTransformacion
                ? `${API_RELACIONES}/transformacion/registrar`
                : API_RELACIONES,
        {
            method: "POST",
            body: JSON.stringify(payload),
        });
        limpiarFormulario();
        await cargarDatos();
        if (registrandoTransformacion) {
            await actualizarHistorialDesdeServidor();
        }
        const mensaje = String(respuesta["mensaje"] || "Transformación registrada.");
        const folioSalida = String(respuesta["folio_salida"] || "");
        const folioEntrada = String(respuesta["folio_entrada"] || "");
        mostrarMensaje(`${mensaje} ${folioSalida} → ${folioEntrada}`, "success");
    } catch (error) {
        mostrarMensaje(error.message);
    } finally {
        boton.disabled = false;
        boton.textContent = registrandoTransformacion
            ? "Registrar transformación"
            : "Relacionar documentos";
    }
}

async function iniciarSesion(evento) {
    evento?.preventDefault();
    const formulario = document.getElementById("loginForm");
    if (!formulario?.reportValidity()) return;
    const boton = document.getElementById("loginButton");
    const error = document.getElementById("loginError");
    boton.disabled = true;
    boton.textContent = "Entrando...";
    error.textContent = "";
    try {
        await solicitarJson("/login/", {
            method: "POST",
            body: JSON.stringify({
                usuario: document.getElementById("usuario").value.trim(),
                password: document.getElementById("password").value,
            }),
        });
        window.location.assign("/dashboard");
    } catch (e) {
        if (e.status === 403) {
            mostrarAccesoDenegado();
        } else {
            error.textContent = e.message;
        }
    } finally {
        boton.disabled = false;
        boton.textContent = "Entrar";
    }
}

function mostrarAccesoDenegado() {
    const modal = document.getElementById("modal-acceso-denegado");
    if (!modal) return;

    const password = document.getElementById("password");
    if (password) password.value = "";

    modal.classList.remove("hidden");
    document.body.classList.add("modal-open");
    window.setTimeout(() => {
        document.getElementById("cerrar-acceso-denegado")?.focus();
    }, 0);
}

function cerrarAccesoDenegado() {
    const modal = document.getElementById("modal-acceso-denegado");
    if (modal) modal.classList.add("hidden");
    document.body.classList.remove("modal-open");
    document.getElementById("usuario")?.focus();
}

function iniciarPaginaLogin() {
    document.getElementById("loginForm")?.addEventListener(
        "submit",
        iniciarSesion
    );
    document.getElementById("cerrar-acceso-denegado")?.addEventListener(
        "click",
        cerrarAccesoDenegado
    );
}

function mostrarVistaModulo(vista) {
    const vistas = {
        inicio: document.getElementById("vista-inicio"),
        historial: document.getElementById("vista-historial"),
        configuracion: document.getElementById("vista-configuracion"),
        auditoria: document.getElementById("vista-auditoria"),
    };
    if (!vistas[vista]) return;

    Object.entries(vistas).forEach(([nombre, elemento]) => {
        if (elemento) elemento.classList.toggle("hidden", nombre !== vista);
    });

    const navegacion = {
        inicio: document.getElementById("nav-inicio"),
        historial: document.getElementById("nav-historial"),
    };
    Object.entries(navegacion).forEach(([nombre, boton]) => {
        if (!boton) return;
        const activo = nombre === vista;
        boton.classList.toggle("active", activo);
        if (activo) boton.setAttribute("aria-current", "page");
        else boton.removeAttribute("aria-current");
    });

    const botonConfiguracion = document.getElementById("boton-Configuracion");
    if (botonConfiguracion) {
        botonConfiguracion.classList.toggle(
            "current-section",
            ["configuracion", "auditoria"].includes(vista)
        );
    }
    const hash = vista === "inicio" ? "#inicio" : `#${vista}`;
    window.history.replaceState(null, "", hash);
    window.scrollTo({ top: 0, behavior: "smooth" });
}

function abrirConfiguracion() {
    mostrarVistaModulo("configuracion");
}


async function cerrarSesion() {
    try {
        await solicitarJson("/login/logout", { method: "POST" });
    } finally {
        eliminarLocal(CLAVE_BORRADOR_TRANSFORMACION);
        eliminarLocal(CLAVE_BORRADOR_CONFIGURACION);
        window.location.assign("/");
    }
}

function restaurarBorradorConfiguracion() {
    const borrador = leerLocal(CLAVE_BORRADOR_CONFIGURACION);
    const formulario = document.getElementById("form-nueva-configuracion");
    if (!borrador || !formulario) return;

    document.getElementById("config-linea").value = borrador.linea || "";
    document.getElementById("config-nombre").value = borrador.nombre || "";
    document.getElementById("config-cantidad-base").value = borrador.cantidad_base || "";
    document.getElementById("config-merma").value =
        borrador.porcentaje_merma || String(MERMA_TECNICA_PORCENTAJE);
    document.getElementById("config-observaciones").value = borrador.observaciones || "";
    componentesConfiguracion = Array.isArray(borrador.componentes)
        ? borrador.componentes : [];
    configuracionesPendientes = Array.isArray(borrador.pendientes)
        ? borrador.pendientes : [];
    indiceConfiguracionEnEdicion = Number.isInteger(borrador.indice_edicion)
        ? borrador.indice_edicion : -1;
    actualizarCampoMermaConfiguracion();
    renderizarComponentesConfiguracion();
    renderizarConfiguracionesPendientes();
    if (borrador.abierta || nuevaConfiguracionTieneDatos()) {
        formulario.classList.remove("hidden");
        document.getElementById("boton-nueva-configuracion").disabled = true;
        mensajeConfiguracion(
            "Se recuperó automáticamente la captura que estaba pendiente.",
            "success"
        );
    }
}

async function restaurarBorradorTransformacion() {
    const borrador = leerLocal(CLAVE_BORRADOR_TRANSFORMACION);
    if (!borrador?.detalle) return;
    try {
        if (!datosCargados) await cargarDatos();
        detalleTransformacionSeleccionada = borrador.detalle;
        lineaTransformacionSeleccionada = borrador.linea || borrador.detalle.linea || "";
        transformacionCatalogoActualId = String(borrador.catalogo_id || "");
        document.getElementById("panel-inicio").classList.add("hidden");
        document.getElementById("form-relacion").classList.remove("hidden");
        document.getElementById("tipo-movimiento").value = borrador.movimiento || "TRANSFORMACIÓN";
        actualizarCamposAnalisis();
        aplicarPresentacionMovimientoSeleccionado();
        document.getElementById("linea-transformacion").value = lineaTransformacionSeleccionada;
        llenarSelect(
            "base-transformacion",
            [{
                product_id_base: borrador.detalle.producto_base_id,
                producto_base: borrador.detalle.producto_base,
            }],
            "product_id_base", "producto_base", "Producto base"
        );
        document.getElementById("base-transformacion").value =
            String(borrador.detalle.producto_base_id || "");
        llenarSelect(
            "resultante-transformacion", borrador.detalle.resultantes || [],
            "product_id", "producto_resultante", "Producto resultante"
        );
        const primerResultado = borrador.detalle.resultantes?.[0];
        document.getElementById("resultante-transformacion").value =
            String(primerResultado?.product_id || "");
        llenarSelect(
            "transformacion-precargada",
            [{
                transformacion_id: Number(borrador.catalogo_id || 0),
                nombre_transformacion: borrador.detalle.nombre_transformacion,
            }],
            "transformacion_id", "nombre_transformacion", "Transformación"
        );
        document.getElementById("transformacion-precargada").value =
            String(Number(borrador.catalogo_id || 0));
        document.getElementById("cantidad-base-transformacion").disabled = false;
        document.getElementById("cantidad-base-transformacion").value = borrador.kilos || "1";
        document.getElementById("tablajero-transformacion").value = borrador.tablajero || "";
        document.getElementById("linea-seleccionada-sencilla").textContent =
            lineaTransformacionSeleccionada;
        document.getElementById("transformacion-seleccionada-sencilla").textContent =
            limpiarNombreProducto(borrador.detalle.nombre_transformacion);
        document.getElementById("boton-cambiar-transformacion").textContent = "Cambiar";
        actualizarMermaTransformacion();
        calcularInsumosTransformacion();
        await localizarDocumentosTransformacion();
        mostrarMensaje("Se recuperó automáticamente la transformación pendiente.", "success");
    } catch (error) {
        console.warn("No fue posible restaurar el borrador de transformación.", error);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("loginPage")) {
        iniciarPaginaLogin();
        return;
    }
    if (document.getElementById("vista-configuracion")) {
        iniciarPaginaConfiguracion();
        restaurarBorradorConfiguracion();
    }
    renderizarPaginaHistorial();
    document.getElementById("nav-inicio")?.addEventListener("click", () => mostrarVistaModulo("inicio"));
    document.getElementById("nav-historial")?.addEventListener("click", () => {
        mostrarVistaModulo("historial");
        void actualizarHistorialDesdeServidor();
    });
    conectarControlesHistorial();
    document.getElementById("cerrar-detalle-historial")?.addEventListener("click", () => {
        document.getElementById("modal-detalle-historial").classList.add("hidden");
    });
    document.getElementById("fecha-movimiento").valueAsDate = new Date();
    document.getElementById("documento-salida").addEventListener("change", () => cargarPartidas("salida"));
    document.getElementById("documento-entrada").addEventListener("change", () => cargarPartidas("entrada"));
    document.getElementById("tipo-movimiento").addEventListener("change", actualizarCamposAnalisis);
    document.getElementById("boton-iniciar-captura").addEventListener("click", solicitarTipoMovimiento);
    document.getElementById("movimiento-inicial").addEventListener("change", actualizarInicioCaptura);
    document.getElementById("cancelar-inicio-captura").addEventListener("click", cerrarInicioCaptura);
    document.getElementById("continuar-inicio-captura").addEventListener("click", continuarInicioCaptura);
    document.getElementById("boton-cambiar-transformacion").addEventListener("click", abrirCambioTransformacion);
    document.getElementById("cancelar-cambio-transformacion").addEventListener("click", cerrarCambioTransformacion);
    document.getElementById("transformacion-pagina-anterior").addEventListener("click", () => cambiarPaginaTransformaciones(-1));
    document.getElementById("transformacion-pagina-siguiente").addEventListener("click", () => cambiarPaginaTransformaciones(1));
    document.getElementById("boton-volver").addEventListener("click", volverAlInicio);
    document.getElementById("boton-limpiar").addEventListener("click", limpiarFormulario);
    document.getElementById("boton-salir").addEventListener("click", cerrarSesion);
    document.getElementById("boton-Configuracion")?.addEventListener("click", abrirConfiguracion);
    document.getElementById("form-relacion").addEventListener("submit", guardarRelacion);
    document.getElementById("linea-transformacion").addEventListener("change", cargarBasesTransformacion);
    document.getElementById("transformacion-precargada").addEventListener("change", cargarTransformacionPrecargada);
    document.getElementById("cantidad-base-transformacion").addEventListener("input", () => {
        limpiarMensaje();
        limpiarVistaPreviaTransformacion();
        if (!validarKilosTransformacion(false)) {
            actualizarMermaTransformacion();
            calcularInsumosTransformacion();
            window.clearTimeout(temporizadorVistaPreviaTransformacion);
            return;
        }
        actualizarMermaTransformacion();
        calcularInsumosTransformacion();
        guardarBorradorTransformacion();
        window.clearTimeout(temporizadorVistaPreviaTransformacion);
        if (detalleTransformacionSeleccionada) {
            temporizadorVistaPreviaTransformacion = window.setTimeout(
                localizarDocumentosTransformacion,
                350
            );
        }
    });
    document.getElementById("tablajero-transformacion").addEventListener("change", () => {
        if (detalleTransformacionSeleccionada) {
            void localizarDocumentosTransformacion();
            guardarBorradorTransformacion();
        }
    });
    const vistaSolicitada = window.location.hash.replace("#", "");
    if (["historial", "configuracion", "auditoria"].includes(vistaSolicitada)) {
        mostrarVistaModulo(vistaSolicitada);
        if (vistaSolicitada === "historial") {
            void actualizarHistorialDesdeServidor();
        }
        if (vistaSolicitada === "auditoria") {
            void abrirAuditoriaConfiguracion();
        }
    } else {
        void restaurarBorradorTransformacion();
    }
});
