# Daftar – Sprechtexte der Videos (FR / tunesisches Derja)

> Erzeugt mit `node render.mjs --sprechtexte` aus `story.js` (Werbevideo) und `tutoriel.js` (Tutorial) –
> Änderungen bitte dort, nicht hier.

**Zum Gegenlesen:** Das Arabische ist der Sprechtext in tunesischem Derja (arabische Schrift), so wie die Stimme ihn
spricht und wie er im Tutorial als Untertitel erscheint. Die Texte im Bild bleiben Hocharabisch (hier je Szene als
„Bild“ angegeben). Kurze Sätze, Zahlen ausgeschrieben; wo die Schrift von der Aussprache abweicht, steht die
gesprochene Form dahinter (SSML `<sub>`).

**Stimmen (Azure Neural TTS, `voice/tts.py`):** FR `fr-FR-DeniseNeural` · AR `ar-TN-ReemNeural` – je Sprache
durchgängig dieselbe Stimme, in Werbevideo und Tutorial.

**Dauern:** gemessene Längen der Azure-Aufnahmen (Stille am Anfang/Ende entfernt).
Die Szenendauer = Sprechdauer + Pausen (Anfang, zwischen den Sätzen, Ausklang).

## Übersicht

| Fassung | Tempo FR / AR | Dauer FR | Dauer AR | Ziel |
|---|---|---|---|---|
| Werbevideo hochkant 1080×1920 | +10% / +10% | 0:50,6 | 0:57,9 | ≤ 1:00, < 16 MB |
| Werbevideo quer 1920×1080 | +4% / +8% | 1:49,1 | 1:57,0 | etwa 1:30–2:00 |
| Tutorial 1920×1080 | +4% / +4% | 7:58,3 | 8:54,1 | etwa 8–10 min |

## 1. Werbevideo hochkant (1080 × 1920, WhatsApp)

### 1 · Aufhänger
FR 0:00,0–0:02,6 (2,6 s) · AR 0:00,0–0:03,2 (3,2 s)

Bild: „Votre cabinet tourne encore avec un cahier ?“ / „عيادتكم ما زالت تعمل بدفتر ورقي؟“

- **FR** (1,9 s): Votre cabinet tourne encore avec un cahier ?
- **Derja** (2,5 s): العيادة متاعكم مازالت تخدم بالكرّاس؟

### 2 · Vorher → mit Daftar: Telefon klingelt, Heft radieren (Sekretariat)
FR 0:02,6–0:09,7 (7,1 s) · AR 0:03,2–0:12,0 (8,8 s)

Bild vorher: „Le téléphone sonne, le cahier déborde.“ / „الهاتف يرنّ، والدفتر لم يعد يتّسع.“  
Bild mit Daftar: „Un clic, et jamais deux rendez-vous à la même heure.“ / „نقرة واحدة، ولا موعدين في الوقت نفسه أبدًا.“ – Aufnahmen: `v02-agenda-mobile`, `t:20-agenda-conflit`

- **FR vorher** (2,8 s): Ça sonne, on gomme, et deux patients à la même heure.
- **FR mit Daftar** (3,4 s): Avec Daftar : un clic, et jamais deux rendez-vous à la même heure.
- **Derja vorher** (3,3 s): التلفون يرنّ، تفسخ، وزوز مرضى في نفس الوقت.
- **Derja mit Daftar** (4,6 s): مع دفتر: كليك وحدة، وعمرك ما تلقى زوز مواعيد في نفس الوقت.

### 3 · Vorher → mit Daftar: volles Wartezimmer (Sekretariat)
FR 0:09,7–0:16,4 (6,7 s) · AR 0:12,0–0:19,2 (7,2 s)

Bild vorher: „La salle déborde.“ / „القاعة ممتلئة.“  
Bild mit Daftar: „Un ticket par patient, son tour sur son téléphone.“ / „رقم لكل مريض، ودوره على هاتفه.“ – Aufnahmen: `v08-ticket-mobile`, `v07-ecran-tv`

- **FR vorher** (2,0 s): La salle déborde : c’est quand mon tour ?
- **FR mit Daftar** (3,7 s): Avec Daftar, un ticket par patient, et son tour sur son téléphone.
- **Derja vorher** (2,3 s): الصالة معبّية: وقتاش دوري؟
- **Derja mit Daftar** (3,9 s): مع دفتر، كل مريض عندو تيكي، ويتبّع دورو من تلفونو.

### 4 · Vorher → mit Daftar: Erinnerungen am Telefon (Sekretariat)
FR 0:16,4–0:23,8 (7,4 s) · AR 0:19,2–0:27,8 (8,7 s)

Bild vorher: „Les rappels ? Des heures au téléphone.“ / „التذكيرات؟ ساعات على الهاتف.“  
Bild mit Daftar: „Les rappels en un clic, les absences comptées.“ / „التذكير بنقرة، والتغيّب محسوب.“ – Aufnahmen: `v09-rappels-mobile`, `t:32-acompte-conseille`

- **FR vorher** (2,9 s): Des heures de rappels au téléphone, et des absents quand même.
- **FR mit Daftar** (3,6 s): Avec Daftar, un clic par rappel, et chaque absence est comptée.
- **Derja vorher** (3,8 s): سوايع على التلفون للتذكير، ومع هذا فمّا اللي ما يجيش.
- **Derja mit Daftar** (3,9 s): مع دفتر، كليك لكل تذكير، وكل غياب يتحسب.

### 5 · Vorher → mit Daftar: Restbeträge auf Zetteln, Kasse von Hand (Sekretariat)
FR 0:23,8–0:30,7 (6,9 s) · AR 0:27,8–0:35,5 (7,7 s)

Bild vorher: „Des restes à payer sur des bouts de papier.“ / „مبالغ متبقّية على قصاصات ورق.“  
Bild mit Daftar: „Le reste calculé, la caisse du jour prête.“ / „المتبقّي محسوب، وصندوق اليوم جاهز.“ – Aufnahmen: `v13-dossier-mobile`, `t:36-cloture`

- **FR vorher** (1,8 s): Des restes à payer sur des bouts de papier ?
- **FR mit Daftar** (4,1 s): Avec Daftar, le reste se calcule tout seul, et la caisse du jour est prête.
- **Derja vorher** (2,3 s): فلوس باقية مكتوبة في وريقات؟
- **Derja mit Daftar** (4,4 s): مع دفتر، الباقي يتحسب وحدو، والكاسة متاع اليوم حاضرة.

### 6 · Vorher → mit Daftar: Patienten wechseln wegen Wartezeit (Ärztin/Arzt)
FR 0:30,7–0:36,9 (6,2 s) · AR 0:35,5–0:42,5 (7,0 s)

Bild vorher: „Trop d’attente, le patient va ailleurs.“ / „انتظار طويل، فيذهب المريض إلى غيركم.“  
Bild mit Daftar: „Vos patients réservent en ligne, à toute heure.“ / „مرضاكم يحجزون عبر الإنترنت، في أي ساعة.“ – Aufnahmen: `v04-reservation-mobile`

- **FR vorher** (2,1 s): Trop d’attente, et le patient va ailleurs.
- **FR mit Daftar** (3,2 s): Avec Daftar, vos patients réservent en ligne, à toute heure.
- **Derja vorher** (2,7 s): برشا انتظار، والمريض يمشي لغيرك.
- **Derja mit Daftar** (3,3 s): مع دفتر، المرضى يحجزو أونلاين، في أي وقت.

