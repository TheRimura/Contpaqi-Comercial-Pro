"use strict";

const API_CARNICO = "/api/carnico";

let productosCarnicosDraft = [];
let configuracionCarnicosSucia = false;
let productosDisponiblesConfig = [];
let paginaProductosDisponibles = 1;
let modoEliminarConfig = false;
let historialRegistros = [];
let historialFiltro = "todos";
let paginaHistorial = 1;
const PRODUCTOS_POR_PAGINA_CONFIG = 6;
const HISTORIAL_POR_PAGINA = 6;
const MERMA_OPTIMA = 8;

async function solicitarJson(url, opciones = {}) {
    const respuesta = await fetch(url, {
        credentials: "same-origin",
        headers: {
            "Content-Type": "application/json",
            ...(opciones.headers || {}),
        },
        ...opciones,
    });

    let datos = {};
    try {
        datos = await respuesta.json(); 
    } catch (_) {
        datos = {};
    }

    if (respuesta.status === 401 && !document.getElementById("loginPage")) {
        window.location.assign("/");
        throw new Error("La sesion termino.");
    }

    if (!respuesta.ok) {
        let detalle = datos.detail || "No fue posible completar la operacion.";
        if (Array.isArray(detalle)) {
            detalle = detalle.map((item) => item.msg).join(" ");
        }
        throw new Error(detalle);
    }

    return datos;
}

function mostrarMensaje(elemento, texto, tipo = "error") {
    if (!elemento) {
        return;
    }
    elemento.textContent = texto;
    elemento.className = `mensaje visible ${tipo}`;
}

function limpiarMensaje(elemento) {
    if (!elemento) {
        return;
    }
    elemento.textContent = "";
    elemento.className = "mensaje";
}

function hayModalVisible() {
    return Array.from(document.querySelectorAll(".modal-overlay"))
        .some((modal) => !modal.classList.contains("hidden"));
}

function actualizarBloqueoModal() {
    document.body.classList.toggle("modal-open", hayModalVisible());
}

function pedirConfirmacionModulo(opciones) {
    return new Promise((resolve) => {
        const modal = document.getElementById("modal-dialogo-modulo");
        const form = document.getElementById("form-dialogo-modulo");
        const etiqueta = document.getElementById("dialogo-modulo-etiqueta");
        const titulo = document.getElementById("dialogo-modulo-titulo");
        const texto = document.getElementById("dialogo-modulo-texto");
        const campo = document.getElementById("dialogo-modulo-campo");
        const label = document.getElementById("dialogo-modulo-label");
        const input = document.getElementById("dialogo-modulo-input");
        const error = document.getElementById("dialogo-modulo-error");
        const aceptar = document.getElementById("dialogo-modulo-aceptar");
        const cancelar = document.getElementById("dialogo-modulo-cancelar");
        const requiereTexto = Boolean(opciones.requiereTexto);

        etiqueta.textContent = opciones.etiqueta || "Confirmacion";
        titulo.textContent = opciones.titulo || "Confirmar accion";
        texto.textContent = opciones.texto || "";
        label.textContent = opciones.label || "Usuario";
        input.value = "";
        input.placeholder = opciones.placeholder || "";
        error.textContent = "";
        aceptar.textContent = opciones.aceptarTexto || "Aceptar";
        cancelar.textContent = opciones.cancelarTexto || "Cancelar";
        campo.classList.toggle("hidden", !requiereTexto);

        function cerrar(resultado) {
            form.onsubmit = null;
            cancelar.onclick = null;
            modal.classList.add("hidden");
            actualizarBloqueoModal();
            resolve(resultado);
        }

        form.onsubmit = (evento) => {
            evento.preventDefault();
            const valor = input.value.trim();

            if (requiereTexto && !valor) {
                error.textContent = "Escribe el dato solicitado para continuar.";
                input.focus();
                return;
            }

            cerrar({
                confirmado: true,
                valor,
            });
        };

        cancelar.onclick = () => cerrar({
            confirmado: false,
            valor: "",
        });

        modal.classList.remove("hidden");
        actualizarBloqueoModal();

        setTimeout(() => {
            if (requiereTexto) {
                input.focus();
            } else {
                aceptar.focus();
            }
        }, 0);
    });
}

async function iniciarSesion() {
    const usuario = document.getElementById("usuario");
    const password = document.getElementById("password");
    const mensaje = document.getElementById("loginError");
    const boton = document.getElementById("loginButton");

    mensaje.textContent = "";
    boton.disabled = true;
    boton.textContent = "Validando...";

    try {
        await solicitarJson("/login/", {
            method: "POST",
            body: JSON.stringify({
                usuario: usuario.value.trim(),
                password: password.value,
            }),
        });
        window.location.assign("/dashboard");
    } catch (error) {
        mensaje.textContent = error.message;
        password.focus();
        password.select();
    } finally {
        boton.disabled = false;
        boton.textContent = "Iniciar sesion";
    }
}

window.iniciarSesion = iniciarSesion;

function formatoNumero(valor, decimales = 2) {
    return Number(valor || 0).toLocaleString("es-MX", {
        maximumFractionDigits: decimales,
        minimumFractionDigits: decimales,
    });
}

function numeroDesdeEntrada(valor) {
    const limpio = String(valor || "")
        .replace(/\s+/g, "")
        .replace(/kg/ig, "")
        .replace(/%/g, "")
        .replace(",", ".")
        .replace(/[^\d.]/g, "");
    const numero = Number(limpio);
    return Number.isFinite(numero) ? numero : 0;
}

function formatoDecimalComa(valor, decimales = 3) {
    const numero = Number(valor || 0);
    const texto = numero.toFixed(decimales).replace(/\.?0+$/, "");
    return (texto || "0").replace(".", ",");
}

function formatoKg(valor) {
    return `${formatoDecimalComa(valor, 3)} kg`;
}

