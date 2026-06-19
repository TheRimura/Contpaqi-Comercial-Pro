async function iniciarSesion() {
    const usuarioInput = document.getElementById("usuario");
    const passwordInput = document.getElementById("password");
    const mensajeError = document.getElementById("loginError");

    if (!usuarioInput || !passwordInput || !mensajeError) {
        return;
    }

    const usuario = usuarioInput.value.trim();
    const password = passwordInput.value;

    mensajeError.textContent = "";

    if (!usuario || !password) {
        mensajeError.textContent = "Ingresa usuario y contraseña";
        return;
    }

    try {
        const respuesta = await fetch("/login/", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                usuario,
                password
            })
        });
         
        const datos = await respuesta.json();

        if (!respuesta.ok) {
            mensajeError.textContent =
                datos.detail || "No se pudo iniciar sesión";
            return;
        }

        if (!datos.acceso) {
            mensajeError.textContent =
                datos.mensaje || "No se pudo iniciar sesión";
            return;
        }

        window.location.href = "/dashboard";
    } catch (error) {
        mensajeError.textContent =
            "No se pudo conectar con el servidor";
        console.error(error);
    }
}


async function cargarSesionActual() {
    const respuesta = await fetch("/login/sesion", {
        credentials: "same-origin"
    });

    if (!respuesta.ok) {
        window.location.href = "/";
        return null;
    }

    const datos = await respuesta.json();
    sesionActual = datos;

    const usuarioActivo = document.getElementById("usuarioActivo");

    if (usuarioActivo) {
        usuarioActivo.textContent = datos.usuario || "Usuario";
    }

    return datos;
}


function mostrarSeccion(idSeccion) {
    document.querySelectorAll(".section").forEach(function (seccion) {
        seccion.classList.add("hidden");
    });

    document.querySelectorAll(".top-nav [data-seccion]").forEach(
        function (boton) {
            const estaActiva = boton.dataset.seccion === idSeccion;

            boton.classList.toggle("is-active", estaActiva);

            if (estaActiva) {
                boton.setAttribute("aria-current", "page");
            } else {
                boton.removeAttribute("aria-current");
            }
        }
    );

    const seccionSeleccionada = document.getElementById(idSeccion);

    if (seccionSeleccionada) {
        seccionSeleccionada.classList.remove("hidden");
    }

    if (idSeccion === "registros") {
        cargarHistorialTransformaciones();
    }
}


async function cerrarSesion() {
    try {
        await fetch("/login/logout", {
            method: "POST",
            credentials: "same-origin"
        });
    } catch (error) {
        console.error(error);
    }

    window.location.href = "/";
}


const PRODUCTOS_POR_PAGINA = 10;
const REGISTROS_POR_PAGINA = PRODUCTOS_POR_PAGINA;
const TIPO_RECETA_CONFIGURADA = "receta_configurada";
const TIPO_PRODUCTO_FINAL = "producto_final";
let sesionActual = null;
let productosBusquedaActual = "";
let productosPaginaActual = 1;
let registrosPaginaActual = 1;
let productoOrigenSeleccionado = null;
let productoSeleccionadoOriginal = null;
let productosResultantesDisponibles = [];
let productosRecetaDisponibles = [];
let productoTieneRecetaConfigurada = false;
let productoYaTransformadoSeleccionado = false;
let tipoRelacionRecetaConfigurada = null;
let idOperacionActual = crearIdOperacion();


function crearIdOperacion() {
    if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
    }

    return (
        `${Date.now()}-${Math.random().toString(16).slice(2)}` +
        `-${Math.random().toString(16).slice(2)}`
    );
}


async function consultarProductos(
    termino,
    pagina = 1,
    limite = PRODUCTOS_POR_PAGINA
) {
    const parametros = new URLSearchParams({
        busqueda: termino,
        pagina: String(pagina),
        limite: String(limite)
    });

    const respuesta = await fetch(`/productos/?${parametros}`, {
        credentials: "same-origin"
    });
    const datos = await respuesta.json();

    if (!respuesta.ok) {
        throw new Error(
            datos.detail || "No fue posible consultar los productos"
        );
    }

    return datos;
}


function crearTablaProductos(productos) {
    const tabla = document.createElement("table");
    const encabezado = document.createElement("thead");
    const cuerpo = document.createElement("tbody");

    tabla.className = "productos-tabla";

    encabezado.innerHTML = `
        <tr>
            <th>ID</th>
            <th>Clave</th>
            <th>Nombre</th>
            <th>Categoría</th>
            <th>Unidad</th>
            <th>Existencia</th>
        </tr>
    `;

    productos.forEach(function (producto) {
        const fila = document.createElement("tr");
        fila.title =
            "Doble click para usar este producto como origen";

        [
            producto.id,
            producto.clave,
            producto.nombre,
            producto.categoria,
            producto.unidad,
            producto.existencia
        ].forEach(function (valor) {
            const celda = document.createElement("td");
            celda.textContent = valor ?? "";
            fila.appendChild(celda);
        });

        fila.addEventListener("click", function () {
            cuerpo.querySelectorAll("tr").forEach(function (registro) {
                registro.classList.remove("fila-seleccionada");
            });

            fila.classList.add("fila-seleccionada");
        });

        fila.addEventListener("dblclick", function () {
            seleccionarProductoOrigen(producto);
        });

        cuerpo.appendChild(fila);
    });

    tabla.append(encabezado, cuerpo);
    return tabla;
}


function crearControlesPaginacion(
    resultado,
    etiqueta,
    cambiarPagina
) {
    const controles = document.createElement("div");
    controles.className = "paginacion";

    const resumen = document.createElement("span");
    resumen.textContent =
        `Página ${resultado.pagina} de ${resultado.total_paginas} ` +
        `(${resultado.total} ${etiqueta})`;

    const anterior = document.createElement("button");
    anterior.type = "button";
    anterior.textContent = "Anterior";
    anterior.disabled = resultado.pagina <= 1;
    anterior.addEventListener("click", function () {
        cambiarPagina(resultado.pagina - 1);
    });

    const siguiente = document.createElement("button");
    siguiente.type = "button";
    siguiente.textContent = "Siguiente";
    siguiente.disabled = resultado.pagina >= resultado.total_paginas;
    siguiente.addEventListener("click", function () {
        cambiarPagina(resultado.pagina + 1);
    });

    controles.append(anterior, resumen, siguiente);
    return controles;
}


