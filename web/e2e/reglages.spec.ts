import { expect, test } from '@playwright/test';
import {
	acceptInvitation,
	adminSession,
	closeExtraPages,
	extraPage,
	apiContext,
	expectAccessible,
	expectNoHorizontalScroll,
	freshIp,
	practiceOrigin,
	practiceWithOwner,
	signInAs,
	type Session
} from './kunden-helpers';

/** Owner settings (spec 6, 11.2): practice data, hours and closures, acts, practitioners, team (A2/A3), links, export (E4), account. */

let admin: Session;
test.beforeAll(async () => {
	admin = await adminSession();
});
test.afterEach(closeExtraPages);

test('practice data, hours and closures are saved', async ({ page }) => {
	const { owner, practice } = await practiceWithOwner(admin);
	await signInAs(page, owner);
	await page.goto('/app/reglages');
	await expect(page.getByLabel('Nom du cabinet')).toHaveValue(practice.name);
	await page.getByLabel('Nom du cabinet').fill(`${practice.name} – Sousse`);
	await page.getByLabel('Pas de l’agenda').selectOption('20');
	await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
	await expect(page.getByText('Modifications enregistrées.')).toBeVisible();
	await page.reload();
	await expect(page.getByLabel('Nom du cabinet')).toHaveValue(`${practice.name} – Sousse`);
	await expect(page.getByLabel('Pas de l’agenda')).toHaveValue('20');
	await expectAccessible(page, 'reglages cabinet');

	await page.goto('/app/reglages/horaires');
	await page.getByRole('checkbox', { name: 'Samedi' }).uncheck();
	await page.getByRole('button', { name: 'Enregistrer les horaires' }).click();
	await expect(page.getByText('Modifications enregistrées.')).toBeVisible();
	await page.getByLabel('Du', { exact: true }).fill('2027-08-01');
	await page.getByLabel('Au', { exact: true }).fill('2027-08-15');
	await page.getByLabel(/^Motif/).fill('Congés d’été');
	await page.getByRole('button', { name: 'Ajouter la fermeture' }).click();
	await expect(page.getByText('Du 01/08/2027 au 15/08/2027')).toBeVisible();
	await page.reload();
	await expect(page.getByRole('checkbox', { name: 'Samedi' })).not.toBeChecked();
	await expect(page.getByText('Congés d’été')).toBeVisible();
	await expectAccessible(page, 'reglages horaires');
});

test('acts and practitioners are managed by the owner', async ({ page }) => {
	const { owner } = await practiceWithOwner(admin);
	await signInAs(page, owner);
	await page.goto('/app/reglages/actes');
	await expect(page.getByRole('heading', { name: 'Consultation' })).toBeVisible(); // catalog of the specialty
	await page.getByRole('button', { name: 'Nouvel acte' }).click();
	const dialog = page.getByRole('dialog', { name: 'Nouvel acte' });
	await dialog.getByLabel('Acte (français)').fill('Radio panoramique');
	await dialog.getByLabel('Durée (min)').fill('15');
	await dialog.getByLabel(/^Prix \(DT\)/).fill('35,5');
	await dialog.getByRole('button', { name: 'Enregistrer l’acte' }).click();
	const row = page.locator('li', { has: page.getByRole('heading', { name: 'Radio panoramique' }) });
	await expect(row.getByText('35,500 DT')).toBeVisible();
	await expectAccessible(page, 'reglages actes');

	await page.goto('/app/reglages/praticiens');
	await page.getByRole('button', { name: 'Nouveau praticien' }).click();
	const p = page.getByRole('dialog', { name: 'Nouveau praticien' });
	await p.getByLabel('Nom').fill('Karim Trabelsi');
	await p.getByRole('button', { name: 'Enregistrer le praticien' }).click();
	await expect(page.getByRole('heading', { name: 'Dr. Karim Trabelsi' })).toBeVisible();
	await page.getByRole('button', { name: 'Modifier Dr. Karim Trabelsi' }).click();
	await page.getByRole('dialog').getByRole('checkbox', { name: 'Actif' }).uncheck();
	await page.getByRole('dialog').getByRole('button', { name: 'Enregistrer le praticien' }).click();
	await expect(page.locator('li', { has: page.getByRole('heading', { name: 'Dr. Karim Trabelsi' }) }).getByText('Désactivé')).toBeVisible();
	await expectAccessible(page, 'reglages praticiens');
});