function formatoCantidadUnidad(valor, unidad) {
    const unidadNormalizada = String(unidad || "KILO").toUpperCase();
    const abreviatura = unidadNormalizada.includes("LITRO")
        ? "l"
        : unidadNormalizada.includes("PIEZA")
            ? "pza"
            : unidadNormalizada.includes("GRAM")
                ? "g"
                : "kg";
    return `${formatoDecimalComa(valor, abreviatura === "pza" ? 0 : 3)} ${abreviatura}`;
}

function limitarCampoKg(input) {
    if (!input) {
        return;
    }

    let valor = input.value.replace(".", ",").replace(/[^\d,]/g, "");
    const partes = valor.split(",");
    if (partes.length > 2) {
        valor = `${partes.shift()},${partes.join("")}`;
    }

    const numero = numeroDesdeEntrada(valor);
    if (numero > 999) {
        valor = "999";
    }

    input.value = valor;
}

function limitarCampoPorcentaje(input) {
    if (!input) {
        return;
    }

    let valor = input.value.replace(".", ",").replace(/[^\d,]/g, "");
    const partes = valor.split(",");
    if (partes.length > 2) {
        valor = `${partes.shift()},${partes.join("")}`;
    }

    const numero = numeroDesdeEntrada(valor);
    if (numero > 99) {
        valor = "99";
    }

    input.value = valor ? `${valor}%` : "";
}

function calcularMermaKgDesdePorcentaje(cantidadEntrada, porcentajeMerma) {
    if (cantidadEntrada <= 0 || porcentajeMerma <= 0) {
        return 0;
    }
    if (porcentajeMerma >= 100) {
        return 0;
    }
    return cantidadEntrada * porcentajeMerma / (100 - porcentajeMerma);
}

function crearCelda(texto) {
    const celda = document.createElement("td");
    celda.textContent = texto ?? "";
    return celda;
}

function crearTabla(encabezados, filas, mensajeVacio) {
    const contenedor = document.createElement("div");

    if (!filas.length) {
        const vacio = document.createElement("p");
        vacio.className = "estado-vacio";
        vacio.textContent = mensajeVacio;
        contenedor.appendChild(vacio);
        return contenedor;
    }

    const tabla = document.createElement("table");
    const thead = document.createElement("thead");
    const trHead = document.createElement("tr");
    const tbody = document.createElement("tbody");

    tabla.className = "tabla-partidas";
    encabezados.forEach((titulo) => {
        const th = document.createElement("th");
        th.textContent = titulo;
        trHead.appendChild(th);
    });
    thead.appendChild(trHead);

    filas.forEach((filaDatos) => {
        const tr = document.createElement("tr");
        filaDatos.forEach((dato) => tr.appendChild(crearCelda(dato)));
        tbody.appendChild(tr);
    });

    tabla.append(thead, tbody);
    contenedor.appendChild(tabla);
    return contenedor;
}

function cambiarVista(nombre) {
    document.querySelectorAll(".vista").forEach((vista) => {
        vista.classList.toggle("hidden", vista.id !== `vista-${nombre}`);
    });
    document.querySelectorAll(".nav-boton").forEach((boton) => {
        boton.classList.toggle("is-active", boton.dataset.vista === nombre);
    });

    if (nombre === "historial") {
        cargarModuloCarnico();
    }
}

function iniciarNavegacion() {
    document.querySelectorAll(".nav-boton").forEach((boton) => {
        boton.addEventListener("click", () => cambiarVista(boton.dataset.vista));
    });

    document.getElementById("boton-salir")?.addEventListener("click", async () => {
        try {
            await solicitarJson("/login/logout", { method: "POST" });
        } finally {
            window.location.assign("/");
        }
    });
}

function textoProducto(producto) {
    const clave = producto.clave ? `${producto.clave} - ` : "";
    const categoria = producto.opcion_creacion
        ? ` (${producto.opcion_creacion})`
        : "";
    return `${clave}${producto.nombre_producto}${categoria}`;
}

async function buscarProductosCarnicos(termino, limite = 12) {
    const datos = await solicitarJson(
        `${API_CARNICO}/productos-erp?q=${encodeURIComponent(termino)}&limite=${limite}`,
    );
    return datos.productos || [];
}

function configurarAutocompleteProducto(inputId, hiddenId, listaId) {
    const input = document.getElementById(inputId);
    const hidden = document.getElementById(hiddenId);
    const lista = document.getElementById(listaId);

    if (!input || !hidden || !lista) {
        return;
    }

    let temporizador = null;
    let solicitud = 0;

    function ocultar() {
        lista.classList.add("hidden");
        lista.replaceChildren();
    }

    input.addEventListener("input", () => {
        hidden.value = "";
        hidden.dataset.categoria = "";
        hidden.dataset.nombre = "";
        hidden.dataset.proveedor = "";
        const termino = input.value.trim();
        clearTimeout(temporizador);

        if (termino.length < 2) {
            ocultar();
            return;
        }

        temporizador = setTimeout(async () => {
            const solicitudActual = ++solicitud;

            try {
                const productos = await buscarProductosCarnicos(termino);

                if (solicitudActual !== solicitud) {
                    return;
                }

                lista.replaceChildren();
                if (!productos.length) {
                    const vacio = document.createElement("div");
                    vacio.className = "autocomplete-empty";
                    vacio.textContent = "Sin resultados.";
                    lista.appendChild(vacio);
                    lista.classList.remove("hidden");
                    return;
                }

                productos.forEach((producto) => {
                    const boton = document.createElement("button");
                    boton.type = "button";
                    boton.className = "autocomplete-item";
                    boton.innerHTML = `
                        <strong>${textoProducto(producto)}</strong>
                        <span>${producto.categoria || "SIN CATEGORIA"} · ${producto.unidad || "KILO"}</span>
                    `;
                    boton.textContent = "";
                    const nombre = document.createElement("strong");
                    const meta = document.createElement("span");
                    nombre.textContent = textoProducto(producto);
                    meta.textContent = `${producto.categoria || "SIN CATEGORIA"} - ${producto.unidad || "KILO"}`;
                    boton.append(nombre, meta);
                    boton.addEventListener("click", () => {
                        hidden.value = producto.product_id;
                        hidden.dataset.categoria = producto.categoria || "";
                        hidden.dataset.nombre = producto.nombre_producto || "";
                        hidden.dataset.proveedor = producto.proveedor_nombre || "";
                        input.value = textoProducto(producto);
                        if (hiddenId === "producto-entrada-carnico" && producto.categoria) {
                            const categoria = document.getElementById("categoria-base-carnico");
                            if (categoria) {
                                categoria.value = producto.categoria;
                            }
                        }
                        ocultarPanelInsumos();
                        ocultar();
                    });
                    lista.appendChild(boton);
                });
                lista.classList.remove("hidden");
            } catch (error) {
                lista.replaceChildren();
                const mensaje = document.createElement("div");
                mensaje.className = "autocomplete-empty";
                mensaje.textContent = error.message;
                lista.appendChild(mensaje);
                lista.classList.remove("hidden");
            }
        }, 220);
    });

    input.addEventListener("blur", () => {
        setTimeout(ocultar, 160);
    });
}

