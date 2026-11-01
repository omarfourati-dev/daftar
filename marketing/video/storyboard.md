# Daftar – Werbevideo „Vorher → mit Daftar“: Storyboard

> Erzeugt aus `story.js` mit `node render.mjs --storyboard` – Änderungen bitte dort, nicht hier.
> Dauern hier geschätzt; die echten Dauern ergeben sich aus der Sprechdauer (Azure TTS) und stehen in `sprechtexte.md`.

**Ziel:** Sekretariat und Ärztin/Arzt einer Praxis in Tunesien (alle Fachrichtungen) erkennen ihre Alltagsprobleme
wieder und sehen zu jedem Problem, was Daftar konkret ändert – mit echten Screenshots der Demo-Praxis. Danach: Demo.

**Fassungen** (je FR und AR, mit Stimme: FR `fr-FR-DeniseNeural`, AR `ar-TN-ReemNeural` in tunesischem Derja)

| Fassung | Größe | Länge (geschätzt FR/AR) | Grenze | Für |
|---|---|---|---|---|
| vertikal | 1080 × 1920 | 1:01,2 / 0:57,9 | ≤ 60 s, < 16 MB | WhatsApp (Chat, Status), Reels |
| quer | 1920 × 1080 | 2:02,6 / 1:56 | etwa 90–120 s | YouTube, LinkedIn, E-Mail |

**Aufbau:** Aufhänger (Heft) → je Schmerzpunkt eine Szene in zwei Phasen: *vorher* (gezeichnete Szene, Etikett
„À l’accueil“ bzw. „Pour le médecin“) und *mit Daftar* (echte Aufnahmen, Etikett „Avec Daftar“, wichtige Stelle gelb
umrandet). Der Wechsel kommt genau dann, wenn die Stimme auf „Avec Daftar …“ wechselt. → Schluss mit QR-Code zu
https://daftar.omarfourati.de und Preis wie auf der Landing.

**Versprechen geprüft** gegen die Spezifikation und die Landing: Rappels öffnen WhatsApp/SMS mit fertigem Text (kein
automatischer Versand); Doppelbuchungen lehnt die Datenbank ab; Daten auf einem Server bei IONOS in Deutschland,
Verbindung HTTPS; Online-Buchung rund um die Uhr auf der Praxisseite; Kasse mit Tagesabschluss und offenen Beträgen.


## Vertikal 1080 × 1920 – ≈ 1:01,2 (FR)