### 7 · Vorher → mit Daftar: Heft verloren (Ärztin/Arzt)
FR 0:36,9–0:43,2 (6,3 s) · AR 0:42,5–0:49,0 (6,5 s)

Bild vorher: „Et si le cahier se perd ?“ / „وإن ضاع الدفتر؟“  
Bild mit Daftar: „Tout est enregistré, sur chaque appareil.“ / „كل شيء محفوظ، على كل جهاز.“ – Aufnahmen: `v01-agenda-desktop`, `v12-aujourdhui-mobile`

- **FR vorher** (1,2 s): Et si le cahier se perd ?
- **FR mit Daftar** (4,1 s): Avec Daftar, tout est enregistré en Allemagne, et s’ouvre sur chaque appareil.
- **Derja vorher** (1,3 s): وكان الكرّاس ضاع؟
- **Derja mit Daftar** (4,3 s): مع دفتر، كل شي محفوظ في ألمانيا، ويتحلّ على أي جهاز.

### 8 · Schluss (QR, Preis)
FR 0:43,2–0:50,6 (7,5 s) · AR 0:49,0–0:57,9 (8,9 s)

Bild: „Essayez la démo“ / „جرّبوا دفتر الآن“

- **FR** (5,1 s): Essayez la démo gratuite. Phase pilote gratuite, puis dès vingt-neuf dinars par mois.
- **Derja** (6,5 s): جرّبو الديمو بلاش. الفترة التجريبية بلاش، ومن بعد من تسعة وعشرين دينار في الشهر.

## 2. Werbevideo quer (1920 × 1080)

### 1 · Aufhänger
FR 0:00,0–0:05,4 (5,4 s) · AR 0:00,0–0:05,8 (5,8 s)

Bild: „Votre cabinet tourne encore avec un cahier ?“ / „عيادتكم ما زالت تعمل بدفتر ورقي؟“

- **FR** (4,6 s): Votre cabinet tourne encore avec un cahier ? Voici ce que Daftar change.
- **Derja** (5,0 s): العيادة متاعكم مازالت تخدم بالكرّاس؟ هاو شنوّة يبدّل دفتر.

### 2 · Vorher → mit Daftar: Telefon klingelt, Heft radieren (Sekretariat)
FR 0:05,4–0:18,3 (12,9 s) · AR 0:05,8–0:20,0 (14,2 s)

Bild vorher: „Le téléphone sonne sans arrêt.“ / „الهاتف يرنّ دون توقّف.“  
Bild mit Daftar: „Au téléphone : le numéro, l’acte, un clic.“ / „مكالمة؟ الرقم، الخدمة، ونقرة واحدة.“ – Aufnahmen: `v03-telephone-desktop`, `v02-agenda-mobile`

- **FR vorher** (5,3 s): À l’accueil, le téléphone sonne sans arrêt. On cherche, on gomme, on réécrit.
- **FR mit Daftar** (6,3 s): Avec Daftar : le numéro, l’acte, et les créneaux libres s’affichent. Un clic, c’est noté.
- **Derja vorher** (6,0 s): في الاستقبال، التلفون ما يحبسش يرنّ. تلوّج، تفسخ، وتعاود تكتب.
- **Derja mit Daftar** (6,9 s): مع دفتر: النومرو، الخدمة، والأوقات الفارغة تطلعلك. كليك وحدة، ويتسجّل.

### 3 · Vorher → mit Daftar: Doppelbuchung (Sekretariat)
FR 0:18,3–0:26,7 (8,5 s) · AR 0:20,0–0:28,8 (8,8 s)

Bild vorher: „Deux patients, la même heure.“ / „مريضان في الساعة نفسها.“  
Bild mit Daftar: „Un créneau déjà pris ? Daftar refuse.“ / „وقت محجوز؟ دفتر يرفض.“ – Aufnahmen: `v01-agenda-desktop`, `t:20-agenda-conflit`

- **FR vorher** (2,2 s): Et parfois, deux patients à la même heure.
- **FR mit Daftar** (5,0 s): Avec Daftar, c’est impossible : Daftar refuse, et propose les horaires libres.
- **Derja vorher** (2,3 s): وساعات، زوز مرضى في نفس الوقت.
- **Derja mit Daftar** (5,2 s): مع دفتر، هذا ما يصيرش: دفتر يرفض، ويقترحلك الأوقات الفارغة.

### 4 · Vorher → mit Daftar: volles Wartezimmer (Sekretariat)
FR 0:26,7–0:36,7 (10,0 s) · AR 0:28,8–0:39,5 (10,7 s)

Bild vorher: „La salle déborde.“ / „القاعة ممتلئة.“  
Bild mit Daftar: „Un ticket pour chaque patient.“ / „رقم تذكرة لكل مريض.“ – Aufnahmen: `v06-salle-desktop`, `v07-ecran-tv`

- **FR vorher** (3,3 s): La salle est pleine, et chacun demande : c’est quand mon tour ?
- **FR mit Daftar** (5,5 s): Avec Daftar, chaque patient a un ticket. L’écran de la salle affiche les numéros appelés.
- **Derja vorher** (3,8 s): الصالة معبّية، وكل واحد يسأل: وقتاش دوري؟
- **Derja mit Daftar** (5,7 s): مع دفتر، كل مريض عندو تيكي. والشاشة في الصالة تورّي النومرو اللي جا دورو.

### 5 · Vorher → mit Daftar: Erinnerungen am Telefon (Sekretariat)
FR 0:36,7–0:45,4 (8,7 s) · AR 0:39,5–0:48,6 (9,1 s)

Bild vorher: „Les rappels ? Des heures au téléphone.“ / „التذكيرات؟ ساعات على الهاتف.“  
Bild mit Daftar: „Les rappels de demain, en un clic.“ / „تذكيرات الغد بنقرة واحدة.“ – Aufnahmen: `t:37-rappels`, `v09-rappels-mobile`

- **FR vorher** (2,7 s): La veille, des heures au téléphone pour les rappels.
- **FR mit Daftar** (4,7 s): Avec Daftar, un clic ouvre WhatsApp ou les SMS, avec le message déjà écrit.
- **Derja vorher** (2,8 s): العشيّة، سوايع على التلفون باش تفكّر المرضى.
- **Derja mit Daftar** (5,0 s): مع دفتر، كليك يحلّلك الواتساب ولا الإس إم إس، والميساج مكتوب.

### 6 · Vorher → mit Daftar: Restbeträge auf Zetteln, Kasse von Hand (Sekretariat)
FR 0:45,4–0:56,3 (11,0 s) · AR 0:48,6–0:59,7 (11,1 s)

Bild vorher: „Des restes à payer sur des bouts de papier.“ / „مبالغ متبقّية على قصاصات ورق.“  
Bild mit Daftar: „Chaque paiement enregistré, le reste calculé.“ / „كل دفعة مسجّلة، والمتبقّي محسوب.“ – Aufnahmen: `t:29-dossier-solde`, `t:36-cloture`

