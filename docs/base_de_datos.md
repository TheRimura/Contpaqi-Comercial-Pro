# Documento tecnico: `app/utils/base_de_datos.py`

Este documento explica la logica de `app/utils/base_de_datos.py`, que es la capa principal de acceso a SQL Server para el modulo de Transformacion Carnica.

El archivo concentra consultas, validaciones, registros y actualizaciones que conectan la aplicacion FastAPI con la base de datos de Cayal/ERP.

## 1. Proposito del archivo

`base_de_datos.py` tiene una responsabilidad muy concreta:

1. Conectarse a SQL Server usando la infraestructura del paquete `cayal`.
2. Consultar productos, configuraciones, formulas, equivalencias e inventario.
3. Registrar configuraciones de transformacion creadas por el usuario.
4. Registrar transformaciones reales.
5. Crear y actualizar informacion necesaria para la integracion con movimientos ERP.
6. Consultar historial, detalles y componentes de transformaciones.

En terminos practicos, este archivo es el puente entre:

```text
Pantallas HTML/JS
        v
Rutas FastAPI
        v
Repositorios / logica de negocio
        v
BaseDatos
        v
SQL Server / ERP Cayal
```

## 2. Dependencias principales

El archivo importa:

```python
import json
from functools import cache
from platform import node

from cayal.comandos_base_datos import ComandosBaseDatos
```

### `json`

Se usa para convertir listas de productos o componentes a JSON antes de enviarlas a SQL Server.

Ejemplos:

- productos resultantes de una configuracion
- productos resultantes de una transformacion
- componentes de formula

SQL Server despues lee esos datos con `OPENJSON`.

### `cache`

Se usa al final del archivo para mantener una sola instancia de `BaseDatos` durante la ejecucion.

### `node`

Obtiene el nombre de la maquina actual. Ese nombre se usa como servidor SQL.

En tu entorno, por ejemplo, la conexion detecto:

```text
SERVER=MSI
DATABASE=ComercialSP
```

### `ComandosBaseDatos`

Viene del paquete `cayal`. Es la clase base que ya trae metodos para hablar con la base de datos.

Este archivo depende de metodos como:

- `fetchall(...)`
- `fetchone(...)`
- `command(...)`
- `exec_stored_procedure(...)`
- `crear_movimiento_de_almacen(...)`
- `insertar_partida_documento_cayal(...)`
- `buscar_ultimo_costo_producto(...)`
- `registrar_documento_a_recalcular(...)`
- `relacionar_documentos(...)`

Esos metodos no estan definidos en `base_de_datos.py`, sino heredados desde `ComandosBaseDatos`.

## 3. Clase `BaseDatos`

```python
class BaseDatos(ComandosBaseDatos):
```

La clase `BaseDatos` hereda de `ComandosBaseDatos`. Eso significa que no implementa la conexion desde cero, sino que extiende la funcionalidad existente del paquete `cayal`.

### `__init__`

```python
def __init__(self):
    super().__init__(servidor=node())
```

Al crear una instancia de `BaseDatos`, se llama al constructor de `ComandosBaseDatos` y se le pasa como servidor el nombre de la computadora.

Esto permite que la app conecte al SQL Server local/configurado para esa maquina.

## 4. Flujo general del modulo

La logica completa se puede leer asi:

```text
1. El usuario inicia sesion.
2. La app busca productos del modulo carnico.
3. Al seleccionar un producto, se resuelve su relacion de transformacion.
4. La relacion puede venir de:
   - configuracion guardada por usuario
   - formula de producto
   - equivalencia ERP
5. El usuario captura o ajusta cantidades.
6. La app registra la transformacion.
7. Se crea salida de inventario.
8. Se crea entrada de inventario.
9. Se relacionan documentos ERP.
10. Se manda a recalculo.
11. El historial muestra estado, folios, merma y detalle.
```

## 5. Configuracion principal del modulo

### `buscar_configuracion_transformaciones`

Consulta:

