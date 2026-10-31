import { expect, test, type Page } from '@playwright/test';
import {
	adminSession,
	apiContext,
	APP,
	createPractice,
	expectAccessible,
	expectNoHorizontalScroll,
	freshIp,
	practiceOrigin,
	watchConsole,
	type Session
} from './kunden-helpers';

/** Story C1 – online booking for patients (spec 11.3, 13): mostly opened on a phone from a WhatsApp link. */

let admin: Session;
test.beforeAll(async () => {
	admin = await adminSession();
});

const phone = () => `2${Math.floor(1_000_000 + Math.random() * 8_999_999)}`;

/** A practice open every day all day (bookable whenever the test runs), online booking on. */
const bookablePractice = (extra = {}) =>
	createPractice(admin, { allDay: true, onlineBooking: true, practitioners: [{ title: 'Dr.', name: 'Amira Ben Salah' }, { title: 'Dr.', name: 'Karim Trabelsi' }], ...extra });

async function pickFirstFreeTime(page: Page, service = /Consultation/) {
	await page.locator('label.choice', { has: page.getByRole('radio', { name: service }) }).click();
	const firstTime = page.locator('label.choice', { has: page.locator('input[name=time]') }).first();
	await expect(firstTime).toBeVisible();
	await firstTime.click();
	return {
		day: await page.locator('input[name=day]:checked').inputValue(),
		time: await page.locator('input[name=time]:checked').inputValue()
	};
}

async function fillDetails(page: Page, labels = { first: 'Prénom', last: 'Nom', phone: 'Téléphone' }, tel = phone()) {
	await page.getByLabel(labels.first, { exact: true }).fill('Mounia');
	await page.getByLabel(labels.last, { exact: true }).fill('Chebbi');
	await page.getByLabel(labels.phone, { exact: true }).fill(tel);
}

test.describe('on the phone', () => {
	test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

	test('a patient books on the practice sub-domain, keeps the personal link and cancels', async ({ page }) => {
		const problems = watchConsole(page);
		const { slug, practice } = await bookablePractice();
		await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': freshIp() });
		await page.goto(`${practiceOrigin(slug)}/`);
		await expect(page.getByRole('heading', { level: 1, name: practice.name })).toBeVisible();
		await expect(page.locator('link[rel=manifest]')).toHaveAttribute('href', '/booking.webmanifest');
		await expect(page.getByRole('link', { name: 'Appeler' })).toHaveAttribute('href', 'tel:+21671123456');
		await expectAccessible(page, 'booking start');

		const { day, time } = await pickFirstFreeTime(page);
		await expect(page.getByText(new RegExp(`· ${time} · Consultation$`))).toBeVisible();
		await expectNoHorizontalScroll(page, 'booking with times');
		await expectAccessible(page, 'booking times');
		await page.getByRole('button', { name: 'Continuer' }).click();

		await expect(page.getByRole('heading', { name: 'Vos coordonnées' })).toBeVisible();
		await page.getByRole('button', { name: 'Réserver ce rendez-vous' }).click();
		await expect(page.getByLabel('Prénom', { exact: true })).toHaveAttribute('aria-invalid', 'true');
		await fillDetails(page);
		await page.getByRole('checkbox', { name: /rappel la veille/ }).check();
		await expectAccessible(page, 'booking details');
		await page.getByRole('button', { name: 'Réserver ce rendez-vous' }).click();

		await expect(page.getByRole('heading', { name: 'Demande envoyée' })).toBeVisible();
		await expect(page.getByText(time, { exact: true })).toBeVisible();
		const manage = await page.getByRole('textbox', { name: 'Votre lien personnel' }).inputValue();
		expect(manage).toMatch(new RegExp(`^${practiceOrigin(slug).replace(/[.]/g, '\\.')}/rdv#.+`)); // the token stays in the fragment
		await expectAccessible(page, 'booking done');
		expect(day).toMatch(/^\d{4}-\d{2}-\d{2}$/);

		await page.getByRole('link', { name: 'Voir mon rendez-vous' }).click();
		await expect(page).toHaveURL(manage);
		await expect(page.getByRole('heading', { level: 1, name: 'Votre rendez-vous' })).toBeVisible();
		await expect(page.getByText('En attente de confirmation')).toBeVisible();
		await expect(page.locator('body')).not.toContainText('Mounia'); // no patient data on the public page
		await expectAccessible(page, 'manage link');
		await page.getByRole('button', { name: 'Annuler ce rendez-vous' }).click();
		await page.getByRole('dialog').getByRole('button', { name: 'Oui, annuler' }).click();
		await expect(page.getByText('Votre rendez-vous est annulé.')).toBeVisible();
		await expect(page.getByText('Annulé', { exact: true })).toBeVisible();
		await page.reload(); // the personal link keeps working (the token is read from the fragment again)
		await expect(page.getByText('Annulé', { exact: true })).toBeVisible();
		expect(problems).toEqual([]);
	});

	test('a time taken in the meantime (409) sends the patient back to the free times, details kept', async ({ page }) => {
		const { slug } = await bookablePractice();
		await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': freshIp() });
		await page.goto(`${practiceOrigin(slug)}/`);
		const { day, time } = await pickFirstFreeTime(page);
		await page.getByRole('button', { name: 'Continuer' }).click();
		await fillDetails(page);

		// somebody else books the same time (and the only "any practitioner" lane fills up for both practitioners)
		const api = await apiContext();
		const profile = await (await api.get(`/api/public/practices/${slug}`)).json();
		const service = profile.services.find((s: { nameFr: string }) => s.nameFr === 'Consultation');
		for (const practitioner of profile.practitioners) {
			const other = await apiContext();
			const res = await other.post(`/api/public/practices/${slug}/bookings`, {
				data: {
					serviceId: service.id,
					practitionerId: practitioner.id,
					startsAt: `${day}T${time}:00+01:00`,
					firstName: 'Autre',
					lastName: `Patient${practitioner.id}`,
					phone: phone(),
					lang: 'fr',
					reminderConsent: false,
					website: ''
				}
			});
			expect([201, 409], await res.text()).toContain(res.status());
			await other.dispose();
		}
		await api.dispose();

		await page.getByRole('button', { name: 'Réserver ce rendez-vous' }).click();
		await expect(page.getByRole('alert')).toHaveText('Ce créneau vient d’être pris. Choisissez un autre horaire.');
		await expect(page.locator(`input[name=time][value="${time}"]`)).toHaveCount(0);
		await pickFirstFreeTime(page);
		await page.getByRole('button', { name: 'Continuer' }).click();
		await expect(page.getByLabel('Prénom', { exact: true })).toHaveValue('Mounia');
	});
});