async function buscarProductos(pagina = 1) {
    const busquedaInput = document.getElementById("busquedaProducto");
    const contenedor = document.getElementById("tablaProductos");

    if (!busquedaInput || !contenedor) {
        return;
    }

    const termino = busquedaInput.value.trim();
    contenedor.replaceChildren();

    if (termino.length < 2) {
        contenedor.textContent =
            "Escribe al menos dos caracteres para buscar.";
        return;
    }

    contenedor.textContent = "Buscando productos...";

    try {
        productosBusquedaActual = termino;
        productosPaginaActual = pagina;

        const resultado = await consultarProductos(
            productosBusquedaActual,
            productosPaginaActual,
            PRODUCTOS_POR_PAGINA
        );
        const productos = resultado.productos;

        contenedor.replaceChildren();

        if (productos.length === 0) {
            contenedor.textContent = "No se encontraron productos.";
            return;
        }

        contenedor.appendChild(crearTablaProductos(productos));
        contenedor.appendChild(
            crearControlesPaginacion(
                resultado,
                "productos",
                buscarProductos
            )
        );
    } catch (error) {
        contenedor.textContent = error.message;
    }
}


function formatearCantidad(valor) {
    const numero = Number(valor || 0);

    if (!Number.isFinite(numero)) {
        return "0.000";
    }

    return numero.toFixed(3);
}


function formatearCantidadCorta(valor) {
    const numero = Number(valor || 0);

    if (!Number.isFinite(numero)) {
        return "0";
    }

    return new Intl.NumberFormat("es-ES", {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2
    }).format(numero);
}


function formatearKg(valor) {
    return `${formatearCantidadCorta(valor)} kg`;
}


function formatearCantidadCaptura(valor) {
    const numero = Number(valor || 0);

    if (!Number.isFinite(numero) || numero <= 0) {
        return "";
    }

    if (numero < 0.1) {
        return `${formatearCantidadCorta(numero * 1000)} g`;
    }

    return formatearKg(numero);
}


function formatearCantidadFormula(valor) {
    const numero = Number(valor || 0);

    if (!Number.isFinite(numero)) {
        return "";
    }

    if (numero === 0) {
        return "0 kg";
    }

    return formatearCantidadCaptura(numero);
}


function normalizarUnidad(unidad) {
    return String(unidad || "").trim().toUpperCase();
}


function formatearCantidadUnidad(valor, unidad) {
    const numero = Number(valor || 0);
    const unidadNormalizada = normalizarUnidad(unidad);

    if (!Number.isFinite(numero)) {
        return "";
    }

    if (unidadNormalizada === "KILO") {
        return formatearCantidadFormula(numero);
    }

    if (unidadNormalizada === "LITRO") {
        if (numero === 0) {
            return "0 L";
        }

        if (numero < 0.1) {
            return `${formatearCantidadCorta(numero * 1000)} ml`;
        }

        return `${formatearCantidadCorta(numero)} L`;
    }

    if (unidadNormalizada === "PIEZA") {
        return `${formatearCantidadCorta(numero)} pza`;
    }

    return `${formatearCantidadCorta(numero)} ${unidad || ""}`.trim();
}


function leerCantidadKg(valor) {
    if (typeof valor === "number") {
        return Number.isFinite(valor) ? valor : 0;
    }

    const textoOriginal = String(valor || "")
        .toLowerCase()
        .trim();
    const estaEnGramos =
        /\bg\b/.test(textoOriginal) && !/\bkg\b/.test(textoOriginal);
    const texto = textoOriginal
        .replace("kg", "")
        .replace("g", "")
        .replace(",", ".")
        .trim();
    const numero = Number(texto);

    if (!Number.isFinite(numero)) {
        return 0;
    }

    return estaEnGramos ? numero / 1000 : numero;
}


function leerCantidadUnidad(valor, unidad) {
    const unidadNormalizada = normalizarUnidad(unidad);
    const texto = String(valor || "").toLowerCase().trim();

    if (unidadNormalizada === "KILO") {
        return leerCantidadKg(valor);
    }

    if (unidadNormalizada === "LITRO") {
        const numero = Number(
            texto
                .replace("ml", "")
                .replace("l", "")
                .replace(",", ".")
                .trim()
        );

        if (!Number.isFinite(numero)) {
            return 0;
        }

        return texto.includes("ml") ? numero / 1000 : numero;
    }

    const numero = Number(
        texto
            .replace("pzas", "")
            .replace("pza", "")
            .replace(",", ".")
            .trim()
    );
    return Number.isFinite(numero) ? numero : 0;
}


function cantidadApi(valor) {
    return leerCantidadKg(valor).toFixed(4);
}


function formatearPorcentajeCorto(valor) {
    const numero = Number(valor || 0);

    if (!Number.isFinite(numero)) {
        return "0%";
    }

    return `${new Intl.NumberFormat("es-ES", {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2
    }).format(numero)}%`;
}


function formatearPorcentaje(valor) {
    const numero = Number(valor || 0);

    if (!Number.isFinite(numero)) {
        return "0.00";
    }

    return numero.toFixed(2);
}


function porcentajeMermaEstimadaProducto() {
    return Number(
        productoOrigenSeleccionado?.merma_estimada?.porcentaje || 0
    );
}


function calcularEntradaEstimada(totalSalida, porcentajeMerma) {
    const salida = Number(totalSalida || 0);
    const porcentaje = Number(porcentajeMerma || 0);
    const rendimiento = 1 - (porcentaje / 100);

    if (salida <= 0) {
        return 0;
    }

    if (rendimiento <= 0) {
        return salida;
    }

    return salida / rendimiento;
}


function reiniciarLimiteMerma() {
    const porcentajeMermaEsperado = document.getElementById(
        "porcentajeMermaEsperado"
    );

    if (porcentajeMermaEsperado) {
        porcentajeMermaEsperado.value = "";
    }
}


function obtenerProductoDisponible(productoId) {
    return productosResultantesDisponibles.find(function (producto) {
        return Number(producto.id) === Number(productoId);
    });
}


function cantidadBaseProducto(producto) {
    const cantidadFormula = Number(producto?.cantidad_formula || 0);

    if (cantidadFormula > 0) {
        return cantidadFormula;
    }

    return Number(producto?.cantidad_resultante || 0);
}


function esComponenteBaseFormula(producto) {
    const categoria = String(producto?.categoria || "").trim().toUpperCase();

    return producto?.participa_balance !== false && categoria !== "INSUMOS";
}


function actualizarTarjetaOrigen(producto) {
    const tarjeta = document.getElementById("tarjetaOrigen");
    const nombre = document.getElementById("origenNombre");
    const productoNombre = document.getElementById("origenProducto");
    const clave = document.getElementById("origenClave");
    const unidad = document.getElementById("origenUnidad");
    const existencia = document.getElementById("origenExistencia");
    const unidadCantidad = document.getElementById("unidadCantidadOrigen");

    if (!tarjeta || !nombre || !productoNombre || !clave || !unidad) {
        return;
    }

    tarjeta.classList.remove("origen-card-empty");
    nombre.textContent = producto.categoria || "-";
    productoNombre.textContent = producto.nombre || "-";
    clave.textContent = producto.clave || "-";
    unidad.textContent = producto.unidad || "-";

    if (existencia) {
        const existenciaValor = Number(producto.existencia || 0);
        existencia.textContent = existenciaValor > 0
            ? formatearCantidadCorta(existenciaValor)
            : "-";
    }

    if (unidadCantidad) {
        unidadCantidad.textContent = producto.unidad
            ? `(${producto.unidad})`
            : "";
    }
}