test('A2/A3 – team: invitation link for an assistant, reset link for her, role change', async ({ page, browser }) => {
	const { owner, slug } = await practiceWithOwner(admin);
	await signInAs(page, owner);
	await page.goto('/app/reglages/equipe');
	await page.getByLabel('Rôle', { exact: true }).selectOption('assistant');
	await page.getByRole('button', { name: 'Créer le lien d’invitation' }).click();
	const link = await page.getByRole('textbox', { name: 'Lien d’invitation (Assistant(e))' }).inputValue();
	expect(link).toContain(`${practiceOrigin(slug)}/invitation#`);
	await expectAccessible(page, 'reglages equipe');

	const salma = await acceptInvitation(link.split('#')[1], 'Salma Gharbi');
	await page.reload();
	await expect(page.getByLabel('Rôle de Salma Gharbi')).toHaveValue('assistant');
	await page.getByRole('button', { name: 'Mot de passe oublié de Salma Gharbi' }).click();
	const reset = await page.getByRole('textbox', { name: 'Lien de réinitialisation pour Salma Gharbi' }).inputValue();
	expect(reset).toContain(`${practiceOrigin(slug)}/reinitialiser#`);
	await page.getByLabel('Rôle de Salma Gharbi').selectOption('dentist');
	await expect(page.getByText('Rôle enregistré.')).toBeVisible();

	const salmaPage = await extraPage(browser, { extraHTTPHeaders: { 'X-Forwarded-For': freshIp() } });
	await salmaPage.goto(reset);
	await expect(salmaPage.getByText(salma.email, { exact: false })).toBeVisible();
	await salmaPage.getByLabel('Nouveau mot de passe').fill('mot-de-passe-de-salma');
	await salmaPage.getByLabel('Répéter le mot de passe').fill('mot-de-passe-de-salma');
	await salmaPage.getByRole('button', { name: 'Enregistrer le mot de passe' }).click();
	await expect(salmaPage).toHaveURL(/\/app$/);
});

test('C1/C3 – booking link with QR code, online booking switched on, A4 poster', async ({ page }) => {
	const { owner, slug } = await practiceWithOwner(admin);
	await signInAs(page, owner);
	await page.goto('/app/reglages/reservation');
	await expect(page.getByRole('textbox', { name: 'Adresse de la page' })).toHaveValue(`${practiceOrigin(slug)}/`);
	await expect(page.getByRole('img', { name: 'QR code de la page de réservation' }).locator('svg')).toBeVisible();
	await page.getByRole('checkbox', { name: 'Réservation en ligne activée' }).check();
	await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
	await expect(page.getByText('Modifications enregistrées.')).toBeVisible();
	await expectAccessible(page, 'reglages reservation');

	await page.getByRole('link', { name: 'Imprimer l’affiche A4' }).click();
	const poster = page.getByRole('article', { name: 'Affiche A4' });
	await expect(poster).toContainText('Prenez rendez-vous en ligne');
	await expect(poster).toContainText('احجزوا موعدكم عبر الإنترنت');
	await expect(poster.getByRole('img', { name: 'QR code de la page de réservation' }).locator('svg')).toBeVisible();
	await page.emulateMedia({ media: 'print' });
	await expect(page.getByRole('button', { name: 'Imprimer l’affiche' })).toBeHidden(); // only the sheet is printed
	await page.emulateMedia({ media: 'screen' });
	await expectAccessible(page, 'affiche');
});

