// Echte Screenshots für Tutorial und Video aus der Live-App – NACH dem Deploy ausführen.
//
//   $env:BASE = "https://app.daftar.omarfourati.de"; node capture.mjs        (PowerShell, im Ordner video)
//   node capture.mjs --lang ar                     nur Arabisch
//   node capture.mjs --only 18-agenda-jour,v01-agenda-desktop
//   node capture.mjs --headed                      Browser sichtbar (zum Zuschauen/Fehlersuchen)
//   node capture.mjs --list                        nur die Liste der Aufnahmen zeigen, nichts öffnen
//
// Ablauf je Sprache: Landing (BASE ohne „app.“, FR „/“, AR „/ar/“) öffnen wie ein Besucher → „Essayer la démo“ /
// „جرّبوا دفتر الآن“ → Fachrichtung Médecine générale (zwei Behandler) → „Lancer la démo“. Die Demo-Praxis enthält nur
// erfundene Daten (Telefonnummern +216 00 000 0xx gibt es nicht) und wird nach 24 h gelöscht. Pro Lauf entstehen
// zwei Demos (Grenze des Servers: 5 je IP und Stunde).
// Dann alle Bildschirme in Desktop (1440 x 900), Handy (390 x 844, Android) und TV (1920 x 1080) – Dateien:
//   ../tutorial/shots/<id>-<lang>.png   (Tutorial, Liste in ../shared/shots.mjs)
//   ./shots/<id>-<lang>.png             (Video, ids v01…)
// Platzhalter werden überschrieben, damit build.mjs/render.mjs sie als echt erkennen.
//
// Was die Aufnahme in der Demo verändert (nur in der eigenen Demo-Praxis): ein Termin per Telefon-Schnellbuchung,
// ein Einladungslink (in Demos entsteht nie ein Konto), eine Online-Buchung über die Buchungsseite mit erfundenem
// Namen und Nummer +216 00 000 0xx (für „Nouvelles demandes en ligne“). Nichts wird an Patienten gesendet (in Demos
// öffnen die WhatsApp/SMS-Knöpfe nichts).
// Import (40–43): Demos erlauben keinen Import (403). Die Bilder zeigen die echte Importseite; nur die Antworten von
// /api/imports* und isDemo werden in diesem einen Tab nachgestellt (erfundene Excel-Datei, nichts geht an den Server).
// Alles außer BASE, der Landing und <slug>.<domain> wird blockiert (keine Werbung/Tracker, keine fremden Aufrufe).
// Das Anmelde-Token der Demo bleibt im Browser; das Skript liest oder schreibt es nie.

import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { args, need } from '../shared/lib.mjs';
import { TUTORIAL_SHOTS, VIDEO_SHOTS, VIEWPORTS } from '../shared/shots.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const opt = args();
const BASE = (process.env.BASE || opt.base || 'https://app.daftar.omarfourati.de').replace(/\/+$/, '');
const LANDING = (process.env.LANDING || opt.landing || BASE.replace('://app.', '://')).replace(/\/+$/, '');
const BASE_URL = new URL(BASE);
const DOMAIN = BASE_URL.hostname.replace(/^app\./, '');
const langs = opt.lang ? [opt.lang] : ['fr', 'ar'];
const only = opt.only ? new Set(String(opt.only).split(',').map((s) => s.trim())) : null;
const ALL = [...TUTORIAL_SHOTS, ...VIDEO_SHOTS];
const byId = Object.fromEntries(ALL.map((s) => [s.id, s]));
const want = (id) => byId[id]?.mode !== 'manual' && (!only || only.has(id));

/** Chooses a visually hidden radio by clicking its visible label, like a person; checks that it is chosen. */
async function pick(radio) {
  await radio.locator('xpath=ancestor::label[1]').click();
  if (!(await radio.isChecked())) await radio.evaluate((el) => el.click());
  if (!(await radio.isChecked())) throw new Error('radio not chosen');
}
const DIR = { tutorial: join(here, '..', 'tutorial', 'shots'), video: join(here, 'shots') };
mkdirSync(DIR.tutorial, { recursive: true });
mkdirSync(DIR.video, { recursive: true });

if (opt.list) {
  for (const s of ALL) console.log(`${s.mode === 'manual' ? 'von Hand' : 'auto    '}  ${s.id.padEnd(28)} ${s.view.padEnd(8)} ${s.state}`);
  process.exit(0);
}

