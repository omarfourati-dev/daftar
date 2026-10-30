import { expect, test } from '@playwright/test';
import {
	acceptInvitation,
	ADMIN_EMAIL,
	APP,
	ADMIN_PASSWORD,
	adminSession,
	closeExtraPages,
	extraPage,
	apiContext,
	createPractice,
	expectAccessible,
	expectNoHorizontalScroll,
	freshIp,
	practiceOrigin,
	practiceWithOwner,
	signInAs,
	uniqueSlug,
	watchConsole,
	type Session
} from './kunden-helpers';

/** Stories A1 (practice wizard), A3 (owner reset link), I1 (admin subscriptions), I2 (pilot requests, feedback). */

let admin: Session;
test.beforeAll(async () => {
	admin = await adminSession();
});
test.afterEach(closeExtraPages);

test('A1 – the admin signs in and creates a practice with the wizard, then the owner accepts the invitation', async ({ page, browser }) => {
	const problems = watchConsole(page);
	const slug = uniqueSlug('lac');
	await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': freshIp() });
	await page.goto(APP + '/connexion'); // the form login happens on the app host
	await page.getByLabel('E-mail').fill(ADMIN_EMAIL);
	await page.getByLabel('Mot de passe').fill(ADMIN_PASSWORD);
	await page.getByRole('button', { name: 'Se connecter' }).click();
	await expect(page.getByRole('heading', { level: 1, name: 'Administration' })).toBeVisible();
	await expectAccessible(page, 'admin list');
	await page.getByRole('link', { name: 'Nouveau cabinet' }).click();

	// 1 Cabinet & contact
	await page.getByLabel('Spécialité').selectOption('dentiste');
	await page.getByLabel('Nom du cabinet').fill(`Cabinet Dentaire ${slug}`);
	await page.getByLabel(/^Nom en arabe/).fill('عيادة البحيرة');
	await page.getByLabel('Personne responsable').fill('Dr Amira Ben Salah');
	await page.getByLabel('Téléphone du cabinet').fill('71 123 456');
	await page.getByRole('button', { name: 'Suivant' }).click();
	// 2 Adresse & sous-domaine – live check
	await expect(page.getByRole('heading', { level: 2, name: 'Adresse & sous-domaine' })).toBeVisible();
	await page.getByLabel('Sous-domaine').fill('admin');
	await expect(page.getByText('Ce nom est réservé. Choisissez-en un autre.')).toBeVisible();
	await page.getByLabel('Sous-domaine').fill(slug);
	await expect(page.getByText(`Disponible : ${practiceOrigin(slug)}/`)).toBeVisible();
	await page.getByLabel('Adresse', { exact: true }).fill('12 rue du Lac Léman');
	await page.getByLabel('Ville').fill('Les Berges du Lac');
	await page.getByLabel('Gouvernorat').selectOption('tunis');
	await expectAccessible(page, 'wizard step 2');
	await page.getByRole('button', { name: 'Suivant' }).click();
	// 3 Horaires (defaults) · 4 Praticiens · 5 Actes · 6 Réservation
	await expect(page.getByRole('heading', { level: 2, name: 'Horaires' })).toBeVisible();
	await page.getByRole('button', { name: 'Suivant' }).click();
	await expect(page.getByLabel('Nom 1')).toHaveValue('Amira Ben Salah');
	await page.getByRole('button', { name: 'Suivant' }).click();
	await expect(page.getByLabel('Acte (français) 3')).toHaveValue('Détartrage');
	await page.getByLabel('Prix (DT) 1').fill('40');
	await page.getByRole('button', { name: 'Suivant' }).click();
	await page.getByRole('checkbox', { name: 'Réservation en ligne activée' }).check();
	await page.getByRole('button', { name: 'Suivant' }).click();
	await expect(page.getByRole('heading', { level: 2, name: 'Récapitulatif' })).toBeVisible();
	await expectAccessible(page, 'wizard summary');
	await page.getByRole('button', { name: 'Créer le cabinet' }).click();

	await expect(page.getByRole('heading', { name: `Cabinet Dentaire ${slug} est créé` })).toBeVisible();
	const invitation = await page.getByRole('textbox', { name: 'Lien d’invitation du titulaire' }).inputValue();
	expect(invitation).toMatch(new RegExp(`^${practiceOrigin(slug).replace(/[.]/g, '\\.')}/invitation#.+`));
	await expect(page.getByRole('textbox', { name: 'Page de réservation des patients' })).toHaveValue(`${practiceOrigin(slug)}/`);
	expect(problems).toEqual([]);

	// the owner opens the link on the practice's own address
	const ownerPage = await extraPage(browser, { extraHTTPHeaders: { 'X-Forwarded-For': freshIp() } });
	await ownerPage.goto(invitation);
	await ownerPage.getByLabel('Votre nom').fill('Dr Amira Ben Salah');
	await ownerPage.getByLabel('E-mail').fill(`${slug}@cabinet.test`);
	await ownerPage.getByLabel('Mot de passe', { exact: true }).fill('mot-de-passe-solide-123');
	await ownerPage.getByLabel('Répéter le mot de passe').fill('mot-de-passe-solide-123');
	await ownerPage.getByRole('button', { name: 'Créer mon compte' }).click();
	await expect(ownerPage).toHaveURL(new RegExp(`^${practiceOrigin(slug).replace(/[.]/g, '\\.')}/app`));
});

