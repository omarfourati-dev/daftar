import { expect, test } from '@playwright/test';
import { addDays, APP, axe, iso, newPatient, newPractice, onApp, signIn, slot, tunisNow, watchConsole } from './daily';

/** Dashboard: tiles, online requests (C2) with the badge, first steps (A5), statistics for the owner (H1). */

test('C2 + A5 – the day at a glance, an online request with its badge, the first steps', async ({ page, request }) => {
	const p = await newPractice(request, { onlineBooking: true });
	const patient = await newPatient(p, { firstName: 'Walid', lastName: 'Prochain' });
	const at = slot(60);
	await p.api.post('/api/appointments', { patientId: patient.id, startsAt: at.startsAt, durationMin: 15, reason: 'Contrôle' });

	const service = p.services.find((s) => s.onlineBookable) ?? p.services[0];
	const day = addDays(tunisNow().day, 3);
	const slots = await (await request.get(`/api/public/practices/${p.slug}/slots?date=${day}&serviceId=${service.id}`, onApp())).json();
	const booked = await request.post(`/api/public/practices/${p.slug}/bookings`, {
		...onApp(),
		data: { serviceId: service.id, startsAt: iso(day, slots.slots[0]), firstName: 'Salma', lastName: 'Demande', phone: '20 000 778', lang: 'fr', reminderConsent: true, website: '' }
	});
	const hasRequest = booked.status() === 201;

	const problems = watchConsole(page);
	await signIn(page, p);
	await page.goto(APP + '/app');
	await expect(page.getByRole('heading', { level: 1, name: 'Aujourd’hui' })).toBeVisible();
	await expect(page.getByRole('list', { name: 'Résumé de la journée' }).getByRole('link', { name: /^Rendez-vous/ })).toBeVisible();
	const steps = page.getByRole('region', { name: 'Premiers pas' });
	await expect(steps).toContainText('Praticiens');
	await expect(steps.getByRole('link', { name: 'Installer l’application' })).toHaveAttribute('href', '/app/installer');
	if (at.day === tunisNow().day) await expect(page.getByRole('region', { name: 'Prochains rendez-vous' })).toContainText('Walid Prochain');
	await axe(page);

	if (hasRequest) {
		const nav = page.getByRole('navigation', { name: 'Navigation principale' });
		await expect(nav.getByRole('link', { name: /Aujourd’hui/ })).toContainText('1 à traiter');
		const requests = page.getByRole('region', { name: 'Nouvelles demandes en ligne' });
		await expect(requests).toContainText('Salma Demande');
		await requests.getByRole('button', { name: 'Confirmer' }).click();
		await expect(requests.getByRole('link', { name: 'Prévenir par WhatsApp' })).toHaveAttribute('href', /^https:\/\/wa\.me\/21620000778\?text=/);
		await expect(nav.getByRole('link', { name: /Aujourd’hui/ })).not.toContainText('à traiter');
	}
	await steps.getByRole('button', { name: 'Masquer' }).click();
	await expect(steps).toHaveCount(0);
	expect(problems).toEqual([]);
});

test('H1 – the owner sees the month with the previous one; the statistics are in the navigation', async ({ page, request }) => {
	const p = await newPractice(request);
	await signIn(page, p);
	await page.goto(APP + '/app');
	await page.getByRole('navigation', { name: 'Navigation principale' }).getByRole('link', { name: 'Statistiques' }).click();
	await expect(page.getByRole('heading', { level: 1, name: 'Statistiques' })).toBeVisible();
	const kpis = page.getByRole('list', { name: 'Statistiques' });
	await expect(kpis.getByText('Taux d’absence')).toBeVisible();
	await expect(page.getByRole('img', { name: 'Ce mois et le mois précédent' })).toBeVisible();
	await axe(page);
	await page.getByRole('button', { name: 'Mois précédent' }).click();
	await expect(kpis).toBeVisible();
});

test('Arabic – the daily pages read right to left', async ({ page, request }) => {
	const p = await newPractice(request);
	await signIn(page, p, 'ar');
	for (const [path, heading] of [
		['/app', 'اليوم'],
		['/app/agenda', 'المواعيد'],
		['/app/salle', 'قاعة الانتظار'],
		['/app/patients', 'المرضى'],
		['/app/caisse', 'الصندوق'],
		['/app/rappels', 'التذكيرات'],
		['/app/statistiques', 'الإحصائيات']
	]) {
		await page.goto(APP + path);
		await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible();
		await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
		await axe(page);
	}
});

test('A5 – the first steps open the settings sections (no missing anchors)', async ({ page, request }) => {
	const p = await newPractice(request);
	await signIn(page, p);
	await page.goto(APP + '/app');
	const steps = page.getByRole('region', { name: 'Premiers pas' });
	// newPractice creates two practitioners: that step is done (struck through, no link); the team is still to invite
	await expect(steps.getByRole('link', { name: 'Praticiens' })).toHaveCount(0);
	await expect(steps.getByText('Praticiens', { exact: true })).toHaveClass(/line-through/);
	await steps.getByRole('link', { name: 'Inviter l’équipe' }).click();
	await expect(page).toHaveURL(/\/app\/reglages\/equipe$/);
	await expect(page.getByRole('heading', { level: 2, name: 'Équipe' })).toBeVisible();
	await page.goto(APP + '/app/reglages#praticiens'); // an old link with an anchor
	await expect(page).toHaveURL(/\/app\/reglages\/praticiens$/);
	await expect(page.getByRole('heading', { level: 2, name: 'Praticiens' })).toBeVisible();
});

test('B4 – on a phone: appointment by phone and patient search from "Aujourd’hui" and the menu "Plus"', async ({ page, request }) => {
	const p = await newPractice(request);
	const patient = await newPatient(p, { firstName: 'Rania', lastName: 'Mobile' });
	await page.setViewportSize({ width: 390, height: 844 });
	await signIn(page, p);
	await page.goto(APP + '/app');
	await page.getByRole('button', { name: 'Rendez-vous par téléphone' }).click();
	const phone = page.getByRole('dialog', { name: 'Rendez-vous par téléphone' });
	await expect(phone.getByLabel('Numéro de l’appelant')).toBeVisible();
	await phone.getByRole('button', { name: 'Fermer' }).last().click();

	await page.getByRole('navigation', { name: 'Navigation rapide' }).getByRole('button', { name: 'Plus' }).click();
	const more = page.getByRole('dialog', { name: 'Plus' });
	await expect(more.getByRole('link', { name: 'Importer' })).toHaveAttribute('href', '/app/import');
	await expect(more.getByRole('link', { name: 'Abonnement' })).toHaveAttribute('href', '/app/abonnement');
	await axe(page);
	await more.getByRole('button', { name: 'Rechercher un patient' }).click();
	const search = page.getByRole('combobox', { name: 'Rechercher un patient' });
	await expect(search).toBeFocused();
	await search.fill('Mobile');
	await page.getByRole('option', { name: /Rania Mobile/ }).click();
	await expect(page).toHaveURL(new RegExp(`/app/patients/${patient.id}$`));
	await expect(search).toBeHidden(); // folded away again on the new page
	expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
});
