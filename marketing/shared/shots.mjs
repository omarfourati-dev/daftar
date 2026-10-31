// Liste aller Screenshots für Tutorial und Video – eine Quelle für
//   tutorial/build.mjs  (Platzhalter erzeugen, prüfen, ob alle Bilder da und echt sind),
//   video/render.mjs    (Platzhalter der Video-Aufnahmen),
//   video/capture.mjs   (echte Aufnahmen nach dem Deploy; jede id hat dort einen Ablauf).
//
// Dateinamen: tutorial/shots/<id>-<fr|ar>.png  und  video/shots/<id>-<fr|ar>.png
// view:  desktop = 1440 x 900 CSS-px, Faktor 1.25 · mobile = 390 x 844, Faktor 2 (Android-Chrome) · tv = 1920 x 1080
// crop:  page = ganzer Bildschirm · dialog = nur das offene Fenster (role=dialog) · section = nur der genannte Abschnitt
// mode:  auto = capture.mjs nimmt es auf · manual = von Hand auf einem echten Gerät fotografieren (Browser-Menüs
//        kann Playwright nicht zeigen)
// size:  ungefähre Größe in CSS-px für Platzhalter von Ausschnitten (die echten Bilder dürfen abweichen)
// state: was genau zu sehen sein muss (für Platzhalter, Storyboard und die Kontrolle nach der Aufnahme)

export const VIEWPORTS = {
  desktop: { width: 1440, height: 900, deviceScaleFactor: 1.25 },
  mobile: {
    width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true,
    userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Mobile Safari/537.36',
  },
  tv: { width: 1920, height: 1080, deviceScaleFactor: 1 },
};

const S = (id, view, crop, state, extra = {}) => ({ id, view, crop, mode: 'auto', state, ...extra });
const M = (id, view, state, extra = {}) => ({ id, view, crop: 'page', mode: 'manual', state, ...extra });