test('A1/I1 – the admin edits status, plan and notes; A3 – owner reset link sets a new password', async ({ page, browser }) => {
	const { practice, slug, owner } = await practiceWithOwner(admin);
	await signInAs(page, admin);
	await page.goto(`${APP}/app/admin/cabinets/${practice.id}`);
	await expect(page.getByRole('heading', { level: 1, name: practice.name })).toBeVisible();
	await expect(page.getByText(`Titulaire : Dr Amira Ben Salah (${owner.email})`)).toBeVisible();
	await page.getByLabel('Statut').selectOption('active');
	await page.getByLabel('Formule').selectOption('cabinet_mensuel');
	await page.getByLabel(/^Notes internes/).fill('Rencontré au congrès de Sousse');
	await page.getByRole('button', { name: 'Enregistrer les modifications' }).click();
	await expect(page.getByText('Modifications enregistrées.')).toBeVisible();
	await page.reload();
	await expect(page.getByLabel('Statut')).toHaveValue('active');
	await expect(page.getByLabel(/^Notes internes/)).toHaveValue('Rencontré au congrès de Sousse');
	await expectAccessible(page, 'admin edit');

	await page.getByRole('button', { name: 'Créer un lien de réinitialisation' }).click();
	const link = await page.getByRole('textbox', { name: 'Lien de réinitialisation' }).inputValue();
	expect(link).toContain(`${practiceOrigin(slug)}/reinitialiser#`);

	const ownerPage = await extraPage(browser, { extraHTTPHeaders: { 'X-Forwarded-For': freshIp() } });
	await ownerPage.goto(link);
	await expect(ownerPage.getByText(`Choisissez un nouveau mot de passe pour ${owner.email}`, { exact: false })).toBeVisible();
	await ownerPage.getByLabel('Nouveau mot de passe').fill('encore-un-nouveau-mot-de-passe');
	await ownerPage.getByLabel('Répéter le mot de passe').fill('encore-un-nouveau-mot-de-passe');
	await ownerPage.getByRole('button', { name: 'Enregistrer le mot de passe' }).click();
	await expect(ownerPage).toHaveURL(/\/app$/);
	// the link works only once
	await ownerPage.goto(link);
	await expect(ownerPage.getByRole('alert')).toContainText('Ce lien n’est pas valide');
});

test('I1 – subscriptions: the admin creates the next invoice and records a bank transfer; the owner sees it', async ({ page, browser }) => {
	const { practice, owner } = await practiceWithOwner(admin);
	const api = await apiContext(freshIp(), admin.token);
	const patched = await api.patch(`/api/admin/practices/${practice.id}`, { data: { status: 'active', planCode: 'cabinet_mensuel', paidUntil: '2026-12-31' } });
	expect(patched.status(), await patched.text()).toBe(200);
	await api.dispose();

	await signInAs(page, admin);
	await page.goto(APP + '/app/admin/abonnements');
	const card = page.locator('article', { has: page.getByRole('heading', { name: practice.name }) });
	await card.getByRole('button', { name: `Créer la facture suivante – ${practice.name}` }).click();
	await expect(page.getByText(/^Facture DAF-\d{4}-\d{4} créée\.$/)).toBeVisible();
	const number = (await page.getByText(/^Facture DAF-\d{4}-\d{4} créée\.$/).textContent())!.match(/DAF-\d{4}-\d{4}/)![0];
	await expect(card.getByText(number)).toBeVisible();
	await expectAccessible(page, 'admin billing');

	// the owner sees the open invoice and how to pay without online payment
	const ownerPage = await extraPage(browser);
	await signInAs(ownerPage, owner);
	await ownerPage.goto(APP + '/app/abonnement');
	await expect(ownerPage.getByText(number)).toBeVisible();
	await expect(ownerPage.getByText(/Règlement par virement/)).toBeVisible();
	await expectAccessible(ownerPage, 'owner subscription');

	await card.getByRole('button', { name: `Marquer payée ${number}` }).click();
	const dialog = page.getByRole('dialog', { name: `Facture ${number} payée ?` });
	await dialog.getByLabel('Moyen de paiement').selectOption('virement');
	await dialog.getByRole('button', { name: 'Enregistrer le paiement' }).click();
	await expect(page.getByText('Paiement enregistré.')).toBeVisible();
	await ownerPage.reload();
	await expect(ownerPage.locator('li', { hasText: number }).getByText(/^Payée le /)).toBeVisible();
});