function actualizarOrigenDesdeFormula(productoBase) {
    const resultadoOrigen = document.getElementById("resultadoOrigen");
    const productoIdInput = document.getElementById("productoOrigenId");

    if (!productoBase) {
        return;
    }

    productoOrigenSeleccionado = productoBase;

    if (productoIdInput) {
        productoIdInput.value = String(productoBase.id);
    }

    actualizarTarjetaOrigen(productoBase);
    reiniciarLimiteMerma();

    if (resultadoOrigen) {
        resultadoOrigen.className = "seleccion-origen";
        resultadoOrigen.textContent =
            `Categoria de origen: ${productoBase.categoria || "-"}`;
    }
}


function restaurarProductoSeleccionadoComoOrigen() {
    const productoIdInput = document.getElementById("productoOrigenId");

    if (!productoSeleccionadoOriginal) {
        return;
    }

    productoOrigenSeleccionado = productoSeleccionadoOriginal;

    if (productoIdInput) {
        productoIdInput.value = String(productoSeleccionadoOriginal.id);
    }

    actualizarTarjetaOrigen(productoSeleccionadoOriginal);
    reiniciarLimiteMerma();
}


async function consultarProductosResultantes(productoId) {
    const respuesta = await fetch(`/productos/${productoId}/resultantes`, {
        credentials: "same-origin"
    });
    const datos = await respuesta.json();

    if (!respuesta.ok) {
        throw new Error(
            datos.detail || "No fue posible consultar los resultantes"
        );
    }

    return datos;
}


async function cargarProductosResultantes(productoId) {
    const contenedor = document.getElementById("productosResultantes");

    if (!contenedor) {
        return;
    }

    productoYaTransformadoSeleccionado = false;
    productoTieneRecetaConfigurada = false;
    tipoRelacionRecetaConfigurada = null;
    productosResultantesDisponibles = [];
    productosRecetaDisponibles = [];
    contenedor.replaceChildren();
    contenedor.textContent = "Cargando productos resultantes...";

    try {
        const datos = await consultarProductosResultantes(productoId);
        productosRecetaDisponibles = datos.productos || [];
        tipoRelacionRecetaConfigurada = datos.tipo_relacion || null;
        productoTieneRecetaConfigurada =
            productosRecetaDisponibles.length > 0;
        configurarTipoTransformacion(productoTieneRecetaConfigurada);
        renderizarProductosResultantes();
    } catch (error) {
        contenedor.textContent = error.message;
    }
}


function obtenerTipoTransformacionSeleccionado() {
    const tipoTransformacion = document.getElementById("tipoTransformacion");

    if (!tipoTransformacion) {
        return TIPO_RECETA_CONFIGURADA;
    }

    return tipoTransformacion.value || TIPO_RECETA_CONFIGURADA;
}


function configurarTipoTransformacion(tieneReceta) {
    const tipoTransformacion = document.getElementById("tipoTransformacion");
    const ayuda = document.getElementById("ayudaTipoTransformacion");

    if (!tipoTransformacion) {
        return;
    }

    tipoTransformacion.disabled = false;

    Array.from(tipoTransformacion.options).forEach(function (opcion) {
        opcion.disabled =
            opcion.value === TIPO_RECETA_CONFIGURADA && !tieneReceta;
    });

    tipoTransformacion.value = tieneReceta
        ? TIPO_RECETA_CONFIGURADA
        : TIPO_PRODUCTO_FINAL;

    if (ayuda) {
        if (!tieneReceta) {
            ayuda.textContent =
                "Este producto no tiene receta configurada; solo se puede registrar como producto final.";
        } else if (
            tipoRelacionRecetaConfigurada ===
            "formula_lista_para_cocinar"
        ) {
            ayuda.textContent =
                "Se cargaran todos los componentes de la formula configurada.";
        } else {
            ayuda.textContent =
                "Puedes usar la receta configurada o registrarlo como producto final.";
        }
    }
}


function crearAvisoProductoFinal() {
    const aviso = document.createElement("div");
    aviso.className = "aviso-producto-transformado";
    aviso.textContent =
        "Se registrara como producto final: captura la salida y el sistema estimara entrada y merma.";

    return aviso;
}


function renderizarProductosResultantes() {
    const contenedor = document.getElementById("productosResultantes");
    const tipoTransformacion = obtenerTipoTransformacionSeleccionado();

    if (!contenedor || !productoOrigenSeleccionado) {
        return;
    }

    contenedor.replaceChildren();
    contenedor.classList.remove("formula-resultantes");
    configurarEncabezadoResultantes("Productos resultantes", true);
    productoYaTransformadoSeleccionado =
        tipoTransformacion === TIPO_PRODUCTO_FINAL;

    if (productoYaTransformadoSeleccionado) {
        restaurarProductoSeleccionadoComoOrigen();
        configurarEncabezadoResultantes("Producto final", false);
        productosResultantesDisponibles = [
            {
                ...productoSeleccionadoOriginal,
                cantidad_origen: 1,
                cantidad_resultante: 1
            }
        ];

        agregarProductoResultante();
        contenedor.prepend(crearAvisoProductoFinal());
        actualizarBalance();
        return;
    }

    restaurarProductoSeleccionadoComoOrigen();
    productosResultantesDisponibles = productosRecetaDisponibles;

    if (productosResultantesDisponibles.length === 0) {
        mostrarMensajeResultantes(
            "Este producto no tiene receta configurada."
        );
        actualizarBalance();
        return;
    }

    if (tipoRelacionRecetaConfigurada === "formula_lista_para_cocinar") {
        configurarEncabezadoResultantes("Componentes de formula", false);
        renderizarFormula(productosResultantesDisponibles);
        actualizarBalance();
        return;
    }

    agregarProductoResultante();
    actualizarBalance();
}


async function seleccionarProductoOrigen(producto) {
    const productoIdInput = document.getElementById("productoOrigenId");
    const cantidadOrigenInput = document.getElementById("cantidadOrigen");
    const resultadoOrigen = document.getElementById("resultadoOrigen");

    if (!productoIdInput || !cantidadOrigenInput) {
        return;
    }

    productoSeleccionadoOriginal = producto;
    productoOrigenSeleccionado = producto;
    productoIdInput.value = producto.id;
    cantidadOrigenInput.value = "0";
    actualizarTarjetaOrigen(producto);
    reiniciarLimiteMerma();

    if (resultadoOrigen) {
        resultadoOrigen.className = "seleccion-origen";
        resultadoOrigen.textContent =
            `Producto origen seleccionado: ${producto.categoria}`;
    }

    const resultadoTransformacion = document.getElementById(
        "resultadoTransformacion"
    );

    if (resultadoTransformacion) {
        resultadoTransformacion.className = "";
        resultadoTransformacion.textContent = "";
    }

    mostrarSeccion("transformacion");
    await cargarProductosResultantes(producto.id);
    actualizarBalance();
}


