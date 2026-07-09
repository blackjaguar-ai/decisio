import { useState } from "react";
import ClienteView from "./components/ClienteView.jsx";
import AgenteView from "./components/AgenteView.jsx";
import Dashboard from "./components/Dashboard.jsx";
import AboutView from "./components/AboutView.jsx";
import BrandLogo from "./components/BrandLogo.jsx";

const VIEWS = [
  { key: "about", label: "Cómo funciona" },
  { key: "cliente", label: "Vista cliente" },
  { key: "agente", label: "Vista agente" },
  { key: "dashboard", label: "Dashboard" },
];

export default function App() {
  const [view, setView] = useState("about");
  const [navOpen, setNavOpen] = useState(false);

  function selectView(key) {
    setView(key);
    setNavOpen(false);
  }

  return (
    <div className={"app app--" + view}>
      <header className="app-header">
        <div className="app-header__brand">
          <BrandLogo />
          <span className="app-header__product">DECISIO</span>
        </div>

        {/* Desktop: switcher de píldoras, siempre visible — se mantiene
            igual que antes. CSS lo oculta bajo el breakpoint mobile. */}
        <nav className="app-header__nav app-header__nav--desktop">
          {VIEWS.map((v) => (
            <button
              key={v.key}
              className={"nav-tab" + (view === v.key ? " nav-tab--active" : "")}
              onClick={() => selectView(v.key)}
            >
              {v.label}
            </button>
          ))}
        </nav>

        {/* Mobile: hamburguesa + desplegable, calcado del patrón real de
            iO (menú oscuro semitransparente que se abre desde la esquina
            superior derecha). CSS lo oculta arriba del breakpoint mobile. */}
        <div className="app-header__mobile-nav">
          <button
            className="hamburger-btn"
            onClick={() => setNavOpen((v) => !v)}
            aria-label="Abrir menú de vistas"
            aria-expanded={navOpen}
          >
            <span className="hamburger-icon">
              <span /><span /><span />
            </span>
          </button>

          {navOpen && (
            <>
              <button
                className="nav-dropdown__backdrop"
                aria-label="Cerrar menú"
                onClick={() => setNavOpen(false)}
              />
              <div className="nav-dropdown">
                {VIEWS.map((v) => (
                  <button
                    key={v.key}
                    className={"nav-dropdown__item" + (view === v.key ? " nav-dropdown__item--active" : "")}
                    onClick={() => selectView(v.key)}
                  >
                    {v.label}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </header>

      <main className="app-main">
        {view === "about" && <AboutView onOpenDemo={() => selectView("cliente")} />}
        {view === "cliente" && <ClienteView />}
        {view === "agente" && <AgenteView />}
        {view === "dashboard" && <Dashboard />}
      </main>
    </div>
  );
}
