import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.routes.login import router as login_router
from app.routes.relacion_documentos import router as relacion_router
from app.routes.configuracion import router as configuracion_router
from app.settings import AJUSTES_MODULO
from app.utils.base_de_datos import obtener_base_datos
from app.utils.seguridad import seguridad_sesion


BASE_DIR = Path(__file__).resolve().parent
APP_DIR = BASE_DIR / 'app'
STATIC_DIR = APP_DIR / 'static'

app = FastAPI(
    title='CAYAL - Relación de documentos de almacén',
    version='1.0.0',
)

app.mount(
    '/static',
    StaticFiles(directory=STATIC_DIR),
    name='static',
)
templates = Jinja2Templates(directory=APP_DIR / 'templates')

app.include_router(login_router)
app.include_router(relacion_router)
app.include_router(configuracion_router)


def obtener_version_assets() -> int:
    versiones = []

    for ruta in (
        STATIC_DIR / 'css' / 'styles.css',
        STATIC_DIR / 'js' / 'app.js',
    ):
        try:
            versiones.append(ruta.stat().st_mtime_ns)
        except FileNotFoundError:
            continue

    return max(versiones) if versiones else 0


@app.exception_handler(RuntimeError)
async def manejar_runtime_error(_: Request, error: RuntimeError):
    return JSONResponse(
        status_code=503,
        content={'detail': str(error)},
    )


@app.get('/', include_in_schema=False)
def mostrar_login(request: Request):
    if seguridad_sesion.obtener_sesion(request):
        return RedirectResponse('/dashboard', status_code=303)
    return templates.TemplateResponse(
        request=request,
        name='login.html',
        context={'asset_version': obtener_version_assets()},
    )


@app.get('/dashboard', include_in_schema=False)
def mostrar_dashboard(request: Request):
    sesion = seguridad_sesion.obtener_sesion(request)
    if not sesion:
        return RedirectResponse('/', status_code=303)

    permisos = seguridad_sesion.permisos_publicos(sesion)
    lineas = []
    transformaciones = []
    historial = []
    resumen_historial = {
        'transformaciones': 0,
        'kilos_procesados': 0.0,
        'merma_acumulada': 0.0,
        'rendimiento': 0.0,
    }
    if permisos['configuracion'] or permisos['historial']:
        base_datos = obtener_base_datos()
        if permisos['configuracion']:
            lineas = base_datos.listar_lineas_transformacion()
            for linea in lineas:
                transformaciones.extend(
                    base_datos.listar_transformaciones_precargadas(
                        linea.get('Category1', '')
                    )
                )
        if permisos['historial']:
            historial = base_datos.listar_historial_transformaciones(limite=500)
            hoy = datetime.now()
            registros_mes = [
                registro for registro in historial
                if getattr(
                    registro.get('fecha_hora') or registro.get('fecha'),
                    'year',
                    None,
                ) == hoy.year
                and getattr(
                    registro.get('fecha_hora') or registro.get('fecha'),
                    'month',
                    None,
                ) == hoy.month
            ]
            kilos_procesados = sum(
                float(registro.get('cantidad_base') or 0)
                for registro in registros_mes
            )
            kilos_resultantes = sum(
                float(registro.get('cantidad_resultante') or 0)
                for registro in registros_mes
            )
            resumen_historial = {
                'transformaciones': len(registros_mes),
                'kilos_procesados': kilos_procesados,
                'merma_acumulada': max(
                    kilos_procesados - kilos_resultantes,
                    0.0,
                ),
                'rendimiento': (
                    kilos_resultantes / kilos_procesados * 100
                    if kilos_procesados > 0 else 0.0
                ),
            }

    return templates.TemplateResponse(
        request=request,
        name='dashboard.html',
        context={
            'sesion': sesion,
            'permisos': permisos,
            'ajustes': AJUSTES_MODULO,
            'lineas': lineas,
            'transformaciones': transformaciones,
            'historial': historial,
            'resumen_historial': resumen_historial,
            'asset_version': obtener_version_assets(),
        },
    )


@app.get('/salud', tags=['Sistema'])
def comprobar_salud():
    try:
        conexion = obtener_base_datos().probar_conexion()
        detalle = 'Conexión SQL Server disponible.'
    except Exception as error:
        conexion = False
        detalle = str(error)

    return {
        'aplicacion': 'Módulo Cárnico CAYAL',
        'api': True,
        'base_de_datos': conexion,
        'detalle': detalle,
    }
