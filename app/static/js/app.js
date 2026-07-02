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

        window.location.replace("/dashboard");
    } catch (error) {
        mensajeError.textContent =
            "No se pudo conectar con el servidor";
        console.error(error);
    }
}


async function cargarSesionActual() {
    const respuesta = await fetch("/login/sesion", {
        credentials: "same-origin",
        cache: "no-store"
    });

    if (!respuesta.ok) {
        window.location.replace("/");
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


async function redirigirSiSesionActiva() {
    try {
        const respuesta = await fetch("/login/sesion", {
            credentials: "same-origin",
            cache: "no-store"
        });

        if (respuesta.ok) {
            window.location.replace("/dashboard");
        }
    } catch (error) {
        console.error(error);
    }
}


function prepararConfiguracionesTransformacion() {
    sincronizarDraftConfiguracionDesdeContexto();
    actualizarEstadoFormularioConfiguracion();
    renderizarEditorComponentesConfiguracion();
    renderizarEditorResultantesConfiguracion();
    actualizarResumenConfiguracion();
    cargarConfiguracionesTransformacion(configuracionesPaginaActual);
}


function abrirModalConfiguraciones() {
    const modal = document.getElementById("modalConfiguraciones");

    if (!modal) {
        return;
    }

    modal.classList.remove("hidden");
    document.body.classList.add("modal-open");
    prepararConfiguracionesTransformacion();
}


function cerrarModalConfiguraciones() {
    const modal = document.getElementById("modalConfiguraciones");

    if (!modal) {
        return;
    }

    modal.classList.add("hidden");
    document.body.classList.remove("modal-open");
}


const MOVIMIENTOS_MODULO = {
    transformacion: {
        etiqueta: "Transformacion",
        titulo: "Producto base y resultantes",
        descripcion: "Captura salida, entrada y merma en una sola operacion.",
        accion: "Nueva transformacion",
        seccion: "transformacion"
    },
    salida: {
        etiqueta: "Salida",
        titulo: "Producto padre / inventario",
        descripcion: "Selecciona el producto que sale para iniciar el trabajo.",
        accion: "Abrir opciones de salida",
        seccion: "transformacion"
    },
    entrada: {
        etiqueta: "Entrada",
        titulo: "Producto resultante",
        descripcion: "Revisa o captura el producto que entra al inventario.",
        accion: "Capturar entrada",
        seccion: "transformacion"
    },
    merma: {
        etiqueta: "Merma",
        titulo: "Rendimiento y perdida",
        descripcion: "Valida el balance entre salida, entrada y merma.",
        accion: "Capturar merma",
        seccion: "transformacion"
    }
};

let movimientoModuloActual = "transformacion";


function obtenerMovimientoModulo(tipo) {
    return MOVIMIENTOS_MODULO[tipo] || MOVIMIENTOS_MODULO.transformacion;
}


function seleccionarMovimientoModulo(tipo) {
    const movimiento = obtenerMovimientoModulo(tipo);
    const etiqueta = document.getElementById("moduloMovimientoEtiqueta");
    const titulo = document.getElementById("moduloMovimientoTitulo");
    const descripcion = document.getElementById(
        "moduloMovimientoDescripcion"
    );
    const accionPrincipal = document.getElementById(
        "moduloAccionPrincipal"
    );

    movimientoModuloActual = MOVIMIENTOS_MODULO[tipo]
        ? tipo
        : "transformacion";

    document.querySelectorAll(".modulo-movimiento").forEach(
        function (boton) {
            boton.classList.toggle(
                "is-active",
                boton.dataset.movimiento === movimientoModuloActual
            );
        }
    );

    if (etiqueta) {
        etiqueta.textContent = movimiento.etiqueta;
    }

    if (titulo) {
        titulo.textContent = movimiento.titulo;
    }

    if (descripcion) {
        descripcion.textContent = movimiento.descripcion;
    }

    if (accionPrincipal) {
        accionPrincipal.textContent = movimiento.accion;
    }
}


function obtenerProductoTrabajoMovimiento() {
    return productoOrigenSeleccionado || productoSeleccionadoOriginal;
}


function mostrarEstadoMovimientoModulo(mensaje, tipo = "") {
    const estado = document.getElementById("estadoMovimientoModulo");

    if (!estado) {
        return;
    }

    estado.className = `movimiento-status ${tipo}`.trim();
    estado.textContent = mensaje;
}


function crearOpcionMovimientoModulo(opcion) {
    const boton = document.createElement("button");
    const titulo = document.createElement("strong");
    const descripcion = document.createElement("span");

    boton.type = "button";
    boton.className = "movimiento-opcion";
    boton.disabled = Boolean(opcion.deshabilitada);
    titulo.textContent = opcion.titulo;
    descripcion.textContent = opcion.descripcion;
    boton.append(titulo, descripcion);

    if (opcion.deshabilitada) {
        boton.title = opcion.motivo || "Opcion no disponible";
    } else {
        boton.addEventListener("click", opcion.accion);
    }

    return boton;
}


function abrirCapturaMovimiento(opciones = {}) {
    cerrarPanelMovimientoModulo();
    mostrarSeccion("transformacion");

    window.setTimeout(function () {
        if (opciones.abrirMerma) {
            const detalles = document.querySelector(".merma-opcional");

            if (detalles) {
                detalles.open = true;
            }
        }

        if (opciones.scrollSelector) {
            const destino = document.querySelector(opciones.scrollSelector);

            if (destino) {
                destino.scrollIntoView({
                    behavior: "smooth",
                    block: "center"
                });
            }
        }

        if (opciones.campoId) {
            const campo = document.getElementById(opciones.campoId);

            if (campo) {
                campo.focus();
            }
        }
    }, 0);
}


function abrirConfiguracionesDesdeMovimiento() {
    cerrarPanelMovimientoModulo();
    abrirModalConfiguraciones();
}


function verRegistrosDesdeMovimiento() {
    cerrarPanelMovimientoModulo();
    mostrarSeccion("registros");
}


function obtenerSalidaGuardada() {
    try {
        return JSON.parse(
            window.localStorage.getItem(STORAGE_SALIDA_MOVIMIENTO) || "null"
        );
    } catch (error) {
        console.error(error);
        return null;
    }
}


function obtenerProductoSalidaActual() {
    return salidaProductoSeleccionado || obtenerProductoTrabajoMovimiento();
}


function obtenerProductosSalidaDisponibles() {
    return leerProductosCarnicosGuardados().map(function (producto) {
        return normalizarProductoCarnico(producto);
    }).filter(function (producto) {
        return producto.id;
    });
}


function actualizarContextoSalida(contexto) {
    const producto = obtenerProductoSalidaActual();
    const label = document.createElement("span");
    const nombre = document.createElement("strong");

    label.textContent = "Producto en trabajo";
    nombre.textContent = producto
        ? textoProductoRegistro(producto)
        : "Sin producto seleccionado";
    contexto.replaceChildren(label, nombre);
}


function seleccionarProductoSalida(producto, fila) {
    salidaProductoSeleccionado = normalizarProductoCarnico(producto);

    document
        .querySelectorAll("#opcionesMovimientoModulo tbody tr")
        .forEach(function (registro) {
            registro.classList.remove("fila-seleccionada");
        });

    if (fila) {
        fila.classList.add("fila-seleccionada");
    }

    mostrarEstadoMovimientoModulo(
        movimientoModuloActual === "salida"
            ? "Producto listo. Captura cantidad y empleados para registrar salida."
            : "Producto listo. Presiona Seleccionar producto para cargar la transformacion.",
        "success"
    );
}


function crearTablaSalidaProductos(productos) {
    const tabla = document.createElement("table");
    const encabezado = document.createElement("thead");
    const cuerpo = document.createElement("tbody");

    tabla.className = "salida-productos-tabla";
    encabezado.innerHTML = `
        <tr>
            <th>Clave</th>
            <th>Producto</th>
            <th>Unidad</th>
        </tr>
    `;

    if (!productos.length) {
        cuerpo.appendChild(
            crearFilaVaciaConfiguracionCarnicos(
                "No hay productos configurados para este movimiento.",
                3
            )
        );
        tabla.append(encabezado, cuerpo);
        return tabla;
    }

    productos.forEach(function (producto) {
        const fila = document.createElement("tr");

        if (
            salidaProductoSeleccionado &&
            salidaProductoSeleccionado.id === producto.id
        ) {
            fila.classList.add("fila-seleccionada");
        }

        fila.addEventListener("click", function () {
            seleccionarProductoSalida(producto, fila);
        });

        [
            producto.clave,
            producto.nombre,
            producto.unidad
        ].forEach(function (valor) {
            const celda = document.createElement("td");
            celda.textContent = valor || "-";
            fila.appendChild(celda);
        });

        cuerpo.appendChild(fila);
    });

    tabla.append(encabezado, cuerpo);
    return tabla;
}


function renderizarEmpleadosSalida(contenedor) {
    contenedor.replaceChildren();

    if (!salidaEmpleadosMovimiento.length) {
        const vacio = document.createElement("span");

        vacio.className = "salida-chip salida-chip-empty";
        vacio.textContent = "Sin empleados agregados";
        contenedor.appendChild(vacio);
        return;
    }

    salidaEmpleadosMovimiento.forEach(function (empleado, indice) {
        const chip = document.createElement("button");

        chip.type = "button";
        chip.className = "salida-chip";
        chip.textContent = `${empleado} x`;
        chip.addEventListener("click", function () {
            salidaEmpleadosMovimiento.splice(indice, 1);
            renderizarEmpleadosSalida(contenedor);
            mostrarEstadoMovimientoModulo(
                "Empleado quitado del movimiento.",
                "warning"
            );
        });
        contenedor.appendChild(chip);
    });
}


function agregarEmpleadoSalida(input, contenedor) {
    const empleado = input.value.trim();

    if (!empleado) {
        mostrarEstadoMovimientoModulo(
            "Captura el nombre del empleado.",
            "warning"
        );
        return;
    }

    const yaExiste = salidaEmpleadosMovimiento.some(function (actual) {
        return actual.toUpperCase() === empleado.toUpperCase();
    });

    if (yaExiste) {
        mostrarEstadoMovimientoModulo(
            "Ese empleado ya esta agregado.",
            "warning"
        );
        return;
    }

    salidaEmpleadosMovimiento.push(empleado);
    input.value = "";
    renderizarEmpleadosSalida(contenedor);
    mostrarEstadoMovimientoModulo(
        "Empleado agregado al movimiento.",
        "success"
    );
}


async function seleccionarProductoSalidaActual(panelDestino = "salida") {
    if (!salidaProductoSeleccionado) {
        mostrarEstadoMovimientoModulo(
            "Selecciona un producto de la tabla.",
            "warning"
        );
        return;
    }

    productoSeleccionadoOriginal = salidaProductoSeleccionado;
    productoOrigenSeleccionado = salidaProductoSeleccionado;
    componentesConfiguracionDraft = [];
    resultantesConfiguracionDraft = [];
    actualizarTarjetaOrigen(salidaProductoSeleccionado);
    reiniciarLimiteMerma();
    await cargarProductosResultantes(salidaProductoSeleccionado.id);
    actualizarModuloProductoActual();
    renderizarPanelMovimientoModulo(panelDestino);
    mostrarEstadoMovimientoModulo(
        "Producto seleccionado para trabajar.",
        "success"
    );
}


async function registrarSalidaMovimiento() {
    const cantidadInput = document.getElementById("salidaCantidadMovimiento");
    const observacionesInput = document.getElementById(
        "salidaObservacionesMovimiento"
    );
    const cantidad = Number(cantidadInput?.value || 0);

    if (!salidaProductoSeleccionado) {
        mostrarEstadoMovimientoModulo(
            "Selecciona un producto de salida.",
            "warning"
        );
        return;
    }

    if (!Number.isFinite(cantidad) || cantidad <= 0) {
        mostrarEstadoMovimientoModulo(
            "Captura una cantidad valida para la salida.",
            "warning"
        );
        return;
    }

    if (!salidaEmpleadosMovimiento.length) {
        mostrarEstadoMovimientoModulo(
            "Agrega al menos un empleado al movimiento.",
            "warning"
        );
        return;
    }

    await seleccionarProductoSalidaActual();

    const cantidadOrigenInput = document.getElementById("cantidadOrigen");

    if (cantidadOrigenInput) {
        cantidadOrigenInput.value = String(cantidad);
    }

    actualizarBalance();
    window.localStorage.setItem(
        STORAGE_SALIDA_MOVIMIENTO,
        JSON.stringify({
            producto: salidaProductoSeleccionado,
            cantidad,
            empleados: salidaEmpleadosMovimiento,
            observaciones: observacionesInput?.value.trim() || "",
            usuario: sesionActual?.usuario || "",
            fecha: new Date().toISOString()
        })
    );
    mostrarEstadoMovimientoModulo(
        "Salida registrada en borrador. Continua con entrada o transformacion.",
        "success"
    );
}


function cancelarSalidaMovimiento() {
    salidaProductoSeleccionado = null;
    salidaEmpleadosMovimiento = [];
    window.localStorage.removeItem(STORAGE_SALIDA_MOVIMIENTO);
    renderizarPanelMovimientoModulo("salida");
    mostrarEstadoMovimientoModulo("Salida cancelada.", "warning");
}


function crearCampoSalida(labelTexto, control) {
    const label = document.createElement("label");
    const span = document.createElement("span");

    span.textContent = labelTexto;
    label.append(span, control);
    return label;
}


function renderizarPanelSalidaMovimiento(contenedor, contexto) {
    const productos = obtenerProductosSalidaDisponibles();
    const guardada = obtenerSalidaGuardada();
    const panel = document.createElement("div");
    const productosBloque = document.createElement("div");
    const productosTitulo = document.createElement("h3");
    const form = document.createElement("div");
    const cantidad = document.createElement("input");
    const empleado = document.createElement("input");
    const agregarEmpleado = document.createElement("button");
    const empleadosLista = document.createElement("div");
    const observaciones = document.createElement("input");
    const acciones = document.createElement("div");
    const seleccionar = document.createElement("button");
    const registrar = document.createElement("button");
    const cancelar = document.createElement("button");

    if (!salidaProductoSeleccionado && guardada?.producto) {
        salidaProductoSeleccionado = guardada.producto;
    }

    if (!salidaProductoSeleccionado && obtenerProductoTrabajoMovimiento()) {
        salidaProductoSeleccionado = normalizarProductoCarnico(
            obtenerProductoTrabajoMovimiento()
        );
    }

    if (!salidaEmpleadosMovimiento.length && Array.isArray(guardada?.empleados)) {
        salidaEmpleadosMovimiento = [...guardada.empleados];
    }

    panel.className = "salida-panel";
    productosBloque.className = "salida-bloque";
    productosTitulo.textContent = "Seleccionar producto";
    productosBloque.append(productosTitulo, crearTablaSalidaProductos(productos));

    cantidad.type = "number";
    cantidad.id = "salidaCantidadMovimiento";
    cantidad.min = "0";
    cantidad.step = "0.001";
    cantidad.placeholder = "0.000";
    cantidad.value = guardada?.cantidad || "";

    empleado.type = "text";
    empleado.placeholder = "Nombre del empleado";
    agregarEmpleado.type = "button";
    agregarEmpleado.textContent = "Agregar empleado";
    empleadosLista.className = "salida-empleados-lista";
    agregarEmpleado.addEventListener("click", function () {
        agregarEmpleadoSalida(empleado, empleadosLista);
    });
    empleado.addEventListener("keydown", function (evento) {
        if (evento.key === "Enter") {
            evento.preventDefault();
            agregarEmpleadoSalida(empleado, empleadosLista);
        }
    });

    observaciones.type = "text";
    observaciones.id = "salidaObservacionesMovimiento";
    observaciones.maxLength = 180;
    observaciones.placeholder = "Opcional";
    observaciones.value = guardada?.observaciones || "";

    form.className = "salida-form";
    form.append(
        crearCampoSalida("Cantidad de salida", cantidad),
        crearCampoSalida("Empleado", empleado),
        agregarEmpleado,
        crearCampoSalida("Observaciones", observaciones)
    );

    renderizarEmpleadosSalida(empleadosLista);

    seleccionar.type = "button";
    seleccionar.textContent = "Seleccionar producto";
    seleccionar.className = "modulo-accion-secundaria";
    seleccionar.addEventListener("click", function () {
        void seleccionarProductoSalidaActual();
    });

    registrar.type = "button";
    registrar.textContent = "Registrar salida";
    registrar.addEventListener("click", function () {
        void registrarSalidaMovimiento();
    });

    cancelar.type = "button";
    cancelar.textContent = "Cancelar salida";
    cancelar.className = "modulo-accion-secundaria";
    cancelar.addEventListener("click", cancelarSalidaMovimiento);

    acciones.className = "salida-acciones";
    acciones.append(seleccionar, registrar, cancelar);

    panel.append(productosBloque, form, empleadosLista, acciones);
    contenedor.replaceChildren(panel);
    actualizarContextoSalida(contexto);

    mostrarEstadoMovimientoModulo(
        productos.length
            ? "Selecciona un producto, captura cantidad y empleados."
            : "No hay productos configurados. Agregalos desde Configuracion.",
        productos.length ? "" : "warning"
    );
}


function crearBotonPanelMovimiento(texto, accion, secundario = false) {
    const boton = document.createElement("button");

    boton.type = "button";
    boton.textContent = texto;

    if (secundario) {
        boton.className = "modulo-accion-secundaria";
    }

    boton.addEventListener("click", accion);
    return boton;
}


function crearBloquePanelMovimiento(tituloTexto, ...elementos) {
    const bloque = document.createElement("div");
    const titulo = document.createElement("h3");

    bloque.className = "movimiento-bloque";
    titulo.textContent = tituloTexto;
    bloque.append(titulo, ...elementos);
    return bloque;
}


function crearMetricaMovimiento(etiqueta, valor) {
    const tarjeta = document.createElement("div");
    const label = document.createElement("span");
    const dato = document.createElement("strong");

    tarjeta.className = "movimiento-metrica";
    label.textContent = etiqueta;
    dato.textContent = valor || "-";
    tarjeta.append(label, dato);
    return tarjeta;
}


function textoElemento(id, valorPorDefecto = "-") {
    return document.getElementById(id)?.textContent?.trim() || valorPorDefecto;
}


function obtenerFilasResultantesMovimiento() {
    return Array.from(
        document.querySelectorAll(".producto-resultante")
    ).map(function (fila) {
        const select = fila.querySelector(".producto-resultante-id");
        const cantidad = fila.querySelector(".producto-resultante-cantidad");
        const unidad = cantidad?.dataset.unidad || "KILO";
        const producto = obtenerProductoDisponible(select?.value);

        return {
            fila,
            select,
            cantidad,
            unidad,
            producto
        };
    });
}


function crearSelectEntradaMovimiento(selectOriginal) {
    const select = document.createElement("select");

    Array.from(selectOriginal?.options || []).forEach(function (opcion) {
        const copia = document.createElement("option");

        copia.value = opcion.value;
        copia.textContent = opcion.textContent;
        copia.disabled = opcion.disabled;
        select.appendChild(copia);
    });

    select.value = selectOriginal?.value || "";
    select.addEventListener("change", function () {
        if (!selectOriginal) {
            return;
        }

        selectOriginal.value = select.value;
        selectOriginal.dispatchEvent(
            new Event("change", { bubbles: true })
        );
        renderizarPanelMovimientoModulo("entrada");
    });

    return select;
}


function crearTablaEntradaMovimiento() {
    const tabla = document.createElement("table");
    const encabezado = document.createElement("thead");
    const cuerpo = document.createElement("tbody");
    const filas = obtenerFilasResultantesMovimiento();

    tabla.className = "movimiento-tabla";
    encabezado.innerHTML = `
        <tr>
            <th>Producto resultante</th>
            <th>Unidad</th>
            <th>Cantidad</th>
        </tr>
    `;

    if (!filas.length) {
        cuerpo.appendChild(
            crearFilaVaciaConfiguracionCarnicos(
                "Aun no hay productos resultantes capturados.",
                3
            )
        );
        tabla.append(encabezado, cuerpo);
        return tabla;
    }

    filas.forEach(function (registro) {
        const fila = document.createElement("tr");
        const producto = document.createElement("td");
        const unidad = document.createElement("td");
        const cantidadCelda = document.createElement("td");
        const cantidad = document.createElement("input");

        cantidad.type = "text";
        cantidad.inputMode = "decimal";
        cantidad.value = registro.cantidad?.value || "";
        cantidad.placeholder = "Ej. 1,5 kg";
        cantidad.addEventListener("input", function () {
            if (!registro.cantidad) {
                return;
            }

            registro.cantidad.value = cantidad.value;
            registro.cantidad.dataset.automatica = "0";
            registro.cantidad.dispatchEvent(
                new Event("input", { bubbles: true })
            );
        });

        producto.appendChild(crearSelectEntradaMovimiento(registro.select));
        unidad.textContent = registro.unidad || "KILO";
        cantidadCelda.appendChild(cantidad);
        fila.append(producto, unidad, cantidadCelda);
        cuerpo.appendChild(fila);
    });

    tabla.append(encabezado, cuerpo);
    return tabla;
}


function agregarEntradaMovimiento() {
    agregarProductoResultante();
    actualizarBalance();
    renderizarPanelMovimientoModulo("entrada");
    mostrarEstadoMovimientoModulo("Linea de entrada agregada.", "success");
}


function registrarEntradaMovimiento() {
    const productos = obtenerProductosResultantes();
    const incompleta = productos.length === 0 || productos.some(
        function (producto) {
            return !producto.producto_id || Number(producto.cantidad) <= 0;
        }
    );

    if (!obtenerProductoTrabajoMovimiento()) {
        mostrarEstadoMovimientoModulo(
            "Selecciona primero un producto de salida.",
            "warning"
        );
        return;
    }

    if (incompleta) {
        mostrarEstadoMovimientoModulo(
            "Completa producto y cantidad en cada entrada.",
            "warning"
        );
        return;
    }

    actualizarBalance();
    actualizarModuloProductoActual();
    renderizarPanelMovimientoModulo("entrada");
    mostrarEstadoMovimientoModulo(
        "Entrada capturada. Revisa merma o registra la transformacion.",
        "success"
    );
}


function cancelarEntradaMovimiento() {
    if (productoOrigenSeleccionado) {
        renderizarProductosResultantes();
    }

    renderizarPanelMovimientoModulo("entrada");
    mostrarEstadoMovimientoModulo(
        "Entrada cancelada. Se restablecieron los resultantes.",
        "warning"
    );
}


function renderizarPanelEntradaMovimiento(contenedor) {
    const panel = document.createElement("div");
    const acciones = document.createElement("div");

    panel.className = "movimiento-panel";
    acciones.className = "movimiento-acciones";
    acciones.append(
        crearBotonPanelMovimiento("Agregar entrada", agregarEntradaMovimiento),
        crearBotonPanelMovimiento(
            "Registrar entrada",
            registrarEntradaMovimiento
        ),
        crearBotonPanelMovimiento(
            "Cancelar entrada",
            cancelarEntradaMovimiento,
            true
        )
    );

    panel.append(
        crearBloquePanelMovimiento(
            "Productos que entran al inventario",
            crearTablaEntradaMovimiento()
        ),
        acciones
    );
    contenedor.replaceChildren(panel);

    mostrarEstadoMovimientoModulo(
        obtenerProductoTrabajoMovimiento()
            ? "Captura los productos resultantes y sus kilos."
            : "Primero registra o selecciona un producto de salida.",
        obtenerProductoTrabajoMovimiento() ? "" : "warning"
    );
}


function crearResumenBalanceMovimiento() {
    actualizarBalance();

    const resumen = document.createElement("div");
    resumen.className = "movimiento-resumen-grid";
    resumen.append(
        crearMetricaMovimiento("Salida / origen", textoElemento("totalOrigen", "0 kg")),
        crearMetricaMovimiento(
            "Entrada / resultantes",
            textoElemento("totalResultantes", "0 kg")
        ),
        crearMetricaMovimiento("Merma", textoElemento("totalMerma", "0 kg")),
        crearMetricaMovimiento(
            "Merma estimada",
            textoElemento("porcentajeMermaResumen", "0%")
        )
    );
    return resumen;
}


function crearTablaLecturaResultantesMovimiento() {
    const tabla = document.createElement("table");
    const encabezado = document.createElement("thead");
    const cuerpo = document.createElement("tbody");
    const filas = obtenerFilasResultantesMovimiento();

    tabla.className = "movimiento-tabla";
    encabezado.innerHTML = `
        <tr>
            <th>Producto</th>
            <th>Unidad</th>
            <th>Cantidad</th>
        </tr>
    `;

    if (!filas.length) {
        cuerpo.appendChild(
            crearFilaVaciaConfiguracionCarnicos(
                "Aun no hay entradas capturadas.",
                3
            )
        );
    } else {
        filas.forEach(function (registro) {
            const fila = document.createElement("tr");
            const producto = document.createElement("td");
            const unidad = document.createElement("td");
            const cantidad = document.createElement("td");

            producto.textContent = registro.producto
                ? textoProductoRegistro(registro.producto)
                : "Producto sin seleccionar";
            unidad.textContent = registro.unidad || "KILO";
            cantidad.textContent = registro.cantidad?.value || "-";
            fila.append(producto, unidad, cantidad);
            cuerpo.appendChild(fila);
        });
    }

    tabla.append(encabezado, cuerpo);
    return tabla;
}


function crearSelectorProductoTransformacionMovimiento() {
    const contenedor = document.createElement("div");
    const acciones = document.createElement("div");
    const productos = obtenerProductosSalidaDisponibles();
    const productoTrabajo = obtenerProductoTrabajoMovimiento();

    if (!salidaProductoSeleccionado && productoTrabajo) {
        salidaProductoSeleccionado = normalizarProductoCarnico(productoTrabajo);
    }

    contenedor.className = "movimiento-selector-producto";
    acciones.className = "movimiento-acciones movimiento-acciones-compactas";
    acciones.append(
        crearBotonPanelMovimiento(
            "Seleccionar producto",
            function () {
                void seleccionarProductoSalidaActual("transformacion");
            }
        ),
        crearBotonPanelMovimiento(
            "Abrir configuracion",
            function () {
                cerrarPanelMovimientoModulo();
                abrirPanelConfiguracionCarnicos();
            },
            true
        )
    );

    contenedor.append(crearTablaSalidaProductos(productos), acciones);
    return contenedor;
}


async function registrarTransformacionDesdeMovimiento() {
    if (!obtenerProductoTrabajoMovimiento()) {
        mostrarEstadoMovimientoModulo(
            "Selecciona primero un producto para transformar.",
            "warning"
        );
        return;
    }

    mostrarEstadoMovimientoModulo("Registrando transformacion...");
    await registrarTransformacion();

    const resultado = document.getElementById("resultadoTransformacion");
    const esCorrecto = resultado?.classList.contains("success-card");
    const esError = resultado?.classList.contains("error-card");

    mostrarEstadoMovimientoModulo(
        resultado?.textContent || "Proceso terminado.",
        esCorrecto ? "success" : (esError ? "error" : "")
    );
}


function renderizarPanelTransformacionMovimiento(contenedor) {
    const panel = document.createElement("div");
    const acciones = document.createElement("div");

    panel.className = "movimiento-panel";
    acciones.className = "movimiento-acciones";
    acciones.append(
        crearBotonPanelMovimiento(
            "Editar entrada",
            function () {
                if (!obtenerProductoTrabajoMovimiento()) {
                    mostrarEstadoMovimientoModulo(
                        "Selecciona primero un producto para editar la entrada.",
                        "warning"
                    );
                    return;
                }

                seleccionarMovimientoModulo("entrada");
                renderizarPanelMovimientoModulo("entrada");
            },
            true
        ),
        crearBotonPanelMovimiento(
            "Registrar transformacion",
            function () {
                void registrarTransformacionDesdeMovimiento();
            }
        ),
        crearBotonPanelMovimiento(
            "Cancelar",
            cerrarPanelMovimientoModulo,
            true
        )
    );

    panel.append(
        crearBloquePanelMovimiento(
            "Seleccionar producto",
            crearSelectorProductoTransformacionMovimiento()
        ),
        crearBloquePanelMovimiento(
            "Resumen de la transformacion",
            crearResumenBalanceMovimiento()
        ),
        crearBloquePanelMovimiento(
            "Productos resultantes",
            crearTablaLecturaResultantesMovimiento()
        ),
        acciones
    );
    contenedor.replaceChildren(panel);

    mostrarEstadoMovimientoModulo(
        obtenerProductoTrabajoMovimiento()
            ? "Revisa el resumen antes de guardar la operacion."
            : "Primero registra o selecciona un producto de salida.",
        obtenerProductoTrabajoMovimiento() ? "" : "warning"
    );
}


function crearCampoMermaMovimiento(labelTexto, control) {
    const label = document.createElement("label");
    const span = document.createElement("span");

    span.textContent = labelTexto;
    label.append(span, control);
    return label;
}


function aplicarMermaMovimiento() {
    actualizarBalance();
    renderizarPanelMovimientoModulo("merma");
    mostrarEstadoMovimientoModulo(
        "Merma aplicada al balance de la transformacion.",
        "success"
    );
}


function cancelarMermaMovimiento() {
    const limite = document.getElementById("porcentajeMermaEsperado");
    const observaciones = document.getElementById("observacionesMerma");

    if (limite) {
        limite.value = "";
    }

    if (observaciones) {
        observaciones.value = "";
    }

    actualizarBalance();
    renderizarPanelMovimientoModulo("merma");
    mostrarEstadoMovimientoModulo("Merma cancelada.", "warning");
}


function crearFormularioMermaMovimiento() {
    const form = document.createElement("div");
    const limiteOriginal = document.getElementById("porcentajeMermaEsperado");
    const observacionesOriginal = document.getElementById("observacionesMerma");
    const limite = document.createElement("input");
    const observaciones = document.createElement("input");

    form.className = "movimiento-form";

    limite.type = "number";
    limite.min = "0";
    limite.max = "100";
    limite.step = "0.01";
    limite.placeholder = "Ej. 8";
    limite.value = limiteOriginal?.value || "";
    limite.addEventListener("input", function () {
        if (limiteOriginal) {
            limiteOriginal.value = limite.value;
        }

        actualizarBalance();
    });

    observaciones.type = "text";
    observaciones.maxLength = 250;
    observaciones.placeholder = "Observaciones o incidencia";
    observaciones.value = observacionesOriginal?.value || "";
    observaciones.addEventListener("input", function () {
        if (observacionesOriginal) {
            observacionesOriginal.value = observaciones.value;
        }
    });

    form.append(
        crearCampoMermaMovimiento("Limite de merma (%)", limite),
        crearCampoMermaMovimiento("Observaciones", observaciones)
    );
    return form;
}


function renderizarPanelMermaMovimiento(contenedor) {
    const panel = document.createElement("div");
    const acciones = document.createElement("div");

    panel.className = "movimiento-panel";
    acciones.className = "movimiento-acciones";
    acciones.append(
        crearBotonPanelMovimiento("Aplicar merma", aplicarMermaMovimiento),
        crearBotonPanelMovimiento(
            "Registrar transformacion",
            function () {
                void registrarTransformacionDesdeMovimiento();
            }
        ),
        crearBotonPanelMovimiento(
            "Cancelar merma",
            cancelarMermaMovimiento,
            true
        )
    );

    panel.append(
        crearBloquePanelMovimiento(
            "Balance de merma",
            crearResumenBalanceMovimiento()
        ),
        crearBloquePanelMovimiento(
            "Limite y observacion",
            crearFormularioMermaMovimiento()
        ),
        acciones
    );
    contenedor.replaceChildren(panel);

    mostrarEstadoMovimientoModulo(
        obtenerProductoTrabajoMovimiento()
            ? "Ajusta el limite u observacion de merma."
            : "Primero registra o selecciona un producto de salida.",
        obtenerProductoTrabajoMovimiento() ? "" : "warning"
    );
}


function obtenerOpcionesMovimientoModulo(tipo) {
    const tieneProducto = Boolean(obtenerProductoTrabajoMovimiento());
    const requiereProducto = "Primero selecciona un producto de salida.";

    if (tipo === "entrada") {
        return [
            {
                titulo: "Capturar entrada",
                descripcion: "Ve a los productos resultantes de la operacion.",
                deshabilitada: !tieneProducto,
                motivo: requiereProducto,
                accion: function () {
                    abrirCapturaMovimiento({
                        scrollSelector: "#productosResultantes"
                    });
                }
            },
            {
                titulo: "Agregar resultante manual",
                descripcion: "Agrega otra linea de entrada si aplica.",
                deshabilitada: !tieneProducto,
                motivo: requiereProducto,
                accion: function () {
                    abrirCapturaMovimiento({
                        scrollSelector: "#productosResultantes"
                    });
                    window.setTimeout(function () {
                        const boton = document.getElementById(
                            "botonAgregarResultante"
                        );

                        if (boton && !boton.hidden) {
                            boton.click();
                        }
                    }, 0);
                }
            },
            {
                titulo: "Abrir configuraciones",
                descripcion: "Edita relaciones de origen, insumos y salidas.",
                accion: abrirConfiguracionesDesdeMovimiento
            }
        ];
    }

    if (tipo === "merma") {
        return [
            {
                titulo: "Revisar balance",
                descripcion: "Muestra salida, entrada y merma calculada.",
                deshabilitada: !tieneProducto,
                motivo: requiereProducto,
                accion: function () {
                    abrirCapturaMovimiento({
                        scrollSelector: ".validation-box"
                    });
                }
            },
            {
                titulo: "Capturar limite",
                descripcion: "Define el porcentaje maximo permitido.",
                deshabilitada: !tieneProducto,
                motivo: requiereProducto,
                accion: function () {
                    abrirCapturaMovimiento({
                        abrirMerma: true,
                        campoId: "porcentajeMermaEsperado",
                        scrollSelector: ".merma-opcional"
                    });
                }
            },
            {
                titulo: "Agregar observacion",
                descripcion: "Registra notas o incidencias de la merma.",
                deshabilitada: !tieneProducto,
                motivo: requiereProducto,
                accion: function () {
                    abrirCapturaMovimiento({
                        abrirMerma: true,
                        campoId: "observacionesMerma",
                        scrollSelector: ".merma-opcional"
                    });
                }
            },
            {
                titulo: "Ver registros",
                descripcion: "Consulta mermas de movimientos anteriores.",
                accion: verRegistrosDesdeMovimiento
            }
        ];
    }

    return [
        {
            titulo: "Nueva transformacion",
            descripcion: "Captura salida, entrada y merma en una operacion.",
            accion: function () {
                abrirCapturaMovimiento({
                    scrollSelector: "#tarjetaOrigen"
                });
            }
        },
        {
            titulo: "Usar configuracion",
            descripcion: "Abre recetas y relaciones guardadas.",
            accion: abrirConfiguracionesDesdeMovimiento
        },
        {
            titulo: "Ver registros",
            descripcion: "Revisa operaciones ya registradas.",
            accion: verRegistrosDesdeMovimiento
        }
    ];
}


function renderizarPanelMovimientoModulo(tipo) {
    const movimiento = obtenerMovimientoModulo(tipo);
    const etiqueta = document.getElementById("etiquetaModalMovimientoModulo");
    const titulo = document.getElementById("tituloModalMovimientoModulo");
    const descripcion = document.getElementById(
        "descripcionModalMovimientoModulo"
    );
    const contexto = document.getElementById("contextoMovimientoModulo");
    const opciones = document.getElementById("opcionesMovimientoModulo");
    const productoTrabajo = obtenerProductoTrabajoMovimiento();

    if (etiqueta) {
        etiqueta.textContent = movimiento.etiqueta;
    }

    if (titulo) {
        titulo.textContent = movimiento.titulo;
    }

    if (descripcion) {
        descripcion.textContent = movimiento.descripcion;
    }

    if (contexto) {
        const label = document.createElement("span");
        const producto = document.createElement("strong");

        label.textContent = "Producto en trabajo";
        producto.textContent = productoTrabajo
            ? textoProductoRegistro(productoTrabajo)
            : "Sin producto seleccionado";
        contexto.replaceChildren(label, producto);
    }

    if (opciones && contexto) {
        if (tipo === "salida") {
            renderizarPanelSalidaMovimiento(opciones, contexto);
            return;
        }

        if (tipo === "entrada") {
            renderizarPanelEntradaMovimiento(opciones);
            return;
        }

        if (tipo === "transformacion") {
            renderizarPanelTransformacionMovimiento(opciones);
            return;
        }

        if (tipo === "merma") {
            renderizarPanelMermaMovimiento(opciones);
            return;
        }
    }

    if (opciones) {
        const grid = document.createElement("div");

        grid.className = "movimiento-opciones-grid";
        obtenerOpcionesMovimientoModulo(tipo).forEach(function (opcion) {
            grid.appendChild(crearOpcionMovimientoModulo(opcion));
        });
        opciones.replaceChildren(grid);
    }

    mostrarEstadoMovimientoModulo(
        productoTrabajo
            ? "Selecciona la opcion que necesitas para continuar."
            : "No hay producto en trabajo. Usa configuracion o selecciona un flujo disponible."
    );
}


function abrirPanelMovimientoModulo(tipo) {
    const modal = document.getElementById("modalMovimientoModulo");

    if (!modal) {
        return;
    }

    seleccionarMovimientoModulo(tipo);
    renderizarPanelMovimientoModulo(movimientoModuloActual);
    modal.classList.remove("hidden");
    document.body.classList.add("modal-open");
}


function cerrarPanelMovimientoModulo() {
    const modal = document.getElementById("modalMovimientoModulo");

    if (!modal) {
        return;
    }

    modal.classList.add("hidden");
    document.body.classList.remove("modal-open");
}


function accionPrincipalModulo() {
    const movimiento = obtenerMovimientoModulo(movimientoModuloActual);
    mostrarSeccion(movimiento.seccion);
}


function mostrarSeccion(idSeccion) {
    if (idSeccion === "configuraciones") {
        abrirModalConfiguraciones();
        return;
    }

    cerrarModalConfiguraciones();

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

    if (idSeccion === "moduloCarnico") {
        actualizarModuloProductoActual();
        cargarModuloCarnico();
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

    window.location.replace("/");
}


const PRODUCTOS_POR_PAGINA = 10;
const REGISTROS_POR_PAGINA = PRODUCTOS_POR_PAGINA;
const CONFIGURACIONES_POR_PAGINA = PRODUCTOS_POR_PAGINA;
const PRODUCTOS_CONFIGURACION_POR_PAGINA = 6;
const PRODUCTOS_CARNICOS_CONFIGURACION_POR_PAGINA = 6;
const PRODUCTOS_CARNICOS_AGREGADOS_POR_PAGINA = 6;
const TERMINOS_PRODUCTOS_CARNICOS_INICIALES = [
    "cerdo",
    "pollo",
    "res local"
];
const STORAGE_PRODUCTOS_CARNICOS =
    "cayal.productos_carnicos_configurados";
const STORAGE_SALIDA_MOVIMIENTO =
    "cayal.salida_movimiento_actual";
const TIEMPO_LIMITE_CONSULTA_MS = 15000;
const TIEMPO_LIMITE_REGISTRO_MS = 60000;
const TIPO_TRANSFORMACION_CONFIGURADA = "receta_configurada";
const TIPO_PRODUCTO_FINAL = "producto_final";
let sesionActual = null;
let registrosPaginaActual = 1;
let configuracionesPaginaActual = 1;
let solicitudHistorialActual = 0;
let productoOrigenSeleccionado = null;
let productoSeleccionadoOriginal = null;
let productosResultantesDisponibles = [];
let productosConfiguracionBusquedaActual = "";
let productosConfiguracionPaginaActual = 1;
let productosCarnicosConfigurados = [];
let productosCarnicosConfiguradosPagina = 1;
let productosCarnicosDisponibles = [];
let productosCarnicosDisponiblesPagina = 1;
let productoCarnicoDisponibleSeleccionado = null;
let productoCarnicoConfiguradoSeleccionado = null;
let productosCarnicosBusquedaActual = "";
let productosCarnicosPaginaActual = 1;
let salidaProductoSeleccionado = null;
let salidaEmpleadosMovimiento = [];
let componentesConfiguracionDraft = [];
let resultantesConfiguracionDraft = [];
let origenConfiguradoActual = null;
let configuracionUsuarioActual = null;
let configuracionEditando = null;
let tipoRelacionActual = null;
let tipoTransformacionActual = TIPO_TRANSFORMACION_CONFIGURADA;
let componentesFormulaActual = [];
let productoYaTransformadoSeleccionado = false;
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


async function solicitarJson(
    url,
    opciones = {},
    tiempoLimite = TIEMPO_LIMITE_CONSULTA_MS
) {
    const controlador = new AbortController();
    const temporizador = window.setTimeout(
        function () {
            controlador.abort();
        },
        tiempoLimite
    );

    try {
        const respuesta = await fetch(url, {
            ...opciones,
            signal: controlador.signal
        });
        let datos = {};

        try {
            datos = await respuesta.json();
        } catch (error) {
            if (respuesta.ok) {
                throw new Error("El servidor devolvió una respuesta vacía");
            }
        }

        return {
            respuesta,
            datos
        };
    } catch (error) {
        if (error.name === "AbortError") {
            throw new Error(
                "El servidor tardó demasiado en responder. Intenta nuevamente."
            );
        }

        throw error;
    } finally {
        window.clearTimeout(temporizador);
    }
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


function crearTablaProductosConfiguracion(productos) {
    const tabla = document.createElement("table");
    const encabezado = document.createElement("thead");
    const cuerpo = document.createElement("tbody");

    tabla.className = "productos-tabla config-productos-tabla";
    encabezado.innerHTML = `
        <tr>
            <th>Clave</th>
            <th>Nombre</th>
            <th>Categoria</th>
            <th>Unidad</th>
            <th></th>
        </tr>
    `;

    productos.forEach(function (producto) {
        const fila = document.createElement("tr");
        const celdaAcciones = document.createElement("td");
        const botonOrigen = document.createElement("button");
        const botonInsumo = document.createElement("button");
        const botonResultante = document.createElement("button");

        [
            producto.clave,
            producto.nombre,
            producto.categoria,
            producto.unidad
        ].forEach(function (valor) {
            const celda = document.createElement("td");
            celda.textContent = valor ?? "";
            fila.appendChild(celda);
        });

        botonOrigen.type = "button";
        botonOrigen.textContent = "Origen";
        botonOrigen.className = "modulo-accion-secundaria";
        botonOrigen.addEventListener("click", function () {
            void seleccionarProductoOrigenConfiguracion(producto);
        });

        botonInsumo.type = "button";
        botonInsumo.textContent = "Insumo";
        botonInsumo.addEventListener("click", function () {
            agregarProductoAConfiguracion(producto, "componente");
        });

        botonResultante.type = "button";
        botonResultante.textContent = "Resultante";
        botonResultante.addEventListener("click", function () {
            agregarProductoAConfiguracion(producto, "resultante");
        });

        celdaAcciones.className = "acciones-tabla";
        celdaAcciones.append(botonOrigen, botonInsumo, botonResultante);
        fila.appendChild(celdaAcciones);
        cuerpo.appendChild(fila);
    });

    tabla.append(encabezado, cuerpo);
    return tabla;
}


async function buscarProductosConfiguracion(pagina = 1) {
    const busquedaInput = document.getElementById(
        "busquedaProductoConfiguracion"
    );
    const contenedor = document.getElementById(
        "tablaProductosConfiguracion"
    );

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
        productosConfiguracionBusquedaActual = termino;
        productosConfiguracionPaginaActual = pagina;

        const resultado = await consultarProductos(
            productosConfiguracionBusquedaActual,
            productosConfiguracionPaginaActual,
            PRODUCTOS_CONFIGURACION_POR_PAGINA
        );
        const productos = resultado.productos || [];

        contenedor.replaceChildren();

        if (productos.length === 0) {
            contenedor.textContent = "No se encontraron productos.";
            return;
        }

        contenedor.appendChild(
            crearTablaProductosConfiguracion(productos)
        );
        contenedor.appendChild(
            crearControlesPaginacion(
                resultado,
                "productos",
                buscarProductosConfiguracion
            )
        );
    } catch (error) {
        contenedor.textContent = error.message;
    }
}


function leerProductosCarnicosGuardados() {
    try {
        const guardados = JSON.parse(
            window.localStorage.getItem(STORAGE_PRODUCTOS_CARNICOS) || "[]"
        );

        return Array.isArray(guardados) ? guardados : [];
    } catch (error) {
        console.error(error);
        return [];
    }
}


function productoCarnicoId(producto) {
    return String(producto.id ?? producto.producto_id ?? producto.clave ?? "");
}


function normalizarProductoCarnico(producto) {
    return {
        id: productoCarnicoId(producto),
        clave: producto.clave || producto.ProductKey || "",
        nombre: producto.nombre || producto.ProductName || "",
        categoria: producto.categoria || producto.Category1 || "",
        unidad: producto.unidad || producto.Unit || "",
        cantidad: producto.cantidad || ""
    };
}


function mostrarEstadoConfiguracionCarnicos(mensaje, tipo = "") {
    const estado = document.getElementById("estadoConfiguracionCarnicos");

    if (!estado) {
        return;
    }

    estado.className = `config-carnicos-status ${tipo}`.trim();
    estado.textContent = mensaje;
}


function crearFilaVaciaConfiguracionCarnicos(mensaje, columnas) {
    const fila = document.createElement("tr");
    const celda = document.createElement("td");

    celda.colSpan = columnas;
    celda.className = "tabla-vacia";
    celda.textContent = mensaje;
    fila.appendChild(celda);
    return fila;
}


function paginarListaCarnicos(lista, pagina, limite) {
    const total = lista.length;
    const totalPaginas = Math.max(1, Math.ceil(total / limite));
    const paginaSegura = Math.min(
        Math.max(Number(pagina) || 1, 1),
        totalPaginas
    );
    const inicio = (paginaSegura - 1) * limite;
    const fin = inicio + limite;

    return {
        productos: lista.slice(inicio, fin),
        paginacion: {
            pagina: paginaSegura,
            limite,
            total,
            total_paginas: totalPaginas
        }
    };
}


function agregarPaginacionCarnicos(
    contenedor,
    paginacion,
    etiqueta,
    cambiarPagina
) {
    if (paginacion.total <= paginacion.limite) {
        return;
    }

    contenedor.appendChild(
        crearControlesPaginacion(paginacion, etiqueta, cambiarPagina)
    );
}


function seleccionarProductoCarnicoDisponible(producto, fila) {
    productoCarnicoDisponibleSeleccionado = normalizarProductoCarnico(producto);

    document
        .querySelectorAll("#resultadosProductosCarnicosConfig tbody tr")
        .forEach(function (registro) {
            registro.classList.remove("fila-seleccionada");
        });

    if (fila) {
        fila.classList.add("fila-seleccionada");
    }

    mostrarEstadoConfiguracionCarnicos(
        "Producto seleccionado. Presiona Agregar para sumarlo al modulo.",
        "success"
    );
}


function seleccionarProductoCarnicoConfigurado(producto, fila) {
    productoCarnicoConfiguradoSeleccionado = producto;

    document
        .querySelectorAll("#tablaProductosCarnicosConfig tbody tr")
        .forEach(function (registro) {
            registro.classList.remove("fila-seleccionada");
        });

    if (fila) {
        fila.classList.add("fila-seleccionada");
    }
}


function renderizarProductosCarnicosDisponibles(
    pagina = productosCarnicosDisponiblesPagina
) {
    const contenedor = document.getElementById(
        "resultadosProductosCarnicosConfig"
    );

    if (!contenedor) {
        return;
    }

    const paginaLocal = paginarListaCarnicos(
        productosCarnicosDisponibles,
        pagina,
        PRODUCTOS_CARNICOS_CONFIGURACION_POR_PAGINA
    );
    const seleccionadoVisible = paginaLocal.productos.some(
        function (producto) {
            return (
                productoCarnicoDisponibleSeleccionado &&
                producto.id === productoCarnicoDisponibleSeleccionado.id
            );
        }
    );

    if (!seleccionadoVisible) {
        productoCarnicoDisponibleSeleccionado = null;
    }

    productosCarnicosDisponiblesPagina = paginaLocal.paginacion.pagina;
    contenedor.replaceChildren();
    contenedor.appendChild(
        crearTablaResultadosProductosCarnicos(paginaLocal.productos)
    );
    agregarPaginacionCarnicos(
        contenedor,
        paginaLocal.paginacion,
        "productos",
        renderizarProductosCarnicosDisponibles
    );
}


function renderizarProductosCarnicosConfigurados(
    pagina = productosCarnicosConfiguradosPagina
) {
    const contenedor = document.getElementById("tablaProductosCarnicosConfig");

    if (!contenedor) {
        return;
    }

    const paginaLocal = paginarListaCarnicos(
        productosCarnicosConfigurados,
        pagina,
        PRODUCTOS_CARNICOS_AGREGADOS_POR_PAGINA
    );
    const seleccionadoVisible = paginaLocal.productos.some(
        function (producto) {
            return (
                productoCarnicoConfiguradoSeleccionado &&
                producto.id === productoCarnicoConfiguradoSeleccionado.id
            );
        }
    );

    if (!seleccionadoVisible) {
        productoCarnicoConfiguradoSeleccionado = null;
    }

    productosCarnicosConfiguradosPagina = paginaLocal.paginacion.pagina;
    contenedor.replaceChildren();

    const tabla = document.createElement("table");
    const encabezado = document.createElement("thead");
    const cuerpo = document.createElement("tbody");

    tabla.className = "config-carnicos-tabla";
    encabezado.innerHTML = `
        <tr>
            <th>Clave</th>
            <th>Nombre producto</th>
            <th>Cantidad</th>
        </tr>
    `;

    if (productosCarnicosConfigurados.length === 0) {
        cuerpo.appendChild(
            crearFilaVaciaConfiguracionCarnicos(
                "No hay productos agregados.",
                3
            )
        );
        tabla.append(encabezado, cuerpo);
        contenedor.appendChild(tabla);
        return;
    }

    paginaLocal.productos.forEach(function (producto) {
        const fila = document.createElement("tr");
        const clave = document.createElement("td");
        const nombre = document.createElement("td");
        const cantidadCelda = document.createElement("td");
        const cantidad = document.createElement("input");

        clave.textContent = producto.clave || "-";
        nombre.textContent = producto.nombre || "-";
        fila.tabIndex = 0;

        if (
            productoCarnicoConfiguradoSeleccionado &&
            productoCarnicoConfiguradoSeleccionado.id === producto.id
        ) {
            fila.classList.add("fila-seleccionada");
        }

        fila.addEventListener("click", function () {
            seleccionarProductoCarnicoConfigurado(producto, fila);
        });

        cantidad.type = "text";
        cantidad.value = producto.cantidad || "";
        cantidad.placeholder = producto.unidad || "Cantidad";
        cantidad.addEventListener("click", function () {
            seleccionarProductoCarnicoConfigurado(producto, fila);
        });
        cantidad.addEventListener("input", function () {
            producto.cantidad = cantidad.value;
        });

        cantidadCelda.appendChild(cantidad);
        fila.append(clave, nombre, cantidadCelda);
        cuerpo.appendChild(fila);
    });

    tabla.append(encabezado, cuerpo);
    contenedor.appendChild(tabla);
    agregarPaginacionCarnicos(
        contenedor,
        paginaLocal.paginacion,
        "productos agregados",
        renderizarProductosCarnicosConfigurados
    );
}


function agregarProductoCarnicoSeleccionado() {
    if (!productoCarnicoDisponibleSeleccionado) {
        mostrarEstadoConfiguracionCarnicos(
            "Selecciona primero un producto de la lista disponible.",
            "warning"
        );
        return;
    }

    agregarProductoCarnicoConfiguracion(productoCarnicoDisponibleSeleccionado);
}


function agregarProductoCarnicoConfiguracion(producto) {
    const productoNormalizado = normalizarProductoCarnico(producto);

    if (!productoNormalizado.id) {
        mostrarEstadoConfiguracionCarnicos("Producto no valido.", "error");
        return;
    }

    const yaExiste = productosCarnicosConfigurados.some(function (actual) {
        return actual.id === productoNormalizado.id;
    });

    if (yaExiste) {
        mostrarEstadoConfiguracionCarnicos(
            "Ese producto ya esta en la configuracion.",
            "warning"
        );
        return;
    }

    productosCarnicosConfigurados.push(productoNormalizado);
    productoCarnicoConfiguradoSeleccionado = productoNormalizado;
    productosCarnicosConfiguradosPagina = Math.ceil(
        productosCarnicosConfigurados.length /
            PRODUCTOS_CARNICOS_AGREGADOS_POR_PAGINA
    );
    renderizarProductosCarnicosConfigurados(
        productosCarnicosConfiguradosPagina
    );
    mostrarEstadoConfiguracionCarnicos(
        "Producto agregado. Presiona Guardar para conservar cambios.",
        "success"
    );
}


function eliminarProductoCarnicoSeleccionado() {
    if (!productoCarnicoConfiguradoSeleccionado) {
        mostrarEstadoConfiguracionCarnicos(
            "Selecciona primero un producto agregado para eliminarlo.",
            "warning"
        );
        return;
    }

    quitarProductoCarnicoConfiguracion(productoCarnicoConfiguradoSeleccionado.id);
}


function quitarProductoCarnicoConfiguracion(productoId) {
    const productoIdTexto = String(productoId);

    productosCarnicosConfigurados = productosCarnicosConfigurados.filter(
        function (producto) {
            return producto.id !== productoIdTexto;
        }
    );
    if (
        productoCarnicoConfiguradoSeleccionado &&
        productoCarnicoConfiguradoSeleccionado.id === productoIdTexto
    ) {
        productoCarnicoConfiguradoSeleccionado = null;
    }
    renderizarProductosCarnicosConfigurados(
        productosCarnicosConfiguradosPagina
    );
    mostrarEstadoConfiguracionCarnicos(
        "Producto eliminado. Presiona Guardar para conservar cambios.",
        "warning"
    );
}


function crearTablaResultadosProductosCarnicos(productos) {
    const tabla = document.createElement("table");
    const encabezado = document.createElement("thead");
    const cuerpo = document.createElement("tbody");

    tabla.className = "productos-tabla config-carnicos-resultados-tabla";
    encabezado.innerHTML = `
        <tr>
            <th>Clave</th>
            <th>Nombre producto</th>
            <th>Unidad</th>
        </tr>
    `;

    if (!productos.length) {
        cuerpo.appendChild(
            crearFilaVaciaConfiguracionCarnicos(
                "No hay productos para mostrar.",
                3
            )
        );
        tabla.append(encabezado, cuerpo);
        return tabla;
    }

    productos.forEach(function (producto) {
        const fila = document.createElement("tr");
        const productoNormalizado = normalizarProductoCarnico(producto);

        fila.tabIndex = 0;

        if (
            productoCarnicoDisponibleSeleccionado &&
            productoCarnicoDisponibleSeleccionado.id === productoNormalizado.id
        ) {
            fila.classList.add("fila-seleccionada");
        }

        fila.addEventListener("click", function () {
            seleccionarProductoCarnicoDisponible(productoNormalizado, fila);
        });

        fila.addEventListener("dblclick", function () {
            seleccionarProductoCarnicoDisponible(productoNormalizado, fila);
            agregarProductoCarnicoSeleccionado();
        });

        [
            productoNormalizado.clave,
            productoNormalizado.nombre,
            productoNormalizado.unidad
        ].forEach(function (valor) {
            const celda = document.createElement("td");
            celda.textContent = valor || "-";
            fila.appendChild(celda);
        });
        cuerpo.appendChild(fila);
    });

    tabla.append(encabezado, cuerpo);
    return tabla;
}


function obtenerProductosUnicosCarnicos(listaProductos) {
    const productos = [];
    const ids = new Set();

    listaProductos.forEach(function (producto) {
        const normalizado = normalizarProductoCarnico(producto);

        if (!normalizado.id || ids.has(normalizado.id)) {
            return;
        }

        ids.add(normalizado.id);
        productos.push(normalizado);
    });

    return productos;
}


async function cargarListaInicialProductosCarnicos() {
    const contenedor = document.getElementById(
        "resultadosProductosCarnicosConfig"
    );

    if (!contenedor) {
        return;
    }

    contenedor.replaceChildren();
    contenedor.textContent = "Cargando lista de productos...";
    productoCarnicoDisponibleSeleccionado = null;

    try {
        const respuestas = await Promise.all(
            TERMINOS_PRODUCTOS_CARNICOS_INICIALES.map(function (termino) {
                return consultarProductos(
                    termino,
                    1,
                    PRODUCTOS_CARNICOS_CONFIGURACION_POR_PAGINA
                );
            })
        );
        const productos = obtenerProductosUnicosCarnicos(
            respuestas.flatMap(function (respuesta) {
                return respuesta.productos || [];
            })
        );

        productosCarnicosDisponibles = productos;
        productosCarnicosDisponiblesPagina = 1;
        renderizarProductosCarnicosDisponibles();

        if (productos.length) {
            mostrarEstadoConfiguracionCarnicos(
                "Lista inicial cargada. Puedes agregar productos a la tabla.",
                "success"
            );
        }
    } catch (error) {
        productosCarnicosDisponibles = [];
        productosCarnicosDisponiblesPagina = 1;
        renderizarProductosCarnicosDisponibles();
        mostrarEstadoConfiguracionCarnicos(error.message, "error");
    }
}


async function buscarProductosCarnicosConfiguracion(pagina = 1) {
    const busquedaInput = document.getElementById(
        "busquedaProductoCarnicoConfig"
    );
    const contenedor = document.getElementById(
        "resultadosProductosCarnicosConfig"
    );

    if (!busquedaInput || !contenedor) {
        return;
    }

    const termino = busquedaInput.value.trim();
    contenedor.replaceChildren();
    productoCarnicoDisponibleSeleccionado = null;

    if (termino.length < 2) {
        productosCarnicosBusquedaActual = "";
        productosCarnicosPaginaActual = 1;
        await cargarListaInicialProductosCarnicos();
        return;
    }

    contenedor.textContent = "Buscando productos...";

    try {
        productosCarnicosBusquedaActual = termino;
        productosCarnicosPaginaActual = pagina;

        const resultado = await consultarProductos(
            productosCarnicosBusquedaActual,
            productosCarnicosPaginaActual,
            PRODUCTOS_CARNICOS_CONFIGURACION_POR_PAGINA
        );
        const productos = resultado.productos || [];

        contenedor.replaceChildren();
        productoCarnicoDisponibleSeleccionado = null;

        if (productos.length === 0) {
            contenedor.textContent = "No se encontraron productos.";
            return;
        }

        contenedor.appendChild(
            crearTablaResultadosProductosCarnicos(productos)
        );
        contenedor.appendChild(
            crearControlesPaginacion(
                resultado,
                "productos",
                buscarProductosCarnicosConfiguracion
            )
        );
    } catch (error) {
        contenedor.textContent = error.message;
    }
}


function abrirPanelConfiguracionCarnicos() {
    const modal = document.getElementById("modalConfiguracionCarnicos");

    if (!modal) {
        return;
    }

    productosCarnicosConfigurados = leerProductosCarnicosGuardados();
    productosCarnicosConfiguradosPagina = 1;
    productosCarnicosDisponiblesPagina = 1;
    productoCarnicoDisponibleSeleccionado = null;
    productoCarnicoConfiguradoSeleccionado = null;
    renderizarProductosCarnicosConfigurados(1);
    mostrarEstadoConfiguracionCarnicos("");
    modal.classList.remove("hidden");
    document.body.classList.add("modal-open");
    void cargarListaInicialProductosCarnicos();
}


function cerrarPanelConfiguracionCarnicos() {
    const modal = document.getElementById("modalConfiguracionCarnicos");

    if (!modal) {
        return;
    }

    modal.classList.add("hidden");
    document.body.classList.remove("modal-open");
}


function guardarProductosCarnicosConfiguracion() {
    window.localStorage.setItem(
        STORAGE_PRODUCTOS_CARNICOS,
        JSON.stringify(productosCarnicosConfigurados)
    );
    mostrarEstadoConfiguracionCarnicos(
        "Configuracion guardada correctamente.",
        "success"
    );
}


function limpiarProductosCarnicosConfiguracion() {
    productosCarnicosConfigurados = [];
    productosCarnicosConfiguradosPagina = 1;
    productoCarnicoConfiguradoSeleccionado = null;
    renderizarProductosCarnicosConfigurados(1);
    mostrarEstadoConfiguracionCarnicos(
        "Lista limpia. Presiona Guardar para conservar cambios.",
        "warning"
    );
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


function cantidadSugeridaProducto(producto) {
    return Number(producto?.cantidad_resultante || 0);
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


function restaurarProductoSeleccionadoComoOrigen(usarOrigenConfigurado = true) {
    const productoIdInput = document.getElementById("productoOrigenId");
    const resultadoOrigen = document.getElementById("resultadoOrigen");
    const productoOrigen = (
        usarOrigenConfigurado && origenConfiguradoActual
            ? origenConfiguradoActual
            : productoSeleccionadoOriginal
    );

    if (!productoOrigen) {
        return;
    }

    productoOrigenSeleccionado = productoOrigen;

    if (productoIdInput) {
        productoIdInput.value = String(productoOrigen.id);
    }

    actualizarTarjetaOrigen(productoOrigen);

    if (resultadoOrigen) {
        resultadoOrigen.className = "seleccion-origen";
        resultadoOrigen.textContent =
            `Producto origen seleccionado: ${productoOrigen.categoria}`;
    }

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
    productosResultantesDisponibles = [];
    origenConfiguradoActual = null;
    configuracionUsuarioActual = null;
    tipoRelacionActual = null;
    tipoTransformacionActual = TIPO_TRANSFORMACION_CONFIGURADA;
    componentesFormulaActual = [];
    contenedor.replaceChildren();
    contenedor.textContent = "Cargando productos resultantes...";

    try {
        const datos = await consultarProductosResultantes(productoId);
        productosResultantesDisponibles = datos.productos || [];
        origenConfiguradoActual = datos.producto_origen || null;
        configuracionUsuarioActual = datos.configuracion || null;
        tipoRelacionActual = datos.tipo_relacion || null;
        componentesFormulaActual = datos.componentes || [];
        configurarTipoTransformacion(
            productosResultantesDisponibles.length > 0
        );
        renderizarProductosResultantes();
    } catch (error) {
        contenedor.textContent = error.message;
    }
}


function obtenerTipoTransformacionSeleccionado() {
    return tipoTransformacionActual || TIPO_TRANSFORMACION_CONFIGURADA;
}


function configurarTipoTransformacion(tieneReceta) {
    tipoTransformacionActual = tieneReceta
        ? TIPO_TRANSFORMACION_CONFIGURADA
        : TIPO_PRODUCTO_FINAL;
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
    configurarEncabezadoResultantes("Productos resultantes", true);
    productoYaTransformadoSeleccionado =
        tipoTransformacion === TIPO_PRODUCTO_FINAL;

    if (productoYaTransformadoSeleccionado) {
        restaurarProductoSeleccionadoComoOrigen(false);
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
        actualizarModuloProductoActual();
        return;
    }

    restaurarProductoSeleccionadoComoOrigen();

    if (productosResultantesDisponibles.length === 0) {
        mostrarMensajeResultantes(
            "Este producto no tiene una transformación configurada."
        );
        actualizarBalance();
        actualizarModuloProductoActual();
        return;
    }

    if (
        tipoRelacionActual === "configuracion_usuario" ||
        tipoRelacionActual === "formula_producto"
    ) {
        productosResultantesDisponibles.forEach(function (producto) {
            agregarProductoResultante(producto);
        });
        actualizarBalance();
        actualizarModuloProductoActual();
        return;
    }

    agregarProductoResultante();
    actualizarBalance();
    actualizarModuloProductoActual();
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
    componentesConfiguracionDraft = [];
    resultantesConfiguracionDraft = [];
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
    actualizarModuloProductoActual();
}


async function seleccionarProductoOrigenConfiguracion(producto) {
    const productoIdInput = document.getElementById("productoOrigenId");
    const cantidadOrigenInput = document.getElementById("cantidadOrigen");
    const resultado = document.getElementById("resultadoConfiguracion");

    productoSeleccionadoOriginal = producto;
    productoOrigenSeleccionado = producto;
    componentesConfiguracionDraft = [];
    resultantesConfiguracionDraft = [];

    if (productoIdInput) {
        productoIdInput.value = producto.id;
    }

    if (cantidadOrigenInput) {
        cantidadOrigenInput.value = "0";
    }

    actualizarTarjetaOrigen(producto);
    reiniciarLimiteMerma();

    if (resultado) {
        resultado.className = "result-container";
        resultado.textContent =
            `Origen de configuracion: ${textoProductoRegistro(producto)}.`;
    }

    await cargarProductosResultantes(producto.id);
    sincronizarDraftConfiguracionDesdeContexto();
    renderizarEditorComponentesConfiguracion();
    renderizarEditorResultantesConfiguracion();
    actualizarResumenConfiguracion();
    actualizarModuloProductoActual();
}


function mostrarErrorConfiguracion(mensaje) {
    const resultado = document.getElementById("resultadoConfiguracion");

    if (resultado) {
        resultado.className = "error-card";
        resultado.textContent = mensaje;
    }
}


function agregarProductoAConfiguracion(producto, tipo) {
    const productoNormalizado = normalizarProductoConfiguracion(producto);

    if (!productoNormalizado?.id) {
        mostrarErrorConfiguracion("Producto no valido.");
        return;
    }

    if (!productoOrigenSeleccionado && tipo !== "origen") {
        mostrarErrorConfiguracion(
            "Primero define el producto origen de la configuracion."
        );
        return;
    }

    if (tipo === "componente") {
        componentesConfiguracionDraft =
            obtenerComponentesEditorConfiguracion();

        if (
            componentesConfiguracionDraft.some(function (detalle) {
                return Number(detalle.producto_id) ===
                    Number(productoNormalizado.id);
            })
        ) {
            mostrarErrorConfiguracion("Ese insumo ya esta agregado.");
            return;
        }

        componentesConfiguracionDraft.push(
            crearDetalleConfiguracion(
                productoNormalizado,
                "",
                {
                    unidad: productoNormalizado.unidad || "KILO",
                    es_producto_base: false,
                    tipo_componente: "INSUMO",
                    participa_balance: false,
                    orden: componentesConfiguracionDraft.length + 1
                }
            )
        );
        renderizarEditorComponentesConfiguracion();
        actualizarResumenConfiguracion();
        return;
    }

    if (tipo === "resultante") {
        resultantesConfiguracionDraft =
            obtenerResultantesEditorConfiguracion();

        if (
            resultantesConfiguracionDraft.some(function (detalle) {
                return Number(detalle.producto_id) ===
                    Number(productoNormalizado.id);
            })
        ) {
            mostrarErrorConfiguracion("Ese resultante ya esta agregado.");
            return;
        }

        resultantesConfiguracionDraft.push(
            crearDetalleConfiguracion(
                productoNormalizado,
                "",
                {
                    unidad: "KILO",
                    participa_balance: true,
                    orden: resultantesConfiguracionDraft.length + 1
                }
            )
        );
        renderizarEditorResultantesConfiguracion();
        actualizarResumenConfiguracion();
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
            const cantidadBase = cantidadSugeridaProducto(producto);
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

        const cantidadBase = cantidadSugeridaProducto(
            productoPreseleccionado
        );
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


function obtenerComponentesFormulaParaRegistro(productosResultantes) {
    if (componentesFormulaActual.length === 0) {
        return [];
    }

    const productoPrincipal = productosResultantes[0];
    const referencia = productosResultantesDisponibles[0];
    const cantidadCapturada = Number(productoPrincipal?.cantidad || 0);
    let cantidadReferencia = Number(
        referencia?.cantidad_resultante ||
        referencia?.cantidad_origen ||
        0
    );
    let cantidadCapturadaReferencia = cantidadCapturada;

    if (
        tipoRelacionActual === "configuracion_usuario" &&
        Number(configuracionUsuarioActual?.cantidad_base || 0) > 0
    ) {
        cantidadReferencia = Number(
            configuracionUsuarioActual.cantidad_base
        );
        cantidadCapturadaReferencia = Number(
            document.getElementById("cantidadOrigen")?.value ||
            cantidadCapturada ||
            0
        );
    }

    const factor = cantidadReferencia > 0
        ? cantidadCapturadaReferencia / cantidadReferencia
        : 1;

    return componentesFormulaActual.map(function (componente) {
        const cantidad = Number(componente.cantidad || 0) * factor;
        const esProductoBase = Boolean(componente.es_producto_base);

        return {
            producto_id: Number(componente.producto_id || componente.id),
            cantidad: cantidad.toFixed(6),
            unidad: componente.unidad || "KILO",
            es_producto_base: esProductoBase,
            tipo_componente: (
                componente.tipo_componente ||
                (esProductoBase ? "PRODUCTO_BASE" : "INSUMO")
            ),
            participa_balance: (
                componente.participa_balance ?? esProductoBase
            )
        };
    }).filter(function (componente) {
        return componente.producto_id && Number(componente.cantidad) > 0;
    });
}


function textoProductoRegistro(producto) {
    if (!producto) {
        return "Producto no encontrado";
    }

    return `${producto.nombre} | ${producto.clave}`;
}


function productoDesdeDetalleConfiguracion(detalle) {
    return detalle?.producto || detalle || null;
}


function idProductoDetalleConfiguracion(detalle) {
    const producto = productoDesdeDetalleConfiguracion(detalle);

    return Number(detalle?.producto_id || producto?.id || 0);
}


function normalizarProductoConfiguracion(producto) {
    if (!producto) {
        return null;
    }

    return {
        id: Number(producto.id || producto.producto_id || 0),
        clave: producto.clave || producto.ProductKey || "",
        nombre: producto.nombre || producto.ProductName || "",
        categoria: producto.categoria || producto.Category1 || "",
        unidad: producto.unidad || producto.Unit || "KILO",
        existencia: producto.existencia || producto.QtyPresent || 0,
        merma_estimada: producto.merma_estimada || null
    };
}


function crearDetalleConfiguracion(producto, cantidad = "", extras = {}) {
    const productoNormalizado = normalizarProductoConfiguracion(producto);
    const unidad = extras.unidad || productoNormalizado?.unidad || "KILO";

    return {
        producto: productoNormalizado,
        producto_id: Number(productoNormalizado?.id || 0),
        cantidad,
        cantidad_referencia: extras.cantidad_referencia ?? cantidad,
        unidad,
        participa_balance: extras.participa_balance ?? true,
        es_producto_base: extras.es_producto_base ?? false,
        tipo_componente: extras.tipo_componente || "INSUMO",
        orden: extras.orden || 1
    };
}


function detalleComponenteDesdeApi(componente, indice) {
    return crearDetalleConfiguracion(
        {
            id: componente.producto_id || componente.id,
            clave: componente.clave,
            nombre: componente.nombre,
            categoria: componente.categoria,
            unidad: componente.unidad
        },
        componente.cantidad,
        {
            unidad: componente.unidad || "KILO",
            es_producto_base: Boolean(componente.es_producto_base),
            tipo_componente: (
                componente.tipo_componente ||
                (
                    componente.es_producto_base
                        ? "PRODUCTO_BASE"
                        : "INSUMO"
                )
            ),
            participa_balance: (
                componente.participa_balance ??
                Boolean(componente.es_producto_base)
            ),
            cantidad_referencia: (
                componente.cantidad_referencia ??
                componente.cantidad
            ),
            orden: componente.orden || indice + 1
        }
    );
}


function esDetalleProductoBaseConfiguracion(detalle, indice = 0) {
    const tipo = String(detalle?.tipo_componente || "").toUpperCase();
    const productoId = idProductoDetalleConfiguracion(detalle);
    const productoOrigenId = Number(
        configuracionEditando?.producto_origen?.id ||
        productoOrigenSeleccionado?.id ||
        0
    );

    return Boolean(detalle?.es_producto_base) ||
        tipo === "PRODUCTO_BASE" ||
        (
            indice === 0 &&
            productoId &&
            productoOrigenId &&
            Number(productoId) === productoOrigenId
        );
}


function obtenerProductoDetalleConfiguracion(productoId) {
    const productos = [
        ...(configuracionEditando?.productos_resultantes || []),
        ...(configuracionEditando?.componentes || []),
        ...resultantesConfiguracionDraft,
        ...componentesConfiguracionDraft
    ];

    return productos
        .map(productoDesdeDetalleConfiguracion)
        .find(function (producto) {
            return Number(producto?.id) === Number(productoId);
        });
}


function obtenerProductoConfiguracionPorId(productoId) {
    return obtenerProductoDisponible(productoId) ||
        obtenerProductoDetalleConfiguracion(productoId) ||
        (
            Number(productoOrigenSeleccionado?.id) === Number(productoId)
                ? productoOrigenSeleccionado
                : null
        ) ||
        (
            Number(productoSeleccionadoOriginal?.id) === Number(productoId)
                ? productoSeleccionadoOriginal
                : null
        );
}


function sincronizarResultantesDraftDesdeCaptura() {
    if (configuracionEditando || resultantesConfiguracionDraft.length > 0) {
        return;
    }

    resultantesConfiguracionDraft = obtenerProductosResultantes()
        .filter(function (producto) {
            return producto.producto_id && Number(producto.cantidad) > 0;
        })
        .map(function (producto, indice) {
            return crearDetalleConfiguracion(
                obtenerProductoConfiguracionPorId(producto.producto_id),
                producto.cantidad,
                {
                    unidad: producto.unidad || "KILO",
                    participa_balance: true,
                    orden: indice + 1
                }
            );
        });
}


function sincronizarComponentesDraftDesdeContexto() {
    if (configuracionEditando || componentesConfiguracionDraft.length > 0) {
        return;
    }

    if (componentesFormulaActual.length > 0) {
        componentesConfiguracionDraft = componentesFormulaActual.map(
            detalleComponenteDesdeApi
        );
        return;
    }

    if (!productoOrigenSeleccionado) {
        return;
    }

    const cantidadBase = document.getElementById("configCantidadBase");
    const cantidadOrigen = document.getElementById("cantidadOrigen");
    const unidad = productoOrigenSeleccionado.unidad || "KILO";
    const cantidad = leerCantidadUnidad(
        cantidadBase?.value || cantidadOrigen?.value || "0",
        unidad
    );

    componentesConfiguracionDraft = [
        crearDetalleConfiguracion(
            productoOrigenSeleccionado,
            cantidad > 0 ? cantidad.toFixed(4) : "",
            {
                unidad,
                es_producto_base: true,
                tipo_componente: "PRODUCTO_BASE",
                participa_balance: true,
                orden: 1
            }
        )
    ];
}


function sincronizarDraftConfiguracionDesdeContexto() {
    sincronizarResultantesDraftDesdeCaptura();
    sincronizarComponentesDraftDesdeContexto();
}


function resumenDetallesConfiguracion(detalles, mensajeVacio) {
    const productos = detalles
        .filter(function (detalle) {
            return (
                idProductoDetalleConfiguracion(detalle) &&
                Number(detalle.cantidad || 0) > 0
            );
        })
        .map(function (detalle) {
            const producto = productoDesdeDetalleConfiguracion(detalle) || {
                nombre: `Producto ${idProductoDetalleConfiguracion(detalle)}`,
                clave: idProductoDetalleConfiguracion(detalle)
            };

            return (
                `${textoProductoRegistro(producto)} ` +
                `(${formatearCantidadUnidad(
                    detalle.cantidad,
                    detalle.unidad || producto.unidad
                )})`
            );
        });

    return productos.length ? productos.join(", ") : mensajeVacio;
}


function resumenResultantesCorto(detalles) {
    const productos = detalles.filter(function (detalle) {
        return (
            idProductoDetalleConfiguracion(detalle) &&
            Number(detalle.cantidad || 0) > 0
        );
    });
    const totalKilos = productos.reduce(function (total, detalle) {
        const producto = productoDesdeDetalleConfiguracion(detalle);
        const unidad = detalle.unidad || producto?.unidad || "KILO";

        return total + (
            normalizarUnidad(unidad) === "KILO"
                ? Number(detalle.cantidad || 0)
                : 0
        );
    }, 0);

    if (productos.length === 0) {
        return "Sin productos capturados";
    }

    return (
        `${productos.length} resultante` +
        `${productos.length === 1 ? "" : "s"}` +
        `${totalKilos > 0 ? ` (${formatearKg(totalKilos)})` : ""}`
    );
}


function actualizarResumenConfiguracion() {
    const origen = document.getElementById("configOrigenSeleccionado");
    const cantidadBase = document.getElementById("configCantidadBaseVista");
    const resultantes = document.getElementById("configResultantesVista");
    const nombre = document.getElementById("configNombre");
    const cantidadOrigen = document.getElementById("cantidadOrigen");
    const cantidadBaseInput = document.getElementById("configCantidadBase");
    const productoBase = (
        configuracionEditando?.producto_origen ||
        productoOrigenSeleccionado
    );

    if (!origen || !cantidadBase || !resultantes) {
        return;
    }

    if (!productoBase) {
        origen.textContent = "Selecciona un producto desde Productos";
        cantidadBase.textContent = "0 kg";
        resultantes.textContent = "Sin productos capturados";
        return;
    }

    origen.textContent = textoProductoRegistro(productoBase);

    if (!configuracionEditando && nombre && !nombre.value.trim()) {
        nombre.value = productoBase.nombre || "";
    }

    if (
        !configuracionEditando &&
        cantidadBaseInput &&
        cantidadBaseInput.dataset.automatica !== "0"
    ) {
        const pesoCalculado = leerCantidadKg(cantidadOrigen?.value || "0");
        cantidadBaseInput.value = pesoCalculado > 0
            ? formatearKg(pesoCalculado)
            : "";
    }

    const pesoBase = leerCantidadKg(
        cantidadBaseInput?.value ||
        cantidadOrigen?.value ||
        "0"
    );
    cantidadBase.textContent = formatearKg(pesoBase);

    resultantes.textContent = resumenResultantesCorto(
        obtenerResultantesEditorConfiguracion()
    );
}


function crearIndicadorModulo(etiqueta, valor, destacado = false) {
    const indicador = crearIndicadorRegistro(etiqueta, valor);

    if (destacado) {
        indicador.classList.add("summary-highlight");
    }

    return indicador;
}


function renderizarIndicadoresModulo(indicadores = {}) {
    const contenedor = document.getElementById("moduloIndicadores");

    if (!contenedor) {
        return;
    }

    contenedor.replaceChildren(
        crearIndicadorModulo(
            "Transformaciones del mes",
            String(indicadores.transformaciones || 0)
        ),
        crearIndicadorModulo(
            "Kilos procesados",
            formatearKg(indicadores.kilos_procesados)
        ),
        crearIndicadorModulo(
            "Merma acumulada",
            formatearKg(indicadores.merma_acumulada)
        ),
        crearIndicadorModulo(
            "Rendimiento",
            formatearPorcentajeCorto(indicadores.rendimiento),
            true
        )
    );
}


function claseEstadoErp(estado) {
    return `estado-${String(estado || "sin_estado")
        .toLowerCase()
        .replaceAll("_", "-")}`;
}


function crearRegistroModulo(registro) {
    const item = document.createElement("article");
    const encabezado = document.createElement("div");
    const folio = document.createElement("strong");
    const fecha = document.createElement("span");
    const estado = document.createElement("span");
    const producto = document.createElement("p");
    const detalle = document.createElement("div");

    item.className = "modulo-registro";
    encabezado.className = "modulo-registro-encabezado";
    estado.className = `estado-badge ${claseEstadoErp(registro.estado_erp)}`;
    detalle.className = "modulo-registro-detalle";

    folio.textContent = `Folio ${registro.folio}`;
    fecha.textContent = registro.fecha || "-";
    estado.textContent = textoEstadoErp(registro.estado_erp);
    producto.textContent = textoProductoRegistro(registro.producto_origen);

    [
        ["Salida", formatearKg(registro.cantidad_origen)],
        ["Entrada", formatearKg(registro.total_entrada)],
        ["Merma", formatearKg(registro.peso_merma)],
        ["ERP", textoMovimientosErp(registro)]
    ].forEach(function ([etiqueta, valor]) {
        const bloque = document.createElement("span");
        const titulo = document.createElement("b");
        const contenido = document.createElement("span");

        titulo.textContent = etiqueta;
        contenido.textContent = valor;
        bloque.append(titulo, contenido);
        detalle.appendChild(bloque);
    });

    encabezado.append(folio, fecha, estado);
    item.append(encabezado, producto, detalle);
    return item;
}


function renderizarUltimosRegistrosModulo(registros) {
    const contenedor = document.getElementById("moduloUltimosRegistros");

    if (!contenedor) {
        return;
    }

    contenedor.replaceChildren();

    if (!registros.length) {
        contenedor.textContent = "Aun no hay transformaciones registradas.";
        return;
    }

    const lista = document.createElement("div");
    lista.className = "modulo-registros-lista";

    registros.slice(0, 3).forEach(function (registro) {
        lista.appendChild(crearRegistroModulo(registro));
    });

    contenedor.appendChild(lista);
}


function actualizarModuloProductoActual() {
    const contenedor = document.getElementById("moduloProductoActual");

    if (!contenedor) {
        return;
    }

    contenedor.replaceChildren();

    if (!productoSeleccionadoOriginal) {
        contenedor.className = "modulo-producto-actual is-empty";
        contenedor.textContent = "Sin producto seleccionado.";
        return;
    }

    const productoTrabajo = (
        productoOrigenSeleccionado ||
        productoSeleccionadoOriginal
    );
    const titulo = document.createElement("strong");
    const subtitulo = document.createElement("span");
    const datos = document.createElement("div");
    const acciones = document.createElement("div");
    const abrirCaptura = document.createElement("button");
    const abrirConfiguracion = document.createElement("button");

    contenedor.className = "modulo-producto-actual";
    datos.className = "modulo-producto-datos";
    acciones.className = "modulo-producto-acciones";

    titulo.textContent = textoProductoRegistro(productoSeleccionadoOriginal);
    subtitulo.textContent = (
        productoTrabajo.id !== productoSeleccionadoOriginal.id
            ? `Origen: ${textoProductoRegistro(productoTrabajo)}`
            : productoTrabajo.categoria || "Producto seleccionado"
    );

    [
        ["Categoria", productoTrabajo.categoria || "-"],
        ["Unidad", productoTrabajo.unidad || "-"],
        ["Existencia", formatearCantidadCorta(productoTrabajo.existencia)],
        [
            "Merma ref.",
            formatearPorcentajeCorto(
                productoTrabajo.merma_estimada?.porcentaje || 0
            )
        ]
    ].forEach(function ([etiqueta, valor]) {
        const bloque = document.createElement("div");
        const label = document.createElement("span");
        const contenido = document.createElement("b");

        label.textContent = etiqueta;
        contenido.textContent = valor;
        bloque.append(label, contenido);
        datos.appendChild(bloque);
    });

    abrirCaptura.type = "button";
    abrirCaptura.textContent = "Continuar captura";
    abrirCaptura.addEventListener("click", function () {
        mostrarSeccion("transformacion");
    });

    abrirConfiguracion.type = "button";
    abrirConfiguracion.textContent = "Guardar configuracion";
    abrirConfiguracion.className = "modulo-accion-secundaria";
    abrirConfiguracion.addEventListener("click", function () {
        abrirModalConfiguraciones();
    });

    acciones.append(abrirCaptura, abrirConfiguracion);
    contenedor.append(titulo, subtitulo, datos, acciones);
}


async function cargarModuloCarnico() {
    const registros = document.getElementById("moduloUltimosRegistros");

    if (registros) {
        registros.textContent = "Cargando registros...";
    }

    try {
        const parametros = new URLSearchParams({
            pagina: "1",
            limite: "5"
        });
        const { respuesta, datos } = await solicitarJson(
            `/transformaciones/?${parametros}`,
            {
                credentials: "same-origin"
            }
        );

        if (!respuesta.ok) {
            throw new Error(
                datos.detail || "No fue posible consultar el módulo"
            );
        }

        renderizarIndicadoresModulo(datos.indicadores || {});
        renderizarUltimosRegistrosModulo(datos.registros || []);
    } catch (error) {
        if (registros) {
            registros.textContent = error.message;
        }
    }
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
                : "Transformación configurada",
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
    const idSolicitud = ++solicitudHistorialActual;

    if (!contenedor) {
        return;
    }

    contenedor.textContent = "Cargando registros...";

    try {
        const parametros = new URLSearchParams({
            pagina: String(pagina),
            limite: String(REGISTROS_POR_PAGINA)
        });
        const { respuesta, datos } = await solicitarJson(
            `/transformaciones/?${parametros}`,
            {
                credentials: "same-origin"
            }
        );

        if (idSolicitud !== solicitudHistorialActual) {
            return;
        }

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
        if (idSolicitud === solicitudHistorialActual) {
            contenedor.textContent = error.message;
        }
    }
}


function actualizarEstadoFormularioConfiguracion() {
    const titulo = document.getElementById("tituloFormularioConfiguracion");
    const ayuda = document.getElementById("ayudaFormularioConfiguracion");
    const boton = document.getElementById("botonGuardarConfiguracion");
    const cancelar = document.getElementById(
        "botonCancelarEdicionConfiguracion"
    );

    if (titulo) {
        titulo.textContent = configuracionEditando
            ? "Editar configuracion"
            : "Guardar configuracion";
    }

    if (ayuda) {
        ayuda.textContent = configuracionEditando
            ? (
                "Ajusta el peso base y las cantidades configuradas " +
                "para esta transformacion."
            )
            : (
                "Guarda esta relacion para reutilizarla en " +
                "futuras transformaciones."
            );
    }

    if (boton) {
        boton.textContent = configuracionEditando
            ? "Actualizar configuracion"
            : "Guardar configuracion";
    }

    if (cancelar) {
        cancelar.hidden = !configuracionEditando;
    }
}


function obtenerInputProductoBaseConfiguracion() {
    return Array.from(
        document.querySelectorAll(".config-componente-cantidad")
    ).find(function (input) {
        return esInputProductoBaseConfiguracion(input);
    }) || null;
}


function obtenerInputResultantePrincipalConfiguracion() {
    return document.querySelector(".config-resultante-cantidad");
}


function esInputProductoBaseConfiguracion(input) {
    return input.dataset.esProductoBase === "true" ||
        String(input.dataset.tipoComponente || "").toUpperCase() ===
            "PRODUCTO_BASE";
}


function obtenerFactorProductoBaseConfiguracion() {
    const inputBase = obtenerInputProductoBaseConfiguracion();

    if (!inputBase) {
        return 1;
    }

    const unidadBase = inputBase.dataset.unidad || "KILO";
    const cantidadReferencia = Number(
        inputBase.dataset.cantidadReferencia || 0
    );
    const cantidadActual = leerCantidadUnidad(inputBase.value, unidadBase);

    if (cantidadReferencia <= 0 || cantidadActual <= 0) {
        return 1;
    }

    return cantidadActual / cantidadReferencia;
}


function sincronizarCantidadBaseConfiguracion(inputBase) {
    const cantidadBase = document.getElementById("configCantidadBase");

    if (!cantidadBase || !inputBase) {
        return;
    }

    cantidadBase.value = inputBase.value;
    cantidadBase.dataset.automatica = "0";
}


function escalarComponentesConfiguracion(factor, incluirProductoBase) {
    if (!Number.isFinite(factor) || factor <= 0) {
        return;
    }

    document.querySelectorAll(".config-componente-cantidad").forEach(
        function (input) {
            const esProductoBase = esInputProductoBaseConfiguracion(input);

            if (esProductoBase && !incluirProductoBase) {
                return;
            }

            const unidad = input.dataset.unidad || "KILO";
            const cantidadReferencia = Number(
                input.dataset.cantidadReferencia || 0
            );

            if (cantidadReferencia <= 0) {
                return;
            }

            input.value = formatearCantidadUnidad(
                cantidadReferencia * factor,
                unidad
            );

            if (esProductoBase) {
                sincronizarCantidadBaseConfiguracion(input);
            }
        }
    );
}


function actualizarReferenciaInsumoConfiguracion(input) {
    const unidad = input.dataset.unidad || "KILO";
    const cantidadActual = leerCantidadUnidad(input.value, unidad);
    const factor = obtenerFactorProductoBaseConfiguracion();

    if (cantidadActual <= 0 || factor <= 0) {
        return;
    }

    input.dataset.cantidadReferencia = String(cantidadActual / factor);
}


function escalarInsumosDesdeProductoBase(inputBase) {
    const unidadBase = inputBase.dataset.unidad || "KILO";
    const cantidadReferenciaBase = Number(
        inputBase.dataset.cantidadReferencia || 0
    );
    const cantidadActualBase = leerCantidadUnidad(inputBase.value, unidadBase);

    sincronizarCantidadBaseConfiguracion(inputBase);

    if (cantidadReferenciaBase <= 0 || cantidadActualBase <= 0) {
        actualizarResumenConfiguracion();
        return;
    }

    const factor = cantidadActualBase / cantidadReferenciaBase;

    escalarComponentesConfiguracion(factor, false);

    actualizarResumenConfiguracion();
}


function escalarComponentesDesdeResultantePrincipal(inputResultante) {
    const unidad = inputResultante.dataset.unidad || "KILO";
    const cantidadReferencia = Number(
        inputResultante.dataset.cantidadReferencia || 0
    );
    const cantidadActual = leerCantidadUnidad(inputResultante.value, unidad);

    if (cantidadReferencia <= 0 || cantidadActual <= 0) {
        actualizarResumenConfiguracion();
        return;
    }

    escalarComponentesConfiguracion(
        cantidadActual / cantidadReferencia,
        true
    );
    actualizarResumenConfiguracion();
}


function renderizarEditorComponentesConfiguracion() {
    const contenedor = document.getElementById(
        "editorComponentesConfiguracion"
    );

    if (!contenedor) {
        return;
    }

    contenedor.replaceChildren();

    const titulo = document.createElement("h4");
    titulo.className = "config-editor-title";
    titulo.textContent = "Ingredientes e insumos configurados";
    contenedor.appendChild(titulo);

    if (componentesConfiguracionDraft.length === 0) {
        const ayuda = document.createElement("p");
        ayuda.className = "panel-help config-editor-help";
        ayuda.textContent =
            "Selecciona un producto desde Productos para cargar sus insumos.";
        contenedor.appendChild(ayuda);
        return;
    }

    const tabla = document.createElement("table");
    const encabezado = document.createElement("thead");
    const cuerpo = document.createElement("tbody");

    tabla.className =
        "tabla-resultantes config-editor-tabla config-componentes-tabla";
    encabezado.innerHTML = `
        <tr>
            <th>Producto</th>
            <th>Tipo</th>
            <th>Unidad</th>
            <th>Peso / cantidad</th>
        </tr>
    `;

    componentesConfiguracionDraft.forEach(function (detalle, indice) {
        const fila = document.createElement("tr");
        const producto = productoDesdeDetalleConfiguracion(detalle) || {};
        const unidad = detalle.unidad || producto.unidad || "KILO";
        const esProductoBase = esDetalleProductoBaseConfiguracion(
            detalle,
            indice
        );
        const celdaProducto = document.createElement("td");
        const celdaTipo = document.createElement("td");
        const celdaUnidad = document.createElement("td");
        const celdaCantidad = document.createElement("td");
        const cantidad = document.createElement("input");

        fila.className = "config-componente-fila";
        celdaProducto.textContent = textoProductoRegistro(producto);
        celdaTipo.textContent = esProductoBase ? "Producto base" : "Insumo";
        celdaUnidad.textContent = unidad;
        cantidad.type = "text";
        cantidad.inputMode = "decimal";
        cantidad.className = "config-componente-cantidad";
        cantidad.value = formatearCantidadUnidad(detalle.cantidad, unidad);
        cantidad.dataset.productoId = detalle.producto_id || producto.id;
        cantidad.dataset.unidad = unidad;
        cantidad.dataset.esProductoBase = String(esProductoBase);
        cantidad.dataset.cantidadReferencia = String(
            detalle.cantidad_referencia ?? detalle.cantidad ?? 0
        );
        cantidad.dataset.tipoComponente = (
            detalle.tipo_componente ||
            (esProductoBase ? "PRODUCTO_BASE" : "INSUMO")
        );
        cantidad.dataset.participaBalance = String(
            detalle.participa_balance ?? esProductoBase
        );
        cantidad.dataset.orden = String(detalle.orden || indice + 1);
        cantidad.addEventListener("input", function () {
            if (esProductoBase) {
                escalarInsumosDesdeProductoBase(cantidad);
                return;
            }

            actualizarReferenciaInsumoConfiguracion(cantidad);
            actualizarResumenConfiguracion();
        });

        celdaCantidad.appendChild(cantidad);
        fila.append(
            celdaProducto,
            celdaTipo,
            celdaUnidad,
            celdaCantidad
        );
        cuerpo.appendChild(fila);
    });

    tabla.append(encabezado, cuerpo);
    contenedor.appendChild(tabla);
}


function obtenerComponentesEditorConfiguracion() {
    return Array.from(
        document.querySelectorAll(".config-componente-fila")
    ).map(function (fila, indice) {
        const input = fila.querySelector(".config-componente-cantidad");
        const unidad = input.dataset.unidad || "KILO";
        const esProductoBase = esInputProductoBaseConfiguracion(input);

        return {
            producto_id: Number(input.dataset.productoId || 0),
            cantidad: leerCantidadUnidad(input.value, unidad).toFixed(4),
            cantidad_referencia: Number(
                input.dataset.cantidadReferencia || 0
            ).toFixed(4),
            unidad,
            es_producto_base: esProductoBase,
            tipo_componente: (
                input.dataset.tipoComponente ||
                (esProductoBase ? "PRODUCTO_BASE" : "INSUMO")
            ),
            participa_balance: input.dataset.participaBalance !== "false",
            orden: Number(input.dataset.orden || indice + 1),
            producto: obtenerProductoConfiguracionPorId(
                input.dataset.productoId
            )
        };
    });
}


function renderizarEditorResultantesConfiguracion() {
    const contenedor = document.getElementById(
        "editorResultantesConfiguracion"
    );

    if (!contenedor) {
        return;
    }

    contenedor.replaceChildren();

    const productos = resultantesConfiguracionDraft;
    const titulo = document.createElement("h4");

    titulo.className = "config-editor-title";
    titulo.textContent = "Productos resultantes configurados";
    contenedor.appendChild(titulo);

    if (productos.length === 0) {
        const ayuda = document.createElement("p");
        ayuda.className = "panel-help config-editor-help";
        ayuda.textContent =
            "Selecciona un producto desde Productos para cargar sus resultantes.";
        contenedor.appendChild(ayuda);
        return;
    }

    const tabla = document.createElement("table");
    const encabezado = document.createElement("thead");
    const cuerpo = document.createElement("tbody");

    tabla.className =
        "tabla-resultantes config-editor-tabla config-resultantes-tabla";
    encabezado.innerHTML = `
        <tr>
            <th>Producto</th>
            <th>Unidad</th>
            <th>Peso / cantidad</th>
        </tr>
    `;

    productos.forEach(function (detalle, indice) {
        const fila = document.createElement("tr");
        const producto = productoDesdeDetalleConfiguracion(detalle) || {};
        const unidad = detalle.unidad || producto.unidad || "KILO";
        const celdaProducto = document.createElement("td");
        const celdaUnidad = document.createElement("td");
        const celdaCantidad = document.createElement("td");
        const cantidad = document.createElement("input");

        fila.className = "config-resultante-fila";
        celdaProducto.textContent = textoProductoRegistro(producto);
        celdaUnidad.textContent = unidad;
        cantidad.type = "text";
        cantidad.inputMode = "decimal";
        cantidad.className = "config-resultante-cantidad";
        cantidad.value = formatearCantidadUnidad(detalle.cantidad, unidad);
        cantidad.dataset.productoId = producto.id;
        cantidad.dataset.unidad = unidad;
        cantidad.dataset.cantidadReferencia = String(
            detalle.cantidad_referencia ?? detalle.cantidad ?? 0
        );
        cantidad.dataset.participaBalance = String(
            detalle.participa_balance ?? true
        );
        cantidad.dataset.orden = String(detalle.orden || indice + 1);
        cantidad.addEventListener("input", function () {
            if (indice === 0) {
                escalarComponentesDesdeResultantePrincipal(cantidad);
                return;
            }

            actualizarResumenConfiguracion();
        });

        celdaCantidad.appendChild(cantidad);
        fila.append(
            celdaProducto,
            celdaUnidad,
            celdaCantidad
        );
        cuerpo.appendChild(fila);
    });

    tabla.append(encabezado, cuerpo);
    contenedor.appendChild(tabla);
}


function obtenerResultantesEditorConfiguracion() {
    return Array.from(
        document.querySelectorAll(".config-resultante-fila")
    ).map(function (fila, indice) {
        const input = fila.querySelector(".config-resultante-cantidad");
        const unidad = input.dataset.unidad || "KILO";

        return {
            producto_id: Number(input.dataset.productoId || 0),
            cantidad: leerCantidadUnidad(input.value, unidad).toFixed(4),
            cantidad_referencia: Number(
                input.dataset.cantidadReferencia || 0
            ).toFixed(4),
            unidad,
            participa_balance: input.dataset.participaBalance !== "false",
            orden: Number(input.dataset.orden || indice + 1),
            producto: obtenerProductoConfiguracionPorId(
                input.dataset.productoId
            )
        };
    });
}


function cancelarEdicionConfiguracion() {
    const nombre = document.getElementById("configNombre");
    const cantidadBase = document.getElementById("configCantidadBase");
    const observaciones = document.getElementById("configObservaciones");
    const resultado = document.getElementById("resultadoConfiguracion");

    configuracionEditando = null;
    componentesConfiguracionDraft = [];
    resultantesConfiguracionDraft = [];

    if (nombre) {
        nombre.value = "";
    }

    if (cantidadBase) {
        cantidadBase.value = "";
        cantidadBase.dataset.automatica = "1";
    }

    if (observaciones) {
        observaciones.value = "";
    }

    if (resultado) {
        resultado.className = "";
        resultado.textContent = "";
    }

    actualizarEstadoFormularioConfiguracion();
    sincronizarDraftConfiguracionDesdeContexto();
    renderizarEditorComponentesConfiguracion();
    renderizarEditorResultantesConfiguracion();
    actualizarResumenConfiguracion();

    document.getElementById("tituloFormularioConfiguracion")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
    });
}


function editarConfiguracionTransformacion(configuracion) {
    const nombre = document.getElementById("configNombre");
    const cantidadBase = document.getElementById("configCantidadBase");
    const observaciones = document.getElementById("configObservaciones");
    const resultado = document.getElementById("resultadoConfiguracion");

    configuracionEditando = configuracion;
    componentesConfiguracionDraft = (configuracion.componentes || []).map(
        function (detalle, indice) {
            return crearDetalleConfiguracion(
                detalle.producto,
                detalle.cantidad,
                {
                    unidad: detalle.unidad || detalle.producto?.unidad,
                    es_producto_base: Boolean(detalle.es_producto_base),
                    tipo_componente: detalle.tipo_componente || "INSUMO",
                    participa_balance: (
                        detalle.participa_balance ??
                        Boolean(detalle.es_producto_base)
                    ),
                    orden: detalle.orden || indice + 1
                }
            );
        }
    );

    if (
        componentesConfiguracionDraft.length === 0 &&
        configuracion.producto_origen
    ) {
        componentesConfiguracionDraft = [
            crearDetalleConfiguracion(
                configuracion.producto_origen,
                configuracion.cantidad_base,
                {
                    unidad: (
                        configuracion.producto_origen.unidad || "KILO"
                    ),
                    es_producto_base: true,
                    tipo_componente: "PRODUCTO_BASE",
                    participa_balance: true,
                    orden: 1
                }
            )
        ];
    }

    resultantesConfiguracionDraft = (
        configuracion.productos_resultantes || []
    ).map(function (detalle, indice) {
        return crearDetalleConfiguracion(
            detalle.producto,
            detalle.cantidad,
            {
                unidad: detalle.unidad || detalle.producto?.unidad,
                participa_balance: detalle.participa_balance ?? true,
                orden: detalle.orden || indice + 1
            }
        );
    });

    if (nombre) {
        nombre.value = configuracion.nombre || "";
    }

    if (cantidadBase) {
        cantidadBase.dataset.automatica = "0";
        cantidadBase.value = formatearCantidadUnidad(
            configuracion.cantidad_base,
            configuracion.producto_origen?.unidad || "KILO"
        );
    }

    if (observaciones) {
        observaciones.value = configuracion.observaciones || "";
    }

    if (resultado) {
        resultado.className = "result-container";
        resultado.textContent =
            `Editando configuracion ${configuracion.id}.`;
    }

    actualizarEstadoFormularioConfiguracion();
    renderizarEditorComponentesConfiguracion();
    renderizarEditorResultantesConfiguracion();
    actualizarResumenConfiguracion();
}


function validarConfiguracion(datos) {
    if (datos.nombre_transformacion.length < 3) {
        return "Captura un nombre para la configuracion.";
    }

    if (!datos.producto_origen_id) {
        return "Selecciona un producto desde la tabla de productos.";
    }

    if (Number(datos.cantidad_base) <= 0) {
        return "Captura el peso base de la configuracion.";
    }

    if (datos.productos_resultantes.length === 0) {
        return "Agrega al menos un producto resultante.";
    }

    if (datos.componentes.length === 0) {
        return "Agrega al menos un ingrediente o insumo.";
    }

    if (
        datos.productos_resultantes.some(function (producto) {
            return !producto.producto_id || Number(producto.cantidad) <= 0;
        })
    ) {
        return "Completa producto y cantidad en cada resultante.";
    }

    if (
        datos.componentes.some(function (componente) {
            return !componente.producto_id || Number(componente.cantidad) <= 0;
        })
    ) {
        return "Completa producto y cantidad en cada insumo.";
    }

    const ids = datos.productos_resultantes.map(function (producto) {
        return producto.producto_id;
    });

    if (new Set(ids).size !== ids.length) {
        return "No repitas productos resultantes.";
    }

    const idsComponentes = datos.componentes.map(function (componente) {
        return componente.producto_id;
    });

    if (new Set(idsComponentes).size !== idsComponentes.length) {
        return "No repitas ingredientes o insumos.";
    }

    return "";
}


function obtenerResultantesParaConfiguracion() {
    return obtenerResultantesEditorConfiguracion().map(
        function (producto, indice) {
            return {
                producto_id: producto.producto_id,
                cantidad: producto.cantidad,
                unidad: producto.unidad,
                participa_balance: producto.participa_balance,
                orden: producto.orden || indice + 1
            };
        }
    );
}


function obtenerComponentesParaConfiguracion(cantidadBaseValor, unidadBase) {
    return obtenerComponentesEditorConfiguracion().map(
        function (componente, indice) {
            const cantidad = (
                componente.es_producto_base &&
                Number(componente.cantidad) <= 0
            )
                ? Number(cantidadBaseValor || 0).toFixed(4)
                : componente.cantidad;

            return {
                producto_id: componente.producto_id,
                cantidad,
                unidad: componente.unidad || unidadBase || "KILO",
                es_producto_base: componente.es_producto_base,
                tipo_componente: componente.tipo_componente,
                participa_balance: componente.participa_balance,
                orden: componente.orden || indice + 1
            };
        }
    );
}


async function guardarConfiguracionTransformacion() {
    const resultado = document.getElementById("resultadoConfiguracion");
    const boton = document.getElementById("botonGuardarConfiguracion");
    const nombre = document.getElementById("configNombre");
    const cantidadOrigen = document.getElementById("cantidadOrigen");
    const cantidadBase = document.getElementById("configCantidadBase");
    const observaciones = document.getElementById("configObservaciones");

    if (!resultado || !nombre || !cantidadOrigen) {
        return;
    }

    const productoBase = (
        configuracionEditando?.producto_origen ||
        productoOrigenSeleccionado
    );
    const productoFormula = configuracionEditando
        ? configuracionEditando.producto_formula
        : productoSeleccionadoOriginal;
    const unidadBase = productoBase?.unidad || "KILO";
    sincronizarDraftConfiguracionDesdeContexto();
    componentesConfiguracionDraft = obtenerComponentesEditorConfiguracion();
    resultantesConfiguracionDraft = obtenerResultantesEditorConfiguracion();
    const cantidadBaseValor = leerCantidadUnidad(
        cantidadBase?.value || cantidadOrigen.value || "0",
        unidadBase
    ).toFixed(4);
    const datos = {
        nombre_transformacion: nombre.value.trim(),
        producto_origen_id: Number(productoBase?.id || 0),
        producto_formula_id: productoFormula?.id || null,
        cantidad_base: cantidadBaseValor,
        porcentaje_merma: configuracionEditando?.porcentaje_merma ?? null,
        observaciones: observaciones?.value.trim() || null,
        productos_resultantes: obtenerResultantesParaConfiguracion(),
        componentes: obtenerComponentesParaConfiguracion(
            cantidadBaseValor,
            unidadBase
        )
    };
    const estaEditando = Boolean(configuracionEditando);
    const mensaje = validarConfiguracion(datos);

    if (mensaje) {
        resultado.className = "error-card";
        resultado.textContent = mensaje;
        return;
    }

    resultado.className = "result-container";
    resultado.textContent = estaEditando
        ? "Actualizando configuracion..."
        : "Guardando configuracion...";

    if (boton) {
        boton.disabled = true;
        boton.textContent = estaEditando
            ? "Actualizando..."
            : "Guardando...";
    }

    try {
        const url = estaEditando
            ? `/configuraciones-transformacion/${configuracionEditando.id}`
            : "/configuraciones-transformacion/";
        const { respuesta, datos: respuestaDatos } = await solicitarJson(
            url,
            {
                method: estaEditando ? "PUT" : "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(datos)
            },
            TIEMPO_LIMITE_REGISTRO_MS
        );

        if (!respuesta.ok) {
            const detalle = Array.isArray(respuestaDatos.detail)
                ? respuestaDatos.detail[0]?.msg
                : respuestaDatos.detail;

            throw new Error(
                detalle || (
                    estaEditando
                        ? "No fue posible actualizar la configuracion"
                        : "No fue posible guardar la configuracion"
                )
            );
        }

        resultado.className = "success-card";
        resultado.textContent = estaEditando
            ? `Configuracion ${respuestaDatos.id} actualizada.`
            : `Configuracion guardada con folio ${respuestaDatos.id}.`;

        if (estaEditando) {
            configuracionEditando = null;
            componentesConfiguracionDraft = [];
            resultantesConfiguracionDraft = [];

            nombre.value = "";

            if (cantidadBase) {
                cantidadBase.value = "";
            }

            if (observaciones) {
                observaciones.value = "";
            }
        } else {
            componentesConfiguracionDraft = [];
            resultantesConfiguracionDraft = [];
            nombre.value = "";

            if (observaciones) {
                observaciones.value = "";
            }
        }

        if (cantidadBase) {
            cantidadBase.dataset.automatica = "1";
        }

        actualizarEstadoFormularioConfiguracion();
        sincronizarDraftConfiguracionDesdeContexto();
        renderizarEditorComponentesConfiguracion();
        renderizarEditorResultantesConfiguracion();
        actualizarResumenConfiguracion();
        await cargarConfiguracionesTransformacion(configuracionesPaginaActual);
    } catch (error) {
        resultado.className = "error-card";
        resultado.textContent = error.message;
    } finally {
        if (boton) {
            boton.disabled = false;
            boton.textContent = configuracionEditando
                ? "Actualizar configuracion"
                : "Guardar configuracion";
        }
    }
}
function resumenResultantesConfiguracion(configuracion) {
    const productos = (configuracion.productos_resultantes || []).filter(
        function (detalle) {
            return (
                idProductoDetalleConfiguracion(detalle) &&
                Number(detalle.cantidad || 0) > 0
            );
        }
    );

    if (productos.length === 0) {
        return "-";
    }

    return resumenResultantesCorto(productos);
}


function resumenComponentesConfiguracion(configuracion) {
    const componentes = (configuracion.componentes || []).filter(
        function (detalle) {
            return (
                idProductoDetalleConfiguracion(detalle) &&
                Number(detalle.cantidad || 0) > 0
            );
        }
    );

    if (componentes.length === 0) {
        return "-";
    }

    const productosBase = componentes.filter(function (detalle) {
        return Boolean(detalle.es_producto_base);
    }).length;
    const insumos = componentes.length - productosBase;
    const partes = [];

    if (insumos > 0) {
        partes.push(
            `${insumos} insumo${insumos === 1 ? "" : "s"}`
        );
    }

    if (productosBase > 0) {
        partes.push(
            `${productosBase} base${productosBase === 1 ? "" : "s"}`
        );
    }

    return partes.join(" + ");
}



function crearCeldaConfiguracionPrincipal(configuracion) {
    const celda = document.createElement("td");
    const nombre = document.createElement("strong");
    const id = document.createElement("small");

    nombre.textContent = (
        configuracion.nombre ||
        `Configuracion ${configuracion.id}`
    );
    id.className = "tabla-muted";
    id.textContent = `ID ${configuracion.id}`;
    celda.append(nombre, id);
    return celda;
}


function crearTablaConfiguraciones(configuraciones) {
    const tabla = document.createElement("table");
    const encabezado = document.createElement("thead");
    const cuerpo = document.createElement("tbody");

    tabla.className =
        "productos-tabla registros-tabla config-lista-tabla";
    encabezado.innerHTML = `
        <tr>
            <th>Configuracion</th>
            <th>Origen</th>
            <th>Salida base</th>
            <th>Insumos</th>
            <th>Resultantes</th>
            <th>Usuario</th>
            <th></th>
        </tr>
    `;

    configuraciones.forEach(function (configuracion) {
        const fila = document.createElement("tr");
        fila.appendChild(crearCeldaConfiguracionPrincipal(configuracion));

        const valores = [
            textoProductoRegistro(configuracion.producto_origen),
            formatearCantidadUnidad(
                configuracion.cantidad_base,
                configuracion.producto_origen?.unidad || "KILO"
            ),
            resumenComponentesConfiguracion(configuracion),
            resumenResultantesConfiguracion(configuracion),
            configuracion.usuario_creacion?.nombre || "-",
        ];

        valores.forEach(function (valor) {
            const celda = document.createElement("td");
            celda.textContent = valor ?? "";
            fila.appendChild(celda);
        });

        const celdaAcciones = document.createElement("td");
        const botonIngredientes = document.createElement("button");
        const botonEditar = document.createElement("button");

        botonIngredientes.type = "button";
        botonIngredientes.textContent = "Detalle";
        botonIngredientes.addEventListener("click", function () {
            verDetalleConfiguracion(configuracion);
        });
        botonEditar.type = "button";
        botonEditar.textContent = "Editar";
        botonEditar.addEventListener("click", function () {
            editarConfiguracionTransformacion(configuracion);
        });
        celdaAcciones.className = "acciones-tabla";
        celdaAcciones.appendChild(botonEditar);
        celdaAcciones.appendChild(botonIngredientes);
        fila.appendChild(celdaAcciones);
        cuerpo.appendChild(fila);
    });

    tabla.append(encabezado, cuerpo);
    return tabla;
}


async function cargarConfiguracionesTransformacion(pagina = 1) {
    const contenedor = document.getElementById("tablaConfiguraciones");

    if (!contenedor) {
        return;
    }

    contenedor.textContent = "Cargando configuraciones...";

    try {
        const parametros = new URLSearchParams({
            pagina: String(pagina),
            limite: String(CONFIGURACIONES_POR_PAGINA)
        });
        const { respuesta, datos } = await solicitarJson(
            `/configuraciones-transformacion/?${parametros}`,
            {
                credentials: "same-origin"
            }
        );

        if (!respuesta.ok) {
            throw new Error(
                datos.detail || "No fue posible consultar configuraciones"
            );
        }

        const configuraciones = datos.configuraciones || [];
        configuracionesPaginaActual = datos.pagina;
        contenedor.replaceChildren();

        if (configuraciones.length === 0) {
            contenedor.textContent =
                "Aun no hay configuraciones registradas.";
            return;
        }

        contenedor.appendChild(crearTablaConfiguraciones(configuraciones));
        contenedor.appendChild(
            crearControlesPaginacion(
                datos,
                "configuraciones",
                cargarConfiguracionesTransformacion
            )
        );
    } catch (error) {
        contenedor.textContent = error.message;
    }
}


function crearTablaIngredientes(ingredientes) {
    const tabla = document.createElement("table");
    const encabezado = document.createElement("thead");
    const cuerpo = document.createElement("tbody");

    tabla.className = "productos-tabla";
    encabezado.innerHTML = `
        <tr>
            <th>Clave</th>
            <th>Producto</th>
            <th>Categoria</th>
            <th>Cantidad</th>
        </tr>
    `;

    ingredientes.forEach(function (ingrediente) {
        const producto = ingrediente.producto || ingrediente;
        const fila = document.createElement("tr");
        [
            producto.clave,
            producto.nombre,
            producto.categoria,
            formatearCantidadUnidad(
                ingrediente.cantidad,
                ingrediente.unidad || producto.unidad
            )
        ].forEach(function (valor) {
            const celda = document.createElement("td");
            celda.textContent = valor ?? "";
            fila.appendChild(celda);
        });
        cuerpo.appendChild(fila);
    });

    tabla.append(encabezado, cuerpo);
    return tabla;
}


function crearResumenConfiguracion(configuracion) {
    const resumen = document.createElement("div");
    resumen.className = "config-detalle";

    const origen = document.createElement("div");
    origen.innerHTML = `
        <span>Producto origen</span>
        <strong>${textoProductoRegistro(configuracion.producto_origen)}</strong>
    `;

    const formula = document.createElement("div");
    formula.innerHTML = `
        <span>Producto configurado</span>
        <strong>${
            configuracion.producto_formula
                ? textoProductoRegistro(configuracion.producto_formula)
                : "-"
        }</strong>
    `;

    const cantidad = document.createElement("div");
    cantidad.innerHTML = `
        <span>Cantidad base</span>
        <strong>${formatearCantidadUnidad(
            configuracion.cantidad_base,
            configuracion.producto_origen?.unidad || "KILO"
        )}</strong>
    `;

    resumen.append(origen, formula, cantidad);
    return resumen;
}


function verDetalleConfiguracion(configuracion) {
    const contenedor = document.getElementById("ingredientesConfiguracion");
    const productos = configuracion.productos_resultantes || [];
    const componentes = configuracion.componentes || [];

    if (!contenedor) {
        return;
    }

    contenedor.className = "result-container";
    contenedor.replaceChildren();
    contenedor.appendChild(crearResumenConfiguracion(configuracion));

    const tituloComponentes = document.createElement("h4");
    tituloComponentes.className = "config-editor-title";
    tituloComponentes.textContent = "Ingredientes e insumos";
    contenedor.appendChild(tituloComponentes);

    if (componentes.length === 0) {
        const mensaje = document.createElement("p");
        mensaje.textContent =
            "Esta configuracion aun no tiene insumos capturados.";
        contenedor.appendChild(mensaje);
    } else {
        contenedor.appendChild(crearTablaIngredientes(componentes));
    }

    const tituloProductos = document.createElement("h4");
    tituloProductos.className = "config-editor-title";
    tituloProductos.textContent = "Productos resultantes";
    contenedor.appendChild(tituloProductos);

    if (productos.length === 0) {
        const mensaje = document.createElement("p");
        mensaje.textContent =
            "Esta configuracion aun no tiene productos resultantes.";
        contenedor.appendChild(mensaje);
        return;
    }

    contenedor.appendChild(crearTablaIngredientes(productos));
}


async function verIngredientesConfiguracion(productoFormulaId) {
    const contenedor = document.getElementById("ingredientesConfiguracion");

    if (!contenedor) {
        return;
    }

    contenedor.className = "result-container";
    contenedor.textContent = "Consultando ingredientes...";

    try {
        const { respuesta, datos } = await solicitarJson(
            `/configuraciones-transformacion/formula/` +
            `${productoFormulaId}/ingredientes`,
            {
                credentials: "same-origin"
            }
        );

        if (!respuesta.ok) {
            throw new Error(
                datos.detail || "No fue posible consultar ingredientes"
            );
        }

        const ingredientes = datos.ingredientes || [];

        if (ingredientes.length === 0) {
            contenedor.textContent =
                "Este producto no tiene ingredientes configurados.";
            return;
        }

        contenedor.replaceChildren(crearTablaIngredientes(ingredientes));
    } catch (error) {
        contenedor.className = "error-card";
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

    const porcentajeMermaEstimada = porcentajeMermaEstimadaProducto();
    const totalResultados = obtenerProductosResultantes().reduce(
        function (total, producto) {
            return total + Number(producto.cantidad || 0);
        },
        0
    );
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

    actualizarResumenConfiguracion();

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
    const componentesFormula = obtenerComponentesFormulaParaRegistro(
        productosResultantes
    );

    const datos = {
        id_operacion: idOperacionActual,
        producto_seleccionado_id:
            productoSeleccionadoOriginal?.id || null,
        producto_origen_id: Number(productoOrigenInput.value),
        cantidad_origen: cantidadOrigenInput.value,
        productos_resultantes: productosResultantes,
        componentes_formula: componentesFormula,
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
        const { respuesta, datos: resultado } = await solicitarJson(
            "/transformaciones/",
            {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(datos)
            },
            TIEMPO_LIMITE_REGISTRO_MS
        );

        if (respuesta.ok) {
            contenedor.className = "success-card";
            const registro = resultado.registro || {};
            const movimientos = textoMovimientosErp(registro);
            contenedor.textContent = movimientos === "-"
                ? resultado.mensaje
                : `${resultado.mensaje}. Movimientos: ${movimientos}.`;
            idOperacionActual = crearIdOperacion();
            void cargarHistorialTransformaciones();
            void cargarModuloCarnico();
        } else {
            const detalle = Array.isArray(resultado.detail)
                ? resultado.detail[0]?.msg
                : resultado.detail;

            throw new Error(
                detalle || "No se pudo registrar la transformación"
            );
        }
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
    const login = document.getElementById("loginPage");
    const dashboard = document.getElementById("dashboardPage");

    if (login) {
        redirigirSiSesionActiva();
    }

    if (dashboard) {
        void cargarSesionActual().then(function (sesion) {
            if (!sesion) {
                return;
            }

            seleccionarMovimientoModulo(movimientoModuloActual);
            actualizarModuloProductoActual();
            cargarModuloCarnico();
        });
    }

    const modalConfiguraciones =
        document.getElementById("modalConfiguraciones");
    const modalConfiguracionCarnicos =
        document.getElementById("modalConfiguracionCarnicos");
    const modalMovimientoModulo =
        document.getElementById("modalMovimientoModulo");

    if (modalConfiguraciones) {
        modalConfiguraciones.addEventListener("click", function (evento) {
            if (evento.target === modalConfiguraciones) {
                cerrarModalConfiguraciones();
            }
        });
    }

    if (modalConfiguracionCarnicos) {
        modalConfiguracionCarnicos.addEventListener(
            "click",
            function (evento) {
                if (evento.target === modalConfiguracionCarnicos) {
                    cerrarPanelConfiguracionCarnicos();
                }
            }
        );
    }

    if (modalMovimientoModulo) {
        modalMovimientoModulo.addEventListener("click", function (evento) {
            if (evento.target === modalMovimientoModulo) {
                cerrarPanelMovimientoModulo();
            }
        });
    }

    document.addEventListener("keydown", function (evento) {
        if (evento.key === "Escape") {
            cerrarModalConfiguraciones();
            cerrarPanelConfiguracionCarnicos();
            cerrarPanelMovimientoModulo();
        }
    });

    const busquedaProductoCarnicoConfig = document.getElementById(
        "busquedaProductoCarnicoConfig"
    );
    if (busquedaProductoCarnicoConfig) {
        busquedaProductoCarnicoConfig.addEventListener(
            "keydown",
            function (evento) {
                if (evento.key === "Enter") {
                    buscarProductosCarnicosConfiguracion();
                }
            }
        );
    }

    const cantidadOrigen = document.getElementById("cantidadOrigen");
    const porcentajeMermaEsperado = document.getElementById(
        "porcentajeMermaEsperado"
    );
    const configCantidadBase = document.getElementById("configCantidadBase");

    if (cantidadOrigen) {
        cantidadOrigen.value = "0";
    }

    if (porcentajeMermaEsperado) {
        porcentajeMermaEsperado.addEventListener(
            "input",
            actualizarBalance
        );
    }

    if (configCantidadBase) {
        configCantidadBase.dataset.automatica = "1";
        configCantidadBase.addEventListener("input", function () {
            configCantidadBase.dataset.automatica = "0";
            actualizarResumenConfiguracion();
        });
    }

    const productosResultantes =
        document.getElementById("productosResultantes");

    if (productosResultantes) {
        productosResultantes.textContent =
            "Selecciona un producto desde la tabla de productos.";
    }

    actualizarBalance();
    actualizarEstadoFormularioConfiguracion();
    renderizarEditorComponentesConfiguracion();
    renderizarEditorResultantesConfiguracion();
    actualizarModuloProductoActual();



});


window.addEventListener("pageshow", function (evento) {
    if (!evento.persisted) {
        return;
    }

    if (document.getElementById("loginPage")) {
        redirigirSiSesionActiva();
        return;
    }

    if (document.getElementById("dashboardPage")) {
        void cargarSesionActual().then(function (sesion) {
            if (sesion) {
                cargarModuloCarnico();
            }
        });
    }
});
