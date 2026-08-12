import unittest
import re
from pathlib import Path

from app.settings import PERMISOS_MODULO
from app.utils.base_de_datos import BaseDatos


RAIZ = Path(__file__).resolve().parents[1]


class BaseDatosSimulada(BaseDatos):
    def __init__(self):
        self.consultas = []

    def fetchall(self, sql, params=()):
        self.consultas.append((sql, params))
        if "dbo.engRefCombo" in sql:
            return [{"ItemData": 5, "ItemValue": "TRANSFORMACION"}]
        tipo = params[1] if len(params) > 1 else ""
        return [{
            "relacion_id": 1,
            "fecha_hora": "2026-01-01",
            "tipo_documento": tipo,
            "partida_id": 1,
        }]


class PruebasRegresionModulo(unittest.TestCase):
    def test_catalogo_movimientos_no_necesita_union(self):
        base = BaseDatosSimulada()
        registros = base.buscar_tipo_movimiento_modulo(202)
        self.assertEqual(2, len(registros))
        self.assertEqual(0, registros[0]["ItemData"])
        self.assertNotIn("UNION", base.consultas[0][0].upper())

    def test_exportacion_combina_consultas_en_python(self):
        base = BaseDatosSimulada()
        registros = base.listar_documentos_relacionados_exportacion(10)
        self.assertEqual(2, len(registros))
        self.assertEqual({"SALIDA", "ENTRADA"}, {
            fila["tipo_documento"] for fila in registros
        })
        self.assertEqual(2, len(base.consultas))
        self.assertTrue(all("UNION" not in sql.upper() for sql, _ in base.consultas))

    def test_permiso_restauracion_esta_declarado(self):
        self.assertTrue(
            PERMISOS_MODULO.grupo_tiene_permiso(
                1, "restaurar_productos_catalogo"
            )
        )

    def test_sql_del_modulo_no_contiene_union(self):
        contenido = (RAIZ / "app/utils/base_de_datos.py").read_text(
            encoding="utf-8"
        ).upper()
        self.assertNotIn("UNION ALL", contenido)

    def test_ocultamiento_no_modifica_catalogo_global(self):
        contenido = (RAIZ / "app/utils/base_de_datos.py").read_text(
            encoding="utf-8"
        ).upper()
        self.assertNotIn("UPDATE DBO.ORGPRODUCT", contenido)
        self.assertNotIn("SET DISCONTINUEDON", contenido)

    def test_ids_usados_por_javascript_existen_en_las_plantillas(self):
        javascript = (RAIZ / "app/static/js/app.js").read_text(
            encoding="utf-8"
        )
        plantillas = "\n".join(
            ruta.read_text(encoding="utf-8")
            for ruta in (RAIZ / "app/templates").glob("*.html")
        )
        referencias = set(re.findall(
            r"getElementById\([\"']([^\"']+)", javascript
        ))
        identificadores = set(re.findall(
            r"\bid=[\"']([^\"']+)", plantillas
        ))
        self.assertEqual(set(), referencias - identificadores)


if __name__ == "__main__":
    unittest.main()