function calcularPorcentajeMermaEntrada() {
    return numeroDesdeEntrada(
        document.getElementById("cantidad-merma-carnico")?.value,
    );
}

function actualizarEstadoMerma() {
    const estado = document.getElementById("estado-merma-carnico");
    const campo = document.getElementById("cantidad-merma-carnico");
    const porcentaje = calcularPorcentajeMermaEntrada();

    if (!estado) {
        return;
    }

    estado.className = "ayuda-campo";

    if (!String(campo?.value || "").trim()) {
        estado.textContent = "Merma optima: 8%.";
        return;
    }

    if (porcentaje < MERMA_OPTIMA) {
        estado.textContent =
            `Merma ${formatoDecimalComa(porcentaje, 2)}%: debajo del 8%, revisar practica.`;
        estado.classList.add("alerta");
        return;
    }

    estado.textContent =
        `Merma ${formatoDecimalComa(porcentaje, 2)}%: base correcta.`;
    estado.classList.add("ok");
}

function ocultarPanelInsumos() {
    document.getElementById("panel-insumos-transformacion")?.classList.add("hidden");
    document.getElementById("tabla-insumos-transformacion")?.replaceChildren();
}

function actualizarResumenHistorial(resumen) {
    document.getElementById("historial-total-mes").textContent =
        formatoNumero(resumen?.total_movimientos || resumen?.total_transformaciones || 0, 0);
    document.getElementById("historial-rendimiento").textContent =
        `${formatoNumero(resumen?.rendimiento || 0, 2)}%`;
    document.getElementById("historial-merma").textContent =
        `${formatoNumero(resumen?.kilos_merma || 0, 3)} kg`;
}

function registrosHistorialFiltrados() {
    if (historialFiltro === "todos") {
        return historialRegistros;
    }

    return historialRegistros.filter((registro) => {
        const tipo = String(registro.tipo_movimiento || "").toLowerCase();
        const categoria = String(registro.categoria_base || "").toUpperCase();

        if (historialFiltro === "entrada" || historialFiltro === "salida") {
            return tipo === historialFiltro;
        }

        return categoria === historialFiltro;
    });
}

function actualizarPaginacionHistorial(totalRegistros) {
    const totalPaginas = Math.max(
        1,
        Math.ceil(totalRegistros / HISTORIAL_POR_PAGINA),
    );
    const anterior = document.getElementById("historial-pagina-anterior");
    const siguiente = document.getElementById("historial-pagina-siguiente");
    const info = document.getElementById("historial-pagina-info");

    paginaHistorial = Math.min(paginaHistorial, totalPaginas);

    if (info) {
        info.textContent = `Pagina ${paginaHistorial} de ${totalPaginas} (${totalRegistros} registros)`;
    }
    if (anterior) {
        anterior.disabled = paginaHistorial <= 1;
    }
    if (siguiente) {
        siguiente.disabled = paginaHistorial >= totalPaginas;
    }
}

