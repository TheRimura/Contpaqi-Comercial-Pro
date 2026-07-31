# Inicialización de la base de datos

El módulo ejecuta automáticamente la inicialización al arrancar FastAPI.
También puede ejecutarse manualmente antes de desplegar:

```powershell
.\.venv\Scripts\python.exe scripts\inicializar_base_datos.py
```

## Conexión al servidor de la empresa

El módulo usa `cayal.comandos_base_datos.ComandosBaseDatos`, pero permite
indicar el destino sin modificar código. Antes de instalar, configure estas
variables en el servidor (o en el archivo `.env` del servicio):

```env
CAYAL_DB_SERVER=SERVIDOR_SQL\\INSTANCIA
CAYAL_DB_NAME=ComercialSP
```

Con esas dos variables se utiliza la autenticación integrada de Windows. La
cuenta que ejecuta el servicio debe tener acceso a SQL Server. Si la empresa
usa autenticación SQL, agregue:

```env
CAYAL_DB_USER=usuario_modulo
CAYAL_DB_PASSWORD=contraseña_segura
```

También se puede definir una cadena completa mediante
`CAYAL_DB_CONNECTION_STRING`; cuando existe, tiene prioridad sobre las demás
variables. No guarde credenciales reales dentro del repositorio.

El proceso:

1. Comprueba la conexión y obtiene el servidor y la base activa.
2. Valida los objetos nativos de SSM que consume el módulo.
3. Reutiliza las tablas compatibles que ya existen.
4. Crea únicamente las tablas propias del módulo que falten.
5. Agrega columnas e índices administrados que todavía no existan.
6. Verifica la estructura final y cancela el arranque si falta una
   dependencia o la estructura quedó incompleta.

Para comprobar un despliegue, ejecute el inicializador dos veces. La primera
puede crear o actualizar objetos; la segunda debe informar cero tablas creadas
y todas las tablas como reutilizadas. Después compruebe:

```powershell
Invoke-RestMethod http://localhost:8000/salud
```

El script es idempotente: se puede ejecutar varias veces sin duplicar tablas,
columnas, índices ni la configuración de seguridad.

## Permisos de despliegue

La cuenta utilizada durante la primera instalación debe poder consultar
metadatos y, cuando sea necesario, crear o modificar tablas e índices. Después
de instalar, el servicio puede usar una cuenta con los permisos operativos
habituales del módulo.

Los objetos nativos de SSM no se crean artificialmente. Si falta alguno, el
proceso se detiene indicando su nombre para evitar instalar una estructura
incompatible con el servidor de la empresa.

La máquina del servicio necesita Microsoft ODBC Driver 17 u 18 for SQL Server.
El paquete `cayal` selecciona automáticamente el controlador disponible.
