# DECISIO — Motor de Crédito iO

Motor de decisión crediticia. LangGraph + FastAPI + PostgreSQL + Claude Sonnet 4.6 + React.
Demo para primera reunión con Banco iO.

**Estado: Semana 3 en curso.** Backend con human-in-the-loop real (`interrupt()` +
`AsyncPostgresSaver`), frontend con 4 vistas (Cómo funciona / Vista cliente / Vista
agente / Dashboard), rebrand real de iO (Inter auto-hospedado, paleta real, logo con
bind mount) y dashboard de observabilidad sobre `GET /metrics`. Ver
`Handoff_Semana3_Dashboard_ComoFunciona_Fixes.md` para el detalle técnico de esta
ronda — incluye un fix crítico de latencia (HITL contaminaba el "camino limpio" del
dashboard) y dos fixes de UI descubiertos corriendo la demo real contra el VPS.

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

Incluye `langgraph-checkpoint-postgres` (Semana 2 — checkpointer real).

### Paso 3 — Levantar Postgres

```bash
docker compose up -d postgres
```

**Si el volumen de Postgres ya existía de una ronda anterior**, correr la migración a
mano (agrega columnas que `ADD COLUMN IF NOT EXISTS` no reaplica solo):

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

**autocommit=True es obligatorio** — sin eso, `checkpointer.setup()` revienta porque
sus migraciones corren `CREATE INDEX CONCURRENTLY`, que Postgres prohíbe dentro de una
transacción explícita. Ver comentario en `app/db/connection.py`.

### Paso 5 — Test de las 8 rutas

```bash
PYTHONPATH=. python tests/test_paths.py
```

Debe dar `8/8 tests pasaron`. Los perfiles de `hallazgo_menor`/staleness/anómalos
quedan en `pending_human` — es esperado. Para cerrarlos manualmente:

```bash
curl http://localhost:8000/cases                              # ver bandeja
curl -X POST http://localhost:8000/cases/{id}/resolve \
  -H "Content-Type: application/json" \
  -d '{"action":"honor","resolved_by":"tu_usuario"}'
```

`action` acepta `honor` / `adjust` (requiere `adjusted_amount`) / `revoke`.

**Antes de un ensayo real**, limpiar datos de prueba viejos (quedan con
clasificaciones de métricas de rondas anteriores):

```sql
TRUNCATE metrics, traces, cases, decisions;
```

---

## Setup — Frontend

```bash
cd frontend
npm install
npm run dev
```

Abre `http://localhost:5173`. El dev server proxea `/decision`, `/cases`, `/trace`,
`/metrics`, `/health` hacia `http://localhost:8000` (ver `vite.config.js`) — sin esto
correr `npm run dev` solo, el fetch a rutas relativas no llega a ningún lado.

`npm install` trae dos dependencias nuevas desde Semana 3: `recharts` (gráficos del
dashboard) y `@fontsource/inter` (tipografía real de iO, auto-hospedada — nunca llama
a Google Fonts en runtime, ver `main.jsx`).

Cuatro vistas, switcheables desde el header (píldoras en desktop, hamburguesa +
desplegable en mobile):

- **Cómo funciona** (`AboutView.jsx`): vista explicativa del proyecto DECISIO en sí
  mismo — no simula la app de iO, así que lleva la identidad propia de Escai Tech
  (copper/cyan/petróleo, tonos sólidos). Hero animado, staircase de los 6 nodos reales
  del grafo, stats y compliance, todo con reveal-on-scroll.
- **Vista cliente** (`ClienteView.jsx`): popup de redirección simulando el deep-link
  real de la notificación push → elige uno de los perfiles curados (espejo de
  `data/profiles.py` en `demoProfiles.js`) → oferta con slider → verificación de
  identidad → llamada real a `POST /decision` → resultado con cronómetro real. Si el
  caso escala a un agente, hace polling real a `GET /decision/{id}` hasta que se
  resuelve. Paleta real de iO — mockup de teléfono con proporción real (19.5:9).
- **Vista agente** (`AgenteView.jsx`): bandeja de casos pendientes (polling a
  `GET /cases`), detalle con perfil completo + oferta + razonamiento AI (o, si el caso
  escaló por un guardrail sin pasar por la AI, un panel distinto que lo deja explícito
  en vez de mostrar un "sin confianza" indistinguible de un error), resolución con un
  clic contra `POST /cases/{id}/resolve`.
- **Dashboard** (`Dashboard.jsx`): observabilidad sobre `GET /metrics` — ring de
  latencia real (solo camino automático, nunca mezclado con tiempo de espera humana),
  tendencia, distribución por camino, guardrails disparados, resoluciones por agente,
  feed en vivo. Paleta real de iO.

`npm run build` genera `dist/` — validado que compila limpio antes de cada entrega de
esta ronda (bundle final ~589KB / ~168KB gzip).

### Logo de marca