function renderizarHistorialCarnico(registros = null) {
    if (Array.isArray(registros)) {
        historialRegistros = registros;
    }

    const contenedor = document.getElementById("tabla-historial-carnico");

    if (!contenedor) {
        return;
    }

    contenedor.replaceChildren();

    const filtrados = registrosHistorialFiltrados();
    actualizarPaginacionHistorial(filtrados.length);

    if (!filtrados.length) {
        const vacio = document.createElement("p");
        vacio.className = "estado-vacio";
        vacio.textContent = "Aun no hay movimientos registrados.";
        contenedor.appendChild(vacio);
        return;
    }

    const lista = document.createElement("div");
    lista.className = "historial-lista";

    const inicio = (paginaHistorial - 1) * HISTORIAL_POR_PAGINA;
    const registrosPagina = filtrados.slice(inicio, inicio + HISTORIAL_POR_PAGINA);

    registrosPagina.forEach((registro) => {
        const tipo = String(registro.tipo_movimiento || "Entrada").toLowerCase();
        const fecha = String(registro.fecha || "").replace("T", " ").slice(0, 19);
        const articulo = document.createElement("article");
        const encabezado = document.createElement("div");
        const badge = document.createElement("span");
        const titulo = document.createElement("strong");
        const meta = document.createElement("div");

        articulo.className = "historial-item";
        encabezado.className = "historial-item-header";
        badge.className = `historial-badge ${tipo}`;
        badge.textContent = tipo === "salida" ? "Salida" : "Entrada";
        titulo.className = "historial-title";
        titulo.textContent = tipo === "salida"
            ? registro.producto_salida_nombre || "Salida sin producto"
            : `${registro.categoria_base || "Base"} -> ${registro.producto_entrada_nombre || "Entrada"}`;
        meta.className = "historial-meta";

        const chips = [
            `Folio ${registro.id_registro}`,
            fecha || "Sin fecha",
        ];

        if (tipo !== "salida") {
            chips.push(`Base ${registro.categoria_base || "-"}`);
            chips.push(`Entrada ${formatoKg(registro.cantidad_entrada)}`);
            chips.push(`Merma ${formatoKg(registro.cantidad_merma)}`);
            chips.push(`Rend. ${formatoDecimalComa(registro.rendimiento, 2)}%`);
        } else {
            chips.push(`Salida ${formatoKg(registro.cantidad_salida)}`);
            chips.push(`Base ${registro.categoria_base || "-"}`);
        }

        if (registro.proveedor_nombre) {
            chips.push(`Proveedor ${registro.proveedor_nombre}`);
        }
        if (registro.usuario_confirmacion_nombre) {
            chips.push(`Usuario ${registro.usuario_confirmacion_nombre}`);
        }
        if (registro.estado) {
            chips.push(registro.estado);
        }
        if (registro.observaciones) {
            chips.push(`Obs. ${registro.observaciones}`);
        }

        chips.forEach((texto) => {
            const chip = document.createElement("span");
            chip.className = "historial-chip";
            if (texto.toLowerCase() === "registrado") {
                chip.classList.add("estado-registrado");
            }
            chip.textContent = texto;
            meta.appendChild(chip);
        });

        encabezado.append(badge, titulo);
        articulo.append(encabezado, meta);
        lista.appendChild(articulo);
    });

    contenedor.appendChild(lista);
}

function alternarMenuFiltros() {
    document.getElementById("historial-menu-filtros")?.classList.toggle("hidden");
}

function seleccionarFiltroHistorial(boton) {
    historialFiltro = boton.dataset.filtro || "todos";
    paginaHistorial = 1;
    document.querySelectorAll(".boton-filtro").forEach((item) => {
        item.classList.toggle("is-active", item === boton);
    });
    document.getElementById("historial-filtro-activo").textContent =
        boton.textContent.trim();
    document.getElementById("historial-menu-filtros")?.classList.add("hidden");
    renderizarHistorialCarnico();
}

async function verificarPermisosConfiguracion() {
    const boton = document.getElementById("boton-configuracion-carnicos");

    if (!boton) {
        return;
    }

    try {
        const datos = await solicitarJson(`${API_CARNICO}/permisos`);
        boton.classList.toggle("hidden", !datos.puede_configurar);
        boton.disabled = !datos.puede_configurar;
    } catch (_) {
        boton.classList.add("hidden");
        boton.disabled = true;
    }
}

async function cargarModuloCarnico() {
    const mensaje = document.getElementById("mensaje-carnico");

    try {
        const datos = await solicitarJson(`${API_CARNICO}/resumen`);
        actualizarResumenHistorial(datos.resumen || {});
        paginaHistorial = 1;
        renderizarHistorialCarnico(datos.registros || []);
        limpiarMensaje(mensaje);
    } catch (error) {
        mostrarMensaje(mensaje, error.message, "error");
    }
}

async function registrarTransformacionCarnica(evento) {
    evento.preventDefault();

    const mensaje = document.getElementById("mensaje-carnico");
    const boton = document.getElementById("boton-registrar-carnico");
    const entradaId = Number(document.getElementById("producto-entrada-carnico").value);
    const cantidadEntrada = numeroDesdeEntrada(
        document.getElementById("cantidad-entrada-carnico").value,
    );
    const porcentajeMerma = calcularPorcentajeMermaEntrada();
    const cantidadMerma = calcularMermaKgDesdePorcentaje(
        cantidadEntrada,
        porcentajeMerma,
    );

    if (!entradaId) {
        mostrarMensaje(
            mensaje,
            "Selecciona el producto de entrada desde la lista de sugerencias.",
            "error",
        );
        return;
    }

    if (cantidadEntrada <= 0 || cantidadEntrada > 999) {
        mostrarMensaje(
            mensaje,
            "La cantidad de entrada debe ser mayor a 0 y maximo 999 kg.",
            "error",
        );
        return;
    }

    if (porcentajeMerma < 0 || porcentajeMerma >= 100) {
        mostrarMensaje(
            mensaje,
            "La merma debe ser un porcentaje menor a 100.",
            "error",
        );
        return;
    }

    const decision = await pedirConfirmacionModulo({
        etiqueta: "Transformacion",
        titulo: "Registrar transformacion",
        texto: porcentajeMerma < MERMA_OPTIMA
            ? "La merma esta debajo del 8%. Confirma el usuario que realiza el registro."
            : "Confirma el usuario que realiza el registro. Al aceptar se guardara la transformacion.",
        requiereTexto: true,
        label: "Usuario que registra",
        placeholder: "Nombre de usuario",
        aceptarTexto: "Registrar",
        cancelarTexto: "Cancelar",
    });

    if (!decision.confirmado) {
        return;
    }

    const usuario = decision.valor;

    const payload = {
        producto_entrada_id: entradaId,
        categoria_base: document.getElementById("categoria-base-carnico").value,
        cantidad_entrada: cantidadEntrada,
        cantidad_merma: cantidadMerma,
        observaciones: document.getElementById("observaciones-carnico").value.trim() || null,
        usuario_confirmacion_nombre: usuario.trim(),
    };

    boton.disabled = true;
    boton.textContent = "Registrando...";
    limpiarMensaje(mensaje);

    try {
        const resultado = await solicitarJson(`${API_CARNICO}/transformaciones`, {
            method: "POST",
            body: JSON.stringify(payload),
        });
        mostrarMensaje(mensaje, resultado.mensaje, "exito");
        document.getElementById("form-transformacion-carnica").reset();
        document.getElementById("producto-entrada-carnico").value = "";
        ocultarPanelInsumos();
        actualizarEstadoMerma();
        actualizarResumenHistorial(resultado.resumen || {});
        paginaHistorial = 1;
        renderizarHistorialCarnico(resultado.registros || []);
    } catch (error) {
        mostrarMensaje(mensaje, error.message, "error");
    } finally {
        boton.disabled = false;
        boton.textContent = "Registrar transformacion";
    }
}

