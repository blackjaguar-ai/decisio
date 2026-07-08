# DECISIO — Motor de Crédito iO

Motor de decisión crediticia. LangGraph + FastAPI + PostgreSQL + Claude Sonnet 4.6.
Demo para primera reunión con Banco iO.

---

## Setup paso a paso

### Paso 1 — Variables de entorno

```bash
cp .env.example .env
```

Abrir `.env` y poner la `ANTHROPIC_API_KEY`. El resto de valores funcionan tal cual para desarrollo local.

**Verificar:** el archivo `.env` existe y tiene la API key. No está en el repo (está en `.gitignore`).

---

### Paso 2 — Dependencias Python

```bash
pip install -r requirements.txt
```

**Verificar:**
```bash
python -c "from langgraph.graph import StateGraph; from anthropic import Anthropic; import psycopg; print('OK')"
```
Debe imprimir `OK` sin errores.

---

### Paso 3 — Levantar Postgres

```bash
docker compose up -d postgres
```

**Verificar:**
```bash
docker compose ps
```
El contenedor `decisio_db` debe estar en estado `healthy`. Si dice `starting`, esperar 10 segundos y volver a correr el comando. El schema se crea automáticamente desde `app/db/init.sql`.

Para confirmar que las tablas existen:
```bash
docker exec -it decisio_db psql -U decisio -c "\dt"
```
Debe mostrar: `decisions`, `traces`, `cases`, `metrics`.

---

### Paso 4 — Levantar el servidor

```bash
PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Verificar:**
```bash
curl http://localhost:8000/health
```
Respuesta esperada:
```json
{"status": "ok", "db": "2026-07-06 ..."}
```

Los logs del servidor deben mostrar:
```
DECISIO — online
Postgres pool inicializado
```

---

### Paso 5 — Test de los 4 caminos (Día 10)

Con el servidor corriendo, en otra terminal:

```bash
PYTHONPATH=. python tests/test_paths.py
```

Resultado esperado:
```
══════════════════════════════════════════════════════
  DECISIO — Test 4 Caminos | Semana 1 Día 10
══════════════════════════════════════════════════════
  ✓ Servidor online

  clean_approval_1
  Esperado: approved
  Resultado : approved
  Route     : auto | Latencia: ~2000ms
  ✓ PASS

  gray_zone_1
  Esperado: pending_human
  Resultado : pending_human
  Route     : human | Latencia: ~3000ms
  ✓ PASS

  high_amount
  Esperado: pending_human
  Resultado : pending_human
  Route     : human | Latencia: ~2500ms
  ✓ PASS

  hard_rejection
  Esperado: rejected
  Resultado : rejected
  Route     : auto | Latencia: ~2000ms
  ✓ PASS

  RESULTADO: 4/4 tests pasaron
```

---

### Paso 6 — Verificar trazabilidad (opcional pero recomendado)

Tomar un `decision_id` del output del test anterior y consultar el trace completo:

```bash
curl http://localhost:8000/trace/{decision_id} | python -m json.tool
```

Debe retornar el timeline completo: ingest → rules_engine → ai_explainer → pre_guardrails → guardrails → auto_decision/human_in_loop → finalize.

---

### Paso 7 — Verificar métricas

```bash
curl http://localhost:8000/metrics | python -m json.tool
```

Respuesta esperada (después de correr los 4 tests):
```json
{
  "totals": {"total": 4, "approved": 1, "rejected": 1, "pending_human": 2},
  "latency_ms": {"avg": 2300.0, ...},
  "path_distribution": {"auto_approved": 1, "auto_rejected": 1, "human_escalated": 2}
}
```

---

## Estructura del proyecto

```
decisio-io/
├── app/
│   ├── main.py                        # FastAPI entry point
│   ├── graph/
│   │   ├── state.py                   # CreditState TypedDict
│   │   ├── graph.py                   # Grafo LangGraph compilado
│   │   └── nodes/
│   │       ├── ingest.py              # Normaliza y valida el perfil
│   │       ├── rules_engine.py        # Reglas determinísticas (sin AI)
│   │       ├── ai_assessor.py         # LLM evalúa zona gris
│   │       ├── ai_explainer.py        # LLM genera justificación auditable
│   │       ├── guardrails.py          # Límites duros post-decisión
│   │       ├── auto_decision.py       # Aplica decisión automática
│   │       ├── human_in_loop.py       # Placeholder → interrupt() en Semana 2
│   │       └── finalize.py            # Consolida y persiste en Postgres
│   ├── api/
│   │   ├── schemas.py                 # Pydantic models
│   │   └── routes/
│   │       ├── decision.py            # POST /decision
│   │       ├── trace.py               # GET /trace/{id}
│   │       ├── metrics.py             # GET /metrics
│   │       └── cases.py               # GET /cases (Semana 2)
│   └── db/
│       ├── connection.py              # Pool psycopg v3 async
│       └── init.sql                   # Schema: decisions, traces, cases, metrics
├── data/
│   └── profiles.py                    # 7 perfiles sintéticos curados
├── tests/
│   └── test_paths.py                  # Verificación de los 4 caminos
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Endpoints disponibles (Semana 1)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Estado del servidor y DB |
| POST | `/decision` | Motor principal de decisión |
| GET | `/trace/{id}` | Trace completo de una decisión |
| GET | `/metrics` | Métricas agregadas |
| GET | `/cases` | Bandeja de casos escalados (Semana 2) |

---

## Flujo hacia el VPS (cuando esté listo)

```bash
# Local
git init && git add . && git commit -m "feat: semana 1 — backend completo"
git remote add origin git@github.com:tu-usuario/decisio.git
git push -u origin master

# VPS (una sola vez)
git clone git@github.com:tu-usuario/decisio-io.git
cd decisio-io && cp .env.example .env  # poner API key
docker compose up -d

# Cada deploy siguiente
git pull && docker compose restart
```

El `.env` nunca entra al repo.

---

## Semana 2 — Lo que viene

- `interrupt()` de LangGraph reemplaza el placeholder en `human_in_loop.py`
- `AsyncPostgresSaver` para persistir el estado pausado del grafo
- `POST /cases/{id}/resolve` para que el agente reanude el grafo
- Frontend React: vista cliente + vista agente + dashboard
