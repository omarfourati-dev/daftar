# E2E-Tests der Verkaufswebseite

`landing.spec.ts` prüft alle statischen Seiten unter `landing/` (FR, AR, Rechtstexte) im Browser:
Status 200, `lang`/`dir`, Titel, Canonical, `hreflang`, OG/Twitter, keine Konsolenfehler (inkl. CSP),
keine Requests an fremde Hosts, keine horizontale Scrollleiste bei 360/390 px, alle internen Links,
Sprachwechsel FR ↔ AR, Demo-/Login-Links, JSON-LD, `robots.txt`, `sitemap.xml`, `llms.txt`,
`og-image.png`, App-Icon sowie das Pilot-Formular (Validierung, Erfolg 202, Fehler 429/500/Netzwerk,
JSON-Body inkl. Honeypot `website`, ohne JavaScript nur der `mailto:`-Hinweis). Das Backend wird für
`POST /api/public/pilot-requests` mit `page.route` gemockt.

Seit Abschnitt 11/12 der Spezifikation außerdem: Texte nicht zahnarztspezifisch (alle Fachrichtungen),
Abschnitt Online-Buchung mit Beispieladresse und Mockup, Funktionsliste (mehrere Behandler, Leistungen mit
Dauer und Preis, Pause, Urlaub, keine Doppelbuchung), Preise mit „Flouci ou virement“, Formate der Mockups
(Desktop 1440 × 900, Handy 390 : 844 – gilt auch für die späteren echten Screenshots), Rechtstexte mit
Abschnitten `#reservation-en-ligne` und `#abonnement`, Muster-AVV mit Online-Buchung in den Anlagen.

Basis-URL: `E2E_BASE_URL` (Standard `http://localhost:18083`). Der Server muss `landing/` so ausliefern
wie in Produktion (Datei → Verzeichnis mit `index.html`) und SPA-Routen (`/app/…`, `/connexion`) mit 200
beantworten. Tests mit `request.get` erwarten für Verzeichnisse den Pfad mit abschließendem `/`.

## Starten

Im Haupt-Repo (Datei liegt dann unter `web/e2e/`, `@playwright/test` ist in `web/package.json`):

```sh
cd web
E2E_BASE_URL=http://localhost:18083 npx playwright test e2e/landing.spec.ts --workers=2
```


temporären Ordner außerhalb des Repos:

```sh
mkdir -p /tmp/daftar-e2e && cd /tmp/daftar-e2e && npm init -y && npm i -D @playwright/test
npx playwright install chromium
# landing/ statisch ausliefern, z. B. auf Port 18083, dann:
NODE_PATH=$PWD/node_modules E2E_BASE_URL=http://localhost:18083 \
  npx playwright test --config /dev/null "<repo>/landing/e2e/landing.spec.ts" --workers=2
```

Hinweis: Auf schwächeren Rechnern mit `--workers=2` laufen lassen; bei vielen parallelen Browsern
kommt es sonst zu Zeitüberschreitungen beim Laden.
