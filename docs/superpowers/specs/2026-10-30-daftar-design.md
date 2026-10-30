# Daftar – Design

Stand: 30.10.2026 · Autor: Omar Fourati (mit Claude) · Live-Ziel: https://daftar.omarfourati.de

## 1. Worum es geht

Zahnarztpraxen in Tunesien führen Termine meist in einem Papierheft („دفتر“, daftar). Daftar ersetzt dieses Heft:
Termine, Warteschlange vor Ort, Patientenkartei, Nichterscheinen-Zähler, Barzahlungen in Raten mit offenem Betrag
und Anzahlungen – auf PC am Empfang, Tablet und Handy. Omar will Daftar an Praxen verkaufen; zunächst gibt es eine
**kostenlose Pilotphase** (noch kein Gewerbe, keine Verträge, keine Online-Zahlung) und eine **Demo**, die jeder
sofort ausprobieren kann.

**Ziele**
- Eine Verkaufswebseite (FR + AR), die einen Zahnarzt in 30 Sekunden überzeugt und zur Demo oder Pilot-Anfrage führt.
- Eine App, die eine Empfangskraft ohne Schulung bedienen kann: neuer Termin in 10 Sekunden, Patient per Telefonnummer.
- Läuft auf Desktop, Android und iPhone als installierbare Web-App (PWA). Store-Apps später mit Capacitor (nicht heute).
- Mehrere Praxen auf einem Server (Mandanten), strikt getrennt.
- Datenschutz: Datenschutzerklärung (FR/AR/DE), Impressum, Muster-Auftragsverarbeitungsvertrag (FR), Datenexport,
  Löschung, keine externen Dienste/Tracker, keine Google Fonts.

**Nicht-Ziele (MVP)**: Online-Zahlung (D17/Flouci-API), automatischer SMS/WhatsApp-Versand über eine API
(stattdessen Klick-Links `wa.me`/`sms:`), Zahnschema/Röntgen, CNAM-Abrechnung, Offline-Bearbeitung, Store-Apps,
Selbstregistrierung von Praxen (Praxen legt Omar als Admin an; jeder Besucher bekommt aber eine eigene Demo-Praxis).

**Anti-Ziele**: Patientennamen auf öffentlichen Seiten (Wartezimmer-Bildschirm, Ticket-Seite) – nur Ticketnummern.
Demo-Daten, die echte Telefonnummern enthalten. Irgendein Request an Dritte beim Laden der Seiten.

## 2. Architektur

```
daftar/
  backend/      Python 3.13 · FastAPI · SQLAlchemy 2 (Core) · psycopg 3 · Alembic · PyJWT · argon2-cffi · prometheus-client
  web/          SvelteKit 3 / Svelte 5 SPA (adapter-static, fallback 200.html) · Tailwind 4 · Vitest · Playwright
  landing/      statische Verkaufswebseite + Rechtstexte (HTML/CSS, kein Build, kein Inline-Script)
  Dockerfile    baut web/, kopiert web/build + landing/ in das Python-Image; ein Container „daftar“ (Port 8080)
  .github/workflows/ci.yml, deploy.yml   wie Redefluss (Self-hosted-Runner auf myvps, Postgres des Hosts)
```

- Ein Prozess: FastAPI liefert `/api/*`, `/healthz`, `/metrics` (öffentlich 404 über Caddy), die Landing-Seiten und
  die SPA. Reihenfolge der statischen Auslieferung: exakte Datei in `landing/` → Verzeichnis mit `index.html` in
  `landing/` → Datei aus `web/build` → für Pfade ohne Dateiendung unter `/app`, `/connexion`, `/invitation`,
  `/salle/`, `/ticket/` die SPA-Datei `200.html` → sonst 404 (problem+json für `/api`).
- CSP wie Redefluss (`default-src 'self'`, Hashes der Inline-Scripts von `200.html` zur Startzeit berechnen,
  `img-src 'self' data: blob:`, `connect-src 'self'`, `frame-ancestors 'none'`, `font-src 'self'`). Keine externen Hosts.
  Weitere Header: `X-Content-Type-Options`, `Referrer-Policy: strict-origin-when-cross-origin`,
  `Permissions-Policy: camera=(), microphone=(), geolocation=()`. Hinter Caddy: echte Client-IP = **letzter** Eintrag
  von `X-Forwarded-For`.