export const TUTORIAL_SHOTS = [
  // 0 – Avant de commencer
  S('01-aujourdhui', 'desktop', 'page', '„Aujourd’hui“ (/app) der Demo-Praxis: Seitenleiste links (Aujourd’hui, Agenda, Salle d’attente, Patients, Caisse, Rappels …), Kacheln des Tages, Karte „Premiers pas“.'),
  S('02-menu-mobile', 'mobile', 'page', 'Handy, „Aujourd’hui“, untere Leiste sichtbar, Menü „Plus“ geöffnet (Rendez-vous par téléphone, Rechercher un patient, Caisse, Rappels, Réglages …).'),
  // 1 – Installer l'application
  S('03-installer', 'desktop', 'page', '/app/installer: „Installer l’application“, Schritte „Sur cet appareil“, QR-Code „Pour les téléphones de l’équipe“.'),
  M('04-installer-android', 'mobile', 'Echtes Android-Handy, Chrome auf https://<slug>.daftar.omarfourati.de/app (angemeldet), Menü ⋮ offen, „Installer l’application“ / „تثبيت التطبيق“ sichtbar (Handy auf FR bzw. AR).'),
  M('05-installer-iphone', 'mobile', 'Echtes iPhone, Safari auf https://<slug>.daftar.omarfourati.de/app, Teilen-Menü offen, Eintrag „Sur l’écran d’accueil“ / „إضافة إلى الشاشة الرئيسية“ sichtbar.'),
  M('06-installer-pc', 'desktop', 'Windows-PC, Chrome oder Edge auf https://<slug>.daftar.omarfourati.de/app, Installieren-Symbol in der Adressleiste angeklickt, Dialog mit Knopf „Installer“ sichtbar (Ausschnitt obere Bildschirmhälfte).'),
  // 2 – Premiers pas
  S('07-premiers-pas', 'desktop', 'section', 'Karte „Premiers pas“ auf „Aujourd’hui“ mit den 8 Schritten (Horaires d’ouverture … Imprimer l’affiche) und Fortschritt „x sur 8 terminés“.', { size: [1100, 420] }),
  S('08-horaires', 'desktop', 'page', 'Réglages → Horaires & fermetures: Wochentage mit Plages 08:00–12:30 und 14:00–18:00, Dimanche „Fermé“, Knopf „Enregistrer les horaires“.'),
  S('09-fermetures', 'desktop', 'section', 'Réglages → Horaires & fermetures, Abschnitt „Fermetures exceptionnelles“ mit Feldern Du / Au / Motif und Knopf „Ajouter la fermeture“.', { size: [1000, 380] }),
  S('10-actes', 'desktop', 'page', 'Réglages → Actes & tarifs: Liste der Leistungen der Demo (Consultation, Contrôle …) mit Dauer, Preis, „En ligne“, Knopf „Nouvel acte“.'),
  S('11-praticiens', 'desktop', 'page', 'Réglages → Praticiens: zwei Behandler der Demo mit Farbe, „Actif“, „Réservable en ligne“, Knopf „Nouveau praticien“.'),
  S('12-equipe-invitation', 'desktop', 'section', 'Réglages → Équipe, Abschnitt „Inviter quelqu’un“ nach Klick auf „Créer le lien d’invitation“ (Rolle Assistant(e)): Link mit „Copier“ und „Envoyer par WhatsApp“.', { size: [1000, 420] }),
  S('13-reservation-reglages', 'desktop', 'page', 'Réglages → Réservation en ligne: „Votre page de réservation“ mit Link, QR-Code, „Imprimer l’affiche A4“, darunter „Réservation en ligne activée“ und die Grenzen.'),
  S('14-affiche', 'desktop', 'page', 'Réglages → Affiche A4 (/app/reglages/affiche): Vorschau des Plakats FR+AR mit QR-Code, Knopf „Imprimer l’affiche“.'),
  // 3 – Prendre un rendez-vous
  S('15-telephone-numero', 'desktop', 'dialog', 'Fenster „Rendez-vous par téléphone“: Nummer 00 000 001 eingetippt, gefundener Patient ausgewählt (blaue Karte mit Name und Nummer).', { size: [900, 560] }),
  S('16-telephone-creneaux', 'desktop', 'dialog', 'Gleiches Fenster: Acte / consultation gewählt, rechts „Prochains créneaux libres“ nach Tagen (Aujourd’hui, Demain …).', { size: [900, 620] }),
  S('17-telephone-confirme', 'desktop', 'dialog', 'Nach Klick auf einen Termin: grüne Meldung „Rendez-vous enregistré : …“, Feld „Message de confirmation“, Knöpfe „Copier le texte“, WhatsApp, SMS.', { size: [900, 480] }),
  S('18-agenda-jour', 'desktop', 'page', 'Agenda, Ansicht „Jour“, heute, eine Spalte je Praxis-Behandler, farbige Termine, Pause 12:30–14:00, Linie „Maintenant“.'),
  S('19-agenda-nouveau', 'desktop', 'dialog', 'Fenster „Nouveau rendez-vous“: Patient ausgewählt, Acte / consultation, Date, Heure, Praticien ausgefüllt, Knopf „Enregistrer le rendez-vous“.', { size: [760, 760] }),
  S('20-agenda-conflit', 'desktop', 'dialog', 'Fenster „Nouveau rendez-vous“ nach dem Speichern auf eine belegte Zeit: „Ce créneau est déjà pris.“ und „Prochains créneaux libres :“ mit Vorschlägen.', { size: [760, 520] }),
  S('21-agenda-mobile', 'mobile', 'page', 'Handy, Agenda von heute als Liste.'),
  // 4 – Accueil et salle d'attente
  S('22-rdv-arrive', 'desktop', 'dialog', 'Ein kommender Termin von heute geöffnet: Uhrzeit, Patient, Knöpfe „Ouvrir le dossier“, „Appeler“, WhatsApp und unter „Statut“ der Knopf „Arrivé“.', { size: [640, 560] }),
  S('23-salle', 'desktop', 'page', 'Salle d’attente: Abschnitte „En consultation“, „En attente“ (Ticketnummern, Position, Wartezeit, Knöpfe Appeler / WhatsApp / QR code), rechts die Vorschau „Écran de la salle d’attente“.'),
  S('24-nouveau-ticket', 'desktop', 'dialog', 'Fenster „Nouveau ticket“ mit „Patient du cabinet“ / „Juste un nom“ und Knopf „Donner le ticket“.', { size: [640, 440] }),
  S('25-ticket-qr', 'desktop', 'dialog', 'Fenster „Ticket n“ mit großem QR-Code und Hinweis „Le patient prend ce code en photo …“.', { size: [560, 560] }),
  S('26-patient-suivant', 'desktop', 'page', '/app/salle/suivant: große Anzeige „Maintenant“ / „Ensuite“, Knopf „Appeler le suivant“.'),
  S('27-ecran-salle', 'tv', 'page', 'Bildschirm der Wartezone /salle/<token> im Vollbild: „Ticket appelé“ mit großer Nummer, „Prochains tickets“, keine Namen.'),
  S('28-ticket-patient', 'mobile', 'page', 'Handy des Patienten, /ticket/<token>: Ticketnummer, „Personnes avant vous“, „Attente estimée“.'),
  // 5 – Caisse
  S('29-dossier-solde', 'desktop', 'page', 'Patientenakte (Patient mit Ratenzahlung), Reiter „Actes et paiements“: Actes, Paiements, Solde mit Total des actes / Payé / Reste à payer.'),
  S('30-paiement', 'desktop', 'dialog', 'Fenster „Nouveau paiement“: Montant (DT) ausgefüllt, Mode de paiement „Espèces“, Date, Kästchen „C’est un acompte pour un rendez-vous“.', { size: [600, 520] }),
  S('31-recu', 'desktop', 'page', 'Druckbare Quittung /app/recu/<id>: „Reçu n° …“, Patient, Montant reçu, Mode de paiement, Knopf „Imprimer“.'),
  S('32-acompte-conseille', 'desktop', 'dialog', '„Nouveau rendez-vous“ für einen Patienten mit 2 Absences: gelber Hinweis „2 absences : acompte conseillé.“ und Knopf „Demander …“.', { size: [760, 640] }),
  S('33-acompte-encaisse', 'desktop', 'dialog', 'Termin mit Anzahlung geöffnet: Zeile „Acompte – … payé sur …“ (bzw. Knopf „Encaisser l’acompte“).', { size: [640, 560] }),
  S('34-caisse-jour', 'desktop', 'page', 'Caisse, heute: „Encaissé ce jour“, „Par mode de paiement“, „Paiements du jour“ mit Reçu-Links.'),
  S('35-montants-dus', 'desktop', 'section', 'Caisse, Abschnitt „Montants dus“: Patienten mit offenem Betrag, „Total dû“, „Dernier paiement“.', { size: [1100, 480] }),
  S('36-cloture', 'desktop', 'section', 'Caisse von gestern, Abschnitt „Clôture de caisse“: Espèces attendues / comptées, „Manque 1,000 DT“, „En attente de validation“, Knopf „Valider la clôture“.', { size: [1100, 420] }),
  // 6 – Rappels
  S('37-rappels', 'desktop', 'page', 'Rappels, nächster Tag mit Terminen: je Patient Uhrzeit, fertige Nachricht, Knöpfe WhatsApp / SMS; ein Patient ohne Einwilligung ausgegraut.'),
  S('38-rappels-mobile', 'mobile', 'page', 'Handy, Rappels mit den ersten zwei Patienten und den Knöpfen WhatsApp / SMS.'),
  S('39-rappels-modele', 'desktop', 'section', 'Réglages → Cabinet, Abschnitt „Messages de rappel“ mit den Vorlagen FR und AR und den Variablen.', { size: [1000, 460] }),
  // 7 – Importer
  S('40-import-fichier', 'desktop', 'page', '/app/import, Schritt „Fichier“: „Que voulez-vous importer ?“ (Des patients), Ablagefeld „Déposez votre fichier ici“, Knopf „Choisir un fichier“. (Demo: Antworten des Servers nachgestellt, siehe capture.mjs)'),
  S('41-import-correspondance', 'desktop', 'page', 'Schritt „Correspondance“: je Daftar-Feld eine Spalte der Datei mit Beispielen (Nom, Prénom, Téléphone …), Optionen, Knopf „Vérifier le fichier“.'),
  S('42-import-verification', 'desktop', 'page', 'Schritt „Vérification“: Zähler (à créer, ignorées, en erreur), Tabelle „Lignes à corriger“, Knopf „Importer n ligne(s)“.'),
  S('43-import-termine', 'desktop', 'page', 'Schritt „Import“: „Import terminé“, Zähler, „Télécharger le rapport (CSV)“, „Garder cette correspondance pour le prochain fichier“.'),
  // 8 – Réservation en ligne côté patient
  S('44-reservation-choix', 'mobile', 'page', 'Handy, Buchungsseite der Praxis: Acte gewählt, Tag gewählt, freie Uhrzeiten, eine Uhrzeit markiert, Knopf „Continuer“ sichtbar.'),
  S('45-reservation-coordonnees', 'mobile', 'page', 'Handy, „Vos coordonnées“ ausgefüllt (erfundener Name, Nummer +216 00 000 0xx), Kästchen Rappel, Knopf „Réserver ce rendez-vous“.'),
  S('46-reservation-envoyee', 'mobile', 'page', 'Handy, „Demande envoyée“ (oder „Rendez-vous confirmé“) mit „Votre lien personnel“, Copier / Envoyer par WhatsApp, „Voir mon rendez-vous“.'),
  S('47-rdv-annuler', 'mobile', 'page', 'Handy, /rdv#…: „Votre rendez-vous“, Status, Knopf „Annuler ce rendez-vous“ mit geöffneter Rückfrage „Oui, annuler“.'),
  S('48-demandes-en-ligne', 'desktop', 'section', '„Aujourd’hui“, Abschnitt „Nouvelles demandes en ligne“ mit Knöpfen Confirmer / Refuser.', { size: [1100, 420] }),
];

