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

        sessionStorage.setItem("usuario", datos.usuario);
        sessionStorage.setItem("user_id", String(datos.user_id));
        sessionStorage.setItem(
            "user_group_id",
            String(datos.user_group_id)
        );

        window.location.href = "/dashboard";
    } catch (error) {
        mensajeError.textContent =
            "No se pudo conectar con el servidor";
        console.error(error);
    }
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


function cerrarSesion() {
    sessionStorage.clear();
    window.location.href = "/";
}


const PRODUCTOS_POR_PAGINA = 10;
const CANTIDAD_ORIGEN_INICIAL = "1";
let productosBusquedaActual = "";
let productosPaginaActual = 1;
let productoOrigenSeleccionado = null;
let productosResultantesDisponibles = [];
let productoYaTransformadoSeleccionado = false;


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

    const respuesta = await fetch(`/productos/?${parametros}`);
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


function formatearPorcentaje(valor) {
    const numero = Number(valor || 0);

    if (!Number.isFinite(numero)) {
        return "0.00";
    }

    return numero.toFixed(2);
}


function obtenerProductoDisponible(productoId) {
    return productosResultantesDisponibles.find(function (producto) {
        return Number(producto.id) === Number(productoId);
    });
}


function cantidadOrigenActual() {
    const cantidadOrigenInput = document.getElementById("cantidadOrigen");
    return Number(cantidadOrigenInput?.value || 0);
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


function actualizarTarjetaOrigen(producto) {
    const tarjeta = document.getElementById("tarjetaOrigen");
    const nombre = document.getElementById("origenNombre");
    const clave = document.getElementById("origenClave");
    const categoria = document.getElementById("origenCategoria");
    const unidad = document.getElementById("origenUnidad");
    const existencia = document.getElementById("origenExistencia");
    const unidadCantidad = document.getElementById("unidadCantidadOrigen");

    if (!tarjeta || !nombre || !clave || !categoria || !unidad) {
        return;
    }

    tarjeta.classList.remove("origen-card-empty");
    nombre.textContent = producto.nombre || "-";
    clave.textContent = producto.clave || "-";
    categoria.textContent = producto.categoria || "-";
    unidad.textContent = producto.unidad || "-";

    if (existencia) {
        existencia.textContent = formatearCantidad(producto.existencia);
    }

    if (unidadCantidad) {
        unidadCantidad.textContent = producto.unidad
            ? `(${producto.unidad})`
            : "";
    }
}


async function consultarProductosResultantes(productoId) {
    const respuesta = await fetch(`/productos/${productoId}/resultantes`);
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
    productosResultantesDisponibles = [];
    contenedor.replaceChildren();
    contenedor.textContent = "Cargando productos resultantes...";

    try {
        const datos = await consultarProductosResultantes(productoId);
        productosResultantesDisponibles = datos.productos || [];
        contenedor.replaceChildren();

        if (productosResultantesDisponibles.length === 0) {
            productoYaTransformadoSeleccionado = true;
            productosResultantesDisponibles = [
                {
                    ...productoOrigenSeleccionado,
                    cantidad_origen: 1,
                    cantidad_resultante: 1
                }
            ];

            agregarProductoResultante();

            const aviso = document.createElement("div");
            aviso.className = "aviso-producto-transformado";
            aviso.textContent =
                "Este producto ya esta transformado; se registrara con salida igual a la entrada.";
            contenedor.prepend(aviso);
            return;
        }

        agregarProductoResultante();
    } catch (error) {
        contenedor.textContent = error.message;
    }
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
    cantidadOrigenInput.value = CANTIDAD_ORIGEN_INICIAL;
    actualizarTarjetaOrigen(producto);

    if (resultadoOrigen) {
        resultadoOrigen.className = "seleccion-origen";
        resultadoOrigen.textContent =
            `Producto origen seleccionado: ${producto.nombre}`;
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
                <th>Cantidad sugerida</th>
                <th>Cantidad capturada</th>
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


function actualizarSugeridoFila(fila) {
    const select = fila.querySelector(".producto-resultante-id");
    const cantidad = fila.querySelector(".producto-resultante-cantidad");
    const sugerida = fila.querySelector(".cantidad-sugerida");
    const producto = obtenerProductoDisponible(select.value);
    const cantidadSugerida = calcularCantidadSugerida(producto);

    if (sugerida) {
        sugerida.textContent = formatearCantidad(cantidadSugerida);
    }

    if (cantidad && cantidad.dataset.automatica === "1") {
        cantidad.value = cantidadSugerida
            ? formatearCantidad(cantidadSugerida)
            : "";
    }
}


function actualizarCantidadesSugeridas() {
    document.querySelectorAll(".producto-resultante").forEach(
        actualizarSugeridoFila
    );
}


function agregarProductoResultante() {
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
                "Este producto ya se registra como transformado.";
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
    const celdaSugerida = document.createElement("td");
    const celdaCantidad = document.createElement("td");
    const celdaAcciones = document.createElement("td");
    const cantidad = document.createElement("input");
    const eliminar = document.createElement("button");

    cantidad.type = "number";
    cantidad.min = "0.001";
    cantidad.step = "0.001";
    cantidad.className = "producto-resultante-cantidad";
    cantidad.dataset.automatica = "1";
    celdaUnidad.textContent = "-";
    celdaSugerida.className = "cantidad-sugerida";
    celdaSugerida.textContent = "0.000";

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
            celdaSugerida.textContent = "0.000";
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
        cantidad.dataset.automatica = "1";
        actualizarSugeridoFila(fila);
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
        celdaSugerida,
        celdaCantidad,
        celdaAcciones
    );

    if (productoYaTransformadoSeleccionado) {
        productoId.value = String(productoOrigenSeleccionado.id);
        productoId.disabled = true;
        cantidad.readOnly = true;
        cantidad.dataset.automatica = "1";
        eliminar.disabled = true;
        eliminar.textContent = "Fijo";

        const producto = obtenerProductoDisponible(productoId.value);
        celdaUnidad.textContent = producto?.unidad || "-";
        actualizarSugeridoFila(fila);
    }

    cuerpo.appendChild(fila);
    actualizarOpcionesResultantes();
}


function obtenerProductosResultantes() {
    return Array.from(
        document.querySelectorAll(".producto-resultante")
    ).map(function (fila) {
        return {
            producto_id: Number(
                fila.querySelector(".producto-resultante-id").value
            ),
            cantidad: fila.querySelector(
                ".producto-resultante-cantidad"
            ).value
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
            `(${formatearCantidad(item.cantidad)})`
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
            registro.producto_ya_transformado
                ? "Ya transformado"
                : "Proceso normal",
            registro.fecha,
            registro.usuario || "-",
            textoProductoRegistro(registro.producto_origen),
            formatearCantidad(registro.cantidad_origen),
            formatearCantidad(registro.total_salida),
            (
                `${formatearCantidad(registro.peso_merma)} ` +
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
        const respuesta = await fetch("/transformaciones/");
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
    const validationBox = document.querySelector(".validation-box");
    const estadoBalance = document.getElementById("estadoBalance");
    const totalOrigen = document.getElementById("totalOrigen");
    const totalResultantes = document.getElementById("totalResultantes");
    const totalMerma = document.getElementById("totalMerma");
    const porcentajeMermaResumen = document.getElementById(
        "porcentajeMermaResumen"
    );
    const diferenciaBalance = document.getElementById("diferenciaBalance");

    if (!cantidadOrigenInput || !pesoMermaInput || !resultado) {
        return;
    }

    const cantidadOrigen = Number(cantidadOrigenInput.value || 0);
    const totalResultados = obtenerProductosResultantes().reduce(
        function (total, producto) {
            return total + Number(producto.cantidad || 0);
        },
        0
    );
    const mermaCalculada = totalResultados > 0
        ? cantidadOrigen - totalResultados
        : 0;
    const mermaMostrada = Math.max(mermaCalculada, 0);
    const diferencia = cantidadOrigen - totalResultados - mermaMostrada;
    const porcentajeMermaReal = cantidadOrigen > 0
        ? (mermaMostrada / cantidadOrigen) * 100
        : 0;
    const porcentajeEsperadoTexto =
        porcentajeMermaEsperadoInput?.value.trim() || "";
    const porcentajeEsperado = porcentajeEsperadoTexto
        ? Number(porcentajeEsperadoTexto)
        : null;

    pesoMermaInput.value = formatearCantidad(mermaMostrada);

    if (porcentajeMermaRealInput) {
        porcentajeMermaRealInput.value =
            formatearPorcentaje(porcentajeMermaReal);
    }

    if (totalOrigen) {
        totalOrigen.textContent = formatearCantidad(cantidadOrigen);
    }

    if (totalResultantes) {
        totalResultantes.textContent = formatearCantidad(totalResultados);
    }

    if (totalMerma) {
        totalMerma.textContent = formatearCantidad(mermaMostrada);
    }

    if (porcentajeMermaResumen) {
        porcentajeMermaResumen.textContent =
            `${formatearPorcentaje(porcentajeMermaReal)}%`;
    }

    if (diferenciaBalance) {
        diferenciaBalance.textContent = formatearCantidad(diferencia);
    }

    if (validationBox) {
        validationBox.classList.remove("balance-ok", "balance-pending");
    }

    if (!productoOrigenSeleccionado || cantidadOrigen <= 0) {
        if (estadoBalance) {
            estadoBalance.textContent = "Incompleto";
        }

        resultado.textContent =
            "Selecciona un producto de origen y captura una cantidad mayor a cero.";
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
            "Agrega por lo menos un producto resultante.";
        return;
    }

    if (mermaCalculada < -0.0001) {
        if (validationBox) {
            validationBox.classList.add("balance-pending");
        }

        if (estadoBalance) {
            estadoBalance.textContent = "Revisar";
        }

        resultado.textContent =
            "Los productos resultantes superan la cantidad de origen.";
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
            validationBox.classList.add("balance-pending");
        }

        if (estadoBalance) {
            estadoBalance.textContent = "Listo";
        }

        resultado.textContent =
            `Listo para registrar. Merma calculada: ` +
            `${formatearCantidad(mermaMostrada)} ` +
            `(${formatearPorcentaje(porcentajeMermaReal)}%).`;
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
            `Perdida calculada ${formatearPorcentaje(porcentajeMermaReal)}%, ` +
            `permitido ${formatearPorcentaje(porcentajeEsperado)}%.`;
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
        return "La cantidad de origen debe ser mayor a cero.";
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
        usuario_id: Number(sessionStorage.getItem("user_id")) || null,
        usuario_nombre: sessionStorage.getItem("usuario") || null,
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
    const usuarioActivo = document.getElementById("usuarioActivo");

    if (usuarioActivo) {
        usuarioActivo.textContent =
            sessionStorage.getItem("usuario") || "Usuario";
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

    if (cantidadOrigen && !cantidadOrigen.value) {
        cantidadOrigen.value = CANTIDAD_ORIGEN_INICIAL;
    }

    if (cantidadOrigen) {
        cantidadOrigen.addEventListener("input", function () {
            actualizarCantidadesSugeridas();
            actualizarBalance();
        });
    }

    if (porcentajeMermaEsperado) {
        porcentajeMermaEsperado.addEventListener(
            "input",
            actualizarBalance
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