- **FR vorher** (3,8 s): Des restes à payer sur des bouts de papier, et le soir, la caisse à la main.
- **FR mit Daftar** (5,9 s): Avec Daftar, le reste à payer se calcule tout seul, et le soir, Daftar affiche l’écart de caisse.
- **Derja vorher** (4,8 s): فلوس باقية مكتوبة في وريقات، وفي العشيّة الكاسة تتحسب باليد.
- **Derja mit Daftar** (5,1 s): مع دفتر، الباقي يتحسب وحدو، وفي العشيّة دفتر يورّيك الفرق في الكاسة.

### 7 · Wechsel: Ärztin/Arzt
FR 0:56,3–0:58,2 (1,9 s) · AR 0:59,7–1:02,0 (2,3 s)

Bild: „Et pour le médecin ?“ / „وماذا عن الطبيب؟“

- **FR** (0,9 s): Et pour le médecin ?
- **Derja** (1,3 s): وبالنسبة للطبيب؟

### 8 · Vorher → mit Daftar: Nichterscheinen (Ärztin/Arzt)
FR 0:58,2–1:07,0 (8,8 s) · AR 1:02,0–1:11,4 (9,4 s)

Bild vorher: „Un patient absent, un créneau perdu.“ / „مريض غائب، موعد ضائع.“  
Bild mit Daftar: „Chaque absence est comptée.“ / „يُحتسب كل تغيّب.“ – Aufnahmen: `t:32-acompte-conseille`, `v13-dossier-mobile`

- **FR vorher** (2,5 s): Un patient qui ne vient pas, c’est un créneau perdu.
- **FR mit Daftar** (5,0 s): Avec Daftar, chaque absence est comptée, et après deux, Daftar conseille un acompte.
- **Derja vorher** (2,7 s): مريض ما جاش، معناها بلاصة ضايعة.
- **Derja mit Daftar** (5,4 s): مع دفتر، كل غياب يتحسب، وبعد زوز، دفتر ينصحك تطلب عربون.

### 9 · Vorher → mit Daftar: kein Überblick über Einnahmen/offene Beträge (Ärztin/Arzt)
FR 1:07,0–1:18,6 (11,5 s) · AR 1:11,4–1:24,8 (13,4 s)

Bild vorher: „Combien encaissé ? Combien reste dû ?“ / „كم دُفع اليوم؟ وكم بقي؟“  
Bild mit Daftar: „La caisse du jour et les montants dus.“ / „صندوق اليوم والمبالغ المستحقّة.“ – Aufnahmen: `v11-caisse-desktop`, `t:35-montants-dus`

- **FR vorher** (5,2 s): Combien encaissé aujourd’hui ? Combien reste dû ? Personne ne le sait vraiment.
- **FR mit Daftar** (5,1 s): Avec Daftar : la caisse du jour, par mode de paiement, et les montants dus, à tout moment.
- **Derja vorher** (6,2 s): قدّاش دخل اليوم؟ وقدّاش باقي على المرضى؟ حتى حد ما يعرف بالضبط.
- **Derja mit Daftar** (6,0 s): مع دفتر: الكاسة متاع اليوم حسب طريقة الخلاص، والفلوس اللي باقية، في أي وقت.

### 10 · Vorher → mit Daftar: Patienten wechseln wegen Wartezeit (Ärztin/Arzt)
FR 1:18,6–1:28,0 (9,4 s) · AR 1:24,8–1:34,3 (9,4 s)

Bild vorher: „Trop d’attente, le patient va ailleurs.“ / „انتظار طويل، فيذهب المريض إلى غيركم.“  
Bild mit Daftar: „Réservation en ligne, à toute heure.“ / „حجز عبر الإنترنت، في أي ساعة.“ – Aufnahmen: `v04-reservation-mobile`, `v08-ticket-mobile`

- **FR vorher** (3,1 s): Trop d’attente, et certains patients vont voir un autre médecin.
- **FR mit Daftar** (5,1 s): Avec Daftar, ils réservent en ligne, à toute heure, et suivent leur tour sur leur téléphone.
- **Derja vorher** (3,5 s): برشا انتظار، وفمّا مرضى يمشيو لطبيب آخر.
- **Derja mit Daftar** (4,7 s): مع دفتر، يحجزو أونلاين في أي وقت، ويتبّعو دورهم من التلفون.

### 11 · Vorher → mit Daftar: Heft verloren (Ärztin/Arzt)
FR 1:28,0–1:39,0 (11,0 s) · AR 1:34,3–1:45,6 (11,3 s)

Bild vorher: „Le cahier se perd, l’agenda avec.“ / „يضيع الدفتر، وتضيع معه المواعيد.“  
Bild mit Daftar: „Vos données, enregistrées et protégées.“ / „بياناتكم محفوظة ومحميّة.“ – Aufnahmen: `v01-agenda-desktop`, `v12-aujourdhui-mobile`

- **FR vorher** (3,6 s): Et si le cahier se perd ? Tous les rendez-vous disparaissent.
- **FR mit Daftar** (6,1 s): Avec Daftar, tout est enregistré en Allemagne, connexion chiffrée, sur PC, tablette et téléphone.
- **Derja vorher** (3,8 s): وكان الكرّاس ضاع؟ المواعيد الكل يمشيو معاه.
- **Derja mit Daftar** (6,3 s): مع دفتر، كل شي محفوظ في ألمانيا، والاتصال مشفّر، على البي سي والتابلات والتلفون.

### 12 · Schluss (QR, Preis)
FR 1:39,0–1:49,1 (10,1 s) · AR 1:45,6–1:57,0 (11,3 s)

Bild: „Essayez la démo“ / „جرّبوا دفتر الآن“

- **FR** (7,3 s): Essayez la démo gratuite sur daftar.omarfourati.de. Phase pilote gratuite, puis dès vingt-neuf dinars par mois. _(gesprochen: Essayez la démo gratuite sur daftar point omar fourati point dé e. Phase pilote gratuite, puis dès vingt-neuf dinars par mois.)_
- **Derja** (8,5 s): جرّبو الديمو بلاش: سكانيو الكود اللي على الشاشة. الفترة التجريبية بلاش، ومن بعد من تسعة وعشرين دينار في الشهر.

## 3. Tutorial-Gesamtvideo (1920 × 1080)

Untertitel = Sprechtext. Kapitel und Schritte wie im Tutorial-PDF; je Schritt der echte Screenshot.

### Intro (QR)
FR 0:00,0 (10,6 s) · AR 0:00,0 (12,5 s)

- **FR** (4,5 s): Bienvenue dans Daftar. Voici les gestes de tous les jours, pas à pas.
- **FR** (4,6 s): Pour essayer en même temps, ouvrez la démo gratuite sur daftar.omarfourati.de. _(gesprochen: Pour essayer en même temps, ouvrez la démo gratuite sur daftar point omar fourati point dé e.)_
- **Derja** (5,7 s): مرحبا بيكم في دفتر. هاو الخدمة متاع كل نهار، خطوة بخطوة.
- **Derja** (5,4 s): وباش تجرّبو في نفس الوقت، حلّو الديمو بلاش: سكانيو الكود اللي على الشاشة.

### Kapitel 0 – Avant de commencer · قبل البدء
FR 0:10,6 (7,7 s) · AR 0:12,5 (9,3 s)