async function registrarSalidaCarnica(evento) {
    evento.preventDefault();

    const mensaje = document.getElementById("mensaje-salida-carnico");
    const boton = document.getElementById("boton-registrar-salida");
    const productoId = Number(document.getElementById("producto-base-carnico").value);
    const cantidadSalida = numeroDesdeEntrada(
        document.getElementById("cantidad-salida-base").value,
    );

    if (!productoId) {
        mostrarMensaje(
            mensaje,
            "Selecciona el producto base desde la lista de sugerencias.",
            "error",
        );
        return;
    }

    if (cantidadSalida <= 0 || cantidadSalida > 999) {
        mostrarMensaje(
            mensaje,
            "Los kilos de salida deben ser mayores a 0 y maximo 999 kg.",
            "error",
        );
        return;
    }

    const decision = await pedirConfirmacionModulo({
        etiqueta: "Salida",
        titulo: "Registrar salida de almacen",
        texto: "Se guardara la salida del producto base en el historial del modulo.",
        aceptarTexto: "Registrar",
        cancelarTexto: "Cancelar",
    });

    if (!decision.confirmado) {
        return;
    }

    const payload = {
        producto_salida_id: productoId,
        cantidad_salida: cantidadSalida,
        proveedor_nombre: document.getElementById("proveedor-salida-carnico").value.trim(),
        usuario_confirmacion_nombre: document.getElementById("usuario-salida-carnico").value.trim(),
        observaciones: document.getElementById("observaciones-salida-carnico").value.trim() || null,
    };

    boton.disabled = true;
    boton.textContent = "Registrando...";
    limpiarMensaje(mensaje);

    try {
        const resultado = await solicitarJson(`${API_CARNICO}/salidas`, {
            method: "POST",
            body: JSON.stringify(payload),
        });
        mostrarMensaje(mensaje, resultado.mensaje, "exito");
        document.getElementById("form-salida-carnica").reset();
        document.getElementById("producto-base-carnico").value = "";
        actualizarResumenHistorial(resultado.resumen || {});
        paginaHistorial = 1;
        renderizarHistorialCarnico(resultado.registros || []);
    } catch (error) {
        mostrarMensaje(mensaje, error.message, "error");
    } finally {
        boton.disabled = false;
        boton.textContent = "Registrar salida";
    }
}

function renderizarInsumosTransformacion(insumos) {
    const contenedor = document.getElementById("tabla-insumos-transformacion");

    if (!contenedor) {
        return;
    }

    if (!insumos.length) {
        const vacio = document.createElement("p");
        vacio.className = "estado-vacio";
        vacio.textContent = "No hay receta previa para este producto.";
        contenedor.replaceChildren(vacio);
        return;
    }

    const filas = insumos.map((insumo) => [
        `${insumo.nombre_producto || "-"}${insumo.clave ? ` | ${insumo.clave}` : ""}`,
        insumo.tipo || "Insumo",
        insumo.unidad || "KILO",
        formatoCantidadUnidad(insumo.cantidad, insumo.unidad),
    ]);

    contenedor.replaceChildren(
        crearTabla(
            ["Producto", "Tipo", "Unidad", "Peso / cantidad"],
            filas,
            "No hay insumos configurados.",
        ),
    );
}

async function cargarInsumosTransformacion() {
    const mensaje = document.getElementById("mensaje-carnico");
    const panel = document.getElementById("panel-insumos-transformacion");
    const productoId = Number(document.getElementById("producto-entrada-carnico").value);
    const cantidad = numeroDesdeEntrada(
        document.getElementById("cantidad-entrada-carnico").value,
    );

    if (!productoId || cantidad <= 0) {
        mostrarMensaje(
            mensaje,
            "Selecciona producto de entrada y cantidad para calcular insumos.",
            "error",
        );
        return;
    }

    try {
        const datos = await solicitarJson(
            `${API_CARNICO}/receta?producto_id=${productoId}&cantidad=${cantidad}`,
        );
        renderizarInsumosTransformacion(datos.insumos || []);
        panel.classList.remove("hidden");
        limpiarMensaje(mensaje);
    } catch (error) {
        mostrarMensaje(mensaje, error.message, "error");
    }
}

function renderizarConfiguracionCarnicos() {
    renderizarProductosDisponiblesConfig();
}

function claveProductoConfig(producto) {
    return producto.product_id
        ? `id:${producto.product_id}`
        : `custom:${String(producto.nombre_producto || "").trim().toUpperCase()}:${String(producto.proveedor_nombre || "").trim().toUpperCase()}`;
}

function obtenerProductosTablaConfiguracion() {
    const mapa = new Map();
    const ocultos = new Set();

    productosCarnicosDraft.forEach((producto) => {
        const clave = claveProductoConfig(producto);
        if (producto.activo) {
            mapa.set(clave, producto);
        } else {
            ocultos.add(clave);
        }
    });

    productosDisponiblesConfig.forEach((producto) => {
        const clave = claveProductoConfig(producto);
        if (!ocultos.has(clave) && !mapa.has(clave)) {
            mapa.set(clave, producto);
        }
    });

    return Array.from(mapa.values());
}

