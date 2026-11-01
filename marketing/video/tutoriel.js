/* Tutorial-Gesamtvideo Daftar (FR/AR, 1920 x 1080, etwa 8–10 Minuten) – Datenquelle für tutoriel.html (Bild),
   render.mjs (Export, Stimme) und sprechtexte.md. Kapitel und Schritte wie das Tutorial-PDF (tutorial/tutorial-*.html).

   Je Schritt: der echte Screenshot (tutorial/shots/<shot>-<lang>.png), Titel wie im PDF (FR bzw. Hocharabisch),
   1–2 Sätze Sprechtext (FR bzw. tunesisches Derja, arabische Schrift), die auch als Untertitel erscheinen, und je Satz
   optional ein Fokus { x, y, w, h } (Anteil am Bild, FR-Layout; für AR horizontal gespiegelt): die Kamera fährt sanft
   dorthin und hebt die Stelle hervor. view: page | dialog | section | mobile | tv.
   04/05/06-installer-* sind Platzhalter und werden nicht gezeigt: diese Schritte zeigen 03-installer mit einer
   Merkkarte (panel) der Handgriffe. */
(function (root) {
  const T = (fr, ar) => ({ fr, ar });
  const S = (fr, ar, focus, extra) => Object.assign({ fr, ar }, focus ? { focus } : {}, extra || {});
  const F = (x, y, w, h) => ({ x, y, w, h });
  const ADDR = '<sub alias="daftar point omar fourati point dé e">daftar.omarfourati.de</sub>';
  const QR = '<sub alias="كيو آر">QR</sub>';
  const EXCEL = '<sub alias="إكسال">Excel</sub>';
  const CSV = '<sub alias="سي إس في">CSV</sub>';
  const A4 = '<sub alias="آ كاتر">A4</sub>';

  const tut = {
    voices: {
      fr: { voice: 'fr-FR-DeniseNeural', lang: 'fr-FR' },
      ar: { voice: 'ar-TN-ReemNeural', lang: 'ar-TN' },
    },
    rate: '+4%',
    rateSteps: ['+8%', '+12%'],
    timing: { lead: 0.45, gap: 0.3, tail: 0.6, firstLead: 0.6 },
    limits: { minS: 480, maxS: 600 },
    ui: {
      title: T('Guide de prise en main', 'دليل الاستعمال'),
      sub: T('Pour l’accueil et le médecin – pas à pas, avec l’application réelle.', 'للاستقبال وللطبيب – خطوة بخطوة، مع التطبيق الحقيقي.'),
      demo: T('Essayez la démo', 'جرّبوا دفتر الآن'),
      chapter: T('Chapitre', 'الفصل'),
      question: T('Une question ?', 'لديكم سؤال؟'),
      feedback: T('Dans Daftar, le bouton « Une idée ? Un problème ? » envoie votre message directement à Omar (sans données de patients).', 'في دفتر، زرّ «فكرة؟ مشكلة؟» يرسل رسالتكم مباشرة إلى عمر (دون بيانات المرضى).'),
      mail: 'info@omarfourati.de',
      url: 'daftar.omarfourati.de',
      price: T('Phase pilote gratuite', 'المرحلة التجريبية مجانية'),
      priceRest: T('ensuite à partir de 29 DT par mois, sans engagement', 'بعدها ابتداءً من 29 د.ت شهريًا، دون التزام'),
    },

    intro: {
      kind: 'intro',
      say: [
        S('Bienvenue dans Daftar. Voici les gestes de tous les jours, pas à pas.', 'مرحبا بيكم في دفتر. هاو الخدمة متاع كل نهار، خطوة بخطوة.'),
        S(`Pour essayer en même temps, ouvrez la démo gratuite sur ${ADDR}.`, 'وباش تجرّبو في نفس الوقت، حلّو الديمو بلاش: سكانيو الكود اللي على الشاشة.'),
      ],
    },

    chapters: [
      { no: 0, title: T('Avant de commencer', 'قبل البدء'), who: T('Pour toute l’équipe', 'لكل الفريق'),
        say: [S('Daftar s’ouvre dans le navigateur, sur PC, tablette ou téléphone. Chacun a son compte et sa langue.', 'دفتر يتحلّ في المتصفّح، على البي سي، التابلات ولا التلفون. وكل واحد عندو الحساب متاعو واللغة متاعو.')],
        steps: [
          { shot: '01-aujourdhui', view: 'page', title: T('Le menu', 'القائمة'), say: [
            S('Sur l’ordinateur, le menu est à gauche : Aujourd’hui, Agenda, Salle d’attente, Patients, Caisse, Rappels et Réglages.', 'على البي سي، القائمة على اليمين: اليوم، المواعيد، قاعة الانتظار، المرضى، الصندوق، التذكيرات، والإعدادات.', F(0, 0.03, 0.1, 0.47)),
            S('En haut : la recherche d’un patient, le rendez-vous par téléphone, et la langue.', 'الفوق: البحث على مريض، «موعد بالهاتف»، واللغة.', F(0.16, 0, 0.76, 0.055)),
          ] },
          { shot: '02-menu-mobile', view: 'mobile', title: T('Sur le téléphone', 'على الهاتف'), say: [
            S('Sur le téléphone, le menu est en bas : Aujourd’hui, Agenda, Salle et Patients.', 'على التلفون، القائمة اللوطة: اليوم، المواعيد، القاعة، والمرضى.', F(0, 0.925, 1, 0.075)),
            S('Le reste est sous Plus : la caisse, les rappels, les réglages.', 'والباقي تحت «المزيد»: الصندوق، التذكيرات، والإعدادات.', F(0.02, 0.13, 0.96, 0.58)),
          ] },
        ] },

      { no: 1, title: T('Installer l’application', 'تثبيت التطبيق'), who: T('Pour toute l’équipe, sur chaque appareil', 'لكل الفريق، على كل جهاز'),
        say: [S('Daftar s’installe comme une application, sans passer par un store.', 'دفتر تثبّتوه كيف أي تطبيق، من غير ستور.')],
        steps: [
          { shot: '03-installer', view: 'page', title: T('Ouvrez l’adresse de votre cabinet', 'افتحوا عنوان عيادتكم'), say: [
            S('Ouvrez l’adresse de votre cabinet, et connectez-vous.', 'حلّو العنوان متاع العيادة، وادخلو للحساب متاعكم.', F(0.515, 0.135, 0.345, 0.115)),
            S('La page Installer l’application montre les étapes pour votre appareil, et un QR code pour l’équipe.', `صفحة «تثبيت التطبيق» تورّيكم الخطوات حسب الجهاز، وكود ${QR} للفريق.`, F(0.515, 0.25, 0.345, 0.68)),
          ] },
          { shot: '03-installer', view: 'page', title: T('Android (Chrome)', 'أندرويد (Chrome)'),
            panel: { icon: 'android', lines: T(['Chrome : menu ⋮', 'Installer l’application', 'Confirmer'], ['Chrome: القائمة ⋮', 'تثبيت التطبيق', 'تأكيد']) }, say: [
            S('Sur Android, avec Chrome : touchez le menu, les trois points en haut.', 'على أندرويد، بكروم: انزلو على القائمة، النقاط الثلاثة الفوق.', F(0.515, 0.62, 0.345, 0.3)),
            S('Puis Installer l’application, et confirmez.', 'ومبعد «تثبيت التطبيق»، وأكّدو.'),
          ] },
          { shot: '03-installer', view: 'page', title: T('iPhone et iPad (Safari)', 'آيفون وآيباد (Safari)'),
            panel: { icon: 'apple', lines: T(['Safari : Partager', 'Sur l’écran d’accueil', 'Ajouter'], ['Safari: المشاركة', 'إضافة إلى الشاشة الرئيسية', 'إضافة']) }, say: [
            S('Sur iPhone, avec Safari : touchez Partager, le carré avec une flèche.', 'على الآيفون، بسفاري: انزلو على «المشاركة»، المربّع اللي فيه فليشة.', F(0.515, 0.62, 0.345, 0.3)),
            S('Choisissez Sur l’écran d’accueil, puis Ajouter.', 'اختارو «إضافة إلى الشاشة الرئيسية»، ومبعد «إضافة».'),
          ] },
          { shot: '03-installer', view: 'page', title: T('Ordinateur (Chrome ou Edge)', 'الحاسوب (Chrome أو Edge)'),
            panel: { icon: 'pc', lines: T(['Icône d’installation', 'dans la barre d’adresse', 'Installer'], ['أيقونة التثبيت', 'في شريط العنوان', 'تثبيت']) }, say: [
            S('Sur l’ordinateur, avec Chrome ou Edge : cliquez sur l’icône d’installation, dans la barre d’adresse.', 'على البي سي، بكروم ولا إيدج: انزلو على علامة التثبيت في بار العنوان.', F(0.515, 0.33, 0.345, 0.24)),
            S('Confirmez avec Installer. Daftar apparaît dans le menu Démarrer.', 'أكّدو بـ«تثبيت»، ودفتر يطلعلكم في قائمة «ابدأ».'),
          ] },
        ] },

      { no: 2, title: T('Premiers pas', 'الخطوات الأولى'), who: T('Pour le titulaire du cabinet, une seule fois', 'لصاحب العيادة، مرة واحدة'),
        say: [S('La carte Premiers pas liste les réglages du début. Chaque ligne se coche toute seule.', 'بطاقة «الخطوات الأولى» فيها الإعدادات متاع البداية، وكل سطر يتشطّب وحدو.')],
        steps: [
          { shot: '07-premiers-pas', view: 'section', title: T('La liste des premiers pas', 'قائمة الخطوات الأولى'), say: [
            S('Touchez une ligne pour aller directement au bon réglage.', 'انزلو على سطر، يهزّكم طول للإعداد المناسب.', F(0, 0.27, 0.5, 0.13)),
            S('Masquer cache la carte quand tout est prêt.', 'و«إخفاء» يخبّي البطاقة كي يكون كل شي حاضر.', F(0.86, 0, 0.14, 0.14)),
          ] },
          { shot: '08-horaires', view: 'page', title: T('Horaires d’ouverture', 'أوقات العمل'), say: [
            S('Réglages, Horaires : pour chaque jour, indiquez les plages. Une pause, ce sont deux plages.', '«الإعدادات»، «المواعيد والإغلاق»: لكل نهار، حطّو الأوقات. وكان فمّا استراحة، فترتين.', F(0.15, 0.33, 0.33, 0.24)),
            S('Copier sur les autres jours, puis Enregistrer les horaires.', '«نسخ إلى بقية الأيام»، ومبعد «حفظ المواعيد».', F(0.22, 0.44, 0.2, 0.06)),
          ] },
          { shot: '09-fermetures', view: 'section', title: T('Congés et jours fériés', 'العطل والأعياد'), say: [
            S('Sous Fermetures exceptionnelles, choisissez Du, Au et le Motif, puis Ajouter la fermeture.', 'تحت «أيام الإغلاق الاستثنائي»، اختارو «من»، «إلى»، و«السبب»، ومبعد «إضافة الإغلاق».', F(0, 0.5, 1, 0.2)),
            S('Ces jours-là, ni rendez-vous, ni réservation en ligne.', 'في النهارات هاذي، لا مواعيد ولا حجز أونلاين.', F(0, 0, 1, 0.27)),
          ] },
          { shot: '10-actes', view: 'page', title: T('Actes et tarifs', 'الخدمات والأسعار'), say: [
            S('Actes et tarifs : le catalogue est déjà rempli. Pour chaque acte : durée, prix, et En ligne.', '«الخدمات والأسعار»: القائمة حاضرة. لكل خدمة: المدّة، السوم، و«عبر الإنترنت».', F(0.58, 0.31, 0.39, 0.48)),
            S('Nouvel acte, pour en ajouter un.', 'و«خدمة جديدة» باش تزيدو وحدة.', F(0.81, 0.2, 0.17, 0.065)),
          ] },
          { shot: '11-praticiens', view: 'page', title: T('Praticiens', 'الأطباء والمعالجون'), say: [
            S('Praticiens : chacun a sa colonne et sa couleur dans l’agenda.', '«الأطباء والمعالجون»: كل واحد عندو العمود واللون متاعو في الأجندة.', F(0.34, 0.25, 0.62, 0.15)),
            S('Un praticien n’a pas besoin de compte.', 'والطبيب ما يلزموش حساب.'),
          ] },
          { shot: '12-equipe-invitation', view: 'section', title: T('Inviter l’équipe', 'دعوة الفريق'), say: [
            S('Équipe, puis Inviter quelqu’un : choisissez le rôle, puis Créer le lien d’invitation.', '«الفريق»، ومبعد «دعوة شخص»: اختارو الدور، ومبعد «إنشاء رابط الدعوة».', F(0, 0.27, 0.42, 0.14)),
            S('Envoyez le lien par WhatsApp. Il est valable sept jours.', 'ابعثو الرابط بالواتساب. يقعد صالح سبعة أيام.', F(0, 0.52, 1, 0.14)),
          ] },
          { shot: '13-reservation-reglages', view: 'page', title: T('Réservation en ligne', 'الحجز عبر الإنترنت'), say: [
            S('Cochez Réservation en ligne activée, choisissez vos règles, puis Enregistrer.', 'علّمو «الحجز عبر الإنترنت مفعّل»، اختارو القواعد، ومبعد «حفظ».', F(0.58, 0.6, 0.4, 0.22)),
            S('En haut : l’adresse de votre page de réservation, à partager, et son QR code.', `الفوق: عنوان صفحة الحجز متاعكم باش تبعثوه، والكود ${QR} متاعها.`, F(0.58, 0.17, 0.4, 0.4)),
          ] },
          { shot: '14-affiche', view: 'page', title: T('L’affiche pour la salle d’attente', 'ملصق قاعة الانتظار'), say: [
            S('Imprimer l’affiche A4 prépare une affiche bilingue, avec le QR code de votre page.', `«طباعة ملصق ${A4}» يحضّرلكم ملصق بالعربي وبالفرنسي، فيه الكود ${QR} متاع الصفحة.`, F(0.3, 0.3, 0.42, 0.7)),
            S('Dans la fenêtre d’impression : A4, marges Aucune, et graphiques d’arrière-plan.', `في نافذة الطباعة: ${A4}، الهوامش «بدون»، وفعّلو «رسومات الخلفية».`, F(0.82, 0.2, 0.16, 0.065)),
          ] },
        ] },

      { no: 3, title: T('Prendre un rendez-vous', 'تسجيل موعد'), who: T('Pour l’accueil', 'للاستقبال'),
        say: [S('Deux façons : au téléphone, ou dans l’agenda. Et jamais deux rendez-vous en même temps.', 'فمّا طريقتين: بالتلفون، ولا في الأجندة. وعمرو ما يحطّ زوز مواعيد في نفس الوقت.')],
        steps: [
          { shot: '15-telephone-numero', view: 'dialog', title: T('Au téléphone : le numéro d’abord', 'بالهاتف: الرقم أولًا'), say: [
            S('Touchez Rendez-vous par téléphone, ou la touche T. Tapez le numéro de l’appelant.', 'انزلو على «موعد بالهاتف»، ولا على حرف <sub alias="تي">T</sub>. واكتبو نومرو اللي يكلّم.', F(0, 0.18, 0.5, 0.15)),
            S('Choisissez le bon patient, ou Nouveau patient avec ce numéro.', 'اختارو المريض الصحيح، ولا «مريض جديد بهذا الرقم».', F(0, 0.33, 0.5, 0.15)),
          ] },
          { shot: '16-telephone-creneaux', view: 'dialog', title: T('L’acte, puis un créneau libre', 'الخدمة، ثم وقت فارغ'), say: [
            S('Choisissez l’acte et, si besoin, le praticien.', 'اختارو الخدمة، والطبيب كان لزم.', F(0, 0.42, 0.5, 0.14)),
            S('À droite, les prochains créneaux libres : un clic réserve le rendez-vous.', 'وبجنبها، أقرب الأوقات الفارغة: كليك وحدة ويتحجز الموعد.', F(0.5, 0.17, 0.5, 0.62)),
          ] },
          { shot: '17-telephone-confirme', view: 'dialog', title: T('Le message de confirmation', 'رسالة التأكيد'), say: [
            S('Le rendez-vous est enregistré, et le message de confirmation est prêt.', 'الموعد تسجّل، ورسالة التأكيد حاضرة.', F(0, 0.1, 1, 0.55)),
            S('Copiez-le, ou envoyez-le par WhatsApp ou SMS.', 'انسخوها، ولا ابعثوها بالواتساب ولا بالإس إم إس.', F(0, 0.66, 0.55, 0.15)),
          ] },
          { shot: '18-agenda-jour', view: 'page', title: T('L’agenda', 'الأجندة'), say: [
            S('L’agenda : Jour ou Semaine, et une colonne par praticien.', 'الأجندة: «يوم» ولا «أسبوع»، وعمود لكل طبيب.', F(0.13, 0.17, 0.86, 0.25)),
            S('La couleur montre le statut. Les demandes en ligne sont en pointillés.', 'اللون يورّي الحالة، والطلبات اللي جات أونلاين بخط متقطّع.', F(0.13, 0.36, 0.86, 0.42)),
          ] },
          { shot: '19-agenda-nouveau', view: 'dialog', title: T('Nouveau rendez-vous dans l’agenda', 'موعد جديد في الأجندة'), say: [
            S('Touchez un créneau libre, cherchez le patient, puis choisissez l’acte : la durée se remplit seule.', 'انزلو على وقت فارغ، لوّجو على المريض، واختارو الخدمة: المدّة تتعمّر وحدها.', F(0, 0.08, 1, 0.2)),
            S('Vérifiez, puis Enregistrer le rendez-vous.', 'ثبّتو، ومبعد «حفظ الموعد».', F(0.5, 0.28, 0.5, 0.72)),
          ] },
          { shot: '20-agenda-conflit', view: 'dialog', title: T('Créneau déjà pris ?', 'الوقت محجوز؟'), say: [
            S('Créneau déjà pris ? Daftar refuse, et propose les prochains créneaux libres.', 'الوقت محجوز؟ دفتر ما يقبلش، ويقترحلكم أقرب الأوقات الفارغة.', F(0.025, 0.83, 0.95, 0.09)),
          ] },
          { shot: '21-agenda-mobile', view: 'mobile', title: T('Sur le téléphone', 'على الهاتف'), say: [
            S('Sur le téléphone, l’agenda du jour s’affiche en liste.', 'على التلفون، مواعيد النهار تطلع في قائمة.', F(0.03, 0.6, 0.95, 0.36)),
            S('Le rendez-vous par téléphone se trouve sous Plus.', 'والموعد بالهاتف تلقاوه تحت «المزيد».', F(0.8, 0.94, 0.2, 0.06)),
          ] },
        ] },

      { no: 4, title: T('Accueil et salle d’attente', 'الاستقبال وقاعة الانتظار'), who: T('Pour l’accueil et le médecin', 'للاستقبال والطبيب'),
        say: [S('Chaque patient reçoit un numéro de ticket. L’écran de la salle n’affiche jamais de nom.', 'كل مريض ياخذ نومرو. وشاشة الصالة عمرها ما تورّي الأسامي.')],
        steps: [
          { shot: '22-rdv-arrive', view: 'dialog', title: T('Le patient arrive', 'وصول المريض'), say: [
            S('Le patient arrive : dans l’agenda, touchez son rendez-vous, puis Arrivé.', 'المريض وصل: في الأجندة، انزلو على الموعد متاعو، ومبعد «وصل».', F(0.47, 0.65, 0.32, 0.16)),
            S('Il reçoit automatiquement un ticket, dans l’ordre d’arrivée.', 'ياخذ وحدو نومرو، حسب الترتيب متاع الوصول.'),
          ] },
          { shot: '23-salle', view: 'page', title: T('La salle d’attente', 'قاعة الانتظار'), say: [
            S('La salle d’attente montre qui est en consultation, et qui attend.', 'قاعة الانتظار تورّيكم شكون في الفحص، وشكون يستنّى.', F(0.18, 0.1, 0.53, 0.55)),
            S('Touchez Appeler : le numéro s’affiche sur l’écran de la salle.', 'انزلو على «مناداة»: النومرو يطلع على شاشة الصالة.', F(0.55, 0.21, 0.43, 0.4)),
          ] },
          { shot: '24-nouveau-ticket', view: 'dialog', title: T('Un patient sans rendez-vous', 'مريض دون موعد'), say: [
            S('Un patient sans rendez-vous ? Nouveau ticket : un patient du cabinet, ou juste un nom.', 'مريض من غير موعد؟ «رقم جديد»: «مريض مسجّل»، ولا «اسم فقط».', F(0.03, 0.2, 0.94, 0.14)),
            S('Puis Donner le ticket.', 'ومبعد «إعطاء الرقم».', F(0.69, 0.82, 0.29, 0.15)),
          ] },
          { shot: '25-ticket-qr', view: 'dialog', title: T('Le ticket sur le téléphone du patient', 'الرقم على هاتف المريض'), say: [
            S('WhatsApp envoie au patient le lien de son ticket.', '«واتساب» يبعث للمريض الرابط متاع النومرو متاعو.', F(0.16, 0.84, 0.25, 0.13)),
            S('Ou il prend le QR code en photo, et suit son tour sur son téléphone.', 'ولا يصوّر الكود، ويتبّع دورو من تلفونو.', F(0.29, 0.12, 0.42, 0.52)),
          ] },
          { shot: '26-patient-suivant', view: 'page', title: T('Patient suivant', 'المريض التالي'), say: [
            S('Patient suivant montre qui passe maintenant, et ensuite.', '«المريض التالي» يورّي شكون يدخل توّا، وشكون بعدو.', F(0.13, 0.15, 0.86, 0.36)),
            S('Appeler le suivant appelle la bonne personne : le patient du rendez-vous, ou le premier arrivé.', '«مناداة التالي» ينادي الصحيح: مولى الموعد، ولا أوّل واحد وصل.', F(0.13, 0.39, 0.22, 0.1)),
          ] },
          { shot: '27-ecran-salle', view: 'tv', title: T('L’écran de la salle', 'شاشة القاعة'), say: [
            S('L’écran de la salle s’affiche sur une télévision ou une tablette, en plein écran.', '«شاشة القاعة» تتحلّ على تلفزة ولا تابلات، في كامل الشاشة.'),
            S('Il se met à jour tout seul, avec des numéros uniquement.', 'وتتبدّل وحدها، وفيها نومروات برك.'),
          ] },
          { shot: '28-ticket-patient', view: 'mobile', title: T('Ce que voit le patient', 'ما يراه المريض'), say: [
            S('Le patient voit son numéro, les personnes avant lui, et l’attente estimée.', 'المريض يشوف النومرو متاعو، قدّاش من واحد قبلو، وقدّاش باش يستنّى.', F(0.03, 0.04, 0.94, 0.53)),
            S('Quand c’est son tour : C’est votre tour, présentez-vous à l’accueil.', 'وكي يجي دورو: «حان دورك! تفضّل إلى الاستقبال».'),
          ] },
        ] },

      { no: 5, title: T('Caisse', 'الصندوق'), who: T('Pour l’accueil – vérification par le titulaire', 'للاستقبال – والمراجعة لصاحب العيادة'),
        say: [S('Daftar enregistre les paiements reçus, et calcule le reste à payer. Il n’encaisse rien lui-même.', 'دفتر يسجّل الخلاص اللي تقبضوه، ويحسب الباقي. وهو بيدو ما يقبض شي.')],
        steps: [
          { shot: '29-dossier-solde', view: 'page', title: T('Les actes et le reste à payer', 'الخدمات والمتبقّي للدفع'), say: [
            S('Dans le dossier du patient, Acte ajoute un acte avec son prix.', 'في ملف المريض، «خدمة» تزيد خدمة بالسوم متاعها.', F(0.13, 0.47, 0.58, 0.53)),
            S('Le solde montre le total, ce qui est payé, et le reste à payer.', 'و«الرصيد» يورّي المجموع، اللي تخلّص، واللي باقي.', F(0.72, 0.14, 0.26, 0.27)),
          ] },
          { shot: '30-paiement', view: 'dialog', title: T('Encaisser un paiement', 'تسجيل دفعة'), say: [
            S('Paiement : le montant, le mode de paiement, puis Enregistrer le paiement.', '«دفعة»: المبلغ، طريقة الخلاص، ومبعد «تسجيل الدفعة».', F(0.02, 0.15, 0.96, 0.22)),
            S('En plusieurs fois ? Enregistrez chaque versement : le reste se met à jour.', 'بالتقسيط؟ سجّلو كل قسط، والباقي يتبدّل وحدو.', F(0.6, 0.86, 0.38, 0.13)),
          ] },
          { shot: '31-recu', view: 'page', title: T('Le reçu', 'الوصل'), say: [
            S('Dans la liste des paiements, Reçu ouvre un reçu, à imprimer avec Imprimer.', 'في قائمة الدفعات، «وصل» يحلّ وصل، تطبعوه بـ«طباعة».', F(0.37, 0.12, 0.42, 0.62)),
          ] },
          { shot: '32-acompte-conseille', view: 'dialog', title: T('Acompte conseillé', 'يُنصح بطلب عربون'), say: [
            S('Après deux absences, le rendez-vous affiche : acompte conseillé.', 'بعد زوز غيابات، الموعد يكتبلكم: يُنصح بطلب عربون.', F(0.015, 0.125, 0.48, 0.08)),
            S('Demander inscrit le montant de l’acompte demandé.', 'و«طلب» يكتب مبلغ العربون.', F(0.5, 0.52, 0.5, 0.12)),
          ] },
          { shot: '33-acompte-encaisse', view: 'dialog', title: T('Encaisser l’acompte', 'استلام العربون'), say: [
            S('Encaisser l’acompte enregistre le paiement, lié au rendez-vous.', '«استلام العربون» يسجّل الخلاص، مربوط بالموعد.', F(0.02, 0.69, 0.96, 0.12)),
          ] },
          { shot: '34-caisse-jour', view: 'page', title: T('La caisse du jour', 'صندوق اليوم'), say: [
            S('La caisse du jour : le total par mode de paiement, et la liste des paiements.', 'صندوق اليوم: المجموع حسب طريقة الخلاص، وقائمة الدفعات.', F(0.18, 0.2, 0.53, 0.8)),
          ] },
          { shot: '35-montants-dus', view: 'section', title: T('Les montants dus', 'المبالغ المستحقّة'), say: [
            S('Plus bas, les montants dus : qui doit encore de l’argent, du plus grand au plus petit.', 'اللوطة، «المبالغ المستحقّة»: شكون مازال عليه فلوس، من الأكبر للأصغر.'),
          ] },
          { shot: '36-cloture', view: 'section', title: T('La clôture du soir', 'غلق الصندوق مساءً'), say: [
            S('Le soir, notez les espèces comptées, puis Clôturer la caisse : Daftar affiche l’écart.', 'في العشيّة، اكتبو الفلوس اللي عدّيتوها، ومبعد «غلق الصندوق»: دفتر يورّيكم الفرق.', F(0.05, 0.43, 0.9, 0.16)),
            S('Le titulaire vérifie ensuite avec Valider la clôture.', 'ومبعد، صاحب العيادة يراجع بـ«المصادقة على الغلق».', F(0.05, 0.66, 0.5, 0.13)),
          ] },
        ] },

      { no: 6, title: T('Rappels', 'التذكيرات'), who: T('Pour l’accueil, la veille', 'للاستقبال، في اليوم السابق'),
        say: [S('Daftar prépare le rappel de chaque rendez-vous du lendemain. C’est vous qui l’envoyez, d’un clic.', 'دفتر يحضّر التذكير لكل موعد متاع غدوة. وإنتوما اللي تبعثوه، بكليك.')],
        steps: [
          { shot: '37-rappels', view: 'page', title: T('Les rappels de demain', 'تذكيرات الغد'), say: [
            S('Le menu Rappels montre les rendez-vous de demain, avec le message prêt.', 'قائمة «التذكيرات» تورّي مواعيد غدوة، والميساج حاضر.', F(0.2, 0.335, 0.38, 0.265)),
            S('Touchez WhatsApp ou SMS : le texte est déjà écrit. Le rappel est noté Envoyé.', 'انزلو على «واتساب» ولا «إرسالية قصيرة»: النص مكتوب. والتذكير يتسجّل «أُرسل».', F(0.2, 0.5, 0.38, 0.11)),
          ] },
          { shot: '38-rappels-mobile', view: 'mobile', title: T('Depuis le téléphone du cabinet', 'من هاتف العيادة'), say: [
            S('Depuis le téléphone du cabinet, WhatsApp ou les SMS s’ouvrent directement.', 'من تلفون العيادة، الواتساب ولا الإس إم إس يتحلّو طول.', F(0.03, 0.31, 0.94, 0.33)),
            S('Les patients sans accord pour les rappels sont grisés.', 'والمرضى اللي ما قبلوش التذكير يطلعو باهتين.', F(0.03, 0.66, 0.94, 0.3)),
          ] },
          { shot: '39-rappels-modele', view: 'section', title: T('Modifier le texte', 'تعديل النص'), say: [
            S('Le texte se modifie dans les Réglages, en français et en arabe.', 'النص تبدّلوه في «الإعدادات»، بالعربي وبالفرنسي.'),
            S('Les mots entre accolades sont remplacés automatiquement.', 'والكلمات اللي بين الأقواس تتبدّل وحدها.', F(0, 0.1, 0.6, 0.13)),
          ] },
        ] },

      { no: 7, title: T('Importer une liste Excel', 'استيراد قائمة Excel'), who: T('Pour le titulaire ou l’assistante, une fois au départ', 'لصاحب العيادة أو المساعِدة، مرة واحدة في البداية'),
        say: [S('Vos patients sont dans Excel ? Daftar les reprend, et rien n’est enregistré avant la fin.', `المرضى متاعكم في ${EXCEL}؟ دفتر ياخذهم، وحتى شي ما يتسجّل قبل الآخر.`)],
        steps: [
          { shot: '40-import-fichier', view: 'page', title: T('Choisir le fichier', 'اختيار الملف'), say: [
            S('Choisissez Des patients ou Des rendez-vous, puis un fichier Excel ou CSV.', `اختارو «مرضى» ولا «مواعيد»، ومبعد ملف ${EXCEL} ولا ${CSV}.`, F(0.18, 0.36, 0.78, 0.43)),
          ] },
          { shot: '41-import-correspondance', view: 'page', title: T('Correspondance des colonnes', 'ربط الأعمدة'), say: [
            S('Pour chaque information, choisissez la colonne de votre fichier. Daftar propose déjà ce qui ressemble.', 'لكل معلومة، اختارو العمود المناسب من الملف متاعكم. دفتر يقترح من قبل اللي يشبهها.', F(0.18, 0.43, 0.78, 0.52)),
            S('Vérifiez, puis Vérifier le fichier.', 'ثبّتو، ومبعد «التحقق من الملف».'),
          ] },
          { shot: '42-import-verification', view: 'page', title: T('Vérification', 'التحقق'), say: [
            S('Daftar montre ce que l’import ferait, et les lignes à corriger.', 'دفتر يورّيكم شنوّة باش يعمل الاستيراد، والسطور اللي لازمها تصليح.', F(0.18, 0.2, 0.78, 0.43)),
            S('Rien n’est encore enregistré. Importer lance l’import.', 'حتى شي ما تسجّل مازال. و«استيراد» يبدا الخدمة.', F(0.8, 0.9, 0.17, 0.07)),
          ] },
          { shot: '43-import-termine', view: 'page', title: T('Import terminé', 'انتهى الاستيراد'), say: [
            S('Import terminé. Téléchargez le rapport si besoin.', 'الاستيراد كمل. نزّلو التقرير كان تحبّو.', F(0.18, 0.27, 0.42, 0.18)),
            S('Gardez la correspondance comme modèle, pour le prochain fichier.', 'واحفظو الربط كنموذج، للملف الجاي.', F(0.18, 0.45, 0.78, 0.17)),
          ] },
        ] },

      { no: 8, title: T('Réservation en ligne côté patient', 'الحجز عبر الإنترنت من جهة المريض'), who: T('Pour vos patients – à connaître à l’accueil', 'لمرضاكم – ومن المفيد أن يعرفه الاستقبال'),
        say: [S('Vos patients réservent sur la page de votre cabinet, à toute heure, et sans créer de compte.', 'المرضى متاعكم يحجزو من صفحة العيادة، في أي وقت، ومن غير ما يعملو حساب.')],
        steps: [
          { shot: '44-reservation-choix', view: 'mobile', title: T('Choisir l’acte et l’heure', 'اختيار الخدمة والساعة'), say: [
            S('Le patient choisit l’acte, le praticien, le jour et un horaire, puis Continuer.', 'المريض يختار الخدمة، الطبيب، النهار والساعة، ومبعد «متابعة».', F(0.03, 0.45, 0.94, 0.45)),
            S('Seuls les horaires libres sont affichés.', 'وما يطلعلو كان الأوقات الفارغة.'),
          ] },
          { shot: '45-reservation-coordonnees', view: 'mobile', title: T('Ses coordonnées', 'معلوماته'), say: [
            S('Il indique son prénom, son nom et son téléphone, et peut demander un rappel la veille.', 'يكتب الاسم، اللقب والتلفون، وينجّم يطلب تذكير نهار قبل.', F(0.03, 0.14, 0.94, 0.6)),
            S('Puis Réserver ce rendez-vous.', 'ومبعد «احجز هذا الموعد».', F(0.03, 0.8, 0.94, 0.08)),
          ] },
          { shot: '46-reservation-envoyee', view: 'mobile', title: T('Son lien personnel', 'رابطه الشخصي'), say: [
            S('Demande envoyée. Le patient garde son lien personnel, et peut l’envoyer par WhatsApp.', '«تمّ إرسال الطلب». والمريض يخبّي الرابط متاعو، وينجّم يبعثو بالواتساب.', F(0.03, 0.46, 0.94, 0.5)),
          ] },
          { shot: '47-rdv-annuler', view: 'mobile', title: T('Annuler par le lien', 'الإلغاء عبر الرابط'), say: [
            S('Avec son lien, le patient peut annuler. Le créneau est libéré pour un autre patient.', 'بالرابط متاعو، المريض ينجّم يبطّل الموعد. والوقت يتحرّر لمريض آخر.', F(0, 0.72, 1, 0.28)),
            S('Après le délai minimum que vous avez choisi, il appelle le cabinet.', 'وبعد المهلة اللي اخترتوها، يكلّم العيادة.'),
          ] },
          { shot: '48-demandes-en-ligne', view: 'section', title: T('Au cabinet : confirmer la demande', 'في العيادة: تأكيد الطلب'), say: [
            S('Les demandes arrivent sur la page Aujourd’hui, et en pointillés dans l’agenda.', 'الطلبات توصل لصفحة «اليوم»، وبخط متقطّع في الأجندة.', F(0, 0, 1, 0.14)),
            S('Confirmer ou Refuser, puis Prévenir par WhatsApp : le texte est prêt.', '«تأكيد» ولا «رفض»، ومبعد «إعلام عبر واتساب»: النص حاضر.', F(0, 0.2, 0.42, 0.13)),
          ] },
        ] },
    ],

    outro: {
      kind: 'outro',
      say: [
        S('Une question ? Le bouton Une idée, un problème, dans Daftar, écrit directement à Omar.', 'عندكم سؤال؟ الزر «فكرة؟ مشكلة؟» في دفتر يبعث الميساج طول لعمر.'),
        S('Phase pilote gratuite, puis dès vingt-neuf dinars par mois. À bientôt sur Daftar !', 'الفترة التجريبية بلاش، ومن بعد من تسعة وعشرين دينار في الشهر. نتلاقاو في دفتر!'),
      ],
      timing: { tail: 3 },
    },
  };

  /** Szenenliste: Intro, je Kapitel Kapiteltafel + Schritte, Outro */
  tut.scenes = [tut.intro];
  tut.chapters.forEach((c) => {
    tut.scenes.push({ kind: 'chapter', chapter: c, say: c.say });
    c.steps.forEach((st, i) => tut.scenes.push(Object.assign({ kind: 'step', chapter: c, n: i + 1 }, st)));
  });
  tut.scenes.push(tut.outro);

  root.DAFTAR_TUTORIEL = tut;
})(typeof window !== 'undefined' ? window : globalThis);
