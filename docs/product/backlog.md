# Daftar – Product Backlog (PO)

Stand 30.10.2026. Grundlage: `docs/superpowers/specs/2026-10-30-daftar-design.md` (Abschnitte 1–13). Dieses Dokument
legt fest, **was in welche Version kommt** und **wann etwas fertig ist**. Bei Widerspruch zur Spezifikation gilt die
Spezifikation für das „Wie“, dieses Backlog für das „Was zuerst“.

## Produktziel

Eine tunesische Arztpraxis wirft ihr Terminheft weg, weil Daftar am Empfang schneller ist als Papier, weniger
Patienten nicht erscheinen, das Wartezimmer ruhiger ist und offene Beträge nicht mehr verloren gehen. Erfolg im
Pilot: 5 Praxen nutzen Daftar 4 Wochen lang täglich; Nichterscheinen sinkt messbar; jede Praxis sagt „ich würde
dafür zahlen“.

## Definition of Done (gilt für jede Story)

1. **TDD**: Test zuerst geschrieben und rot gesehen; Backend pytest gegen echtes Postgres, Web Vitest.
2. **E2E**: Jede Story hat mindestens einen Playwright-Test des Hauptwegs; läuft lokal gegen den Docker-Stack und in CI.
3. **Mandantentrennung**: Jeder neue Endpunkt hat einen Test „fremde Praxis → 404“ und einen Rollentest.
4. **FR + AR** vollständig (keine fehlenden Schlüssel), RTL geprüft; Zahlen westlich, Zeitzone Africa/Tunis.
5. **Geräte**: geprüft bei 390 px (Handy), 820 px (Tablet), 1440 px (Desktop); keine horizontale Scrollleiste.
6. **Barrierefreiheit**: axe-core im E2E-Test ohne „serious“/„critical“; Tastatur bedienbar; sichtbarer Fokus.
7. **Sicherheit**: keine Patientendaten in Logs/URLs/öffentlichen Seiten; Eingaben begrenzt; Rate-Limits bei
   öffentlichen Endpunkten; Fehler als problem+json ohne Interna.
8. **Leere, Lade- und Fehlerzustände** gestaltet (kein „undefined“, kein endloser Spinner, verständliche Meldung).
9. `npm run check`, alle Tests grün, Commit auf main, Deploy grün, Smoke-Test live.

## Release 1 – heute live (Pilot-fähig)

### Epic A – Kundenstamm & Zugang
- A1 **Admin legt Praxis mit vollständigen Daten an** (Assistent, Spec 11.2/12) → Einladungslink + Buchungslink.
  *AK*: Slug live geprüft (Format, reserviert, vergeben); Fachrichtung belegt Leistungskatalog vor; Pflichtfelder validiert.
- A2 **Einladung annehmen** (Besitzer, Mitarbeiter) – Einmal-Link 7 Tage.
- A3 **Passwort vergessen ohne E-Mail**: Besitzer erzeugt für Mitarbeiter, Admin für Besitzer einen
  **Zurücksetzen-Link** (Einmal-Link 24 h, nur Hash gespeichert, alle Sitzungen des Kontos werden ungültig).
  *AK*: Link zweimal benutzen → Fehler; abgelaufen → Fehler; fremde Praxis → 404.
- A4 **Eigene App je Praxis** (Spec 13) inkl. `/app/installer` und QR-Code.
- A5 **Erste Schritte** (Checkliste auf dem Dashboard, bis alles erledigt ist): Öffnungszeiten, Leistungen & Preise,
  Behandler, Team eingeladen, Online-Buchung aktiviert, App installiert, Plakat gedruckt. Abgeleitet aus Daten.

### Epic B – Termine ohne Doppelbuchung
- B1 **Agenda Tag/Woche**, Spalte je Behandler, Schließtage sichtbar, „Jetzt“-Linie.
- B2 **Termin in ≤ 10 s**: Klick auf freien Slot → Patient per Name/Telefon suchen oder neu → Leistung (setzt Dauer)
  → speichern. *AK*: Überschneidung → 409 und Vorschläge der nächsten freien Zeiten; Patient mit ≥ 2 Nichterscheinen
  → Hinweis „Acompte conseillé“.
- B3 **Status-Workflow** (requested → confirmed → arrived → in_treatment → done / no_show / cancelled) mit großen Knöpfen.
- B4 **Serientermine** (Kiné/Psy): „toutes les semaines / 2× par semaine, N séances“; jede Sitzung einzeln geprüft;
  Konflikte werden vor dem Speichern gelistet (überspringen oder abbrechen). Spalte `appointment.series_id`.
- B5 **Tagesabschluss**: Termine von heute, die noch `scheduled/confirmed` sind und deren Zeit vorbei ist, erscheinen als
  „Non venus ?“ mit einem Klick auf `no_show`.
