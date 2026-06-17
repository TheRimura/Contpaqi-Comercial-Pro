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
const TIPO_RECETA_CONFIGURADA = "receta_configurada";
const TIPO_PRODUCTO_FINAL = "producto_final";
let sesionActual = null;
let productosBusquedaActual = "";
let productosPaginaActual = 1;
let productoOrigenSeleccionado = null;
let productosResultantesDisponibles = [];
let productosRecetaDisponibles = [];
let productoTieneRecetaConfigurada = false;
let productoYaTransformadoSeleccionado = false;
let tipoRelacionRecetaConfigurada = null;


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


function crearControlesPaginacion(resultado) {
    const controles = document.createElement("div");
    controles.className = "paginacion";

    const resumen = document.createElement("span");
    resumen.textContent =
        `Página ${resultado.pagina} de ${resultado.total_paginas} ` +
        `(${resultado.total} productos)`;

    const anterior = document.createElement("button");
    anterior.type = "button";
    anterior.textContent = "Anterior";
    anterior.disabled = resultado.pagina <= 1;
    anterior.addEventListener("click", function () {
        buscarProductos(resultado.pagina - 1);
    });

    const siguiente = document.createElement("button");
    siguiente.type = "button";
    siguiente.textContent = "Siguiente";
    siguiente.disabled = resultado.pagina >= resultado.total_paginas;
    siguiente.addEventListener("click", function () {
        buscarProductos(resultado.pagina + 1);
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
        contenedor.appendChild(crearControlesPaginacion(resultado));
    } catch (error) {
        contenedor.textContent = error.message;
    }
}


function describirProducto(producto) {
    return `${producto.nombre} | ${producto.clave} | ID ${producto.id}`;
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


function aplicarMermaEstimadaProducto(producto) {
    const porcentajeMermaEsperado = document.getElementById(
        "porcentajeMermaEsperado"
    );

    const porcentaje = Number(producto?.merma_estimada?.porcentaje || 0);

    if (porcentajeMermaEsperado) {
        porcentajeMermaEsperado.value = porcentaje
            ? formatearPorcentaje(porcentaje)
            : "";
    }
}


function obtenerProductoDisponible(productoId) {
    return productosResultantesDisponibles.find(function (producto) {
        return Number(producto.id) === Number(productoId);
    });
}


function cantidadOrigenActual() {
    const cantidadOrigenInput = document.getElementById("cantidadOrigen");
    return leerCantidadKg(cantidadOrigenInput?.value || 0);
}


function calcularCantidadSugerida(producto) {
    const cantidadOrigen = cantidadOrigenActual();
    const baseOrigen = Number(producto?.cantidad_origen || 1);
    const baseResultante = Number(producto?.cantidad_resultante || 0);

    if (!cantidadOrigen || !baseOrigen || !baseResultante) {
        return 0;
    }

    return (cantidadOrigen * baseResultante) / baseOrigen;
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

    if (!productoBase) {
        return;
    }

    actualizarTarjetaOrigen(productoBase);

    if (resultadoOrigen) {
        resultadoOrigen.className = "seleccion-origen";
        resultadoOrigen.textContent =
            `Categoria de origen: ${productoBase.categoria || "-"}`;
    }
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
                "Se cargaran los componentes en kilos de la formula configurada.";
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
        configurarEncabezadoResultantes("Producto final", false);
        productosResultantesDisponibles = [
            {
                ...productoOrigenSeleccionado,
                cantidad_origen: 1,
                cantidad_resultante: 1
            }
        ];

        agregarProductoResultante();
        contenedor.prepend(crearAvisoProductoFinal());
        actualizarBalance();
        return;
    }

    productosResultantesDisponibles = productosRecetaDisponibles;

    if (productosResultantesDisponibles.length === 0) {
        mostrarMensajeResultantes(
            "Este producto no tiene receta configurada."
        );
        actualizarBalance();
        return;
    }

    if (tipoRelacionRecetaConfigurada === "formula_lista_para_cocinar") {
        const productosParaBalance = productosResultantesDisponibles.filter(
            function (producto) {
                return producto.participa_balance !== false;
            }
        );
        const productosExcluidos = productosResultantesDisponibles.filter(
            function (producto) {
                return producto.participa_balance === false;
            }
        );

        configurarEncabezadoResultantes("Componentes de formula", false);
        renderizarFormula(productosParaBalance, productosExcluidos);
        actualizarBalance();
        return;
    }

    agregarProductoResultante();
    actualizarBalance();
}


async function seleccionarProductoOrigen(producto) {
    const busquedaInput = document.getElementById("buscarOrigen");
    const productoIdInput = document.getElementById("productoOrigenId");
    const cantidadOrigenInput = document.getElementById("cantidadOrigen");
    const resultadoOrigen = document.getElementById("resultadoOrigen");

    if (!busquedaInput || !productoIdInput || !cantidadOrigenInput) {
        return;
    }

    productoOrigenSeleccionado = producto;
    productoIdInput.value = producto.id;
    busquedaInput.value = describirProducto(producto);
    busquedaInput.readOnly = true;
    busquedaInput.classList.add("input-bloqueado");
    cantidadOrigenInput.value = "0";
    actualizarTarjetaOrigen(producto);
    aplicarMermaEstimadaProducto(producto);

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


function crearOpcionProducto(producto, alSeleccionar) {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "producto-opcion";
    boton.textContent =
        `${producto.nombre} | ${producto.clave} | ID ${producto.id}`;

    boton.addEventListener("click", function () {
        alSeleccionar(producto);
    });

    return boton;
}


async function buscarProductoOrigen() {
    const busquedaInput = document.getElementById("buscarOrigen");
    const productoIdInput = document.getElementById("productoOrigenId");
    const contenedor = document.getElementById("resultadoOrigen");

    if (!busquedaInput || !productoIdInput || !contenedor) {
        return;
    }

    const termino = busquedaInput.value.trim();

    if (termino.length < 2) {
        contenedor.textContent =
            "Escribe al menos dos caracteres para buscar.";
        return;
    }

    contenedor.textContent = "Buscando...";

    try {
        const resultado = await consultarProductos(termino, 1, 10);
        const productos = resultado.productos;
        contenedor.replaceChildren();

        if (productos.length === 0) {
            contenedor.textContent = "No se encontraron productos.";
            return;
        }

        productos.forEach(function (producto) {
            const opcion = crearOpcionProducto(
                producto,
                function (seleccionado) {
                    seleccionarProductoOrigen(seleccionado);
                }
            );

            contenedor.appendChild(opcion);
        });
    } catch (error) {
        contenedor.textContent = error.message;
    }
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


function crearResumenFormulaAnterior(productosBalance, productosExcluidos) {
    const resumen = document.createElement("div");
    const texto = document.createElement("div");
    const etiquetas = document.createElement("div");

    resumen.className = "formula-resumen";
    texto.innerHTML = `
        <strong>Formula configurada</strong>
        <span>Componentes que participan en el balance de kilos.</span>
    `;
    etiquetas.className = "formula-etiquetas";

    const etiquetaKilos = document.createElement("span");
    etiquetaKilos.textContent = `${productosBalance.length} en kilos`;
    etiquetas.appendChild(etiquetaKilos);

    if (productosExcluidos.length > 0) {
        const etiquetaExcluidos = document.createElement("span");
        etiquetaExcluidos.textContent =
            `${productosExcluidos.length} fuera del balance`;
        etiquetas.appendChild(etiquetaExcluidos);
    }

    resumen.append(texto, etiquetas);
    return resumen;
}


function agregarComponenteFormulaAnterior(producto) {
    const lista = document.getElementById("listaFormula");

    if (!lista) {
        return;
    }

    const fila = document.createElement("div");
    const productoId = document.createElement("input");
    const info = document.createElement("div");
    const cantidad = document.createElement("input");
    const cantidadBase = cantidadBaseProducto(producto);

    fila.className = "producto-resultante formula-item";
    productoId.type = "hidden";
    productoId.className = "producto-resultante-id";
    productoId.value = String(producto.id);

    info.className = "formula-info";
    info.innerHTML = `
        <strong>${producto.nombre}</strong>
        <span>${producto.clave || "Sin clave"} · ${producto.categoria || "-"}</span>
    `;

    cantidad.type = "text";
    cantidad.inputMode = "decimal";
    cantidad.placeholder = "Cantidad";
    cantidad.className = "producto-resultante-cantidad formula-cantidad";
    cantidad.value = formatearCantidadCaptura(cantidadBase);

    cantidad.addEventListener("input", actualizarBalance);

    fila.append(productoId, info, cantidad);
    lista.appendChild(fila);
}


function renderizarFormulaAnterior(productosBalance, productosExcluidos) {
    const contenedor = document.getElementById("productosResultantes");
    const lista = document.createElement("div");

    if (!contenedor) {
        return;
    }

    contenedor.replaceChildren();
    contenedor.classList.add("formula-resultantes");
    lista.id = "listaFormula";
    lista.className = "formula-lista";

    contenedor.append(
        crearResumenFormula(productosBalance, productosExcluidos),
        lista
    );

    productosBalance.forEach(function (producto) {
        agregarComponenteFormula(producto);
    });
}


function crearResumenFormula(productoBase, ingredientes, productosExcluidos) {
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

    if (productosExcluidos.length > 0) {
        const etiquetaExcluidos = document.createElement("span");
        etiquetaExcluidos.textContent =
            `${productosExcluidos.length} fuera del balance`;
        etiquetas.appendChild(etiquetaExcluidos);
    }

    resumen.append(texto, etiquetas);
    return resumen;
}


function crearCampoCantidadFormula(producto, esBase) {
    const fila = document.createElement("div");
    const productoId = document.createElement("input");
    const info = document.createElement("div");
    const cantidad = document.createElement("input");
    const cantidadBase = cantidadBaseProducto(producto);

    fila.className = esBase
        ? "producto-resultante formula-base"
        : "producto-resultante formula-item";
    productoId.type = "hidden";
    productoId.className = "producto-resultante-id";
    productoId.value = String(producto.id);

    info.className = "formula-info";
    info.innerHTML = `
        <strong>${producto.nombre}</strong>
        <span>${producto.clave || "Sin clave"} - ${producto.categoria || "-"}</span>
    `;

    cantidad.type = "text";
    cantidad.inputMode = "decimal";
    cantidad.placeholder = "Cantidad";
    cantidad.className = "producto-resultante-cantidad formula-cantidad";
    cantidad.value = formatearCantidadCaptura(cantidadBase);
    cantidad.dataset.cantidadBase = String(cantidadBase);

    if (esBase) {
        cantidad.id = "formulaProductoBaseCantidad";
        cantidad.addEventListener("input", ajustarFormulaDesdeProductoBase);
    } else {
        cantidad.readOnly = true;
        cantidad.tabIndex = -1;
    }

    fila.append(productoId, info, cantidad);
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
        .querySelectorAll(".formula-item .producto-resultante-cantidad")
        .forEach(function (input) {
            const cantidadBase = Number(input.dataset.cantidadBase || 0);

            if (cantidadBase > 0) {
                input.value = formatearCantidadFormula(
                    cantidadBase * factor
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


function renderizarFormula(productosBalance, productosExcluidos) {
    const contenedor = document.getElementById("productosResultantes");
    const lista = document.createElement("div");
    const formula = separarFormula(productosBalance);

    if (!contenedor) {
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
            formula.ingredientes,
            productosExcluidos
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
        celdaUnidad.textContent = producto?.unidad || "-";

        if (cantidad.dataset.automatica === "1") {
            const cantidadBase = cantidadBaseProducto(producto);
            cantidad.value = cantidadBase > 0
                ? formatearCantidadCaptura(cantidadBase)
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
        celdaUnidad.textContent = productoPreseleccionado.unidad || "-";

        const cantidadBase = cantidadBaseProducto(productoPreseleccionado);
        cantidad.value = cantidadBase > 0
            ? formatearCantidadCaptura(cantidadBase)
            : "";
    }

    if (productoYaTransformadoSeleccionado) {
        productoId.value = String(productoOrigenSeleccionado.id);
        productoId.disabled = true;
        cantidad.dataset.automatica = "1";
        eliminar.disabled = true;
        eliminar.textContent = "Fijo";

        const producto = obtenerProductoDisponible(productoId.value);
        celdaUnidad.textContent = producto?.unidad || "-";
    }

    cuerpo.appendChild(fila);
    actualizarOpcionesResultantes();
}


function obtenerProductosResultantes() {
    return Array.from(
        document.querySelectorAll(".producto-resultante")
    ).map(function (fila) {
        const cantidad = fila.querySelector(
            ".producto-resultante-cantidad"
        ).value;

        return {
            producto_id: Number(
                fila.querySelector(".producto-resultante-id").value
            ),
            cantidad: cantidadApi(cantidad)
        };
    });
}


function textoProductoRegistro(producto) {
    if (!producto) {
        return "Producto no encontrado";
    }

    return `${producto.nombre} | ${producto.clave}`;
}


function resumenProductosResultantes(registro) {
    const productos = registro.productos_resultantes || [];

    if (productos.length === 0) {
        return "-";
    }

    return productos.map(function (item) {
        return (
            `${textoProductoRegistro(item.producto)} ` +
            `(${formatearKg(item.cantidad)})`
        );
    }).join(", ");
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
            <th>Entrada</th>
            <th>Salida</th>
            <th>Merma</th>
            <th>Resultantes</th>
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
            formatearKg(registro.total_salida),
            (
                `${formatearKg(registro.peso_merma)} ` +
                `(${formatearPorcentaje(registro.porcentaje_merma_real)}%)`
            ),
            resumenProductosResultantes(registro)
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


async function cargarHistorialTransformaciones() {
    const contenedor = document.getElementById("tablaRegistros");

    if (!contenedor) {
        return;
    }

    contenedor.textContent = "Cargando registros...";

    try {
        const respuesta = await fetch("/transformaciones/", {
            credentials: "same-origin"
        });
        const datos = await respuesta.json();

        if (!respuesta.ok) {
            throw new Error(
                datos.detail || "No fue posible consultar los registros"
            );
        }

        const registros = datos.registros || [];
        contenedor.replaceChildren();

        if (registros.length === 0) {
            contenedor.textContent =
                "Aun no hay transformaciones registradas.";
            return;
        }

        contenedor.appendChild(crearTablaRegistros(registros));
    } catch (error) {
        contenedor.textContent = error.message;
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

    const totalResultados = obtenerProductosResultantes().reduce(
        function (total, producto) {
            return total + leerCantidadKg(producto.cantidad);
        },
        0
    );
    const porcentajeMermaEstimada = porcentajeMermaEstimadaProducto();
    const cantidadOrigen = calcularEntradaEstimada(
        totalResultados,
        porcentajeMermaEstimada
    );
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
                `Entrada estimada: ${formatearKg(cantidadOrigen)}.`;
            return;
        }

        resultado.textContent =
            `Listo para registrar. Entrada estimada: ` +
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
            `Listo para registrar. Entrada estimada: ` +
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
        producto_origen_id: Number(productoOrigenInput.value),
        cantidad_origen: cantidadOrigenInput.value,
        productos_resultantes: productosResultantes,
        usuario_id: sesionActual?.user_id || null,
        usuario_nombre: sesionActual?.usuario || null,
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
        contenedor.textContent =
            resultado.folio
                ? `${resultado.mensaje}. Folio ${resultado.folio}.`
                : resultado.mensaje;

        cargarHistorialTransformaciones();
    } catch (error) {
        contenedor.className = "error-card";
        contenedor.textContent = error.message;
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

    const buscarOrigen = document.getElementById("buscarOrigen");

    if (buscarOrigen) {
        buscarOrigen.addEventListener("keydown", function (evento) {
            if (evento.key === "Enter") {
                evento.preventDefault();
                buscarProductoOrigen();
            }
        });
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
