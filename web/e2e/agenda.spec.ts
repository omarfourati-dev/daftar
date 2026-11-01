import { expect, test } from '@playwright/test';
import { addDays, APP, axe, currentQuarter, iso, newPatient, newPractice, onApp, signIn, slot, tunisNow, watchConsole } from './daily';

/** Stories B1–B4, B6, B7 and 16.1 against the real stack. */

test('B1 – the day with one column per practitioner, the week, no console errors, accessible', async ({ page, request }) => {
	const p = await newPractice(request);
	const problems = watchConsole(page);
	await signIn(page, p);
	await page.goto(APP + '/app/agenda');
	await expect(page.getByRole('heading', { level: 1, name: 'Agenda' })).toBeVisible();
	await expect(page.getByRole('region', { name: 'Dr Amira Ben Salem' })).toBeVisible();
	await expect(page.getByRole('region', { name: 'Dr Karim Jaziri' })).toBeVisible();
	await expect(page.getByRole('img', { name: /^Maintenant, \d\d:\d\d$/ })).toHaveCount(1);
	await axe(page);
	await page.getByRole('button', { name: 'Semaine' }).click();
	await expect(page.getByRole('region', { name: new RegExp(`${Number(tunisNow().day.slice(8))} `) }).first()).toBeVisible();
	await page.getByRole('button', { name: 'Semaine suivante' }).click();
	await expect(page.getByText('Aucun rendez-vous cette semaine.')).toBeVisible();
	expect(problems).toEqual([]);
});

test('B2 – new appointment from a free slot; a taken slot proposes the next free times', async ({ page, request }) => {
	const p = await newPractice(request);
	const sami = await newPatient(p, { firstName: 'Sami', lastName: 'Slot' });
	const lina = await newPatient(p, { firstName: 'Lina', lastName: 'Conflit', alerts: 'Allergie pénicilline' });
	const at = slot(60);
	await signIn(page, p);
	await page.goto(`${APP}/app/agenda?date=${at.day}`);
	const karim = page.getByRole('region', { name: 'Dr Karim Jaziri' });
	await karim.getByRole('button', { name: `Nouveau rendez-vous à ${at.time} avec Dr Karim Jaziri` }).click();
	const dialog = page.getByRole('dialog', { name: 'Nouveau rendez-vous' });
	await dialog.getByLabel('Nom ou téléphone').fill('Slot');
	await dialog.getByRole('button', { name: /Sami Slot/ }).click();
	await dialog.getByLabel('Acte / consultation').selectOption({ label: 'Consultation' });
	await axe(page);
	await dialog.getByRole('button', { name: 'Enregistrer le rendez-vous' }).click();
	await expect(page.getByRole('status')).toHaveText('Rendez-vous enregistré.');
	await expect(karim.getByRole('button', { name: new RegExp(`${at.time} Sami Slot`) })).toBeVisible();

	// the same time with the same practitioner for somebody else → 409 and the next free times
	await page.getByRole('button', { name: 'Nouveau rendez-vous', exact: true }).click();
	const again = page.getByRole('dialog', { name: 'Nouveau rendez-vous' });
	await again.getByLabel('Nom ou téléphone').fill('Conflit');
	await again.getByRole('button', { name: /Lina Conflit/ }).click();
	await expect(again.getByText('Allergie pénicilline')).toBeVisible();
	await again.getByLabel('Date').fill(at.day);
	await again.getByLabel('Heure').fill(at.time);
	await again.getByLabel('Praticien').selectOption({ label: 'Dr Karim Jaziri' });
	await again.getByRole('button', { name: 'Enregistrer le rendez-vous' }).click();
	const conflict = again.getByRole('alert');
	await expect(conflict).toContainText('Ce créneau est déjà pris.');
	await expect(conflict).toContainText('Sami Slot');
	await conflict.getByRole('button').first().click();
	await expect(page.getByRole('status')).toHaveText('Rendez-vous enregistré.');
	// the status above may still be the one of the first booking: wait for the server, not for the text
	await expect.poll(async () => (await p.api.get(`/api/patients/${lina.id}/appointments`)).length).toBe(1);
	void sami;
});

