import { useEffect, useState, useCallback } from "react";
import { listCases, resolveCase } from "../api.js";

const REFRESH_MS = 4000;

function formatMoney(n) {
  if (n === null || n === undefined) return "—";
  return "S/ " + Number(n).toLocaleString("es-PE", { maximumFractionDigits: 0 });
}

export default function AgenteView() {
  const [cases, setCases] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastResolved, setLastResolved] = useState(null);
  const [err, setErr] = useState("");

  const refresh = useCallback(async () => {
    try {
      const { cases } = await listCases();
      setCases(cases);
      setErr("");
    } catch (e) {
      setErr("No se pudo conectar con el motor — reintentando…");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, REFRESH_MS);
    return () => clearInterval(t);
  }, [refresh]);

  useEffect(() => {
    if (!cases.find((c) => c.id === selectedId)) {
      setSelectedId(cases[0]?.id ?? null);
    }
  }, [cases, selectedId]);

  const selected = cases.find((c) => c.id === selectedId) || null;

  async function handleResolve(action, resolvedBy, adjustedAmount) {
    if (!selected) return;
    try {
      const result = await resolveCase(selected.id, {
        action,
        resolved_by: resolvedBy || "agente_demo",
        adjusted_amount: adjustedAmount || null,
      });
      setLastResolved({ id: selected.id, name: selected.context?.customer?.name, result });
      setSelectedId(null);
      refresh();
    } catch (e) {
      setErr(e.message || "Error al resolver el caso.");
    }
  }

  return (
    <div className="agent-console">
      <aside className="agent-sidebar">
        <div className="agent-sidebar__header">
          <div className="agent-sidebar__title">Bandeja</div>
          <div className="agent-sidebar__count">{cases.length} pendientes</div>
        </div>
        {err && <div className="agent-error">{err}</div>}
        {loading && <div className="agent-empty">Cargando…</div>}
        {!loading && cases.length === 0 && (
          <div className="agent-empty">Sin casos pendientes. La bandeja se actualiza sola.</div>
        )}
        <div className="agent-case-list">
          {cases.map((c) => (
            <button
              key={c.id}
              className={"agent-case-item" + (c.id === selectedId ? " agent-case-item--active" : "")}
              onClick={() => setSelectedId(c.id)}
            >
              <div className="agent-case-item__name">
                {c.context?.customer?.name || c.decision_id.slice(0, 8)}
              </div>
              <div className="agent-case-item__reason">{c.escalation_reason}</div>
              <div className="agent-case-item__meta">
                <span className={"confidence-dot confidence-dot--" + confidenceLevel(c.ai_confidence)} />
                {c.ai_recommendation || "sin recomendación AI"}
              </div>
            </button>
          ))}
        </div>
      </aside>

      <main className="agent-detail">
        {lastResolved && !selected && (
          <div className="agent-toast">
            Caso de {lastResolved.name || lastResolved.id.slice(0, 8)} resuelto:{" "}
            <strong>{lastResolved.result.outcome}</strong>
            {lastResolved.result.approved_amount ? ` — ${formatMoney(lastResolved.result.approved_amount)}` : ""}
          </div>
        )}
        {!selected && !lastResolved && (
          <div className="agent-empty agent-empty--detail">
            Selecciona un caso de la bandeja para revisarlo.
          </div>
        )}
        {selected && <CaseDetail caseItem={selected} onResolve={handleResolve} />}
      </main>
    </div>
  );
}

function confidenceLevel(confidence) {
  if (confidence === null || confidence === undefined) return "unknown";
  if (confidence >= 0.7) return "high";
  if (confidence >= 0.4) return "mid";
  return "low";
}

function CaseDetail({ caseItem, onResolve }) {
  const [resolvedBy, setResolvedBy] = useState("agente_maria");
  const [adjustedAmount, setAdjustedAmount] = useState("");
  const [showAdjust, setShowAdjust] = useState(false);

  const customer = caseItem.context?.customer;
  const offer = caseItem.context?.offer;
  const selectedAmount = caseItem.context?.selected_amount;

  return (
    <div className="case-detail">
      <div className="case-detail__header">
        <h2>{customer?.name || "Cliente"}</h2>
        <span className="case-detail__id">{caseItem.decision_id}</span>
      </div>

      <div className="case-detail__grid">
        <Field label="Score" value={customer?.credit_score} />
        <Field label="Antigüedad" value={customer ? `${customer.tenure_months} meses` : "—"} />
        <Field label="DTI actual" value={customer ? `${(customer.dti_ratio * 100).toFixed(0)}%` : "—"} />
        <Field label="Mora (12m)" value={customer ? `${customer.max_days_overdue_12m} días` : "—"} />
        <Field label="Estado de cuenta" value={customer?.account_status} />
        <Field label="Rango ofertado" value={offer ? `${formatMoney(offer.floor_amount)} – ${formatMoney(offer.cap_at_offer_time)}` : "—"} />
        <Field label="Monto seleccionado" value={formatMoney(selectedAmount)} />
        <Field label="Versión de criterio" value={offer?.rules_version} />
      </div>

      <div className="case-detail__escalation">
        <div className="case-detail__section-title">Motivo del escalamiento</div>
        <p>{caseItem.escalation_reason}</p>
      </div>

      <div className="case-detail__ai">
        <div className="case-detail__section-title">
          Recomendación AI
          <span className={"confidence-dot confidence-dot--" + confidenceLevel(caseItem.ai_confidence)} />
          {caseItem.ai_confidence !== null ? `${(caseItem.ai_confidence * 100).toFixed(0)}% confianza` : "sin confianza"}
        </div>
        <p className="case-detail__ai-reasoning">{caseItem.ai_summary || "Sin razonamiento disponible."}</p>
        <div className="case-detail__ai-badge">{caseItem.ai_recommendation || "—"}</div>
      </div>

      <div className="case-detail__actions">
        <input
          className="text-input text-input--inline"
          value={resolvedBy}
          onChange={(e) => setResolvedBy(e.target.value)}
          placeholder="Tu usuario de agente"
        />
        <div className="case-detail__buttons">
          <button className="btn btn--primary" onClick={() => onResolve("honor", resolvedBy)}>
            Honrar oferta original
          </button>
          <button className="btn btn--secondary" onClick={() => setShowAdjust((v) => !v)}>
            Ajustar monto
          </button>
          <button className="btn btn--danger" onClick={() => onResolve("revoke", resolvedBy)}>
            Revocar
          </button>
        </div>
        {showAdjust && (
          <div className="case-detail__adjust">
            <input
              type="number"
              className="text-input text-input--inline"
              placeholder={`Monto ajustado (máx ${formatMoney(selectedAmount)})`}
              value={adjustedAmount}
              onChange={(e) => setAdjustedAmount(e.target.value)}
            />
            <button
              className="btn btn--primary"
              onClick={() => onResolve("adjust", resolvedBy, Number(adjustedAmount))}
              disabled={!adjustedAmount}
            >
              Confirmar ajuste
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, value }) {
  return (
    <div className="field">
      <div className="field__label">{label}</div>
      <div className="field__value">{value ?? "—"}</div>
    </div>
  );
}