test('E4 – waiting-room screen link and data export', async ({ page }) => {
	const { owner, slug } = await practiceWithOwner(admin);
	await signInAs(page, owner);
	await page.goto('/app/reglages/ecran');
	const before = await page.getByRole('textbox', { name: 'Adresse de l’écran' }).inputValue();
	expect(before).toMatch(/\/salle\/[0-9a-f]{16,}$/);
	await page.getByRole('button', { name: 'Générer une nouvelle adresse' }).click();
	await page.getByRole('dialog').getByRole('button', { name: 'Générer la nouvelle adresse' }).click();
	await expect(page.getByText('Nouvelle adresse créée.')).toBeVisible();
	await expect(page.getByRole('textbox', { name: 'Adresse de l’écran' })).not.toHaveValue(before);

	await page.goto('/app/reglages/donnees');
	const download = page.waitForEvent('download');
	await page.getByRole('button', { name: 'Télécharger l’export' }).click();
	const file = await download;
	expect(file.suggestedFilename()).toMatch(new RegExp(`^daftar-export-${slug}-\\d{4}-\\d{2}-\\d{2}\\.json$`));
	const content = JSON.parse(await (await import('node:fs/promises')).readFile((await file.path())!, 'utf8'));
	expect(content.format).toBe('daftar-export/1');
	expect(JSON.stringify(content)).not.toContain('passwordHash');
});

test('my account: name, language and password; other roles only see their account', async ({ page }) => {
	const { owner } = await practiceWithOwner(admin);
	await signInAs(page, owner);
	await page.goto('/app/reglages/compte');
	await page.getByLabel('Nom affiché').fill('Dr Amira B. Salah');
	await page.getByRole('button', { name: 'Enregistrer le nom' }).click();
	await expect(page.getByText('Nom enregistré.')).toBeVisible();
	await page.getByLabel('Mot de passe actuel').fill(owner.password);
	await page.getByLabel('Nouveau mot de passe').fill('un-mot-de-passe-tout-neuf');
	await page.getByLabel('Confirmer le nouveau mot de passe').fill('un-mot-de-passe-tout-neuf');
	await page.getByRole('button', { name: 'Changer le mot de passe' }).click();
	await expect(page.getByText(/Mot de passe changé/)).toBeVisible();
	await page.reload(); // the new token was stored
	await expect(page.getByLabel('Nom affiché')).toHaveValue('Dr Amira B. Salah');
	await page.getByRole('group', { name: 'Langue' }).first().getByRole('button', { name: 'العربية' }).click();
	await expect(page.getByRole('heading', { name: 'حسابي' })).toBeVisible();
	await expectAccessible(page, 'compte ar');

	// an assistant of the same practice sees only her account and the import (the password change issued a new token)
	const token = await page.evaluate(() => localStorage.getItem('daftar.token'));
	const api = await apiContext(freshIp(), token ?? '');
	const inv = await (await api.post('/api/staff/invitations', { data: { role: 'assistant' } })).json();
	await api.dispose();
	const salma = await acceptInvitation(inv.token, 'Salma');
	await signInAs(page, salma);
	await page.goto('/app/reglages');
	await expect(page.getByRole('heading', { name: 'Mon compte' })).toBeVisible();
	const nav = page.getByRole('navigation', { name: 'Rubriques des réglages' });
	await expect(nav.getByRole('link')).toHaveText(['Mon compte', 'Importer depuis Excel', 'Installer l’application']);
	await page.goto('/app/reglages/equipe');
	await expect(page.getByText('Cette page est réservée au titulaire du cabinet.')).toBeVisible();
});

test('settings work at 390 / 820 / 1440 px without horizontal scrolling, in French and Arabic', async ({ page }) => {
	const { owner } = await practiceWithOwner(admin);
	for (const lang of ['fr', 'ar']) {
		await signInAs(page, owner, undefined, lang);
		for (const width of [390, 820, 1440]) {
			await page.setViewportSize({ width, height: 900 });
			for (const path of ['/app/reglages', '/app/reglages/horaires', '/app/reglages/actes', '/app/reglages/equipe', '/app/reglages/reservation']) {
				await page.goto(path);
				await expect(page.getByRole('navigation', { name: lang === 'ar' ? 'أقسام الإعدادات' : 'Rubriques des réglages' })).toBeVisible();
				await expectNoHorizontalScroll(page, `${lang} ${width} ${path}`);
			}
		}
	}
});