test('B3 – arrival puts the patient in the waiting room; status buttons follow the day', async ({ page, request }) => {
	const p = await newPractice(request);
	const patient = await newPatient(p, { firstName: 'Nadia', lastName: 'Arrivee' });
	const now = currentQuarter();
	await p.api.post('/api/appointments', { patientId: patient.id, startsAt: now.startsAt, durationMin: 10, reason: 'Consultation', practitionerId: p.practitioners[0].id });
	await signIn(page, p);
	await page.goto(APP + '/app/agenda');
	await page.getByRole('button', { name: new RegExp(`${now.time} Nadia Arrivee`) }).click();
	const dialog = page.getByRole('dialog', { name: 'Nadia Arrivee' });
	await axe(page);
	await dialog.getByRole('button', { name: 'Arrivé' }).click();
	await expect(dialog.getByRole('status')).toHaveText('Statut : Arrivé.');
	await expect(dialog.getByRole('button', { name: 'En consultation' })).toBeVisible();
	await expect(dialog.getByRole('button', { name: 'Déplacer / modifier' })).toHaveCount(0);
	await page.goto(APP + '/app/salle');
	await expect(page.getByRole('region', { name: 'En attente' }).getByText('Nadia Arrivee')).toBeVisible();
});

test('B3 – an online request is confirmed or declined with a WhatsApp text', async ({ page, request }) => {
	const p = await newPractice(request, { onlineBooking: true });
	const service = p.services.find((s) => s.onlineBookable) ?? p.services[0];
	const day = addDays(tunisNow().day, 2);
	const slots = await (await request.get(`/api/public/practices/${p.slug}/slots?date=${day}&serviceId=${service.id}`, onApp())).json();
	const booked = await request.post(`/api/public/practices/${p.slug}/bookings`, {
		...onApp(),
		data: { serviceId: service.id, startsAt: iso(day, slots.slots[0]), firstName: 'Salma', lastName: 'EnLigne', phone: '20 000 777', lang: 'fr', reminderConsent: true, website: '' }
	});
	test.skip(booked.status() === 429, 'public booking limit (3 per IP and hour) reached by earlier runs');
	expect(booked.status(), await booked.text()).toBe(201);
	await signIn(page, p);
	await page.goto(`${APP}/app/agenda?date=${day}`);
	await page.getByRole('button', { name: /Salma EnLigne/ }).click();
	const dialog = page.getByRole('dialog', { name: 'Salma EnLigne' });
	await expect(dialog.getByText('Demandé en ligne')).toBeVisible();
	await dialog.getByRole('button', { name: 'Confirmer' }).click();
	const link = dialog.getByRole('link', { name: 'Prévenir par WhatsApp' });
	await expect(link).toHaveAttribute('href', /^https:\/\/wa\.me\/21620000777\?text=Bonjour%20Salma/);
});

test('B4 – a weekly series is checked session by session and created', async ({ page, request }) => {
	const p = await newPractice(request);
	await newPatient(p, { firstName: 'Rim', lastName: 'Serie' });
	const start = addDays(tunisNow().day, 1);
	await signIn(page, p);
	await page.goto(APP + '/app/agenda');
	await page.getByRole('button', { name: 'Nouveau rendez-vous', exact: true }).click();
	const dialog = page.getByRole('dialog', { name: 'Nouveau rendez-vous' });
	await dialog.getByLabel('Nom ou téléphone').fill('Serie');
	await dialog.getByRole('button', { name: /Rim Serie/ }).click();
	await dialog.getByLabel('Date').fill(start);
	await dialog.getByLabel('Heure').fill('10:00');
	await dialog.getByLabel('Praticien').selectOption({ label: 'Dr Amira Ben Salem' });
	await dialog.getByLabel('Répéter (séances)').check();
	await dialog.getByLabel('Nombre de séances').fill('3');
	await dialog.getByRole('button', { name: 'Vérifier les dates' }).click();
	await expect(dialog.getByText('Toutes les séances sont libres.')).toBeVisible();
	await expect(dialog.getByRole('list', { name: 'Séances régulières' }).getByRole('listitem')).toHaveCount(3);
	await dialog.getByRole('button', { name: 'Créer 3 rendez-vous' }).click();
	await expect(page.getByRole('status')).toHaveText('Rendez-vous créés : 3.');
});