| # | Zeit (FR, ≈) | Szene | Bild | Bildtext FR | Bildtext AR | Aufnahmen |
|---|---|---|---|---|---|---|
| 1 | 0:00–0:03,5 | cahier | Heftseite füllt sich Zeile für Zeile mit handschriftlichen Terminen. | **Votre cabinet tourne encore avec un cahier ?** | <span dir="rtl">**عيادتكم ما زالت تعمل بدفتر ورقي؟**</span> | gezeichnet |
| 2 | 0:03,5–0:12,4 | vorher → mit Daftar (Sekretariat) | Telefon klingelt, im Heft wird radiert und neu geschrieben | vorher: **Le téléphone sonne, le cahier déborde.**<br>mit Daftar: **Un clic, et jamais deux rendez-vous à la même heure.** | <span dir="rtl">قبل: **الهاتف يرنّ، والدفتر لم يعد يتّسع.**<br>مع دفتر: **نقرة واحدة، ولا موعدين في الوقت نفسه أبدًا.**</span> | `v02-agenda-mobile`<br>`t:20-agenda-conflit` (markiert) |
| 3 | 0:12,4–0:20,5 | vorher → mit Daftar (Sekretariat) | volles Wartezimmer, „C’est quand mon tour ?“, Streit um die Reihenfolge | vorher: **La salle déborde.**<br>mit Daftar: **Un ticket par patient, son tour sur son téléphone.** | <span dir="rtl">قبل: **القاعة ممتلئة.**<br>مع دفتر: **رقم لكل مريض، ودوره على هاتفه.**</span> | `v08-ticket-mobile`<br>`v07-ecran-tv` |
| 4 | 0:20,5–0:29,4 | vorher → mit Daftar (Sekretariat) | Liste mit Telefonnummern wird abtelefoniert, Uhr rast | vorher: **Les rappels ? Des heures au téléphone.**<br>mit Daftar: **Les rappels en un clic, les absences comptées.** | <span dir="rtl">قبل: **التذكيرات؟ ساعات على الهاتف.**<br>مع دفتر: **التذكير بنقرة، والتغيّب محسوب.**</span> | `v09-rappels-mobile`<br>`t:32-acompte-conseille` (markiert) |
| 5 | 0:29,4–0:38 | vorher → mit Daftar (Sekretariat) | Zettel mit Restbeträgen, Geld, Summe „= ?“ | vorher: **Des restes à payer sur des bouts de papier.**<br>mit Daftar: **Le reste calculé, la caisse du jour prête.** | <span dir="rtl">قبل: **مبالغ متبقّية على قصاصات ورق.**<br>مع دفتر: **المتبقّي محسوب، وصندوق اليوم جاهز.**</span> | `v13-dossier-mobile`<br>`t:36-cloture` (markiert) |
| 6 | 0:38–0:45,7 | vorher → mit Daftar (Ärztin/Arzt) | Uhr läuft, zwei Patienten stehen auf und gehen | vorher: **Trop d’attente, le patient va ailleurs.**<br>mit Daftar: **Vos patients réservent en ligne, à toute heure.** | <span dir="rtl">قبل: **انتظار طويل، فيذهب المريض إلى غيركم.**<br>مع دفتر: **مرضاكم يحجزون عبر الإنترنت، في أي ساعة.**</span> | `v04-reservation-mobile` |
| 7 | 0:45,7–0:53,4 | vorher → mit Daftar (Ärztin/Arzt) | Heft fällt, Seiten fliegen weg, leerer Umriss mit „?“ | vorher: **Et si le cahier se perd ?**<br>mit Daftar: **Tout est enregistré, sur chaque appareil.** | <span dir="rtl">قبل: **وإن ضاع الدفتر؟**<br>مع دفتر: **كل شيء محفوظ، على كل جهاز.**</span> | `v01-agenda-desktop`<br>`v12-aujourdhui-mobile` |
| 8 | 0:53,4–1:01,2 | cta | Abschluss auf Dunkel-Teal: Logo, Aufforderung, QR-Code zu https://daftar.omarfourati.de (wird beim Export gelesen und geprüft), Adresse groß, Preis-Hinweis. | **Essayez la démo**<br>Gratuite, sans inscription – un cabinet fictif prêt en quelques secondes.<br>daftar.omarfourati.de · Phase pilote gratuite – ensuite à partir de 29 DT par mois, sans engagement | <span dir="rtl">**جرّبوا دفتر الآن**<br>مجانًا ودون تسجيل – عيادة وهمية جاهزة في ثوانٍ.<br>daftar.omarfourati.de · المرحلة التجريبية مجانية – بعدها ابتداءً من 29 د.ت شهريًا، دون التزام</span> | QR-Code (erzeugt, geprüft) |

## Quer 1920 × 1080 – ≈ 2:02,6 (FR)

