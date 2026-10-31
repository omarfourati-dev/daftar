# Daftar – Stock et hygiène (Material, Sterilisation, Wartung, Etiketten)

Stand 31.10.2026 · Quelle: Gespräch Omar ↔ Nisrine Hamza (Assistentin der Pilotpraxis, Zahnärztin Dr. Fadoua, Sfax).
Bindend zusammen mit `2026-10-30-daftar-design.md` (Rollen, Mandanten, Geld in Millimes, Africa/Tunis, FR/AR mit
RTL, Definition of Done aus `docs/product/backlog.md`).

## 1. Warum

Am Empfang wird heute neben dem Terminbuch ein **zweites Papierbuch** geführt: Wareneingänge mit Lieferant, Produkt,
Menge, Preis. Die Besitzerin sieht daraus weder ihre **Ausgaben** noch **wofür** das Material verbraucht wird. Dazu
kommen tägliche Pflichten der Assistenz, die heute nirgends stehen: **Etiketten für sterilisierte Instrumente**,
**Reinigung und Wartung der Geräte** (Autoklav, Absaugung, Wasserleitungen der Einheit …) und – in allgemeinmedizinischen
Praxen – **Etiketten für Blutentnahmen und Proben**.

Omar (PO): „Denk wie ein Arzt, beste UI/UX.“ Das heißt hier: in Sekunden am Handy erledigt, nichts doppelt tippen,
die Besitzerin sieht am Ende Zahlen, denen sie traut, und eine Kontrolle (Hygiene-Inspektion) findet lückenlose
Nachweise.

## 2. Ziele / Nicht-Ziele / Anti-Ziele

**Ziele**
1. Wareneingang in unter einer Minute am Handy erfassen; Verbrauch in **höchstens drei Tippern**.
2. Bestand je Produkt jederzeit sichtbar; „À commander“ und „Bientôt périmé“ von selbst.
3. Besitzerin: Ausgaben je Monat (je Lieferant/Kategorie) und Verbrauch je Behandlung (Acte) mit Materialkosten.
4. Sterilisationszyklen dokumentieren und Etiketten drucken; ein Paket lässt sich einem Patienten/Termin zuordnen
   (Rückverfolgbarkeit).
5. Wiederkehrende Hygiene-/Wartungsaufgaben mit Tagesliste „Hygiène du jour“ und Nachweis (wer, wann).
6. Probenetiketten aus Patientenakte oder Termin drucken.
7. Ein Etiketten-Druck für alles: Etikettendrucker (Rolle) **und** A4-Etikettenbögen für Praxen ohne Spezialdrucker.

**Nicht-Ziele (jetzt)**: Bestellungen direkt an Lieferanten senden, Buchhaltung/MwSt., Barcode-Scan per Kamera
(später, siehe 9), Laborbefunde/Labor-Schnittstellen, Gerätezulassung oder Normkonformitätszusagen.

**Anti-Ziele (Misserfolg, auch wenn es „funktioniert“)**
- Der Terminablauf am Empfang wird langsamer (keine Pflichtfelder für Material im Termin).
- Bestände, die niemand glaubt (Korrekturen ohne Spur, negative Bestände ohne Hinweis).
- Etiketten, die auf echten Druckern verrutschen oder unlesbar sind.
- Texte, die eine rechtliche Konformität versprechen (Daftar dokumentiert, es zertifiziert nicht).

## 3. Rollen

| Bereich | assistant | dentist | owner | admin |
|---|---|---|---|---|
| Produkte, Lieferanten anlegen/ändern | ✓ | – | ✓ | – |
| Wareneingang, Verbrauch, Inventur-Korrektur | ✓ | ✓ (Verbrauch) | ✓ | – |
| Preise sehen | ✓ (sie tippt sie von der Rechnung ab) | – | ✓ | – |
| Auswertung Ausgaben / Verbrauch je Acte | – | – | ✓ | – |
| Sterilisation, Hygiene-Aufgaben abhaken, Etiketten | ✓ | ✓ | ✓ | – |
| Geräte und Aufgabenpläne einrichten | ✓ | – | ✓ | – |
| Löschen von Eingängen/Zyklen | – | – | ✓ (mit Protokoll, siehe 8) | – |