- `dbo.ConfiguracionTransformaciones`
- `dbo.orgDepot`

Devuelve la configuracion activa del modulo:

- `id_configuracion`
- `almacen_id`
- `almacen`
- `movimiento_salida`
- `movimiento_entrada`
- `modulo_entrada`
- `modulo_salida`
- `estatus_equivalencia`
- `catalogo_salida`
- `catalogo_entrada`

Esta funcion es una de las mas importantes del archivo.

Muchas otras funciones dependen de ella porque necesitan saber:

- de que almacen leer existencias
- que tipo de movimiento usar en ERP
- que estatus de equivalencias considerar
- que catalogos consultar para salida y entrada

Si no existe configuracion activa, lanza:

```text
No existe una configuracion activa para transformaciones
```

### Importancia

Sin esta configuracion, el modulo no sabe:

- donde consultar inventario
- como crear movimientos
- como interpretar equivalencias
- que movimientos ERP usar

## 6. Seguridad y sesion

### `buscar_configuracion_seguridad`

Consulta:

- `dbo.ConfiguracionSeguridad`

Devuelve:

- `grupo_llave_maestra`
- `nombre_cookie`
- `duracion_sesion_segundos`
- `clave_firma`

Esta informacion se usa desde `app/utils/seguridad.py` para:

- firmar cookies
- nombrar la cookie de sesion
- definir duracion de sesion
- validar acceso

Si no hay configuracion activa, lanza:

```text
No existe una configuracion activa de seguridad
```

### `buscar_hashes_grupo_maestro`

Consulta:

- `dbo.engUser`
- `dbo.engUserGroup`
- `dbo.engUserCayal`

Busca los hashes de contrasena de usuarios que pertenecen al grupo maestro configurado.

Sirve para la logica de llave maestra del login.

En otras palabras:

- el usuario puede entrar con su contrasena normal
- o puede entrar con una contrasena maestra valida del grupo configurado

## 7. Categorias y merma

### `buscar_porcentajes_merma`

Consulta:

- `dbo.CategoriasTransformacion`

Devuelve un diccionario como:

```python
{
    "POLLO": 5.0,
    "CERDO": 4.5,
    "RES LOCAL": 6.0,
}
```

La clave se normaliza:

- se convierte a `str`
- se hace `strip`
- se pasa a mayusculas

Si `porcentaje_merma` viene `NULL`, se toma como `0`.

### Para que sirve

El frontend y la logica de productos usan estos porcentajes para:

- mostrar merma estimada
- calcular salida/entrada sugerida
- determinar si una categoria pertenece al modulo carnico

## 8. Busqueda de productos

### `buscar_productos_por_nombre`

Consulta principalmente:

- `dbo.orgProduct`
- `dbo.vwLBSProductQuantityList`
- `dbo.CategoriasTransformacion`
- `dbo.zvwFormulasListasPCocinar`
- `dbo.zvwEquivalenciasTransKoben`

Busca productos por nombre (`ProductName LIKE ?`) y solo trae productos que:

- no esten eliminados (`DeletedOn IS NULL`)
- esten disponibles para venta (`AvailableForSale = 1`)
- pertenezcan al modulo carnico por alguna regla valida

### Reglas para considerar un producto del modulo

Un producto entra al modulo si cumple al menos una de estas condiciones:

1. Su categoria coincide con una categoria activa en `CategoriasTransformacion`.
2. Es una formula que tiene un componente cuya categoria pertenece al modulo.
3. Tiene equivalencia activa con otro producto cuya categoria pertenece al modulo.

### Datos devueltos

Devuelve datos como:

- `ProductID`
- `ProductKey`
- `ProductName`
- `Category1`
- `Unit`
- `CostPrice`
- `QtyPresent`
- `ProductTypeIDCayal`

### Detalle importante

Usa `OUTER APPLY` para calcular:

- existencia del producto en el almacen configurado
- categoria homologada por categoria directa
- categoria inferida desde formulas
- categoria inferida desde equivalencias

