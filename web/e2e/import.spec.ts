import { expect, test, type Page } from '@playwright/test';
import { adminSession, apiContext, expectAccessible, expectNoHorizontalScroll, freshIp, practiceWithOwner, signInAs, type Session } from './kunden-helpers';

/** Story E5 – Excel/CSV import with the practice's own column mapping (spec 14). Files are generated in the test. */

let admin: Session;
test.beforeAll(async () => {
	admin = await adminSession();
});

const csv = (rows: string[][]) => Buffer.from('﻿' + rows.map((r) => r.join(';')).join('\r\n'), 'utf8');

async function upload(page: Page, name: string, content: Buffer) {
	await page.getByLabel('Choisir un fichier').setInputFiles({ name, mimeType: 'text/csv', buffer: content });
}

test('patients: upload, mapping, dry run with an error per row, import, report and template', async ({ page }) => {
	const { owner } = await practiceWithOwner(admin);
	await signInAs(page, owner);
	await page.goto('/app/import');
	await expectAccessible(page, 'import start');
	await upload(
		page,
		'patients.csv',
		csv([
			['Nom', 'Prénom', 'GSM', 'Date de naissance', 'Notes', 'Reste à payer'],
			['Ben Salah', 'Amira', '20123456', '12/03/1980', 'Allergie pénicilline', '120'],
			['Trabelsi', 'Karim', '98111222', '01/01/1975', '', ''],
			['Gharbi', 'Sami', '2012', '', '', ''],
			['الشابي', 'منية', '55222333', '', '', '35,500']
		])
	);
	await expect(page.getByText('patients.csv – 4 ligne(s)')).toBeVisible();
	await page.getByRole('button', { name: 'Continuer' }).click();

	// the server's suggestions are pre-selected; the rest is chosen by hand
	await expect(page.getByLabel('Nom', { exact: true })).not.toHaveValue('');
	await expect(page.getByLabel('Téléphone', { exact: true })).not.toHaveValue('');
	await page.getByLabel('Date de naissance', { exact: true }).selectOption({ label: 'D – Date de naissance' });
	await page.getByLabel('Solde à reprendre (DT)', { exact: true }).selectOption({ label: 'F – Reste à payer' });
	await expectAccessible(page, 'import mapping');
	await page.getByRole('button', { name: 'Vérifier le fichier' }).click();

	await expect(page.getByRole('heading', { name: 'Vérification' })).toBeVisible();
	const errors = page.getByRole('table', { name: 'Lignes à corriger' });
	await expect(errors.getByRole('row')).toHaveCount(2); // header + the bad phone
	await expect(errors).toContainText('2012');
	await expectAccessible(page, 'import check');
	await page.getByRole('button', { name: 'Importer 3 ligne(s)' }).click();

	await expect(page.getByRole('heading', { name: 'Import terminé' })).toBeVisible();
	await expect(page.getByText('3 créé(s), 0 complété(s), 0 ignoré(s), 1 en erreur.')).toBeVisible();
	const report = page.waitForEvent('download');
	await page.getByRole('button', { name: 'Télécharger le rapport (CSV)' }).click();
	expect((await report).suggestedFilename()).toMatch(/\.csv$/);
	await page.getByLabel('Nom du modèle').fill('Mon ancien fichier');
	await page.getByRole('button', { name: 'Enregistrer le modèle' }).click();
	await expect(page.getByText('Modèle enregistré.')).toBeVisible();

	// the patients are there, with the Arabic name and the opening balance
	const api = await apiContext(freshIp(), owner.token);
	const all = await (await api.get('/api/patients?q=&limit=50')).json();
	const names = all.items.map((p: { lastName: string }) => p.lastName).sort();
	expect(names).toEqual(['Ben Salah', 'Trabelsi', 'الشابي'].sort());
	await api.dispose();

	// next time the template brings the mapping back
	await page.getByRole('button', { name: 'Importer un autre fichier' }).click();
	await upload(page, 'patients-2.csv', csv([['Nom', 'Prénom', 'GSM', 'Date de naissance', 'Notes', 'Reste à payer'], ['Haddad', 'Rim', '22333444', '', '', '']]));
	await page.getByRole('button', { name: 'Continuer' }).click();
	await page.getByLabel('Modèle enregistré').selectOption({ label: 'Mon ancien fichier' });
	await page.getByRole('button', { name: 'Appliquer le modèle' }).click();
	await expect(page.getByText('Modèle « Mon ancien fichier » appliqué.')).toBeVisible();
	await expect(page.getByLabel('Solde à reprendre (DT)', { exact: true })).toHaveValue('5');
});