Mandantentrennung wie überall: jede Zeile hat `practice_id`, fremde IDs → 404. Demo-Praxen dürfen alles ausprobieren.

## 4. Modul Stock (Material)

### 4.1 Daten
- **Lieferant** (`supplier`): Name, Telefon, WhatsApp, Notiz, aktiv.
- **Produkt** (`stock_product`): Name, Kategorie (Hygiène, Anesthésie, Restauration, Endodontie, Prothèse,
  Chirurgie, Prélèvements, Bureau, Autre – je Fachrichtung vorbelegt, frei änderbar), Einheit (pièce, boîte, flacon,
  carpule, paquet, ml …), Standard-Lieferant, Mindestbestand (Alarmschwelle), Notiz, aktiv. Optional EAN (für später).
- **Wareneingang** (`stock_receipt`): Datum, Lieferant, Lieferschein-/Rechnungsnummer, Notiz, erfasst von/um; Zeilen
  (`stock_receipt_line`): Produkt, Menge, Stückpreis in Millimes (optional), Charge/Lot (optional), Verfallsdatum
  (optional – Pflicht-Hinweis für Anästhetika u. ä. nicht erzwingen).
- **Bewegung** (`stock_movement`): eine Tabelle für alle Bestandsänderungen – `receipt` (+), `use` (−), `adjust`
  (± Inventur mit Grund), `waste` (− verfallen/beschädigt). Verbrauch optional mit `service_id` (Acte) und/oder
  `appointment_id`. Bestand = Summe der Bewegungen (keine gespeicherte Zahl, die auseinanderlaufen kann).
- Materialkosten eines Verbrauchs = Menge × gleitender Durchschnittspreis der Eingänge (FIFO ist für eine Praxis zu
  viel; Durchschnitt ist nachvollziehbar und stabil).

### 4.2 Bildschirme
- **Stock** (Navigation „Stock“): Liste der Produkte mit Bestand, Einheit, Ampel (ok / unter Mindestbestand /
  leer), Verfall in < 30 Tagen; Suche, Filter Kategorie; oben zwei große Knöpfe **„Réception“** und **„Sortie“**.
- **Réception** (Assistent, mobile-first): Lieferant wählen (oder neu), dann Zeilen: Produkt suchen (oder neu anlegen
  im selben Dialog), Menge (+/−), Preis, Lot/Verfall aufklappbar; Summe live; „Enregistrer“. Ein Eingang mit 5 Zeilen
  soll am Handy flüssig gehen.
- **Sortie / Utilisé** (3 Tipper): Produkt (zuletzt benutzte oben), Menge (Standard 1), optional „pour l’acte …“
  (Acte-Auswahl) → speichern. Zusätzlich im **Termin-Detail** ein freiwilliger Abschnitt „Matériel utilisé“ (verknüpft
  Termin und Acte automatisch) – nie Pflicht.
- **Inventaire**: Ist-Bestand zählen → Korrekturbewegung mit Grund.
- **Fournisseurs**: einfache Liste; Tippen auf Telefon/WhatsApp öffnet den Anruf/Chat.
- **„À commander“**: Liste aller Produkte unter Mindestbestand, gruppiert nach Lieferant, mit Knopf „WhatsApp au
  fournisseur“ (vorformulierter Text mit Produkten und Mengen, wie die Erinnerungen per `wa.me`).

### 4.3 Besitzerin – Auswertung (in **Statistiques**, owner-only)
- Ausgaben je Monat (Summe der Eingänge), aufgeteilt nach Lieferant und Kategorie; Vergleich Vormonat.
- Verbrauch je Acte: Anzahl Behandlungen, verbrauchtes Material und Materialkosten je Behandlung im Zeitraum;
  „Top-Material“ nach Kosten.