// Texte der App (web/src/lib/i18n/fr|ar), für Knöpfe und Felder
const L = {
  fr: {
    landingPath: '/', demoStart: 'Lancer la démo', phone: 'Rendez-vous par téléphone', plus: 'Plus', newTicket: 'Nouveau ticket',
    qr: 'QR code', tabMoney: 'Actes et paiements', addPayment: 'Paiement', amount: 'Montant (DT)', cancel: 'Annuler', close: 'Fermer',
    inviteCreate: 'Créer le lien d’invitation', nextDay: 'Jour suivant', continue: 'Continuer', firstName: 'Prénom', lastName: 'Nom',
    phoneLabel: 'Téléphone', submitBooking: 'Réserver ce rendez-vous', openManage: 'Voir mon rendez-vous', cancelBooking: 'Annuler ce rendez-vous',
    check: 'Vérifier le fichier', browse: 'Choisir un fichier', importN: /^Importer \d/, save: 'Enregistrer le rendez-vous',
    conflict: 'Ce créneau est déjà pris.', date: 'Date', time: 'Heure', practitioner: 'Praticien', service: 'Acte / consultation',
    booked: 'Rendez-vous enregistré', nextSlotDay: 'Voir le jour suivant', bookedTitle: /Demande envoyée|Rendez-vous confirmé/,
    sample: { first: 'Nour', last: 'Exemple' },
  },
  ar: {
    landingPath: '/ar/', demoStart: 'بدء النسخة التجريبية', phone: 'موعد بالهاتف', plus: 'المزيد', newTicket: 'رقم جديد',
    qr: 'رمز QR', tabMoney: 'الخدمات والدفعات', addPayment: 'دفعة', amount: 'المبلغ (د.ت)', cancel: 'إلغاء', close: 'إغلاق',
    inviteCreate: 'إنشاء رابط الدعوة', nextDay: 'اليوم التالي', continue: 'متابعة', firstName: 'الاسم', lastName: 'اللقب',
    phoneLabel: 'الهاتف', submitBooking: 'احجز هذا الموعد', openManage: 'عرض موعدي', cancelBooking: 'إلغاء هذا الموعد',
    check: 'التحقق من الملف', browse: 'اختيار ملف', importN: /^استيراد \d/, save: 'حفظ الموعد',
    conflict: 'هذا الوقت محجوز.', date: 'التاريخ', time: 'الساعة', practitioner: 'الطبيب', service: 'الخدمة / الاستشارة',
    booked: 'تم حفظ الموعد', nextSlotDay: 'عرض اليوم التالي', bookedTitle: /تمّ إرسال الطلب|تمّ تأكيد الموعد/,
    sample: { first: 'نور', last: 'مثال' },
  },
};

const { chromium } = need('playwright');
const browser = await chromium.launch({ headless: !opt.headed });
const done = [];
const failed = [];

function allowed(url) {
  try {
    const u = new URL(url);
    if (u.protocol === 'data:' || u.protocol === 'blob:' || u.protocol === 'about:') return true;
    const h = u.hostname;
    return h === BASE_URL.hostname || h === new URL(LANDING).hostname || h === DOMAIN || h.endsWith('.' + DOMAIN);
  } catch { return false; }
}

async function newContext(view, lang, storageState) {
  const v = VIEWPORTS[view];
  const ctx = await browser.newContext({
    viewport: { width: v.width, height: v.height }, deviceScaleFactor: v.deviceScaleFactor, isMobile: !!v.isMobile, hasTouch: !!v.hasTouch,
    userAgent: v.userAgent, locale: lang === 'ar' ? 'ar-TN' : 'fr-FR', timezoneId: 'Africa/Tunis', storageState,
  });
  await ctx.route('**/*', (route) => (allowed(route.request().url()) ? route.continue() : route.abort()));
  return ctx;
}