- Cache: `/_app/immutable/*` 1 Jahr immutable; `200.html`, `sw.js`, `manifest.webmanifest`, Landing-HTML `no-cache`.
- Zeitzone aller Fachlogik: `Africa/Tunis` (UTC+1, keine Sommerzeit). „Heute“ = Datum in Tunis über eine injizierte Uhr.
- Geld: ganzzahlig in **Millimes** (1 DT = 1000 Millimes), Feldnamen enden auf `Millimes`.
- Telefon: normalisiert E.164. Tunesische Eingaben „20 123 456“, „+216 20123456“, „0021620123456“ → `+21620123456`
  (8 Ziffern nach 216). Andere Länder nur mit `+`. Familien teilen Nummern → keine Eindeutigkeit.
- Lokal: Postgres im Docker-Container `daftar-postgres` auf Port **55436** (Tests in DB `daftar_test`). Niemals andere
  Container anfassen und Docker Desktop nie neu starten (auf dem Rechner laufen Firmen-Container auf 5432/8081/8090/9092).
  Java/Kotlin läuft auf diesem Rechner nicht (Loopback blockiert) – deshalb Python.

## 3. Rollen und Mandanten

| Rolle | Wer | Darf |
|---|---|---|
| `admin` | Omar (aus `ADMIN_EMAIL`/`ADMIN_PASSWORD` beim Start angelegt, keine Praxis) | Praxen anlegen, Besitzer-Einladungslink erzeugen, Pilot-Anfragen sehen/löschen, Praxen löschen |
| `owner` | Zahnarzt, dem die Praxis gehört | alles in seiner Praxis + Mitarbeiter, Einstellungen, Export, Patient/Zahlung löschen |
| `dentist` | weiterer Zahnarzt | Termine, Patienten, Warteschlange, Zahlungen erfassen; kann Behandler eines Termins sein |
| `assistant` | Empfang/Assistenz | wie `dentist`, ist aber nie Behandler |

Jede fachliche Tabelle hat `practice_id`; jede Abfrage filtert über die Praxis aus dem Token. Fremde IDs → **404**
(nie 403, damit nichts über fremde Daten verraten wird). Tests prüfen das für jeden Endpunkt-Typ.

## 4. Datenmodell (Postgres, Alembic)

- `practice(id, name, address, city, phone, day_start TIME '08:00', day_end TIME '18:00', slot_minutes 15,
  default_duration_min 30, reminder_template_fr, reminder_template_ar, display_token UNIQUE, is_demo BOOL,
  demo_expires_at, created_at)`
- `app_user(id, email UNIQUE lower, password_hash, token_version, practice_id NULL→practice ON DELETE CASCADE, role,
  name, lang 'fr'|'ar', created_at)`
- `invitation(id, practice_id, role 'owner'|'dentist'|'assistant', token_hash UNIQUE (SHA-256, nie das Token),
  created_by NULL, created_at, expires_at (+7 Tage), used_at)` – Einmal-Link `/invitation#<token>`.
- `patient(id, practice_id, first_name, last_name, phone, birth_year NULL, lang, reminder_consent BOOL, notes,
  created_at)`; Index `(practice_id, last_name, first_name)`, `(practice_id, phone)`.
- `appointment(id, practice_id, patient_id CASCADE, practitioner_id NULL→app_user SET NULL, starts_at TIMESTAMPTZ,
  duration_min, reason, status, notes, deposit_required_millimes 0, reminder_sent_at, created_by, created_at)`;
  `status ∈ scheduled|confirmed|arrived|in_treatment|done|no_show|cancelled`.
- `queue_entry(id, practice_id, day DATE, ticket_no, patient_id NULL, appointment_id NULL UNIQUE, name, phone,
  status waiting|called|in_treatment|done|left, ticket_token UNIQUE, arrived_at, called_at, done_at)`;
  `UNIQUE(practice_id, day, ticket_no)`.