- Export CSV (wie die anderen Exporte) und Aufnahme der neuen Tabellen in den Daten-Export der Praxis.

### 4.4 Startliste je Fachrichtung
Wie die Standard-Leistungen: Knopf „Proposer une liste de départ“ legt typische Produkte und Kategorien an (Zahnarzt:
Gants, Masques, Carpules d’articaïne, Aiguilles, Composite, Coton, Pompes à salive, Gobelets, Sachets de
stérilisation, Désinfectant …; Allgemeinmedizin: Gants, Seringues, Aiguilles, Tubes EDTA/sec/citrate, Compresses,
Bandelettes …). Nie automatisch ohne Klick.

## 5. Modul Hygiène

### 5.1 Geräte und Aufgaben
- **Gerät** (`equipment`): Name, Art (autoclave, thermodésinfecteur, bac à ultrasons, compresseur, aspiration,
  fauteuil/unit, radiographie, autre), Seriennummer, Notiz, aktiv.
- **Aufgabe** (`hygiene_task`): Titel, Gerät (optional), Rhythmus (täglich, wöchentlich am Tag X, monatlich, jährlich,
  alle N Tage), Hinweis/Anleitung, aktiv. Vorlagen je Fachrichtung, z. B. Zahnarzt: täglich „Purge des conduits du
  fauteuil“, „Nettoyage aspiration“; wöchentlich „Test Bowie-Dick / Hélix autoclave“; jährlich „Maintenance
  autoclave“, „Contrôle radioprotection“.
- **Erledigung** (`hygiene_task_done`): Aufgabe, Fälligkeitstag, erledigt von/um, Notiz, Ergebnis ok/nicht ok.

### 5.2 Bildschirme
- **„Hygiène du jour“** als Karte auf **Aujourd’hui**: heute fällige Aufgaben als große Abhak-Zeilen, Überfälliges
  rot oben; Abzeichen in der Navigation wie bei den Online-Anfragen.
- **Hygiène** (Navigation): Reiter *Aujourd’hui · Stérilisation · Équipements · Historique*.
- **Historique**: lückenloser Nachweis (Filter Zeitraum/Gerät), druckbar als A4-Liste für eine Inspektion.

### 5.3 Sterilisation und Etiketten
- **Zyklus** (`sterilization_cycle`): Autoklav (Gerät), Datum/Uhrzeit, laufende Zyklusnummer je Gerät (automatisch,
  änderbar), Programm (z. B. 134 °C 18 min), Ergebnis (conforme / non conforme), Anzahl Pakete, durchgeführt von.
  „Non conforme“ → keine Etiketten, Hinweis „Recommencer le cycle“.
- **Paket** (`sterile_pack`): gehört zu einem Zyklus; Inhalt (Freitext oder Vorlage „Kit examen“, „Kit extraction“
  …), Verpackungsart → Haltbarkeit (Praxis-Einstellung, Standard 90 Tage), eindeutiger kurzer Code
  (z. B. `A3-0412-07` = Gerät-Zyklus-Paket), Verfallsdatum.
- **Etikett Sterilisation**: Praxisname, Inhalt, „Stérilisé le“, „À utiliser avant“, Code als Klartext **und** QR,
  Autoklav, Initialen der durchführenden Person.
- **Rückverfolgung**: im Termin-Detail „Traçabilité stérilisation“ → Code eintippen (Autovervollständigung der
  heutigen/gültigen Pakete) → Paket gilt als verwendet für Patient/Termin; abgelaufene Pakete werden abgelehnt mit
  klarem Hinweis. Suche „Wer bekam Paket X?“ / „Welche Pakete bekam Patient Y?“ für die Besitzerin.

## 6. Etiketten für Proben (Prélèvements)
- Aus **Patientenakte** und **Termin-Detail**: „Étiquettes de prélèvement“ → Röhrchen/Probenart wählen (Vorlagen:
  Sang EDTA, Sang tube sec, Citrate, Hépariné, Urine, Selles, Frottis, Autre), Anzahl je Art, Entnahmezeitpunkt
  (Standard jetzt), entnommen von.
