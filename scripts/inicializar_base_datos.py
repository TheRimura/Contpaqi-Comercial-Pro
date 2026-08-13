import json
import os
import sys
from contextlib import redirect_stdout
from dataclasses import asdict
from io import StringIO
from pathlib import Path
from platform import node


RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

try:
    from dotenv import load_dotenv
    load_dotenv(RAIZ_PROYECTO / '.env')
except ImportError:
    pass


def _actualizar_variable_env(nombre: str, valor: str) -> None:
    ruta_env = RAIZ_PROYECTO / '.env'
    lineas = (
        ruta_env.read_text(encoding='utf-8').splitlines()
        if ruta_env.is_file()
        else []
    )
    prefijo = f'{nombre}='
    nuevas_lineas = []
    reemplazada = False
    for linea in lineas:
        if linea.strip().startswith(prefijo):
            nuevas_lineas.append(f'{prefijo}{valor}')
            reemplazada = True
        else:
            nuevas_lineas.append(linea)
    if not reemplazada:
        nuevas_lineas.append(f'{prefijo}{valor}')
    ruta_env.write_text(
        '\n'.join(nuevas_lineas).rstrip() + '\n',
        encoding='utf-8',
    )
    os.environ[nombre] = valor


def _detectar_servidor_sql() -> str:
    from cayal.comandos_base_datos import ComandosBaseDatos

    equipo = node().strip()
    servidor_explicito = os.getenv('CAYAL_DB_SERVER', '').strip()

    candidatos = (servidor_explicito, equipo, 'localhost')
    revisados: set[str] = set()
    for candidato in candidatos:
        clave = candidato.casefold()
        if not candidato or clave in revisados:
            continue
        revisados.add(clave)
        try:

            with redirect_stdout(StringIO()):
                comandos = ComandosBaseDatos(
                    servidor=candidato,
                    base_de_datos='ComercialSP',
                )
            filas = comandos.fetchall(
                """
                SELECT
                    DB_NAME() AS base_datos,
                    OBJECT_ID('dbo.orgProduct') AS org_product,
                    OBJECT_ID('dbo.docDocument') AS doc_document
                """,
                (),
            )
            if (
                filas
                and str(filas[0].get('base_datos') or '').casefold()
                    == 'comercialsp'
                and filas[0].get('org_product')
                and filas[0].get('doc_document')
            ):
                return candidato
        except Exception:
            continue
    raise RuntimeError(
        'No se encontró una instancia SQL compatible con ComercialSP. '
        'Defina CAYAL_DB_SERVER en el archivo .env.'
    )


def _preparar_destino_sql() -> str:
    servidor = _detectar_servidor_sql()
    equipo = node().strip().casefold()
    servidor_normalizado = servidor.strip().casefold()
    es_remoto = servidor_normalizado not in {
        equipo,
        'localhost',
        '.',
        '(local)',
        '127.0.0.1',
    }
    _actualizar_variable_env('CAYAL_DB_SERVER', servidor)
    _actualizar_variable_env('CAYAL_DB_NAME', 'ComercialSP')
    _actualizar_variable_env(
        'CAYAL_PERMITIR_SERVIDOR_REMOTO',
        '1' if es_remoto else '0',
    )
    return servidor


if __name__ == "__main__":
    servidor_detectado = _preparar_destino_sql()
    from app.utils.inicializador_base_datos import (
        inicializar_base_datos_modulo,
    )

    reporte = inicializar_base_datos_modulo()
    salida = asdict(reporte)
    salida['servidor_detectado'] = servidor_detectado
    salida['creacion_indices'] = False
    print(json.dumps(salida, ensure_ascii=False, indent=2))
