import { expect, test } from '@playwright/test';
import { axe, newPatient, newPractice, signIn } from './daily';

/** Story F2 (cash book, open balances) and 16.3 (cash closing verified by the owner). */

test('F2 + 16.3 – the cash of the day, the closing with its difference and the owner’s verification', async ({ page, request }) => {
	const p = await newPractice(request);
	const patient = await newPatient(p, { firstName: 'Meriem', lastName: 'Kasse' });
	await p.api.post(`/api/patients/${patient.id}/treatments`, { label: 'Consultation', priceMillimes: 100000 });
	await p.api.post(`/api/patients/${patient.id}/payments`, { amountMillimes: 50000, method: 'cash' });
	await p.api.post(`/api/patients/${patient.id}/payments`, { amountMillimes: 20000, method: 'd17' });

	await signIn(page, p);
	await page.goto('/app/caisse');
	await expect(page.getByText('Encaissé ce jour').locator('..')).toContainText('70 DT');
	await expect(page.getByRole('list', { name: 'Par mode de paiement' })).toContainText('Espèces');
	await expect(page.getByRole('table', { name: 'Paiements du jour' })).toContainText('Meriem Kasse');
	await expect(page.getByRole('region', { name: 'Montants dus' })).toContainText('30 DT');
	await axe(page);

	const closing = page.getByRole('region', { name: 'Clôture de caisse' });
	await expect(closing.getByText('Espèces attendues').locator('..')).toContainText('50 DT');
	await closing.getByLabel('Espèces comptées (DT)').fill('45');
	await closing.getByRole('button', { name: 'Clôturer la caisse' }).click();
	await expect(closing.getByText('Manque 5 DT')).toBeVisible();
	await closing.getByRole('button', { name: 'Valider la clôture' }).click();
	await expect(closing.getByText(/^Validée par Dr Amira Ben Salem le /)).toBeVisible();
	await expect(closing.getByRole('button', { name: 'Recompter' })).toHaveCount(0);
});

test('16.3 – the owner’s dashboard lists closed days that are not verified yet', async ({ page, request }) => {
	const p = await newPractice(request);
	const patient = await newPatient(p);
	await p.api.post(`/api/patients/${patient.id}/payments`, { amountMillimes: 30000, method: 'cash' });
	const today = (await p.api.get('/api/cash')).day as string;
	await p.api.post('/api/cash/close', { day: today, countedCashMillimes: 30000 });
	await signIn(page, p);
	await page.goto('/app');
	const check = page.getByRole('region', { name: 'Caisses à vérifier' });
	await expect(check.getByRole('link')).toContainText('caisse juste');
	await check.getByRole('link').click();
	await expect(page).toHaveURL(new RegExp(`/app/caisse\\?day=${today}$`));
	await expect(page.getByRole('button', { name: 'Valider la clôture' })).toBeVisible();
});