- `treatment(id, practice_id, patient_id CASCADE, label, tooth, price_millimes, performed_on DATE NULL,
  appointment_id NULL SET NULL, created_at)` – Behandlungsplan/Leistungen.
- `payment(id, practice_id, patient_id CASCADE, amount_millimes >0, method cash|d17|flouci|card|cheque|transfer|other,
  paid_at, appointment_id NULL SET NULL, is_deposit BOOL, note, received_by NULL, created_at)`.
- `pilot_request(id, name, practice, city, phone, email, message, lang, created_at)`.

Ableitungen: Saldo eines Patienten = Σ treatment.price − Σ payment.amount (`totalMillimes`, `paidMillimes`,
`dueMillimes`). Nichterscheinen = Anzahl Termine mit `no_show`; `attended` = `done`.
Anzahlung eines Termins bezahlt = Σ payment.amount mit `is_deposit` und diesem `appointment_id`.

## 5. API (JSON, `Authorization: Bearer <JWT>`, Fehler als `application/problem+json` mit `title`/`detail`)

Feldnamen camelCase. Zeitpunkte ISO-8601 mit Offset (`2026-10-30T09:30:00+01:00`), Tage `YYYY-MM-DD`.

**Auth & Konto**
- `POST /api/auth/login {email,password}` → `{token, user: Me}`; 401 falsch, 429 gedrosselt (wie Redefluss: 20/IP, 5/E-Mail+IP je 15 min).
- `GET /api/auth/me` → `Me {id,email,name,role,lang,practice:{id,name,isDemo,demoExpiresAt}|null}`
- `PATCH /api/auth/me {name?,lang?}` → Me · `POST /api/auth/password {current,next}` (next ≥ 10 Zeichen) → `{token}`
- `POST /api/auth/logout-all` → 204 (token_version++)
- `POST /api/invitations/preview {token}` → `{practiceName, role}` (404 ungültig/abgelaufen/benutzt)
- `POST /api/invitations/accept {token,name,email,password}` → 201 `{token,user}`; 409 E-Mail vergeben.

**Praxis & Team** (lesen: alle Rollen; ändern: owner)
- `GET /api/practice` → `{id,name,address,city,phone,dayStart:"08:00",dayEnd:"18:00",slotMinutes,defaultDurationMin,reminderTemplateFr,reminderTemplateAr,displayToken,isDemo}`
- `PATCH /api/practice {…}` · `POST /api/practice/display-token` → neues Token
- `GET /api/practice/export` (owner) → JSON-Download aller Praxisdaten (`Content-Disposition: attachment`)
- `GET /api/staff` → `[{id,name,email,role,createdAt}]` · `PATCH /api/staff/{id} {role}` · `DELETE /api/staff/{id}` (nicht sich selbst, nicht owner)
- `GET /api/staff/invitations` → `[{id,role,createdAt,expiresAt}]` · `POST /api/staff/invitations {role:'dentist'|'assistant'}` → 201 `{id,token,expiresAt}` · `DELETE /api/staff/invitations/{id}`
- `GET /api/practitioners` → `[{id,name}]` (owner + dentist)

**Patienten**
- `GET /api/patients?q=&limit=50&offset=0` → `{items:[PatientSummary],total}`; `q` sucht in Vor-/Nachname und Telefon-Ziffern.
  `PatientSummary {id,firstName,lastName,phone,birthYear,lang,reminderConsent,noShows,attended,dueMillimes,nextAppointmentAt}`
- `POST /api/patients {firstName,lastName,phone,birthYear?,lang,reminderConsent,notes?}` → 201 Patient (422 ungültige Telefonnummer)
- `GET /api/patients/{id}` → `Patient` = Summary + `{notes,createdAt,cancelled,totalMillimes,paidMillimes}`
- `PATCH /api/patients/{id}` · `DELETE /api/patients/{id}` (owner) → 204, löscht alles des Patienten
- `GET /api/patients/{id}/appointments` → `[Appointment]` (neueste zuerst)
- `GET /api/patients/{id}/ledger` → `{treatments:[Treatment],payments:[Payment],totalMillimes,paidMillimes,dueMillimes}`