function ocultarProductoConfiguracion(producto) {
    const clave = claveProductoConfig(producto);
    const indice = productosCarnicosDraft.findIndex((registro) => (
        claveProductoConfig(registro) === clave
    ));

    if (indice >= 0) {
        productosCarnicosDraft[indice].activo = false;
    } else {
        productosCarnicosDraft.push({
            id_configuracion: null,
            product_id: producto.product_id || null,
            clave: producto.clave || "",
            proveedor_id: producto.proveedor_id || null,
            proveedor_nombre: producto.proveedor_nombre || "",
            nombre_producto: producto.nombre_producto || "",
            categoria: producto.categoria || "CERDO",
            categoria_resultante: producto.opcion_creacion || "",
            unidad: producto.unidad || "KILO",
            porcentaje_merma: Number(producto.porcentaje_merma || 0),
            activo: false,
        });
    }

    configuracionCarnicosSucia = true;
    renderizarConfiguracionCarnicos();
}

function mostrarFormularioConfigProducto(producto = null) {
    const formulario = document.getElementById("form-producto-carnico");
    const id = document.getElementById("config-producto-id");
    const clave = document.getElementById("config-producto-clave");
    const nombre = document.getElementById("config-producto-nombre");
    const proveedor = document.getElementById("config-producto-proveedor");
    const categoria = document.getElementById("config-producto-categoria");
    const resultante = document.getElementById("config-producto-resultante");
    const unidad = document.getElementById("config-producto-unidad");
    const merma = document.getElementById("config-producto-merma");

    formulario.classList.remove("hidden");
    formulario.reset();
    id.value = producto?.product_id || "";
    clave.value = producto?.clave || "";
    nombre.value = producto?.nombre_producto || "";
    proveedor.value = producto?.proveedor_nombre || "";
    categoria.value = producto?.categoria || "CERDO";
    resultante.value = producto?.opcion_creacion || producto?.categoria_resultante || "";
    unidad.value = producto?.unidad || "KILO";
    merma.value = producto?.porcentaje_merma ?? "";
    nombre.focus();
}

function renderizarProductosDisponiblesConfig() {
    const contenedor = document.getElementById("tabla-productos-disponibles");
    const info = document.getElementById("config-pagina-info");
    const anterior = document.getElementById("config-pagina-anterior");
    const siguiente = document.getElementById("config-pagina-siguiente");
    const tabla = document.createElement("table");
    const thead = document.createElement("thead");
    const tbody = document.createElement("tbody");
    const trHead = document.createElement("tr");
    const productosTabla = obtenerProductosTablaConfiguracion();
    const totalPaginas = Math.max(
        1,
        Math.ceil(productosTabla.length / PRODUCTOS_POR_PAGINA_CONFIG),
    );

    paginaProductosDisponibles = Math.min(paginaProductosDisponibles, totalPaginas);
    tabla.className = "tabla-partidas tabla-seleccionable";
    const encabezados = ["Clave", "Nombre producto", "Proveedor", "Unidad"];
    if (modoEliminarConfig) {
        encabezados.push("Accion");
    }

    encabezados.forEach((titulo) => {
        const th = document.createElement("th");
        th.textContent = titulo;
        trHead.appendChild(th);
    });
    thead.appendChild(trHead);

    const inicio = (paginaProductosDisponibles - 1) * PRODUCTOS_POR_PAGINA_CONFIG;
    const productosPagina = productosTabla.slice(
        inicio,
        inicio + PRODUCTOS_POR_PAGINA_CONFIG,
    );

    productosPagina.forEach((producto) => {
        const tr = document.createElement("tr");
        tr.tabIndex = 0;
        tr.append(
            crearCelda(producto.clave || "-"),
            crearCelda(producto.nombre_producto || "-"),
            crearCelda(producto.proveedor_nombre || "-"),
            crearCelda(producto.unidad || "KILO"),
        );

        if (modoEliminarConfig) {
            const tdAccion = document.createElement("td");
            const accion = document.createElement("button");
            accion.type = "button";
            accion.className = "boton-tabla boton-icono";
            accion.textContent = "🗑";
            accion.title = "Ocultar producto";
            accion.setAttribute("aria-label", "Ocultar producto");
            accion.addEventListener("click", (evento) => {
                evento.stopPropagation();
                ocultarProductoConfiguracion(producto);
            });
            tdAccion.appendChild(accion);
            tr.appendChild(tdAccion);
        }

        tr.addEventListener("click", () => mostrarFormularioConfigProducto(producto));
        tr.addEventListener("keydown", (evento) => {
            if (evento.key === "Enter" || evento.key === " ") {
                evento.preventDefault();
                mostrarFormularioConfigProducto(producto);
            }
        });
        tbody.appendChild(tr);
    });

    tabla.append(thead, tbody);
    contenedor.replaceChildren();

    if (!productosTabla.length) {
        const vacio = document.createElement("p");
        vacio.className = "estado-vacio";
        vacio.textContent = "No se encontraron productos disponibles.";
        contenedor.appendChild(vacio);
    } else {
        contenedor.appendChild(tabla);
    }

    info.textContent =
        `Pagina ${paginaProductosDisponibles} de ${totalPaginas} (${productosTabla.length} productos)`;
    anterior.disabled = paginaProductosDisponibles <= 1;
    siguiente.disabled = paginaProductosDisponibles >= totalPaginas;
}

async function cargarProductosDisponiblesConfig(termino = "") {
    const mensaje = document.getElementById("mensaje-configuracion-carnicos");

    try {
        productosDisponiblesConfig = await buscarProductosCarnicos(termino, 50);
        paginaProductosDisponibles = 1;
        renderizarProductosDisponiblesConfig();
        limpiarMensaje(mensaje);
    } catch (error) {
        mostrarMensaje(mensaje, error.message, "error");
    }
}

