const API_RELACIONES = "/api/relaciones-documentos";
const AJUSTES_INTERFAZ = document.body?.dataset || {};
const MERMA_TECNICA_PORCENTAJE = Number(AJUSTES_INTERFAZ.mermaTecnica || 8);
const FACTOR_RENDIMIENTO = 1 - (MERMA_TECNICA_PORCENTAJE / 100);
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
let componentesConfiguracion = [];
let productosConfiguracionDisponibles = [];
let lineaCatalogoActual = "";
let temporizadorCatalogo = null;
let productosCatalogoActual = [];
let productoCatalogoSeleccionadoId = 0;
let modoEliminacionCatalogo = false;
let controladorCargaComponentesConfiguracion = null;
let paginaCatalogoActual = 1;
const PRODUCTOS_POR_PAGINA = Number(AJUSTES_INTERFAZ.productosPorPagina || 12);
const HISTORIAL_POR_PAGINA = 10;
let paginaHistorialActual = 1;

function limpiarNombreProducto(nombre) {
    return String(nombre || "")
        .replace(/\s*\.?\s*1\s*\(\s*\d+\s*(?:-\s*\d+|\+)\s*\)\s*$/i, "")
        .trim();
}

function llenarConfigSelect(elemento, registros, placeholder) {
    elemento.replaceChildren(new Option(placeholder, ""));
    registros.forEach((registro) => {
        const opcion = new Option(limpiarNombreProducto(registro.producto), String(registro.product_id));
        opcion.dataset.unidad = registro.unidad || "KILO";
        elemento.add(opcion);
    });
    elemento.disabled = registros.length === 0;
}

function mensajeConfiguracion(texto, tipo = "error") {
    const mensaje = document.getElementById("mensaje-configuracion");
    mensaje.textContent = texto;
    mensaje.className = `message visible ${tipo}`;
}

function obtenerProductosOcultos() {
    try {
        return new Set(JSON.parse(localStorage.getItem("cayal-productos-ocultos") || "[]").map(Number));
    } catch (_) {
        return new Set();
    }
}

function guardarProductosOcultos(productos) {
    try {
        localStorage.setItem("cayal-productos-ocultos", JSON.stringify([...productos]));
    } catch (_) {
        // El ocultamiento sigue funcionando durante la sesión actual.
    }
}