**Termine**
- `Appointment {id,patient:{id,firstName,lastName,phone,noShows},practitionerId,practitionerName,startsAt,durationMin,reason,status,notes,depositRequiredMillimes,depositPaidMillimes,reminderSentAt,createdAt}`
- `GET /api/appointments?from=YYYY-MM-DD&to=YYYY-MM-DD&practitionerId=` (max. 62 Tage) → `[Appointment]` nach Beginn sortiert
- `POST /api/appointments {patientId,startsAt,durationMin?,reason,practitionerId?,notes?,depositRequiredMillimes?}` → 201 `{appointment, conflicts:[{id,startsAt,patientName}]}` (Überschneidungen mit nicht stornierten Terminen desselben Behandlers bzw. ohne Behandler; nur Warnung)
- `PATCH /api/appointments/{id} {…}` → gleiche Antwortform · `DELETE /api/appointments/{id}` → 204
- `POST /api/appointments/{id}/status {status}` → Appointment. Nebenwirkung: `arrived` legt (falls noch nicht da) einen Warteschlangen-Eintrag für heute an (Name/Telefon vom Patienten, verknüpft); `in_treatment`/`done` setzen den verknüpften Eintrag mit.
- `POST /api/appointments/{id}/reminder` → Appointment mit `reminderSentAt` = jetzt

**Warteschlange**
- `QueueEntry {id,ticketNo,name,phone,patientId,appointmentId,appointmentAt,status,arrivedAt,calledAt,doneAt,ticketToken,position,peopleAhead,estimatedWaitMin}` (`position` nur für `waiting`, 1-basiert; Schätzung = peopleAhead × defaultDurationMin, nur Ganzzahl)
- `GET /api/queue?day=` (Standard heute) → `[QueueEntry]` (aktive zuerst nach Ticket, dann erledigte)
- `POST /api/queue {patientId?|name+phone?}` → 201 QueueEntry (nächste Ticketnummer des Tages)
- `POST /api/queue/{id}/status {status}` → QueueEntry · `DELETE /api/queue/{id}` → 204
- öffentlich: `GET /api/public/display/{displayToken}` → `{practiceName,called:[ticketNo] (called/in_treatment, neueste zuerst, max 3),next:[ticketNo] (max 5),waiting:int}`
- öffentlich: `GET /api/public/ticket/{ticketToken}` → `{practiceName,practicePhone,ticketNo,status,peopleAhead,estimatedWaitMin,day}` – **keine Namen**

**Geld**
- `Treatment {id,label,tooth,priceMillimes,performedOn,appointmentId,createdAt}`
- `POST /api/patients/{id}/treatments {label,tooth?,priceMillimes,performedOn?,appointmentId?}` → 201 · `PATCH /api/treatments/{id}` · `DELETE /api/treatments/{id}` → 204
- `Payment {id,patientId,patientName,amountMillimes,method,paidAt,appointmentId,isDeposit,note,receivedByName}`
- `POST /api/patients/{id}/payments {amountMillimes,method,paidAt?,appointmentId?,isDeposit?,note?}` → 201 · `GET /api/payments/{id}` → Payment + `practice:{name,address,city,phone}` (Quittung) · `DELETE /api/payments/{id}` (owner) → 204
- `GET /api/cash?day=` → `{day,totalMillimes,byMethod:{cash:…,d17:…,…},payments:[Payment]}`
- `GET /api/balances?limit=100` → `[{patientId,name,phone,dueMillimes,lastPaymentAt}]` (nur due > 0, absteigend)

**Erinnerungen & Übersicht**
- `GET /api/reminders?day=` (Standard morgen) → `[{appointment:Appointment,patientLang,reminderConsent,phoneDigits,message}]`; `message` = Vorlage der Patientensprache mit `{patient} {date} {time} {practice} {phone}` ersetzt (Datum `jj/mm/aaaa`, Zeit `HH:MM`); stornierte Termine fehlen. `phoneDigits` ohne `+` für `wa.me`.
- `GET /api/dashboard` → `{today,appointments:{total,byStatus:{…}},upcoming:[Appointment] (heute, ab jetzt, max 5),queue:{waiting,called},cashTodayMillimes,remindersPending,dueTotalMillimes,patientsCount}`