- B6 **Agenda drucken** (Tagesliste, Druck-CSS) für Praxen, die Papier mögen.
- B7 **Globale Suche** im Kopf (Name/Telefon, Tastenkürzel `/`), Tastenkürzel `N` = neuer Termin.

### Epic C – Online-Buchung
- C1 Buchungsseite je Praxis (Spec 11.3), Verwaltungslink, Stornieren, Sperre bei Nichterscheinen.
- C2 **Anfragen-Zähler** in der Navigation (Abfrage alle 60 s), Bestätigen/Ablehnen mit WhatsApp-Text.
- C3 **Plakat/Aufsteller A4** (druckbar, FR+AR): „Prenez rendez-vous en ligne“ mit QR-Code der Buchungsseite.

### Epic D – Warteschlange
- D1 Tickets, Aufrufen, Wartezimmer-Bildschirm, Ticket-Seite des Patienten (Spec 5/6) – nie Namen öffentlich.

### Epic E – Patienten
- E1 Liste/Suche/Akte (Spec 6); Zuverlässigkeit (gekommen / nicht gekommen / storniert).
- E2 **Medizinischer Hinweis** (`patient.alerts`, z. B. Allergie, Antikoagulans) – rot oben in Akte, Termin-Dialog und
  Warteschlange. Nur für eingeloggte Praxis.
- E3 **Gleiche Telefonnummer**: Akte zeigt „Même numéro : …“ (Familien) mit Link.
- E4 Export (JSON) und Löschen (Besitzer, mit Bestätigung durch Eintippen des Namens).
- E5 **Import aus Excel/CSV mit eigener Spaltenzuordnung** (Spec 14): Patienten, Termine, Anfangssalden.
  *AK*: arabische CSV in Windows-1256 wird korrekt gelesen; Telefonnummer als Excel-Zahl wird repariert; Probe zeigt
  Fehler je Zeile ohne zu speichern; Dubletten-Regel wirkt; überschneidende Termine landen im Bericht statt in der
  Datenbank; Zuordnung als Modell speicherbar; Datei nach Commit/24 h gelöscht.

### Epic F – Geld
- F1 Leistungen/Behandlungsplan, Zahlungen in Raten, Saldo, Anzahlung je Termin, Quittung druckbar.
- F2 Tageskasse nach Zahlart, offene Beträge.

### Epic L – Neu am 30.10. abends (Spec 16)
- L1 **Termin am Telefon** in Sekunden mit nächsten freien Zeiten (16.1).
- L2 **„Patient suivant“** für Empfang/Arzt: wer ist jetzt dran, automatisch der nächste Anwesende, wenn der
  Terminpatient fehlt (16.2). *AK*: zwei gleichzeitige „Appeler le suivant“ rufen nie dieselbe Person doppelt auf.
- L3 **Kassenabschluss** mit Zählbetrag und Prüfung durch den Besitzer (16.3).

### Epic G – Erinnerungen
- G1 Morgen-Liste mit WhatsApp/SMS-Knopf, Einwilligung beachtet, „envoyé“ markieren.

### Epic H – Auswertung (Besitzer)
- H1 **Statistik** `/app/statistiques`: je Monat Termine, Nichterscheinen-Quote, Umsatz (Zahlungen), Anteil Online-
  Buchungen, Top-Leistungen; Vergleich zum Vormonat. Endpoint `GET /api/stats?month=YYYY-MM`.

### Epic I – Abos & Admin
- I1 Pläne, Rechnungen, „bezahlt bis“, Sperre (Spec 11.4); Flouci aus, bis Schlüssel da sind; manuelle Zahlung.
- I2 Admin-Übersicht: Praxen, Status, Nutzung (letzte Aktivität, Termine/Woche), Pilot-Anfragen, Feedback.

### Epic J – Vertrieb & Vertrauen
- J1 Landing FR/AR, Demo je Fachrichtung, Pilot-Formular, Rechtstexte, Muster-AVV.
- J2 **Feedback-Knopf** in der App („Une idée ? Un problème ?“) → `feedback(id, practice_id, user_id, message, page,
  created_at)`, Admin sieht es, Metrik `daftar_feedback_total` (Alarm-Mail).

### Epic K – Betrieb
- K1 Deploy, Monitoring (Probes, Alarme inkl. Pilot-Anfrage/Feedback), Metriken.
- K2 **Datensicherung** vor dem ersten echten Piloten: tägliches `pg_dump` der DB `daftar`, 14 Tage aufbewahrt,
  Wiederherstellung einmal getestet und im README beschrieben. (Kopie außerhalb des Servers: Release 1.1.)

