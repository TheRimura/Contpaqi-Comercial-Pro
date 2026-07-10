const API = "/api/relaciones-documentos";

const formulario = document.getElementById("form-relacion");
const salidaSelect = document.getElementById("source-document-id");
const entradaSelect = document.getElementById("destination-document-id");
const movimientoSelect = document.getElementById("tipo-movimiento");
const proveedorSelect = document.getElementById("proveedor-id");
const usuarioFisicoSelect = document.getElementById("usuario-fisico-id");
const fechaInput = document.getElementById("fecha-movimiento");
const botonRelacionar = document.getElementById("boton-relacionar");
const mensaje = document.getElementById("mensaje");

    function hoyLocal() {
        const fecha = new Date();
        const diferencia = fecha.getTimezoneOffset() *60_000;
        return new Date(fecha.getTime() - diferencia).toISOString().slice(0, 10);
    }

    async function solicitar(url, opciones = {}) {
        const respuesta = await fetch(url, {
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                ...(opciones.headers || {}),
            },
            ...opciones,
        });

        if (respuesta.status === 401) {
            window.location.assign("/");
            throw new Error ("La Sesión Termino");
        }

        const contenido = await respuesta.json().catch(() => ({}));

        if (!respuesta.ok) {
            throw new Error(contenido.detall || "No fue posible completar la operacion");
        }

        return contenido;
    }

    function llenarSelect(select, registro, configuracion) {
        select.replaceChildren();

        const opcionInicial = document.createElement("option");
        opcionInicial.value = "";
        opcionInicial.textContent = configuracion.placeholder;
        select.appendChild(opcionInicial);

        registro.forEach((registro) => {
          const opcion = document.createElement("option");
          opcionInicial.value = registro[configuracion.valor];
          opcion.textContent = configuracion.texto(registro);
          select.appendChild(opcion);
        });
    }

    function mostrarMensaje(texto,tipo) {
        mensaje.textContent = texto;
        mensaje.className = `mensaje visible ${tipo}`;
    }

    function limpiarMensaje() {
        mensaje.textContent = "";
        mensaje.className = "mensaje";
    }

    function CrearTablaPartidas(partidas) {
        if (!partidas.length) {
            return "<p>No hay partidas para mostrar.</p>"
        }

        const filas = partidas.map((partida) => `
            <tr>
                <td>${partida.ProductKey || ""}</td>
                <td>${partida.ProductName || ""}</td>
                <td>${partida.Quantity || "0.00"}</td>
                <td>${partida.total || "$0.00"}</td>
            </tr>
                    
        `).join("");

        return `
            <table class="tabla-partida">
            <thead>
                <tr>
                    <th>Clave</th>
                    <th>Producto</th>
                    <th>Cantidad</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody>${filas}</tbody>
            </table>
        `;
    }

    async function cargarPartidas(documentId, contenedorId) {
      const contenedor = document.getElementById(contenedorId);
      contenedor.innerHTML = "";

      if (!contenedor) {
          return;
      }

      try {
        const partidas = await solicitar(`${API}/documentos/${documentId}/partidas`);
        contenedor.innerHTML = crearTablaPartidas(partidas);
      } catch (error) {
        contenedor.innerHTML = `<p>${error.message}</p>`;
      }
    }

    async function cargarCatalogos() {
    const [catalogos, salidas, entradas] = await Promise.all([
        solicitar(`${API}/catalogos`),
        solicitar(`${API}/documentos-disponibles/203`),
        solicitar(`${API}/documentos-disponibles/202`),
    ]);

    llenarSelect(salidaSelect, salidas, {
        placeholder: "Selecciona una salida",
        valor: "DocumentID",
        texto: (r) => `${r.DocFolio} · ${r.UserName || "Sin usuario"}`,
    });

    llenarSelect(entradaSelect, entradas, {
        placeholder: "Selecciona una entrada",
        valor: "DocumentID",
        texto: (r) => `${r.DocFolio} · ${r.UserName || "Sin usuario"}`,
    });

    llenarSelect(movimientoSelect, catalogos.movimientos, {
        placeholder: "Selecciona el movimiento",
        valor: "ItemValue",
        texto: (r) => r.ItemValue,
    });

    llenarSelect(proveedorSelect, catalogos.proveedores, {
        placeholder: "Selecciona el proveedor",
        valor: "BusinessEntityID",
        texto: (r) => r.OfficialName,
    });

    llenarSelect(usuarioFisicoSelect, catalogos.usuarios_fisicos, {
        placeholder: "Selecciona el usuario físico",
        valor: "UserID",
        texto: (r) => r.OfficialName,
    });
}

salidaSelect.addEventListener("change", () => {
    cargarPartidas(salidaSelect.value, "partidas-salida");
});

entradaSelect.addEventListener("change", () => {
    cargarPartidas(entradaSelect.value, "partidas-entrada");
});

formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    limpiarMensaje();

    const sourceBrand = document.getElementById("source-brand-id").value;
    const destinationBrand = document.getElementById("destination-brand-id").value;

    const datos = {
        source_document_id: Number(salidaSelect.value),
        destination_document_id: Number(entradaSelect.value),
        tipo_movimiento: movimientoSelect.value,
        proveedor_id: Number(proveedorSelect.value),
        usuario_fisico_id: Number(usuarioFisicoSelect.value),
        fecha_movimiento: fechaInput.value,
        source_brand_id: sourceBrand ? Number(sourceBrand) : null,
        destination_brand_id: destinationBrand ? Number(destinationBrand) : null,
    };

    botonRelacionar.disabled = true;
    botonRelacionar.textContent = "Relacionando...";

    try {
        const resultado = await solicitar(API, {
            method: "POST",
            body: JSON.stringify(datos),
        });

        mostrarMensaje(
            `${resultado.mensaje} ${resultado.folio_salida} → ${resultado.folio_entrada}`,
            "exito",
        );

        formulario.reset();
        fechaInput.value = hoyLocal();
        document.getElementById("partidas-salida").innerHTML = "";
        document.getElementById("partidas-entrada").innerHTML = "";
        await cargarCatalogos();
    } catch (error) {
        mostrarMensaje(error.message, "error");
    } finally {
        botonRelacionar.disabled = false;
        botonRelacionar.textContent = "Relacionar documentos";
    }
});

fechaInput.value = hoyLocal();

cargarCatalogos().catch((error) => {
    mostrarMensaje(error.message, "error");
});
