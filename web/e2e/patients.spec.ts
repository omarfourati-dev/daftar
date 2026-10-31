import { expect, test } from '@playwright/test';
import { APP, axe, newPatient, newPractice, onApp, signIn, watchConsole } from './daily';

/** Stories E1–E4 (list, file, alert, same number, delete) and F1 (treatments, payments, receipt). */

test('E1–E3 – a new patient with a medical alert, the file, the same phone number of the family', async ({ page, request }) => {
	const p = await newPractice(request);
	const problems = watchConsole(page);
	await signIn(page, p);
	await page.goto(APP + '/app/patients');
	await expect(page.getByText('Aucun patient pour le moment.')).toBeVisible();
	await axe(page);
	await page.getByRole('button', { name: 'Nouveau patient' }).click();
	const dialog = page.getByRole('dialog', { name: 'Nouveau patient' });
	await dialog.getByLabel('Prénom').fill('Leila');
	await dialog.getByLabel('Nom', { exact: true }).fill('Famille');
	await dialog.getByLabel('Téléphone').fill('20 000 888');
	await dialog.getByLabel('Année de naissance').fill('1985');
	await dialog.getByLabel('Alerte médicale (allergie, anticoagulant…)').fill('Sous anticoagulant');
	await dialog.getByRole('button', { name: 'Enregistrer' }).click();
	await expect(page.getByRole('heading', { level: 1, name: 'Leila Famille' })).toBeVisible();
	await expect(page.getByRole('note')).toContainText('Sous anticoagulant');
	await expect(page.getByText('né(e) en 1985')).toBeVisible();

	const child = await newPatient(p, { firstName: 'Adam', lastName: 'Famille', phone: '+21620000888' });
	await page.reload();
	await expect(page.getByRole('link', { name: 'Adam Famille' })).toHaveAttribute('href', `/app/patients/${child.id}`);
	await axe(page);

	await page.goto(APP + '/app/patients?q=000888');
	await expect(page.getByText('2 patients')).toBeVisible();
	await expect(page.getByRole('link', { name: /Leila Famille/ })).toContainText('Alerte médicale');
	expect(problems).toEqual([]);
});

test('F1 – treatment, payment in instalments and the printable receipt', async ({ page, request }) => {
	const p = await newPractice(request);
	const patient = await newPatient(p, { firstName: 'Hichem', lastName: 'Caisse' });
	await signIn(page, p);
	await page.goto(`${APP}/app/patients/${patient.id}`);
	await page.getByRole('button', { name: 'Acte', exact: true }).click();
	const treatment = page.getByRole('dialog', { name: 'Nouvel acte' });
	await treatment.getByLabel('Acte', { exact: true }).fill('Bilan de santé');
	await treatment.getByLabel('Prix (DT)').fill('90');
	await treatment.getByRole('button', { name: 'Ajouter l’acte' }).click();
	await expect(page.getByRole('status')).toContainText('Acte ajouté.');
	const balance = page.getByRole('region', { name: 'Solde' });
	await expect(balance).toContainText('90 DT');

	await page.getByRole('button', { name: 'Paiement', exact: true }).click();
	const payment = page.getByRole('dialog', { name: 'Nouveau paiement' });
	await expect(payment.getByLabel('Montant (DT)')).toHaveValue('90');
	await payment.getByLabel('Montant (DT)').fill('40');
	await payment.getByRole('button', { name: 'Enregistrer le paiement' }).click();
	await expect(page.getByRole('status')).toContainText('Paiement enregistré.');
	await expect(balance.getByText('Reste à payer').locator('..')).toContainText('50 DT');
	await axe(page);

	await page.getByRole('link', { name: 'Imprimer le reçu' }).click();
	await expect(page.getByRole('heading', { level: 1, name: /^Reçu n° \d+$/ })).toBeVisible();
	await expect(page.getByText('Montant reçu').locator('..')).toContainText('40 DT');
	await expect(page.getByRole('article').getByText(p.name)).toBeVisible();
	await axe(page);
});

test('E4 – only the owner deletes a patient, after typing the full name', async ({ page, request }) => {
	const p = await newPractice(request);
	const patient = await newPatient(p, { firstName: 'Anis', lastName: 'Supprime' });
	await signIn(page, p);
	await page.goto(`${APP}/app/patients/${patient.id}`);
	await page.getByRole('button', { name: 'Supprimer le patient' }).click();
	const dialog = page.getByRole('dialog', { name: 'Supprimer Anis Supprime ?' });
	const confirm = dialog.getByRole('button', { name: 'Supprimer définitivement' });
	await expect(confirm).toBeDisabled();
	await dialog.getByLabel(/Pour confirmer, tapez le nom complet/).fill('anis supprime');
	await confirm.click();
	await expect(page).toHaveURL(/\/app\/patients$/);
	expect((await request.get(`/api/patients/${patient.id}`, onApp({ Authorization: `Bearer ${p.token}` }))).status()).toBe(404);
});