- **FR** (6,6 s): Daftar s’ouvre dans le navigateur, sur PC, tablette ou téléphone. Chacun a son compte et sa langue.
- **Derja** (8,3 s): دفتر يتحلّ في المتصفّح، على البي سي، التابلات ولا التلفون. وكل واحد عندو الحساب متاعو واللغة متاعو.

#### 0.1 Le menu · القائمة
FR 0:18,3 (13,2 s) · AR 0:21,9 (15,0 s) · Bild `01-aujourdhui` (page)

- **FR** (7,4 s): Sur l’ordinateur, le menu est à gauche : Aujourd’hui, Agenda, Salle d’attente, Patients, Caisse, Rappels et Réglages.
- **FR** (4,5 s): En haut : la recherche d’un patient, le rendez-vous par téléphone, et la langue.
- **Derja** (9,5 s): على البي سي، القائمة على اليمين: اليوم، المواعيد، قاعة الانتظار، المرضى، الصندوق، التذكيرات، والإعدادات.
- **Derja** (4,1 s): الفوق: البحث على مريض، «موعد بالهاتف»، واللغة.

#### 0.2 Sur le téléphone · على الهاتف
FR 0:31,5 (9,8 s) · AR 0:36,8 (11,5 s) · Bild `02-menu-mobile` (mobile)

- **FR** (4,8 s): Sur le téléphone, le menu est en bas : Aujourd’hui, Agenda, Salle et Patients.
- **FR** (3,7 s): Le reste est sous Plus : la caisse, les rappels, les réglages.
- **Derja** (5,5 s): على التلفون، القائمة اللوطة: اليوم، المواعيد، القاعة، والمرضى.
- **Derja** (4,7 s): والباقي تحت «المزيد»: الصندوق، التذكيرات، والإعدادات.

### Kapitel 1 – Installer l’application · تثبيت التطبيق
FR 0:41,3 (4,6 s) · AR 0:48,4 (4,3 s)

- **FR** (3,5 s): Daftar s’installe comme une application, sans passer par un store.
- **Derja** (3,3 s): دفتر تثبّتوه كيف أي تطبيق، من غير ستور.

#### 1.1 Ouvrez l’adresse de votre cabinet · افتحوا عنوان عيادتكم
FR 0:45,8 (9,1 s) · AR 0:52,7 (10,2 s) · Bild `03-installer` (page)

- **FR** (2,7 s): Ouvrez l’adresse de votre cabinet, et connectez-vous.
- **FR** (5,0 s): La page Installer l’application montre les étapes pour votre appareil, et un QR code pour l’équipe.
- **Derja** (3,8 s): حلّو العنوان متاع العيادة، وادخلو للحساب متاعكم.
- **Derja** (5,1 s): صفحة «تثبيت التطبيق» تورّيكم الخطوات حسب الجهاز، وكود QR للفريق. _(gesprochen: صفحة «تثبيت التطبيق» تورّيكم الخطوات حسب الجهاز، وكود كيو آر للفريق.)_

#### 1.2 Android (Chrome) · أندرويد (Chrome)
FR 0:55,0 (7,6 s) · AR 1:02,9 (8,4 s) · Bild `03-installer` (page) mit Merkkarte

- **FR** (4,0 s): Sur Android, avec Chrome : touchez le menu, les trois points en haut.
- **FR** (2,3 s): Puis Installer l’application, et confirmez.
- **Derja** (4,6 s): على أندرويد، بكروم: انزلو على القائمة، النقاط الثلاثة الفوق.
- **Derja** (2,5 s): ومبعد «تثبيت التطبيق»، وأكّدو.

#### 1.3 iPhone et iPad (Safari) · آيفون وآيباد (Safari)
FR 1:02,6 (8,6 s) · AR 1:11,3 (10,6 s) · Bild `03-installer` (page) mit Merkkarte

- **FR** (4,7 s): Sur iPhone, avec Safari : touchez Partager, le carré avec une flèche.
- **FR** (2,5 s): Choisissez Sur l’écran d’accueil, puis Ajouter.
- **Derja** (5,4 s): على الآيفون، بسفاري: انزلو على «المشاركة»، المربّع اللي فيه فليشة.
- **Derja** (3,8 s): اختارو «إضافة إلى الشاشة الرئيسية»، ومبعد «إضافة».

#### 1.4 Ordinateur (Chrome ou Edge) · الحاسوب (Chrome أو Edge)
FR 1:11,2 (11,1 s) · AR 1:21,9 (10,1 s) · Bild `03-installer` (page) mit Merkkarte

- **FR** (5,5 s): Sur l’ordinateur, avec Chrome ou Edge : cliquez sur l’icône d’installation, dans la barre d’adresse.
- **FR** (4,2 s): Confirmez avec Installer. Daftar apparaît dans le menu Démarrer.
- **Derja** (5,0 s): على البي سي، بكروم ولا إيدج: انزلو على علامة التثبيت في بار العنوان.
- **Derja** (3,8 s): أكّدو بـ«تثبيت»، ودفتر يطلعلكم في قائمة «ابدأ».

### Kapitel 2 – Premiers pas · الخطوات الأولى
FR 1:22,2 (5,9 s) · AR 1:32,0 (6,5 s)

- **FR** (4,8 s): La carte Premiers pas liste les réglages du début. Chaque ligne se coche toute seule.
- **Derja** (5,4 s): بطاقة «الخطوات الأولى» فيها الإعدادات متاع البداية، وكل سطر يتشطّب وحدو.

#### 2.1 La liste des premiers pas · قائمة الخطوات الأولى
FR 1:28,1 (6,0 s) · AR 1:38,5 (8,1 s) · Bild `07-premiers-pas` (section)

- **FR** (2,7 s): Touchez une ligne pour aller directement au bon réglage.
- **FR** (2,0 s): Masquer cache la carte quand tout est prêt.
- **Derja** (3,4 s): انزلو على سطر، يهزّكم طول للإعداد المناسب.
- **Derja** (3,3 s): و«إخفاء» يخبّي البطاقة كي يكون كل شي حاضر.

#### 2.2 Horaires d’ouverture · أوقات العمل
FR 1:34,1 (10,5 s) · AR 1:46,5 (12,6 s) · Bild `08-horaires` (page)

- **FR** (6,2 s): Réglages, Horaires : pour chaque jour, indiquez les plages. Une pause, ce sont deux plages.
- **FR** (3,0 s): Copier sur les autres jours, puis Enregistrer les horaires.
- **Derja** (7,7 s): «الإعدادات»، «المواعيد والإغلاق»: لكل نهار، حطّو الأوقات. وكان فمّا استراحة، فترتين.
- **Derja** (3,6 s): «نسخ إلى بقية الأيام»، ومبعد «حفظ المواعيد».

#### 2.3 Congés et jours fériés · العطل والأعياد
FR 1:44,6 (9,7 s) · AR 1:59,2 (10,9 s) · Bild `09-fermetures` (section)

- **FR** (5,2 s): Sous Fermetures exceptionnelles, choisissez Du, Au et le Motif, puis Ajouter la fermeture.
- **FR** (3,2 s): Ces jours-là, ni rendez-vous, ni réservation en ligne.
- **Derja** (6,6 s): تحت «أيام الإغلاق الاستثنائي»، اختارو «من»، «إلى»، و«السبب»، ومبعد «إضافة الإغلاق».
- **Derja** (2,9 s): في النهارات هاذي، لا مواعيد ولا حجز أونلاين.