**Demo, Pilot, Admin**
- `POST /api/demo {lang?}` → 201 `{token,user}`: neue Praxis „Cabinet Dentaire Démo“ (`is_demo`, läuft nach 24 h ab), Besitzer `demo-<zufall>@demo.daftar.invalid`, gefüllt mit erfundenen Daten relativ zu heute (25 Patienten mit tunesischen Namen, Telefon **`+21600000001…`** – die Vorwahl 00 existiert nicht; Termine −14…+7 Tage mit realistischen Status inkl. Nichterscheinen; heute 3 Wartende, 1 in Behandlung; Leistungen und Teilzahlungen; Termine morgen für Erinnerungen). Drosselung: 5 je IP und Stunde, 300 je Tag gesamt → 429. Aufräumjob alle 30 min löscht abgelaufene Demo-Praxen (CASCADE) und abgelaufene unbenutzte Einladungen älter als 30 Tage.
- `POST /api/public/pilot-requests {name,practice,city,phone,email?,message?,lang,website}` → 202; `website` ist ein Honeypot (nicht leer → trotzdem 202, aber nicht speichern); Längen begrenzt (Name/Praxis/Stadt ≤ 120, Nachricht ≤ 2000); 5 je IP und Stunde.
- `GET /api/admin/practices` → `[{id,name,city,isDemo,createdAt,users,patients,appointments,lastActivityAt}]` (Demo-Praxen ausblendbar per `?demo=false`, Standard ohne Demos)
- `POST /api/admin/practices {name,city,phone?,address?}` → 201 `{practice,invitation:{token,expiresAt}}` (Einladung Rolle owner)
- `POST /api/admin/practices/{id}/invitation` → 201 `{token,expiresAt}` · `DELETE /api/admin/practices/{id}` → 204
- `GET /api/admin/pilot-requests` → `[PilotRequest]` · `DELETE /api/admin/pilot-requests/{id}` → 204

**Betrieb**: `GET /healthz` (DB-Ping) · `GET /metrics` (Prometheus): `daftar_practices{kind="pilot|demo"}`,
`daftar_users`, `daftar_patients`, Zähler `daftar_appointments_created_total`, `daftar_demo_started_total`,
`daftar_pilot_requests_total`, `daftar_logins_total{result}`, HTTP-Dauer/Status je Route-Vorlage.

## 6. App (SvelteKit, Routen)

FR ist Standard, AR wählbar (RTL, `dir="rtl"`, westliche Ziffern). Sprache gespeichert in localStorage und am Konto.