async function abrirDetalleProductoCatalogo(producto) {
    const modal = document.getElementById("modal-detalle-producto");
    const cuerpo = document.getElementById("detalle-producto-componentes");
    document.getElementById("titulo-detalle-producto").textContent = limpiarNombreProducto(producto.producto);
    document.getElementById("mensaje-detalle-producto").textContent = "Consultando ingredientes en SSM...";
    cuerpo.replaceChildren();
    modal.classList.remove("hidden");
    try {
        const componentes = await solicitarJson(`${API_CONFIGURACION}/formula/${producto.product_id}`);
        document.getElementById("mensaje-detalle-producto").textContent = componentes.length
            ? "Ingredientes registrados para este producto."
            : "Este producto no tiene ingredientes registrados.";
        componentes.forEach((componente) => {
            const fila = document.createElement("tr");
            [
                limpiarNombreProducto(componente.producto),
                Number(componente.cantidad || 0).toFixed(3),
                componente.unidad || "SIN UNIDAD",
            ].forEach((valor) => {
                const celda = document.createElement("td");
                celda.textContent = valor;
                fila.appendChild(celda);
            });
            cuerpo.appendChild(fila);
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
            fila.dataset.productoId = String(producto.product_id);
            const nombre = document.createElement("strong");
            nombre.textContent = limpiarNombreProducto(producto.producto);
            const unidad = document.createElement("span");
            unidad.textContent = producto.unidad || "SIN UNIDAD";
            fila.append(nombre, unidad);
            fila.addEventListener("click", async () => {
                if (modoEliminacionCatalogo) {
                    const confirmado = await solicitarConfirmacionEliminarProductoCatalogo(
                        producto
                    );
                    if (confirmado) {
                        ocultarProductoCatalogo(Number(producto.product_id));
                    }
                    return;
                }
                productoCatalogoSeleccionadoId = Number(producto.product_id);
                document.querySelectorAll(".catalog-product").forEach((elemento) => {
                    elemento.classList.toggle("selected", elemento === fila);
                });
            });
            fila.addEventListener("dblclick", () => {
                if (!modoEliminacionCatalogo) abrirDetalleProductoCatalogo(producto);
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

async function cargarProductosCatalogo(linea, termino = "") {
    lineaCatalogoActual = linea;
    const panel = document.getElementById("catalogo-productos");
    const lista = document.getElementById("lista-productos-catalogo");
    panel.classList.remove("hidden");
    document.getElementById("configuraciones-guardadas").classList.add("hidden");
    document.getElementById("catalogo-productos-titulo").textContent = linea;
    document.getElementById("catalogo-productos-total").textContent = "";
    lista.innerHTML = '<p class="catalog-loading">Consultando productos en SSM...</p>';
    document.getElementById("paginacion-productos-catalogo").classList.add("hidden");
    document.querySelectorAll(".configuration-line").forEach((boton) => {
        boton.classList.toggle("active", boton.dataset.linea === linea);
    });
    try {
        const productos = await solicitarJson(
            `${API_CONFIGURACION}/productos-base?linea=${encodeURIComponent(linea)}&termino=${encodeURIComponent(termino)}`
        );
        const ocultos = obtenerProductosOcultos();
        productosCatalogoActual = productos.filter(
            (producto) => !ocultos.has(Number(producto.product_id))
        );
        productoCatalogoSeleccionadoId = 0;
        paginaCatalogoActual = 1;
        renderizarPaginaCatalogo();
        document.getElementById("catalogo-productos-total").textContent =
            `${productosCatalogoActual.length} producto${productosCatalogoActual.length === 1 ? "" : "s"}`;
    } catch (error) {
        productosCatalogoActual = [];
        document.getElementById("paginacion-productos-catalogo").classList.add("hidden");
        lista.innerHTML = `<p class="catalog-loading catalog-error">${error.message}</p>`;
    }
}

function ocultarProductoCatalogo(productoId) {
    if (!modoEliminacionCatalogo || !productoId) return;
    const ocultos = obtenerProductosOcultos();
    ocultos.add(productoId);
    guardarProductosOcultos(ocultos);
    productosCatalogoActual = productosCatalogoActual.filter(
        (producto) => Number(producto.product_id) !== productoId
    );
    productoCatalogoSeleccionadoId = 0;
    renderizarPaginaCatalogo();
    document.getElementById("catalogo-productos-total").textContent =
        `${productosCatalogoActual.length} productos visibles`;
}

function solicitarConfirmacionEliminarProductoCatalogo(producto) {
    return new Promise((resolve) => {
        const modal = document.getElementById("modal-confirmar-eliminacion-producto");
        const botonConfirmar = document.getElementById("confirmar-eliminacion-producto");
        const botonCancelar = document.getElementById("cancelar-eliminacion-producto");
        const nombre = limpiarNombreProducto(producto?.producto) || "Producto seleccionado";

        document.getElementById("nombre-producto-a-eliminar").textContent = nombre;

        const cerrar = (confirmado) => {
            modal.classList.add("hidden");
            document.body.classList.remove("modal-open");
            botonConfirmar.removeEventListener("click", confirmar);
            botonCancelar.removeEventListener("click", cancelar);
            resolve(confirmado);
        };
        const confirmar = () => cerrar(true);
        const cancelar = () => cerrar(false);

        botonConfirmar.addEventListener("click", confirmar);
        botonCancelar.addEventListener("click", cancelar);
        modal.classList.remove("hidden");
        document.body.classList.add("modal-open");
        botonCancelar.focus();
    });
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
    document.getElementById("catalogo-productos")?.classList.remove("delete-mode");
    const eliminar = document.getElementById("eliminar-producto-catalogo");
    if (eliminar) {
        eliminar.classList.remove("active");
        eliminar.textContent = "Eliminar";
    }
    document.getElementById("cancelar-eliminacion-catalogo")?.classList.add("hidden");
    const ayuda = document.getElementById("ayuda-interaccion-catalogo");
    if (ayuda) ayuda.textContent = "Un clic selecciona el producto; doble clic muestra sus insumos.";
}

function cerrarCatalogoProductos() {
    cancelarEliminacionCatalogo();
    document.getElementById("catalogo-productos").classList.add("hidden");
    document.getElementById("configuraciones-guardadas").classList.remove("hidden");
    document.getElementById("buscar-producto-catalogo").value = "";
    document.querySelectorAll(".configuration-line").forEach((boton) => boton.classList.remove("active"));
    lineaCatalogoActual = "";
    productosCatalogoActual = [];
    productoCatalogoSeleccionadoId = 0;
    paginaCatalogoActual = 1;
}

async function cargarProductosConfiguracion() {
    const linea = document.getElementById("config-linea").value;
    const selector = document.getElementById("config-insumo-producto");
    const botonAsignar = document.getElementById("ir-asignar-insumos");
    cancelarCargaComponentesConfiguracion();
    cerrarAsignacionInsumosConfiguracion();
    componentesConfiguracion = [];
    productosConfiguracionDisponibles = [];
    renderizarComponentesConfiguracion();
    if (!linea) {
        llenarConfigSelect(selector, [], "Selecciona primero una línea");
        botonAsignar.textContent = "Asignar producto base e insumos";
        document.getElementById("config-nombres-disponibles").replaceChildren();
        return;
    }
    try {
        botonAsignar.textContent = "Asignar producto base e insumos";
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
            mensajeConfiguracion("Esta línea no tiene productos disponibles en SSM.");
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
        boton.textContent = "Asignar producto base e insumos";
    }
}

async function agregarBaseSugeridaConfiguracion() {
    const linea = document.getElementById("config-linea").value;
    const nombre = document.getElementById("config-nombre").value.trim();
    if (!linea || nombre.length < 3 || !productosConfiguracionDisponibles.length) {
        return;
    }
    try {
        const sugerencia = await solicitarJson(
            `${API_CONFIGURACION}/base-sugerida?linea=${encodeURIComponent(linea)}&nombre=${encodeURIComponent(nombre)}`
        );
        if (!sugerencia?.producto_base_id) return;

        const baseExistente = componentesConfiguracion.find(
            (componente) => componente.es_base
        );
        if (baseExistente) {
            if (!baseExistente.es_sugerido) return;
            if (
                Number(baseExistente.producto_id) ===
                Number(sugerencia.producto_base_id)
            ) {
                baseExistente.cantidad =
                    Number(document.getElementById("config-cantidad-base").value) ||
                    baseExistente.cantidad;
                renderizarComponentesConfiguracion();
                return;
            }
            componentesConfiguracion = componentesConfiguracion.filter(
                (componente) => componente !== baseExistente
            );
        }

        const producto = productosConfiguracionDisponibles.find(
            (registro) =>
                Number(registro.product_id) === Number(sugerencia.producto_base_id)
        );
        if (!producto) return;

        componentesConfiguracion.push({
            producto_id: Number(producto.product_id),
            producto: limpiarNombreProducto(producto.producto),
            cantidad: Number(document.getElementById("config-cantidad-base").value) || 1,
            unidad: producto.unidad || sugerencia.unidad || "KILO",
            es_base: true,
            es_sugerido: true,
        });
        renderizarComponentesConfiguracion();
        mensajeConfiguracion(
            `Producto base relacionado automáticamente: ${limpiarNombreProducto(producto.producto)}.`,
            "success"
        );
    } catch (error) {
        console.error("No fue posible sugerir el producto base.", error);
    }
}

function cancelarCargaComponentesConfiguracion() {
    controladorCargaComponentesConfiguracion?.abort();
    controladorCargaComponentesConfiguracion = null;
    const boton = document.getElementById("ir-asignar-insumos");
    if (boton) {
        boton.classList.remove("active");
        boton.textContent = "Asignar producto base e insumos";
    }
}

function cerrarAsignacionInsumosConfiguracion() {
    const seccion = document.getElementById("config-formula");
    const boton = document.getElementById("ir-asignar-insumos");
    if (!seccion || !boton) return;
    seccion.classList.add("hidden");
    boton.classList.remove("active");
    boton.textContent = "Asignar producto base e insumos";
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
    if (!(await cargarComponentesParaAsignacion())) return;
    await agregarBaseSugeridaConfiguracion();
    seccion.classList.remove("hidden");
    boton.classList.add("active");
    boton.textContent = "Cerrar asignación";
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
        [
            componente.producto,
            componente.es_base ? "Producto base" : "Insumo",
            Number(componente.cantidad).toFixed(3),
            componente.unidad,
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
        });
        acciones.appendChild(quitar);
        fila.appendChild(acciones);
        cuerpo.appendChild(fila);
    });
}

function agregarComponenteConfiguracion() {
    const selector = document.getElementById("config-insumo-producto");
    const productoId = Number(selector.value || 0);
    const cantidad = Number(document.getElementById("config-insumo-cantidad").value || 0);
    const esBase = document.getElementById("config-insumo-tipo").value === "BASE";
    const producto = productosConfiguracionDisponibles.find(
        (registro) => Number(registro.product_id) === productoId
    );
    if (!producto || cantidad <= 0) {
        mensajeConfiguracion("Selecciona un producto y captura una cantidad válida.");
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
        unidad: producto.unidad || "KILO",
        es_base: esBase,
    });
    selector.value = "";
    document.getElementById("config-insumo-cantidad").value = "";
    document.getElementById("config-insumo-tipo").value = "INSUMO";
    document.getElementById("config-insumo-unidad").textContent = "kg";
    limpiarMensajeConfiguracion();
    renderizarComponentesConfiguracion();
}

function abrirNuevaConfiguracion() {
    const formulario = document.getElementById("form-nueva-configuracion");
    formulario.classList.remove("hidden");
    document.getElementById("boton-nueva-configuracion").disabled = true;
    document.getElementById("config-linea").focus();
    formulario.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function cerrarNuevaConfiguracion() {
    cancelarCargaComponentesConfiguracion();
    const formulario = document.getElementById("form-nueva-configuracion");
    formulario.reset();
    componentesConfiguracion = [];
    productosConfiguracionDisponibles = [];
    llenarConfigSelect(document.getElementById("config-insumo-producto"), [], "Selecciona primero una línea");
    cerrarAsignacionInsumosConfiguracion();
    renderizarComponentesConfiguracion();
    limpiarMensajeConfiguracion();
    formulario.classList.add("hidden");
    document.getElementById("boton-nueva-configuracion").disabled = false;
    document.getElementById("boton-nueva-configuracion").focus();
}

async function guardarNuevaConfiguracion(evento) {
    evento.preventDefault();
    const formulario = evento.currentTarget;
    if (!formulario.reportValidity()) return;
    const boton = document.getElementById("guardar-configuracion");
    if (!componentesConfiguracion.length) {
        mensajeConfiguracion("Agrega por lo menos un producto o insumo.");
        return;
    }
    if (componentesConfiguracion.filter((componente) => componente.es_base).length !== 1) {
        mensajeConfiguracion("Marca exactamente un ingrediente como producto base.");
        return;
    }
    boton.disabled = true;
    boton.textContent = "Guardando...";
    try {
        await solicitarJson(`${API_CONFIGURACION}/transformaciones`, {
            method: "POST",
            body: JSON.stringify({
                nombre: document.getElementById("config-nombre").value.trim(),
                linea: document.getElementById("config-linea").value,
                cantidad_base: Number(document.getElementById("config-cantidad-base").value),
                porcentaje_merma: Number(document.getElementById("config-merma").value),
                componentes: componentesConfiguracion.map((componente) => ({
                    producto_id: componente.producto_id,
                    cantidad: componente.cantidad,
                    unidad: componente.unidad,
                    es_base: componente.es_base,
                })),
                observaciones: document.getElementById("config-observaciones").value.trim() || null,
            }),
        });
        mensajeConfiguracion("Configuración guardada. Ya está disponible en el módulo de transformación.", "success");
        window.setTimeout(() => window.location.reload(), 900);
    } catch (error) {
        mensajeConfiguracion(error.message);
        boton.disabled = false;
        boton.textContent = "Guardar configuración";
    }
}

function iniciarPaginaConfiguracion() {
    const formulario = document.getElementById("form-nueva-configuracion");
    if (formulario) {
        document.getElementById("boton-nueva-configuracion").addEventListener("click", abrirNuevaConfiguracion);
        document.getElementById("cancelar-nueva-configuracion").addEventListener("click", cerrarNuevaConfiguracion);
        document.getElementById("config-linea").addEventListener("change", cargarProductosConfiguracion);
        document.getElementById("config-nombre").addEventListener("change", () => {
            if (!document.getElementById("config-formula").classList.contains("hidden")) {
                agregarBaseSugeridaConfiguracion();
            }
        });
        document.getElementById("config-cantidad-base").addEventListener("input", (evento) => {
            const baseSugerida = componentesConfiguracion.find(
                (componente) => componente.es_base && componente.es_sugerido
            );
            if (baseSugerida && Number(evento.target.value) > 0) {
                baseSugerida.cantidad = Number(evento.target.value);
                renderizarComponentesConfiguracion();
            }
        });
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
        });
        document.getElementById("agregar-config-insumo").addEventListener("click", agregarComponenteConfiguracion);
        formulario.addEventListener("submit", guardarNuevaConfiguracion);
    }
    document.querySelectorAll(".configuration-line").forEach((boton) => {
        boton.addEventListener("click", () => {
            cancelarEliminacionCatalogo();
            document.getElementById("buscar-producto-catalogo").value = "";
            cargarProductosCatalogo(boton.dataset.linea);
        });
    });
    document.getElementById("cerrar-catalogo-productos").addEventListener("click", cerrarCatalogoProductos);
    document.getElementById("eliminar-producto-catalogo").addEventListener("click", activarEliminacionCatalogo);
    document.getElementById("cancelar-eliminacion-catalogo").addEventListener("click", cancelarEliminacionCatalogo);
    document.getElementById("cerrar-detalle-producto").addEventListener("click", () => {
        document.getElementById("modal-detalle-producto").classList.add("hidden");
    });
    document.getElementById("catalogo-pagina-anterior").addEventListener("click", () => cambiarPaginaCatalogo(-1));
    document.getElementById("catalogo-pagina-siguiente").addEventListener("click", () => cambiarPaginaCatalogo(1));
    document.getElementById("buscar-producto-catalogo").addEventListener("input", (evento) => {
        window.clearTimeout(temporizadorCatalogo);
        temporizadorCatalogo = window.setTimeout(() => {
            if (lineaCatalogoActual) cargarProductosCatalogo(lineaCatalogoActual, evento.target.value.trim());
        }, 250);
    });
}

function renderizarPaginaHistorial() {
    const filas = [...document.querySelectorAll("#filas-historial .history-row")];
    const paginacion = document.getElementById("paginacion-historial");
    if (!paginacion) return;

    const totalPaginas = Math.max(Math.ceil(filas.length / HISTORIAL_POR_PAGINA), 1);
    paginaHistorialActual = Math.min(Math.max(paginaHistorialActual, 1), totalPaginas);
    const inicio = (paginaHistorialActual - 1) * HISTORIAL_POR_PAGINA;
    const fin = inicio + HISTORIAL_POR_PAGINA;
    filas.forEach((fila, indice) => fila.classList.toggle("hidden", indice < inicio || indice >= fin));

    document.getElementById("historial-pagina-actual").textContent =
        `Página ${paginaHistorialActual} de ${totalPaginas} (${filas.length} registros)`;
    document.getElementById("historial-pagina-anterior").disabled = paginaHistorialActual <= 1;
    document.getElementById("historial-pagina-siguiente").disabled = paginaHistorialActual >= totalPaginas;
    paginacion.classList.toggle("hidden", filas.length <= HISTORIAL_POR_PAGINA);
}

function cambiarPaginaHistorial(desplazamiento) {
    paginaHistorialActual += desplazamiento;
    renderizarPaginaHistorial();
}

function conectarControlesHistorial() {
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
    document.querySelectorAll("#filas-historial .history-row").forEach((fila) => {
        const abrir = () => abrirDetalleHistorial(Number(fila.dataset.relacionId));
        fila.addEventListener("click", abrir);
        fila.addEventListener("keydown", (evento) => {
            if (evento.key === "Enter" || evento.key === " ") {
                evento.preventDefault();
                abrir();
            }
        });
    });
}

async function actualizarHistorialDesdeServidor() {
    const historialActual = document.getElementById("vista-historial");
    if (!historialActual) return;

    try {
        const respuesta = await fetch("/dashboard", {
            credentials: "same-origin",
            cache: "no-store",
        });
        if (!respuesta.ok) return;

        const documento = new DOMParser().parseFromString(
            await respuesta.text(),
            "text/html"
        );
        const historialNuevo = documento.getElementById("vista-historial");
        if (!historialNuevo) return;

        historialActual.innerHTML = historialNuevo.innerHTML;
        paginaHistorialActual = 1;
        conectarControlesHistorial();
        renderizarPaginaHistorial();
    } catch (error) {
        console.error("No fue posible actualizar el historial.", error);
    }
}

function crearDocumentoDetalleHistorial(titulo, folio, partidas, tipo) {
    const tarjeta = document.createElement("article");
    tarjeta.className = `history-detail-document history-detail-${tipo}`;
    const encabezado = document.createElement("header");
    const etiqueta = document.createElement("small");
    etiqueta.textContent = titulo;
    const folioElemento = document.createElement("strong");
    folioElemento.textContent = folio || "Sin folio";
    encabezado.append(etiqueta, folioElemento);
    tarjeta.appendChild(encabezado);

    const tabla = document.createElement("table");
    tabla.className = "registration-table";
    tabla.innerHTML = "<thead><tr><th>Producto</th><th>Cantidad</th></tr></thead>";
    const cuerpo = document.createElement("tbody");
    (partidas || []).forEach((partida) => {
        const fila = document.createElement("tr");
        const producto = document.createElement("td");
        producto.textContent = limpiarNombreProducto(partida.ProductName) || "Producto";
        const cantidad = document.createElement("td");
        cantidad.textContent = `${Number(partida.Quantity || 0).toFixed(3)} kg`;
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
    return tarjeta;
}

async function abrirDetalleHistorial(relacionId) {
    const modal = document.getElementById("modal-detalle-historial");
    const contenido = document.getElementById("detalle-historial-contenido");
    contenido.innerHTML = '<p class="catalog-loading">Consultando documentos en SSM...</p>';
    modal.classList.remove("hidden");
    try {
        const detalle = await solicitarJson(`${API_RELACIONES}/historial/${relacionId}`);
        document.getElementById("titulo-detalle-historial").textContent =
            `${detalle.folio_salida} → ${detalle.folio_entrada}`;
        contenido.replaceChildren(
            crearDocumentoDetalleHistorial("Documento de salida", detalle.folio_salida, detalle.salida, "out"),
            crearDocumentoDetalleHistorial("Documento de entrada", detalle.folio_entrada, detalle.entrada, "in")
        );
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

function exportarHistorialExcel() {
    const encabezados = [
        "FECHA", "RESPONSABLE", "PRODUCTO ORIGEN", "SALIDA", "ENTRADA",
        "MERMA", "PRODUCTO RESULTANTE", "DOCUMENTOS", "ESTADO",
    ];
    const filas = [...document.querySelectorAll("#filas-historial .history-row")]
        .map((fila) => [...fila.cells].map((celda) => celda.textContent.trim().replace(/\s+/g, " ")));
    const celda = (valor, estilo = "Dato") =>
        `<Cell ss:StyleID="${estilo}"><Data ss:Type="String">${escaparXml(valor)}</Data></Cell>`;
    const filasXml = filas.map((valores) =>
        `<Row>${valores.map((valor) => celda(valor)).join("")}</Row>`
    ).join("");
    const xml = `<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Styles>
  <Style ss:ID="Titulo"><Font ss:Bold="1" ss:Size="16" ss:Color="#FFFFFF"/><Interior ss:Color="#B51223" ss:Pattern="Solid"/></Style>
  <Style ss:ID="Encabezado"><Font ss:Bold="1" ss:Color="#FFFFFF"/><Interior ss:Color="#172033" ss:Pattern="Solid"/><Alignment ss:Vertical="Center" ss:WrapText="1"/></Style>
  <Style ss:ID="Dato"><Borders><Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#D8E0EA"/></Borders><Alignment ss:Vertical="Center" ss:WrapText="1"/></Style>
 </Styles>
 <Worksheet ss:Name="Transformaciones">
  <Table>
   <Column ss:Width="85"/><Column ss:Width="150"/><Column ss:Width="180"/><Column ss:Width="75"/><Column ss:Width="75"/><Column ss:Width="85"/><Column ss:Width="190"/><Column ss:Width="135"/><Column ss:Width="85"/>
   <Row ss:Height="28"><Cell ss:MergeAcross="8" ss:StyleID="Titulo"><Data ss:Type="String">CARNES CAYAL · HISTORIAL DE TRANSFORMACIONES</Data></Cell></Row>
   <Row><Cell ss:MergeAcross="8" ss:StyleID="Dato"><Data ss:Type="String">Generado: ${escaparXml(new Date().toLocaleString("es-MX"))}</Data></Cell></Row>
   <Row>${encabezados.map((valor) => celda(valor, "Encabezado")).join("")}</Row>
   ${filasXml}
  </Table>
  <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel"><FreezePanes/><FrozenNoSplit/><SplitHorizontal>3</SplitHorizontal><TopRowBottomPane>3</TopRowBottomPane><Selected/></WorksheetOptions>
 </Worksheet>
</Workbook>`;
    const archivo = new Blob([xml], { type: "application/vnd.ms-excel;charset=utf-8" });
    const enlace = document.createElement("a");
    const fecha = new Date().toISOString().slice(0, 10);
    enlace.href = URL.createObjectURL(archivo);
    enlace.download = `historial_transformaciones_${fecha}.xls`;
    enlace.click();
    window.setTimeout(() => URL.revokeObjectURL(enlace.href), 1000);
}

async function solicitarJson(url, opciones = {}) {
    const respuesta = await fetch(url, {
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", ...(opciones.headers || {}) },
        ...opciones,
    });
    let datos = {};
    try { datos = await respuesta.json(); } catch (_) { datos = {}; }
    if (respuesta.status === 401 && !document.getElementById("loginPage")) {
        window.location.assign("/");
        throw new Error("La sesión terminó.");
    }
    if (!respuesta.ok) {
        const detalle = Array.isArray(datos.detail)
            ? datos.detail.map((item) => item.msg).join(" ")
            : datos.detail || "No fue posible completar la operación.";
        throw new Error(detalle);
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

function formatoDinero(valor) {
    return Number(valor || 0).toLocaleString("es-MX", {
        style: "currency",
        currency: "MXN",
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
    respuestas.flat().forEach((marca) => mapa.set(Number(marca.BrandID), marca));
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

async function prepararMovimientoSeleccionado() {
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
    document.getElementById("resumen-sencillo-transformacion")?.classList.add("hidden");
    renderizarInsumosTransformacion();
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
    document.getElementById("resumen-sencillo-transformacion")?.classList.add("hidden");
    llenarSelect("base-transformacion", [], "product_id_base", "producto_base", "Se completa automáticamente");
    llenarSelect("resultante-transformacion", [], "product_id", "producto_resultante", "Selecciona un producto resultante");
    renderizarInsumosTransformacion();
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
        renderizarInsumosTransformacion();
        return;
    }
    try {
        const detalle = await solicitarJson(`${API_RELACIONES}/transformacion/precargadas/${transformacionId}`);
        detalleTransformacionSeleccionada = detalle;
        llenarSelect("base-transformacion", [{ product_id_base: detalle.producto_base_id, producto_base: detalle.producto_base }], "product_id_base", "producto_base", "Producto base");
        document.getElementById("base-transformacion").value = String(detalle.producto_base_id);
        llenarSelect("resultante-transformacion", detalle.resultantes, "product_id", "producto_resultante", "Producto resultante");
        document.getElementById("resultante-transformacion").value = String(detalle.resultantes[0].product_id);
        const nombreBaseSencillo = document.getElementById("nombre-base-sencillo");
        const nombreResultanteSencillo = document.getElementById("nombre-resultante-sencillo");
        if (nombreBaseSencillo) nombreBaseSencillo.textContent = limpiarNombreProducto(detalle.producto_base);
        if (nombreResultanteSencillo) nombreResultanteSencillo.textContent = limpiarNombreProducto(detalle.resultantes[0].producto_resultante);
        document.getElementById("resumen-sencillo-transformacion")?.classList.remove("hidden");
        actualizarMermaTransformacion();
        renderizarInsumosTransformacion();
        limpiarMensaje();
    } catch (error) { mostrarMensaje(error.message); }
}

function renderizarInsumosTransformacion() {
    const cuerpo = document.getElementById("tabla-insumos-transformacion");
    const panel = document.getElementById("panel-insumos-transformacion");
    if (cuerpo) cuerpo.replaceChildren();
    insumosTransformacionCalculados = [];
    if (!detalleTransformacionSeleccionada) {
        if (panel) panel.classList.add("hidden");
        return;
    }
    const componentes = detalleTransformacionSeleccionada.componentes || [];
    const baseReceta = componentes.find((componente) => componente.es_producto_base);
    const kilos = Number(document.getElementById("cantidad-base-transformacion").value || 0);
    const factor = Number(baseReceta?.cantidad || 0) > 0
        ? kilos / Number(baseReceta.cantidad)
        : 1;
    insumosTransformacionCalculados = componentes
        .filter((componente) => !componente.es_producto_base)
        .map((componente) => ({
            ...componente,
            cantidad_calculada: Number(componente.cantidad || 0) * factor,
        }));
    if (cuerpo) {
        insumosTransformacionCalculados.forEach((insumo) => {
            const fila = document.createElement("tr");
            [insumo.producto, formatoNumero(insumo.cantidad_calculada, 3), insumo.unidad].forEach((texto) => {
                const celda = document.createElement("td");
                celda.textContent = texto;
                fila.appendChild(celda);
            });
            cuerpo.appendChild(fila);
        });
    }
    if (panel) panel.classList.toggle("hidden", !insumosTransformacionCalculados.length);
}

function actualizarMermaTransformacion() {
    const base = Number(document.getElementById("cantidad-base-transformacion").value || 0);
    const porcentajeMerma = Number(
        detalleTransformacionSeleccionada?.porcentaje_merma ??
        MERMA_TECNICA_PORCENTAJE
    );
    const factorRendimiento = 1 - (porcentajeMerma / 100);
    const resultante = base * factorRendimiento;
    document.getElementById("cantidad-resultante-transformacion").value = resultante.toFixed(3);
    const pesoAproximado = document.getElementById("peso-aproximado-transformacion");
    if (pesoAproximado) pesoAproximado.textContent = resultante.toFixed(3);
    const merma = base * (porcentajeMerma / 100);
    const porcentaje = base > 0 ? porcentajeMerma : 0;
    const nivelNormal = porcentaje <= MERMA_TECNICA_PORCENTAJE;
    const etiquetaMerma = document.getElementById("merma-transformacion-activa");
    if (etiquetaMerma) etiquetaMerma.textContent = `Merma: ${porcentajeMerma.toFixed(1)}%`;
    const resumen = document.getElementById("resumen-merma-transformacion");
    if (resumen) {
        resumen.textContent = base > 0
            ? `De ${base.toFixed(3)} kg se obtendrán aproximadamente ${resultante.toFixed(3)} kg.`
            : "Escribe los kilos que vas a utilizar.";
        resumen.classList.toggle("merma-normal", nivelNormal);
        resumen.classList.toggle("merma-alerta", !nivelNormal);
    }
    const pesoSencillo = document.getElementById("peso-resultante-sencillo");
    if (pesoSencillo) pesoSencillo.textContent = `${resultante.toFixed(3)} kg`;
    return { merma, porcentaje, nivelNormal };
}

async function localizarDocumentosTransformacion() {
    const transformacionConfigId = Number(document.getElementById("transformacion-precargada").value || 0);
    const baseId = Number(document.getElementById("base-transformacion").value || 0);
    const resultanteId = Number(document.getElementById("resultante-transformacion").value || 0);
    const cantidadBase = Number(document.getElementById("cantidad-base-transformacion").value || 0);
    const cantidadResultante = Number(document.getElementById("cantidad-resultante-transformacion").value || 0);
    const tablajero = document.getElementById("tablajero-transformacion");
    if (!detalleTransformacionSeleccionada || !baseId || !resultanteId || cantidadBase <= 0 || cantidadResultante <= 0) {
        mostrarMensaje("No fue posible preparar la transformación. Revisa los kilos e inténtalo nuevamente.");
        return;
    }
    const boton = document.getElementById("localizar-documentos");
    if (boton) boton.disabled = true;
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
    } finally {
        if (boton) boton.disabled = false;
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
        transformacionesDisponibles = await solicitarJson(
            `${API_RELACIONES}/transformacion/disponibles`
        );
        const movimientosPermitidos = catalogos.movimientos.filter((registro) =>
            Number(registro.EntradaID) === 5 && Number(registro.SalidaID) === 2
        );
        llenarSelect(
            "movimiento-inicial", movimientosPermitidos,
            "ItemValue", "ItemValue", "Selecciona el movimiento"
        );
        const lineas = [...new Set(
            transformacionesDisponibles.map((registro) => registro.linea).filter(Boolean)
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
        window.alert(error.message);
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
            transformacionesDisponibles = await solicitarJson(
                `${API_RELACIONES}/transformacion/disponibles`
            );
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
                seleccionarTransformacionAlternativa(transformacion.transformacion_id)
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

async function seleccionarTransformacionAlternativa(transformacionId) {
    const seleccionada = transformacionesDisponibles.find(
        (registro) => String(registro.transformacion_id) === String(transformacionId)
    );
    if (!seleccionada) return;
    try {
        limpiarVistaPreviaTransformacion();
        const detalle = await solicitarJson(
            `${API_RELACIONES}/transformacion/catalogo/${seleccionada.transformacion_id}`
        );
        detalleTransformacionSeleccionada = detalle;
        document.getElementById("linea-transformacion").value = detalle.linea;
        llenarSelect(
            "base-transformacion",
            [{ product_id_base: detalle.producto_base_id, producto_base: detalle.producto_base }],
            "product_id_base", "producto_base", "Producto base"
        );
        document.getElementById("base-transformacion").value = String(detalle.producto_base_id);
        llenarSelect(
            "resultante-transformacion", detalle.resultantes,
            "product_id", "producto_resultante", "Producto resultante"
        );
        document.getElementById("resultante-transformacion").value = String(detalle.resultantes[0].product_id);
        llenarSelect(
            "transformacion-precargada",
            [{ transformacion_id: 0, nombre_transformacion: detalle.nombre_transformacion }],
            "transformacion_id", "nombre_transformacion", "Transformación"
        );
        document.getElementById("transformacion-precargada").value = "0";
        actualizarMermaTransformacion();
        renderizarInsumosTransformacion();
        document.getElementById("linea-seleccionada-sencilla").textContent = seleccionada.linea;
        document.getElementById("transformacion-seleccionada-sencilla").textContent = limpiarNombreProducto(seleccionada.nombre_transformacion);
        transformacionCatalogoActualId = String(seleccionada.transformacion_id);
        document.getElementById("cantidad-base-transformacion").disabled = false;
        document.getElementById("boton-cambiar-transformacion").textContent = "Cambiar";
        cerrarCambioTransformacion();
        await localizarDocumentosTransformacion();
        document.getElementById("cantidad-base-transformacion").focus();
        document.getElementById("cantidad-base-transformacion").select();
        limpiarMensaje();
    } catch (error) { mostrarMensaje(error.message); }
}

function volverAlInicio() {
    document.getElementById("form-relacion").classList.add("hidden");
    const inicio = document.getElementById("panel-inicio");
    inicio.classList.remove("hidden");
    limpiarMensaje();
    inicio.scrollIntoView({ behavior: "smooth", block: "start" });
}

function limpiarFormulario() {
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

        document.getElementById("confirmacion-producto-salida").textContent = productoSalida;
        document.getElementById("confirmacion-producto-entrada").textContent = productoEntrada;
        document.getElementById("confirmacion-cantidad-salida").textContent = `${cantidadSalida.toFixed(3)} kg`;
        document.getElementById("confirmacion-cantidad-entrada").textContent = `${cantidadEntrada.toFixed(3)} kg`;

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
    if (registrandoTransformacion && !transformacionPreparada) {
        mostrarMensaje("Primero prepara la relación de transformación.");
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
    const fechaRegistro = new Date();
    const fechaAutomatica = [
        fechaRegistro.getFullYear(),
        String(fechaRegistro.getMonth() + 1).padStart(2, "0"),
        String(fechaRegistro.getDate()).padStart(2, "0"),
    ].join("-");
    const payload = registrandoTransformacion ? {
        transformacion_config_id: Number(document.getElementById("transformacion-precargada").value),
        linea: document.getElementById("linea-transformacion").value,
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
        mostrarMensaje(`${respuesta.mensaje} ${respuesta.folio_salida} → ${respuesta.folio_entrada}`, "success");
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
        error.textContent = e.message;
    } finally {
        boton.disabled = false;
        boton.textContent = "Entrar";
    }
}

function iniciarPaginaLogin() {
    document.getElementById("loginForm")?.addEventListener(
        "submit",
        iniciarSesion
    );
}

function mostrarVistaModulo(vista) {
    const vistas = {
        inicio: document.getElementById("vista-inicio"),
        historial: document.getElementById("vista-historial"),
        configuracion: document.getElementById("vista-configuracion"),
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

    document.getElementById("boton-Configuracion")?.classList.toggle(
        "current-section",
        vista === "configuracion"
    );
    const hash = vista === "inicio" ? "#inicio" : `#${vista}`;
    window.history.replaceState(null, "", hash);
    window.scrollTo({ top: 0, behavior: "smooth" });
}

function abrirConfiguracion() {
    mostrarVistaModulo("configuracion");
}


async function cerrarSesion() {
    try { await solicitarJson("/login/logout", { method: "POST" }); }
    finally { window.location.assign("/"); }
}

document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("loginPage")) {
        iniciarPaginaLogin();
        return;
    }
    if (document.getElementById("vista-configuracion")) iniciarPaginaConfiguracion();
    renderizarPaginaHistorial();
    document.getElementById("nav-inicio")?.addEventListener("click", () => mostrarVistaModulo("inicio"));
    document.getElementById("nav-historial")?.addEventListener("click", () => {
        mostrarVistaModulo("historial");
        actualizarHistorialDesdeServidor();
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
        limpiarVistaPreviaTransformacion();
        actualizarMermaTransformacion();
        renderizarInsumosTransformacion();
        window.clearTimeout(temporizadorVistaPreviaTransformacion);
        if (detalleTransformacionSeleccionada) {
            temporizadorVistaPreviaTransformacion = window.setTimeout(
                localizarDocumentosTransformacion,
                350
            );
        }
    });
    document.getElementById("tablajero-transformacion").addEventListener("change", () => {
        if (detalleTransformacionSeleccionada) localizarDocumentosTransformacion();
    });
    const vistaSolicitada = window.location.hash.replace("#", "");
    if (["historial", "configuracion"].includes(vistaSolicitada)) {
        mostrarVistaModulo(vistaSolicitada);
    }
});