test('I2 – a pilot request from the landing form starts a pre-filled wizard and can be deleted', async ({ page }) => {
	const practiceName = `Cabinet Pilote ${uniqueSlug('p')}`;
	const api = await apiContext();
	const sent = await api.post('/api/public/pilot-requests', {
		data: { name: 'Dr Sami Gharbi', practice: practiceName, city: 'Sfax', phone: '98 111 222', email: 'sami@gharbi.test', message: 'Trois médecins.', lang: 'fr', website: '' }
	});
	expect(sent.status(), await sent.text()).toBe(202);
	await api.dispose();

	await signInAs(page, admin);
	await page.goto(APP + '/app/admin/demandes');
	const card = page.locator('article', { has: page.getByRole('heading', { name: practiceName }) });
	await expect(card.getByText('Trois médecins.')).toBeVisible();
	await expect(card.getByRole('link', { name: 'Appeler' })).toHaveAttribute('href', 'tel:+21698111222');
	await expectAccessible(page, 'pilot requests');
	await card.getByRole('button', { name: `Créer le cabinet – ${practiceName}` }).click();
	await expect(page.getByLabel('Nom du cabinet')).toHaveValue(practiceName);
	await expect(page.getByLabel('Personne responsable')).toHaveValue('Dr Sami Gharbi');

	await page.goto(APP + '/app/admin/demandes');
	await card.getByRole('button', { name: `Supprimer – ${practiceName}` }).click();
	await page.getByRole('dialog').getByRole('button', { name: 'Supprimer la demande' }).click();
	await expect(page.getByRole('heading', { name: practiceName })).toHaveCount(0);
});

test('J2 – feedback from a practice reaches the admin', async ({ page, browser }) => {
	const { practice, owner } = await practiceWithOwner(admin);
	const message = `Pouvez-vous ajouter les SMS ? ${uniqueSlug('fb')}`;
	await signInAs(page, owner);
	await page.goto(APP + '/app/reglages/compte');
	await page.getByRole('button', { name: 'Une idée ? Un problème ?' }).click();
	const dialog = page.getByRole('dialog', { name: 'Une idée ? Un problème ?' });
	await dialog.getByLabel('Votre message').fill(message);
	await dialog.getByRole('button', { name: 'Envoyer' }).click();
	await expect(dialog.getByText('Merci ! Votre message est envoyé.')).toBeVisible();

	const adminPage = await extraPage(browser);
	await signInAs(adminPage, admin);
	await adminPage.goto(APP + '/app/admin/retours');
	const item = adminPage.locator('article', { hasText: message });
	await expect(item.getByText(`${practice.name} · Dr Amira Ben Salah`)).toBeVisible();
	await expect(item.getByText('Page : /app/reglages/compte')).toBeVisible();
	await expectAccessible(adminPage, 'feedback list');
});

test('the admin pages work on a phone and in Arabic without horizontal scrolling', async ({ page }) => {
	await createPractice(admin);
	await page.setViewportSize({ width: 390, height: 844 });
	await signInAs(page, admin, undefined, 'ar');
	for (const path of ['/app/admin', '/app/admin/cabinets/nouveau', '/app/admin/abonnements', '/app/admin/demandes', '/app/admin/retours']) {
		await page.goto(APP + path);
		await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
		await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
		await expectNoHorizontalScroll(page, path);
	}
	await expectAccessible(page, 'admin wizard ar 390');
});

test('accepting the owner invitation by API works (helper sanity)', async () => {
	const created = await createPractice(admin);
	const session = await acceptInvitation(created.invitation.token);
	expect(session.user.role).toBe('owner');
});
