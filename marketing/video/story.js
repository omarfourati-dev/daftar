/* Storyboard des Daftar-Werbevideos „Vorher → mit Daftar“ – die eine Datenquelle für scenes.html (Animation),
   render.mjs (Export, Stimme), storyboard.md und sprechtexte.md (beide werden daraus erzeugt; nicht von Hand ändern).

   Zwei Fassungen: v = vertikal 1080 x 1920 (WhatsApp, höchstens 60 s und unter 16 MB), h = quer 1920 x 1080
   (YouTube, LinkedIn, E-Mail, etwa 90–120 s). Jede Fassung FR und AR, mit Stimme (Azure Neural TTS, voice/tts.py).
   Die Szenendauer ergibt sich aus der Länge der Sprechtexte (timing.js).

   Texte im Bild: FR bzw. Hocharabisch (wie Landing und Flyer). Sprechtexte (say): FR bzw. tunesisches Derja in
   arabischer Schrift, kurze Sätze, Zahlen ausgeschrieben, Adresse per SSML-<sub>. Nichts versprechen, was die App nicht
   kann (geprüft gegen docs/superpowers/specs/2026-10-30-daftar-design.md und die Landing): Rappels werden mit einem
   Klick in WhatsApp/SMS geöffnet, nicht automatisch verschickt; Doppelbuchungen lehnt die Datenbank ab; Daten liegen
   auf einem Server bei IONOS in Deutschland, Verbindung HTTPS; keine Aussagen zu Sicherungskopien.

   kind:  cahier (Aufhänger) | pair (vorher → mit Daftar) | persona (Wechsel zur Ärztin/zum Arzt) | cta
   pair:  pain: { art, who, title, sub } – art: phone | double | salle | calls | notes | absent | overview | leave | lost
          fix:  { title, sub, shots, badge? } – shots: [{ id, slot, url?, mark?, crop? }]
                id: Video-Aufnahme (video/shots/<id>-<lang>.png) oder „t:<id>“ = Tutorial-Aufnahme (tutorial/shots/…)
                mark: { x, y, w, h } Anteil am Bild (FR-Layout; für AR horizontal gespiegelt) → Hervorhebung
                crop: { x, y, w, h } nur diesen Ausschnitt zeigen
   say:   [{ fr, ar, switch? }] – ein Eintrag je Satzgruppe; switch: true = hier wechselt das Bild auf „mit Daftar“ */
