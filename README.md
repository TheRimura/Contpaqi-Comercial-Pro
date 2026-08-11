# Módulo de transformación cárnica CAYAL

Aplicación web para configurar y registrar transformaciones cárnicas,
calcular merma e insumos, generar la relación de documentos de almacén y
consultar el historial operativo en SSM.

## Estructura

- `app/routes`: endpoints de acceso, configuración y transformación.
- `app/schemas`: contratos de entrada y validaciones de la API.
- `app/static`: estilos, imágenes y comportamiento del navegador.
- `app/templates`: las dos vistas del módulo (`login` y `dashboard`).
- `app/utils`: acceso a SQL Server, seguridad e inicialización.
- `scripts`: consultas de soporte e instalación idempotente de la base.
- `main.py`: arranque de FastAPI y composición del módulo.
- `app/settings.py`: ajustes operativos y permisos editables.

## Instalación local

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

Abra `http://127.0.0.1:8000`. El estado de la aplicación y de SQL Server se
puede consultar en `http://127.0.0.1:8000/salud`.

## Conexión al servidor

El módulo hereda de `cayal.comandos_base_datos.ComandosBaseDatos`. Sin una
configuración de despliegue usa `platform.node()` y se conecta a la instancia
SQL de la computadora local. El instalador detecta, en este orden, una
configuración explícita, la instancia `COMPAC` del equipo y la instancia local;
después guarda el destino validado en `.env`:

```env
CAYAL_DB_SERVER=SERVIDOR_SQL\INSTANCIA
CAYAL_DB_NAME=ComercialSP
```

La detección no explora toda la red: solamente prueba los destinos anteriores
y exige que la base sea `ComercialSP` y contenga los objetos nativos de SSM.
Nunca almacene credenciales reales dentro del repositorio.

## Inicialización de la base de datos

La validación se ejecuta al arrancar FastAPI. También puede iniciarse de forma
manual antes de un despliegue:

```powershell
.\.venv\Scripts\python.exe scripts\inicializar_base_datos.py
```

El proceso:

1. Comprueba la conexión y obtiene el servidor y la base activa.
2. Valida los objetos nativos de SSM utilizados por el módulo.
3. Reutiliza las tablas compatibles existentes.
4. Crea solamente las tablas propias que hagan falta.
5. Agrega solamente las columnas administradas pendientes.
6. Verifica la estructura final antes de habilitar el módulo.

El inicializador es idempotente: puede ejecutarse varias veces sin duplicar
tablas, columnas ni configuraciones de seguridad. No crea índices, claves
primarias ni restricciones únicas. Los objetos nativos
de SSM no se crean artificialmente; si falta alguno, el proceso se detiene para
evitar una instalación incompatible.

La primera instalación requiere permisos para consultar metadatos y, cuando
sea necesario, crear o modificar tablas. El servidor necesita
Microsoft ODBC Driver 17 u 18 para SQL Server.

## Validación antes de publicar

```powershell
.\.venv\Scripts\python.exe -m compileall -q main.py app scripts
node --check app\static\js\app.js
git diff --check
```

No se deben versionar `.env`, secretos de sesión, entornos virtuales, cachés de
Python ni archivos temporales de pruebas.
