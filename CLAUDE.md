# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Code, comments, and docs are in Spanish. Prefer this file and `MANUAL_SISTEMA.md`
as the source of truth. `README.md` describes an OLDER architecture (60 workers,
active `nombreWHAPP.py`, proxy rotation) — prefer the manual where they disagree.

**Last major update:** 2026-07-10 (fair-price engine overhaul, generations tab,
comparables modal improvements — see "Recent work" at the bottom).

## What this is

Market-intelligence system for used cars on **chileautos.cl**. Business goal:
**find buying opportunities from private sellers** (cars listed below fair price).
It scrapes the catalog, tracks listings incrementally, enriches them with seller
comments and technical specs, classifies those comments (keywords + Groq LLM),
computes "fair price" / opportunity / rotation metrics, and publishes a static
`dashboard.html` locally (and optionally to GitHub Pages:
https://notclassic.github.io/-chileautos-sistema/dashboard.html — currently the
user does NOT use the web version; push fails with "rejected, fetch first").

**Scale:** ~44,000 active ads. Incremental state in `estado_avisos.csv` (~44,011 clean).

**Location on the PC:** `C:\Users\Maria Nery\OneDrive\Documentos\GitHub\-chileautos-sistema\`

## Two independent processes — do not conflate them

1. **Car download (scraper)** — fast, safe to run a couple times/day.
2. **Comment drip (`enriquecer_comentarios.py`)** — deliberately SLOW,
   one ad at a time with random 4–11s pauses, meant to run overnight so
   Datadome (chileautos' bot defense) doesn't block it. This is the delicate
   part; the "night only" rule applies ONLY here, not to the car download.

## Two code lineages

- **Legacy full-dump path**: `actualizar.py` → `main.py` → `scrapper.py` +
  `telefono.py` → Excel in `capturas/`. `actualizar.py` copies
  `scrapper_auto.py` onto `scrapper.py` at runtime, runs, then deletes it — so
  `from scrapper import ...` resolves to the auto version.
- **Current incremental path**: `actualizar_incremental.py` diffs the light
  catalog against `estado_avisos.csv` and only re-fetches genuinely new ads.
  It marks an ad "probably sold" only after `DIAS_PARA_VENDIDO=7` days absent
  (the scrape drops ~thousands of ads per run at random, so a single day's
  absence is NOT a sale). `motor.py` prefers this incremental state when present.

## Pipeline / data flow

```
scrapper_auto.py (catalog API)
  -> actualizar_incremental.py  -> estado_avisos.csv (+ capturas/*.xlsx)
  -> enriquecer_comentarios.py  -> comentarios.json
  -> bajar_especificaciones.py  -> especificaciones.csv + especificaciones_full.json
  -> clasificar_ia.py (Groq)    -> comentarios_ia.json
  -> clasificar_comentarios.py  -> comentarios_clasificados.json  (keywords + IA merge)
  -> motor.py                   -> datos.json (+ base_FECHA.xlsx)
  -> ver_comentarios.py / actualizar.py -> dashboard.html -> git push
```

`motor.py` (the ~84KB brain — grew from ~57KB with the 2026-07 overhaul) reads
`capturas/*.xlsx` + `estado_avisos.csv` + `especificaciones.csv` +
`generaciones.xlsx`, cleans data, computes fair price from comparables
(`DESCUENTO_MIN=15%`, `MIN_COMPARABLES=5`), computes rotation across consecutive
captures, cross-references `comentarios_clasificados.json` and manual overrides
(`correcciones_versiones.json`, `correcciones_avisos.json`), and emits `datos.json`.
The dashboard consumes only `datos.json`; the motor never touches the dashboard.

`actualizar.py` / `ver_comentarios.py` embed `datos.json` into the
`/*__DATA__*/` placeholder of `plantilla_dashboard.html` to produce
`dashboard.html`, then git commit + push. Never hand-edit `dashboard.html`
(regenerated every run) or the template except for design.

## CRITICAL: dashboard regeneration (recurring source of confusion)

**Replacing `plantilla_dashboard.html` or `motor.py` does NOT update the
dashboard.** The dashboard is built in two steps: template (`/*__DATA__*/`
placeholder) + `datos.json` → `ver_comentarios.py` writes `dashboard.html`.

To apply code changes:
1. Replace the new files in the folder (overwrite the old ones)
2. If `panel.py` changed: restart PANEL.bat
3. `python ver_comentarios.py` (or the "Clasificar + dashboard" button)
4. Ctrl+F5 in Chrome

**Verify it regenerated:** `dir dashboard.html` — the timestamp must be recent.
If `dashboard.html` is OLDER than `plantilla_dashboard.html`, it did NOT
regenerate and you're seeing the old version. This is the #1 cause of "I don't
see my changes."

## Running it

Setup: `pip install -r requirements.txt` (also needs `requests` and `numpy`,
which are not pinned there — `requests` is used by `clasificar_ia.py`, `numpy`
by `motor.py`).

Common commands (all run from the repo root):

- `python actualizar.py`              — full legacy path: scrape + motor + dashboard + push
- `python actualizar.py --solo-motor` — skip scraping; just recompute + publish
- `python actualizar_incremental.py`  — daily incremental catalog diff → state + capture (THIS is the base download)
- `python enriquecer_comentarios.py --continuo`  — nightly comment drip (slow, delicate)
- `python bajar_especificaciones.py --solo-nuevos --limite 0`  — specs drip
- `python bajar_especificaciones.py --limite 300`  — one manual specs batch (~40-60 min with pauses)
- `python clasificar_ia.py`           — Groq LLM comment classification (needs key)
- `python ver_comentarios.py`         — classify comments + motor + dashboard + push (no scrape)
- `python panel.py`                   — local control server at http://localhost:8777

`.bat` launchers (double-click; each does `cd /d "%~dp0"` first):
`DESCARGAR_BASE.bat` = `actualizar.py`; `ACTUALIZAR_DASHBOARD.bat` =
`ver_comentarios.py`; `ACTUALIZAR_AUTO.bat` = unattended incremental chain
logged to `log_actualizacion.txt`; `PANEL.bat`/`DASHBOARD.bat` = launch panel;
`PROBAR.bat` = test run that keeps the window open. `panel.py`'s `"todo"`
action is the canonical daily chain (incremental → enriquecer → specs →
relleno → clasificar_ia → ver_comentarios).

There is no test suite, linter, or build step. Verify changes by running the
relevant script and inspecting its output file (`datos.json`, the CSVs, or the
regenerated `dashboard.html`).

## Dashboard buttons (user operates everything from here — no hand-edited files)

- **"Bajar base"** — downloads new ads from Chileautos (uses IP, slow). Ends by
  classifying and building the dashboard automatically. The everyday button.
- **"Clasificar + dashboard"** — downloads NOTHING. Recomputes and regenerates
  the dashboard from what's already on disk. The button to apply code changes
  without downloading.
- **"Solo base"** — downloads without classifying (to resume a crashed run).
- **Toggle "Relleno histórico"** — activates automatic download of ~150 old
  specs/day on the first daily run. State in `relleno_activo.txt` (internal,
  user never touches it). Verified end-to-end.
- **"Incluir teléfonos"** — captures phones when downloading (slower).
- **"Detener corrida"** / **"Descartar aviso"** — kill a hung run.

Classification is NOT done by Claude. Scripts on the PC do it (Groq + keywords).
Claude improves the code; the user presses the button to run it.

## Fair price — how it works (heavily reworked 2026-07)

### Comparability filters (what makes two cars comparable)
A car is compared only with others of the same **model, generation, engine,
fuel, transmission, drivetrain, cab, and special line** (GT/Raptor/AMG/etc.):

- **Generation:** a 3008 gen I (2013) is not compared with gen II (2018). Cuts in
  `generaciones.xlsx`. Only ~85 models have generations defined; others show "—".
- **Transition years:** a generation can launch mid-year (3008 gen II presented
  May 2016), so that year two generations coexist. The system marks those years
  with a 📸 chip and does NOT force the generation filter (shows both, user
  destildas by photos). Confirmed vs Wikipedia: 3008 gen I 2010-2016, II
  2017-2023, III (E-3008, electric) 2024+.
- **Engine/trim:** an "allure" (1.6) is not compared with a "gt" (2.0). When the
  ad doesn't declare the engine in text, it filters by trim. If the trim has a
  known dominant engine, it uses that.
- **Beast versions** (Raptor, AMG, Rubicon, STI, GTI): hard separation both ways.

### Year + km adjustment (rates derived from the real base)
Each comparable is NORMALIZED to the target's year and km before taking the
median. Rates derived from 234 models of the Chilean base:
- **Depreciation per year: 6.5%** (not the theoretical 10% — Chile depreciates slower)
- **Depreciation per km: 0.17% per 1000 km**
- **PREF_KM = 1.6** — user-preference knob: weights km 60% more than the market
  would, because the user prefers old-with-low-km over new-with-high-km.

The radar fair price, the modal recalculated price, and the "Precio ajust."
column ALL use the same algorithm — full coherence.

### Suspicious filters (MARKED, not hidden)
Philosophy: the system marks the doubtful and removes it from the automatic
calculation, but NEVER hides info or decides for the user.
- **Discount >55%** — MARKED with 🔍 "revisar" chip (could be a real deal or an error).
- **Impossible km** (2+ yrs with <1000km, or 5+ yrs with <5000km) — MARKED with
  red "km dudoso" chip. In the modal it starts UNCHECKED (doesn't dirty the calc).
- **Rare cars** (damaged/legal-problem/modified, by comment tag) — EXCLUDED from
  the comparables pool (don't drag the fair price), but still priced and shown marked.
- **Poor valuation** — if the strict filter leaves <5 real comparables, the fair
  price is marked ⚠ "poco confiable".
- **High dispersion** — if the comparables group is too scattered (IQR/median
  >0.45), the valuation isn't reliable and doesn't generate a gold opportunity.

### Radar ↔ modal coherence
The radar's comparable count now matches the modal's (both use the strict filter).

## Dashboard — tabs

- **Radar de oportunidades** — main table. Cars below fair price. Filters: only
  private sellers, by comment, by make/model. Status chips.
- **Rotación de mercado** — sell velocity per model. REQUIRES consecutive-day
  captures of the same origin; if they don't overlap, shows an honest "not yet
  available" message instead of a false 100%. (Overlap <40% OR exit rate >85%
  invalidates it. IDs normalized to lowercase for matching.)
- **Análisis de mercado**
- **Tasador**
- **Arreglar versiones** — proposes real versions per model (grouping the chaos
  of how sellers write them), separated by generation. Rename/merge/exclude.
- **Generaciones** (new, 2026-07) — edit generation year-cuts per model from the
  dashboard (no Excel), and fix the generation of individual ads. Respects
  transition years. Writes `generaciones.xlsx` via `/guardar_generaciones` panel
  route (with backup). Also uses `/depurar_aviso` for per-ad gen fixes.
- **Depuración BBDD (avanzado)**

### Comparables modal (click on "X comp.")
- Columns: Incluir, Año, Km, Km/año, Precio, Precio ajust., Versión (vendedor),
  Sugerida (ficha), Gen, Vendedor. Width 1150px.
- **Sortable** by each column (click header). **Quick filters** by year and
  generation (chips on top). **Counter** of how many comparables are included.
- Per-ad ✏ button: opens a version selector with model suggestions + free field.
- "✏ Arreglar versiones de este modelo" → jumps to that tab with the model loaded.
- Km-dudoso comparables start unchecked.

## Specs (technical sheets)

- **State:** ~356 sheets downloaded (of 44k ads). The last 192 downloaded with
  0 errors / 0 Datadome blocks (300 visited).
- **Purpose:** rescue data (engine, drivetrain, transmission, official trim) for
  ads that don't declare it in text (~32% of the base has no cylinder capacity in text).
- **Real limit:** when the text lacks the engine, the sheet sometimes lacks the
  number too, but DOES have the official trim ("ALLURE 4X2 AT"), which helps.
  Only works for ads that already have a downloaded sheet.
- **The downloader ACCUMULATES, doesn't overwrite:** `ids_ya_bajados()` skips
  what's already done. Manual batch and drip don't compete (same list), but do
  NOT run both the same day (duplicates requests → block).

## Anti-bot rules (the fragile parts)

- **Cookies expire.** If the scraper returns no cars with no clear error, the
  hard-coded cookie jar / `datadome` token in `scrapper_auto.py` is the first
  suspect (`log_actualizacion.txt` will show "No se pudieron obtener cookies").
- **403/429 = blocked.** Lower concurrency: `NUM_WORKERS_TEL` in `main.py`
  (currently 12; was 60 and got blocked). curl_cffi impersonation
  (`impersonate="chrome99_android"`) is what gets past Datadome — keep it.
- The comment/spec drips surrender after ~3 consecutive blocks and resume
  where they left off next run. Do not "speed them up" to fix slowness.
- Specs budget: ~500-600 sheets/day spread out. Don't run a manual specs batch
  the same day the relleno toggle runs (duplicates requests).
- Particulares usually list only WhatsApp (no phone), and some ads have neither
  — that is expected, not a bug. `telefono.py` decodes space-encoded
  particular WhatsApp numbers (`9%208209%200285` → `+56982090285`).

## Secrets

`clasificar_ia.py` reads the Groq API key from env `GROQ_API_KEY` or
`groq_key.txt`. (Note: `groq_key.txt` is currently committed to this public
repo and should be rotated + gitignored.)

## PENDING work

1. **Depuración BBDD redesign — flat table per model (USER SPEC EXISTS:
   depurador_versiones.xlsx, 2026-07-10)**. One row per ad with columns:
   Generación | Año | Marca | Modelo | Versión (vendedor) | **Versión Ajustada**
   (canonical, editable — strays get assigned here, e.g. "sin determinar 1" →
   "Version entry") | ~70 technical-sheet columns (airbags, dimensions, consumos,
   frenos, suspensión, torque, tracción...) filled ONLY for ads with a downloaded
   spec | Comentarios del vendedor. Render PER MODEL on demand (embedding 70
   spec columns × 44k ads would blow up the 25MB dashboard). Saving uses the
   existing /depurar_aviso route. This subsumes the earlier "grouped by
   generation" design. **Large build — own session on the stable base.**
2. **Add missing models to generaciones.xlsx** — only 85 models have generations
   (e.g. Peugeot 2008 doesn't, hence Gen "—"). Add from the Generaciones tab.
2b. **Extract the "Detalles" tab of each ad page (USER REQUEST 2026-07-10)**.
   The ad page has two tabs: "Especificaciones" (already scraped by
   bajar_especificaciones.py) and "Detalles" (NOT scraped). Fields to add:
   **Color exterior, Color interior, Carrocería (body + doors + seats),
   Región, Comuna** (Litros/Combustible/Kilometraje/Precio already captured
   elsewhere). These feed the Depuración BBDD flat table (pending #1) and
   enable region/comuna filtering. **Blocked on: user must provide
   bajar_especificaciones.py** (never shared in-session; scraper can't be
   modified blind).

3. **Pure "—" ads** (no engine/trim in text, no spec) — irreducible
   automatically. Only the human eye resolves them. The grouped view will make
   it fast.
4. **Web version (GitHub Pages)** — for phone. Push fails ("rejected, fetch
   first"); needs `git pull` then `git push`. User doesn't use it yet.
5. **Real rotation** — needs accumulated daily captures of the same origin.
   Activates itself in ~1 week of daily use.
6. **Rotate `groq_key.txt`** and gitignore it (committed to public repo).

## User working preferences

- Spanish, casual, strict honesty. Gets frustrated when told "fixed" prematurely.
  Prefers direct diagnosis over long explanation.
- Complete paste-ready files, never fragments.
- Operates 100% from the dashboard — no hand-edited .txt files.
- Suspicious items MARKED, not hidden. The system flags the doubtful and removes
  it from the automatic calc, but never decides for the user or hides info.
- Priority: private sellers + new listings.
- Non-technical — needs clear steps and jargon-free explanations.

### Catálogo maestro de versiones (spec del usuario 2026-07-10, PRÓXIMO GRAN PASO)
Tabla curada: **generación | marca | modelo | versión (forma canónica homologada) |
% de peso de cada versión en el mercado**. Regla de negocio: la mayoría de los
modelos tienen 3-4 versiones reales; camionetas (por cabinas: simple / media /
doble) y modelos con líneas GT/deportivas llegan a ~10. El usuario traerá un
análisis propio para diseñar la clasificación. La homologación de escritura ya
existe (orden canónico motor+acabado+tracción+combustible+caja); falta el
catálogo con pesos, construible desde depuracion_avisos agrupado + curación.

### Pendientes registrados 2026-07-11 (madrugada)
1. **Región/comuna por aviso + alerta de "oro viajero"**: la región vive en la
   ficha de cada aviso (hoy solo ~356 la tienen). Requiere extender el bajador
   de fichas — pedir a Eduardo `bajar_especificaciones.py` para agregar región,
   comuna y fecha real de publicación a cada ficha nueva. Con el dato: filtro
   por región en el radar + señal "oro en otra región: ¿vale el viaje?"
   (descuento absoluto en $ vs distancia).
2. **Análisis de mercado como dashboard tipo BI**: autoadministrable, con
   filtros combinables (marca/modelo/gen/región/año/precio) y widgets
   configurables. Rediseño grande de la pestaña — sesión propia.
3. Resumen de depuración: falta la vista "versiones correctas por generación"
   (pocas canónicas + cola sin determinar, medible) — preguntas de diseño
   enviadas, sin responder aún (quién define las correctas, qué pasa con las
   minoritarias).

### Dashboard BI interactivo — DISEÑO ACORDADO (2026-07-11, respuestas del usuario)
Pestaña nueva "Análisis BI". Un solo tablero que responde compra + rotación +
precios. **Barra de filtros global** (marca/modelo/gen/años/precio/vendedor;
región cuando exista el dato) que recalcula todos los widgets al instante.
**KPIs del segmento** (avisos, precio mediano, descuento medio, % oro, días en
mercado). **Grilla de widgets** con mostrar/ocultar: distribución por año,
dispersión precio/km, ranking de versiones con % peso, top oportunidades,
rotación. **Tabla dinámica** (fila: marca/modelo/gen/año/versión/vendedor;
métrica: conteo/mediana precio/descuento/km) — el resumen tipo Hilux del
usuario se arma ahí. **Vistas guardadas** con nombre en localStorage (funciona:
es archivo local, no artifact).
MEJORAS ADOPTADAS del doc del usuario (2026-07-11): KPI + histograma de
"antigüedad del inventario" (días en mercado por segmento — vendedores viejos
= negociables); box plot de precios por modelo/gen (dispersión, no solo
mediana); widget de composición por combustible/caja/tracción (datos efectivos
ya calculados); KPI "valor total del segmento" ($); métrica "$ que rotó"
(suma de precios de avisos salidos del mercado, por segmento). DESCARTADO con
fundamento: rentabilidad/márgenes (datos internos de dealer, no de mercado),
tasa de conversión (dato inexistente). Estacionalidad: cuando haya meses de
historia.
FASES: F1 filtros+KPIs+3 widgets · F2 tabla dinámica · F3 widgets on/off +
vistas · F4 series de evolución por captura (motor exporta) + región.
Datos: ampliar depuracion_avisos con 'entidad' (vendedor) y 'primera_vez',
o dataset 'bi' propio.

### Especificado 2026-07-12 (requiere historia acumulada de pares completos)
La primera bajada completa corrió hoy (scrapper 3500). Con pares diarios
completos acumulándose, construir en el BI:
1. **Series históricas por modelo/marca**: el motor guarda por captura
   (fecha, modelo) -> avisos activos, precio mediano, salidas. Persistir en
   un csv acumulativo (historia_mercado.csv) que crece con cada corrida —
   "generar nuestra data" del usuario. Widget de evolución temporal.
2. **Comparador de 3 modelos/marcas en velocidad de venta**: selector
   múltiple (hasta 3), curvas de tasa de salida y días de venta estimados
   lado a lado. Vive en la pestaña Análisis de mercado.
3. **Elasticidad de precio**: cruzar bajas_precio con salidas posteriores —
   ¿los avisos que bajaron X% salen del mercado en menos días que sus
   pares? Por modelo/marca/segmento. Requiere varias semanas de pares.
4. Tabla de rotación: filas ya clickeables -> saltan al BI filtrado (hecho).
