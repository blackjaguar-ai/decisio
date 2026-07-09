import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";

// Inter — tipografía oficial iO, auto-hospedada (Semana 3, corrección sobre
// la versión anterior que llamaba a fonts.gstatic.com). @fontsource/inter
// empaqueta los .woff2 reales de Google Fonts como parte del build de Vite
// — se descargan UNA vez desde registry.npmjs.org (ya en la lista blanca
// del proyecto) al hacer `npm install`, y de ahí en adelante Vite los
// hashea como assets propios en dist/assets/. Cero llamada a un CDN externo
// en runtime — mismo criterio de "cero CDN" de Semana 1/2, ahora aplicado
// también a la fuente. Solo se importan los subsets latin + latin-ext
// (cubren español/portugués/inglés) — se omiten cyrillic/greek/vietnamese
// del CSS original de Google, que la app nunca necesita para el mercado
// peruano, para no descargar peso muerto.
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-ext-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-ext-500.css";
import "@fontsource/inter/latin-700.css";
import "@fontsource/inter/latin-ext-700.css";
import "@fontsource/inter/latin-800.css";
import "@fontsource/inter/latin-ext-800.css";
import "@fontsource/inter/latin-900.css";
import "@fontsource/inter/latin-ext-900.css";
import "./App.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