Esto permite que la pantalla de productos muestre productos que no necesariamente tienen la categoria directa, pero si pertenecen al flujo carnico por formula o equivalencia.

## 9. Validacion de productos del modulo

### `buscar_ids_productos_modulo`

Recibe una lista de IDs de productos y devuelve un `set` con los IDs que realmente pertenecen al modulo.

Primero limpia la lista:

- convierte a `int`
- elimina valores vacios
- elimina duplicados conservando orden

Despues usa reglas similares a `buscar_productos_por_nombre`:

- categoria activa
- formula con componente de categoria activa
- equivalencia activa

### Para que sirve

Se usa para evitar registrar transformaciones con productos fuera del alcance del modulo.

Por ejemplo, si alguien intenta mandar un producto que no es pollo, cerdo, res local o una formula/equivalencia relacionada, la validacion de negocio lo puede rechazar.

## 10. Equivalencias de transformacion

### `buscar_resultantes_transformacion`

Consulta:

- `dbo.zvwEquivalenciasTransKoben`
- `dbo.orgProduct`
- `dbo.vwLBSProductQuantityList`
- `dbo.CategoriasTransformacion`

Busca los productos resultantes configurados por equivalencia para un producto origen.

Filtra por:

- `E.ProductID1 = producto_origen_id`
- `E.Status = configuracion["estatus_equivalencia"]`

### Datos importantes

Devuelve:

- producto resultante (`ProductID2`)
- cantidad origen (`Cant1`)
- cantidad resultante (`Cant2`)
- datos del producto resultante
- existencia en almacen
- categoria homologada

### Como se usa

Si un producto no tiene configuracion de usuario ni formula, el sistema intenta resolverlo por equivalencias.

## 11. Consulta de productos por IDs

### `buscar_productos_por_ids`

Recibe IDs y trae datos basicos desde `orgProduct`.

Tambien calcula existencia en el almacen configurado.

Se usa cuando la app ya conoce los IDs y necesita completar informacion para mostrar o validar.

## 12. Configuraciones de usuario

Las configuraciones de usuario permiten guardar una relacion personalizada de transformacion.

Tablas principales:

- `dbo.TransformacionesUsuario`
- `dbo.TransformacionesUsuarioDetalle`

### `buscar_configuracion_usuario_para_producto`

Busca una configuracion activa relacionada con un producto.

Puede encontrarla por:

- `producto_formula`
- `producto_origen`

Ordena dando prioridad a coincidencia por `producto_formula`.

Esto permite que si seleccionas una formula, el sistema encuentre la configuracion personalizada que indica:

- producto origen real
- producto formula
- cantidad base
- porcentaje de merma
- datos del producto origen
- datos del producto formula
- existencias

### `contar_configuraciones_usuario`

Cuenta cuantas configuraciones activas existen.

Se usa para paginacion.

### `buscar_configuraciones_usuario`

Lista las configuraciones activas con paginacion.

Devuelve encabezados:

- ID
- nombre
- producto origen
- producto formula
- cantidad base
- porcentaje merma
- usuario creador
- usuario actualizador
- fechas
- observaciones

No trae detalles; esos se consultan aparte.

### `buscar_detalles_configuraciones_usuario`

Recibe IDs de configuraciones y trae sus productos resultantes activos.

Consulta:

- `dbo.TransformacionesUsuarioDetalle`
- `dbo.orgProduct`
- `dbo.vwLBSProductQuantityList`

Devuelve:

- producto resultante
- cantidad resultante
- unidad
- si participa en balance
- orden
- datos del producto
- existencia

### `registrar_configuracion_usuario`

Crea una nueva configuracion de usuario.

Flujo:

```text
1. Convierte productos_resultantes a JSON.
2. Inicia transaccion.
3. Inserta encabezado en TransformacionesUsuario.
4. Obtiene el ID con SCOPE_IDENTITY().
5. Inserta detalles en TransformacionesUsuarioDetalle usando OPENJSON.
6. Confirma transaccion.
7. Devuelve id_transformacion_usuario.
```

