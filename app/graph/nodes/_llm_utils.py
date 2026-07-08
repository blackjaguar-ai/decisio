"""
Utilidades compartidas entre ai_assessor y ai_explainer.

Fix #6 — parseo de JSON tolerante: antes solo se hacía strip() de backticks;
si el modelo agregaba una frase de cortesía antes o después del JSON pese a
las reglas del SYSTEM, el parseo truena directo al fallback. Ahora hay un
segundo intento: extraer el primer bloque {...} balanceado del texto crudo.

Fix #7 — timeout explícito + un reintento antes de rendirse al fallback
determinístico. El argumento central de la demo es "8 segundos vs 72 horas";
si la API externa se cuelga sin timeout, ese cronómetro se rompe en vivo.
"""

import json
import logging

logger = logging.getLogger(__name__)

LLM_TIMEOUT_SECONDS = 20.0
LLM_MAX_ATTEMPTS = 2


def call_llm(client, model: str, system: str, prompt: str, max_tokens: int,
             decision_id: str, node: str) -> str:
    """Llama al LLM con timeout explícito. Un reintento antes de propagar el error
    al caller, que debe caer a su fallback determinístico."""
    last_error: Exception | None = None
    for attempt in range(1, LLM_MAX_ATTEMPTS + 1):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                timeout=LLM_TIMEOUT_SECONDS,
            )
            return response.content[0].text.strip()
        except Exception as e:
            last_error = e
            logger.warning("%s | %s | intento %d/%d falló: %s",
                          node, decision_id, attempt, LLM_MAX_ATTEMPTS, e)
    raise last_error


def parse_llm_json(raw: str) -> dict:
    """Parsea JSON de una respuesta de LLM. Primer intento: directo, tras strip
    de backticks. Segundo intento: extraer el primer objeto {...} balanceado del
    texto completo, por si el modelo agregó texto adicional pese al SYSTEM."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    if start == -1:
        raise ValueError("No se encontró ningún '{' en la respuesta del modelo")

    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(raw[start:i + 1])

    raise ValueError("No se encontró un bloque JSON balanceado en la respuesta del modelo")
