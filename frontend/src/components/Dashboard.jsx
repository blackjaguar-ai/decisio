import { useEffect, useState, useCallback, useMemo } from "react";
import {
  ResponsiveContainer, PieChart, Pie, Cell,
  LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import { getMetrics } from "../api.js";

const REFRESH_MS = 5000;
const TARGET_LATENCY_MS = 30_000; // objetivo de la propuesta: <30s (Propuesta §1)
const OLD_SLA_MS = 72 * 60 * 60 * 1000; // 72h — el proceso actual de iO

const OUTCOME_LABELS = {
  honored: "Honrada",
  revoked: "Revocada",
  pending_human: "En revisión",
  identity_verification_failed: "Identidad rechazada",
};

const GUARDRAIL_LABELS = {
  amount_staleness: "Staleness de monto",
  amount_tampering: "Tampering de monto",
  rule_ai_conflict: "Conflicto regla / AI",
  invalid_ai_recommendation: "Recomendación AI inválida",
  low_ai_confidence: "Confianza AI baja",
  anomalous_inputs: "Inputs anómalos",
};

const RESOLUTION_LABELS = { honor: "Honrar oferta", adjust: "Ajustar monto", revoke: "Revocar" };

const PIE_COLORS = {
  auto_honored: "#2fd1d9",
  auto_revoked: "#e5484d",
  human_escalated: "#5b62f4",
  unknown: "#9aa1a8",
};

function formatMs(ms) {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function formatMoney(n) {
  if (n === null || n === undefined) return "—";
  return "S/ " + Number(n).toLocaleString("es-PE", { maximumFractionDigits: 0 });
}

function formatTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("es-PE", { hour12: false });
}

/** Ring de latencia — calcado del donut "Cashback Obtenido" del landing real
 * de iO: fondo negro con glow índigo→cian, cifra grande al centro. Muestra
 * qué tan lejos está el promedio real medido de la meta de 30s — nunca un
 * número inventado, siempre `metrics.latency_ms.avg` tal como lo mide
 * finalize.py con time.time(). */
function LatencyRing({ avgMs }) {
  const pct = avgMs ? Math.min(avgMs / TARGET_LATENCY_MS, 1) : 0;
  const r = 64;
  const circumference = 2 * Math.PI * r;
  const dash = circumference * pct;
  return (
    <svg width="160" height="160" viewBox="0 0 160 160">
      <circle cx="80" cy="80" r={r} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="14" />
      <circle
        cx="80" cy="80" r={r} fill="none" stroke="url(#ringGrad)" strokeWidth="14"
        strokeDasharray={`${dash} ${circumference - dash}`}
        strokeLinecap="round"
        transform="rotate(-90 80 80)"
      />
      <defs>
        <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#5b62f4" />
          <stop offset="100%" stopColor="#2fd1d9" />
        </linearGradient>
      </defs>
      <text x="80" y="76" textAnchor="middle" fill="#fff" fontSize="24" fontWeight="800"
            fontFamily="ui-monospace, 'SF Mono', monospace">
        {avgMs ? formatMs(avgMs) : "—"}
      </text>
      <text x="80" y="96" textAnchor="middle" fill="rgba(255,255,255,0.55)" fontSize="10.5">
        latencia real
      </text>
    </svg>
  );
}

function BarList({ data, labels, danger = false }) {
  const entries = Object.entries(data || {});
  if (entries.length === 0) {
    return <p className="agent-empty" style={{ padding: "8px 0" }}>Sin eventos registrados todavía.</p>;
  }
  const max = Math.max(...entries.map(([, v]) => v), 1);
  return (
    <div className="bar-list">
      {entries.sort((a, b) => b[1] - a[1]).map(([key, value]) => (
        <div className="bar-list__row" key={key}>
          <span className="bar-list__label">{labels[key] || key}</span>
          <span className="bar-list__track">
            <span
              className={"bar-list__fill" + (danger ? " bar-list__fill--danger" : "")}
              style={{ width: `${(value / max) * 100}%` }}
            />
          </span>
          <span className="bar-list__value">{value}</span>
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const [metrics, setMetrics] = useState(null);
  const [err, setErr] = useState("");

  const refresh = useCallback(async () => {
    try {
      const data = await getMetrics();
      setMetrics(data);
      setErr("");
    } catch (e) {
      setErr("No se pudo conectar con el motor — reintentando…");
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, REFRESH_MS);
    return () => clearInterval(t);
  }, [refresh]);

  const pieData = useMemo(() => {
    if (!metrics) return [];
    return Object.entries(metrics.path_distribution || {})
      .filter(([path]) => path !== "identity_blocked")
      .map(([path, count]) => ({ name: path, value: count }));
  }, [metrics]);

  const trendData = useMemo(() => {
    if (!metrics) return [];
    // Solo camino automático: mezclar con latencia de casos HITL (que incluye
    // minutos reales de espera de agente) aplastaría la línea auto a cero en
    // la misma escala. Los casos con humano se ven en el feed de abajo, con
    // su latencia real intacta y su propio pill de "En revisión"/"Honrada".
    return [...metrics.recent]
      .filter((r) => r.latency_ms !== null && r.latency_ms !== undefined
                  && (r.path === "auto_honored" || r.path === "auto_revoked"))
      .reverse()
      .map((r, i) => ({ idx: i + 1, ms: r.latency_ms, time: formatTime(r.created_at) }));
  }, [metrics]);

  if (!metrics && !err) {
    return (
      <div className="dashboard">
        <div className="dashboard__empty">Cargando métricas en vivo…</div>
      </div>
    );
  }

  if (metrics && metrics.totals.total === 0) {
    return (
      <div className="dashboard">
        <div className="dashboard__header">
          <div>
            <h1 className="dashboard__title">Observabilidad DECISIO</h1>
            <p className="dashboard__subtitle">Aún no hay decisiones registradas.</p>
          </div>
        </div>
        <div className="dashboard__empty">
          Corre el primer perfil desde la vista cliente para ver métricas reales aquí —
          este panel no muestra datos de ejemplo, solo lo que el motor ya procesó.
        </div>
      </div>
    );
  }

  const t = metrics?.totals || {};
  const lat = metrics?.latency_ms || {};
  // FIX Semana 3: el ring y el "Nx más rápido" deben venir SIEMPRE de
  // `avg_auto` (solo decisiones sin intervención humana). `lat.avg` mezcla
  // el tiempo real de espera de un agente en casos HITL — usarlo aquí fue
  // el bug que infló el ring a 101.9s con un solo caso escalado. Ver nota
  // en metrics.py.
  const cleanAvg = lat.avg_auto || 0;
  const speedupX = cleanAvg ? Math.round(OLD_SLA_MS / cleanAvg) : null;

  return (
    <div className="dashboard">
      <div className="dashboard__header">
        <div>
          <h1 className="dashboard__title">Observabilidad DECISIO</h1>
          <p className="dashboard__subtitle">
            Cada cifra viene de decisiones ya ejecutadas contra el motor real — nada simulado.
          </p>
        </div>
        <div className="dashboard__status">
          <span className="live-dot" />
          {err ? err : `Actualizado — refresco cada ${REFRESH_MS / 1000}s`}
        </div>
      </div>

      <div className="dash-grid">
        <div className="hero-latency">
          <div className="hero-latency__ring-wrap">
            <LatencyRing avgMs={cleanAvg} />
          </div>
          <div className="hero-latency__body">
            <div className="hero-latency__eyebrow">
              Camino limpio (auto) — {lat.n_auto || 0} decisión(es) sin intervención humana
            </div>
            <h2 className="hero-latency__title">
              {speedupX ? `${speedupX}x más rápido que el proceso actual` : "Esperando decisiones automáticas"}
            </h2>
            <p className="hero-latency__compare">
              Camino limpio (auto): <strong>{formatMs(lat.avg_auto)}</strong> (n={lat.n_auto || 0})<br />
              Con escalamiento humano: <strong>{formatMs(lat.avg_human_escalation)}</strong> (n={lat.n_human || 0}) —
              incluye tiempo real de espera del agente, no es latencia del motor<br />
              Proceso actual de iO: <strong>72 h</strong>
            </p>
          </div>
        </div>

        <div className="dash-card dash-card--cyan">
          <div className="dash-card__label">Decisiones totales</div>
          <div className="dash-card__value">{t.total}</div>
          <div className="dash-card__meta">{t.honored} honradas · {t.revoked} revocadas</div>
        </div>

        <div className="dash-card dash-card--indigo">
          <div className="dash-card__label">Intervención humana</div>
          <div className="dash-card__value">{Math.round((metrics.human_intervention_rate || 0) * 100)}%</div>
          <div className="dash-card__meta">{metrics.pending_cases_now} caso(s) pendiente(s) ahora</div>
        </div>

        <div className="dash-card dash-card--lilac">
          <div className="dash-card__label">Gate de identidad</div>
          <div className="dash-card__value">{t.identity_blocked}</div>
          <div className="dash-card__meta">verificaciones bloqueadas antes de tocar el grafo</div>
        </div>
      </div>

      <div className="dash-row">
        <div className="panel">
          <h3 className="panel__title">Tendencia de latencia real — solo camino automático</h3>
          <div className="chart-wrap">
            {trendData.length > 1 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke="var(--border-light)" vertical={false} />
                  <XAxis dataKey="time" tick={{ fontSize: 10, fill: "var(--slate-light)" }} />
                  <YAxis tick={{ fontSize: 10, fill: "var(--slate-light)" }}
                         tickFormatter={(v) => formatMs(v)} width={54} />
                  <Tooltip formatter={(v) => formatMs(v)} labelFormatter={(l) => `Decisión — ${l}`} />
                  <Line type="monotone" dataKey="ms" stroke="#5b62f4" strokeWidth={2}
                        dot={{ r: 3, fill: "#2fd1d9" }} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="agent-empty">Se necesitan al menos 2 decisiones para graficar tendencia.</p>
            )}
          </div>
        </div>

        <div className="panel">
          <h3 className="panel__title">Distribución por camino</h3>
          <div className="chart-wrap">
            {pieData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85}
                       paddingAngle={3}>
                    {pieData.map((entry) => (
                      <Cell key={entry.name} fill={PIE_COLORS[entry.name] || PIE_COLORS.unknown} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="agent-empty">Sin datos todavía.</p>
            )}
          </div>
        </div>
      </div>

      <div className="dash-row">
        <div className="panel">
          <h3 className="panel__title">Guardrails disparados</h3>
          <BarList data={metrics.guardrail_counts} labels={GUARDRAIL_LABELS} danger />
        </div>
        <div className="panel">
          <h3 className="panel__title">Resoluciones del agente</h3>
          <BarList data={metrics.human_resolutions} labels={RESOLUTION_LABELS} />
        </div>
      </div>

      <div className="panel">
        <h3 className="panel__title">Actividad por agente</h3>
        <BarList data={metrics.agent_activity} labels={{}} />
      </div>

      <div className="panel">
        <h3 className="panel__title">Últimas decisiones (feed en vivo)</h3>
        <div className="table-scroll">
          <table className="feed-table">
            <thead>
              <tr>
                <th>Hora</th>
                <th>Resultado</th>
                <th>Camino</th>
                <th>Decidido por</th>
                <th>Monto</th>
                <th>Latencia real</th>
              </tr>
            </thead>
            <tbody>
              {metrics.recent.slice(0, 12).map((r) => (
                <tr key={r.decision_id}>
                  <td>{formatTime(r.created_at)}</td>
                  <td>
                    <span className={"pill-outcome pill-outcome--" + r.outcome}>
                      {OUTCOME_LABELS[r.outcome] || r.outcome}
                    </span>
                  </td>
                  <td>{r.route}</td>
                  <td>{r.decided_by || "—"}</td>
                  <td>{formatMoney(r.approved_amount)}</td>
                  <td>{formatMs(r.latency_ms)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
