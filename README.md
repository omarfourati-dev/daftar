# Daftar – agenda du cabinet médical

Daftar (لاتيني + „دفتر“, das Heft) ersetzt das Papierheft der Arztpraxen in Tunesien: Termine, Warteschlange vor Ort,
Patientenkartei, Nichterscheinen, Barzahlungen in Raten, Online-Buchung je Praxis und eine installierbare App
(PWA) – auf PC am Empfang, Tablet und Handy, auf Französisch und Arabisch. Live: https://daftar.omarfourati.de
(Verkaufsseite mit Google AdSense), die App auf eigenem Ursprung unter https://app.daftar.omarfourati.de, jede Praxis
unter `https://<slug>.daftar.omarfourati.de`. Spezifikation: `docs/superpowers/specs/2026-10-30-daftar-design.md`.

## Stack

| Teil | Technik |
|---|---|
| `backend/` | Python 3.13 · FastAPI · SQLAlchemy 2 (Core) · psycopg 3 · Alembic · PyJWT · argon2-cffi · prometheus-client · Pillow |
| `web/` | SvelteKit 3 / Svelte 5 SPA (adapter-static, `200.html`) · Tailwind 4 · IBM Plex Sans Arabic (selbst gehostet) · Vitest · Playwright |
| `landing/` | statische Verkaufswebseite + Rechtstexte (HTML/CSS, kein Build) |
| Betrieb | ein Docker-Container `daftar` (Port 8080) hinter Caddy, Postgres des Servers, GitHub Actions |

FastAPI liefert alles aus einem Prozess: `/api/*`, `/healthz`, `/metrics`, die Landing und die SPA (Reihenfolge und
Sicherheits-Header siehe `backend/daftar/static.py` und `http.py`). Je Host:

| Host | liefert |
|---|---|
| `daftar.omarfourati.de` (Hauptdomain, AdSense) | Landing, Rechtstexte, statische Dateien; App-Pfade (`/app…`, `/connexion`, `/invitation`, `/reinitialiser`, `/r/…`, `/rdv/…`, `/salle/…`, `/ticket/…`) → 301 auf `app.`; keine Anmeldung |
| `app.daftar.omarfourati.de` | die ganze SPA (Admin, alle Praxis-Benutzer, Demo, Buchungsseiten `/r/<slug>`); `/` → `/app`; Landing-Pfade → 302 auf die Hauptdomain |
| `<slug>.daftar.omarfourati.de` | Buchungsseite (`/`) und eigene App der Praxis; nur deren Benutzer melden sich an |

Lokal mit `BASE_DOMAIN=localhost`: Hauptdomain `http://localhost:<port>`, App `http://app.localhost:<port>`, Praxis
`http://<slug>.localhost:<port>` (Browser lösen `*.localhost` selbst auf).

## Lokal entwickeln

Voraussetzungen: Docker, Python 3.13, Node 22. Auf Omars Rechner sind 5432/8080/8081/8090/9092 belegt – Daftar
nutzt **55436** (Postgres), **18083** (App im Docker), **18084** (Backend lokal).

```bash
# Datenbank (eine von beiden Varianten, beide auf Port 55436):
docker run -d --name daftar-postgres -e POSTGRES_PASSWORD=daftar -e POSTGRES_USER=daftar -p 55436:5432 postgres:17-alpine
docker compose up -d postgres

# Backend (siehe backend/README.md für alle Bausteine)
cd backend && py -3.13 -m venv .venv && .venv/Scripts/python -m pip install -r requirements-dev.txt

# Web mit Vite-Dev-Server (leitet /api an http://localhost:18084 weiter, API_URL überschreibt das).
# Anmelden geht nur auf dem App-Host: Backend mit BASE_DOMAIN=localhost starten und http://app.localhost:5173 öffnen.
cd web && npm ci && npm run dev

# Alles wie in Produktion (baut web/, startet Postgres + Landing auf http://localhost:18083, die App auf
# http://app.localhost:18083, Admin admin@daftar.test / local-admin-password-123, Praxen als <slug>.localhost:18083).
# Läuft der Container daftar-postgres schon auf 55436: POSTGRES_PORT=55437 davorsetzen.
docker compose --profile app up -d --build
```