function mostrarMensajeResultantes(mensaje) {
    const contenedor = document.getElementById("productosResultantes");

    if (!contenedor) {
        return;
    }

    contenedor.replaceChildren();
    contenedor.textContent = mensaje;
}


function configurarEncabezadoResultantes(titulo, mostrarBoton) {
    const tituloSeccion = document.getElementById(
        "tituloProductosResultantes"
    );
    const botonAgregar = document.getElementById("botonAgregarResultante");

    if (tituloSeccion) {
        tituloSeccion.textContent = titulo;
    }

    if (botonAgregar) {
        botonAgregar.hidden = !mostrarBoton;
    }
}


function crearResumenFormula(productoBase, ingredientes) {
    const resumen = document.createElement("div");
    const texto = document.createElement("div");
    const etiquetas = document.createElement("div");

    resumen.className = "formula-resumen";
    texto.innerHTML = `
        <strong>Formula configurada</strong>
        <span>Los ingredientes se ajustan con el peso del producto base.</span>
    `;
    etiquetas.className = "formula-etiquetas";

    if (productoBase) {
        const etiquetaBase = document.createElement("span");
        etiquetaBase.textContent = "1 producto base";
        etiquetas.appendChild(etiquetaBase);
    }

    const etiquetaIngredientes = document.createElement("span");
    etiquetaIngredientes.textContent = `${ingredientes.length} ingredientes`;
    etiquetas.appendChild(etiquetaIngredientes);

    resumen.append(texto, etiquetas);
    return resumen;
}


function crearInfoFormula(producto) {
    const info = document.createElement("div");
    const nombre = document.createElement("strong");
    const detalle = document.createElement("span");

    info.className = "formula-info";
    nombre.textContent = producto.nombre || "Producto";
    detalle.textContent =
        `${producto.clave || "Sin clave"} - ${producto.categoria || "-"}`;
    info.append(nombre, detalle);
    return info;
}


function crearCampoCantidadFormula(producto, esBase) {
    const fila = document.createElement("div");
    const productoId = document.createElement("input");
    const info = crearInfoFormula(producto);
    const cantidad = document.createElement("input");
    const campoCantidad = document.createElement("div");
    const cantidadBase = cantidadBaseProducto(producto);
    const unidadProducto = normalizarUnidad(producto.unidad);

    fila.className = esBase
        ? "formula-componente formula-base"
        : "formula-componente formula-item";
    productoId.type = "hidden";
    productoId.className = "formula-componente-id";
    productoId.value = String(producto.id);

    cantidad.type = "text";
    cantidad.inputMode = "decimal";
    cantidad.placeholder = "Cantidad";
    cantidad.className = "formula-componente-cantidad formula-cantidad";
    cantidad.value = esBase
        ? formatearCantidadCorta(cantidadBase)
        : formatearCantidadUnidad(cantidadBase, unidadProducto);
    cantidad.dataset.cantidadBase = String(cantidadBase);
    cantidad.dataset.unidad = unidadProducto;

    if (esBase) {
        const unidad = document.createElement("span");

        cantidad.id = "formulaProductoBaseCantidad";
        cantidad.addEventListener("input", ajustarFormulaDesdeProductoBase);
        campoCantidad.className = "formula-cantidad-unidad";
        unidad.className = "formula-unidad-fija";
        unidad.textContent = "kg";
        campoCantidad.append(cantidad, unidad);
    } else {
        cantidad.readOnly = true;
        cantidad.tabIndex = -1;
        campoCantidad.appendChild(cantidad);
    }

    fila.append(productoId, info, campoCantidad);
    return fila;
}


function agregarComponenteFormula(producto) {
    const lista = document.getElementById("listaFormula");

    if (!lista) {
        return;
    }

    lista.appendChild(crearCampoCantidadFormula(producto, false));
}


function ajustarFormulaDesdeProductoBase() {
    const cantidadBaseInput = document.getElementById(
        "formulaProductoBaseCantidad"
    );

    if (!cantidadBaseInput) {
        return;
    }

    const cantidadActual = leerCantidadKg(cantidadBaseInput.value);
    const cantidadOriginal = Number(
        cantidadBaseInput.dataset.cantidadBase || 0
    );

    if (!Number.isFinite(cantidadActual) || cantidadOriginal <= 0) {
        actualizarBalance();
        return;
    }

    const factor = cantidadActual / cantidadOriginal;

    document
        .querySelectorAll(".formula-item .formula-componente-cantidad")
        .forEach(function (input) {
            const cantidadBase = Number(input.dataset.cantidadBase || 0);
            const unidad = input.dataset.unidad || "";

            if (cantidadBase > 0) {
                input.value = formatearCantidadUnidad(
                    cantidadBase * factor,
                    unidad
                );
            }
        });

    actualizarBalance();
}


function separarFormula(productosBalance) {
    const productoBase =
        productosBalance.find(esComponenteBaseFormula) ||
        productosBalance[0] ||
        null;
    const ingredientes = productosBalance.filter(function (producto) {
        return !productoBase || producto.id !== productoBase.id;
    });

    return {
        productoBase,
        ingredientes,
    };
}


function crearResultadoFormula(producto) {
    const fila = document.createElement("div");
    const productoId = document.createElement("input");
    const info = crearInfoFormula(producto);
    const cantidad = document.createElement("input");

    fila.className = "producto-resultante formula-resultado";
    productoId.type = "hidden";
    productoId.className = "producto-resultante-id";
    productoId.value = String(producto.id);

    cantidad.type = "text";
    cantidad.readOnly = true;
    cantidad.tabIndex = -1;
    cantidad.className =
        "producto-resultante-cantidad formula-cantidad";
    cantidad.dataset.unidad = "KILO";
    cantidad.value = "0 kg";

    fila.append(productoId, info, cantidad);
    return fila;
}