Campos insertados en encabezado:

- `nombre_transformacion`
- `producto_origen`
- `producto_formula`
- `cantidad_base`
- `porcentaje_merma`
- `usuario_creacion`
- `observaciones`

Campos insertados en detalle:

- `producto_resultante`
- `cantidad_resultante`
- `unidad`
- `participa_balance`
- `orden`

### `actualizar_configuracion_usuario`

Actualiza una configuracion existente.

Esta funcion se agrego para soportar edicion desde la pantalla de Configuraciones.

Flujo:

```text
1. Convierte productos_resultantes a JSON.
2. Inicia transaccion.
3. Actualiza encabezado en TransformacionesUsuario.
4. Si se actualizo 1 fila:
   - desactiva detalles anteriores
   - inserta nuevos detalles desde OPENJSON
5. Confirma transaccion.
6. Devuelve True si actualizo algo.
```

### Por que desactiva detalles y no los modifica uno por uno

Porque es mas sencillo y confiable para representar una nueva version de la configuracion.

Ventajas:

- evita tener que comparar detalle por detalle
- conserva historial fisico de detalles anteriores si la tabla lo permite
- reduce casos raros cuando se agregan o quitan productos

Riesgo:

- si la tabla crece mucho, puede acumular detalles inactivos

## 13. Formulas

### `buscar_ingredientes_formula`

Consulta:

- `dbo.zvwFormulasListasPCocinar`
- `dbo.orgProduct`

Devuelve los componentes/ingredientes de una formula.

Datos:

- ID del componente
- nombre del componente
- cantidad del componente
- clave producto
- categoria
- unidad

Se usa para:

- saber si un producto seleccionado es formula
- detectar producto base
- mostrar ingredientes
- registrar componentes asociados a una transformacion

## 14. Tipos de movimiento ERP

### `buscar_tipo_movimiento`

Busca un movimiento ERP dentro de `dbo.engRefCombo`.

Recibe:

- `tipo`: salida o entrada
- `nombre`: nombre del movimiento configurado

Primero obtiene la configuracion activa.

Despues decide que catalogo usar:

```python
grupo = configuracion.get(f"catalogo_{tipo_normalizado}")
```

Si `tipo` es `salida`, usa `catalogo_salida`.

Si `tipo` es `entrada`, usa `catalogo_entrada`.

Luego busca el movimiento por nombre, normalizando espacios y mayusculas.

Devuelve:

- `id`
- `nombre`

Si no encuentra el movimiento, lanza error.

## 15. Integracion ERP

Estas funciones apoyan a `app/repositories/movimientos_erp.py`.

### `buscar_transformacion_por_operacion`

Consulta `dbo.Transformaciones` por `id_operacion`.

Sirve para idempotencia.

Es decir: si una operacion ya creo documentos de salida o entrada, el sistema puede reutilizarlos y no duplicar movimientos.

Devuelve:

- `id_transformacion`
- `documento_salida`
- `documento_entrada`
- `almacen_id`
- `estado_erp`
- `error_erp`

### `actualizar_integracion_erp`

Actualiza en `dbo.Transformaciones`:

- documento de salida
- documento de entrada
- estado ERP
- error ERP

Usa `COALESCE` para no reemplazar documentos con `NULL` accidentalmente.

El campo `error_erp` si se asigna directamente, porque tambien se necesita poder limpiarlo con `None`.

### `configurar_almacen_documento`

Actualiza `dbo.docDocument`.

Asigna:

- `DepotID`
- `DepotIDFrom`

Ambos al almacen configurado.

Sirve para asegurar que los movimientos ERP queden ligados al almacen correcto.

### `insertar_partida_movimiento`

Inserta una partida en un documento ERP.

Flujo:

```text
1. Busca ultimo costo del producto.
2. Calcula total = costo * cantidad.
3. Inserta partida con insertar_partida_documento_cayal.
4. Actualiza docDocumentItem con almacen, costo, precio y total.
5. Devuelve DocumentItemID.
```