Hinter einem TLS-prüfenden Proxy braucht der Docker-Build ein zusätzliches Root-Zertifikat: lokal liegt es in
`.git/extra-ca.pem`, `docker-compose.override.yml` (gitignored) reicht es als BuildKit-Secret `extra_ca` durch.

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest                 # gegen echtes Postgres (55436, DB daftar_test)
cd backend && .venv/Scripts/python -m tests.mutation_check   # optional: baut Fehler ein und erwartet rote Tests
cd web && npm run check && npx vitest run && npm run build
cd web && npx playwright test                                # E2E gegen den Docker-Stack auf :18083 (+ app.localhost)
```

CI (`.github/workflows/ci.yml`): Backend-Job mit Postgres-Service, Web-Job (check, vitest, build), E2E-Job
(Compose-Stack mit Wegwerf-Geheimnissen, Playwright).

## Deploy

Push auf `main` → `deploy.yml`: CI, dann Self-hosted-Runner auf myvps: rsync nach `/home/daftar`, DB-Rolle und DB
`daftar` in `zentrades-postgres`, `.env` aus den Secrets, `docker compose -f docker-compose.prod.yml up -d --build`
(App `daftar` und Datensicherung `daftar-backup`), Health abwarten, Caddy neu laden.

GitHub-Einstellungen (Environment `production`): Secrets `DB_PASSWORD` (nur Buchstaben, Ziffern, `_`, `-`, weil er in
der `DATABASE_URL` steht), `JWT_SECRET` (≥ 32 Zeichen), `ADMIN_PASSWORD` (≥ 10 Zeichen), optional
`FLOUCI_APP_TOKEN`, `FLOUCI_APP_SECRET`; Variablen `ADMIN_EMAIL`, optional `BASE_DOMAIN`.

Caddy (Wildcard-DNS `*.daftar` → Server, On-Demand-TLS fragt das Backend; `app.daftar.omarfourati.de` läuft über den
Wildcard-Block, der tls-check antwortet für `app` mit 200). HSTS setzt die App selbst (nur über HTTPS, ohne
`includeSubDomains`):

```
{
	on_demand_tls {
		ask http://daftar:8080/api/public/tls-check
	}
}
daftar.omarfourati.de {
	import access_log
	respond /metrics 404
	request_body { max_size 2MB }
	reverse_proxy daftar:8080
}
*.daftar.omarfourati.de {
	tls { on_demand }
	import access_log
	respond /metrics 404
	request_body { max_size 2MB }
	reverse_proxy daftar:8080
}
```

## Datensicherung und Wiederherstellung

Der Container `daftar-backup` (`postgres:17-alpine`, Skript `ops/backup.sh`, in `docker-compose.prod.yml`) sichert
die Datenbank `daftar` täglich um 02:30 Uhr (Europe/Berlin) mit `pg_dump -Fc` in das benannte Docker-Volume
`daftar_backups` – bewusst nicht unter `/home/daftar`, das der Deploy mit `rsync --delete` abgleicht. Dateiname
`daftar-JJJJ-MM-TT_HHMM.dump`; Sicherungen älter als 14 Tage löscht das Skript. Das Passwort kommt als `PGPASSWORD`
aus `DB_PASSWORD` und erscheint nie im Log. Test: `backend/tests/test_backup_script.py` (Dump, Aufbewahrung,
Wiederherstellung in eine Wegwerf-DB, Fehlerfall, Zeitplan; braucht Docker).

```bash
# Sicherungen und Log ansehen
docker run --rm -v daftar_backups:/b:ro alpine ls -lh /b
docker logs daftar-backup --tail 20

# Sofort sichern (z. B. vor einem größeren Update)
docker exec daftar-backup sh /ops/backup.sh

# Eine Sicherung aus dem Volume holen (danach z. B. per scp auf den eigenen Rechner)
docker run --rm -v daftar_backups:/b:ro alpine cat /b/daftar-2026-10-30_0230.dump > /root/daftar-2026-10-30_0230.dump

# Wiederherstellen – ersetzt den Inhalt der Datenbank daftar (alles oder nichts: --single-transaction)
cd /home/daftar
docker compose -f docker-compose.prod.yml stop daftar
DB_PASSWORD=$(sed -n 's/^DB_PASSWORD=//p' .env)          # nur in dieser Shell, nie in der Kommandozeile von docker
PGPASSWORD="$DB_PASSWORD" docker run --rm -e PGPASSWORD -v daftar_backups:/b:ro --network web \
  --add-host=host.docker.internal:host-gateway postgres:17-alpine \
  pg_restore -h host.docker.internal -p 5433 -U daftar -d daftar \
  --clean --if-exists --no-owner --single-transaction --exit-on-error /b/daftar-2026-10-30_0230.dump
unset DB_PASSWORD
docker compose -f docker-compose.prod.yml start daftar
```

Zum Ausprobieren ohne Risiko in eine Wegwerf-Datenbank wiederherstellen: vorher
`docker exec zentrades-postgres psql -U zentrades -d postgres -c "CREATE DATABASE daftar_probe OWNER daftar"`, im
`pg_restore` dann `-d daftar_probe`, danach `DROP DATABASE daftar_probe`. Die Sicherungen liegen auf demselben Server –
gegen einen Plattenausfall regelmäßig eine Kopie herunterladen.

## Umgebungsvariablen

| Variable | Pflicht | Bedeutung |
|---|---|---|
| `DATABASE_URL` | ja | `postgresql+psycopg://user:passwort@host:port/db` (auch `postgresql://` wird angenommen) |
| `JWT_SECRET` | ja | ≥ 32 Zeichen, signiert die Anmelde-Tokens (30 Tage gültig) |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | empfohlen | legt beim Start das Admin-Konto an (Passwort ≥ 10 Zeichen) |
| `ADMIN_RESET_PASSWORD` | nein | `true` setzt das Admin-Passwort beim Start auf `ADMIN_PASSWORD` zurück |
| `PORT` | nein | Standard 8080 |
| `BASE_DOMAIN` | nein | Standard `daftar.omarfourati.de`; Praxen unter `<slug>.<BASE_DOMAIN>` (lokal `localhost`) |
| `FLOUCI_APP_TOKEN`, `FLOUCI_APP_SECRET` | nein | Online-Zahlung der Abos; ohne sie bleibt sie ausgeschaltet |
| `LANDING_DIR`, `WEB_DIR` | nein | Verzeichnisse der Landing und des SPA-Builds (im Image `/app/landing`, `/app/web`) |
| `LOG_REQUESTS` | nein | `false` schaltet das Request-Log ab |