#### 2.4 Actes et tarifs · الخدمات والأسعار
FR 1:54,3 (9,6 s) · AR 2:10,1 (11,1 s) · Bild `10-actes` (page)

- **FR** (6,2 s): Actes et tarifs : le catalogue est déjà rempli. Pour chaque acte : durée, prix, et En ligne.
- **FR** (2,0 s): Nouvel acte, pour en ajouter un.
- **Derja** (7,4 s): «الخدمات والأسعار»: القائمة حاضرة. لكل خدمة: المدّة، السوم، و«عبر الإنترنت».
- **Derja** (2,4 s): و«خدمة جديدة» باش تزيدو وحدة.

#### 2.5 Praticiens · الأطباء والمعالجون
FR 2:03,9 (6,4 s) · AR 2:21,2 (8,0 s) · Bild `11-praticiens` (page)

- **FR** (3,2 s): Praticiens : chacun a sa colonne et sa couleur dans l’agenda.
- **FR** (1,9 s): Un praticien n’a pas besoin de compte.
- **Derja** (4,7 s): «الأطباء والمعالجون»: كل واحد عندو العمود واللون متاعو في الأجندة.
- **Derja** (1,9 s): والطبيب ما يلزموش حساب.

#### 2.6 Inviter l’équipe · دعوة الفريق
FR 2:10,3 (9,5 s) · AR 2:29,1 (11,1 s) · Bild `12-equipe-invitation` (section)

- **FR** (4,5 s): Équipe, puis Inviter quelqu’un : choisissez le rôle, puis Créer le lien d’invitation.
- **FR** (3,7 s): Envoyez le lien par WhatsApp. Il est valable sept jours.
- **Derja** (5,5 s): «الفريق»، ومبعد «دعوة شخص»: اختارو الدور، ومبعد «إنشاء رابط الدعوة».
- **Derja** (4,3 s): ابعثو الرابط بالواتساب. يقعد صالح سبعة أيام.

#### 2.7 Réservation en ligne · الحجز عبر الإنترنت
FR 2:19,8 (10,2 s) · AR 2:40,2 (11,6 s) · Bild `13-reservation-reglages` (page)

- **FR** (4,2 s): Cochez Réservation en ligne activée, choisissez vos règles, puis Enregistrer.
- **FR** (4,6 s): En haut : l’adresse de votre page de réservation, à partager, et son QR code.
- **Derja** (5,2 s): علّمو «الحجز عبر الإنترنت مفعّل»، اختارو القواعد، ومبعد «حفظ».
- **Derja** (5,1 s): الفوق: عنوان صفحة الحجز متاعكم باش تبعثوه، والكود QR متاعها. _(gesprochen: الفوق: عنوان صفحة الحجز متاعكم باش تبعثوه، والكود كيو آر متاعها.)_

#### 2.8 L’affiche pour la salle d’attente · ملصق قاعة الانتظار
FR 2:30,0 (10,4 s) · AR 2:51,9 (12,9 s) · Bild `14-affiche` (page)

- **FR** (4,7 s): Imprimer l’affiche A4 prépare une affiche bilingue, avec le QR code de votre page.
- **FR** (4,4 s): Dans la fenêtre d’impression : A4, marges Aucune, et graphiques d’arrière-plan.
- **Derja** (6,2 s): «طباعة ملصق A4» يحضّرلكم ملصق بالعربي وبالفرنسي، فيه الكود QR متاع الصفحة. _(gesprochen: «طباعة ملصق آ كاتر» يحضّرلكم ملصق بالعربي وبالفرنسي، فيه الكود كيو آر متاع الصفحة.)_
- **Derja** (5,3 s): في نافذة الطباعة: A4، الهوامش «بدون»، وفعّلو «رسومات الخلفية». _(gesprochen: في نافذة الطباعة: آ كاتر، الهوامش «بدون»، وفعّلو «رسومات الخلفية».)_

### Kapitel 3 – Prendre un rendez-vous · تسجيل موعد
FR 2:40,4 (6,1 s) · AR 3:04,7 (7,5 s)

- **FR** (5,1 s): Deux façons : au téléphone, ou dans l’agenda. Et jamais deux rendez-vous en même temps.
- **Derja** (6,5 s): فمّا طريقتين: بالتلفون، ولا في الأجندة. وعمرو ما يحطّ زوز مواعيد في نفس الوقت.

#### 3.1 Au téléphone : le numéro d’abord · بالهاتف: الرقم أولًا
FR 2:46,5 (8,5 s) · AR 3:12,3 (10,5 s) · Bild `15-telephone-numero` (dialog)

- **FR** (4,0 s): Touchez Rendez-vous par téléphone, ou la touche T. Tapez le numéro de l’appelant.
- **FR** (3,1 s): Choisissez le bon patient, ou Nouveau patient avec ce numéro.
- **Derja** (5,4 s): انزلو على «موعد بالهاتف»، ولا على حرف T. واكتبو نومرو اللي يكلّم. _(gesprochen: انزلو على «موعد بالهاتف»، ولا على حرف تي. واكتبو نومرو اللي يكلّم.)_
- **Derja** (3,7 s): اختارو المريض الصحيح، ولا «مريض جديد بهذا الرقم».

#### 3.2 L’acte, puis un créneau libre · الخدمة، ثم وقت فارغ
FR 2:55,1 (8,0 s) · AR 3:22,7 (8,8 s) · Bild `16-telephone-creneaux` (dialog)

- **FR** (2,8 s): Choisissez l’acte et, si besoin, le praticien.
- **FR** (3,9 s): À droite, les prochains créneaux libres : un clic réserve le rendez-vous.
- **Derja** (2,5 s): اختارو الخدمة، والطبيب كان لزم.
- **Derja** (4,9 s): وبجنبها، أقرب الأوقات الفارغة: كليك وحدة ويتحجز الموعد.

#### 3.3 Le message de confirmation · رسالة التأكيد
FR 3:03,1 (7,8 s) · AR 3:31,5 (7,8 s) · Bild `17-telephone-confirme` (dialog)

- **FR** (3,7 s): Le rendez-vous est enregistré, et le message de confirmation est prêt.
- **FR** (2,8 s): Copiez-le, ou envoyez-le par WhatsApp ou SMS.
- **Derja** (3,0 s): الموعد تسجّل، ورسالة التأكيد حاضرة.
- **Derja** (3,5 s): انسخوها، ولا ابعثوها بالواتساب ولا بالإس إم إس.

#### 3.4 L’agenda · الأجندة
FR 3:10,9 (9,0 s) · AR 3:39,3 (9,5 s) · Bild `18-agenda-jour` (page)

- **FR** (3,3 s): L’agenda : Jour ou Semaine, et une colonne par praticien.
- **FR** (4,3 s): La couleur montre le statut. Les demandes en ligne sont en pointillés.
- **Derja** (4,0 s): الأجندة: «يوم» ولا «أسبوع»، وعمود لكل طبيب.
- **Derja** (4,2 s): اللون يورّي الحالة، والطلبات اللي جات أونلاين بخط متقطّع.

#### 3.5 Nouveau rendez-vous dans l’agenda · موعد جديد في الأجندة
FR 3:20,0 (8,9 s) · AR 3:48,9 (9,6 s) · Bild `19-agenda-nouveau` (dialog)