Si no puede insertar la partida, lanza error.

### `registrar_recalculo_si_pendiente`

Consulta `dbo.zvwDocumentosRecalculadosCayal`.

Si el documento ya esta registrado para recalculo con el mismo `id_operacion`, no hace nada.

Si no existe, llama:

```python
self.registrar_documento_a_recalcular(...)
```

Esto manda el documento al proceso de recalculo/afectacion.

### `buscar_folio_documento`

Consulta `dbo.docDocument` y arma folio:

```text
FolioPrefix + Folio
```

Se usa para mostrar folios ERP en respuestas e historial.

## 16. Registro de transformacion

### `registrar_transformacion`

Esta funcion registra la transformacion principal usando el stored procedure:

```text
zvwRegistrarTransformacionCayal
```

Antes de llamar el procedimiento:

1. Convierte productos resultantes a JSON.
2. Convierte componentes de formula a JSON.
3. Manda todos los parametros necesarios.

Parametros importantes:

- `id_operacion`
- `producto_origen_id`
- `producto_seleccionado_id`
- `cantidad_origen`
- `usuario`
- `usuario_id`
- `tipo_transformacion`
- `porcentaje_merma_esperado`
- `almacen_id`
- `peso_merma`
- `observaciones_merma`
- `productos_json`
- `componentes_json`

El stored procedure devuelve el ID de transformacion.

### Por que usa JSON

Porque una transformacion puede tener varios productos resultantes y varios componentes.

Mandarlos como JSON evita hacer multiples llamadas desde Python.

## 17. Historial de transformaciones

### `buscar_historial_transformaciones`

Consulta `dbo.Transformaciones` y arma el encabezado del historial.

Tablas/vistas involucradas:

- `dbo.Transformaciones`
- `dbo.orgProduct`
- `dbo.orgDepot`
- `dbo.docDocument`
- `dbo.Mermas`
- `dbo.zvwDocumentosRecalculadosCayal`

Devuelve:

- folio interno
- fecha
- usuario
- producto origen
- cantidad origen
- merma
- almacen
- documentos ERP
- folios ERP
- estado ERP
- error ERP

### Logica especial del estado ERP

La consulta calcula `estado_erp` asi:

Si existen documento de salida y entrada, ambos estan en recalculo, y ninguno esta pendiente (`Status = 0`), entonces muestra:

```text
completada
```

Si no, conserva `T.estado_erp`.

Esto permite que el historial refleje cuando inventario ya fue afectado, aunque el estado original haya sido `pendiente_afectacion`.

### `buscar_detalles_transformaciones`

Trae productos resultantes de transformaciones ya registradas.

Consulta:

- `dbo.DetalleTransformaciones`
- `dbo.orgProduct`

### `buscar_componentes_transformaciones`

Trae componentes/ingredientes registrados en una transformacion.

Consulta:

- `dbo.ComponentesTransformacion`
- `dbo.orgProduct`

Esto se usa para reconstruir historiales donde hay formula o insumos.

### `buscar_bases_formulas`

Busca el componente base de formulas.

Consulta:

- `dbo.zvwFormulasListasPCocinar`
- `dbo.orgProduct`

La logica prioriza:

1. componentes cuya categoria no sea `INSUMOS`
2. orden original por `IDComp`

Solo considera componentes con unidad `KILO`.

Esto ayuda a mostrar historiales anteriores donde no se registraban componentes de forma explicita.

## 18. Validacion de existencia

### `buscar_ids_productos_existentes`

Recibe IDs y devuelve solo los que existen en `dbo.orgProduct` y no estan eliminados.

Se usa antes de guardar configuraciones o transformaciones.

Evita registrar IDs invalidos.

## 19. Instancia cacheada

### `obtener_base_datos`

Al final:

```python
@cache
def obtener_base_datos():
    return BaseDatos()
```

Esto hace que la app reutilice la misma instancia de `BaseDatos`.

Ventajas:

