# Daftar – Werbevideo: Storyboard

> Erzeugt aus `story.js` mit `node render.mjs --storyboard` – Änderungen bitte dort, nicht hier.

**Ziel:** Ärztinnen und Ärzte in Tunesien (alle Fachrichtungen) sehen in einer Minute, was Daftar am Empfang ändert,
und probieren die Demo aus. Versand per WhatsApp (Status, Chat) und E-Mail, dazu YouTube/LinkedIn.

**Fassungen**

| Fassung | Größe | Länge | Für |
|---|---|---|---|
| vertikal | 1080 × 1920 | 0:54.5 | WhatsApp-Status, Reels, Chat (bleibt unter 60 s) |
| quer | 1920 × 1080 | 1:31.5 | YouTube, LinkedIn, Link in der E-Mail |

Jede Fassung auf Französisch und Arabisch (Arabisch: ganzes Bild von rechts nach links, Namen in arabischer Schrift).

**Gestaltung:** ohne Sprecher und ohne Musik – alles steht als große Texttafel im Bild, weil die meisten das Video
stumm ansehen. Ruhige Bewegung: Texte und Geräte gleiten in 0,7–1 s ins Bild und stehen dann still; Szenen blenden
in 0,5 s über. Farben, Schrift (IBM Plex Sans Arabic) und Logo wie die Landing; das karierte Heft (Seyès, roter
Rand) ist das Motiv des Aufhängers. Am Ende QR-Code zu https://daftar.omarfourati.de (wird beim Export aus dem
fertigen Video gelesen und geprüft).

**Aufhänger:** das Papierheft der Praxis – Doppelbuchungen, volle Wartezone, Nichterscheinen und offene Beträge, die
im Rand verloren gehen → „Daftar remplace le cahier.“ → fünf bis sieben Funktionen mit echten Screenshots der
Demo-Praxis → Demo ausprobieren.


## Vertikal 1080 × 1920 – 0:54.5