async function settle(page, ms = 700) {
  await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
  await page.evaluate(() => document.fonts.ready).catch(() => {});
  await page.waitForFunction(() => !document.querySelector('[aria-busy="true"]'), null, { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(ms);
}

async function go(page, path) {
  await page.goto(path.startsWith('http') ? path : BASE + path, { waitUntil: 'domcontentloaded' });
  await settle(page);
}

/** JSON aus der API, im Browser mit dem dort gespeicherten Token (das Token verlässt die Seite nie). */
async function api(page, path) {
  return page.evaluate(async (p) => {
    const res = await fetch(p, { headers: { Authorization: 'Bearer ' + localStorage.getItem('daftar.token') } });
    if (!res.ok) throw new Error(`${p} → ${res.status}`);
    return res.json();
  }, path);
}

function file(id, lang) {
  return join(/^v\d/.test(id) ? DIR.video : DIR.tutorial, `${id}-${lang}.png`);
}

async function shot(target, id, lang, opts = {}) {
  if (!want(id)) return;
  const path = file(id, lang);
  const isPage = typeof target.screenshot === 'function' && typeof target.goto === 'function';
  if (isPage) {
    await target.screenshot({ path, animations: 'disabled', caret: 'hide' });
  } else {
    await target.scrollIntoViewIfNeeded();
    const page = target.page();
    await page.waitForTimeout(250);
    const box = await target.boundingBox();
    if (opts.maxHeight && box && box.height > opts.maxHeight) {
      await page.screenshot({ path, animations: 'disabled', caret: 'hide', clip: { x: box.x, y: box.y, width: box.width, height: opts.maxHeight } });
    } else {
      await target.screenshot({ path, animations: 'disabled', caret: 'hide' });
    }
  }
  done.push(`${id}-${lang}`);
  console.log(`  OK ${id}-${lang}.png`);
}

async function step(ids, lang, fn) {
  const list = [ids].flat();
  if (!list.some(want)) return;
  try {
    await fn();
  } catch (e) {
    for (const id of list.filter(want)) if (!done.includes(`${id}-${lang}`)) failed.push(`${id}-${lang}: ${e.message.split('\n')[0]}`);
    console.log(`  FEHLER ${list.join(', ')} (${lang}): ${e.message.split('\n')[0]}`);
  }
}

const dialog = (page) => page.getByRole('dialog').last();
const section = (page, headingId) => page.locator(`section[aria-labelledby="${headingId}"]`);
const tunisDay = (offset = 0) => {
  const d = new Date(Date.now() + offset * 86400000);
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Tunis', year: 'numeric', month: '2-digit', day: '2-digit' }).format(d);
};
const hhmm = (iso) => new Intl.DateTimeFormat('fr-FR', { timeZone: 'Africa/Tunis', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(iso));
const isSunday = (day) => new Date(day + 'T12:00:00Z').getUTCDay() === 0;

// ======================================================================================================
for (const lang of langs) {
  const t = L[lang];
  console.log(`\n=== ${lang.toUpperCase()} – Demo über ${LANDING}${t.landingPath} ===`);

  // ---------- Demo starten, wie ein Besucher ----------
  const desk = await newContext('desktop', lang);
  const page = await desk.newPage();
  try {
    await page.goto(LANDING + t.landingPath, { waitUntil: 'domcontentloaded' });
  } catch (e) {
    console.error(`Landing nicht erreichbar (${LANDING}${t.landingPath}): ${e.message.split('\n')[0]}`);
    process.exitCode = 1;
    break;
  }
  const cta = page.locator('.hero-actions a.btn-primary');
  const href = await cta.getAttribute('href');
  const target = new URL(href, LANDING);
  if (target.origin === BASE_URL.origin) {
    await cta.click();
  } else {
    // Landing verweist auf eine andere App-Adresse (z. B. beim Test gegen eine lokale Instanz): gleicher Pfad auf BASE
    console.log(`  Hinweis: Landing verlinkt ${target.origin}, öffne ${BASE}${target.pathname}${target.search}`);
    await page.goto(BASE + target.pathname + target.search);
  }
  await page.waitForURL(/\/app\/demo/, { timeout: 20000 });
  await page.getByRole('button', { name: t.demoStart }).click();
  try {
    await page.waitForURL((u) => /\/app\/?$/.test(u.pathname), { timeout: 30000 });
  } catch {
    const alert = await page.locator('[role=alert]').textContent().catch(() => '');
    console.error(`Demo ließ sich nicht starten${alert ? `: ${alert}` : ''}. (Grenze: 5 Demos je IP und Stunde)`);
    process.exitCode = 1;
    break;
  }
  await settle(page, 1200);

  // ---------- Daten der Demo ----------
  const practice = await api(page, '/api/practice');
  const patients = (await api(page, '/api/patients?q=&limit=100&offset=0')).items;
  const byPhone = (n) => patients.find((p) => p.phone === `+21600000${String(n).padStart(3, '0')}`);
  const planPatient = byPhone(1);                                   // Ratenzahlung (Spec: PLAN_PATIENT)
  const unreliable = patients.find((p) => p.noShows >= 2) ?? byPhone(5); // 2 Absences → Acompte conseillé
  const today = tunisDay(0);
  const agendaDay = isSunday(today) ? tunisDay(1) : today;
  const appts = await api(page, `/api/appointments?from=${today}&to=${tunisDay(7)}`);
  const now = Date.now();
  const upcomingToday = appts.find((a) => a.startsAt.slice(0, 10) === today && ['scheduled', 'confirmed'].includes(a.status) && new Date(a.startsAt).getTime() > now + 10 * 60000)
    ?? appts.find((a) => ['scheduled', 'confirmed'].includes(a.status) && new Date(a.startsAt).getTime() > now);
  const withDeposit = appts.find((a) => a.depositRequiredMillimes > 0 && a.status !== 'cancelled');
  const taken = appts.find((a) => a.startsAt.slice(0, 10) !== today && ['scheduled', 'confirmed'].includes(a.status) && a.practitionerId);
  const queue = await api(page, '/api/queue');
  const waiting = queue.filter((q) => q.status === 'waiting');
  const ticket = waiting[1] ?? waiting[0] ?? queue[0];
  console.log(`  Demo „${practice.name}“ (${practice.slug}), ${patients.length} Patienten, ${appts.length} Termine in 7 Tagen, ${waiting.length} Wartende`);

  // ---------- Desktop ----------
  await step(['01-aujourdhui', '07-premiers-pas'], lang, async () => {
    await go(page, '/app');
    await shot(page, '01-aujourdhui', lang);
    await shot(section(page, 'steps-title'), '07-premiers-pas', lang);
  });

  await step(['15-telephone-numero', '16-telephone-creneaux', 'v03-telephone-desktop', '17-telephone-confirme'], lang, async () => {
    await go(page, '/app');
    await page.getByRole('button', { name: t.phone }).first().click();
    const d = dialog(page);
    await d.locator('input[type=tel]').fill('00 000 001');
    const match = d.locator('ul button').first();
    await match.waitFor({ timeout: 10000 });
    await match.click();
    await page.waitForTimeout(500);
    await shot(d, '15-telephone-numero', lang);
    await d.locator('select').first().selectOption({ index: 1 });
    await d.locator('section button').first().waitFor({ timeout: 10000 });
    await settle(page, 500);
    await shot(d, '16-telephone-creneaux', lang);
    await shot(page, 'v03-telephone-desktop', lang);
    if (want('17-telephone-confirme')) {
      await d.locator('section button').first().click();
      await d.getByText(t.booked).waitFor({ timeout: 10000 });
      await shot(d, '17-telephone-confirme', lang);
    }
    await d.getByRole('button', { name: t.close, exact: true }).last().click();
  });

  await step(['18-agenda-jour', 'v01-agenda-desktop'], lang, async () => {
    await go(page, `/app/agenda?date=${agendaDay}`);
    await shot(page, '18-agenda-jour', lang);
    await shot(page, 'v01-agenda-desktop', lang);
  });

  await step(['19-agenda-nouveau', '20-agenda-conflit'], lang, async () => {
    const p = patients.find((x) => x.noShows === 0 && x.id !== planPatient?.id) ?? patients[3];
    await go(page, `/app/agenda?date=${agendaDay}&nouveau=1&patient=${p.id}`);
    const d = dialog(page);
    await d.getByLabel(t.service).selectOption({ index: 1 });
    await page.waitForTimeout(400);
    await shot(d, '19-agenda-nouveau', lang);
    if (want('20-agenda-conflit') && taken) {
      await d.getByLabel(t.date, { exact: true }).fill(taken.startsAt.slice(0, 10));
      await d.getByLabel(t.time, { exact: true }).fill(hhmm(taken.startsAt));
      await d.getByLabel(t.practitioner).selectOption(String(taken.practitionerId));
      await d.getByRole('button', { name: t.save }).click();
      await d.getByText(t.conflict).first().waitFor({ timeout: 10000 });
      await page.waitForTimeout(400);
      await shot(d, '20-agenda-conflit', lang);
    }
    await page.keyboard.press('Escape');
  });

  await step('32-acompte-conseille', lang, async () => {
    await go(page, `/app/agenda?date=${agendaDay}&nouveau=1&patient=${unreliable.id}`);
    const d = dialog(page);
    await d.getByLabel(t.service).selectOption({ index: 1 });
    await page.waitForTimeout(400);
    await shot(d, '32-acompte-conseille', lang);
    await page.keyboard.press('Escape');
  });

  await step('22-rdv-arrive', lang, async () => {
    if (!upcomingToday) throw new Error('kein kommender Termin gefunden (Aufnahme während der Öffnungszeiten wiederholen)');
    await go(page, `/app/agenda?date=${upcomingToday.startsAt.slice(0, 10)}`);
    await page.getByRole('button').filter({ hasText: hhmm(upcomingToday.startsAt) }).filter({ hasText: upcomingToday.patient.lastName }).first().click();
    await page.waitForTimeout(500);
    await shot(dialog(page), '22-rdv-arrive', lang);
    await page.keyboard.press('Escape');
  });

  await step('33-acompte-encaisse', lang, async () => {
    if (!withDeposit) throw new Error('kein Termin mit Anzahlung in den nächsten 7 Tagen');
    await go(page, `/app/agenda?date=${withDeposit.startsAt.slice(0, 10)}`);
    await page.getByRole('button').filter({ hasText: hhmm(withDeposit.startsAt) }).filter({ hasText: withDeposit.patient.lastName }).first().click();
    await page.waitForTimeout(500);
    await shot(dialog(page), '33-acompte-encaisse', lang);
    await page.keyboard.press('Escape');
  });

  await step(['23-salle', 'v06-salle-desktop', '24-nouveau-ticket', '25-ticket-qr'], lang, async () => {
    await go(page, '/app/salle');
    await shot(page, '23-salle', lang);
    await shot(page, 'v06-salle-desktop', lang);
    if (want('24-nouveau-ticket')) {
      await page.getByRole('button', { name: t.newTicket }).first().click();
      await page.waitForTimeout(500);
      await shot(dialog(page), '24-nouveau-ticket', lang);
      await dialog(page).getByRole('button', { name: t.cancel, exact: true }).click();
    }
    if (want('25-ticket-qr')) {
      await page.getByRole('button', { name: t.qr }).first().click();
      await page.waitForTimeout(600);
      await shot(dialog(page), '25-ticket-qr', lang);
      await page.keyboard.press('Escape');
    }
  });

  await step('26-patient-suivant', lang, async () => {
    await go(page, '/app/salle/suivant');
    await shot(page, '26-patient-suivant', lang);
  });

  await step(['29-dossier-solde', '30-paiement'], lang, async () => {
    await go(page, `/app/patients/${planPatient.id}`);
    await page.getByRole('tab', { name: t.tabMoney }).click();
    await settle(page, 500);
    await shot(page, '29-dossier-solde', lang);
    if (want('30-paiement')) {
      await page.getByRole('button', { name: t.addPayment, exact: true }).click();
      const d = dialog(page);
      await d.getByLabel(t.amount).fill('50');
      await page.waitForTimeout(300);
      await shot(d, '30-paiement', lang);
      await d.getByRole('button', { name: t.cancel, exact: true }).click(); // nicht speichern
    }
  });

  await step('31-recu', lang, async () => {
    const ledger = await api(page, `/api/patients/${planPatient.id}/ledger`);
    const pay = ledger.payments[0];
    if (!pay) throw new Error('keine Zahlung gefunden');
    await go(page, `/app/recu/${pay.id}`);
    await shot(page, '31-recu', lang);
  });

  await step(['34-caisse-jour', 'v11-caisse-desktop', '35-montants-dus'], lang, async () => {
    await go(page, '/app/caisse');
    await shot(page, '34-caisse-jour', lang);
    await shot(page, 'v11-caisse-desktop', lang);
    await shot(section(page, 'balances-title'), '35-montants-dus', lang, { maxHeight: 520 });
  });

  await step('36-cloture', lang, async () => {
    let day = null;
    for (let i = 1; i <= 7 && !day; i++) {
      const cash = await api(page, `/api/cash?day=${tunisDay(-i)}`);
      if (cash.closing && !cash.closing.verifiedAt) day = tunisDay(-i);
    }
    await go(page, `/app/caisse?day=${day ?? tunisDay(-1)}`);
    await shot(section(page, 'closing-title'), '36-cloture', lang);
  });

  await step('37-rappels', lang, async () => {
    await go(page, '/app/rappels');
    for (let i = 0; i < 4 && !(await page.locator('main li').count()); i++) {
      await page.getByRole('button', { name: t.nextDay }).click();
      await settle(page, 500);
    }
    await shot(page, '37-rappels', lang);
  });

  await step('39-rappels-modele', lang, async () => {
    await go(page, '/app/reglages');
    await shot(page.locator('section[aria-labelledby="c-reminders"]'), '39-rappels-modele', lang);
  });

  await step(['08-horaires', '09-fermetures'], lang, async () => {
    await go(page, '/app/reglages/horaires');
    await shot(page, '08-horaires', lang);
    await shot(section(page, 'h-closures'), '09-fermetures', lang);
  });
  await step('10-actes', lang, async () => { await go(page, '/app/reglages/actes'); await shot(page, '10-actes', lang); });
  await step('11-praticiens', lang, async () => { await go(page, '/app/reglages/praticiens'); await shot(page, '11-praticiens', lang); });
  await step('12-equipe-invitation', lang, async () => {
    await go(page, '/app/reglages/equipe');
    await page.getByRole('button', { name: t.inviteCreate }).click();
    await page.waitForTimeout(800);
    await shot(section(page, 't-invite'), '12-equipe-invitation', lang);
  });
  await step('13-reservation-reglages', lang, async () => { await go(page, '/app/reglages/reservation'); await shot(page, '13-reservation-reglages', lang); });
  await step('14-affiche', lang, async () => { await go(page, '/app/reglages/affiche'); await shot(page, '14-affiche', lang); });
  await step('03-installer', lang, async () => { await go(page, '/app/installer'); await shot(page, '03-installer', lang); });

  // ---------- Import (Antworten nachgestellt, siehe Kopf) ----------
  await step(['40-import-fichier', '41-import-correspondance', '42-import-verification', '43-import-termine'], lang, async () => {
    const imp = await desk.newPage();
    await mockImport(imp, lang);
    await go(imp, '/app/import');
    await shot(imp, '40-import-fichier', lang);
    await imp.getByLabel(t.browse).setInputFiles({ name: lang === 'ar' ? 'المرضى.csv' : 'patients-cabinet.csv', mimeType: 'text/csv', buffer: Buffer.from('nom;prenom\n', 'utf8') });
    await imp.getByRole('button', { name: t.continue }).click();
    await settle(imp, 500);
    await shot(imp, '41-import-correspondance', lang);
    await imp.getByRole('button', { name: t.check }).click();
    await settle(imp, 500);
    await shot(imp, '42-import-verification', lang);
    await imp.getByRole('button', { name: t.importN }).click();
    await settle(imp, 500);
    await shot(imp, '43-import-termine', lang);
    await imp.close();
  });

  // ---------- Handy (gleiche Anmeldung) ----------
  await go(page, '/app'); // echtes Konto (isDemo) wieder in den Speicher, bevor das Handy die Anmeldung übernimmt
  const state = await desk.storageState();
  const mob = await newContext('mobile', lang, state);
  const m = await mob.newPage();

  await step(['v12-aujourdhui-mobile', '02-menu-mobile'], lang, async () => {
    await go(m, '/app');
    await shot(m, 'v12-aujourdhui-mobile', lang);
    if (want('02-menu-mobile')) {
      await m.locator('nav').last().getByRole('button', { name: t.plus }).click();
      await m.waitForTimeout(500);
      await shot(m, '02-menu-mobile', lang);
    }
  });
  await step(['21-agenda-mobile', 'v02-agenda-mobile'], lang, async () => {
    await go(m, `/app/agenda?date=${agendaDay}`);
    await shot(m, '21-agenda-mobile', lang);
    await shot(m, 'v02-agenda-mobile', lang);
  });
  await step(['38-rappels-mobile', 'v09-rappels-mobile'], lang, async () => {
    await go(m, '/app/rappels');
    for (let i = 0; i < 4 && !(await m.locator('main li').count()); i++) {
      await m.getByRole('button', { name: t.nextDay }).click();
      await settle(m, 500);
    }
    await m.locator('main li').first().scrollIntoViewIfNeeded();
    await shot(m, '38-rappels-mobile', lang);
    await shot(m, 'v09-rappels-mobile', lang);
  });
  await step('v13-dossier-mobile', lang, async () => {
    await go(m, `/app/patients/${planPatient.id}`);
    await m.getByRole('tab', { name: t.tabMoney }).click();
    await settle(m, 500);
    await m.getByRole('tab', { name: t.tabMoney }).scrollIntoViewIfNeeded();
    await m.evaluate(() => window.scrollBy(0, -60));
    await shot(m, 'v13-dossier-mobile', lang);
  });

  // Ticket-Seite des Patienten (öffentlich, ohne Anmeldung)
  await step(['28-ticket-patient', 'v08-ticket-mobile'], lang, async () => {
    if (!ticket) throw new Error('kein Ticket in der Warteschlange');
    await go(m, `/ticket/${ticket.ticketToken}?lang=${lang}`);
    await shot(m, '28-ticket-patient', lang);
    await shot(m, 'v08-ticket-mobile', lang);
  });

  // Buchungsseite der Praxis (Demo-Praxen haben keine eigene Subdomain mit Zertifikat → /r/<slug>)
  await step(['44-reservation-choix', 'v04-reservation-mobile', '45-reservation-coordonnees', '46-reservation-envoyee', '47-rdv-annuler'], lang, async () => {
    await go(m, `/r/${practice.slug}?lang=${lang}`);
    await pick(m.locator('input[name=service]').first());
    await settle(m, 400);
    const firstDay = m.locator('input[name=day]:not([disabled])').first();
    if (await firstDay.count()) await pick(firstDay);
    for (let i = 0; i < 6; i++) {
      await settle(m, 400);
      if (await m.locator('input[name=time]').count()) break;
      const next = m.getByRole('button', { name: t.nextSlotDay });
      if (await next.count()) await next.click();
    }
    await pick(m.locator('input[name=time]').first());
    await m.getByRole('button', { name: t.continue }).scrollIntoViewIfNeeded();
    await m.waitForTimeout(400);
    await shot(m, '44-reservation-choix', lang);
    await shot(m, 'v04-reservation-mobile', lang);
    if (!['45-reservation-coordonnees', '46-reservation-envoyee', '47-rdv-annuler'].some(want)) return;
    await m.getByRole('button', { name: t.continue }).click();
    await settle(m, 400);
    await m.getByLabel(t.firstName, { exact: true }).fill(t.sample.first);
    await m.getByLabel(t.lastName, { exact: true }).fill(t.sample.last);
    await m.getByLabel(t.phoneLabel, { exact: true }).fill(`+216 00 000 ${String(900 + Math.floor(Math.random() * 99)).slice(-3)}`);
    await m.locator('input[type=checkbox]').first().check();
    await m.getByRole('button', { name: t.submitBooking }).scrollIntoViewIfNeeded();
    await m.waitForTimeout(300);
    await shot(m, '45-reservation-coordonnees', lang);
    await m.getByRole('button', { name: t.submitBooking }).click();
    await m.getByRole('heading', { name: t.bookedTitle }).waitFor({ timeout: 15000 });
    await m.evaluate(() => window.scrollTo(0, 0));
    await settle(m, 400);
    await m.getByRole('heading', { name: t.bookedTitle }).scrollIntoViewIfNeeded();
    await shot(m, '46-reservation-envoyee', lang);
    await m.getByRole('link', { name: t.openManage }).click();
    await settle(m, 600);
    await m.getByRole('button', { name: t.cancelBooking }).click();
    await m.waitForTimeout(500);
    await shot(m, '47-rdv-annuler', lang); // Rückfrage offen, nicht bestätigt
  });

  // nach der Online-Buchung: Anfragen auf „Aujourd’hui“
  await step(['48-demandes-en-ligne', 'v05-demandes-desktop'], lang, async () => {
    await go(page, '/app');
    const s = section(page, 'requests-title');
    await shot(s, '48-demandes-en-ligne', lang, { maxHeight: 560 });
    await s.scrollIntoViewIfNeeded();
    await page.evaluate(() => window.scrollBy(0, -120));
    await page.waitForTimeout(300);
    await shot(page, 'v05-demandes-desktop', lang);
  });

  // ---------- Bildschirm der Wartezone (öffentlich) ----------
  await step(['27-ecran-salle', 'v07-ecran-tv'], lang, async () => {
    const tv = await newContext('tv', lang);
    const p = await tv.newPage();
    await go(p, `/salle/${practice.displayToken}?lang=${lang}`);
    await p.waitForTimeout(1500);
    await shot(p, '27-ecran-salle', lang);
    await shot(p, 'v07-ecran-tv', lang);
    await tv.close();
  });

  await mob.close();
  await desk.close();
}

await browser.close();
const manual = TUTORIAL_SHOTS.filter((s) => s.mode === 'manual').map((s) => s.id);
console.log(`\n${done.length} Aufnahmen gespeichert.`);
console.log(`Von Hand aufzunehmen (Browser-Menüs): ${manual.join(', ')} → ../tutorial/shots/<id>-fr.png / -ar.png`);
if (failed.length) {
  console.error('\nNICHT AUFGENOMMEN (Platzhalter bleiben):\n  ' + failed.join('\n  '));
  process.exitCode = 1;
}

// ======================================================================================================
/** Importseite mit nachgestellten Antworten (Demo-Praxen dürfen nicht importieren). Nur dieser Tab ist betroffen. */
async function mockImport(page, lang) {
  const ar = lang === 'ar';
  // nur beim Lesen ändern, nicht im gespeicherten Konto (der Haupt-Tab lädt danach /app neu und schreibt das echte Konto)
  await page.addInitScript(() => {
    const read = Storage.prototype.getItem;
    Storage.prototype.getItem = function (key) {
      const value = read.call(this, key);
      if (key !== 'daftar.user' || !value) return value;
      try {
        const u = JSON.parse(value);
        if (u && u.practice) u.practice.isDemo = false;
        return JSON.stringify(u);
      } catch { return value; }
    };
  });
  await page.route('**/api/auth/me', async (route) => {
    if (route.request().method() !== 'GET') return route.continue();
    const res = await route.fetch();
    const me = await res.json();
    if (me.practice) me.practice.isDemo = false;
    return route.fulfill({ response: res, json: me });
  });
  const headers = ar ? ['اللقب', 'الاسم', 'الهاتف', 'تاريخ الولادة', 'ملاحظات', 'الباقي'] : ['Nom', 'Prénom', 'GSM', 'Date de naissance', 'Remarques', 'Reste à payer'];
  const rows = ar
    ? [['الطرابلسي', 'أميرة', '00 000 101', '12/03/1980', 'حساسية من البنسلين', '120'], ['الغربي', 'سامي', '00 000 102', '01/01/1975', '', ''], ['الجلاصي', 'سلمى', '00 000 103', '23/07/1992', '', '35,500']]
    : [['Trabelsi', 'Amira', '00 000 101', '12/03/1980', 'Allergie pénicilline', '120'], ['Gharbi', 'Sami', '00 000 102', '01/01/1975', '', ''], ['Jlassi', 'Salma', '00 000 103', '23/07/1992', '', '35,500']];
  const job = {
    id: '00000000-0000-4000-8000-000000000001', filename: ar ? 'المرضى.csv' : 'patients-cabinet.csv', sheets: [ar ? 'المرضى' : 'Patients'],
    sheet: ar ? 'المرضى' : 'Patients', headerRow: 1, rowCount: 214,
    columns: headers.map((header, index) => ({ index, header, samples: rows.map((r) => r[index]).filter(Boolean) })),
    suggestedMapping: { lastName: 0, firstName: 1, phone: 2, birthDate: 3, notes: 4, openingBalance: 5 },
  };
  const preview = {
    willCreate: 211, willUpdate: 0, willSkip: 1, willCreatePatients: 0, errorCount: 2,
    errors: [
      { row: 57, field: 'phone', message: ar ? 'رقم غير صالح.' : 'Numéro invalide.', value: '2012' },
      { row: 140, field: 'birthDate', message: ar ? 'تاريخ غير صالح.' : 'Date invalide.', value: '31/02/1975' },
    ],
    duplicates: [{ row: 12, patientId: null, name: ar ? 'أميرة الطرابلسي' : 'Amira Trabelsi' }],
    conflicts: [],
    sample: rows.map((r) => ({ lastName: r[0], firstName: r[1], phone: '+216' + r[2].replace(/\s/g, ''), birthDate: r[3], notes: r[4] })),
  };
  const result = { created: 211, updated: 0, skipped: 1, errorCount: 2, patientsCreated: 0 };
  await page.route('**/api/import-templates**', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/imports**', (route) => {
    const url = route.request().url();
    if (url.endsWith('/preview')) return route.fulfill({ json: preview });
    if (url.endsWith('/commit')) return route.fulfill({ json: result });
    if (url.endsWith('/sheet')) return route.fulfill({ json: job });
    if (url.includes('report.csv')) return route.fulfill({ body: 'ligne;champ;message\n', contentType: 'text/csv' });
    return route.fulfill({ status: 201, json: job });
  });
}
