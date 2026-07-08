"""
Logging estructurado (fix #11). Antes: `logger.info` con f-strings/%s sueltos —
inconsistente con la promesa de "trazabilidad auditable" que se vende en la
reunión, donde el `trace` de negocio en Postgres sí es JSON estructurado pero
los logs de aplicación eran texto libre. Ahora cada línea de log es un JSON
parseable (ts, level, logger, message, exc_info si aplica), sin tocar los call
sites existentes — cero riesgo de romper los `logger.info("... | %s ...", x)`
ya escritos en cada nodo.
"""

import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts":     datetime.now(timezone.utc).isoformat(),
            "level":  record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_json_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