function renderizarFormula(productosFormula) {
    const contenedor = document.getElementById("productosResultantes");
    const lista = document.createElement("div");
    const formula = separarFormula(productosFormula);

    if (!contenedor || !productoSeleccionadoOriginal) {
        return;
    }

    actualizarOrigenDesdeFormula(formula.productoBase);
    contenedor.replaceChildren();
    contenedor.classList.add("formula-resultantes");
    lista.id = "listaFormula";
    lista.className = "formula-lista";

    contenedor.appendChild(
        crearResumenFormula(
            formula.productoBase,
            formula.ingredientes
        )
    );

    if (formula.productoBase) {
        contenedor.appendChild(
            crearCampoCantidadFormula(formula.productoBase, true)
        );
    }

    contenedor.appendChild(lista);

    formula.ingredientes.forEach(function (producto) {
        agregarComponenteFormula(producto);
    });

    const tituloResultado = document.createElement("h4");
    tituloResultado.className = "formula-resultado-titulo";
    tituloResultado.textContent = "Producto resultante";
    contenedor.append(
        tituloResultado,
        crearResultadoFormula(productoSeleccionadoOriginal)
    );
}


function obtenerCuerpoTablaResultantes() {
    const contenedor = document.getElementById("productosResultantes");

    if (!contenedor) {
        return null;
    }

    let cuerpo = document.getElementById("cuerpoProductosResultantes");

    if (!cuerpo) {
        contenedor.replaceChildren();

        const tabla = document.createElement("table");
        const encabezado = document.createElement("thead");
        cuerpo = document.createElement("tbody");

        tabla.className = "tabla-resultantes";
        cuerpo.id = "cuerpoProductosResultantes";

        encabezado.innerHTML = `
            <tr>
                <th>Producto resultante</th>
                <th>Unidad</th>
                <th>Cantidad</th>
                <th></th>
            </tr>
        `;

        tabla.append(encabezado, cuerpo);
        contenedor.appendChild(tabla);
    }

    return cuerpo;
}


function idsResultantesSeleccionados(selectOmitido = null) {
    return Array.from(
        document.querySelectorAll(".producto-resultante-id")
    ).filter(function (select) {
        return select !== selectOmitido && select.value;
    }).map(function (select) {
        return select.value;
    });
}


function actualizarOpcionesResultantes() {
    document.querySelectorAll(".producto-resultante-id").forEach(
        function (select) {
            const idsUsados = idsResultantesSeleccionados(select);

            Array.from(select.options).forEach(function (opcion) {
                opcion.disabled =
                    opcion.value !== "" &&
                    idsUsados.includes(opcion.value);
            });
        }
    );
}


function agregarProductoResultante(productoPreseleccionado = null) {
    if (!productoOrigenSeleccionado) {
        mostrarMensajeResultantes(
            "Primero selecciona un producto desde la tabla de productos."
        );
        return;
    }

    if (productosResultantesDisponibles.length === 0) {
        mostrarMensajeResultantes(
            "No hay productos resultantes disponibles para este origen."
        );
        return;
    }

    if (
        productoYaTransformadoSeleccionado &&
        document.querySelector(".producto-resultante")
    ) {
        const resultadoTransformacion = document.getElementById(
            "resultadoTransformacion"
        );

        if (resultadoTransformacion) {
            resultadoTransformacion.className = "result-container";
            resultadoTransformacion.textContent =
                "Este producto ya se registra como producto final.";
        }

        return;
    }

    const cuerpo = obtenerCuerpoTablaResultantes();

    if (!cuerpo) {
        return;
    }

    const fila = document.createElement("tr");
    const productoId = document.createElement("select");
    const opcionInicial = document.createElement("option");

    fila.className = "producto-resultante";
    productoId.className = "producto-resultante-id";
    opcionInicial.value = "";
    opcionInicial.textContent = "Selecciona un producto";

    productoId.appendChild(opcionInicial);

    const celdaProducto = document.createElement("td");
    const celdaUnidad = document.createElement("td");
    const celdaCantidad = document.createElement("td");
    const celdaAcciones = document.createElement("td");
    const cantidad = document.createElement("input");
    const eliminar = document.createElement("button");

    cantidad.type = "text";
    cantidad.inputMode = "decimal";
    cantidad.placeholder = "Ej. 1,5 kg";
    cantidad.className = "producto-resultante-cantidad";
    cantidad.dataset.automatica = "1";
    cantidad.dataset.unidad = "KILO";
    celdaUnidad.textContent = "-";

    productosResultantesDisponibles.forEach(function (producto) {
        const opcion = document.createElement("option");

        opcion.value = producto.id;
        opcion.textContent = `${producto.nombre} | ${producto.clave}`;
        productoId.appendChild(opcion);
    });

    productoId.addEventListener("change", function () {
        const repetido = idsResultantesSeleccionados(productoId).includes(
            productoId.value
        );

        if (repetido) {
            const resultadoTransformacion = document.getElementById(
                "resultadoTransformacion"
            );

            fila.classList.add("fila-error");
            productoId.value = "";
            celdaUnidad.textContent = "-";
            cantidad.value = "";

            if (resultadoTransformacion) {
                resultadoTransformacion.className = "error-card";
                resultadoTransformacion.textContent =
                    "Ese producto resultante ya fue agregado.";
            }

            actualizarOpcionesResultantes();
            actualizarBalance();
            return;
        }

        const producto = obtenerProductoDisponible(productoId.value);
        fila.classList.remove("fila-error");
        celdaUnidad.textContent = "KILO";
        cantidad.dataset.unidad = "KILO";

        if (cantidad.dataset.automatica === "1") {
            const cantidadBase = cantidadBaseProducto(producto);
            cantidad.value = cantidadBase > 0
                ? formatearKg(cantidadBase)
                : "";
        }

        actualizarOpcionesResultantes();
        actualizarBalance();
    });

    eliminar.type = "button";
    eliminar.textContent = "Quitar";
    eliminar.addEventListener("click", function () {
        fila.remove();
        actualizarBalance();
    });

    cantidad.addEventListener("input", function () {
        cantidad.dataset.automatica = "0";
        actualizarBalance();
    });

    celdaProducto.appendChild(productoId);
    celdaCantidad.appendChild(cantidad);
    celdaAcciones.appendChild(eliminar);
    fila.append(
        celdaProducto,
        celdaUnidad,
        celdaCantidad,
        celdaAcciones
    );

    if (productoPreseleccionado) {
        productoId.value = String(productoPreseleccionado.id);
        celdaUnidad.textContent = "KILO";
        cantidad.dataset.unidad = "KILO";

        const cantidadBase = cantidadBaseProducto(productoPreseleccionado);
        cantidad.value = cantidadBase > 0
            ? formatearKg(cantidadBase)
            : "";
    }

    if (productoYaTransformadoSeleccionado) {
        productoId.value = String(productoOrigenSeleccionado.id);
        productoId.disabled = true;
        cantidad.dataset.automatica = "1";
        eliminar.disabled = true;
        eliminar.textContent = "Fijo";

        const producto = obtenerProductoDisponible(productoId.value);
        celdaUnidad.textContent = "KILO";
        cantidad.dataset.unidad = "KILO";
    }

    cuerpo.appendChild(fila);
    actualizarOpcionesResultantes();
}