- **FR** (5,2 s): Touchez un créneau libre, cherchez le patient, puis choisissez l’acte : la durée se remplit seule.
- **FR** (2,3 s): Vérifiez, puis Enregistrer le rendez-vous.
- **Derja** (6,0 s): انزلو على وقت فارغ، لوّجو على المريض، واختارو الخدمة: المدّة تتعمّر وحدها.
- **Derja** (2,2 s): ثبّتو، ومبعد «حفظ الموعد».

#### 3.6 Créneau déjà pris ? · الوقت محجوز؟
FR 3:28,8 (6,0 s) · AR 3:58,5 (6,9 s) · Bild `20-agenda-conflit` (dialog)

- **FR** (5,0 s): Créneau déjà pris ? Daftar refuse, et propose les prochains créneaux libres.
- **Derja** (5,9 s): الوقت محجوز؟ دفتر ما يقبلش، ويقترحلكم أقرب الأوقات الفارغة.

#### 3.7 Sur le téléphone · على الهاتف
FR 3:34,9 (6,9 s) · AR 4:05,4 (7,1 s) · Bild `21-agenda-mobile` (mobile)

- **FR** (3,1 s): Sur le téléphone, l’agenda du jour s’affiche en liste.
- **FR** (2,5 s): Le rendez-vous par téléphone se trouve sous Plus.
- **Derja** (3,0 s): على التلفون، مواعيد النهار تطلع في قائمة.
- **Derja** (2,7 s): والموعد بالهاتف تلقاوه تحت «المزيد».

### Kapitel 4 – Accueil et salle d’attente · الاستقبال وقاعة الانتظار
FR 3:41,8 (6,1 s) · AR 4:12,4 (6,0 s)

- **FR** (5,0 s): Chaque patient reçoit un numéro de ticket. L’écran de la salle n’affiche jamais de nom.
- **Derja** (4,9 s): كل مريض ياخذ نومرو. وشاشة الصالة عمرها ما تورّي الأسامي.

#### 4.1 Le patient arrive · وصول المريض
FR 3:47,9 (8,4 s) · AR 4:18,4 (9,4 s) · Bild `22-rdv-arrive` (dialog)

- **FR** (4,1 s): Le patient arrive : dans l’agenda, touchez son rendez-vous, puis Arrivé.
- **FR** (3,0 s): Il reçoit automatiquement un ticket, dans l’ordre d’arrivée.
- **Derja** (4,8 s): المريض وصل: في الأجندة، انزلو على الموعد متاعو، ومبعد «وصل».
- **Derja** (3,2 s): ياخذ وحدو نومرو، حسب الترتيب متاع الوصول.

#### 4.2 La salle d’attente · قاعة الانتظار
FR 3:56,3 (7,9 s) · AR 4:27,8 (8,4 s) · Bild `23-salle` (page)

- **FR** (3,3 s): La salle d’attente montre qui est en consultation, et qui attend.
- **FR** (3,3 s): Touchez Appeler : le numéro s’affiche sur l’écran de la salle.
- **Derja** (3,6 s): قاعة الانتظار تورّيكم شكون في الفحص، وشكون يستنّى.
- **Derja** (3,5 s): انزلو على «مناداة»: النومرو يطلع على شاشة الصالة.

#### 4.3 Un patient sans rendez-vous · مريض دون موعد
FR 4:04,2 (7,6 s) · AR 4:36,2 (8,8 s) · Bild `24-nouveau-ticket` (dialog)

- **FR** (5,2 s): Un patient sans rendez-vous ? Nouveau ticket : un patient du cabinet, ou juste un nom.
- **FR** (1,0 s): Puis Donner le ticket.
- **Derja** (5,9 s): مريض من غير موعد؟ «رقم جديد»: «مريض مسجّل»، ولا «اسم فقط».
- **Derja** (1,6 s): ومبعد «إعطاء الرقم».

#### 4.4 Le ticket sur le téléphone du patient · الرقم على هاتف المريض
FR 4:11,8 (7,2 s) · AR 4:45,0 (7,4 s) · Bild `25-ticket-qr` (dialog)

- **FR** (2,3 s): WhatsApp envoie au patient le lien de son ticket.
- **FR** (3,6 s): Ou il prend le QR code en photo, et suit son tour sur son téléphone.
- **Derja** (3,1 s): «واتساب» يبعث للمريض الرابط متاع النومرو متاعو.
- **Derja** (2,9 s): ولا يصوّر الكود، ويتبّع دورو من تلفونو.

#### 4.5 Patient suivant · المريض التالي
FR 4:19,0 (8,9 s) · AR 4:52,4 (10,2 s) · Bild `26-patient-suivant` (page)

- **FR** (2,9 s): Patient suivant montre qui passe maintenant, et ensuite.
- **FR** (4,7 s): Appeler le suivant appelle la bonne personne : le patient du rendez-vous, ou le premier arrivé.
- **Derja** (4,0 s): «المريض التالي» يورّي شكون يدخل توّا، وشكون بعدو.
- **Derja** (4,9 s): «مناداة التالي» ينادي الصحيح: مولى الموعد، ولا أوّل واحد وصل.

#### 4.6 L’écran de la salle · شاشة القاعة
FR 4:27,9 (8,3 s) · AR 5:02,6 (8,4 s) · Bild `27-ecran-salle` (tv)

- **FR** (4,0 s): L’écran de la salle s’affiche sur une télévision ou une tablette, en plein écran.
- **FR** (2,9 s): Il se met à jour tout seul, avec des numéros uniquement.
- **Derja** (4,3 s): «شاشة القاعة» تتحلّ على تلفزة ولا تابلات، في كامل الشاشة.
- **Derja** (2,8 s): وتتبدّل وحدها، وفيها نومروات برك.

#### 4.7 Ce que voit le patient · ما يراه المريض
FR 4:36,2 (8,8 s) · AR 5:11,0 (11,0 s) · Bild `28-ticket-patient` (mobile)

- **FR** (4,0 s): Le patient voit son numéro, les personnes avant lui, et l’attente estimée.
- **FR** (3,5 s): Quand c’est son tour : C’est votre tour, présentez-vous à l’accueil.
- **Derja** (5,2 s): المريض يشوف النومرو متاعو، قدّاش من واحد قبلو، وقدّاش باش يستنّى.
- **Derja** (4,4 s): وكي يجي دورو: «حان دورك! تفضّل إلى الاستقبال».

### Kapitel 5 – Caisse · الصندوق
FR 4:45,0 (6,8 s) · AR 5:22,0 (7,1 s)

- **FR** (5,7 s): Daftar enregistre les paiements reçus, et calcule le reste à payer. Il n’encaisse rien lui-même.
- **Derja** (6,0 s): دفتر يسجّل الخلاص اللي تقبضوه، ويحسب الباقي. وهو بيدو ما يقبض شي.

#### 5.1 Les actes et le reste à payer · الخدمات والمتبقّي للدفع
FR 4:51,8 (8,3 s) · AR 5:29,1 (8,9 s) · Bild `29-dossier-solde` (page)

