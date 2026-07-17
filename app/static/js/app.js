const API_RELACIONES = "/api/relaciones-documentos";
let catalogos = { movimientos: [], proveedores: [], usuarios_fisicos: [] };
let documentos = { salida: [], entrada: [] };
let partidasEntrada = [];
let datosCargados = false;
let transformacionPreparada = false;
let detalleTransformacionSeleccionada = null;
let insumosTransformacionCalculados = [];
const API_CONFIGURACION = "/api/configuracion";
let formulaActual = [];
let lineaCatalogoActual = "";
let temporizadorCatalogo = null;

function llenarConfigSelect(elemento, registros, placeholder) {
    elemento.replaceChildren(new Option(placeholder, ""));
    registros.forEach((registro) => {
        const opcion = new Option(registro.producto, String(registro.product_id));
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

function limpiarMensajeConfiguracion() {
    const mensaje = document.getElementById("mensaje-configuracion");
    mensaje.textContent = "";
    mensaje.className = "message";
}

async function cargarProductosCatalogo(linea, termino = "") {
    lineaCatalogoActual = linea;
    const panel = document.getElementById("catalogo-productos");
    const lista = document.getElementById("lista-productos-catalogo");
    panel.classList.remove("hidden");
    document.getElementById("catalogo-productos-titulo").textContent = linea;
    document.getElementById("catalogo-productos-total").textContent = "";
    lista.innerHTML = '<p class="catalog-loading">Consultando productos en SSM...</p>';
    document.querySelectorAll(".configuration-line").forEach((boton) => {
        boton.classList.toggle("active", boton.dataset.linea === linea);
    });
    try {
        const productos = await solicitarJson(
            `${API_CONFIGURACION}/productos-base?linea=${encodeURIComponent(linea)}&termino=${encodeURIComponent(termino)}`
        );
        lista.replaceChildren();
        productos.forEach((producto) => {
            const fila = document.createElement("div");
            fila.className = "catalog-product";
            const nombre = document.createElement("strong");
            nombre.textContent = producto.producto;
            const unidad = document.createElement("span");
            unidad.textContent = producto.unidad || "SIN UNIDAD";
            fila.append(nombre, unidad);
            lista.appendChild(fila);
        });
        if (!productos.length) lista.innerHTML = '<p class="catalog-loading">No se encontraron productos.</p>';
        document.getElementById("catalogo-productos-total").textContent =
            `${productos.length} producto${productos.length === 1 ? "" : "s"}`;
    } catch (error) {
        lista.innerHTML = `<p class="catalog-loading catalog-error">${error.message}</p>`;
    }
}

function cerrarCatalogoProductos() {
    document.getElementById("catalogo-productos").classList.add("hidden");
    document.getElementById("buscar-producto-catalogo").value = "";
    document.querySelectorAll(".configuration-line").forEach((boton) => boton.classList.remove("active"));
    lineaCatalogoActual = "";
}

async function cargarResultantesConfiguracion() {
    const linea = document.getElementById("config-linea").value;
    const resultante = document.getElementById("config-resultante");
    const base = document.getElementById("config-base");
    formulaActual = [];
    llenarConfigSelect(base, [], "Selecciona el producto resultante");
    document.getElementById("config-formula").classList.add("hidden");
    if (!linea) {
        llenarConfigSelect(resultante, [], "Selecciona la línea primero");
        return;
    }
    try {
        const productos = await solicitarJson(`${API_CONFIGURACION}/productos-resultantes?linea=${encodeURIComponent(linea)}`);
        llenarConfigSelect(resultante, productos, "Selecciona un producto resultante");
        if (!productos.length) mensajeConfiguracion("Esta línea no tiene productos resultantes con fórmula en SSM.");
        else limpiarMensajeConfiguracion();
    } catch (error) { mensajeConfiguracion(error.message); }
}

async function cargarFormulaConfiguracion() {
    const productoId = Number(document.getElementById("config-resultante").value || 0);
    const linea = document.getElementById("config-linea").value.toUpperCase();
    const base = document.getElementById("config-base");
    formulaActual = [];
    if (!productoId) {
        llenarConfigSelect(base, [], "Selecciona el producto resultante");
        document.getElementById("config-formula").classList.add("hidden");
        return;
    }
    try {
        formulaActual = await solicitarJson(`${API_CONFIGURACION}/formula/${productoId}`);
        const candidatosBase = formulaActual.filter((componente) =>
            String(componente.linea || "").trim().toUpperCase() === linea
        );
        llenarConfigSelect(base, candidatosBase, "Selecciona el producto base");
        const cuerpo = document.getElementById("config-componentes");
        cuerpo.replaceChildren();
        formulaActual.forEach((componente) => {
            const fila = document.createElement("tr");
            [componente.producto, Number(componente.cantidad).toFixed(3), componente.unidad].forEach((valor) => {
                const celda = document.createElement("td");
                celda.textContent = valor;
                fila.appendChild(celda);
            });
            cuerpo.appendChild(fila);
        });
        document.getElementById("config-formula").classList.toggle("hidden", !formulaActual.length);
        if (!candidatosBase.length) mensajeConfiguracion("La fórmula no contiene un producto base de la línea seleccionada.");
        else limpiarMensajeConfiguracion();
    } catch (error) { mensajeConfiguracion(error.message); }
}

function actualizarResultadoEsperado() {
    const cantidad = Number(document.getElementById("config-cantidad-base").value || 0);
    document.getElementById("config-cantidad-resultante").value = (cantidad * 0.92).toFixed(3);
}

async function guardarNuevaConfiguracion(evento) {
    evento.preventDefault();
    const formulario = evento.currentTarget;
    if (!formulario.reportValidity()) return;
    const boton = document.getElementById("guardar-configuracion");
    boton.disabled = true;
    boton.textContent = "Guardando...";
    try {
        await solicitarJson(`${API_CONFIGURACION}/transformaciones`, {
            method: "POST",
            body: JSON.stringify({
                nombre: document.getElementById("config-nombre").value.trim(),
                linea: document.getElementById("config-linea").value,
                producto_base_id: Number(document.getElementById("config-base").value),
                producto_resultante_id: Number(document.getElementById("config-resultante").value),
                cantidad_base: Number(document.getElementById("config-cantidad-base").value),
                cantidad_resultante: Number(document.getElementById("config-cantidad-resultante").value),
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
    document.querySelectorAll(".configuration-line").forEach((boton) => {
        boton.addEventListener("click", () => {
            document.getElementById("buscar-producto-catalogo").value = "";
            cargarProductosCatalogo(boton.dataset.linea);
        });
    });
    document.getElementById("cerrar-catalogo-productos").addEventListener("click", cerrarCatalogoProductos);
    document.getElementById("buscar-producto-catalogo").addEventListener("input", (evento) => {
        window.clearTimeout(temporizadorCatalogo);
        temporizadorCatalogo = window.setTimeout(() => {
            if (lineaCatalogoActual) cargarProductosCatalogo(lineaCatalogoActual, evento.target.value.trim());
        }, 250);
    });
    document.getElementById("config-linea").addEventListener("change", cargarResultantesConfiguracion);
    document.getElementById("config-resultante").addEventListener("change", cargarFormulaConfiguracion);
    document.getElementById("config-cantidad-base").addEventListener("input", actualizarResultadoEsperado);
    document.getElementById("form-nueva-configuracion").addEventListener("submit", guardarNuevaConfiguracion);
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
            partida.ProductName || "—",
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
        5: ["Transformación", "Selecciona la línea, los productos, el tablajero y el peso de la transformación."],
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
    document.getElementById("resumen-salida").textContent = "Se rellenará al preparar la relación.";
    document.getElementById("resumen-entrada").textContent = "Se rellenará al preparar la relación.";
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
    document.getElementById("resumen-sencillo-transformacion").classList.add("hidden");
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
    document.getElementById("resumen-sencillo-transformacion").classList.add("hidden");
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
        document.getElementById("nombre-base-sencillo").textContent = detalle.producto_base;
        document.getElementById("nombre-resultante-sencillo").textContent = detalle.resultantes[0].producto_resultante;
        document.getElementById("resumen-sencillo-transformacion").classList.remove("hidden");
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
    const resultante = base * 0.92;
    document.getElementById("cantidad-resultante-transformacion").value = resultante.toFixed(3);
    const merma = base * 0.08;
    const porcentaje = base > 0 ? 8 : 0;
    const nivelNormal = porcentaje <= 8;
    const resumen = document.getElementById("resumen-merma-transformacion");
    resumen.textContent = base > 0
        ? `De ${base.toFixed(3)} kg se obtendrán aproximadamente ${resultante.toFixed(3)} kg.`
        : "Escribe los kilos que vas a utilizar.";
    const pesoSencillo = document.getElementById("peso-resultante-sencillo");
    if (pesoSencillo) pesoSencillo.textContent = `${resultante.toFixed(3)} kg`;
    resumen.classList.toggle("merma-normal", nivelNormal);
    resumen.classList.toggle("merma-alerta", !nivelNormal);
    return { merma, porcentaje, nivelNormal };
}

async function localizarDocumentosTransformacion() {
    const transformacionConfigId = Number(document.getElementById("transformacion-precargada").value || 0);
    const baseId = Number(document.getElementById("base-transformacion").value || 0);
    const resultanteId = Number(document.getElementById("resultante-transformacion").value || 0);
    const cantidadBase = Number(document.getElementById("cantidad-base-transformacion").value || 0);
    const cantidadResultante = Number(document.getElementById("cantidad-resultante-transformacion").value || 0);
    const tablajero = document.getElementById("tablajero-transformacion");
    if (!transformacionConfigId || !baseId || !resultanteId || cantidadBase <= 0 || cantidadResultante <= 0 || !tablajero.value) {
        mostrarMensaje("Selecciona la línea, la transformación precargada, el peso y el tablajero responsable.");
        return;
    }
    const boton = document.getElementById("localizar-documentos");
    boton.disabled = true;
    try {
        const folios = await solicitarJson(`${API_RELACIONES}/transformacion/folios-siguientes`);
        const nombreBase = document.getElementById("base-transformacion").selectedOptions[0]?.textContent || "Producto base";
        const nombreResultante = document.getElementById("resultante-transformacion").selectedOptions[0]?.textContent || "Producto resultante";
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
            tablajero.selectedOptions[0]?.textContent || "—";
        const evaluacionMerma = actualizarMermaTransformacion();
        document.getElementById("resumen-nivel-merma").textContent = evaluacionMerma.nivelNormal
            ? `NORMAL · ${evaluacionMerma.porcentaje.toFixed(2)}%`
            : `FUERA DE NIVEL · ${evaluacionMerma.porcentaje.toFixed(2)}%`;
        document.getElementById("resumen-registro-transformacion").classList.remove("hidden");
        document.getElementById("boton-guardar").textContent = "Registrar transformación";
        transformacionPreparada = true;
        mostrarMensaje("La relación está preparada. SSM generará y relacionará ambos documentos al registrar.", "success");
        document.getElementById("panel-documentos").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
        limpiarVistaPreviaTransformacion();
        mostrarMensaje(error.message);
    } finally { boton.disabled = false; }
}

async function cargarDatos() {
    const boton = document.getElementById("boton-actualizar");
    boton.disabled = true;
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
        const movimientoInicial = document.getElementById("tipo-movimiento-inicial");
        movimientoInicial.innerHTML = '<option value="">Selecciona el movimiento</option>';
        catalogos.movimientos.forEach((registro) => {
            const disponible = Number(registro.EntradaID) === 5
                && Number(registro.SalidaID) === 2;
            if (!disponible) return;
            const opcion = document.createElement("option");
            opcion.value = registro.ItemValue;
            opcion.textContent = registro.ItemValue;
            movimientoInicial.appendChild(opcion);
        });
        limpiarMensaje();
    } catch (error) {
        mostrarMensaje(error.message);
    } finally {
        boton.disabled = false;
    }
}

async function solicitarTipoMovimiento() {
    const boton = document.getElementById("boton-iniciar-captura");
    boton.disabled = true;
    boton.textContent = "Preparando...";
    if (!datosCargados) await cargarDatos();
    boton.disabled = false;
    boton.textContent = "Iniciar captura";
    if (!datosCargados) return;
    document.getElementById("tipo-movimiento-inicial").value = "";
    document.getElementById("modal-tipo-movimiento").classList.remove("hidden");
    document.body.classList.add("modal-open");
    document.getElementById("tipo-movimiento-inicial").focus();
}

function cerrarSelectorMovimiento() {
    document.getElementById("modal-tipo-movimiento").classList.add("hidden");
    document.body.classList.remove("modal-open");
}

async function mostrarCaptura() {
    const movimientoInicial = document.getElementById("tipo-movimiento-inicial");
    if (!movimientoInicial.value) {
        movimientoInicial.setCustomValidity("Selecciona un tipo de movimiento.");
        movimientoInicial.reportValidity();
        return;
    }
    movimientoInicial.setCustomValidity("");
    document.getElementById("tipo-movimiento").value = movimientoInicial.value;
    actualizarCamposAnalisis();
    cerrarSelectorMovimiento();
    document.getElementById("panel-inicio").classList.add("hidden");
    const formulario = document.getElementById("form-relacion");
    formulario.classList.remove("hidden");
    try { await prepararMovimientoSeleccionado(); }
    catch (error) { mostrarMensaje(error.message); }
    formulario.scrollIntoView({ behavior: "smooth", block: "start" });
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
    if (registrandoTransformacion && !window.confirm(
        "¿Está seguro de registrar la salida de esta transformación? Esta acción generará y relacionará los documentos en SSM."
    )) {
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

async function iniciarSesion() {
    const boton = document.getElementById("loginButton");
    const error = document.getElementById("loginError");
    boton.disabled = true;
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
    }
}

function abrirConfiguracion() {
    window.location.assign("/configuracion");
}


async function cerrarSesion() {
    try { await solicitarJson("/login/logout", { method: "POST" }); }
    finally { window.location.assign("/"); }
}

document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("loginPage")) return;
    if (document.getElementById("form-nueva-configuracion")) {
        iniciarPaginaConfiguracion();
        return;
    }
    document.getElementById("fecha-movimiento").valueAsDate = new Date();
    document.getElementById("documento-salida").addEventListener("change", () => cargarPartidas("salida"));
    document.getElementById("documento-entrada").addEventListener("change", () => cargarPartidas("entrada"));
    document.getElementById("tipo-movimiento").addEventListener("change", actualizarCamposAnalisis);
    document.getElementById("boton-iniciar-captura").addEventListener("click", solicitarTipoMovimiento);
    document.getElementById("cancelar-tipo-movimiento").addEventListener("click", cerrarSelectorMovimiento);
    document.getElementById("continuar-tipo-movimiento").addEventListener("click", mostrarCaptura);
    document.getElementById("boton-volver").addEventListener("click", volverAlInicio);
    document.getElementById("boton-actualizar").addEventListener("click", cargarDatos);
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
    });
    document.getElementById("localizar-documentos").addEventListener("click", localizarDocumentosTransformacion);
    document.getElementById("tablajero-transformacion").addEventListener("change", () => {
        limpiarVistaPreviaTransformacion();
    });
});
