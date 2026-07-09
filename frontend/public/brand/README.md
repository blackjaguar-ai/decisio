# Carpeta de assets de marca — iO

Esta carpeta (`frontend/public/brand/`) es la carpeta "linkeada" para subir
los assets reales de iO. Todo lo que se copie a `frontend/public/`, Vite lo
copia tal cual a la raíz de `dist/` al hacer build — el header de la app
(`App.jsx`) ya está cableado para leer los nombres de archivo exactos de
abajo, sin tocar código.

## Archivo esperado

| Nombre de archivo         | Uso                                          | Formato preferido |
|----------------------------|-----------------------------------------------|--------------------|
| `logo-io.svg`               | Isotipo/wordmark real de iO en el header      | SVG, fondo transparente |
| `logo-io.png`               | Fallback si no hay SVG disponible             | PNG, fondo transparente, ≥120px de alto |

El header intenta cargar `logo-io.svg` primero. Si no existe (404), cae a
`logo-io.png`. Si tampoco existe, cae a `logo-io-ring.png` (el ring de marca
real que ya viene incluido — extraído de tu propio `logo-footer.png`, sin
el wordmark). Si ninguno carga, el header muestra el badge de texto "iO"
como último recurso — la app nunca se rompe visualmente por falta de un
asset.

## Cómo subir el logo real

1. Reemplaza (o agrega) `logo-io.svg` en esta misma carpeta con el archivo
   real de iO (idealmente el isotipo completo: la "i" + el ring "o" en
   gradiente índigo→cian, tal como aparece en la app real).
2. **Ya no hace falta rebuild.** Desde Semana 3, `docker-compose.yml` monta
   esta carpeta como bind mount de solo lectura directo sobre el contenedor
   de Nginx (`./frontend/public/brand:/usr/share/nginx/html/brand:ro`).
   Subes el archivo al VPS con `scp`/`rsync` a esta misma ruta y con un
   refresh del navegador ya se ve — Nginx lee archivos estáticos de disco
   en cada request, no los cachea en la imagen.
   ```bash
   scp logo-io.svg usuario@vps:/opt/escai/decisio/frontend/public/brand/
   ```
3. Si en algún momento reconstruyes la imagen completa (`docker compose up
   -d --build`), el archivo que subiste por `scp` directo al VPS
   sobrevive — vive en el filesystem del host, no dentro de la imagen. Lo
   único que sí requiere rebuild es si cambias el código de `App.jsx` o
   `App.css` (el resto del sitio sigue siendo servido por la imagen
   construida en build-time).

## Por qué no usé las fotos de WhatsApp como logo

Las capturas de pantalla del teléfono (`WhatsApp Image...jpeg`) tienen el
logo incrustado dentro de una foto de la pantalla completa — recortarlo de
ahí arrastra compresión JPEG, halos de anti-aliasing y el fondo de la app
detrás. Sirve para ver la paleta y la tipografía, no para usarlo como
archivo de marca en producción. El único asset "limpio" que sí es
utilizable tal cual es `logo-footer.png` (el ring, sin wordmark) — es el
que quedó como fallback intermedio mientras subes el archivo oficial
completo.