function obtenerProductosResultantes() {
    return Array.from(
        document.querySelectorAll(".producto-resultante")
    ).map(function (fila) {
        const cantidadInput = fila.querySelector(
            ".producto-resultante-cantidad"
        );
        const unidad = cantidadInput.dataset.unidad || "KILO";

        return {
            producto_id: Number(
                fila.querySelector(".producto-resultante-id").value
            ),
            cantidad: leerCantidadUnidad(
                cantidadInput.value,
                unidad
            ).toFixed(4),
            unidad
        };
    });
}


function obtenerComponentesFormula() {
    return Array.from(
        document.querySelectorAll(".formula-componente")
    ).map(function (fila) {
        const productoId = fila.querySelector(
            ".formula-componente-id"
        );
        const cantidad = fila.querySelector(
            ".formula-componente-cantidad"
        );
        const unidad = cantidad.dataset.unidad || "";

        return {
            producto_id: Number(productoId.value),
            cantidad: leerCantidadUnidad(
                cantidad.value,
                unidad
            ).toFixed(4),
            unidad,
            es_producto_base: fila.classList.contains("formula-base")
        };
    });
}


function estaUsandoFormula() {
    return (
        obtenerTipoTransformacionSeleccionado() ===
            TIPO_RECETA_CONFIGURADA &&
        tipoRelacionRecetaConfigurada ===
            "formula_lista_para_cocinar"
    );
}


function textoProductoRegistro(producto) {
    if (!producto) {
        return "Producto no encontrado";
    }

    return `${producto.nombre} | ${producto.clave}`;
}


function resumenProductosResultantes(registro) {
    const productos = registro.productos_resultantes || [];

    if (productos.length > 0) {
        return productos.map(function (item) {
            return (
                `${textoProductoRegistro(item.producto)} ` +
                `(${formatearCantidadUnidad(
                    item.cantidad,
                    item.unidad || item.producto?.unidad
                )})`
            );
        }).join(", ");
    }

    if (registro.producto_base_formula) {
        return (
            `${textoProductoRegistro(registro.producto_base_formula.producto)} ` +
            `(${formatearCantidadUnidad(
                registro.producto_base_formula.cantidad,
                registro.producto_base_formula.unidad || "KILO"
            )})`
        );
    }

    return "-";
}

function textoEstadoErp(estado) {
    const estados = {
        completada: "Inventario afectado",
        pendiente_afectacion: "Pendiente de afectar",
        procesando: "Procesando",
        error: "Error de integración",
        sin_movimientos: "Sin movimientos"
    };

    return estados[estado] || estado || "Sin estado";
}


function textoMovimientosErp(registro) {
    const salida = registro.folio_salida || registro.documento_salida;
    const entrada = registro.folio_entrada || registro.documento_entrada;

    if (!salida && !entrada) {
        return "-";
    }

    return `${salida || "Pendiente"} → ${entrada || "Pendiente"}`;
}

function crearIndicadorRegistro(etiqueta, valor) {
    const indicador = document.createElement("div");
    const titulo = document.createElement("span");
    const contenido = document.createElement("strong");

    indicador.className = "summary-item";
    titulo.textContent = etiqueta;
    contenido.textContent = valor;
    indicador.append(titulo, contenido);
    return indicador;
}


function renderizarIndicadoresRegistros(indicadores) {
    const contenedor = document.getElementById("indicadoresRegistros");

    if (!contenedor) {
        return;
    }

    contenedor.replaceChildren(
        crearIndicadorRegistro(
            "Transformaciones del mes",
            String(indicadores.transformaciones || 0)
        ),
        crearIndicadorRegistro(
            "Kilos procesados",
            formatearKg(indicadores.kilos_procesados)
        ),
        crearIndicadorRegistro(
            "Merma acumulada",
            formatearKg(indicadores.merma_acumulada)
        ),
        crearIndicadorRegistro(
            "Rendimiento",
            formatearPorcentajeCorto(indicadores.rendimiento)
        )
    );
    contenedor.hidden = false;
}


function crearTablaRegistros(registros) {
    const tabla = document.createElement("table");
    const encabezado = document.createElement("thead");
    const cuerpo = document.createElement("tbody");

    tabla.className = "productos-tabla registros-tabla";
    encabezado.innerHTML = `
        <tr>
            <th>Folio</th>
            <th>Tipo</th>
            <th>Fecha</th>
            <th>Usuario</th>
            <th>Producto origen</th>
            <th>Salida</th>
            <th>Entrada</th>
            <th>Merma</th>
            <th>Resultantes</th>
            <th>Movimientos ERP</th>
            <th>Estado</th>
        </tr>
    `;

    registros.forEach(function (registro) {
        const fila = document.createElement("tr");
        const valores = [
            registro.folio,
            registro.tipo_transformacion === TIPO_PRODUCTO_FINAL
                ? "Producto final"
                : "Receta configurada",
            registro.fecha,
            registro.usuario || "-",
            textoProductoRegistro(registro.producto_origen),
            formatearKg(registro.cantidad_origen),
            formatearKg(registro.total_entrada),
            (
                `${formatearKg(registro.peso_merma)} ` +
                `(${formatearPorcentaje(registro.porcentaje_merma_real)}%)`
            ),
            resumenProductosResultantes(registro),
            textoMovimientosErp(registro),
            textoEstadoErp(registro.estado_erp)
        ];

        valores.forEach(function (valor) {
            const celda = document.createElement("td");
            celda.textContent = valor ?? "";
            fila.appendChild(celda);
        });

        cuerpo.appendChild(fila);
    });

    tabla.append(encabezado, cuerpo);
    return tabla;
}


async function cargarHistorialTransformaciones(pagina = 1) {
    const contenedor = document.getElementById("tablaRegistros");

    if (!contenedor) {
        return;
    }

    contenedor.textContent = "Cargando registros...";

    try {
        const parametros = new URLSearchParams({
            pagina: String(pagina),
            limite: String(REGISTROS_POR_PAGINA)
        });
        const respuesta = await fetch(`/transformaciones/?${parametros}`, {
            credentials: "same-origin"
        });
        const datos = await respuesta.json();

        if (!respuesta.ok) {
            throw new Error(
                datos.detail || "No fue posible consultar los registros"
            );
        }

        const registros = datos.registros || [];
        registrosPaginaActual = datos.pagina;
        contenedor.replaceChildren();
        renderizarIndicadoresRegistros(datos.indicadores || {});

        if (registros.length === 0) {
            contenedor.textContent =
                "Aun no hay transformaciones registradas.";
            return;
        }

        contenedor.appendChild(crearTablaRegistros(registros));
        contenedor.appendChild(
            crearControlesPaginacion(
                datos,
                "registros",
                cargarHistorialTransformaciones
            )
        );
    } catch (error) {
        contenedor.textContent = error.message;
    }
}