(function (root) {
  const T = (fr, ar) => ({ fr, ar });
  const S = (fr, ar, extra) => Object.assign({ fr, ar }, extra || {});
  const ADDR = '<sub alias="daftar point omar fourati point dé e">daftar.omarfourati.de</sub>';

  const WHO = {
    accueil: T('À l’accueil', 'في الاستقبال'),
    medecin: T('Pour le médecin', 'للطبيب'),
    daftar: T('Avec Daftar', 'مع دفتر'),
  };

  const CTA = {
    kind: 'cta',
    title: T('Essayez la démo', 'جرّبوا دفتر الآن'),
    sub: T('Gratuite, sans inscription – un cabinet fictif prêt en quelques secondes.', 'مجانًا ودون تسجيل – عيادة وهمية جاهزة في ثوانٍ.'),
    url: 'daftar.omarfourati.de',
    price: T('Phase pilote gratuite', 'المرحلة التجريبية مجانية'),
    priceRest: T('ensuite à partir de 29 DT par mois, sans engagement', 'بعدها ابتداءً من 29 د.ت شهريًا، دون التزام'),
    note: 'Abschluss auf Dunkel-Teal: Logo, Aufforderung, QR-Code zu https://daftar.omarfourati.de (wird beim Export gelesen und geprüft), Adresse groß, Preis-Hinweis.',
  };

  const ENTRIES = {
    fr: [['08:30', 'Mme Trabelsi'], ['09:00', 'M. Gharbi'], ['09:30', 'Mme Jlassi'], ['10:00', 'M. Mejri'], ['10:30', 'M. Dridi'], ['11:00', 'Mme Sassi'], ['11:30', 'M. Hammami']],
    ar: [['08:30', 'السيدة الطرابلسي'], ['09:00', 'السيد الغربي'], ['09:30', 'السيدة الجلاصي'], ['10:00', 'السيد الماجري'], ['10:30', 'السيد الدريدي'], ['11:00', 'السيدة الساسي'], ['11:30', 'السيد الحمامي']],
  };

  // ---------- Bausteine „mit Daftar“ (Bildschirmtexte und echte Aufnahmen) ----------
  const FIX = {
    telephone: {
      title: T('Au téléphone : le numéro, l’acte, un clic.', 'مكالمة؟ الرقم، الخدمة، ونقرة واحدة.'),
      sub: T('Daftar propose les prochains créneaux libres. Le rendez-vous est dans l’agenda.', 'يقترح دفتر أقرب الأوقات الشاغرة، والموعد في الأجندة.'),
      shots: [{ id: 'v03-telephone-desktop', slot: 'browser-back', url: 'app.daftar.omarfourati.de/app', mark: { x: 0.495, y: 0.29, w: 0.265, h: 0.41 } },
        { id: 'v02-agenda-mobile', slot: 'phone-front' }],
    },
    conflit: {
      title: T('Un créneau déjà pris ? Daftar refuse.', 'وقت محجوز؟ دفتر يرفض.'),
      sub: T('Et il propose aussitôt les horaires libres.', 'ويقترح فورًا الساعات الشاغرة.'),
      shots: [{ id: 'v01-agenda-desktop', slot: 'browser-back', url: 'app.daftar.omarfourati.de/app/agenda' },
        { id: 't:20-agenda-conflit', slot: 'card-front', crop: { x: 0, y: 0.38, w: 1, h: 0.62 }, mark: { x: 0.025, y: 0.83, w: 0.95, h: 0.085 } }],
    },
    salle: {
      title: T('Un ticket pour chaque patient.', 'رقم تذكرة لكل مريض.'),
      sub: T('L’écran de la salle affiche les numéros, jamais les noms.', 'تعرض شاشة القاعة الأرقام، دون أي اسم.'),
      shots: [{ id: 'v06-salle-desktop', slot: 'browser-back', url: 'app.daftar.omarfourati.de/app/salle', mark: { x: 0.722, y: 0.21, w: 0.25, h: 0.39 } },
        { id: 'v07-ecran-tv', slot: 'tv-front' }],
    },
    rappels: {
      title: T('Les rappels de demain, en un clic.', 'تذكيرات الغد بنقرة واحدة.'),
      sub: T('WhatsApp ou SMS s’ouvre avec le message déjà écrit.', 'يُفتح واتساب أو الرسائل القصيرة والنص جاهز.'),
      shots: [{ id: 't:37-rappels', slot: 'browser-back', url: 'app.daftar.omarfourati.de/app/rappels', mark: { x: 0.2, y: 0.335, w: 0.38, h: 0.265 } },
        { id: 'v09-rappels-mobile', slot: 'phone-front' }],
    },
    paiements: {
      title: T('Chaque paiement enregistré, le reste calculé.', 'كل دفعة مسجّلة، والمتبقّي محسوب.'),
      sub: T('Le soir : espèces comptées, écart affiché.', 'في المساء: النقد المعدود، والفارق ظاهر.'),
      shots: [{ id: 't:29-dossier-solde', slot: 'browser-back', url: 'app.daftar.omarfourati.de/app/patients', mark: { x: 0.735, y: 0.305, w: 0.23, h: 0.1 } },
        { id: 't:36-cloture', slot: 'card-front', mark: { x: 0.05, y: 0.43, w: 0.9, h: 0.16 } }],
    },
    absences: {
      title: T('Chaque absence est comptée.', 'يُحتسب كل تغيّب.'),
      sub: T('Après deux absences : acompte conseillé.', 'بعد تغيّبين: يُنصح بطلب عربون.'),
      shots: [{ id: 't:32-acompte-conseille', slot: 'card-back', crop: { x: 0, y: 0, w: 0.52, h: 0.36 }, mark: { x: 0.015, y: 0.125, w: 0.48, h: 0.075 } },
        { id: 'v13-dossier-mobile', slot: 'phone-front', mark: { x: 0.07, y: 0.325, w: 0.88, h: 0.09 } }],
    },
    caisse: {
      title: T('La caisse du jour et les montants dus.', 'صندوق اليوم والمبالغ المستحقّة.'),
      sub: T('Par mode de paiement, et à tout moment.', 'حسب طريقة الدفع، وفي أي وقت.'),
      shots: [{ id: 'v11-caisse-desktop', slot: 'browser-back', url: 'app.daftar.omarfourati.de/app/caisse', mark: { x: 0.19, y: 0.215, w: 0.52, h: 0.25 } },
        { id: 't:35-montants-dus', slot: 'card-front' }],
    },
    enligne: {
      title: T('Réservation en ligne, à toute heure.', 'حجز عبر الإنترنت، في أي ساعة.'),
      sub: T('Et chacun suit son tour sur son téléphone.', 'ويتابع كل مريض دوره على هاتفه.'),
      shots: [{ id: 'v04-reservation-mobile', slot: 'pair-a' }, { id: 'v08-ticket-mobile', slot: 'pair-b' }],
    },
    donnees: {
      title: T('Vos données, enregistrées et protégées.', 'بياناتكم محفوظة ومحميّة.'),
      sub: T('Hébergées en Allemagne, connexion chiffrée – sur PC, tablette et téléphone.', 'استضافة في ألمانيا واتصال مشفَّر – على الحاسوب واللوحة والهاتف.'),
      badge: T('Serveur en Allemagne · HTTPS', 'خادم في ألمانيا · HTTPS'),
      shots: [{ id: 'v01-agenda-desktop', slot: 'browser-back', url: 'app.daftar.omarfourati.de/app/agenda' }, { id: 'v12-aujourdhui-mobile', slot: 'phone-front' }],
    },
  };

  // ---------- Schmerzpunkte (Bildschirmtexte) ----------
  const PAIN = {
    phone: { art: 'phone', who: 'accueil', title: T('Le téléphone sonne sans arrêt.', 'الهاتف يرنّ دون توقّف.'), sub: T('On cherche dans le cahier, on gomme, on réécrit.', 'نبحث في الدفتر، نمحو، ونعيد الكتابة.') },
    double: { art: 'double', who: 'accueil', title: T('Deux patients, la même heure.', 'مريضان في الساعة نفسها.'), sub: T('Le cahier ne dit jamais non.', 'الدفتر الورقي لا يرفض أبدًا.') },
    salle: { art: 'salle', who: 'accueil', title: T('La salle déborde.', 'القاعة ممتلئة.'), sub: T('Chacun demande son tour, l’ordre de passage se discute.', 'الكل يسأل عن دوره، والترتيب محلّ نقاش.') },
    calls: { art: 'calls', who: 'accueil', title: T('Les rappels ? Des heures au téléphone.', 'التذكيرات؟ ساعات على الهاتف.'), sub: T('La veille, un appel par patient.', 'في اليوم السابق، مكالمة لكل مريض.') },
    notes: { art: 'notes', who: 'accueil', title: T('Des restes à payer sur des bouts de papier.', 'مبالغ متبقّية على قصاصات ورق.'), sub: T('Et le soir, la caisse se compte à la main.', 'وفي المساء، يُحسب الصندوق باليد.') },
    absent: { art: 'absent', who: 'medecin', title: T('Un patient absent, un créneau perdu.', 'مريض غائب، موعد ضائع.'), sub: T('Et personne ne note que c’est la troisième fois.', 'ولا أحد يسجّل أنها المرة الثالثة.') },
    overview: { art: 'overview', who: 'medecin', title: T('Combien encaissé ? Combien reste dû ?', 'كم دُفع اليوم؟ وكم بقي؟'), sub: T('Avec le cahier, personne ne le sait vraiment.', 'مع الدفتر الورقي، لا أحد يعرف بالضبط.') },
    leave: { art: 'leave', who: 'medecin', title: T('Trop d’attente, le patient va ailleurs.', 'انتظار طويل، فيذهب المريض إلى غيركم.'), sub: T('Des heures dans la salle, sans savoir quand.', 'ساعات في القاعة، دون معرفة متى.') },
    lost: { art: 'lost', who: 'medecin', title: T('Le cahier se perd, l’agenda avec.', 'يضيع الدفتر، وتضيع معه المواعيد.'), sub: T('Un seul exemplaire, posé à l’accueil.', 'نسخة واحدة على مكتب الاستقبال.') },
  };
  const pair = (pain, fix, say, extra) => Object.assign({ kind: 'pair', pain: PAIN[pain], fix: FIX[fix], say }, extra || {});

  const story = {
    voices: {
      fr: { voice: 'fr-FR-DeniseNeural', lang: 'fr-FR' },
      ar: { voice: 'ar-TN-ReemNeural', lang: 'ar-TN' },
    },
    // Sprechtempo je Fassung; ist eine Fassung zu lang, erhöht render.mjs das Tempo stufenweise (rateSteps)
    rate: { v: '+10%', h: '+4%' },
    rateSteps: { v: ['+14%', '+18%'], h: ['+8%', '+12%'] },
    // Pausen je Fassung (timing.js): lead = Stille am Szenenanfang, switchGap = Pause vor „mit Daftar“, tail = Ausklang
    timing: { v: { lead: 0.2, gap: 0.25, switchGap: 0.45, tail: 0.3 }, h: { lead: 0.3, gap: 0.3, switchGap: 0.55, tail: 0.4 } },
    limits: { v: { maxS: 60, maxBytes: 16e6 }, h: { minS: 90, maxS: 120 } },
    who: WHO,
    entries: ENTRIES,
    double: { time: '10:00', fr: 'Mme Ayari', ar: 'السيدة العياري' },
    absent: { fr: ['M. Hammami', 'absent'], ar: ['السيد الحمامي', 'غائب'], debt: T('reste 120 DT ?', 'بقي 120 د.ت؟') },
    bubble: T('C’est quand mon tour ?', 'متى يأتي دوري؟'),
    bubble2: T('J’étais là avant !', 'جئت قبله!'),
    art: {
      notes: { fr: ['reste 120 DT', 'doit 45 DT', 'Sassi : 60 ?', 'reste 30 DT'], ar: ['بقي 120 د.ت', 'عليه 45 د.ت', 'الساسي: 60؟', 'بقي 30 د.ت'] },
      sum: T('385 + 120 + 90 + … = ?', '385 + 120 + 90 + … = ؟'),
      overview: { fr: ['Encaissé aujourd’hui', 'Montants dus', 'Absences du mois'], ar: ['المقبوض اليوم', 'المبالغ المستحقّة', 'غيابات الشهر'] },
      calls: T('Allô ? C’est le cabinet…', 'آلو؟ معاك العيادة…'),
      lost: T('Rendez-vous', 'المواعيد'),
      wait: T('2 h 10', '2:10'),
    },

    // ---------------- Hochformat (≤ 60 s) ----------------
    v: [
      { kind: 'cahier', title: T('Votre cabinet tourne encore avec un cahier ?', 'عيادتكم ما زالت تعمل بدفتر ورقي؟'),
        timing: { firstLead: 0.3, tail: 0.35 },
        say: [S('Votre cabinet tourne encore avec un cahier ?', 'العيادة متاعكم مازالت تخدم بالكرّاس؟')],
        note: 'Heftseite füllt sich Zeile für Zeile mit handschriftlichen Terminen.' },
      pair('phone', 'telephone', [
        S('Ça sonne, on gomme, et deux patients à la même heure.', 'التلفون يرنّ، تفسخ، وزوز مرضى في نفس الوقت.'),
        S('Avec Daftar : un clic, et jamais deux rendez-vous à la même heure.', 'مع دفتر: كليك وحدة، وعمرك ما تلقى زوز مواعيد في نفس الوقت.', { switch: true }),
      ], { pain: Object.assign({}, PAIN.phone, { title: T('Le téléphone sonne, le cahier déborde.', 'الهاتف يرنّ، والدفتر لم يعد يتّسع.'), sub: null }),
        fix: { title: T('Un clic, et jamais deux rendez-vous à la même heure.', 'نقرة واحدة، ولا موعدين في الوقت نفسه أبدًا.'),
          shots: [{ id: 'v02-agenda-mobile', slot: 'phone' }, { id: 't:20-agenda-conflit', slot: 'card-front', crop: { x: 0, y: 0.38, w: 1, h: 0.62 }, mark: { x: 0.025, y: 0.83, w: 0.95, h: 0.085 } }] } }),
      pair('salle', 'salle', [
        S('La salle déborde : c’est quand mon tour ?', 'الصالة معبّية: وقتاش دوري؟'),
        S('Avec Daftar, un ticket par patient, et son tour sur son téléphone.', 'مع دفتر، كل مريض عندو تيكي، ويتبّع دورو من تلفونو.', { switch: true }),
      ], { pain: Object.assign({}, PAIN.salle, { sub: null }),
        fix: { title: T('Un ticket par patient, son tour sur son téléphone.', 'رقم لكل مريض، ودوره على هاتفه.'),
          shots: [{ id: 'v08-ticket-mobile', slot: 'phone' }, { id: 'v07-ecran-tv', slot: 'tv-front' }] } }),
      pair('calls', 'rappels', [
        S('Des heures de rappels au téléphone, et des absents quand même.', 'سوايع على التلفون للتذكير، ومع هذا فمّا اللي ما يجيش.'),
        S('Avec Daftar, un clic par rappel, et chaque absence est comptée.', 'مع دفتر، كليك لكل تذكير، وكل غياب يتحسب.', { switch: true }),
      ], { pain: Object.assign({}, PAIN.calls, { sub: T('Et des absents quand même.', 'ومع ذلك يتغيّب البعض.') }),
        fix: { title: T('Les rappels en un clic, les absences comptées.', 'التذكير بنقرة، والتغيّب محسوب.'),
          shots: [{ id: 'v09-rappels-mobile', slot: 'phone' }, { id: 't:32-acompte-conseille', slot: 'card-front', crop: { x: 0, y: 0, w: 1, h: 0.36 }, mark: { x: 0.015, y: 0.125, w: 0.48, h: 0.075 } }] } }),
      pair('notes', 'paiements', [
        S('Des restes à payer sur des bouts de papier ?', 'فلوس باقية مكتوبة في وريقات؟'),
        S('Avec Daftar, le reste se calcule tout seul, et la caisse du jour est prête.', 'مع دفتر، الباقي يتحسب وحدو، والكاسة متاع اليوم حاضرة.', { switch: true }),
      ], { pain: Object.assign({}, PAIN.notes, { sub: null }),
        fix: { title: T('Le reste calculé, la caisse du jour prête.', 'المتبقّي محسوب، وصندوق اليوم جاهز.'),
          shots: [{ id: 'v13-dossier-mobile', slot: 'phone' }, { id: 't:36-cloture', slot: 'card-front', mark: { x: 0.05, y: 0.43, w: 0.9, h: 0.16 } }] } }),
      pair('leave', 'enligne', [
        S('Trop d’attente, et le patient va ailleurs.', 'برشا انتظار، والمريض يمشي لغيرك.'),
        S('Avec Daftar, vos patients réservent en ligne, à toute heure.', 'مع دفتر، المرضى يحجزو أونلاين، في أي وقت.', { switch: true }),
      ], { pain: Object.assign({}, PAIN.leave, { sub: null }),
        fix: { title: T('Vos patients réservent en ligne, à toute heure.', 'مرضاكم يحجزون عبر الإنترنت، في أي ساعة.'),
          shots: [{ id: 'v04-reservation-mobile', slot: 'phone' }] } }),
      pair('lost', 'donnees', [
        S('Et si le cahier se perd ?', 'وكان الكرّاس ضاع؟'),
        S('Avec Daftar, tout est enregistré en Allemagne, et s’ouvre sur chaque appareil.', 'مع دفتر، كل شي محفوظ في ألمانيا، ويتحلّ على أي جهاز.', { switch: true }),
      ], { pain: Object.assign({}, PAIN.lost, { title: T('Et si le cahier se perd ?', 'وإن ضاع الدفتر؟'), sub: null }),
        fix: { title: T('Tout est enregistré, sur chaque appareil.', 'كل شيء محفوظ، على كل جهاز.'), badge: FIX.donnees.badge,
          shots: [{ id: 'v01-agenda-desktop', slot: 'browser-back', url: 'app.daftar.omarfourati.de/app/agenda' }, { id: 'v12-aujourdhui-mobile', slot: 'phone-front' }] } }),
      Object.assign({}, CTA, { timing: { tail: 2.2 },
        say: [S('Essayez la démo gratuite. Phase pilote gratuite, puis dès vingt-neuf dinars par mois.', 'جرّبو الديمو بلاش. الفترة التجريبية بلاش، ومن بعد من تسعة وعشرين دينار في الشهر.')] }),
    ],

    // ---------------- Querformat (≈ 90–120 s) ----------------
    h: [
      { kind: 'cahier', title: T('Votre cabinet tourne encore avec un cahier ?', 'عيادتكم ما زالت تعمل بدفتر ورقي؟'),
        sub: T('Voici ce que Daftar change, à l’accueil et pour le médecin.', 'إليكم ما يغيّره دفتر، في الاستقبال وللطبيب.'),
        timing: { firstLead: 0.4 },
        say: [S('Votre cabinet tourne encore avec un cahier ? Voici ce que Daftar change.', 'العيادة متاعكم مازالت تخدم بالكرّاس؟ هاو شنوّة يبدّل دفتر.')],
        note: 'Heftseite füllt sich mit handschriftlichen Terminen, Text auf der Leseanfangsseite.' },
      pair('phone', 'telephone', [
        S('À l’accueil, le téléphone sonne sans arrêt. On cherche, on gomme, on réécrit.', 'في الاستقبال، التلفون ما يحبسش يرنّ. تلوّج، تفسخ، وتعاود تكتب.'),
        S('Avec Daftar : le numéro, l’acte, et les créneaux libres s’affichent. Un clic, c’est noté.', 'مع دفتر: النومرو، الخدمة، والأوقات الفارغة تطلعلك. كليك وحدة، ويتسجّل.', { switch: true }),
      ]),
      pair('double', 'conflit', [
        S('Et parfois, deux patients à la même heure.', 'وساعات، زوز مرضى في نفس الوقت.'),
        S('Avec Daftar, c’est impossible : Daftar refuse, et propose les horaires libres.', 'مع دفتر، هذا ما يصيرش: دفتر يرفض، ويقترحلك الأوقات الفارغة.', { switch: true }),
      ]),
      pair('salle', 'salle', [
        S('La salle est pleine, et chacun demande : c’est quand mon tour ?', 'الصالة معبّية، وكل واحد يسأل: وقتاش دوري؟'),
        S('Avec Daftar, chaque patient a un ticket. L’écran de la salle affiche les numéros appelés.', 'مع دفتر، كل مريض عندو تيكي. والشاشة في الصالة تورّي النومرو اللي جا دورو.', { switch: true }),
      ]),
      pair('calls', 'rappels', [
        S('La veille, des heures au téléphone pour les rappels.', 'العشيّة، سوايع على التلفون باش تفكّر المرضى.'),
        S('Avec Daftar, un clic ouvre WhatsApp ou les SMS, avec le message déjà écrit.', 'مع دفتر، كليك يحلّلك الواتساب ولا الإس إم إس، والميساج مكتوب.', { switch: true }),
      ]),
      pair('notes', 'paiements', [
        S('Des restes à payer sur des bouts de papier, et le soir, la caisse à la main.', 'فلوس باقية مكتوبة في وريقات، وفي العشيّة الكاسة تتحسب باليد.'),
        S('Avec Daftar, le reste à payer se calcule tout seul, et le soir, Daftar affiche l’écart de caisse.', 'مع دفتر، الباقي يتحسب وحدو، وفي العشيّة دفتر يورّيك الفرق في الكاسة.', { switch: true }),
      ]),
      { kind: 'persona', title: T('Et pour le médecin ?', 'وماذا عن الطبيب؟'), timing: { lead: 0.45, tail: 0.55 },
        say: [S('Et pour le médecin ?', 'وبالنسبة للطبيب؟')],
        note: 'Kurzer Wechsel auf Teal: Stethoskop-Symbol, Frage groß.' },
      pair('absent', 'absences', [
        S('Un patient qui ne vient pas, c’est un créneau perdu.', 'مريض ما جاش، معناها بلاصة ضايعة.'),
        S('Avec Daftar, chaque absence est comptée, et après deux, Daftar conseille un acompte.', 'مع دفتر، كل غياب يتحسب، وبعد زوز، دفتر ينصحك تطلب عربون.', { switch: true }),
      ]),
      pair('overview', 'caisse', [
        S('Combien encaissé aujourd’hui ? Combien reste dû ? Personne ne le sait vraiment.', 'قدّاش دخل اليوم؟ وقدّاش باقي على المرضى؟ حتى حد ما يعرف بالضبط.'),
        S('Avec Daftar : la caisse du jour, par mode de paiement, et les montants dus, à tout moment.', 'مع دفتر: الكاسة متاع اليوم حسب طريقة الخلاص، والفلوس اللي باقية، في أي وقت.', { switch: true }),
      ]),
      pair('leave', 'enligne', [
        S('Trop d’attente, et certains patients vont voir un autre médecin.', 'برشا انتظار، وفمّا مرضى يمشيو لطبيب آخر.'),
        S('Avec Daftar, ils réservent en ligne, à toute heure, et suivent leur tour sur leur téléphone.', 'مع دفتر، يحجزو أونلاين في أي وقت، ويتبّعو دورهم من التلفون.', { switch: true }),
      ]),
      pair('lost', 'donnees', [
        S('Et si le cahier se perd ? Tous les rendez-vous disparaissent.', 'وكان الكرّاس ضاع؟ المواعيد الكل يمشيو معاه.'),
        S('Avec Daftar, tout est enregistré en Allemagne, connexion chiffrée, sur PC, tablette et téléphone.', 'مع دفتر، كل شي محفوظ في ألمانيا، والاتصال مشفّر، على البي سي والتابلات والتلفون.', { switch: true }),
      ]),
      Object.assign({}, CTA, { timing: { tail: 2.5 },
        say: [S(`Essayez la démo gratuite sur ${ADDR}. Phase pilote gratuite, puis dès vingt-neuf dinars par mois.`,
          'جرّبو الديمو بلاش: سكانيو الكود اللي على الشاشة. الفترة التجريبية بلاش، ومن بعد من تسعة وعشرين دينار في الشهر.')] }),
    ],
  };

  root.DAFTAR_STORY = story;
})(typeof window !== 'undefined' ? window : globalThis);
