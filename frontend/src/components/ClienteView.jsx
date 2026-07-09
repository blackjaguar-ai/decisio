import { useEffect, useRef, useState } from "react";
import { DEMO_PROFILES } from "../demoProfiles.js";
import { postDecision, getDecisionStatus } from "../api.js";

const POLL_INTERVAL_MS = 2500;

function formatMoney(n) {
  if (n === null || n === undefined) return "—";
  return "S/ " + Number(n).toLocaleString("es-PE", { maximumFractionDigits: 0 });
}

function useElapsedSeconds(running) {
  const [elapsedMs, setElapsedMs] = useState(0);
  const startRef = useRef(null);
  const frameRef = useRef(null);

  useEffect(() => {
    if (!running) return;
    startRef.current = performance.now();
    setElapsedMs(0);
    const tick = () => {
      setElapsedMs(performance.now() - startRef.current);
      frameRef.current = requestAnimationFrame(tick);
    };
    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, [running]);

  return elapsedMs;
}

export default function ClienteView() {
  const [step, setStep] = useState("intro"); // intro -> notification -> offer -> identity -> processing -> result
  const [profile, setProfile] = useState(null);
  const [amount, setAmount] = useState(0);
  const [password, setPassword] = useState("");
  const [identityError, setIdentityError] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [pollCount, setPollCount] = useState(0);

  const isTicking = step === "processing" || (step === "result" && result?.outcome === "pending_human");
  const elapsedMs = useElapsedSeconds(isTicking);
  const pollTimer = useRef(null);

  function pickProfile(p) {
    setProfile(p);
    setAmount(p.selected_amount);
    setStep("offer");
  }

  function confirmOffer() {
    setPassword("");
    setIdentityError("");
    setStep("identity");
  }

  function submitIdentity(e) {
    e.preventDefault();
    if (!password.trim()) {
      setIdentityError("Ingresa tu contraseña para confirmar.");
      return;
    }
    const shouldSucceed = profile.identityCheckBehavior !== "always_fail";
    runDecision(shouldSucceed);
  }

  async function runDecision(identityVerified) {
    setStep("processing");
    setError("");
    try {
      const payload = {
        customer: profile.customer,
        offer: profile.offer,
        selected_amount: amount,
        identity_verified: identityVerified,
        idempotency_key: `demo-${profile.key}-${Date.now()}`,
      };
      const res = await postDecision(payload);
      setResult(res);
      setStep("result");
      if (res.outcome === "pending_human") {
        startPolling(res.decision_id);
      }
    } catch (err) {
      setError(err.message || "Error de red al procesar la decisión.");
      setStep("result");
    }
  }

  function startPolling(decisionId) {
    pollTimer.current = setInterval(async () => {
      try {
        const status = await getDecisionStatus(decisionId);
        setPollCount((c) => c + 1);
        if (status.outcome !== "pending_human") {
          clearInterval(pollTimer.current);
          setResult((prev) => ({ ...prev, ...status }));
        }
      } catch {
        // red intermitente durante el polling — se reintenta en el próximo tick,
        // no se rompe la espera del cliente por un solo fallo transitorio.
      }
    }, POLL_INTERVAL_MS);
  }

  useEffect(() => () => clearInterval(pollTimer.current), []);

  function reset() {
    clearInterval(pollTimer.current);
    setStep("notification");
    setProfile(null);
    setResult(null);
    setError("");
    setPollCount(0);
  }

  return (
    <div className="phone-frame">
      <div className="phone-notch" />
      <div className="phone-screen">
        {step === "intro" && (
          <RedirectIntro onContinue={() => setStep("notification")} />
        )}

        {step === "notification" && (
          <NotificationStep onPick={pickProfile} />
        )}

        {step === "offer" && profile && (
          <OfferStep
            profile={profile}
            amount={amount}
            onChangeAmount={setAmount}
            onConfirm={confirmOffer}
            onBack={reset}
          />
        )}

        {step === "identity" && profile && (
          <IdentityStep
            password={password}
            setPassword={setPassword}
            error={identityError}
            onSubmit={submitIdentity}
            onBack={() => setStep("offer")}
          />
        )}

        {step === "processing" && (
          <ProcessingStep elapsedMs={elapsedMs} />
        )}

        {step === "result" && (
          <ResultStep
            result={result}
            error={error}
            elapsedMs={elapsedMs}
            pollCount={pollCount}
            onReset={reset}
          />
        )}
      </div>
    </div>
  );
}

function RedirectIntro({ onContinue }) {
  // Popup de apertura — simula el deep-link real: tocar la notificación
  // push lleva DIRECTO a la oferta, nunca a soporte (el hallazgo #1 de la
  // Propuesta, §2.1). Tono oscuro deliberado (mismo --gradient-hero que el
  // ring de "Cashback Obtenido" del landing real de iO) — reservamos el
  // tono claro/pastel para el resto del flujo del cliente, así este primer
  // instante se siente como una notificación real llegando, no como una
  // pantalla más de la app.
  return (
    <div className="step step--intro">
      <div className="redirect-card">
        <div className="redirect-card__badge">🔔</div>
        <div className="redirect-card__eyebrow">Notificación push</div>
        <h3 className="redirect-card__title">Tienes una ampliación de línea preaprobada</h3>
        <p className="redirect-card__copy">
          Un toque te lleva directo a tu oferta — nunca a soporte, nunca a una cola de 72 horas.
        </p>
        <button className="redirect-card__cta" onClick={onContinue}>
          Ver oferta →
        </button>
      </div>
    </div>
  );
}

function NotificationStep({ onPick }) {
  const [tapped, setTapped] = useState(null);

  return (
    <div className="step step--notification">
      <div className="lockscreen-time">9:41</div>
      <p className="lockscreen-hint">
        Elige qué cliente sintético "recibió" la notificación — la demo arranca
        siempre en el deep-link a la oferta, nunca en soporte.
      </p>
      <div className="profile-list">
        {DEMO_PROFILES.map((p) => (
          <button
            key={p.key}
            className={"push-card" + (tapped === p.key ? " push-card--tapped" : "")}
            onClick={() => {
              setTapped(p.key);
              setTimeout(() => onPick(p), 180);
            }}
          >
            <div className="push-card__icon">iO</div>
            <div className="push-card__body">
              <div className="push-card__title">Ampliación preaprobada</div>
              <div className="push-card__subtitle">
                {p.label} · hasta {formatMoney(p.offer.cap_at_offer_time)}
              </div>
              <div className="push-card__tag">{p.tag}</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function OfferStep({ profile, amount, onChangeAmount, onConfirm, onBack }) {
  const { floor_amount, cap_at_offer_time } = profile.offer;
  return (
    <div className="step step--offer">
      <button className="link-back" onClick={onBack}>← Cambiar cliente</button>
      <div className="eyebrow">Ampliación de línea preaprobada</div>
      <div className="offer-amount">{formatMoney(amount)}</div>
      <input
        type="range"
        min={floor_amount}
        max={cap_at_offer_time}
        step="100"
        value={amount}
        onChange={(e) => onChangeAmount(Number(e.target.value))}
        className="slider"
      />
      <div className="slider-bounds">
        <span>{formatMoney(floor_amount)}</span>
        <span>{formatMoney(cap_at_offer_time)}</span>
      </div>
      <p className="offer-note">{profile.tagline}</p>
      <button className="btn btn--primary" onClick={onConfirm}>
        Ampliar a {formatMoney(amount)} — Acepto
      </button>
    </div>
  );
}

function IdentityStep({ password, setPassword, error, onSubmit, onBack }) {
  return (
    <form className="step step--identity" onSubmit={onSubmit}>
      <button type="button" className="link-back" onClick={onBack}>← Volver</button>
      <div className="eyebrow">Verificación de identidad</div>
      <p className="identity-copy">
        Confirma tu contraseña para autorizar este cambio en tu línea de crédito.
      </p>
      <input
        type="password"
        autoFocus
        placeholder="Contraseña"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="text-input"
      />
      {error && <div className="field-error">{error}</div>}
      <button className="btn btn--primary" type="submit">Confirmar identidad</button>
      <p className="identity-disclaimer">
        Demo: reingreso de contraseña como proxy. Producción integra biometría
        nativa (Face ID / huella) del proveedor de iO/BCP.
      </p>
    </form>
  );
}

function ProcessingStep({ elapsedMs }) {
  return (
    <div className="step step--processing">
      <div className="spinner" />
      <div className="cronometro">{(elapsedMs / 1000).toFixed(1)}s</div>
      <p className="processing-copy">Revalidando tu oferta…</p>
    </div>
  );
}

function ResultStep({ result, error, elapsedMs, pollCount, onReset }) {
  if (error) {
    return (
      <div className="step step--result result--error">
        <div className="result-icon">⚠</div>
        <div className="result-title">No pudimos procesar tu solicitud</div>
        <p className="result-copy">{error}</p>
        <button className="btn btn--ghost" onClick={onReset}>Intentar con otro cliente</button>
      </div>
    );
  }

  if (!result) return null;

  if (result.outcome === "identity_verification_failed") {
    return (
      <div className="step step--result result--blocked">
        <div className="result-icon">🔒</div>
        <div className="result-title">Verificación fallida</div>
        <p className="result-copy">
          No se ejecutó ninguna operación sobre tu línea de crédito. El sistema
          nunca llegó a evaluar la ampliación.
        </p>
        <button className="btn btn--ghost" onClick={onReset}>Volver a intentar</button>
      </div>
    );
  }

  if (result.outcome === "pending_human") {
    return (
      <div className="step step--result result--pending">
        <div className="pending-pulse" />
        <div className="cronometro cronometro--pending">{(elapsedMs / 1000).toFixed(0)}s</div>
        <div className="result-title">En revisión con un especialista</div>
        <p className="result-copy">{result.explanation?.explanation_for_customer ||
          "Detectamos un cambio desde que te ofrecimos esta ampliación. Un agente lo está revisando ahora mismo."}</p>
        <p className="pending-meta">Consultando resolución… ({pollCount})</p>
      </div>
    );
  }

  const honored = result.outcome === "honored";
  return (
    <div className={"step step--result " + (honored ? "result--honored" : "result--revoked")}>
      <div className="result-icon">{honored ? "✓" : "•"}</div>
      <div className="cronometro">{(elapsedMs / 1000).toFixed(1)}s</div>
      <div className="comparativo">Interbank: ~30s con botón único · iO (antes): hasta 72h</div>
      <div className="result-title">
        {honored ? `Ampliación aprobada: ${formatMoney(result.approved_amount)}` : "Ampliación no confirmada"}
      </div>
      <p className="result-copy">{result.explanation?.explanation_for_customer}</p>
      {result.notice_type === "adverse_action" && (
        <div className="badge badge--adverse">Notificación de reversión de oferta</div>
      )}
      {result.decided_by?.startsWith("human:") && (
        <div className="badge badge--human">Resuelto por un especialista</div>
      )}
      <button className="btn btn--ghost" onClick={onReset}>Simular otro cliente</button>
    </div>
  );
}