async function abrirConfiguracionCarnicos() {
    const modal = document.getElementById("modal-configuracion-carnicos");
    const mensaje = document.getElementById("mensaje-configuracion-carnicos");

    modal.classList.remove("hidden");
    actualizarBloqueoModal();
    limpiarMensaje(mensaje);

    try {
        const datos = await solicitarJson(`${API_CARNICO}/productos?incluir_inactivos=true`);
        productosCarnicosDraft = (datos.productos || []).map((producto) => ({ ...producto }));
        configuracionCarnicosSucia = false;
        modoEliminarConfig = false;
        renderizarConfiguracionCarnicos();
        await cargarProductosDisponiblesConfig("");
    } catch (error) {
        mostrarMensaje(mensaje, error.message, "error");
    }
}

async function cerrarConfiguracionCarnicos() {
    if (
        configuracionCarnicosSucia
    ) {
        const decision = await pedirConfirmacionModulo({
            etiqueta: "Configuracion",
            titulo: "Cerrar sin guardar",
            texto: "Hay cambios de configuracion sin guardar. Si cierras ahora se perderan.",
            aceptarTexto: "Cerrar sin guardar",
            cancelarTexto: "Volver",
        });

        if (!decision.confirmado) {
            return;
        }
    }
    document.getElementById("modal-configuracion-carnicos").classList.add("hidden");
    actualizarBloqueoModal();
}

function agregarProductoCarnico(evento) {
    evento.preventDefault();

    const productoId = document.getElementById("config-producto-id");
    const clave = document.getElementById("config-producto-clave");
    const nombre = document.getElementById("config-producto-nombre");
    const proveedor = document.getElementById("config-producto-proveedor");
    const categoria = document.getElementById("config-producto-categoria");
    const resultante = document.getElementById("config-producto-resultante");
    const unidad = document.getElementById("config-producto-unidad");
    const merma = document.getElementById("config-producto-merma");
    const nombreValor = nombre.value.trim();
    const proveedorValor = proveedor.value.trim();

    if (!nombreValor || !proveedorValor) {
        nombre.reportValidity();
        proveedor.reportValidity();
        return;
    }

    const productIdValor = Number(productoId.value || 0) || null;
    const producto = {
        id_configuracion: null,
        product_id: productIdValor,
        clave: clave.value.trim(),
        proveedor_id: null,
        proveedor_nombre: proveedorValor,
        nombre_producto: nombreValor,
        categoria: categoria.value,
        categoria_resultante: resultante.value.trim(),
        unidad: unidad.value,
        porcentaje_merma: Number(merma.value || 0),
        activo: true,
    };
    const indiceExistente = productosCarnicosDraft.findIndex((registro) => (
        (productIdValor && Number(registro.product_id) === productIdValor)
        || (
            !productIdValor
            && registro.nombre_producto.trim().toUpperCase() === nombreValor.toUpperCase()
            && String(registro.proveedor_nombre || "").trim().toUpperCase()
                === proveedorValor.toUpperCase()
        )
    ));

    if (indiceExistente >= 0) {
        productosCarnicosDraft[indiceExistente] = {
            ...productosCarnicosDraft[indiceExistente],
            ...producto,
            id_configuracion: productosCarnicosDraft[indiceExistente].id_configuracion,
        };
    } else {
        productosCarnicosDraft.push(producto);
    }

    evento.target.reset();
    productoId.value = "";
    clave.value = "";
    categoria.value = "CERDO";
    unidad.value = "KILO";
    configuracionCarnicosSucia = true;
    renderizarConfiguracionCarnicos();
    mostrarMensaje(
        document.getElementById("mensaje-configuracion-carnicos"),
        "Producto agregado al borrador. Presiona Guardar para confirmar.",
        "exito",
    );
}

async function confirmarLimpiezaConfiguracion() {
    if (!productosCarnicosDraft.length) {
        return;
    }

    const decision = await pedirConfirmacionModulo({
        etiqueta: "Configuracion",
        titulo: "Limpiar productos agregados",
        texto: "Los productos se marcaran como ocultos en el borrador. Guarda para aplicar el cambio.",
        aceptarTexto: "Limpiar",
        cancelarTexto: "Cancelar",
    });

    if (!decision.confirmado) {
        return;
    }

    productosCarnicosDraft = productosCarnicosDraft.map((producto) => ({
        ...producto,
        activo: false,
    }));
    configuracionCarnicosSucia = true;
    renderizarConfiguracionCarnicos();
}

function alternarModoEliminarConfig() {
    modoEliminarConfig = !modoEliminarConfig;
    const boton = document.getElementById("config-boton-eliminar");
    boton.classList.toggle("is-active", modoEliminarConfig);
    boton.textContent = modoEliminarConfig ? "Terminar" : "Eliminar";
    renderizarConfiguracionCarnicos();
}

function mostrarSelectorCaptura() {
    document.getElementById("panel-tipo-captura")?.classList.remove("hidden");
    document.getElementById("panel-captura-carnica")?.classList.add("hidden");
    document.getElementById("panel-captura-salida")?.classList.add("hidden");
    document.getElementById("panel-tipo-captura")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
    });
}

function seleccionarTipoCaptura(tipo) {
    const esEntrada = tipo === "entrada";
    document.getElementById("panel-tipo-captura")?.classList.add("hidden");
    document.getElementById("panel-captura-carnica")?.classList.toggle("hidden", !esEntrada);
    document.getElementById("panel-captura-salida")?.classList.toggle("hidden", esEntrada);

    if (esEntrada) {
        document.getElementById("producto-entrada-busqueda")?.focus();
    } else {
        document.getElementById("producto-base-busqueda")?.focus();
    }
}

