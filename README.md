# DECISIO — Motor de Crédito iO

Motor de decisión crediticia. LangGraph + FastAPI + PostgreSQL + Claude Sonnet 4.6 + React.
Demo para primera reunión con Banco iO.

**Estado: Semana 2 completa.** Backend con human-in-the-loop real (`interrupt()` +
`AsyncPostgresSaver`) y frontend funcional (vista cliente + vista agente). Ver
`Handoff_Semana2_HITL_Frontend.md` para el detalle técnico de esta ronda.

---

## Setup — Backend

### Paso 1 — Variables de entorno

```bash
cp .env.example .env
```

Poner `ANTHROPIC_API_KEY`. El resto de valores funcionan tal cual para desarrollo local.

### Paso 2 — Dependencias Python

```bash
pip install -r requirements.txt
```

Incluye `langgraph-checkpoint-postgres` (nuevo en Semana 2 — checkpointer real).

### Paso 3 — Levantar Postgres

```bash
docker compose up -d postgres
```

**Si el volumen de Postgres ya existía de Semana 1**, correr la migración a mano
(agrega `explanation`/`context`/columnas de idempotencia que `ADD COLUMN IF NOT
EXISTS` no reaplica solo):

```bash
docker compose exec -T postgres psql -U decisio -d decisio < app/db/init.sql
```

### Paso 4 — Levantar el servidor

```bash
PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Logs esperados en el arranque:
```
Postgres pool inicializado (autocommit=True)
checkpointer | AsyncPostgresSaver.setup() OK — tablas de checkpoint listas
graph | compilado con checkpointer Postgres — interrupt()/resume habilitado
DECISIO — online (HITL real con interrupt()/AsyncPostgresSaver)
```

**autocommit=True es obligatorio** desde esta ronda — sin eso, `checkpointer.setup()`
revienta porque sus migraciones corren `CREATE INDEX CONCURRENTLY`, que Postgres
prohíbe dentro de una transacción explícita. Ver comentario en `app/db/connection.py`.

### Paso 5 — Test de las 8 rutas

```bash
PYTHONPATH=. python tests/test_paths.py
```

Debe dar `8/8 tests pasaron`. Los 4 perfiles de `hallazgo_menor`/staleness/anómalos
quedan en `pending_human` — es esperado, ya no se auto-resuelven como en Semana 1
placeholder. Para cerrarlos manualmente:

```bash
curl http://localhost:8000/cases                              # ver bandeja
curl -X POST http://localhost:8000/cases/{id}/resolve \
  -H "Content-Type: application/json" \
  -d '{"action":"honor","resolved_by":"tu_usuario"}'
```

`action` acepta `honor` / `adjust` (requiere `adjusted_amount`) / `revoke`.

---

## Setup — Frontend

```bash
cd frontend
npm install
npm run dev
```

Abre `http://localhost:5173`. El dev server proxea `/decision`, `/cases`,
`/trace`, `/metrics`, `/health` hacia `http://localhost:8000` (ver
`vite.config.js`) — sin esto correr `npm run dev` solo, el fetch a rutas
relativas no llega a ningún lado.

Dos vistas, switcheables desde el header:
- **Vista cliente**: simula tocar la notificación push de uno de los 8 perfiles
  curados (espejo exacto de `data/profiles.py` en `src/demoProfiles.js`) → oferta
  con slider → verificación de identidad (contraseña, proxy de demo) → llamada
  real a `POST /decision` → resultado con cronómetro real y comparativo Interbank.
  Si el caso escala a un agente, hace polling real a `GET /decision/{id}` hasta
  que se resuelve — sin websockets, fuera de alcance de la demo.
- **Vista agente**: bandeja de casos pendientes (polling a `GET /cases`), detalle
  con perfil completo del cliente + oferta + razonamiento AI, y resolución con un
  clic (honrar / ajustar / revocar) contra `POST /cases/{id}/resolve`.

`npm run build` genera `dist/` — validado que compila limpio antes de esta entrega.

---

## Estructura del proyecto

```
decisio-io/
├── app/
│   ├── main.py                        # FastAPI — arranca pool, checkpointer y grafo en orden
│   ├── graph/
│   │   ├── state.py
│   │   ├── graph.py                   # Compilación diferida + interrupt()/resume
│   │   ├── checkpointer.py            # NUEVO — AsyncPostgresSaver sobre el pool compartido
│   │   └── nodes/
│   │       ├── ingest.py
│   │       ├── bounds_check.py        # G1 (bounds monto) + G4 (inputs anómalos)
│   │       ├── rules_engine.py
│   │       ├── ai_assessor.py
│   │       ├── ai_explainer.py
│   │       ├── guardrails.py          # G2 (coherencia regla-AI) + G3 (confianza mínima)
│   │       ├── auto_decision.py
│   │       ├── human_in_loop.py       # REAL — interrupt() de LangGraph, ya no placeholder
│   │       └── finalize.py
│   ├── api/
│   │   ├── schemas.py                 # + CaseResolutionRequest (Semana 2)
│   │   └── routes/
│   │       ├── decision.py            # POST /decision + GET /decision/{id} (polling)
│   │       ├── trace.py
│   │       ├── metrics.py
│   │       └── cases.py               # GET /cases + GET /cases/{id} + POST /cases/{id}/resolve
│   └── db/
│       ├── connection.py              # autocommit=True + get_pool()
│       └── init.sql                   # + explanation, context (Semana 2)
├── frontend/                          # NUEVO — Vite + React
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx / App.css
│       ├── api.js
│       ├── demoProfiles.js            # espejo de data/profiles.py
│       └── components/
│           ├── ClienteView.jsx
│           └── AgenteView.jsx
├── data/profiles.py
├── tests/test_paths.py
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Estado del servidor y DB |
| POST | `/decision` | Motor principal — puede volver `pending_human` (grafo pausado) |
| GET | `/decision/{id}` | Polling de estado — para la vista cliente mientras espera agente |
| GET | `/trace/{id}` | Trace completo de una decisión |
| GET | `/metrics` | Métricas agregadas |
| GET | `/cases` | Bandeja de casos pendientes, con contexto completo |
| GET | `/cases/{id}` | Detalle de un caso |
| POST | `/cases/{id}/resolve` | Reanuda el grafo — honor / adjust / revoke |

---

## Flujo hacia el VPS

```bash
git add . && git commit -m "feat: semana 2 — HITL real + frontend"
git push

# VPS
git pull
docker compose exec -T postgres psql -U decisio -d decisio < app/db/init.sql   # migración a mano
docker compose up -d --build
```

El `.env` nunca entra al repo. Si algo no toma los cambios, `docker compose up -d
--build --force-recreate` (aprendizaje de la ronda anterior: el deploy silencioso
es el enemigo real).

---

## Semana 3 — lo que sigue

- Dashboard de observabilidad (React) sobre `GET /metrics`
- Trazabilidad completa por caso (timeline click-through) — hoy el trace de un
  caso pendiente solo muestra la fila placeholder, el timeline detallado llega
  con `finalize`, después de resolver
- Despliegue al VPS: Nginx + HTTPS + dominio propio
- Curación final de los perfiles de demo + guion de 15 min ensayado