`frontend/public/brand/` es una carpeta con bind mount de solo lectura montada en
`docker-compose.yml` sobre el contenedor de Nginx — subir `logo-io.svg` (o `.png`) ahí
en el VPS se refleja con un refresh del navegador, **sin rebuild**. Instrucciones
completas en `frontend/public/brand/README.md`. Mientras no se suba el archivo real,
corre con un fallback (`logo-io-ring.png`, extraído del logo real de iO) — no se ve
roto, no es el isotipo completo.

---

## Estructura del proyecto

```
decisio-io/
├── app/
│   ├── main.py                        # FastAPI — arranca pool, checkpointer y grafo en orden
│   ├── graph/
│   │   ├── state.py
│   │   ├── graph.py                   # Compilación diferida + interrupt()/resume
│   │   ├── checkpointer.py            # AsyncPostgresSaver sobre el pool compartido
│   │   └── nodes/
│   │       ├── ingest.py
│   │       ├── bounds_check.py        # G1 (bounds monto) + G4 (inputs anómalos)
│   │       ├── rules_engine.py
│   │       ├── ai_assessor.py
│   │       ├── ai_explainer.py
│   │       ├── guardrails.py          # G2 (coherencia regla-AI) + G3 (confianza mínima)
│   │       ├── auto_decision.py
│   │       ├── human_in_loop.py       # interrupt() real + escalation_reason con guardrails (Semana 3)
│   │       └── finalize.py            # path por route, no por outcome (fix Semana 3)
│   ├── api/
│   │   ├── schemas.py
│   │   └── routes/
│   │       ├── decision.py            # POST /decision + GET /decision/{id} + log identity_blocked
│   │       ├── trace.py
│   │       ├── metrics.py             # extendido Semana 3: guardrails, agentes, n_auto/n_human
│   │       └── cases.py
│   └── db/
│       ├── connection.py              # autocommit=True + get_pool()
│       └── init.sql
├── frontend/
│   ├── vite.config.js
│   ├── package.json                   # + recharts, @fontsource/inter
│   ├── public/
│   │   └── brand/                     # NUEVO — bind mount, logo sin rebuild
│   │       ├── README.md
│   │       └── logo-io-ring.png
│   └── src/
│       ├── main.jsx                   # imports de @fontsource/inter (auto-hospedado)
│       ├── App.jsx                    # nav dual desktop/mobile, 4 vistas
│       ├── App.css                    # paleta iO real + paleta Escai (about-view) + phone-frame + mobile
│       ├── api.js                     # + getMetrics()
│       ├── demoProfiles.js            # espejo de data/profiles.py
│       └── components/
│           ├── AboutView.jsx          # NUEVO — vista explicativa, paleta Escai
│           ├── BrandLogo.jsx          # NUEVO — cadena de fallback de logo
│           ├── Dashboard.jsx          # NUEVO — observabilidad, paleta iO
│           ├── ClienteView.jsx        # + step "intro" (popup de redirección)
│           └── AgenteView.jsx         # fix input + panel guardrail-only
├── data/profiles.py
├── tests/test_paths.py
├── docker-compose.yml                 # + bind mount frontend/public/brand
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
| GET | `/metrics` | Métricas agregadas — extendido Semana 3 (ver Handoff §1.1) |
| GET | `/cases` | Bandeja de casos pendientes, con contexto completo |
| GET | `/cases/{id}` | Detalle de un caso |
| POST | `/cases/{id}/resolve` | Reanuda el grafo — honor / adjust / revoke |

---

## Flujo hacia el VPS

```bash
git add . && git commit -m "feat: semana 3 — dashboard, cómo funciona, fixes HITL/mobile, rebrand real"
git push

# VPS
git pull
docker compose exec -T postgres psql -U decisio -d decisio < app/db/init.sql   # migración a mano
docker compose up -d --build
```

El `.env` nunca entra al repo. Si algo no toma los cambios, `docker compose up -d
--build --force-recreate`.

**Después del primer deploy de esta ronda**, para reemplazar el logo real ya no hace
falta rebuild — solo `scp` a `frontend/public/brand/logo-io.svg` en el VPS y refresh.

---

## Semana 4 — lo que sigue

Ver Handoff_Semana3 §6 para el detalle completo. Resumen:

1. Correr los dos fixes críticos de esta ronda (latencia HITL, guardrail-only sin AI)
   contra el motor real — el primer caso HITL real post-deploy es la prueba de fuego.
2. Trazabilidad completa por caso (timeline click-through) — sigue pendiente desde
   Semana 2, diferida otra vez.
3. Confirmar en logs del VPS que la idempotencia nunca re-invoca `run_decision()` en
   un cache-hit — pendiente desde la ronda de auditoría.
4. Truncar datos de prueba antes del ensayo (quedaron casos con clasificaciones viejas
   de las rondas de fixes).
5. Curación final de perfiles + guion de 15 min ensayado.
6. Subir el logo SVG/PNG real de iO a `frontend/public/brand/`.