function actualizarResultadoFormula(cantidad) {
    const salida = document.querySelector(
        ".formula-resultado .producto-resultante-cantidad"
    );

    if (salida) {
        salida.value = formatearKg(cantidad);
    }
}


function actualizarBalance() {
    const cantidadOrigenInput = document.getElementById("cantidadOrigen");
    const pesoMermaInput = document.getElementById("pesoMerma");
    const porcentajeMermaRealInput = document.getElementById(
        "porcentajeMermaReal"
    );
    const porcentajeMermaEsperadoInput = document.getElementById(
        "porcentajeMermaEsperado"
    );
    const resultado = document.getElementById("balanceTransformacion");
    const validationBox = document.querySelector('.validation-box');
    const estadoBalance = document.getElementById("estadoBalance");
    const totalOrigen = document.getElementById("totalOrigen");
    const totalResultantes = document.getElementById("totalResultantes");
    const totalMerma = document.getElementById("totalMerma");
    const porcentajeMermaResumen = document.getElementById(
        "porcentajeMermaResumen"
    );
    const mermaRealResumen = document.getElementById(
        "mermaRealResumen"
    );
    const diferenciaBalance = document.getElementById("diferenciaBalance");

    if (!cantidadOrigenInput || !pesoMermaInput || !resultado) {
        return;
    }

    const porcentajeMermaEstimada = porcentajeMermaEstimadaProducto();
    let totalResultados;
    let cantidadOrigen;

    if (estaUsandoFormula()) {
        const cantidadBase = document.getElementById(
            "formulaProductoBaseCantidad"
        );
        cantidadOrigen = leerCantidadKg(cantidadBase?.value || 0);
        totalResultados = Math.max(
            cantidadOrigen * (1 - porcentajeMermaEstimada / 100),
            0
        );
        actualizarResultadoFormula(totalResultados);
    } else {
        totalResultados = obtenerProductosResultantes().reduce(
            function (total, producto) {
                return total + Number(producto.cantidad || 0);
            },
            0
        );
        cantidadOrigen = calcularEntradaEstimada(
            totalResultados,
            porcentajeMermaEstimada
        );
    }

    const mermaMostrada = Math.max(cantidadOrigen - totalResultados, 0);
    const diferencia = 0;
    const porcentajeMermaReal = cantidadOrigen > 0
        ? (mermaMostrada / cantidadOrigen) * 100
        : 0;
    const porcentajeEsperadoTexto =
        porcentajeMermaEsperadoInput?.value.trim() || "";
    const porcentajeEsperado = porcentajeEsperadoTexto
        ? Number(porcentajeEsperadoTexto)
        : null;

    cantidadOrigenInput.value = cantidadApi(cantidadOrigen);
    pesoMermaInput.value = cantidadApi(mermaMostrada);

    if (porcentajeMermaRealInput) {
        porcentajeMermaRealInput.value =
            formatearPorcentaje(porcentajeMermaReal);
    }

    if (totalOrigen) {
        totalOrigen.textContent = formatearKg(cantidadOrigen);
    }

    if (totalResultantes) {
        totalResultantes.textContent = formatearKg(totalResultados);
    }

    if (totalMerma) {
        totalMerma.textContent = formatearKg(mermaMostrada);
    }

    if (porcentajeMermaResumen) {
        porcentajeMermaResumen.textContent =
            formatearPorcentajeCorto(porcentajeMermaEstimada);
    }

    if (mermaRealResumen) {
        mermaRealResumen.textContent =
            `Real: ${formatearCantidadCorta(mermaMostrada)} kg`;
    }

    if (diferenciaBalance) {
        diferenciaBalance.textContent = formatearCantidad(diferencia);
    }

    if (validationBox) {
        validationBox.classList.remove("balance-ok", "balance-pending");
    }

    if (!productoOrigenSeleccionado) {
        if (estadoBalance) {
            estadoBalance.textContent = "Incompleto";
        }

        resultado.textContent =
            "Selecciona un producto de origen.";
        return;
    }

    if (totalResultados <= 0) {
        if (validationBox) {
            validationBox.classList.add("balance-pending");
        }

        if (estadoBalance) {
            estadoBalance.textContent = "Pendiente";
        }

        resultado.textContent =
            "Captura la cantidad en productos resultantes.";
        return;
    }

    if (
        porcentajeEsperado !== null &&
        (
            !Number.isFinite(porcentajeEsperado) ||
            porcentajeEsperado < 0 ||
            porcentajeEsperado > 100
        )
    ) {
        if (validationBox) {
            validationBox.classList.add("balance-pending");
        }

        if (estadoBalance) {
            estadoBalance.textContent = "Revisar";
        }

        resultado.textContent =
            "El porcentaje permitido debe estar entre 0 y 100.";
        return;
    }

    if (porcentajeEsperado === null) {
        if (validationBox) {
            validationBox.classList.add("balance-ok");
        }

        if (estadoBalance) {
            estadoBalance.textContent = "Listo";
        }

        if (productoYaTransformadoSeleccionado) {
            resultado.textContent =
                "Listo para registrar como producto final. " +
                `Salida calculada: ${formatearKg(cantidadOrigen)}.`;
            return;
        }

        resultado.textContent =
            `Listo para registrar. Salida calculada: ` +
            `${formatearKg(cantidadOrigen)}.`;
        return;
    }

    const diferenciaPorcentual = porcentajeMermaReal - porcentajeEsperado;

    if (diferenciaPorcentual <= 0.0001) {
        if (validationBox) {
            validationBox.classList.add("balance-ok");
        }

        if (estadoBalance) {
            estadoBalance.textContent = "Correcto";
        }

        resultado.textContent =
            `Listo para registrar. Salida calculada: ` +
            `${formatearKg(cantidadOrigen)}.`;
        return;
    }

    if (validationBox) {
        validationBox.classList.add("balance-pending");
    }

    if (estadoBalance) {
        estadoBalance.textContent = "Revisar";
    }

    resultado.textContent =
        `Perdida calculada ${formatearPorcentaje(porcentajeMermaReal)}%, ` +
        `permitido ${formatearPorcentaje(porcentajeEsperado)}%. ` +
        `Se paso ${formatearPorcentaje(diferenciaPorcentual)} puntos.`;
}