## Release 1.1 – nächste Tage
- **Rechnungen an Patienten mit Rabatt** (genehmigt von Dr. …, Spec 16.4).
  - Dazu (Epic F, Security-Review 31.10. **N4**): **Audit-Log** für Löschen einer Leistung, Preissenkung und
    rückdatierte Zahlungen (wer, wann, alter/neuer Wert), für den Besitzer sichtbar; Löschen/Senken und Rückdatieren
    vor den letzten geprüften Kassentag nur durch den Besitzer. Heute darf jede Rolle das ohne Spur.
- **TOTP-Zwei-Faktor für den Admin** (Epic I, Security-Review 31.10. **M4**): das Admin-Konto öffnet über
  Besitzer-Reset-Links jede Praxis; zweiter Faktor (Authenticator-App) beim Admin-Login, Wiederherstellungscodes,
  optional Admin-Login nur von festen IPs. (Sperre je Konto und strengere Passwortregel sind seit Fix-Runde 3 live.)
- **Flyer** (Druck-PDF, FR/AR): Praxis Dr. Fadoua mit zwei QR-Codes (Website + Online-Termin); Daftar-Flyer für Ärzte.
- **Sonderöffnungszeiten** für Zeiträume (Ramadan, Sommer) + Vorschlagsliste fester tunesischer Feiertage.
- Änderungsprotokoll je Termin/Zahlung (wer, wann, was).
- Wartebereich: Warteliste „früherer Termin gewünscht“, automatischer Vorschlag bei Stornierung.
- **Backup-Kopie außerhalb des Servers** (Epic K, Security-Review 31.10. **N7**): täglich eine **verschlüsselte**
  Kopie (age/gpg, Schlüssel nicht auf dem VPS) auf einen Speicher außer Haus (z. B. Storage-Box mit eigenem
  Schreib-Account ohne Löschrecht); Wiederherstellungsübung regelmäßig. Heute liegen die Sicherungen unverschlüsselt
  nur auf demselben Server.
- Tutorial (FR/AR, Seite + PDF) und Werbevideo (Hoch- und Querformat) – Omars Wunsch, mit echten Screenshots.

## Release 2 – nach dem Pilot
- **Patientenportal** mit Rechnungen und Zahlung per Flouci direkt auf das Konto der Praxis (Spec 16.5).
- Aus der Konkurrenzanalyse (30.10., MAW3DI/Olycab/MedOrdo/med.tn): automatische Erinnerungen (Zusatzpaket),
  Konsultationsnotiz + Rezept/Attest (erst nach Rechtsprüfung), Telefon-Bestätigung bei Online-Buchung und Umbuchen
  durch den Patienten über seinen Link, Zahnschema, CNAM-Formulare – jeweils erst nach Rückfrage bei Pilotpraxen.
- **Hosting/Recht vor echten Patientendaten klären:** Datenübermittlung ins Ausland (Hosting in Deutschland) braucht
  nach tunesischem Recht evtl. eine INPDP-Genehmigung (Loi 2004-63, Art. 52 – unbestätigt) → Anwalt/INPDP fragen;
  Alternative: Produktivbetrieb bei einem Hoster in Tunesien.
- WhatsApp-Business-API/SMS-Gateway für automatische Erinnerungen; Web-Push für neue Online-Anfragen.
- Logo-Upload je Praxis; Flouci live (Händlerkonto); eine Windows-App (Tauri, signiert), eine Store-App (Capacitor).
  - **Vor** dem Aktivieren des Flouci-Händlerkontos (Epic I, Security-Review 31.10. **N5**): `pay`/`verify` rufen
    Flouci heute innerhalb der DB-Transaktion mit Zeilensperre auf (bis 15 s) – Provider außerhalb der Transaktion
    aufrufen, danach mit Sperre den Status erneut prüfen; Rate-Limit je Praxis.
- **Praxis-Website als Zusatzleistung** („site vitrine“): eigene Website je Praxis (FR/AR, SEO lokal, Öffnungszeiten
  und Leistungen live aus Daftar, Buchungsknopf), auf eigener Domain der Praxis. Prototyp: Cabinet Dr. Fadoua Bellaj
  Fourati (30.10.2026).
- Zwei-Faktor-Anmeldung, Sitzungsliste; Mehrere Standorte; Konsultationsnotizen (erst nach Rechtsprüfung).

## Bewusst nicht
- Patientennamen auf öffentlichen Seiten · Tracking/Cookies/Werbung in der App (Google AdSense nur auf `/` und `/ar/`) · Funktionen, die Werbung verspricht, aber nicht gibt ·
  echte Telefonnummern in der Demo · Selbstregistrierung ohne Admin, solange kein Gewerbe/AVV-Prozess steht.