test('in Arabic on the app host (/r/<slug>), at 820 and 1440 px', async ({ page }) => {
	const { slug } = await bookablePractice();
	await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': freshIp() });
	await page.goto(`${APP}/r/${slug}?lang=ar`);
	await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
	await expect(page.getByRole('heading', { level: 1, name: 'عيادة الاختبار' })).toBeVisible();
	await expect(page.getByRole('heading', { name: 'احجز موعدك عبر الإنترنت' })).toBeVisible();
	await pickFirstFreeTime(page, /معاينة/);
	for (const width of [820, 1440]) {
		await page.setViewportSize({ width, height: 900 });
		await expectNoHorizontalScroll(page, `booking ar ${width}`);
	}
	await page.getByRole('button', { name: 'متابعة' }).click();
	await fillDetails(page, { first: 'الاسم', last: 'اللقب', phone: 'الهاتف' });
	await page.getByRole('button', { name: 'احجز هذا الموعد' }).click();
	await expect(page.getByRole('heading', { name: 'تمّ إرسال الطلب' })).toBeVisible();
	await expectAccessible(page, 'booking ar done');
});

test('a practice without online booking shows its contact details only', async ({ page }) => {
	const { slug } = await createPractice(admin, { onlineBooking: false });
	await page.goto(`${practiceOrigin(slug)}/`);
	await expect(page.getByText(/ne prend pas de rendez-vous en ligne/)).toBeVisible();
	await expect(page.locator('input[name=service]')).toHaveCount(0);
	await expectAccessible(page, 'booking off');
});

test('an unknown practice and an unknown personal link are explained', async ({ page }) => {
	await page.goto(`${APP}/r/cabinet-qui-n-existe-pas`);
	await expect(page.getByRole('alert')).toHaveText('Ce cabinet est introuvable. Vérifiez l’adresse reçue.');
	await page.goto(`${APP}/rdv#ceci-n-est-pas-un-lien`);
	await expect(page.getByRole('alert')).toContainText('Ce lien n’est pas valide.');
	await page.goto(`${APP}/rdv`); // a link without its token
	await expect(page.getByRole('alert')).toContainText('Ce lien n’est pas valide.');
});
