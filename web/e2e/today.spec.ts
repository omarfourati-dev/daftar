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
