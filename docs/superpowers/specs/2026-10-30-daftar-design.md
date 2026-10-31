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
  die SPA – je nach Host (`backend/daftar/hosts.py`, `static.py`):
  - **App-Host `app.<BASE_DOMAIN>`** (Fix-Liste 1, 30.10. abends; Slug `app` reserviert, tls-check 200): die komplette
    SPA – Admin, alle Praxis-Benutzer, `/app/demo`, `/connexion`, `/invitation`, `/reinitialiser`, `/r/<slug>`,
    `/rdv`, `/salle/…`, `/ticket/…` → `200.html`; Dateien aus `web/build`; `/` → 302 `/app`; alles andere 302 auf
    denselben Pfad der Hauptdomain. Das Anmelde-Token im localStorage liegt damit auf einem Ursprung ohne fremde Scripts.
  - **Hauptdomain `<BASE_DOMAIN>`** (zeigt AdSense; auch jeder andere Host): nur Landing, Rechtstexte und statische
    Dateien – exakte Datei in `landing/` → Verzeichnis mit `index.html` in `landing/` → Datei aus `web/build`, aber nie
    `200.html` → sonst 404 (problem+json für `/api`). App-Pfade (ohne Dateiendung unter `/app`, `/connexion`,
    `/invitation`, `/reinitialiser`, `/r/`, `/salle/`, `/ticket/` sowie die Seite `/rdv`) → **301** auf
    `https://app.<BASE_DOMAIN><pfad>?<query>` (Fragmente wie `#token` behält der Browser). Anmelden geht hier nicht
    (401 wie bei falschem Passwort); die API (z. B. `POST /api/public/pilot-requests` der Landing) läuft weiter. Der
    Service Worker tut hier nichts und meldet sich ab.
  - **Praxis-Subdomain `<slug>.<BASE_DOMAIN>`**: Abschnitte 11.3 und 13.
  - Lokal `BASE_DOMAIN=localhost`: `http://localhost:<port>` ist die Hauptdomain, `http://app.localhost:<port>` die App.
- CSP wie Redefluss (`default-src 'self'`, Hashes der Inline-Scripts von `200.html` zur Startzeit berechnen,
  `img-src 'self' data: blob:`, `connect-src 'self'`, `frame-ancestors 'none'`, `font-src 'self'`). Keine externen Hosts.
  Ausnahme (Omar, 30.10.): Google AdSense auf den beiden Startseiten `/` und `/ar/` – nur deren HTML bekommt eine
  gelockerte CSP wie Briefklar (`script-src 'self' 'unsafe-inline' https:`, `img-src … https:`, `frame-src https:`,
  `connect-src 'self' https:`, `ADS_CSP` in `backend/daftar/http.py`); App, Buchungs-/Ticket-/Wartezimmerseiten,
  Praxis-Subdomains, Rechtstexte und API behalten die strenge CSP.
  Weitere Header: `X-Content-Type-Options`, `Referrer-Policy: strict-origin-when-cross-origin`,
  `Permissions-Policy: camera=(), microphone=(), geolocation=()`, über HTTPS (direkt oder `X-Forwarded-Proto: https`
  von Caddy) `Strict-Transport-Security: max-age=31536000` – ohne `includeSubDomains`/`preload`, die andere
  Subdomains von omarfourati.de mitbinden würden. Hinter Caddy: echte Client-IP = **letzter** Eintrag von
  `X-Forwarded-For`.
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
- `POST /api/auth/login {email,password}` → `{token, user: Me}`; 401 falsch, 429 gedrosselt (wie Redefluss: 20/IP, 5/E-Mail+IP je 15 min;
  dazu je Konto unabhängig von der IP: nach 10 Fehlversuchen einer E-Mail in 15 min 429 für jede Anmeldung dieser E-Mail –
  auch mit richtigem Passwort – bis der älteste Fehlversuch das Fenster verlässt; unbekannte E-Mails genauso, Security-Review M4).
- `GET /api/auth/me` → `Me {id,email,name,role,lang,practice:{id,name,isDemo,demoExpiresAt}|null}`
- `PATCH /api/auth/me {name?,lang?}` → Me · `POST /api/auth/password {current,next}` → `{token}`. Passwortregel (auch bei
  Einladung und Reset-Link): 10–200 Zeichen, nicht ein einziges wiederholtes Zeichen (`password_repeated`), keine reine
  Ziffern-/Alphabet-/Tastaturfolge vor- oder rückwärts wie `1234567890`, `azertyuiop`, `qwertyuiop` (`password_sequence`),
  nicht die eigene E-Mail oder ihr lokaler Teil ab 4 Zeichen (`password_contains_email`); jeweils 422.
- `POST /api/auth/logout-all` → 204 (token_version++)
- `POST /api/invitations/preview {token}` → `{practiceName, role, isDemo}` (404 ungültig/abgelaufen/benutzt)
- `POST /api/invitations/accept {token,name,email,password}` → 201 `{token,user}`; 409 E-Mail vergeben; 403
  `demo_invitation` für Einladungen einer Demo-Praxis (der Link darf zur Vorführung erzeugt werden, ein Konto entsteht
  nie; geprüft vor der E-Mail – Security-Review M2; die Seite `/invitation` zeigt dann einen Hinweis statt des
  Formulars). Beide zusammen: 5 Versuche je IP und 15 min, nur ein angenommenes Token setzt den Zähler zurück.

