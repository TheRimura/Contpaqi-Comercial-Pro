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

@app.middleware('http')
async def revalidar_archivos_estaticos(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'no-cache, must-revalidate'
    return response


app.mount(
    '/static',
    StaticFiles(directory=STATIC_DIR),
    name='static',
)
templates = Jinja2Templates(directory=APP_DIR / 'templates')

app.include_router(login_router)
app.include_router(relacion_router)
app.include_router(configuracion_router)


def preparar_historial(registros: list[dict]) -> tuple[list[dict], dict]:
    """Calcula los valores del historial antes de enviarlos a la plantilla."""
    hoy = datetime.now()
    historial = []
    registros_mes = []

    for registro_original in registros:
        registro = dict(registro_original)
        cantidad_base = float(registro.get('cantidad_base') or 0)
        cantidad_resultante = float(
            registro.get('cantidad_resultante') or 0
        )
        merma = max(cantidad_base - cantidad_resultante, 0.0)
        porcentaje_merma = (
            merma / cantidad_base * 100
            if cantidad_base > 0 else 0.0
        )
        fecha_hora = registro.get('fecha_hora') or registro.get('fecha')

        registro.update({
            'fecha_texto': (
                fecha_hora.strftime('%d/%m/%Y')
                if fecha_hora else 'Sin fecha'
            ),
            'hora_texto': (
                fecha_hora.strftime('%H:%M')
                if fecha_hora else ''
            ),
            'cantidad_base_numero': cantidad_base,
            'cantidad_resultante_numero': cantidad_resultante,
            'merma_numero': merma,
            'porcentaje_merma': porcentaje_merma,
        })
        historial.append(registro)

        if (
            getattr(fecha_hora, 'year', None) == hoy.year
            and getattr(fecha_hora, 'month', None) == hoy.month
        ):
            registros_mes.append(registro)

    kilos_procesados = sum(
        registro['cantidad_base_numero']
        for registro in registros_mes
    )
    kilos_resultantes = sum(
        registro['cantidad_resultante_numero']
        for registro in registros_mes
    )
    merma_acumulada = sum(
        registro['merma_numero']
        for registro in registros_mes
    )
    resumen = {
        'transformaciones': len(registros_mes),
        'kilos_procesados': kilos_procesados,
        'merma_acumulada': merma_acumulada,
        'rendimiento': (
            kilos_resultantes / kilos_procesados * 100
            if kilos_procesados > 0 else 0.0
        ),
    }
    return historial, resumen


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
            registros = base_datos.listar_historial_transformaciones(
                limite=500
            )
            historial, resumen_historial = preparar_historial(registros)

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