async function guardarConfiguracionCarnicos() {
    const mensaje = document.getElementById("mensaje-configuracion-carnicos");
    const decision = await pedirConfirmacionModulo({
        etiqueta: "Configuracion",
        titulo: "Guardar configuracion",
        texto: "Confirma el usuario que realizo los cambios. Al aceptar se guardara la configuracion.",
        requiereTexto: true,
        label: "Usuario que autoriza",
        placeholder: "Nombre de usuario",
        aceptarTexto: "Guardar",
        cancelarTexto: "Cancelar",
    });

    if (!decision.confirmado) {
        return;
    }

    const usuario = decision.valor;
    const confirmacion = await pedirConfirmacionModulo({
        etiqueta: "Configuracion",
        titulo: "Confirmar guardado",
        texto: "Seguro que quieres guardar los cambios de configuracion?",
        aceptarTexto: "Si, guardar",
        cancelarTexto: "Cancelar",
    });

    if (!confirmacion.confirmado) {
        return;
    }

    try {
        const datos = await solicitarJson(`${API_CARNICO}/productos`, {
            method: "PUT",
            body: JSON.stringify({
                usuario_confirmacion_nombre: usuario.trim(),
                productos: productosCarnicosDraft,
            }),
        });
        productosCarnicosDraft = (datos.productos || []).map((producto) => ({ ...producto }));
        configuracionCarnicosSucia = false;
        renderizarConfiguracionCarnicos();
        mostrarMensaje(mensaje, "Configuracion guardada.", "exito");
        await cargarModuloCarnico();
    } catch (error) {
        mostrarMensaje(mensaje, error.message, "error");
    }
}

function iniciarModuloCarnico() {
    document.getElementById("form-transformacion-carnica")
        ?.addEventListener("submit", registrarTransformacionCarnica);
    document.getElementById("form-salida-carnica")
        ?.addEventListener("submit", registrarSalidaCarnica);
    document.getElementById("cantidad-entrada-carnico")
        ?.addEventListener("input", (evento) => {
            limitarCampoKg(evento.target);
            ocultarPanelInsumos();
            actualizarEstadoMerma();
        });
    document.getElementById("cantidad-merma-carnico")
        ?.addEventListener("input", (evento) => {
            limitarCampoPorcentaje(evento.target);
            ocultarPanelInsumos();
            actualizarEstadoMerma();
        });
    document.getElementById("boton-ver-insumos")
        ?.addEventListener("click", cargarInsumosTransformacion);
    document.getElementById("cantidad-salida-base")
        ?.addEventListener("input", (evento) => {
            limitarCampoKg(evento.target);
        });
    document.getElementById("boton-iniciar-captura")
        ?.addEventListener("click", mostrarSelectorCaptura);
    document.querySelectorAll(".tipo-captura-card").forEach((boton) => {
        boton.addEventListener("click", () => seleccionarTipoCaptura(boton.dataset.captura));
    });
    document.getElementById("boton-toggle-filtros")
        ?.addEventListener("click", alternarMenuFiltros);
    document.querySelectorAll(".boton-filtro").forEach((boton) => {
        boton.addEventListener("click", () => seleccionarFiltroHistorial(boton));
    });
    document.getElementById("historial-pagina-anterior")
        ?.addEventListener("click", () => {
            paginaHistorial = Math.max(1, paginaHistorial - 1);
            renderizarHistorialCarnico();
        });
    document.getElementById("historial-pagina-siguiente")
        ?.addEventListener("click", () => {
            const totalPaginas = Math.max(
                1,
                Math.ceil(registrosHistorialFiltrados().length / HISTORIAL_POR_PAGINA),
            );
            paginaHistorial = Math.min(totalPaginas, paginaHistorial + 1);
            renderizarHistorialCarnico();
        });
    document.getElementById("boton-configuracion-carnicos")
        ?.addEventListener("click", abrirConfiguracionCarnicos);
    document.getElementById("cerrar-configuracion-carnicos")
        ?.addEventListener("click", cerrarConfiguracionCarnicos);
    document.getElementById("form-producto-carnico")
        ?.addEventListener("submit", agregarProductoCarnico);
    document.getElementById("guardar-configuracion-carnicos")
        ?.addEventListener("click", guardarConfiguracionCarnicos);
    document.getElementById("config-boton-agregar")
        ?.addEventListener("click", () => mostrarFormularioConfigProducto());
    document.getElementById("config-boton-buscar")
        ?.addEventListener("click", () => {
            const termino = document.getElementById("config-buscar-producto")?.value.trim() || "";
            void cargarProductosDisponiblesConfig(termino);
        });
    document.getElementById("config-buscar-producto")
        ?.addEventListener("keydown", (evento) => {
            if (evento.key === "Enter") {
                evento.preventDefault();
                const termino = evento.target.value.trim();
                void cargarProductosDisponiblesConfig(termino);
            }
        });
    document.getElementById("config-boton-eliminar")
        ?.addEventListener("click", alternarModoEliminarConfig);
    document.getElementById("config-pagina-anterior")
        ?.addEventListener("click", () => {
            paginaProductosDisponibles = Math.max(1, paginaProductosDisponibles - 1);
            renderizarProductosDisponiblesConfig();
        });
    document.getElementById("config-pagina-siguiente")
        ?.addEventListener("click", () => {
            const totalProductos = obtenerProductosTablaConfiguracion().length;
            const totalPaginas = Math.max(
                1,
                Math.ceil(totalProductos / PRODUCTOS_POR_PAGINA_CONFIG),
            );
            paginaProductosDisponibles = Math.min(totalPaginas, paginaProductosDisponibles + 1);
            renderizarProductosDisponiblesConfig();
        });

    configurarAutocompleteProducto(
        "producto-entrada-busqueda",
        "producto-entrada-carnico",
        "sugerencias-entrada-carnico",
    );
    configurarAutocompleteProducto(
        "producto-base-busqueda",
        "producto-base-carnico",
        "sugerencias-base-carnico",
    );

    verificarPermisosConfiguracion();
    cargarModuloCarnico();
}

document.addEventListener("DOMContentLoaded", () => {
    if (!document.getElementById("dashboardPage")) {
        return;
    }

    iniciarNavegacion();
    iniciarModuloCarnico();
});