**Praxis & Team** (lesen: alle Rollen; ändern: owner)
- `GET /api/practice` → `{id,name,address,city,phone,dayStart:"08:00",dayEnd:"18:00",slotMinutes,defaultDurationMin,reminderTemplateFr,reminderTemplateAr,displayToken,isDemo}`
- `PATCH /api/practice {…}` · `POST /api/practice/display-token` → neues Token. In Demo-Praxen bleiben Name (FR/AR),
  Telefon, WhatsApp und Karten-Link fest (Änderung → 403 `demo_locked`, in den Réglages schreibgeschützt), und die
  öffentliche Buchungsseite einer Demo zeigt ein deutliches Demo-Banner plus `noindex` (Security-Review N3).
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
- `POST /api/demo {lang?}` → 201 `{token,user}`: neue Praxis „Cabinet Dentaire Démo“ (`is_demo`, läuft nach 24 h ab), Besitzer `demo-<zufall>@demo.daftar.invalid`, gefüllt mit erfundenen Daten relativ zu heute (25 Patienten mit tunesischen Namen, Telefon **`+21600000001…`** – die Vorwahl 00 existiert nicht; Termine −14…+7 Tage mit realistischen Status inkl. Nichterscheinen; heute 3 Wartende, 1 in Behandlung; Leistungen und Teilzahlungen; Termine morgen für Erinnerungen). Drosselung: 5 je IP und Stunde, 20 je Adressbereich (IPv4 /24, IPv6 /64) und Tag (Security-Review N8), 300 je Tag gesamt → 429. Aufräumjob alle 30 min löscht abgelaufene Demo-Praxen (CASCADE) und abgelaufene unbenutzte Einladungen älter als 30 Tage.
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
woff2 400/600/700), kein Inline-Script, kein externes Laden – außer Google AdSense auf `/` und `/ar/` (Omar, 30.10.:
Loader mit `ca-pub-4072840905222883`, Googles Einwilligungsfenster, Knopf „Paramètres de confidentialité“ /
„إعدادات الخصوصية“ in der Fußzeile über `landing/privacy-settings.js`, `Mediapartners-Google` in `robots.txt`). Seiten:
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
beschrieben, keine Cookies/kein Tracking in der App (seit 30.10.: Google AdSense mit Einwilligung nur auf den beiden
Startseiten, Abschnitt 4.2 „publicite“ der Rechtstexte), Pilot-Formular (Zweck, Rechtsgrundlage Art. 6 Abs. 1 lit. b/f
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

## 11. Erweiterung (Omar, 30.10. nachmittags): Kundenstamm, Online-Buchung, keine Doppelbuchungen

**Dieser Abschnitt hat Vorrang vor 1–10, wo sie sich widersprechen.** Online-Buchung ist damit kein Nicht-Ziel mehr.

### 11.1 Keine Doppelbuchungen (hart, in der Datenbank)
- `appointment` bekommt `ends_at TIMESTAMPTZ NOT NULL` (von der App aus `starts_at + duration_min` berechnet,
  `CHECK (ends_at > starts_at)`), damit ein Index-Ausdruck möglich ist (`timestamptz + interval` ist nicht IMMUTABLE).
- Zwei Ausschluss-Constraints (Extension `btree_gist`, ist „trusted“, darf der DB-Besitzer anlegen), jeweils
  `WHERE (status NOT IN ('cancelled','no_show'))`:
  `EXCLUDE USING gist (practice_id WITH =, (coalesce(practitioner_id, 0)) WITH =, tstzrange(starts_at, ends_at) WITH &&)`
  und dasselbe mit `patient_id` statt Behandler (ein Patient nie zweimal gleichzeitig).
- API: Überschneidung → **409** `{title, detail, conflicts:[{id,startsAt,endsAt,patientName}]}` statt Warnung
  (ersetzt „nur Warnung“ in Abschnitt 5). Die App zeigt dann freie Zeiten an. Notfälle laufen über die Warteschlange,
  nicht über den Kalender.
- **Hat die Praxis aktive Behandler, hat jeder Termin einen** (Code-Review H1, 31.10. – ein Termin „Non attribué“
  blockierte den Kalender der Ärztin nicht, Online-/Telefonbuchung legten denselben Zeitpunkt ein zweites Mal an).
  `practitionerId = null` beim Anlegen, Verschieben, Wiedereröffnen (storniert/absent → geplant), in Serien und im
  Import heißt: genau ein aktiver Behandler → dieser; mehrere → der erste (Reihenfolge der Praxis), der zur
  gewünschten Zeit frei ist (dieselbe Regel wie Online- und Telefonbuchung; eine Serie bekommt möglichst einen
  Behandler für alle Sitzungen); keiner frei → 409 mit Vorschlägen, in denen irgendeiner frei ist. Nur Praxen
  **ohne** aktive Behandler kennen weiter Termine ohne Behandler (ihr einer Kalender). Web: bei genau einem Behandler
  ist er vorgewählt und „Non attribué“ entfällt; bei mehreren ist „Premier disponible“ (sendet `null`) die Vorgabe.
  Migration `0006` ordnet bestehende nicht stornierte Termine ohne Behandler in Praxen mit genau einem aktiven
  Behandler diesem zu (Termine, die dort eine Überschneidung ergäben, bleiben ohne Behandler und zeigen sich in der
  Agenda; ältere Termine ohne Behandler in Praxen mit mehreren Behandlern bleiben, bis sie verschoben werden).
- `GET /api/availability?date=&durationMin=&practitionerId=` → `{date, slots:[{time:"09:15", practitionerIds:[…]}]}`:
  Raster `slot_minutes` innerhalb der Öffnungszeiten des Wochentags, ohne Schließtage, ohne belegte Zeiten, ohne
  Vergangenheit. Dieselbe Logik nutzt die Online-Buchung.

### 11.2 Kundenstamm („Business Customer“ = Praxis) mit vollständigen Daten
`practice` bekommt zusätzlich: `slug TEXT UNIQUE NOT NULL` (Subdomain, `^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$`,
reserviert: www, app, api, admin, demo, mail, smtp, static, assets, daftar, status, monitoring, test; Demo-Praxen
`demo-<8 Zeichen>`), `name_ar`, `contact_name` (verantwortliche Person), `whatsapp` (E.164), `email`, `postal_code`,
`governorate` (eins der 24 Gouvernorate), `maps_url`, `description_fr`, `description_ar`, `tax_id` (Matricule fiscal),
`status 'pilot'|'trial'|'active'|'suspended'` (Standard pilot), `pilot_until DATE`, `admin_notes` (nur Admin),
`weekly_hours JSONB` (ISO-Wochentag → Liste von Zeitfenstern, z. B. `{"1":[["08:00","12:30"],["14:00","18:00"]],…,"7":[]}`;
**ersetzt `day_start`/`day_end`** – Agenda-Bereich = früheste bis späteste Öffnungszeit), Online-Buchung:
`online_booking_enabled` (false), `online_auto_confirm` (false), `booking_horizon_days` (30),
`booking_min_notice_hours` (2), `booking_max_per_day` (20), `booking_block_no_shows` (2; 0 = aus).

Neue Tabellen:
- `practitioner(id, practice_id, name, title ('Dr.'), color, user_id NULL→app_user SET NULL, online_bookable BOOL true,
  active BOOL true, sort INT)` – Behandler sind **keine** Benutzerkonten (der Zahnarzt arbeitet oft nicht selbst in der
  Software). `appointment.practitioner_id` verweist hierauf (ON DELETE SET NULL); `/api/practitioners` liefert diese
  Tabelle (Abschnitt 5 entsprechend).
- `service(id, practice_id, name_fr, name_ar, duration_min, price_millimes NULL, online_bookable BOOL, color, active,
  sort)` – Leistungskatalog. Neue Praxen bekommen einen Standardkatalog (Consultation 30, Contrôle 20, Détartrage 45,
  Soin carie / composite 45, Extraction 30, Traitement de canal 60, Couronne – séance 60, Blanchiment 60,
  Urgence / douleur 30; Preise leer, online buchbar: Consultation, Contrôle, Détartrage). `appointment.service_id NULL`.
- `practice_closure(id, practice_id, starts_on DATE, ends_on DATE, label)` – Urlaub/Feiertage (keine Termine/Buchungen).

`appointment` zusätzlich: `service_id`, `source 'staff'|'online'`, Status **`requested`** (Online-Anfrage, blockiert
den Slot), `booking_token_hash TEXT UNIQUE NULL` (SHA-256 des Verwaltungslinks des Patienten), `patient_note`.

Admin-API (ersetzt die schmale Version in Abschnitt 5):
- `POST /api/admin/practices` mit vollständigen Daten `{name,nameAr?,slug,contactName,phone,whatsapp?,email?,address,
  postalCode?,city,governorate,mapsUrl?,taxId?,status,pilotUntil?,adminNotes?,weeklyHours,practitioners:[{name,title?}],
  services?:[…] (fehlt → Standardkatalog),onlineBooking:{enabled,autoConfirm,horizonDays,minNoticeHours,maxPerDay,
  blockNoShows}}` → 201 `{practice, invitation:{token,expiresAt}}` (Besitzer-Einladung)
- `GET /api/admin/practices/{id}` (alles) · `PATCH /api/admin/practices/{id}` (alles inkl. slug/status/adminNotes)
- `GET /api/admin/slug-available?slug=` → `{available, reason?}`
- Besitzer: `GET/PATCH /api/practice` (alle Felder außer slug, status, pilotUntil, adminNotes), CRUD
  `/api/practitioners`, `/api/services`, `/api/closures`.

App: `/app/admin/cabinets/nouveau` als Assistent in Schritten (1 Cabinet & contact · 2 Adresse & sous-domaine mit
Live-Prüfung · 3 Horaires · 4 Praticiens · 5 Actes & tarifs · 6 Réservation en ligne · Zusammenfassung → Einladungslink
+ Buchungslink kopieren), `/app/admin/cabinets/[id]` zum Bearbeiten. In `/app/reglages` pflegt der Besitzer dieselben
Daten (ohne Admin-Felder) plus Schließtage, Leistungen, Behandler und sieht seinen Buchungslink mit QR-Code.

### 11.3 Online-Buchung für Patienten
- Adresse: `https://<slug>.daftar.omarfourati.de` (Wildcard-DNS `*.daftar` → 212.132.95.145; Caddy On-Demand-TLS mit
  `ask` → `GET /api/public/tls-check?domain=<host>`: 200 nur für bestehende, nicht gesperrte Nicht-Demo-Praxis, sonst
  404) und immer auch `https://app.daftar.omarfourati.de/r/<slug>` (Tests, lokal, Fallback; auf der Hauptdomain 301
  dorthin).
- Host-Routing im Backend (Einstellung `BASE_DOMAIN`, Standard `daftar.omarfourati.de`): Host `<slug>.<BASE_DOMAIN>` →
  `/` und `/rdv` (sowie `/app…`, `/connexion`, `/invitation`, `/reinitialiser`) liefern die SPA (`200.html`),
  `/api/*`, `/_app/*`, Icons, Manifest normal, alles andere 302
  auf `https://<BASE_DOMAIN><pfad>`. Unbekannter Slug → 404-Seite. Die SPA-Route `/` (existiert nur für Subdomains;
  auf der Hauptdomain liefert der Server die Landing) liest den Slug aus `location.hostname`, sonst
  `location.replace('/')`. `/r/[slug]` zeigt dieselbe Buchungsseite, `/rdv#<token>` die Verwaltung des Patienten
  (auf der Praxis-Subdomain und auf `app.`; die Hauptdomain leitet `/rdv` per 301 auf `app.` um, das Fragment bleibt).
- Öffentliche API (ohne Login, nie Daten anderer Patienten):
  `GET /api/public/practices/{slug}` → Praxisprofil (Name FR/AR, Adresse, Gouvernorat, Telefon, WhatsApp, Karte,
  Beschreibung, Öffnungszeiten, `onlineBookingEnabled`, online buchbare Leistungen mit Dauer und ggf. Preis, online
  buchbare Behandler, `horizonDays`, `isDemo`) · `GET /api/public/practices/{slug}/slots?date=&serviceId=&practitionerId=` →
  `{date, slots:["09:00",…]}` · `POST /api/public/practices/{slug}/bookings {serviceId, practitionerId?, startsAt,
  firstName, lastName, phone, lang, reminderConsent, note?, website}` → 201 `{status:'requested'|'confirmed', startsAt,
  serviceName, practitionerName, manageToken}`. Geprüft wird **zuerst der Termin** (für alle gleich, wie `/slots`):
  422 `too_soon`/`outside_horizon`, 429 `day_full` (`booking_max_per_day`), 409 Slot weg. **Danach die Person** – jede
  dieser Ablehnungen gibt dieselbe Antwort 422 `booking_refused` „Merci d'appeler le cabinet pour prendre rendez-vous“
  (AR „يُرجى الاتصال بالعيادة لحجز موعد“), damit das Formular nicht verrät, ob eine Nummer Patient der Praxis ist
  (Security-Review M1): die Telefonnummer hat in der Praxis ≥ `booking_block_no_shows` Nichterscheinen, sie hat schon
  2 künftige Online-Buchungen, oder der wiedererkannte Patient hat zu dieser Zeit schon einen Termin. 429 (20
  Versuche/h je IP – Patienten hinter Mobilfunk-NAT teilen sich eine –, 3 Versuche/h je Telefonnummer und Praxis); die
  Buchungen einer Praxis laufen per `pg_advisory_xact_lock` nacheinander, damit parallele Anfragen die Grenzen nicht
  gemeinsam überspringen. Patient wird über Telefon **und** Nachname (ohne Groß/Klein) wiedererkannt, sonst neu
  angelegt.
  Verwaltung mit dem Token im Body (Fix-Liste 3; die Seite `/rdv#<token>` hält ihn aus Caddy- und App-Logs):
  `POST /api/public/bookings/lookup {token}` → Termin, Status, Praxis-Kontakt · `POST /api/public/bookings/cancel
  {token}` → storniert (bis `booking_min_notice_hours` vorher). Der Link, den die Buchungsbestätigung zeigt (auch zum
  Teilen per WhatsApp), lautet `https://<host der Buchung>/rdv#<token>`. Die Pfad-Varianten
  (`GET /api/public/bookings/{token}`, `POST /api/public/bookings/{token}/cancel`) und die Seite `/rdv/<token>` sind
  entfernt (Fix-Liste 2, 31.10.; es gab noch keine echte Buchung).
- Praxis-Seite: Online-Anfragen erscheinen im Dashboard („Nouvelles demandes en ligne“) und gestrichelt in der Agenda;
  Bestätigen (→ `confirmed`) oder Ablehnen (→ `cancelled`) mit fertigem WhatsApp-Text an den Patienten.
- Datenschutz: Die Rechtstexte erklären die Online-Buchung (Daten gehen an die Praxis als Verantwortliche, Daftar als
  Auftragsverarbeiter).

### 11.4 Abonnements der Praxen, Zahlung über Flouci
Daftar verwaltet die Abos selbst; Flouci kassiert nur die einzelne Rechnung (Flouci bietet nach unserem Stand
Einmalzahlungen per Zahlungslink, keine Abbuchung). Ohne Flouci-Schlüssel ist die Online-Zahlung ausgeschaltet und
Omar trägt Zahlungen (Virement, espèces) als Admin von Hand ein.
- `practice` statt `status`/`pilot_until`: `plan_code` (FK `plan`), `status 'pilot'|'trial'|'active'|'past_due'|
  'suspended'|'canceled'` (Standard pilot), `paid_until DATE` (Ende Pilot/bezahlter Zeitraum).
- `plan(code PK, name_fr, name_ar, price_millimes, period_months, active)`; Startwerte: `pilot` 0/1,
  `cabinet_mensuel` 49 000/1, `cabinet_annuel` 490 000/12 (Admin kann Preise ändern).
- `invoice(id, practice_id, number UNIQUE 'DAF-2026-0001', plan_code, period_start, period_end, amount_millimes,
  status 'open'|'paid'|'void', due_on, paid_at, method 'flouci'|'virement'|'especes'|'autre', provider_payment_id,
  created_at)`.
- Täglicher Job: für `active`-Praxen 10 Tage vor `paid_until` die nächste Rechnung anlegen; nach `paid_until` →
  `past_due`; 14 Tage danach → `suspended` (Anmeldung und Export gehen weiter, alle schreibenden Fach-Endpunkte
  antworten 402 problem+json „Abonnement suspendu“, Banner in der App). Bezahlt → `active`, `paid_until` = Ende der
  Rechnungsperiode. Pilot-Praxen bekommen keine Rechnungen, bis Omar den Plan umstellt. `canceled` (vom Admin
  gesetzt) wirkt wie `suspended`: Lesen, Anmeldung und Export gehen weiter, Schreiben → 402 `subscription_canceled`
  „Abonnement résilié“, Banner in der App (Security-Review N6).
- Besitzer: `GET /api/billing` → `{plan, status, paidUntil, plans, invoices, onlinePaymentAvailable}` ·
  `POST /api/billing/invoices/{id}/pay` → `{paymentUrl}` (Flouci-Zahlungslink, `developer_tracking_id` = Rechnungsnummer,
  Erfolg/Fehler zurück nach `/app/abonnement`) · `POST /api/billing/invoices/{id}/verify` → fragt Flouci nach dem Status.
  Webhook `POST /api/public/flouci/webhook` vertraut dem Body nie, sondern prüft immer per Flouci-Verify-API.
- Admin: `GET /api/admin/billing` (alle Praxen mit Plan, Status, bezahlt bis, offene Beträge), `PATCH` des Plans/Status
  über `/api/admin/practices/{id}`, `POST /api/admin/practices/{id}/invoices` (nächste Periode), 
  `POST /api/admin/invoices/{id}/mark-paid {method}`, `POST /api/admin/invoices/{id}/void`.
- Flouci-Anbindung als austauschbarer `PaymentProvider` (Fake in Tests); Schlüssel nur aus Umgebung
  (`FLOUCI_APP_TOKEN`, `FLOUCI_APP_SECRET`), nie geloggt. API-Details aus der offiziellen Flouci-Entwicklerdoku
  übernehmen, nicht raten.
- App: `/app/abonnement` (Besitzer: Plan, Status, Rechnungen, „Payer avec Flouci“), Admin-Übersicht „Abonnements“.

## 12. Alle Fachrichtungen, nicht nur Zahnärzte (Omar, 30.10.)

**Hat Vorrang vor allem davor.** Daftar ist die Terminverwaltung für **Arztpraxen aller Fachrichtungen** in Tunesien
(Allgemeinmedizin, Zahnmedizin, Kinderheilkunde, Gynäkologie, Dermatologie, Augenheilkunde, Kardiologie, HNO,
Physiotherapie/Kiné, Psychologie, …). Zahnärzte bleiben ein Beispiel, nicht die Zielgruppe allein.
- `practice.specialty` (Pflicht) ∈ `generaliste | dentiste | pediatre | gynecologue | dermatologue | ophtalmologue |
  cardiologue | orl | kinesitherapeute | psychologue | autre`; `practitioner.specialty` optional (Gemeinschaftspraxen).
- Standard-Leistungskatalog **je Fachrichtung** (Konstante im Code, FR + AR, Dauer, online buchbar ja/nein; Preise leer),
  z. B. Généraliste: Consultation 20, Contrôle 15, Certificat médical 10, Vaccination 15, Urgence 20; Pédiatre:
  Consultation 30, Suivi croissance 20, Vaccination 15; Kiné: Séance 45, Bilan 60; Psychologue: Séance 50, Premier
  entretien 60; Dentiste wie in 11.2; Ophtalmologue: Consultation 20, Mesure de la vue / réfraction 20, Fond d'œil 20,
  Tension oculaire 15, Adaptation lentilles 30; Gynécologue: Consultation 30, Suivi de grossesse 30, Échographie 20,
  Frottis 15; Dermatologue: Consultation 20, Contrôle 15, Petite chirurgie 30; Cardiologue: Consultation 30, ECG 15,
  Échographie cardiaque 30, Pose Holter 15; ORL: Consultation 20, Audiogramme 30, Lavage d'oreille 15;
  `autre`: Consultation 30, Contrôle 20.
- Feld `treatment.tooth` bleibt, die App zeigt es nur bei `dentiste` („Dent“).
- Texte neutral: „cabinet“, „praticien“, „patient“, „acte / consultation“ statt zahnspezifischer Begriffe; Manifest-Name
  „Daftar – agenda du cabinet médical“.
- Demo: `POST /api/demo {lang?, specialty?}` (Standard `generaliste`); `/app/demo` lässt vorher kurz wählen
  (Généraliste, Dentiste, Pédiatre, Kiné, Autre) und seedet passende Leistungen, Gründe und Namen.
- Admin-Assistent: Fachrichtung im ersten Schritt; der Katalog im Schritt „Actes & tarifs“ wird daraus vorbelegt.
- Landing: spricht alle Praxen an („médecins, dentistes, kinés, psychologues…“), Beispiele aus mehreren Fachrichtungen.

## 13. Eigene App je Praxis (Omar, 30.10.)

Jede Praxis bekommt **ihre eigene installierbare App** mit Voreinstellung – als PWA über ihre Subdomain (kein
Store, keine Warnmeldungen, sofortige Updates). Native Store-Apps je Praxis gibt es bewusst **nicht** (Apple
Guideline 4.2.6 lehnt Vorlagen-Apps ab, die nicht über das Konto der jeweiligen Praxis eingereicht werden; Google
wertet viele fast gleiche Apps als Spam). Später möglich: **eine** signierte Windows-App (Tauri), die sich über ihren
Dateinamen `Daftar-<slug>.exe` selbst auf die Praxis einstellt, und **eine** Daftar-App in Play Store/App Store
(Capacitor), Praxis per QR-Code/Code. Heute nur die PWA.
- **Ersetzt die Weiterleitung aus 11.3:** Auf `<slug>.<BASE_DOMAIN>` liefert der Server zusätzlich `/app/*`,
  `/connexion`, `/invitation`, `/reinitialiser` als SPA (statt 302). Anmeldung auf einer Praxis-Subdomain akzeptiert
  nur Benutzer dieser Praxis (sonst dieselbe 401-Meldung wie bei falschem Passwort); Admin und alle Praxis-Benutzer
  melden sich auf `app.<BASE_DOMAIN>` an, auf der Hauptdomain niemand (Fix-Liste 1). Die Login-Seite zeigt auf der
  Subdomain Name und Icon der Praxis. Manifest des App-Hosts: das statische `web/static/manifest.webmanifest`
  („Daftar“, `start_url` `/app`).
- **Manifeste je Host:** `GET /manifest.webmanifest` auf einer Praxis-Subdomain → `name` „<Praxisname> – Daftar“,
  `short_name` (Praxisname, max. 12 Zeichen), `start_url` `/app`, `scope` `/`, Icons der Praxis; `GET
  /booking.webmanifest` → „<Praxisname> – Rendez-vous“, `start_url` `/` (Patienten installieren die Buchungsseite).
  Hauptdomain behält das statische Manifest. Beide `no-cache`.
- **Icons je Praxis:** `GET /icons/practice-192.png`, `-512.png`, `-maskable-512.png` auf der Subdomain → serverseitig
  gerendert (Pillow): Initialen der Praxis (max. 2 Buchstaben, auch arabisch möglich → Latein-Initialen aus `name`) in
  Weiß auf `practice.brand_color` (neue Spalte, Standard `#0f766e`, Format `#rrggbb`), im Speicher gecacht bis zur
  nächsten Praxisänderung. Später Logo-Upload.
- **Installieren-Seite** `/app/installer` (auch in Réglages verlinkt): erkennt Gerät/Browser und zeigt den passenden
  Weg (Windows/Edge-Chrome „Installer“, Android-Chrome „Installer l'application“ bzw. `beforeinstallprompt`-Knopf,
  iPhone/iPad Safari „Partager → Sur l'écran d'accueil“), plus QR-Code des Praxis-Links für Handys im Team.

## 14. Import aus Excel/CSV mit eigenem Mapping (Omar, 30.10.)

Viele Praxen führen ihre Patienten (und manchmal Termine und offene Beträge) in Excel. Sie importieren das **selbst**
und legen die Zuordnung der Spalten **selbst in der Oberfläche** fest.
- Formate: `.xlsx` (openpyxl), `.xls` (xlrd), `.csv`/`.txt` (Trennzeichen `;` `,` Tab automatisch; Kodierung UTF-8
  mit/ohne BOM, sonst Windows-1256 bei arabischen Zeichen, sonst Windows-1252). Max. 2 MB, max. 20 000 Zeilen.
  Excel-Datumszahlen, `jj/mm/aaaa`, `aaaa-mm-jj`; Telefonnummern als Zahl (`20123456.0`, fehlende führende Null)
  werden repariert und normalisiert.
- Ablauf in der App `/app/import` (Besitzer und Assistenz): 1 Datei (Drag & Drop) → 2 Blatt + „erste Zeile =
  Überschriften“ → 3 **Zuordnung**: je Daftar-Feld ein Auswahlfeld mit den Spalten der Datei und Beispielwerten,
  automatisch vorgeschlagen anhand der Überschriften (FR/AR/EN: Nom, Prénom, Nom complet, Tél/Téléphone/GSM,
  Date de naissance, الاسم, اللقب, الهاتف …), Pflichtfelder markiert, Optionen (Namensaufteilung „Nom Prénom“ /
  „Prénom Nom“, Datumsformat, Standardsprache, Einwilligung Erinnerungen ja/nein, Umgang mit Dubletten
  überspringen/aktualisieren/neu anlegen) → 4 **Prüfung** (Probe ohne Speichern: Anzahl neu/aktualisiert/übersprungen,
  Tabelle der Fehler je Zeile und Feld, Dubletten mit vorhandenem Patienten) → 5 **Import** (eine Transaktion) →
  Ergebnis + Fehlerbericht als CSV + „Modèle enregistrer“ (Zuordnung für das nächste Mal speichern).
- Arten: **Patienten** (Felder lastName, firstName, fullName, phone, birthDate, birthYear, notes, alerts, lang,
  reminderConsent, openingBalance → Leistung „Reprise de solde“ mit diesem Betrag, externalRef → an notes angehängt)
  und **Termine** (date, time oder datetime, durationMin oder endTime, Patient über Name + Telefon – fehlt er, wird er
  angelegt –, service per Name, practitioner per Name, notes; vergangene Termine → `done`; Überschneidungen werden
  **nicht** importiert, sondern im Bericht gelistet).
- API: `POST /api/imports` (multipart `file`) → 201 `{id, filename, sheets, sheet, headerRow, columns:[{index, header,
  samples}], rowCount, suggestedMapping}` · `POST /api/imports/{id}/sheet {sheet, headerRow}` → dieselbe Form ·
  `POST /api/imports/{id}/preview {kind, mapping:{feld: spaltenIndex|null}, options}` → `{willCreate, willUpdate,
  willSkip, errors:[{row, field, message}], duplicates:[{row, patientId, name}], sample:[…10 normalisierte Zeilen]}` ·
  `POST /api/imports/{id}/commit {…}` → `{created, updated, skipped, errorCount}` · `GET /api/imports/{id}/report.csv` ·
  `GET/POST/DELETE /api/import-templates` (`{id, name, kind, mapping, options}`).
- Tabelle `import_job(id UUID, practice_id, created_by, filename, file_bytes BYTEA, created_at, expires_at,
  committed_at)` – die Datei wird beim Commit bzw. spätestens nach 24 h gelöscht (Aufräumjob); `import_template(id,
  practice_id, name, kind, mapping JSONB, options JSONB, created_at)`. Mandantentrennung wie überall.
- Schutz (Security-Review H1/H2): `.xlsx` je ZIP-Eintrag (u. a. `xl/sharedStrings.xml`, jedes Arbeitsblatt) höchstens
  5 MB entpackt, insgesamt höchstens 20 MB (422 `file_too_complex`); höchstens 3 offene (nicht übernommene)
  Import-Jobs je Praxis – ein neuer Upload löscht den ältesten; 10 Uploads je Benutzer und Stunde (429, auch
  fehlgeschlagene zählen); in Demo-Praxen kein Import (403 `demo_import_disabled`, die Importseite zeigt stattdessen
  einen Hinweis).
- Die Checkliste „Erste Schritte“ bekommt „Importer vos patients (Excel)“; Landing und Rechtstexte erwähnen den Import.

## 15. API-Verträge für die Backlog-Stories (Release 1)

Verbindlich für Backend **und** Web (werden parallel gebaut). Schema-Ergänzungen kommen, falls nicht schon in 0001,
als Migration 0002.
- `Me.practice` = `{id, name, slug, specialty, brandColor, status, isDemo, demoExpiresAt}`.
- **Passwort zurücksetzen** (A3): `POST /api/staff/{userId}/reset-link` (owner, nicht für sich selbst) und
  `POST /api/admin/practices/{id}/owner-reset-link` (admin) → 201 `{token, expiresAt}` (24 h, einmalig);
  öffentlich `POST /api/password-reset/preview {token}` → `{email, practiceName}` · `POST /api/password-reset/accept
  {token, password}` → `{token, user}` (token_version++). Seite `/reinitialiser#<token>`.
- **Serien** (B4): `POST /api/appointments/series/preview {patientId, startsAt, durationMin?, serviceId?, practitionerId?,
  reason, notes?, rule:{weekdays:[1..7], count:1..52}}` → `{occurrences:[{startsAt, endsAt, conflict:{id,startsAt,
  patientName}|null, closed:bool}]}` · `POST /api/appointments/series {…, skipConflicts:bool}` → 201 `{seriesId,
  created:[Appointment], skipped:[{startsAt, reason:'conflict'|'closed'}]}` (ohne skipConflicts und mit Konflikt → 409)
  · `POST /api/appointments/series/{seriesId}/cancel {from:'YYYY-MM-DD'}` → `{cancelled:n}`. `Appointment.seriesId`.
- **Vorschläge bei Konflikt** (B2): 409-Body enthält zusätzlich `suggestions:[startsAt…]` (bis 5 nächste freie Beginne
  gleicher Dauer und gleichen Behandlers in den nächsten 7 Tagen).
- **Tagesabschluss** (B5): `GET /api/appointments/overdue` → `[Appointment]` (heute, `scheduled|confirmed`, Ende vor
  mehr als 15 min).
- **Abzeichen** (C2): `GET /api/badges` → `{onlineRequests, overdue}` (leicht, App fragt alle 60 s).
- **Medizinischer Hinweis / gleiche Nummer** (E2/E3): `Patient.alerts` (Text, max. 500), `PatientSummary.hasAlerts`,
  `Patient.samePhone:[{id, firstName, lastName}]`, `Appointment.patient.alerts`, `QueueEntry.alerts` (nur intern).
- **Statistik** (H1, owner): `GET /api/stats?month=YYYY-MM` → `{month, appointments:{total, done, noShow, cancelled,
  online}, noShowRate, revenueMillimes, newPatients, topServices:[{name, count}], previous:{…gleiche Felder ohne
  previous…}}`.
- **Erste Schritte** (A5): `GET /api/onboarding` → `{steps:[{key, done}], dismissed}` mit `key ∈ hours, services,
  practitioners, team, booking, import, install, poster` (aus Daten abgeleitet; `install`/`poster` per
  `POST /api/onboarding/{key}/done`), `POST /api/onboarding/dismiss`; Spalte `practice.onboarding JSONB '{}'`.
- **Feedback** (J2): `POST /api/feedback {message ≤ 2000, page}` → 201 · `GET /api/admin/feedback` ·
  `DELETE /api/admin/feedback/{id}`; Zähler `daftar_feedback_total`.
- **Demo** (12): `POST /api/demo {lang?, specialty?}`. Die SPA wertet `?lang=ar|fr` auf `/app/demo` und `/connexion` aus.
## 16. Weitere Wünsche von Omar (30.10. abends)

**16.1 Termin am Telefon (Schnellmodus, Release 1).** Knopf „Rendez-vous par téléphone“ in der Kopfzeile (Taste `T`):
Telefonnummer zuerst (findet vorhandene Patienten, sonst neu), Leistung, dann sofort die **nächsten freien Zeiten**
(heute, morgen, später) als Liste – ein Klick bucht, danach WhatsApp-/SMS-Bestätigungstext zum Kopieren.
API: `GET /api/availability/next?serviceId=&practitionerId=&limit=8` → `[{startsAt, practitionerId}]` (über Tage
hinweg, max. 14 Tage, gleiche Regeln wie `/api/availability`).

**16.2 „Patient suivant“ – Ansicht für Empfang/Arzt (Release 1).** Regel: Ist der Patient des aktuellen bzw.
fälligen Termins (Beginn ≤ jetzt + 5 min) anwesend (Warteschlange `waiting`), ist er dran; ist er nicht da, ist
automatisch die **erste anwesende Person** der Warteschlange dran (nach Ticketnummer; früh gekommene Terminpatienten
zählen wie alle anderen). Terminpatienten, die 10 min nach Beginn nicht da sind, werden als „en retard“ markiert
(kein automatisches Nichterscheinen). API: `GET /api/queue/next?practitionerId=` → `{entry: QueueEntry|null,
reason: 'appointment'|'waiting_list', lateAppointments:[Appointment], upcoming:[QueueEntry] (nächste 3)}` ·
`POST /api/queue/call-next {practitionerId?}` → ruft genau diesen Eintrag auf (`called`, race-sicher) und gibt ihn
zurück. Web: `/app/salle/suivant` (große Anzeige „Maintenant / Ensuite“, Knopf „Appeler le suivant“); der
Wartezimmer-Bildschirm zeigt die aufgerufene Nummer.

**16.3 Kassenabschluss und Prüfung durch den Besitzer (Release 1).** `POST /api/cash/close {day, countedCashMillimes,
note?}` (Personal) → `{expectedCashMillimes, countedCashMillimes, differenceMillimes, closedBy, closedAt}`;
`POST /api/cash/{day}/verify` (owner) → `verifiedBy, verifiedAt`; `/api/cash?day=` liefert den Abschluss mit; das
Dashboard des Besitzers zeigt ungeprüfte Tage. Tabelle `cash_closing(practice_id, day, expected_cash_millimes,
counted_cash_millimes, note, closed_by, closed_at, verified_by, verified_at, PRIMARY KEY(practice_id, day))`.

**16.4 Rechnungen an Patienten mit Rabatt (Release 1.1).** „Note d'honoraires“ aus erfassten Leistungen, fortlaufend
je Praxis (`F-2026-0001`), Praxis-Kopf mit Matricule fiscal, druckbar. Rabatt (Betrag oder %) mit Pflichtangaben
„Grund“ und „genehmigt von Dr. …“ (Behandler), wer ihn eingetragen hat wird gespeichert; der Besitzer sieht alle Rabatte
in der Tagesübersicht. Zahlungen können sich auf eine Rechnung beziehen; Status offen/teilweise/bezahlt/storniert
(Storno nur owner). Steuerfelder konfigurierbar, Standard ohne MwSt (vor dem Einsatz mit einem Steuerberater klären).

**16.5 Patientenportal und Zahlung direkt an die Praxis (Release 2, Konzept).** Patienten melden sich per Einmal-Link
(von der Praxis per WhatsApp geschickt oder über den Buchungslink) an, sehen ihre Termine und Rechnungen und zahlen offene
Beträge mit **Flouci über das eigene Händlerkonto der Praxis** – das Geld geht von Flouci direkt auf das Konto (RIB) der
Praxis, Daftar hält nie Geld (deshalb keine Zahlungsdienst-Lizenz nötig). Jede Praxis eröffnet dafür selbst ein
Flouci-Händlerkonto (mit ihrer Matricule fiscal und ihrem RIB); ihre API-Schlüssel speichert Daftar verschlüsselt je
Praxis. Alternativ Barzahlung vor Ort; das Personal setzt die Rechnung auf bezahlt. Webhook nur mit Verify-API.
Daftars eigene Abo-Rechnungen (11.4) laufen getrennt über Omars Flouci-Konto.

- Reine Web-Seiten ohne neue API: `/app/agenda/imprimer?date=` (Druck), `/app/reglages/affiche` (A4-Plakat mit QR,
  QR lokal erzeugt, keine externen Dienste), `/app/installer`, `/app/import`, `/app/statistiques`, `/app/abonnement`.