- evita crear objetos repetidamente
- centraliza acceso a la conexion base
- simplifica uso desde rutas y repositorios

Consideracion:

Si en algun momento se necesita cambiar servidor o credenciales durante ejecucion, esta cache tendria que limpiarse o replantearse.

## 20. Tablas y vistas principales

| Tabla / vista | Uso principal |
|---|---|
| `dbo.ConfiguracionTransformaciones` | Configuracion activa del modulo carnico |
| `dbo.ConfiguracionSeguridad` | Configuracion de sesion/cookies |
| `dbo.CategoriasTransformacion` | Categorias validas y porcentaje de merma |
| `dbo.orgProduct` | Catalogo principal de productos |
| `dbo.vwLBSProductQuantityList` | Existencias por almacen |
| `dbo.zvwFormulasListasPCocinar` | Formulas e ingredientes |
| `dbo.zvwEquivalenciasTransKoben` | Equivalencias de transformacion |
| `dbo.TransformacionesUsuario` | Configuraciones creadas por usuarios |
| `dbo.TransformacionesUsuarioDetalle` | Detalle de configuraciones |
| `dbo.Transformaciones` | Encabezado de transformaciones registradas |
| `dbo.DetalleTransformaciones` | Productos resultantes registrados |
| `dbo.ComponentesTransformacion` | Componentes/ingredientes registrados |
| `dbo.Mermas` | Merma registrada por transformacion |
| `dbo.docDocument` | Documentos ERP |
| `dbo.docDocumentItem` | Partidas de documentos ERP |
| `dbo.zvwDocumentosRecalculadosCayal` | Seguimiento de recalculo/afectacion |
| `dbo.engRefCombo` | Catalogos ERP de movimientos |
| `dbo.engUser` | Usuarios |
| `dbo.engUserGroup` | Grupos de usuarios |
| `dbo.engUserCayal` | Hashes de usuarios Cayal |

## 21. Relaciones con otros archivos

### `app/routes/productos.py`

Usa `BaseDatos` para:

- buscar productos
- encontrar resultantes
- resolver configuracion usuario / formula / equivalencia

### `app/routes/configuraciones.py`

Usa `BaseDatos` para:

- listar configuraciones
- guardar configuraciones
- actualizar configuraciones
- consultar ingredientes de formula

### `app/repositories/transformaciones.py`

Usa `BaseDatos` para:

- validar productos existentes
- validar productos del modulo
- validar equivalencias
- guardar transformacion
- consultar historial

### `app/repositories/movimientos_erp.py`

Usa `BaseDatos` para:

- buscar tipos de movimiento
- crear documentos ERP
- insertar partidas
- relacionar documentos
- registrar recalculo
- actualizar estado ERP

### `app/utils/seguridad.py`

Usa `BaseDatos` para:

- cargar configuracion de seguridad
- validar cookies
- obtener hashes de llave maestra

## 22. Flujo de configuracion guardada

```text
Usuario selecciona producto
        v
Frontend consulta /productos/{id}/resultantes
        v
productos.py llama buscar_configuracion_usuario_para_producto
        v
Si existe configuracion:
        v
buscar_detalles_configuraciones_usuario
        v
Frontend muestra resultantes configurados
        v
Usuario puede guardar o editar configuracion
        v
POST o PUT /configuraciones-transformacion
        v
registrar_configuracion_usuario o actualizar_configuracion_usuario
```

## 23. Flujo de transformacion real

```text
Usuario registra transformacion
        v
repositorio valida productos
        v
BaseDatos.registrar_transformacion
        v
Stored procedure zvwRegistrarTransformacionCayal
        v
IntegracionMovimientosERP.procesar
        v
crear documento salida
        v
insertar partida salida
        v
crear documento entrada
        v
insertar partidas entrada
        v
relacionar documentos
        v
registrar recalculo
        v
actualizar estado ERP
```

## 24. Patrones importantes del archivo

### Limpieza de IDs

Varias funciones hacen esto:

