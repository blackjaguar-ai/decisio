import { useEffect, useRef, useState } from "react";

/**
 * AboutView — vista explicativa del proyecto (Semana 3).
 *
 * A propósito NO usa la paleta de iO (clara, Inter, banca). Esta vista no
 * simula la app del banco — presenta el proyecto DECISIO en sí mismo, así
 * que toma un lenguaje visual propio (oscuro, gradiente violeta/magenta,
 * tarjetas escalonadas con animación al hacer scroll), con estilo similar
 * al pedido de referencia. Todo el contenido factual (nombres de nodos,
 * normas, cifras) viene directo de los documentos del proyecto — nada
 * inventado para que se vea bonito.
 */

const TAGLINES = [
  "Motor de decisión de crédito",
  "Revalidación de oferta firme",
  "Human-in-the-loop real",
];

const GRAPH_NODES = [
  {
    key: "ingest",
    title: "ingest",
    desc: "Normaliza el perfil y recupera el criterio congelado (rules_version / criteria_snapshot) que generó la oferta.",
  },
  {
    key: "rules_engine",
    title: "rules_engine",
    desc: "Revalida determinísticamente contra ese criterio congelado — nunca contra la política vigente hoy.",
  },
  {
    key: "ai",
    title: "ai_assessor + ai_explainer",
    desc: "La AI razona sobre hallazgos ambiguos y explica cada decisión en lenguaje humano. Nunca decide dinero sola.",
  },
  {
    key: "guardrails",
    title: "guardrails",
    desc: "Bounds de monto, staleness, coherencia regla-AI, confianza mínima. Override del regulador, no de la AI.",
  },
  {
    key: "decision",
    title: "auto_decision / human_in_loop",
    desc: "Camino limpio se ejecuta solo. Hallazgo ambiguo se pausa de verdad con interrupt() y espera a un agente.",
  },
  {
    key: "finalize",
    title: "finalize",
    desc: "Consolida la decisión y escribe la traza completa — el registro de 3 años que el regulador puede auditar.",
  },
];

const STATS = [
  { value: "72h → <30s", label: "Objetivo de latencia (Propuesta §1)" },
  { value: "3 + 1", label: "Rutas reales del grafo + gate de identidad" },
  { value: "interrupt()", label: "HITL real, no simulado — sobrevive un restart" },
  { value: "Sept 2026", label: "Deadline de cumplimiento DS 115-2025-PCM" },
];

const COMPLIANCE = [
  {
    title: "Resolución SBS 053-2023",
    desc: "Riesgo de modelo. El score entra como input dado — el inventario de modelos recae sobre iO, no sobre este motor de orquestación.",
  },
  {
    title: "DS 115-2025-PCM",
    desc: "Clasifica la evaluación crediticia automatizada como IA de alto riesgo. Exige supervisión humana explícita y explicabilidad antes de septiembre 2026.",
  },
];

function useReveal() {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          obs.disconnect();
        }
      },
      { threshold: 0.2 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  return [ref, visible];
}

function Reveal({ children, delay = 0, className = "" }) {
  const [ref, visible] = useReveal();
  return (
    <div
      ref={ref}
      className={"reveal" + (visible ? " reveal--visible" : "") + (className ? " " + className : "")}
      style={{ transitionDelay: visible ? `${delay}ms` : "0ms" }}
    >
      {children}
    </div>
  );
}

function useTypewriter(words, typeMs = 45, holdMs = 1600, deleteMs = 25) {
  const [text, setText] = useState("");
  const [wordIdx, setWordIdx] = useState(0);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const current = words[wordIdx % words.length];
    let timer;

    if (!deleting && text.length < current.length) {
      timer = setTimeout(() => setText(current.slice(0, text.length + 1)), typeMs);
    } else if (!deleting && text.length === current.length) {
      timer = setTimeout(() => setDeleting(true), holdMs);
    } else if (deleting && text.length > 0) {
      timer = setTimeout(() => setText(current.slice(0, text.length - 1)), deleteMs);
    } else if (deleting && text.length === 0) {
      setDeleting(false);
      setWordIdx((i) => i + 1);
    }
    return () => clearTimeout(timer);
  }, [text, deleting, wordIdx, words, typeMs, holdMs, deleteMs]);

  return text;
}

export default function AboutView({ onOpenDemo }) {
  const typed = useTypewriter(TAGLINES);

  return (
    <div className="about-view">
      <div className="about-glow about-glow--1" />
      <div className="about-glow about-glow--2" />

      <section className="about-hero">
        <div className="about-eyebrow">Escai Tech · Banco iO</div>
        <h1 className="about-title">
          De <span className="about-title__accent--copper">72 horas</span> a{" "}
          <span className="about-title__accent--cyan">30 segundos</span>
        </h1>
        <div className="about-typewriter">
          <span>{typed}</span>
          <span className="about-cursor" />
        </div>
        <p className="about-hero__copy">
          DECISIO es el motor que revalida y ejecuta ampliaciones de línea de crédito ya
          preaprobadas — sin tocar el core, con supervisión humana real donde el compromiso
          con el cliente lo exige.
        </p>
        <div className="about-hero__actions">
          <button className="about-btn about-btn--primary" onClick={onOpenDemo}>
            Ver demo en vivo →
          </button>
          <a className="about-btn about-btn--ghost" href="#about-graph">
            Ver arquitectura ↓
          </a>
        </div>
      </section>

      <section className="about-stats">
        {STATS.map((s, i) => (
          <Reveal key={s.label} delay={i * 90} className="about-stat">
            <div className="about-stat__value">{s.value}</div>
            <div className="about-stat__label">{s.label}</div>
          </Reveal>
        ))}
      </section>

      <section className="about-section" id="about-graph">
        <Reveal>
          <div className="about-section__eyebrow">El grafo de decisión</div>
          <h2 className="about-section__title">Seis nodos, LangGraph real</h2>
          <p className="about-section__copy">
            No evalúa solicitudes nuevas — revalida si una oferta firme, ya preaprobada por
            el modelo interno de iO, sigue siendo honrable en el momento exacto de la aceptación.
          </p>
        </Reveal>

        <div className="about-staircase">
          {GRAPH_NODES.map((node, i) => (
            <Reveal key={node.key} delay={i * 110} className="about-node-wrap">
              <div className="about-node" style={{ "--step": i }}>
                <div className="about-node__index">{String(i + 1).padStart(2, "0")}</div>
                <div className="about-node__title">{node.title}</div>
                <div className="about-node__desc">{node.desc}</div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="about-section">
        <Reveal>
          <div className="about-section__eyebrow">Cumplimiento por diseño</div>
          <h2 className="about-section__title">No es un dashboard bonito, es el audit trail</h2>
        </Reveal>
        <div className="about-compliance">
          {COMPLIANCE.map((c, i) => (
            <Reveal key={c.title} delay={i * 120} className="about-compliance__card">
              <div className="about-compliance__title">{c.title}</div>
              <p className="about-compliance__desc">{c.desc}</p>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="about-cta">
        <Reveal>
          <h2 className="about-cta__title">Esto corre sobre datos sintéticos hoy.</h2>
          <p className="about-cta__copy">
            La Fase 0 de Discovery cuantifica con datos reales de iO cuánto crédito se fuga
            en esas 72 horas.
          </p>
          <button className="about-btn about-btn--primary" onClick={onOpenDemo}>
            Recorrer la demo →
          </button>
        </Reveal>
      </section>
    </div>
  );
}
