import { expect, test } from '@playwright/test';
import { adminSession, expectAccessible, expectNoHorizontalScroll, freshIp, practiceOrigin, practiceWithOwner, signInAs, type Session } from './kunden-helpers';

/** Demo with a specialty (12), installer (A4), owner subscription page (I1), invalid reset link (A3). */

let admin: Session;
test.beforeAll(async () => {
	admin = await adminSession();
});

test('the demo starts for the chosen specialty and language', async ({ page }) => {
	await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': freshIp() });
	await page.goto('/app/demo?lang=ar');
	await expect(page.getByRole('heading', { level: 1, name: 'جرّب دفتر مع عيادة وهمية' })).toBeVisible();
	await expectAccessible(page, 'demo ar');
	await page.getByRole('radio', { name: 'العلاج الطبيعي' }).check();
	await page.getByRole('button', { name: 'بدء النسخة التجريبية' }).click();
	await expect(page).toHaveURL(/\/app$/);
	const user = await page.evaluate(() => JSON.parse(localStorage.getItem('daftar.user') ?? '{}'));
	expect(user.practice.isDemo).toBe(true);
	expect(user.practice.specialty).toBe('kinesitherapeute');
	expect(user.lang).toBe('ar');
});

test('the installer sends the main domain to the practice address and shows the steps there', async ({ page }) => {
	const { owner, slug } = await practiceWithOwner(admin);
	await signInAs(page, owner);
	await page.goto('/app/installer');
	await expect(page.getByRole('link', { name: 'Ouvrir l’adresse du cabinet' })).toHaveAttribute('href', `${practiceOrigin(slug)}/app/installer`);

	await signInAs(page, owner, practiceOrigin(slug));
	await page.goto(`${practiceOrigin(slug)}/app/installer`);
	await expect(page.getByRole('heading', { level: 1, name: 'Installer l’application' })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Ouvrir l’adresse du cabinet' })).toHaveCount(0);
	await expect(page.getByRole('heading', { name: /^Sur cet appareil : / })).toBeVisible();
	await expect(page.getByRole('img', { name: 'QR code de l’application du cabinet' }).locator('svg')).toBeVisible();
	await expect(page.locator('link[rel=manifest]')).toHaveAttribute('href', '/manifest.webmanifest');
	const manifest = await (await page.request.get(`${practiceOrigin(slug)}/manifest.webmanifest`)).json();
	expect(manifest.start_url).toBe('/app');
	await page.getByRole('button', { name: 'C’est fait, l’application est installée' }).click();
	await expect(page.getByText('Parfait ! L’étape « Installer l’application » est cochée.')).toBeVisible();
	await expectAccessible(page, 'installer');
});

test('a pilot practice sees its free pilot phase on the subscription page', async ({ page }) => {
	const { owner } = await practiceWithOwner(admin);
	await signInAs(page, owner);
	await page.goto('/app/abonnement');
	await expect(page.getByRole('heading', { level: 1, name: 'Abonnement' })).toBeVisible();
	await expect(page.getByText(/^Phase pilote : Daftar est gratuit pour votre cabinet/)).toBeVisible();
	await expect(page.getByText('Aucune facture pour l’instant.')).toBeVisible();
	await expectAccessible(page, 'abonnement pilot');
	await page.setViewportSize({ width: 390, height: 844 });
	await expectNoHorizontalScroll(page, 'abonnement 390');
});

test('an unknown password reset link is explained without signing anybody in', async ({ page }) => {
	await page.goto('/reinitialiser#ceci-n-est-pas-un-lien');
	await expect(page.getByRole('alert')).toContainText('Ce lien n’est pas valide');
	await expect(page.getByRole('link', { name: 'Aller à la connexion' })).toHaveAttribute('href', '/connexion');
	await expectAccessible(page, 'reset invalid');
});
