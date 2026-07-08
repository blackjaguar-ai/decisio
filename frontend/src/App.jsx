import { useState } from "react";
import ClienteView from "./components/ClienteView.jsx";
import AgenteView from "./components/AgenteView.jsx";

export default function App() {
  const [view, setView] = useState("cliente");

  return (
    <div className={"app app--" + view}>
      <header className="app-header">
        <div className="app-header__brand">
          <span className="app-header__mark">iO</span>
          <span className="app-header__product">DECISIO</span>
        </div>
        <nav className="app-header__nav">
          <button
            className={"nav-tab" + (view === "cliente" ? " nav-tab--active" : "")}
            onClick={() => setView("cliente")}
          >
            Vista cliente
          </button>
          <button
            className={"nav-tab" + (view === "agente" ? " nav-tab--active" : "")}
            onClick={() => setView("agente")}
          >
            Vista agente
          </button>
        </nav>
      </header>

      <main className="app-main">
        {view === "cliente" ? <ClienteView /> : <AgenteView />}
      </main>
    </div>
  );
}