- **FR** (3,2 s): Dans le dossier du patient, Acte ajoute un acte avec son prix.
- **FR** (3,8 s): Le solde montre le total, ce qui est payé, et le reste à payer.
- **Derja** (3,9 s): في ملف المريض، «خدمة» تزيد خدمة بالسوم متاعها.
- **Derja** (3,7 s): و«الرصيد» يورّي المجموع، اللي تخلّص، واللي باقي.

#### 5.2 Encaisser un paiement · تسجيل دفعة
FR 5:00,2 (10,0 s) · AR 5:38,0 (10,0 s) · Bild `30-paiement` (dialog)

- **FR** (3,8 s): Paiement : le montant, le mode de paiement, puis Enregistrer le paiement.
- **FR** (4,8 s): En plusieurs fois ? Enregistrez chaque versement : le reste se met à jour.
- **Derja** (4,3 s): «دفعة»: المبلغ، طريقة الخلاص، ومبعد «تسجيل الدفعة».
- **Derja** (4,3 s): بالتقسيط؟ سجّلو كل قسط، والباقي يتبدّل وحدو.

#### 5.3 Le reçu · الوصل
FR 5:10,2 (5,1 s) · AR 5:47,9 (5,2 s) · Bild `31-recu` (page)

- **FR** (4,0 s): Dans la liste des paiements, Reçu ouvre un reçu, à imprimer avec Imprimer.
- **Derja** (4,1 s): في قائمة الدفعات، «وصل» يحلّ وصل، تطبعوه بـ«طباعة».

#### 5.4 Acompte conseillé · يُنصح بطلب عربون
FR 5:15,2 (7,5 s) · AR 5:53,1 (8,0 s) · Bild `32-acompte-conseille` (dialog)

- **FR** (3,7 s): Après deux absences, le rendez-vous affiche : acompte conseillé.
- **FR** (2,5 s): Demander inscrit le montant de l’acompte demandé.
- **Derja** (4,6 s): بعد زوز غيابات، الموعد يكتبلكم: يُنصح بطلب عربون.
- **Derja** (2,1 s): و«طلب» يكتب مبلغ العربون.

#### 5.5 Encaisser l’acompte · استلام العربون
FR 5:22,8 (4,1 s) · AR 6:01,1 (4,7 s) · Bild `33-acompte-encaisse` (dialog)

- **FR** (3,1 s): Encaisser l’acompte enregistre le paiement, lié au rendez-vous.
- **Derja** (3,6 s): «استلام العربون» يسجّل الخلاص، مربوط بالموعد.

#### 5.6 La caisse du jour · صندوق اليوم
FR 5:26,9 (5,1 s) · AR 6:05,7 (5,7 s) · Bild `34-caisse-jour` (page)

- **FR** (4,1 s): La caisse du jour : le total par mode de paiement, et la liste des paiements.
- **Derja** (4,6 s): صندوق اليوم: المجموع حسب طريقة الخلاص، وقائمة الدفعات.

#### 5.7 Les montants dus · المبالغ المستحقّة
FR 5:32,0 (5,5 s) · AR 6:11,4 (6,8 s) · Bild `35-montants-dus` (section)

- **FR** (4,4 s): Plus bas, les montants dus : qui doit encore de l’argent, du plus grand au plus petit.
- **Derja** (5,7 s): اللوطة، «المبالغ المستحقّة»: شكون مازال عليه فلوس، من الأكبر للأصغر.

#### 5.8 La clôture du soir · غلق الصندوق مساءً
FR 5:37,5 (9,6 s) · AR 6:18,2 (11,4 s) · Bild `36-cloture` (section)

- **FR** (5,2 s): Le soir, notez les espèces comptées, puis Clôturer la caisse : Daftar affiche l’écart.
- **FR** (3,0 s): Le titulaire vérifie ensuite avec Valider la clôture.
- **Derja** (6,0 s): في العشيّة، اكتبو الفلوس اللي عدّيتوها، ومبعد «غلق الصندوق»: دفتر يورّيكم الفرق.
- **Derja** (4,0 s): ومبعد، صاحب العيادة يراجع بـ«المصادقة على الغلق».

### Kapitel 6 – Rappels · التذكيرات
FR 5:47,1 (6,7 s) · AR 6:29,6 (7,2 s)

- **FR** (5,6 s): Daftar prépare le rappel de chaque rendez-vous du lendemain. C’est vous qui l’envoyez, d’un clic.
- **Derja** (6,2 s): دفتر يحضّر التذكير لكل موعد متاع غدوة. وإنتوما اللي تبعثوه، بكليك.

#### 6.1 Les rappels de demain · تذكيرات الغد
FR 5:53,8 (10,1 s) · AR 6:36,8 (11,9 s) · Bild `37-rappels` (page)

- **FR** (3,5 s): Le menu Rappels montre les rendez-vous de demain, avec le message prêt.
- **FR** (5,3 s): Touchez WhatsApp ou SMS : le texte est déjà écrit. Le rappel est noté Envoyé.
- **Derja** (3,8 s): قائمة «التذكيرات» تورّي مواعيد غدوة، والميساج حاضر.
- **Derja** (6,8 s): انزلو على «واتساب» ولا «إرسالية قصيرة»: النص مكتوب. والتذكير يتسجّل «أُرسل».

#### 6.2 Depuis le téléphone du cabinet · من هاتف العيادة
FR 6:03,9 (7,9 s) · AR 6:48,7 (8,3 s) · Bild `38-rappels-mobile` (mobile)

- **FR** (4,1 s): Depuis le téléphone du cabinet, WhatsApp ou les SMS s’ouvrent directement.
- **FR** (2,4 s): Les patients sans accord pour les rappels sont grisés.
- **Derja** (4,1 s): من تلفون العيادة، الواتساب ولا الإس إم إس يتحلّو طول.
- **Derja** (2,8 s): والمرضى اللي ما قبلوش التذكير يطلعو باهتين.

#### 6.3 Modifier le texte · تعديل النص
FR 6:11,8 (7,8 s) · AR 6:57,1 (7,8 s) · Bild `39-rappels-modele` (section)

- **FR** (3,6 s): Le texte se modifie dans les Réglages, en français et en arabe.
- **FR** (2,9 s): Les mots entre accolades sont remplacés automatiquement.
- **Derja** (3,7 s): النص تبدّلوه في «الإعدادات»، بالعربي وبالفرنسي.
- **Derja** (2,8 s): والكلمات اللي بين الأقواس تتبدّل وحدها.

### Kapitel 7 – Importer une liste Excel · استيراد قائمة Excel
FR 6:19,6 (6,4 s) · AR 7:04,9 (7,0 s)

- **FR** (5,3 s): Vos patients sont dans Excel ? Daftar les reprend, et rien n’est enregistré avant la fin.
- **Derja** (5,9 s): المرضى متاعكم في Excel؟ دفتر ياخذهم، وحتى شي ما يتسجّل قبل الآخر. _(gesprochen: المرضى متاعكم في إكسال؟ دفتر ياخذهم، وحتى شي ما يتسجّل قبل الآخر.)_

#### 7.1 Choisir le fichier · اختيار الملف
FR 6:25,9 (4,8 s) · AR 7:11,9 (5,3 s) · Bild `40-import-fichier` (page)