| Route | Inhalt |
|---|---|
| `/connexion` | Login |
| `/invitation#token` | Einladung annehmen (Name, E-Mail, Passwort ×2, ≥ 10 Zeichen) |
| `/app` | „Aujourd'hui“: Kacheln (Termine heute nach Status, Wartende, Kasse heute, offene Erinnerungen, offene Beträge), nächste Termine |
| `/app/agenda` | Tag (Zeitraster `dayStart`–`dayEnd`, Spalte je Behandler wenn > 1) und Woche; Datum blättern; Klick auf Slot → Termin anlegen (Patient suchen per Name/Telefon oder neu anlegen im selben Dialog); Termin-Dialog: Status-Knöpfe, Verschieben, Anzahlung; Warnung bei Überschneidung und bei ≥ 2 Nichterscheinen („Acompte conseillé“) |
| `/app/salle` | Warteschlange heute: Ticket ziehen (Patient oder nur Name/Telefon), Aufrufen, In Behandlung, Fertig, Gegangen; je Ticket WhatsApp-Link mit Ticket-Seite und QR-Code zum Abfotografieren; Link zum Wartezimmer-Bildschirm |
| `/app/patients`, `/app/patients/[id]` | Liste mit Suche; Akte: Daten, Zuverlässigkeit (gekommen/nicht gekommen), Termine, Leistungen, Zahlungen, Saldo, Zahlung/Leistung erfassen, Quittung |
| `/app/caisse` | Kasse des Tages nach Zahlart, Liste; offene Beträge |
| `/app/rappels` | Termine morgen: je Zeile WhatsApp- und SMS-Knopf mit fertiger Nachricht, „Envoyé“ markieren; ohne Einwilligung ausgegraut; in Demo-Praxen öffnen die Knöpfe nichts, sondern zeigen einen Hinweis |
| `/app/recu/[paymentId]` | druckbare Quittung |
| `/app/reglages` | Praxis, Zeiten, Vorlagen FR/AR, Bildschirm-Link (neu erzeugen), Team & Einladungen (owner), Export (owner), eigenes Konto/Passwort/Sprache, Abmelden überall |
| `/app/admin` | nur admin: Praxen, neue Praxis + Einladungslink kopieren, Pilot-Anfragen |
| `/app/demo` | startet eine Demo und leitet nach `/app`; Banner „Démo – données fictives, supprimées après 24 h“ in allen Demo-Sitzungen |
| `/salle/[token]` | öffentlicher Wartezimmer-Bildschirm (Vollbild, große Ziffern, Abfrage alle 10 s) |
| `/ticket/[token]` | öffentliche Ticket-Seite für den Patienten (Position, Wartezeit, Abfrage alle 20 s) |