| # | Zeit | Art | Bild | Text FR | Text AR | Screenshot |
|---|---|---|---|---|---|---|
| 1 | 0:00–0:04.5 | Aufhänger: Heft | Heftseite (Seyès-Lineatur, roter Rand) füllt sich Zeile für Zeile mit handschriftlichen Terminen. | **Votre agenda tient encore dans un cahier ?** | <span dir="rtl">**مواعيد عيادتكم ما زالت في دفتر ورقي؟**</span> | gezeichnet |
| 2 | 0:04.5–0:09 | Problem: Doppelbuchung | Gleiche Heftseite, Zeile 10:00 bekommt einen zweiten Namen; roter Kreis wird darum gezogen, rotes Ausrufezeichen. | **Deux patients, la même heure.**<br>Le cahier ne dit jamais non. | <span dir="rtl">**مريضان في الساعة نفسها.**<br>الدفتر الورقي لا يرفض أبدًا.</span> | gezeichnet |
| 3 | 0:09–0:13.5 | Problem: Wartezimmer | Gezeichnete Wartezone: Stuhlreihen füllen sich mit Silhouetten, Sprechblase „C’est quand mon tour ?“. | **La salle d’attente déborde.** | <span dir="rtl">**قاعة الانتظار ممتلئة.**</span> | gezeichnet |
| 4 | 0:13.5–0:18 | Problem: Nichterscheinen | Heftzeilen desselben Patienten an drei Tagen, nacheinander rote Stempel „absent“; am Rand „reste 120 DT ?“. | **Il ne vient pas. Encore.**<br>Et personne ne l’a noté. | <span dir="rtl">**لم يحضر. مرّة أخرى.**<br>ولم يسجّل ذلك أحد.</span> | gezeichnet |
| 5 | 0:18–0:21.5 | Wende: Daftar | Wechsel auf Teal: Logo (weiß) erscheint, Satz darunter. | **Daftar remplace le cahier.** | <span dir="rtl">**دفتر يعوّض الدفتر الورقي.**</span> | gezeichnet |
| 6 | 0:21.5–0:26 | Lösung | Handy mit der Agenda von heute fährt von unten ins Bild. | **Jamais deux rendez-vous à la même heure.**<br>Daftar refuse et propose les horaires libres. | <span dir="rtl">**لا موعدين في الوقت نفسه أبدًا.**<br>يرفض دفتر ذلك ويقترح الساعات الشاغرة.</span> | `v02-agenda-mobile-‹lang›.png` |
| 7 | 0:26–0:30.5 | Lösung | Handy mit der Buchungsseite der Praxis (Acte, Tag, freie Uhrzeit gewählt). | **Vos patients réservent en ligne, à toute heure.** | <span dir="rtl">**مرضاكم يحجزون عبر الإنترنت، في أي ساعة.**</span> | `v04-reservation-mobile-‹lang›.png` |
| 8 | 0:30.5–0:35 | Lösung | Handy des Patienten mit seiner Ticket-Seite (Nummer, Personen davor, Wartezeit). | **Un ticket pour chaque patient.**<br>L’accueil appelle le suivant d’un clic. | <span dir="rtl">**رقم لكل مريض.**<br>والاستقبال ينادي التالي بنقرة.</span> | `v08-ticket-mobile-‹lang›.png` |
| 9 | 0:35–0:39.5 | Lösung | Handy mit der Liste „Rappels“ und den Knöpfen WhatsApp / SMS. | **Les rappels de demain, en un clic.**<br>WhatsApp ou SMS, le texte est déjà écrit. | <span dir="rtl">**تذكيرات الغد بنقرة واحدة.**<br>واتساب أو رسالة قصيرة، والنص مكتوب.</span> | `v09-rappels-mobile-‹lang›.png` |
| 10 | 0:39.5–0:44 | Lösung | Handy mit der Patientenakte, Reiter „Actes et paiements“, Reste à payer. | **Paiements en plusieurs fois, rien ne se perd.**<br>Reste à payer calculé, reçu pour chaque paiement. | <span dir="rtl">**الدفع على أقساط دون أن يضيع شيء.**<br>المتبقّي يُحسب تلقائيًا، مع وصل لكل دفعة.</span> | `v13-dossier-mobile-‹lang›.png` |
| 11 | 0:44–0:47.5 | FR + AR | Zwei Handys nebeneinander: dieselbe Seite „Aujourd’hui“ einmal FR, einmal AR (RTL). | **En français et en arabe.**<br>Sur PC, tablette et téléphone. | <span dir="rtl">**بالعربية والفرنسية.**<br>على الحاسوب واللوحة والهاتف.</span> | `v12-aujourdhui-mobile-‹lang›.png`<br>`v12-aujourdhui-mobile-‹andere›.png` |
| 12 | 0:47.5–0:54.5 | Aufforderung | Abschluss auf Dunkel-Teal: Logo, Aufforderung, QR-Code zu https://daftar.omarfourati.de (wird beim Export gelesen und geprüft), Adresse groß, Preis-Hinweis. | **Essayez la démo**<br>Gratuite, sans inscription – un cabinet fictif prêt en quelques secondes.<br>daftar.omarfourati.de · Phase pilote gratuite – ensuite à partir de 49 DT par mois, sans engagement | <span dir="rtl">**جرّبوا دفتر الآن**<br>مجانًا ودون تسجيل – عيادة وهمية جاهزة في ثوانٍ.<br>daftar.omarfourati.de · المرحلة التجريبية مجانية – بعدها ابتداءً من 49 د.ت شهريًا، دون التزام</span> | QR-Code (erzeugt) |

## Quer 1920 × 1080 – 1:31.5