- **FR** (3,7 s): Choisissez Des patients ou Des rendez-vous, puis un fichier Excel ou CSV.
- **Derja** (4,3 s): اختارو «مرضى» ولا «مواعيد»، ومبعد ملف Excel ولا CSV. _(gesprochen: اختارو «مرضى» ولا «مواعيد»، ومبعد ملف إكسال ولا سي إس في.)_

#### 7.2 Correspondance des colonnes · ربط الأعمدة
FR 6:30,7 (9,7 s) · AR 7:17,2 (11,1 s) · Bild `41-import-correspondance` (page)

- **FR** (6,2 s): Pour chaque information, choisissez la colonne de votre fichier. Daftar propose déjà ce qui ressemble.
- **FR** (2,1 s): Vérifiez, puis Vérifier le fichier.
- **Derja** (7,0 s): لكل معلومة، اختارو العمود المناسب من الملف متاعكم. دفتر يقترح من قبل اللي يشبهها.
- **Derja** (2,7 s): ثبّتو، ومبعد «التحقق من الملف».

#### 7.3 Vérification · التحقق
FR 6:40,4 (8,3 s) · AR 7:28,3 (10,3 s) · Bild `42-import-verification` (page)

- **FR** (3,2 s): Daftar montre ce que l’import ferait, et les lignes à corriger.
- **FR** (3,7 s): Rien n’est encore enregistré. Importer lance l’import.
- **Derja** (4,7 s): دفتر يورّيكم شنوّة باش يعمل الاستيراد، والسطور اللي لازمها تصليح.
- **Derja** (4,2 s): حتى شي ما تسجّل مازال. و«استيراد» يبدا الخدمة.

#### 7.4 Import terminé · انتهى الاستيراد
FR 6:48,7 (8,1 s) · AR 7:38,6 (7,8 s) · Bild `43-import-termine` (page)

- **FR** (3,5 s): Import terminé. Téléchargez le rapport si besoin.
- **FR** (3,3 s): Gardez la correspondance comme modèle, pour le prochain fichier.
- **Derja** (3,7 s): الاستيراد كمل. نزّلو التقرير كان تحبّو.
- **Derja** (2,8 s): واحفظو الربط كنموذج، للملف الجاي.

### Kapitel 8 – Réservation en ligne côté patient · الحجز عبر الإنترنت من جهة المريض
FR 6:56,8 (5,9 s) · AR 7:46,4 (6,6 s)

- **FR** (4,9 s): Vos patients réservent sur la page de votre cabinet, à toute heure, et sans créer de compte.
- **Derja** (5,6 s): المرضى متاعكم يحجزو من صفحة العيادة، في أي وقت، ومن غير ما يعملو حساب.

#### 8.1 Choisir l’acte et l’heure · اختيار الخدمة والساعة
FR 7:02,7 (7,9 s) · AR 7:53,0 (8,7 s) · Bild `44-reservation-choix` (mobile)

- **FR** (4,6 s): Le patient choisit l’acte, le praticien, le jour et un horaire, puis Continuer.
- **FR** (2,0 s): Seuls les horaires libres sont affichés.
- **Derja** (5,2 s): المريض يختار الخدمة، الطبيب، النهار والساعة، ومبعد «متابعة».
- **Derja** (2,2 s): وما يطلعلو كان الأوقات الفارغة.

#### 8.2 Ses coordonnées · معلوماته
FR 7:10,6 (7,2 s) · AR 8:01,7 (8,0 s) · Bild `45-reservation-coordonnees` (mobile)

- **FR** (4,5 s): Il indique son prénom, son nom et son téléphone, et peut demander un rappel la veille.
- **FR** (1,4 s): Puis Réserver ce rendez-vous.
- **Derja** (4,8 s): يكتب الاسم، اللقب والتلفون، وينجّم يطلب تذكير نهار قبل.
- **Derja** (1,8 s): ومبعد «احجز هذا الموعد».

#### 8.3 Son lien personnel · رابطه الشخصي
FR 7:17,9 (6,5 s) · AR 8:09,7 (6,8 s) · Bild `46-reservation-envoyee` (mobile)

- **FR** (5,5 s): Demande envoyée. Le patient garde son lien personnel, et peut l’envoyer par WhatsApp.
- **Derja** (5,7 s): «تمّ إرسال الطلب». والمريض يخبّي الرابط متاعو، وينجّم يبعثو بالواتساب.

#### 8.4 Annuler par le lien · الإلغاء عبر الرابط
FR 7:24,4 (10,0 s) · AR 8:16,5 (10,3 s) · Bild `47-rdv-annuler` (mobile)

- **FR** (5,3 s): Avec son lien, le patient peut annuler. Le créneau est libéré pour un autre patient.
- **FR** (3,4 s): Après le délai minimum que vous avez choisi, il appelle le cabinet.
- **Derja** (5,9 s): بالرابط متاعو، المريض ينجّم يبطّل الموعد. والوقت يتحرّر لمريض آخر.
- **Derja** (3,1 s): وبعد المهلة اللي اخترتوها، يكلّم العيادة.

#### 8.5 Au cabinet : confirmer la demande · في العيادة: تأكيد الطلب
FR 7:34,4 (8,8 s) · AR 8:26,8 (10,1 s) · Bild `48-demandes-en-ligne` (section)

- **FR** (3,6 s): Les demandes arrivent sur la page Aujourd’hui, et en pointillés dans l’agenda.
- **FR** (3,9 s): Confirmer ou Refuser, puis Prévenir par WhatsApp : le texte est prêt.
- **Derja** (4,1 s): الطلبات توصل لصفحة «اليوم»، وبخط متقطّع في الأجندة.
- **Derja** (4,6 s): «تأكيد» ولا «رفض»، ومبعد «إعلام عبر واتساب»: النص حاضر.

### Outro (QR, Preis)
FR 7:43,3 (15,1 s) · AR 8:36,9 (17,2 s)

- **FR** (6,2 s): Une question ? Le bouton Une idée, un problème, dans Daftar, écrit directement à Omar.
- **FR** (5,1 s): Phase pilote gratuite, puis dès vingt-neuf dinars par mois. À bientôt sur Daftar !
- **Derja** (6,7 s): عندكم سؤال؟ الزر «فكرة؟ مشكلة؟» في دفتر يبعث الميساج طول لعمر.
- **Derja** (6,7 s): الفترة التجريبية بلاش، ومن بعد من تسعة وعشرين دينار في الشهر. نتلاقاو في دفتر!

## Hinweise zum Derja

- Schreibweise wie man in Tunesien im Chat schreibt (z. B. توّا، برشا، متاع، باش، كان = „wenn/nur“, ولا = „oder“,
  مبعد = „danach“, نومرو، تيكي، الكاسة، الخلاص، السوم، لوّج، فسخ، يحلّ = „öffnen“, ورّى = „zeigen“).
- Knopf- und Menünamen stehen in «…» genau wie in der arabischen Oberfläche (Hocharabisch), damit man sie wiedererkennt.
- Fachwörter aus dem Französischen, wie man sie in der Praxis sagt: الديمو، أونلاين، البي سي، التابلات، الواتساب، الإس إم إس، سيرفور.
- Die Stimme ar-TN spricht tunesisch gefärbt; ob jedes Derja-Wort natürlich klingt, bitte nach dem ersten Lauf anhören
  (Cache: `marketing/voice/cache/`, je Satz eine WAV-Datei).