// Video: immer der ganze Bildschirm (die Szenen setzen ihn in einen Browser- bzw. Handyrahmen).
export const VIDEO_SHOTS = [
  S('v01-agenda-desktop', 'desktop', 'page', 'Agenda „Jour“ von heute, zwei Behandler-Spalten, viele Termine, Linie „Maintenant“ (wie 18-agenda-jour).'),
  S('v02-agenda-mobile', 'mobile', 'page', 'Handy, Agenda von heute als Liste (wie 21-agenda-mobile).'),
  S('v03-telephone-desktop', 'desktop', 'page', 'Ganzer Bildschirm mit offenem Fenster „Rendez-vous par téléphone“: Patient gefunden, „Prochains créneaux libres“ sichtbar.'),
  S('v04-reservation-mobile', 'mobile', 'page', 'Handy, Buchungsseite: Acte, Tag und Uhrzeit gewählt (wie 44-reservation-choix).'),
  S('v05-demandes-desktop', 'desktop', 'page', '„Aujourd’hui“ mit „Nouvelles demandes en ligne“ (Confirmer / Refuser) im Bild.'),
  S('v06-salle-desktop', 'desktop', 'page', 'Salle d’attente mit Tickets und Vorschau des Bildschirms (wie 23-salle).'),
  S('v07-ecran-tv', 'tv', 'page', 'Bildschirm der Wartezone /salle/<token> (wie 27-ecran-salle).'),
  S('v08-ticket-mobile', 'mobile', 'page', 'Handy des Patienten, Ticket-Seite (wie 28-ticket-patient).'),
  S('v09-rappels-mobile', 'mobile', 'page', 'Handy, Rappels mit Knöpfen WhatsApp / SMS (wie 38-rappels-mobile).'),
  S('v11-caisse-desktop', 'desktop', 'page', 'Caisse von heute (wie 34-caisse-jour).'),
  S('v12-aujourdhui-mobile', 'mobile', 'page', 'Handy, „Aujourd’hui“ mit Kacheln (ohne geöffnetes Menü).'),
  S('v13-dossier-mobile', 'mobile', 'page', 'Handy, Patientenakte (Patient mit Ratenzahlung), Reiter „Actes et paiements“, Solde mit „Reste à payer“ im Bild.'),
];

export const LANGS = ['fr', 'ar'];

/** Pixelgröße eines Platzhalters bzw. einer Aufnahme. */
export function pixelSize(shot) {
  const v = VIEWPORTS[shot.view];
  const [w, h] = shot.crop === 'page' ? [v.width, v.height] : shot.size ?? [v.width, v.height];
  return { width: Math.round(w * v.deviceScaleFactor), height: Math.round(h * v.deviceScaleFactor), css: [w, h] };
}