test('B6 – the day prints as a list per practitioner', async ({ page, request }) => {
	const p = await newPractice(request);
	const patient = await newPatient(p, { firstName: 'Walid', lastName: 'Papier' });
	const at = slot(90);
	await p.api.post('/api/appointments', { patientId: patient.id, startsAt: at.startsAt, durationMin: 15, reason: 'Contrôle', practitionerId: p.practitioners[1].id, notes: 'À jeun' });
	await signIn(page, p);
	await page.goto(`${APP}/app/agenda/imprimer?date=${at.day}`);
	const table = page.getByRole('table', { name: 'Dr Karim Jaziri' });
	await expect(table.getByRole('row', { name: new RegExp(at.time) })).toContainText('Walid Papier');
	await expect(table.getByRole('row', { name: new RegExp(at.time) })).toContainText('À jeun');
	await axe(page);
	await page.emulateMedia({ media: 'print' });
	await expect(page.getByRole('button', { name: 'Imprimer' })).toBeHidden();
});

test('B7 – "/" searches a patient, "N" opens a new appointment', async ({ page, request }) => {
	const p = await newPractice(request);
	const patient = await newPatient(p, { firstName: 'Hichem', lastName: 'Clavier' });
	await signIn(page, p);
	await page.goto(APP + '/app');
	await expect(page.getByRole('heading', { level: 1, name: 'Aujourd’hui' })).toBeVisible();
	await page.keyboard.press('/');
	await expect(page.getByRole('combobox', { name: 'Rechercher un patient' })).toBeFocused();
	await page.keyboard.type('Clavier');
	await expect(page.getByRole('option', { name: /Hichem Clavier/ })).toBeVisible();
	await page.keyboard.press('ArrowDown');
	await page.keyboard.press('Enter');
	await expect(page).toHaveURL(new RegExp(`/app/patients/${patient.id}$`));
	await expect(page.getByRole('heading', { level: 1, name: 'Hichem Clavier' })).toBeVisible();
	await page.locator('body').click({ position: { x: 5, y: 5 } });
	await page.keyboard.press('n');
	await expect(page.getByRole('dialog', { name: 'Nouveau rendez-vous' })).toBeVisible();
});

test('16.1 – appointment on the phone: number first, next free times, one click, confirmation text', async ({ page, request }) => {
	const p = await newPractice(request);
	const patient = await newPatient(p, { firstName: 'Youssef', lastName: 'Telephone' });
	await signIn(page, p);
	await page.goto(APP + '/app/agenda');
	await expect(page.getByRole('heading', { level: 1, name: 'Agenda' })).toBeVisible();
	await page.keyboard.press('t');
	const dialog = page.getByRole('dialog', { name: 'Rendez-vous par téléphone' });
	await dialog.getByLabel('Numéro de l’appelant').fill(patient.phone.slice(4));
	await dialog.getByRole('button', { name: /Youssef Telephone/ }).click();
	await dialog.getByLabel('Acte / consultation').selectOption({ label: 'Consultation' });
	const free = dialog.getByRole('region', { name: 'Prochains créneaux libres' });
	await axe(page);
	await free.getByRole('button').first().click();
	await expect(dialog.getByRole('status')).toContainText('Rendez-vous enregistré');
	await expect(dialog.getByLabel('Message de confirmation')).toHaveValue(/^Bonjour Youssef, votre rendez-vous au Cabinet E2E/);
	await dialog.getByRole('button', { name: 'Fermer' }).last().click();
	expect(await p.api.get(`/api/patients/${patient.id}/appointments`)).toHaveLength(1);
});
