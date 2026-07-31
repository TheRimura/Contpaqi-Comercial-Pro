import json
import sys
from dataclasses import asdict
from pathlib import Path


RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

try:
    from dotenv import load_dotenv
    load_dotenv(RAIZ_PROYECTO / '.env')
except ImportError:
    pass

from app.utils.inicializador_base_datos import (  # noqa: E402
    inicializar_base_datos_modulo,
)


if __name__ == "__main__":
    reporte = inicializar_base_datos_modulo()
    print(json.dumps(asdict(reporte), ensure_ascii=False, indent=2))