function obtenerMensajeValidacionTransformacion(datos) {
    const cantidadOrigen = Number(datos.cantidad_origen || 0);
    const pesoMerma = Number(datos.peso_merma || 0);
    const esProductoFinal =
        datos.tipo_transformacion === TIPO_PRODUCTO_FINAL ||
        datos.producto_ya_transformado;
    const porcentajeMermaEsperado =
        datos.porcentaje_merma_esperado === null
            ? null
            : Number(datos.porcentaje_merma_esperado);
    const productos = datos.productos_resultantes;
    const componentes = datos.componentes_formula || [];
    const totalResultados = productos.reduce(
        function (total, producto) {
            return total + Number(producto.cantidad || 0);
        },
        0
    );
    const idsProductos = productos
        .map(function (producto) {
            return producto.producto_id;
        })
        .filter(Boolean);

    if (!datos.producto_origen_id) {
        return "Selecciona un producto de origen desde Productos.";
    }

    if (cantidadOrigen <= 0) {
        return "Captura cantidad en productos resultantes.";
    }

    if (pesoMerma < 0) {
        return "La merma no puede ser negativa.";
    }

    if (productos.length === 0) {
        return "Agrega al menos un producto resultante.";
    }

    if (
        productos.some(function (producto) {
            return !producto.producto_id || Number(producto.cantidad) <= 0;
        })
    ) {
        return "Completa producto y cantidad en cada resultante.";
    }

    if (
        estaUsandoFormula() &&
        (
            !datos.producto_seleccionado_id ||
            componentes.length === 0 ||
            componentes.some(function (componente) {
                return (
                    !componente.producto_id ||
                    Number(componente.cantidad) <= 0
                );
            })
        )
    ) {
        return "La formula no tiene todos sus componentes completos.";
    }

    if (esProductoFinal) {
        if (productos.length !== 1) {
            return "El producto final solo debe tener una salida.";
        }

        if (productos[0].producto_id !== datos.producto_origen_id) {
            return "El producto final debe salir con el mismo producto.";
        }

    }

    if (new Set(idsProductos).size !== idsProductos.length) {
        return "No repitas productos resultantes en la misma transformacion.";
    }

    if (totalResultados > cantidadOrigen) {
        return "Los productos resultantes no pueden superar la cantidad de origen.";
    }

    if (
        porcentajeMermaEsperado !== null &&
        (
            !Number.isFinite(porcentajeMermaEsperado) ||
            porcentajeMermaEsperado < 0 ||
            porcentajeMermaEsperado > 100
        )
    ) {
        return "El porcentaje permitido debe estar entre 0 y 100.";
    }

    return "";
}


async function registrarTransformacion() {
    if (!sesionActual) {
        const sesion = await cargarSesionActual();

        if (!sesion) {
            return;
        }
    }

    const productoOrigenInput =
        document.getElementById("productoOrigenId");
    const cantidadOrigenInput =
        document.getElementById("cantidadOrigen");
    const pesoMermaInput = document.getElementById("pesoMerma");
    const porcentajeMermaEsperadoInput = document.getElementById(
        "porcentajeMermaEsperado"
    );
    const observacionesMermaInput = document.getElementById(
        "observacionesMerma"
    );
    const contenedor = document.getElementById(
        "resultadoTransformacion"
    );
    const botonRegistrar = document.getElementById(
        "botonRegistrarTransformacion"
    );

    if (
        !productoOrigenInput ||
        !cantidadOrigenInput ||
        !pesoMermaInput ||
        !porcentajeMermaEsperadoInput ||
        !observacionesMermaInput ||
        !contenedor
    ) {
        return;
    }

    actualizarBalance();

    const productosResultantes = obtenerProductosResultantes();

    const datos = {
        id_operacion: idOperacionActual,
        producto_seleccionado_id:
            productoSeleccionadoOriginal?.id || null,
        producto_origen_id: Number(productoOrigenInput.value),
        cantidad_origen: cantidadOrigenInput.value,
        productos_resultantes: productosResultantes,
        componentes_formula: obtenerComponentesFormula(),
        tipo_transformacion: obtenerTipoTransformacionSeleccionado(),
        producto_ya_transformado: productoYaTransformadoSeleccionado,
        peso_merma: pesoMermaInput.value || "0",
        porcentaje_merma_esperado:
            porcentajeMermaEsperadoInput.value || null,
        observaciones_merma:
            observacionesMermaInput.value.trim() || null
    };

    const mensajeValidacion = obtenerMensajeValidacionTransformacion(datos);

    if (mensajeValidacion) {
        contenedor.className = "error-card";
        contenedor.textContent = mensajeValidacion;
        return;
    }

    contenedor.className = "result-container";
    contenedor.textContent = "Validando transformación...";

    if (botonRegistrar) {
        botonRegistrar.disabled = true;
        botonRegistrar.textContent = "Registrando...";
    }

    try {
        const respuesta = await fetch("/transformaciones/", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(datos)
        });

        const resultado = await respuesta.json();

        if (!respuesta.ok) {
            const detalle = Array.isArray(resultado.detail)
                ? resultado.detail[0]?.msg
                : resultado.detail;

            throw new Error(
                detalle || "No se pudo registrar la transformación"
            );
        }

        contenedor.className = "success-card";
        const registro = resultado.registro || {};
        const movimientos = textoMovimientosErp(registro);
        contenedor.textContent = movimientos === "-"
            ? resultado.mensaje
            : `${resultado.mensaje}. Movimientos: ${movimientos}.`;

        idOperacionActual = crearIdOperacion();

        await cargarHistorialTransformaciones();
    } catch (error) {
        contenedor.className = "error-card";
        contenedor.textContent = error.message;
    } finally {
        if (botonRegistrar) {
            botonRegistrar.disabled = false;
            botonRegistrar.textContent = "Registrar transformación";
        }
    }
}


document.addEventListener("DOMContentLoaded", function () {
    const dashboard = document.getElementById("dashboardPage");

    if (dashboard) {
        cargarSesionActual();
    }

    const usuarioInput = document.getElementById("usuario");
    const passwordInput = document.getElementById("password");

    [usuarioInput, passwordInput].forEach(function (input) {
        if (!input) {
            return;
        }

        input.addEventListener("keydown", function (evento) {
            if (evento.key === "Enter") {
                iniciarSesion();
            }
        });
    });

    const busquedaProducto =
        document.getElementById("busquedaProducto");

    if (busquedaProducto) {
        busquedaProducto.addEventListener(
            "keydown",
            function (evento) {
                if (evento.key === "Enter") {
                    buscarProductos();
                }
            }
        );
    }

    const cantidadOrigen = document.getElementById("cantidadOrigen");
    const porcentajeMermaEsperado = document.getElementById(
        "porcentajeMermaEsperado"
    );
    const tipoTransformacion = document.getElementById("tipoTransformacion");

    if (cantidadOrigen) {
        cantidadOrigen.value = "0";
    }

    if (porcentajeMermaEsperado) {
        porcentajeMermaEsperado.addEventListener(
            "input",
            actualizarBalance
        );
    }

    if (tipoTransformacion) {
        tipoTransformacion.addEventListener(
            "change",
            renderizarProductosResultantes
        );
    }

    const productosResultantes =
        document.getElementById("productosResultantes");

    if (productosResultantes) {
        productosResultantes.textContent =
            "Selecciona un producto desde la tabla de productos.";
    }

    actualizarBalance();



});