- **Etikett**: Nachname VORNAME, Geburtsdatum (oder -jahr), Patienten-Nr., Probenart, Datum/Uhrzeit, Praxis, Code
  + QR (Proben-ID).
- Patient bekommt ein **optionales vollständiges Geburtsdatum** (`birth_date`); ist es gesetzt, ergibt sich das
  Geburtsjahr daraus. Labore brauchen das Datum; ohne steht das Jahr auf dem Etikett.
- Ein kleiner Nachweis (`specimen_label_log`: wer, wann, welche Arten, Anzahl) – keine Befunde.

## 7. Etiketten-Druck (gemeinsam)
- Druck über den Browser-Dialog (wie Quittung und Plakat), eigene Druck-Seite mit `@page`-Größe je Format.
- Formate (Praxis-Einstellung, je Etikettenart wählbar): **Rolle 62 mm** (Brother QL, Länge passend), **57 × 32 mm**
  (Dymo/Zebra-Rollen), **A4-Bogen 3 × 8 à 70 × 37 mm** (mit Startposition, damit angefangene Bögen weiter nutzbar
  sind). Vorschau in Originalgröße vor dem Drucken; Testseite „Imprimer un test“.
- Lesbarkeit: Mindestschrift 7 pt, Kontrast schwarz auf weiß, QR mit ausreichender Ruhezone; AR-Texte RTL, Codes immer
  LTR.

## 8. Querschnitt
- **Protokoll**: Löschen oder Korrigieren von Eingängen, Bewegungen und Zyklen nur Besitzerin bzw. als
  Gegenbuchung mit Grund; jede Änderung mit wer/wann/alt→neu (Grundstein für das Audit-Log aus dem Security-Review N4).
- **Aujourd’hui**: Karten „Hygiène du jour“ und „À commander (n)“; Abzeichen.
- **Navigation**: neue Punkte **Stock** und **Hygiène** (Seitenleiste; am Handy im Menü „Plus“), ohne die
  Hauptleiste zu überladen.
- **Demo**: Demo-Praxen bekommen Beispielprodukte, Eingänge, Verbrauch, Geräte, Aufgaben, einen Zyklus mit Paketen
  – damit Interessenten und das Werbevideo es zeigen können.
- **Daten-Export** der Praxis enthält alle neuen Tabellen.
- **i18n**: jeder Text FR und AR; Zahlen/Codes LTR.
- **Qualität**: TDD (pytest, Vitest), Playwright-E2E je Modul mit axe, keine horizontale Scrollleiste bei 360 px,
  Migrationen additiv und auf der Live-Datenbank sicher.

## 9. Später (Backlog, nicht jetzt)
Barcode/EAN per Kamera (BarcodeDetector, nur Android-Chrome), automatischer Verbrauch je Acte über Stücklisten,
Bestellungen per E-Mail/WhatsApp mit Bestätigung, Fotos von Lieferscheinen, Erinnerungen per WhatsApp an die
Assistenz.

## 10. Vom Builder zu entscheiden
Tabellen- und Spaltennamen im Detail, API-Pfade (Muster `/api/stock/...`, `/api/hygiene/...`, `/api/labels/...`),
Aufteilung der Svelte-Komponenten, genaue Etiketten-Layouts innerhalb der Regeln aus 7, Reihenfolge der Umsetzung
innerhalb der Phasen.

## 11. Phasen
1. **Stock** (4) inkl. Navigation, Aujourd’hui-Karte „À commander“, Auswertung, Demo, Export.
2. **Hygiène-Aufgaben** (5.1, 5.2) inkl. „Hygiène du jour“.
3. **Etiketten-Druck** (7) + **Sterilisation** (5.3) inkl. Rückverfolgung.
4. **Probenetiketten** (6) inkl. `birth_date`.
Jede Phase für sich testbar und deploybar.
