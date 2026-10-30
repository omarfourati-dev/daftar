import { expect, test } from '@playwright/test';
import { axe, newPractice, signIn, watchConsole } from './daily';

/** Story D1 (waiting room, screen, ticket page – never a name in public) and 16.2 ("Patient suivant"). */

test('D1 – walk-in ticket, call, consultation, done; screen and ticket page show numbers only', async ({ page, request, browser }) => {
	const p = await newPractice(request);
	const problems = watchConsole(page);
	await signIn(page, p);
	await page.goto('/app/salle');
	await expect(page.getByText('Personne en salle d’attente.')).toBeVisible();
	await axe(page);

	await page.getByRole('button', { name: 'Nouveau ticket' }).click();
	const dialog = page.getByRole('dialog', { name: 'Nouveau ticket' });
	await dialog.getByText('Juste un nom').click();
	await dialog.getByLabel('Nom', { exact: true }).fill('Mme Secrète');
	await dialog.getByLabel('Téléphone (facultatif)').fill('20 000 555');
	await dialog.getByRole('button', { name: 'Donner le ticket' }).click();
	await expect(dialog.getByText('Ticket 1 pour Mme Secrète')).toBeVisible();
	await expect(dialog.getByRole('img', { name: 'QR code du ticket 1' }).locator('svg')).toBeVisible();
	await expect(dialog.getByRole('link', { name: 'WhatsApp' })).toHaveAttribute('href', /^https:\/\/wa\.me\/21620000555\?text=/);
	await axe(page);
	await dialog.getByRole('button', { name: 'Fermer' }).last().click();

	const [entry] = await p.api.get('/api/queue');
	// the public pages: number yes, name never
	const visitor = await browser.newContext({ locale: 'fr-FR', timezoneId: 'Africa/Tunis' });
	const screenPage = await visitor.newPage();
	await screenPage.goto(`/salle/${p.displayToken}`);
	await expect(screenPage.getByRole('heading', { level: 1, name: p.name })).toBeVisible();
	await expect(screenPage.getByRole('region', { name: /Prochains tickets/ }).getByText('1', { exact: true })).toBeVisible();
	await expect(screenPage.locator('body')).not.toContainText('Secrète');
	await axe(screenPage);
	const ticketPage = await visitor.newPage();
	await ticketPage.goto(`/ticket/${entry.ticketToken}`);
	await expect(ticketPage.getByText('1', { exact: true }).first()).toBeVisible();
	await expect(ticketPage.getByText('Vous êtes le prochain.')).toBeVisible();
	await expect(ticketPage.locator('body')).not.toContainText('Secrète');
	await axe(ticketPage);

	const card = page.getByRole('listitem').filter({ hasText: 'Mme Secrète' });
	await card.getByRole('button', { name: 'Appeler' }).click();
	await expect(page.getByRole('status')).toHaveText('Ticket 1 : Appelé.');
	await expect(page.getByRole('region', { name: 'Écran de la salle d’attente' })).toContainText('1');
	await ticketPage.reload();
	await expect(ticketPage.getByRole('status')).toHaveText('C’est votre tour ! Présentez-vous à l’accueil.');
	await page.getByRole('listitem').filter({ hasText: 'Mme Secrète' }).getByRole('button', { name: 'En consultation' }).click();
	await expect(page.getByRole('status')).toHaveText('Ticket 1 : En consultation.');
	await page.getByRole('listitem').filter({ hasText: 'Mme Secrète' }).getByRole('button', { name: 'Terminé' }).click();
	await expect(page.getByRole('region', { name: 'Terminés aujourd’hui' })).toContainText('Mme Secrète');
	await visitor.close();
	expect(problems).toEqual([]);
});

test('16.2 – "Patient suivant" shows now / then and calls the next one', async ({ page, request }) => {
	const p = await newPractice(request);
	await p.api.post('/api/queue', { name: 'Premier Arrivé', phone: '20 000 601' });
	await p.api.post('/api/queue', { name: 'Second Arrivé' });
	await signIn(page, p);
	await page.goto('/app/salle');
	await page.getByRole('link', { name: 'Patient suivant' }).click();
	await expect(page.getByRole('heading', { level: 1, name: 'Patient suivant' })).toBeVisible();
	const now = page.getByRole('region', { name: 'Maintenant' });
	await expect(now).toContainText('Premier Arrivé');
	await expect(page.getByRole('region', { name: 'Ensuite' })).toContainText('Second Arrivé');
	await axe(page);
	await page.getByRole('button', { name: 'Appeler le suivant' }).click();
	await expect(page.getByRole('status')).toHaveText('Ticket 1 appelé : Premier Arrivé.');
	await expect(now).toContainText('Second Arrivé');
	await page.getByRole('button', { name: 'Appeler le suivant' }).click();
	await expect(page.getByRole('status')).toHaveText('Ticket 2 appelé : Second Arrivé.');
	await expect(now).toContainText('Personne n’attend.');
	await expect(page.getByRole('button', { name: 'Appeler le suivant' })).toBeDisabled();
});
