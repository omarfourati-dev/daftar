import { expect, test } from '@playwright/test';
import { addDays, APP, axe, iso, newPatient, newPractice, signIn, tunisNow } from './daily';

/** Story G1 – reminders of the next opening day by click (wa.me / sms:), consent respected, marked as sent. */

test('G1 – tomorrow’s reminders with WhatsApp/SMS links, no buttons without consent, marked as sent', async ({ page, request }) => {
	const p = await newPractice(request);
	const yes = await newPatient(p, { firstName: 'Youssef', lastName: 'Accord', reminderConsent: true });
	const no = await newPatient(p, { firstName: 'Anis', lastName: 'Refus', reminderConsent: false });
	// the next opening day (code review M6): tomorrow, or Monday when tomorrow is Sunday (default hours Mon–Sat)
	let day = addDays(tunisNow().day, 1);
	if (new Date(`${day}T12:00:00Z`).getUTCDay() === 0) day = addDays(day, 1);
	await p.api.post('/api/appointments', { patientId: yes.id, startsAt: iso(day, '09:00'), durationMin: 20, reason: 'Consultation' });
	await p.api.post('/api/appointments', { patientId: no.id, startsAt: iso(day, '09:30'), durationMin: 20, reason: 'Contrôle' });

	await signIn(page, p);
	await page.goto(APP + '/app/rappels');
	await expect(page.getByText('2 rendez-vous, 0 rappel(s) envoyé(s)')).toBeVisible();
	const card = (name: string) => page.getByRole('listitem').filter({ has: page.getByRole('heading', { name: new RegExp(name) }) });
	const whatsapp = card('Youssef Accord').getByRole('link', { name: 'WhatsApp' });
	await expect(whatsapp).toHaveAttribute('href', new RegExp(`^https://wa\\.me/${yes.phone.slice(1)}\\?text=`));
	await expect(card('Youssef Accord').getByRole('link', { name: 'SMS' })).toHaveAttribute('href', new RegExp(`^sms:\\+${yes.phone.slice(1)}\\?&body=`));
	await expect(card('Anis Refus').getByText('Pas d’accord pour les rappels')).toBeVisible();
	await expect(card('Anis Refus').getByRole('button', { name: 'WhatsApp' })).toBeDisabled();
	await axe(page);

	await card('Youssef Accord').getByRole('button', { name: 'Marquer comme envoyé' }).click();
	await expect(card('Youssef Accord').getByText(/^Envoyé à \d\d:\d\d$/)).toBeVisible();
	await expect(page.getByText('2 rendez-vous, 1 rappel(s) envoyé(s)')).toBeVisible();
});
