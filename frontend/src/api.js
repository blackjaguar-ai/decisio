/**
 * Cliente API — DECISIO backend (FastAPI).
 * Sin mocks: cada función golpea el motor real. En dev, Vite proxea
 * /decision, /cases, /trace, /metrics a http://localhost:8000 (ver
 * vite.config.js). En producción (Semana 3), Nginx hace ese mismo proxy.
 */

async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = body?.detail || `Error ${res.status}`;
    const err = new Error(detail);
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return body;
}

export function postDecision(payload) {
  return request("/decision", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getDecisionStatus(decisionId) {
  return request(`/decision/${decisionId}`);
}

export function listCases() {
  return request("/cases");
}

export function getCase(caseId) {
  return request(`/cases/${caseId}`);
}

export function resolveCase(caseId, resolution) {
  return request(`/cases/${caseId}/resolve`, {
    method: "POST",
    body: JSON.stringify(resolution),
  });
}

export function getMetrics() {
  return request("/metrics");
}
