import json
import unicodedata
from functools import lru_cache
from pathlib import Path


RUTA_CONFIGURACION = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "merma_por_tipo.json"
)


def normalizar(texto):
    texto_normalizado = unicodedata.normalize(
        "NFD",
        str(texto or ""),
    )

    return "".join(
        caracter
        for caracter in texto_normalizado
        if unicodedata.category(caracter) != "Mn"
    ).upper()


@lru_cache(maxsize=1)
def cargar_reglas_merma():
    with RUTA_CONFIGURACION.open(encoding="utf-8") as archivo:
        return json.load(archivo)


def regla_default():
    configuracion = cargar_reglas_merma()
    regla = configuracion["default"]

    return {
        "porcentaje": regla["porcentaje"],
        "descripcion": regla["descripcion"],
        "fuente": "default",
    }


def obtener_merma_estimada(producto):
    configuracion = cargar_reglas_merma()
    categoria = normalizar(producto.get("Category1"))
    nombre = normalizar(producto.get("ProductName"))

    for regla in configuracion.get("categorias", []):
        texto = normalizar(regla.get("texto"))

        if texto and (texto in categoria or texto in nombre):
            return {
                "porcentaje": regla["porcentaje"],
                "descripcion": regla["descripcion"],
                "fuente": "categoria",
            }

    return regla_default()