| # | Zeit (FR, ≈) | Szene | Bild | Bildtext FR | Bildtext AR | Aufnahmen |
|---|---|---|---|---|---|---|
| 1 | 0:00–0:05,6 | cahier | Heftseite füllt sich mit handschriftlichen Terminen, Text auf der Leseanfangsseite. | **Votre cabinet tourne encore avec un cahier ?**<br>Voici ce que Daftar change, à l’accueil et pour le médecin. | <span dir="rtl">**عيادتكم ما زالت تعمل بدفتر ورقي؟**<br>إليكم ما يغيّره دفتر، في الاستقبال وللطبيب.</span> | gezeichnet |
| 2 | 0:05,6–0:18,7 | vorher → mit Daftar (Sekretariat) | Telefon klingelt, im Heft wird radiert und neu geschrieben | vorher: **Le téléphone sonne sans arrêt.**<br>mit Daftar: **Au téléphone : le numéro, l’acte, un clic.** | <span dir="rtl">قبل: **الهاتف يرنّ دون توقّف.**<br>مع دفتر: **مكالمة؟ الرقم، الخدمة، ونقرة واحدة.**</span> | `v03-telephone-desktop` (markiert)<br>`v02-agenda-mobile` |
| 3 | 0:18,7–0:28,3 | vorher → mit Daftar (Sekretariat) | Doppelbuchung im Heft, roter Kreis | vorher: **Deux patients, la même heure.**<br>mit Daftar: **Un créneau déjà pris ? Daftar refuse.** | <span dir="rtl">قبل: **مريضان في الساعة نفسها.**<br>مع دفتر: **وقت محجوز؟ دفتر يرفض.**</span> | `v01-agenda-desktop`<br>`t:20-agenda-conflit` (markiert) |
| 4 | 0:28,3–0:39,9 | vorher → mit Daftar (Sekretariat) | volles Wartezimmer, „C’est quand mon tour ?“, Streit um die Reihenfolge | vorher: **La salle déborde.**<br>mit Daftar: **Un ticket pour chaque patient.** | <span dir="rtl">قبل: **القاعة ممتلئة.**<br>مع دفتر: **رقم تذكرة لكل مريض.**</span> | `v06-salle-desktop` (markiert)<br>`v07-ecran-tv` |
| 5 | 0:39,9–0:49,6 | vorher → mit Daftar (Sekretariat) | Liste mit Telefonnummern wird abtelefoniert, Uhr rast | vorher: **Les rappels ? Des heures au téléphone.**<br>mit Daftar: **Les rappels de demain, en un clic.** | <span dir="rtl">قبل: **التذكيرات؟ ساعات على الهاتف.**<br>مع دفتر: **تذكيرات الغد بنقرة واحدة.**</span> | `t:37-rappels` (markiert)<br>`v09-rappels-mobile` |
| 6 | 0:49,6–1:02,3 | vorher → mit Daftar (Sekretariat) | Zettel mit Restbeträgen, Geld, Summe „= ?“ | vorher: **Des restes à payer sur des bouts de papier.**<br>mit Daftar: **Chaque paiement enregistré, le reste calculé.** | <span dir="rtl">قبل: **مبالغ متبقّية على قصاصات ورق.**<br>مع دفتر: **كل دفعة مسجّلة، والمتبقّي محسوب.**</span> | `t:29-dossier-solde` (markiert)<br>`t:36-cloture` (markiert) |
| 7 | 1:02,3–1:04,9 | persona | Kurzer Wechsel auf Teal: Stethoskop-Symbol, Frage groß. | **Et pour le médecin ?** | <span dir="rtl">**وماذا عن الطبيب؟**</span> | gezeichnet |
| 8 | 1:04,9–1:15,3 | vorher → mit Daftar (Ärztin/Arzt) | Stempel „absent“ an drei Tagen, „reste 120 DT ?“ | vorher: **Un patient absent, un créneau perdu.**<br>mit Daftar: **Chaque absence est comptée.** | <span dir="rtl">قبل: **مريض غائب، موعد ضائع.**<br>مع دفتر: **يُحتسب كل تغيّب.**</span> | `t:32-acompte-conseille` (markiert)<br>`v13-dossier-mobile` (markiert) |
| 9 | 1:15,3–1:28,2 | vorher → mit Daftar (Ärztin/Arzt) | Kacheln „Encaissé / Montants dus / Absences“ mit roten Fragezeichen | vorher: **Combien encaissé ? Combien reste dû ?**<br>mit Daftar: **La caisse du jour et les montants dus.** | <span dir="rtl">قبل: **كم دُفع اليوم؟ وكم بقي؟**<br>مع دفتر: **صندوق اليوم والمبالغ المستحقّة.**</span> | `v11-caisse-desktop` (markiert)<br>`t:35-montants-dus` |
| 10 | 1:28,2–1:39,8 | vorher → mit Daftar (Ärztin/Arzt) | Uhr läuft, zwei Patienten stehen auf und gehen | vorher: **Trop d’attente, le patient va ailleurs.**<br>mit Daftar: **Réservation en ligne, à toute heure.** | <span dir="rtl">قبل: **انتظار طويل، فيذهب المريض إلى غيركم.**<br>مع دفتر: **حجز عبر الإنترنت، في أي ساعة.**</span> | `v04-reservation-mobile`<br>`v08-ticket-mobile` |
| 11 | 1:39,8–1:51,7 | vorher → mit Daftar (Ärztin/Arzt) | Heft fällt, Seiten fliegen weg, leerer Umriss mit „?“ | vorher: **Le cahier se perd, l’agenda avec.**<br>mit Daftar: **Vos données, enregistrées et protégées.** | <span dir="rtl">قبل: **يضيع الدفتر، وتضيع معه المواعيد.**<br>مع دفتر: **بياناتكم محفوظة ومحميّة.**</span> | `v01-agenda-desktop`<br>`v12-aujourdhui-mobile` |
| 12 | 1:51,7–2:02,6 | cta | Abschluss auf Dunkel-Teal: Logo, Aufforderung, QR-Code zu https://daftar.omarfourati.de (wird beim Export gelesen und geprüft), Adresse groß, Preis-Hinweis. | **Essayez la démo**<br>Gratuite, sans inscription – un cabinet fictif prêt en quelques secondes.<br>daftar.omarfourati.de · Phase pilote gratuite – ensuite à partir de 29 DT par mois, sans engagement | <span dir="rtl">**جرّبوا دفتر الآن**<br>مجانًا ودون تسجيل – عيادة وهمية جاهزة في ثوانٍ.<br>daftar.omarfourati.de · المرحلة التجريبية مجانية – بعدها ابتداءً من 29 د.ت شهريًا، دون التزام</span> | QR-Code (erzeugt, geprüft) |

