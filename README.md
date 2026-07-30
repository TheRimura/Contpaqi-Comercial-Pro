# Inicialización de la base de datos

El módulo ejecuta automáticamente la inicialización al arrancar FastAPI.
También puede ejecutarse manualmente antes de desplegar:

```powershell
.\.venv\Scripts\python.exe scripts\inicializar_base_datos.py
```

El proceso:

1. Comprueba la conexión y obtiene el servidor y la base activa.
2. Valida los objetos nativos de SSM que consume el módulo.
3. Reutiliza las tablas compatibles que ya existen.
4. Crea únicamente las tablas propias del módulo que falten.
5. Agrega columnas e índices administrados que todavía no existan.
6. Verifica la estructura final y cancela el arranque si falta una
   dependencia o la estructura quedó incompleta.

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