| # | Zeit | Art | Bild | Text FR | Text AR | Screenshot |
|---|---|---|---|---|---|---|
| 1 | 0:00–0:05.5 | Aufhänger: Heft | Heftseite füllt sich mit handschriftlichen Terminen, Text auf der Leseanfangsseite. | **Votre cabinet tourne encore avec un cahier ?**<br>Le téléphone sonne, la salle est pleine, le cahier déborde. | <span dir="rtl">**عيادتكم ما زالت تعمل بدفتر ورقي؟**<br>الهاتف يرنّ، والقاعة ممتلئة، والدفتر لم يعد يتّسع.</span> | gezeichnet |
| 2 | 0:05.5–0:11 | Problem: Doppelbuchung | Zeile 10:00 doppelt belegt, roter Kreis, Ausrufezeichen. | **Deux patients, la même heure.**<br>Le cahier ne dit jamais non. | <span dir="rtl">**مريضان في الساعة نفسها.**<br>الدفتر الورقي لا يرفض أبدًا.</span> | gezeichnet |
| 3 | 0:11–0:16.5 | Problem: Wartezimmer | Wartezone füllt sich, Sprechblase. | **La salle d’attente déborde.**<br>Chacun vient demander à l’accueil quand ce sera son tour. | <span dir="rtl">**قاعة الانتظار ممتلئة.**<br>والكل يسأل في الاستقبال: متى يأتي دوري؟</span> | gezeichnet |
| 4 | 0:16.5–0:22.5 | Problem: Nichterscheinen | Stempel „absent“ an drei Tagen, Randnotiz „reste 120 DT ?“. | **Absences et impayés se perdent dans la marge.**<br>Trois mois plus tard, plus personne ne sait ce qu’il reste à payer. | <span dir="rtl">**التغيّب والديون تضيع في الهامش.**<br>وبعد ثلاثة أشهر، لا أحد يعرف كم بقي للدفع.</span> | gezeichnet |
| 5 | 0:22.5–0:27.5 | Wende: Daftar | Teal, Logo (weiß), Satz und Aufzählung. | **Daftar remplace le cahier.**<br>Agenda, réservation en ligne, salle d’attente, dossiers et paiements – sur PC, tablette et téléphone. | <span dir="rtl">**دفتر يعوّض الدفتر الورقي.**<br>الأجندة، والحجز عبر الإنترنت، وقاعة الانتظار، والملفات والمدفوعات – على الحاسوب واللوحة والهاتف.</span> | gezeichnet |
| 6 | 0:27.5–0:34.5 | Lösung | Browserfenster mit der Agenda „Jour“ (zwei Behandler-Spalten). | **L’agenda du jour, une colonne par praticien.**<br>Jamais deux rendez-vous à la même heure : Daftar refuse et propose les horaires libres. | <span dir="rtl">**أجندة اليوم، عمود لكل طبيب.**<br>لا موعدين في الوقت نفسه أبدًا: يرفض دفتر ذلك ويقترح الساعات الشاغرة.</span> | `v01-agenda-desktop-‹lang›.png` |
| 7 | 0:34.5–0:41.5 | Lösung | Browserfenster mit „Rendez-vous par téléphone“ und den nächsten freien Zeiten. | **Un appel ? Le numéro, l’acte, un clic.**<br>Daftar propose les prochains créneaux libres et prépare le message de confirmation. | <span dir="rtl">**مكالمة؟ الرقم، الخدمة، ونقرة واحدة.**<br>يقترح دفتر أقرب الأوقات الفارغة ويُحضّر رسالة التأكيد.</span> | `v03-telephone-desktop-‹lang›.png` |
| 8 | 0:41.5–0:49 | Lösung | Hinten Browser mit „Nouvelles demandes en ligne“, vorne Handy mit der Buchungsseite. | **Vos patients réservent en ligne.**<br>Sur la page de votre cabinet, à toute heure. Vous confirmez d’un clic. | <span dir="rtl">**مرضاكم يحجزون عبر الإنترنت.**<br>على صفحة عيادتكم، في أي ساعة. وأنتم تؤكّدون بنقرة.</span> | `v05-demandes-desktop-‹lang›.png`<br>`v04-reservation-mobile-‹lang›.png` |
| 9 | 0:49–0:56.5 | Lösung | Hinten Browser mit der Salle d’attente, vorne Handy mit der Ticket-Seite. | **La salle d’attente, dans l’ordre.**<br>Chaque patient reçoit un ticket et suit son tour sur son téléphone. | <span dir="rtl">**قاعة انتظار منظَّمة.**<br>يحصل كل مريض على رقم ويتابع دوره على هاتفه.</span> | `v06-salle-desktop-‹lang›.png`<br>`v08-ticket-mobile-‹lang›.png` |
| 10 | 0:56.5–1:02.5 | Lösung | Fernseher mit dem Bildschirm der Wartezone (aufgerufene Nummer groß). | **L’écran de la salle : des numéros, jamais de noms.** | <span dir="rtl">**شاشة القاعة: أرقام فقط، دون أسماء.**</span> | `v07-ecran-tv-‹lang›.png` |
| 11 | 1:02.5–1:09.5 | Lösung | Handy mit „Rappels“. | **Les rappels de demain, en un clic.**<br>Le message est prêt dans la langue du patient : WhatsApp ou SMS s’ouvre avec le texte déjà écrit. | <span dir="rtl">**تذكيرات الغد بنقرة واحدة.**<br>الرسالة جاهزة بلغة المريض: يُفتح واتساب أو الرسائل القصيرة والنص مكتوب.</span> | `v09-rappels-mobile-‹lang›.png` |
| 12 | 1:09.5–1:16.5 | Lösung | Hinten Browser mit der Caisse du jour, vorne Handy mit der Patientenakte (Reste à payer). | **Paiements en plusieurs fois, sans rien oublier.**<br>Reste à payer calculé, reçu pour chaque paiement, caisse du jour. | <span dir="rtl">**الدفع على أقساط دون نسيان أي شيء.**<br>المتبقّي يُحسب تلقائيًا، مع وصل لكل دفعة وصندوق اليوم.</span> | `v11-caisse-desktop-‹lang›.png`<br>`v13-dossier-mobile-‹lang›.png` |
| 13 | 1:16.5–1:22.5 | FR + AR | Hinten Browser in der jeweils anderen Sprache, vorne Handy in der Sprache des Videos. | **En français et en arabe, sur tous vos appareils.**<br>Chaque membre de l’équipe a son accès et choisit sa langue. | <span dir="rtl">**بالعربية والفرنسية، على كل أجهزتكم.**<br>لكل فرد من الفريق حسابه، ويختار لغته.</span> | `v01-agenda-desktop-‹andere›.png`<br>`v12-aujourdhui-mobile-‹lang›.png` |
| 14 | 1:22.5–1:31.5 | Aufforderung | Abschluss auf Dunkel-Teal: Logo, Aufforderung, QR-Code zu https://daftar.omarfourati.de (wird beim Export gelesen und geprüft), Adresse groß, Preis-Hinweis. | **Essayez la démo**<br>Gratuite, sans inscription – un cabinet fictif prêt en quelques secondes.<br>daftar.omarfourati.de · Phase pilote gratuite – ensuite à partir de 49 DT par mois, sans engagement | <span dir="rtl">**جرّبوا دفتر الآن**<br>مجانًا ودون تسجيل – عيادة وهمية جاهزة في ثوانٍ.<br>daftar.omarfourati.de · المرحلة التجريبية مجانية – بعدها ابتداءً من 49 د.ت شهريًا، دون التزام</span> | QR-Code (erzeugt) |