## Screenshots

Video-Aufnahmen in `video/shots/<id>-<fr|ar>.png` (`capture.mjs`), dazu Aufnahmen aus dem Tutorial (`t:<id>` →
`tutorial/shots/<id>-<fr|ar>.png`), teils als Ausschnitt.

| id | Ansicht | Was zu sehen ist |
|---|---|---|
| `v01-agenda-desktop` | desktop | Agenda „Jour“ von heute, zwei Behandler-Spalten, viele Termine, Linie „Maintenant“ (wie 18-agenda-jour). |
| `v02-agenda-mobile` | mobile | Handy, Agenda von heute als Liste (wie 21-agenda-mobile). |
| `v03-telephone-desktop` | desktop | Ganzer Bildschirm mit offenem Fenster „Rendez-vous par téléphone“: Patient gefunden, „Prochains créneaux libres“ sichtbar. |
| `v04-reservation-mobile` | mobile | Handy, Buchungsseite: Acte, Tag und Uhrzeit gewählt (wie 44-reservation-choix). |
| `v05-demandes-desktop` | desktop | „Aujourd’hui“ mit „Nouvelles demandes en ligne“ (Confirmer / Refuser) im Bild. |
| `v06-salle-desktop` | desktop | Salle d’attente mit Tickets und Vorschau des Bildschirms (wie 23-salle). |
| `v07-ecran-tv` | tv | Bildschirm der Wartezone /salle/<token> (wie 27-ecran-salle). |
| `v08-ticket-mobile` | mobile | Handy des Patienten, Ticket-Seite (wie 28-ticket-patient). |
| `v09-rappels-mobile` | mobile | Handy, Rappels mit Knöpfen WhatsApp / SMS (wie 38-rappels-mobile). |
| `v11-caisse-desktop` | desktop | Caisse von heute (wie 34-caisse-jour). |
| `v12-aujourdhui-mobile` | mobile | Handy, „Aujourd’hui“ mit Kacheln (ohne geöffnetes Menü). |
| `v13-dossier-mobile` | mobile | Handy, Patientenakte (Patient mit Ratenzahlung), Reiter „Actes et paiements“, Solde mit „Reste à payer“ im Bild. |

## Export

```powershell
cd "C:\Users\ABUS Dev\daftar\marketing\video"
node render.mjs --check-voice      # Azure-Zugang prüfen
node render.mjs                    # alle Fassungen mit Stimme + Tutorial, mit Prüfung (out\*.pruefung.json)
node render.mjs --sprechtexte      # sprechtexte.md mit gemessenen Dauern
```

