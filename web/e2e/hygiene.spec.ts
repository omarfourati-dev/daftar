import { expect, test, type Page } from '@playwright/test';
import { APP, axe, newPractice, signIn } from './daily';

/** Spec stock-hygiène 5.1, 5.2: plan of the specialty, "Hygiène du jour" (card and page), proof, register, Arabic. */

async function noHorizontalScroll(page: Page, label: string) {
	const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
	expect(overflow, `${label} – horizontal overflow in px`).toBeLessThanOrEqual(0);
}

test('hygiene on the phone: plan of the specialty, tick on "Aujourd’hui", failed check, register', async ({ page, request }) => {
	const p = await newPractice(request); // open every day 00:00–23:59: daily tasks are due today
	await page.setViewportSize({ width: 360, height: 780 });
	await signIn(page, p);
	await page.goto(APP + '/app/hygiene?tab=taches');
	await page.getByRole('button', { name: 'Proposer un plan d’hygiène' }).click();
	await expect(page.getByText(/équipement\(s\) et \d+ tâche\(s\) ajoutés\./)).toBeVisible();
	await expect(page.getByRole('list', { name: 'Tâches' })).toContainText('Désinfection des surfaces');
	await axe(page);
	await noHorizontalScroll(page, 'hygiene plan 360');

	// a weekly task of today, created by hand
	await page.getByRole('button', { name: 'Nouvelle tâche' }).click();
	const dialog = page.getByRole('dialog', { name: 'Nouvelle tâche' });
	await dialog.getByLabel('Tâche').fill('Contrôle du stérilisateur');
	await dialog.getByLabel('Fréquence').selectOption('every_n_days');
	await dialog.getByLabel('Nombre de jours').fill('3');
	await dialog.getByRole('button', { name: 'Enregistrer la tâche' }).click();
	await expect(page.getByRole('list', { name: 'Tâches' })).toContainText('Tous les 3 jours');

	// the card on "Aujourd'hui": one tap, the badge goes down
	await page.goto(APP + '/app');
	const card = page.getByRole('region', { name: 'Hygiène du jour' });
	await card.getByRole('button', { name: 'Fait – Désinfection des surfaces' }).click();
	await expect(card.getByText(/Fait par Dr Amira Ben Salem à \d\d:\d\d/)).toBeVisible();
	await axe(page);
	await noHorizontalScroll(page, 'today with hygiene 360');

	// a failed check with its note on the hygiene page
	await page.goto(APP + '/app/hygiene');
	const row = page.getByRole('listitem').filter({ hasText: 'Contrôle du stérilisateur' });
	await row.getByRole('button', { name: 'Résultat et note – Contrôle du stérilisateur' }).click();
	await row.getByLabel('Non conforme').check();
	await row.getByLabel('Note').fill('Joint de porte usé');
	await row.getByRole('button', { name: 'Enregistrer' }).click();
	await expect(row.getByText('Joint de porte usé')).toBeVisible();
	await axe(page);

	// the register shows both proofs and can be printed
	await page.getByRole('button', { name: 'Historique' }).click();
	const register = page.getByRole('table', { name: 'Registre d’hygiène' });
	await expect(register.getByRole('row', { name: /Contrôle du stérilisateur/ })).toContainText('Non conforme');
	await expect(register.getByRole('row', { name: /Désinfection des surfaces/ })).toContainText('Fait');
	await axe(page);
	await noHorizontalScroll(page, 'register 360');
});

test('hygiene in Arabic, right to left', async ({ page, request }) => {
	const p = await newPractice(request);
	await p.api.post('/api/hygiene/starter');
	await signIn(page, p, 'ar');
	await page.goto(APP + '/app/hygiene');
	await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
	await expect(page.getByRole('heading', { level: 1, name: 'النظافة والتعقيم' })).toBeVisible();
	await expect(page.getByRole('list', { name: 'مهام اليوم' })).toBeVisible();
	await axe(page);
	await page.setViewportSize({ width: 360, height: 780 });
	await noHorizontalScroll(page, 'hygiene ar 360');
});