## Screenshots für das Video

Ordner `video/shots/`, je Sprache eine Datei (`<id>-fr.png`, `<id>-ar.png`). Bis zur Aufnahme stehen dort beschriftete
Platzhalter. `capture.mjs` nimmt alle auf (Demo-Praxis, über die Landing gestartet).

| id | Ansicht | Was zu sehen sein muss |
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

## Nach dem Deploy: aufnehmen und exportieren

```powershell
cd "C:\Users\ABUS Dev\daftar\marketing\video"
# 1. Screenshots der Live-App (Demo-Praxis, FR und AR, Desktop und Handy) – ca. 5–10 Minuten
$env:BASE = "https://app.daftar.omarfourati.de"; node capture.mjs
#    nur einzelne Bilder wiederholen:  node capture.mjs --only 18-agenda-jour,v01-agenda-desktop --lang ar
# 2. Video: alle vier Fassungen (FR/AR × vertikal/quer) nach out\, mit Prüfung – ca. 25–35 Minuten
node render.mjs --strict
# 3. Tutorial-PDFs (FR und AR) – vorher die drei Fotos 04–06 vom Handy/PC in ..\tutorial\shots\ legen
cd ..\tutorial; node build.mjs --strict
```

Ergebnis: `video/out/daftar-vertical-fr.mp4`, `…-vertical-ar.mp4`, `…-horizontal-fr.mp4`, `…-horizontal-ar.mp4`
(H.264 High, 30 Bilder/s, MP4 mit `moov` vorne, ohne Tonspur) und `tutorial/tutorial-daftar-fr.pdf`, `…-ar.pdf`.
Vor dem Versand die Datei `*-letztes-bild.png` neben jedem Video ansehen (letztes Bild aus dem dekodierten Video, QR-Code
wird daraus gelesen) und `node render.mjs --stills` für je ein Standbild pro Szene (`out/stills/`).

Von Hand (Browser-Menüs kann Playwright nicht zeigen): `04-installer-android`, `05-installer-iphone`, `06-installer-pc`
– Zustand siehe Platzhalterbild bzw. `shared/shots.mjs`.