test('appointments: future dates become appointments, missing patients are created', async ({ page }) => {
	const { owner } = await practiceWithOwner(admin, { allDay: true });
	const day = new Date(Date.now() + 3 * 86_400_000);
	const ddmmyyyy = `${String(day.getDate()).padStart(2, '0')}/${String(day.getMonth() + 1).padStart(2, '0')}/${day.getFullYear()}`;
	await signInAs(page, owner);
	await page.goto('/app/import');
	await page.getByRole('radio', { name: /Des rendez-vous/ }).check();
	await upload(
		page,
		'agenda.csv',
		csv([
			['Date', 'Heure', 'Patient', 'Téléphone'],
			[ddmmyyyy, '09:00', 'Amira Ben Salah', '20123456'],
			[ddmmyyyy, '10:00', 'Karim Trabelsi', '98111222']
		])
	);
	await page.getByRole('button', { name: 'Continuer' }).click();
	await page.getByLabel('Date', { exact: true }).selectOption({ label: 'A – Date' });
	await page.getByLabel('Heure', { exact: true }).selectOption({ label: 'B – Heure' });
	await page.getByLabel('Nom complet', { exact: true }).selectOption({ label: 'C – Patient' });
	await page.getByLabel('Téléphone', { exact: true }).selectOption({ label: 'D – Téléphone' });
	await page.getByLabel('Ordre dans « Nom complet »').selectOption('first_last');
	await page.getByRole('button', { name: 'Vérifier le fichier' }).click();
	await expect(page.getByText('Aucune erreur trouvée.')).toBeVisible();
	await page.getByRole('button', { name: 'Importer 2 ligne(s)' }).click();
	await expect(page.getByText('2 créé(s), 0 complété(s), 0 ignoré(s), 0 en erreur.')).toBeVisible();
	await expect(page.getByText('2 patient(s) créé(s) au passage.')).toBeVisible();
});

test('a wrong file is refused before upload; required columns are explained; works at 390 px in Arabic', async ({ page }) => {
	const { owner } = await practiceWithOwner(admin);
	await signInAs(page, owner);
	await page.goto('/app/import');
	await page.getByLabel('Choisir un fichier').setInputFiles({ name: 'photo.png', mimeType: 'image/png', buffer: Buffer.from('png') });
	await expect(page.getByRole('alert')).toContainText('Format non reconnu.');
	await upload(page, 'liste.csv', csv([['Colonne1', 'Colonne2'], ['x', 'y']]));
	await page.getByRole('button', { name: 'Continuer' }).click();
	await page.getByLabel('Nom', { exact: true }).selectOption('');
	await page.getByLabel('Nom complet', { exact: true }).selectOption('');
	await page.getByRole('button', { name: 'Vérifier le fichier' }).click();
	await expect(page.getByText('Choisissez la colonne du nom complet, ou celles du nom et du prénom.')).toBeVisible();

	await page.setViewportSize({ width: 390, height: 844 });
	await signInAs(page, owner, undefined, 'ar');
	await page.goto('/app/import');
	await expect(page.getByRole('heading', { level: 1, name: 'استيراد من Excel' })).toBeVisible();
	await expectNoHorizontalScroll(page, 'import ar 390');
});
