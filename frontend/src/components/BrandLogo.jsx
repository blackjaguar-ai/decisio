import { useState } from "react";

// Cadena de fallback: SVG real (que Cristian sube a public/brand/) → PNG
// real → ring de marca real (ya incluido, extraído de logo-footer.png) →
// badge de texto como último recurso. Nunca se rompe visualmente por
// ausencia de un asset — ver public/brand/README.md para instrucciones de
// carga.
const FALLBACK_CHAIN = ["/brand/logo-io.svg", "/brand/logo-io.png", "/brand/logo-io-ring.png"];

export default function BrandLogo() {
  const [attempt, setAttempt] = useState(0);

  if (attempt >= FALLBACK_CHAIN.length) {
    return <span className="app-header__mark">iO</span>;
  }

  return (
    <img
      key={FALLBACK_CHAIN[attempt]}
      src={FALLBACK_CHAIN[attempt]}
      alt="iO"
      className="app-header__logo"
      onError={() => setAttempt((a) => a + 1)}
    />
  );
}