Navigation: Desktop Seitenleiste, Handy untere Leiste (Aujourd'hui, Agenda, Salle, Patients, Plus). Große
Klickflächen (Tablet), Tastatur bedienbar, sichtbarer Fokus, Kontrast AA. Status-Farben: scheduled slate,
confirmed sky, arrived amber, in_treatment violet, done emerald, no_show rose, cancelled zinc (durchgestrichen).

PWA: `manifest.webmanifest` (`name` „Daftar – agenda du cabinet dentaire“, `short_name` „Daftar“, `start_url`
`/app`, `scope` `/`, `display` standalone, `theme_color` #0f766e), Icons aus `landing/brand/icon.svg`, Service
Worker wie Redefluss (nur App-Shell cachen, nie `/api`, Navigation network-first, Fallback `/200.html` nur für
SPA-Routen, Landing-Seiten nicht abfangen). Offline: Banner „Hors ligne“.

## 7. Verkaufswebseite und Rechtstexte (`landing/`)

Statisches HTML + eine CSS-Datei, selbst gehostete Schrift (IBM Plex Sans Arabic, deckt Latein + Arabisch,
woff2 400/600/700), kein Inline-Script, kein externes Laden. Seiten:
- `/` (FR) und `/ar/` (AR, RTL): Hero („Fini le cahier de rendez-vous“), Probleme → Lösungen (Absences, salle
  d'attente, impayés, tout sur papier), Funktionen mit Screenshots (`landing/img/`, PNG/WebP; bis echte Screenshots
  da sind: gezeichnete Platzhalter), „Sur tous vos appareils“ inkl. Installationsanleitung (iPhone: Partager → Sur
  l'écran d'accueil; Android/Chrome; Windows/Edge), Sicherheit & Datenschutz, Ablauf in 3 Schritten, Preise
  („Phase pilote : gratuite“, danach „à partir de 49 DT/mois, sans engagement, tarif préférentiel pour les cabinets
  pilotes“ – Omar kann das ändern), FAQ, Formular „Demander un accès pilote“ (POST `/api/public/pilot-requests`,
  progressive enhancement mit externer `landing/site.js`; ohne JS normaler Form-POST ist nicht nötig – ohne JS
  Hinweis + `mailto:`), Kontakt `info@omarfourati.de`. CTAs: „Essayer la démo“ → `/app/demo`, „Demander un accès pilote“.
- `/mentions-legales/` (FR + DE-Impressum nach § 5 DDG), `/confidentialite/` (FR), `/ar/confidentialite/` (AR),
  `/datenschutz/` (DE), `/contrat-sous-traitance/` (FR, Muster nach Art. 28 DSGVO, als Muster gekennzeichnet).
- `robots.txt`, `sitemap.xml`, `llms.txt`, `favicon.svg`, `og-image.png` (1200×630), OG/Twitter-Tags, `hreflang`.

Inhalt der Datenschutzerklärung (Fakten aus `C:\private\omar_developer_portfolio\src\app\[locale]\datenschutz\page.tsx`
und `…\impressum\page.tsx` übernehmen, nichts erfinden): Verantwortlicher für die Website = Omar Fourati
(Anschrift aus dem Impressum), Hosting VPS bei IONOS SE in Deutschland, Server-Logs (Caddy) wie im Portfolio
beschrieben, keine Cookies/kein Tracking auf der Website, Pilot-Formular (Zweck, Rechtsgrundlage Art. 6 Abs. 1 lit. b/f
DSGVO, Löschung nach spätestens 12 Monaten), Demo (fiktive Daten, 24 h), App: die Praxis ist Verantwortliche für
Patientendaten, Daftar ist Auftragsverarbeiter (Art. 28 DSGVO, Muster-AVV), Speicherung in Deutschland, TLS,
Passwörter gehasht (Argon2), localStorage nur für Anmeldung/Sprache, Export und Löschung, Betroffenenrechte,
Beschwerde bei der zuständigen Aufsichtsbehörde (NRW), Hinweis auf das tunesische Datenschutzgesetz
(Loi organique n° 2004-63) und die INPDP für Praxen. Stand 30.10.2026.

## 8. Marke

Name **Daftar** (لاتيني + „دفتر“). Logo: abgerundetes Quadrat in Teal mit stilisiertem Heft, dessen Rücken ein
Zahn ist; Wortmarke „Daftar“. Farben: primary #0f766e (teal-700), dunkel #134e4a, hell #f0fdfa, Akzent #f59e0b,
Text #0f172a, Fläche #ffffff/#f8fafc. Ton: freundlich, klar, Sie-Form („vous“), keine Übertreibungen, keine
erfundenen Kundenzahlen oder Testimonials.

## 9. Tests und Auslieferung

- Backend: pytest gegen echtes Postgres (Port 55436 lokal, Service-Container in CI); pro Endpunkt Erfolg,
  Validierung, 401 ohne Token, **Mandantentrennung (fremde Praxis → 404)**, Rollenrechte.
- Web: Vitest (jsdom, `mockApi`-Helfer wie Redefluss), `npm run check`, Build.
- E2E: Playwright gegen `docker compose --profile app` (CI): Landing FR/AR, Demo starten, Patient + Termin anlegen,
  Ankunft → Warteschlange, Zahlung → Saldo, Erinnerung-Link, AR-Umschaltung, Pilot-Formular, Ticket-Seite ohne Namen.
- CI `ci.yml` (GitHub-hosted), `deploy.yml` (push auf main → CI → Self-hosted-Runner: rsync nach `/home/daftar`,
  DB-Rolle/DB `daftar` in `zentrades-postgres` anlegen, `.env` aus Secrets `DB_PASSWORD`, `JWT_SECRET`,
  `ADMIN_PASSWORD` und Variable `ADMIN_EMAIL`, `docker compose -f docker-compose.prod.yml up -d --build`, Health
  abwarten, Caddy neu laden). Caddy-Block `daftar.omarfourati.de { import access_log; respond /metrics 404;
  request_body { max_size 2MB }; reverse_proxy daftar:8080 }`.
- Monitoring im Repo `server-monitoring`: Job, Blackbox-Probes (`/`, `/app`, `/healthz`), Alarme (Down,
  5xx-Rate, neue Pilot-Anfrage), Dashboard „Daftar“, README.

## 10. Bewusst offen gelassen (Builder entscheidet)

Komponentenschnitt, genaue Texte der App (kurz, FR/AR), Seed-Details der Demo, Layout der Woche auf dem Handy
(Liste statt Raster ist okay), Aussehen der Landing im Rahmen von Abschnitt 8.