```python
ids_limpios = list(dict.fromkeys(
    int(producto_id)
    for producto_id in ids_productos
    if producto_id
))
```

Esto:

- elimina vacios
- convierte a entero
- elimina duplicados
- mantiene orden

### Parametros seguros

La mayoria de valores se pasan con `?`, no interpolados directo.

Ejemplo:

```python
self.fetchall("SELECT ... WHERE ProductID = ?", (producto_id,))
```

Esto reduce riesgo de SQL injection.

### SQL dinamico controlado

Cuando se arma `IN (?, ?, ?)` se genera dinamicamente la cantidad de placeholders:

```python
parametros = ", ".join("?" for _ in ids_limpios)
```

Los valores reales siguen entrando como parametros.

### Transacciones

Las operaciones de guardado/edicion usan:

```sql
BEGIN TRANSACTION;
...
COMMIT TRANSACTION;
...
ROLLBACK TRANSACTION;
```

Esto evita datos incompletos si algo falla.

## 25. Riesgos y puntos a cuidar

### 1. Mucha logica SQL en una sola clase

`BaseDatos` concentra muchas responsabilidades:

- seguridad
- productos
- configuraciones
- ERP
- historial

Funciona, pero a futuro podria separarse por repositorios especializados.

### 2. Dependencia fuerte de nombres de tablas/vistas

Si cambia una vista como `zvwFormulasListasPCocinar`, varias funciones pueden fallar.

### 3. Configuracion activa unica

El modulo asume una configuracion activa:

```sql
SELECT TOP 1 ...
WHERE activa = 1
ORDER BY id_configuracion
```

Si hay varias activas, toma la primera por ID.

### 4. Edicion de configuracion reemplaza detalles

La edicion desactiva detalles anteriores y crea nuevos.

Esto es correcto para simplicidad, pero puede acumular historico inactivo.

### 5. `@cache` mantiene instancia viva

Si cambia la configuracion de conexion durante ejecucion, la instancia cacheada no se recrea sola.

## 26. Resumen corto por responsabilidad

| Responsabilidad | Funciones |
|---|---|
| Conexion | `__init__`, `obtener_base_datos` |
| Configuracion modulo | `buscar_configuracion_transformaciones` |
| Seguridad | `buscar_configuracion_seguridad`, `buscar_hashes_grupo_maestro` |
| Productos | `buscar_productos_por_nombre`, `buscar_productos_por_ids`, `buscar_ids_productos_existentes` |
| Validacion modulo | `buscar_ids_productos_modulo`, `buscar_porcentajes_merma` |
| Equivalencias | `buscar_resultantes_transformacion` |
| Formulas | `buscar_ingredientes_formula`, `buscar_bases_formulas` |
| Configuraciones usuario | `buscar_configuracion_usuario_para_producto`, `buscar_configuraciones_usuario`, `buscar_detalles_configuraciones_usuario`, `registrar_configuracion_usuario`, `actualizar_configuracion_usuario` |
| ERP | `buscar_tipo_movimiento`, `configurar_almacen_documento`, `insertar_partida_movimiento`, `registrar_recalculo_si_pendiente`, `buscar_folio_documento`, `actualizar_integracion_erp` |
| Transformaciones | `registrar_transformacion`, `buscar_transformacion_por_operacion` |
| Historial | `buscar_historial_transformaciones`, `buscar_detalles_transformaciones`, `buscar_componentes_transformaciones` |

## 27. Lectura recomendada del archivo

Para entenderlo sin perderse, conviene leer en este orden:

1. `buscar_configuracion_transformaciones`
2. `buscar_productos_por_nombre`
3. `buscar_configuracion_usuario_para_producto`
4. `buscar_resultantes_transformacion`
5. `registrar_configuracion_usuario`
6. `actualizar_configuracion_usuario`
7. `registrar_transformacion`
8. funciones ERP
9. funciones de historial

Ese orden sigue el uso real del modulo desde que el usuario busca producto hasta que registra y consulta historial.
