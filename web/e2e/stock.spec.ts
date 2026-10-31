import { expect, test, type Page } from '@playwright/test';
import { APP, axe, currentQuarter, newPatient, newPractice, signIn } from './daily';

/** Spec stock-hygiène 4: start list, delivery, use in three taps, à commander, use per act, owner's figures. */

async function noHorizontalScroll(page: Page, label: string) {
	const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
	expect(overflow, `${label} – horizontal overflow in px`).toBeLessThanOrEqual(0);
}

test('stock on the phone: start list, delivery of two lines, use in three taps, to order', async ({ page, request }) => {
	const p = await newPractice(request);
	await page.setViewportSize({ width: 360, height: 780 });
	await signIn(page, p);
	await page.goto(APP + '/app/stock');
	await expect(page.getByRole('heading', { name: 'Aucun produit pour l’instant' })).toBeVisible();
	await axe(page);
	await page.getByRole('button', { name: 'Proposer une liste de départ' }).click();
	await expect(page.getByText(/produit\(s\) ajouté\(s\)/)).toBeVisible();
	const list = page.getByRole('list', { name: 'Produits en stock' });
	await expect(list.getByText('Seringues 5 ml')).toBeVisible();
	await noHorizontalScroll(page, 'stock list 360');

	// delivery: supplier created on the way, two lines, live total
	await page.getByRole('link', { name: 'Réception' }).click();
	await expect(page.getByRole('heading', { level: 1, name: 'Réception' })).toBeVisible();
	await page.getByRole('button', { name: 'Nouveau fournisseur' }).click();
	const dialog = page.getByRole('dialog', { name: 'Nouveau fournisseur' });
	await dialog.getByLabel('Nom').fill('Pharma Distribution Tunis');
	await dialog.getByLabel('WhatsApp').fill('20 123 456');
	await dialog.getByRole('button', { name: 'Enregistrer le fournisseur' }).click();
	await expect(dialog).toHaveCount(0);
	await expect(page.getByRole('combobox', { name: /^Fournisseur/ })).toHaveValue(/\d+/);
	await page.getByLabel('Ajouter un produit reçu').fill('serin');
	await page.getByRole('button', { name: 'Seringues 5 ml' }).click();
	await page.getByLabel('Quantité').fill('60');
	await page.getByLabel('Prix unitaire (DT)').fill('0,180');
	await page.getByLabel('Ajouter un produit reçu').fill('gants');
	await page.getByRole('button', { name: 'Gants d’examen' }).click();
	await page.getByLabel('Prix unitaire (DT)').nth(1).fill('13,5');
	await expect(page.getByText('24,300 DT')).toBeVisible(); // 60 × 0,180 + 1 × 13,5
	await axe(page);
	await noHorizontalScroll(page, 'reception 360');
	await page.getByRole('button', { name: 'Enregistrer la réception' }).click();
	await expect(page.getByText('Réception enregistrée : 2 produit(s), 24,300 DT.')).toBeVisible();
	await page.getByRole('link', { name: 'Retour au stock' }).click();
	await expect(list.getByRole('button', { name: /Seringues 5 ml/ })).toContainText('60 pièces');

	// use in three taps
	await page.getByRole('button', { name: 'Sortie' }).click();
	const use = page.getByRole('dialog', { name: 'Sortie de stock' });
	await use.getByRole('button', { name: /Seringues 5 ml/ }).click();
	await use.getByRole('button', { name: 'Enregistrer la sortie' }).click();
	await expect(page.getByText('Sortie enregistrée : 1 pièce de Seringues 5 ml. Reste 59 pièces.')).toBeVisible();

	// the gloves (1 box, threshold 4) are to be ordered from the supplier of their delivery
	await page.getByRole('button', { name: /^À commander/ }).click();
	const group = page.getByRole('region', { name: 'Pharma Distribution Tunis' });
	await expect(group.getByText('Gants d’examen')).toBeVisible();
	await expect(group.getByRole('link', { name: 'Commander par WhatsApp' })).toHaveAttribute('href', /^https:\/\/wa\.me\/21620123456\?text=/);
	await axe(page);
	await noHorizontalScroll(page, 'to order 360');
});

test('material of an appointment and the owner’s figures; Arabic right to left', async ({ page, request }) => {
	const p = await newPractice(request);
	await p.api.post('/api/stock/products/starter');
	const syringes = (await p.api.get('/api/stock/products')).find((x: { name: string }) => x.name === 'Seringues 5 ml');
	await p.api.post('/api/stock/receipts', { lines: [{ productId: syringes.id, quantity: 100, unitPriceMillimes: 200 }] });
	const patient = await newPatient(p, { firstName: 'Hela', lastName: 'Materiel' });
	const now = currentQuarter();
	const created = await p.api.post('/api/appointments', {
		patientId: patient.id,
		startsAt: now.startsAt,
		durationMin: 10,
		serviceId: p.services[0].id,
		reason: 'Consultation',
		practitionerId: p.practitioners[0].id
	});
	await p.api.post(`/api/appointments/${created.appointment.id}/status`, { status: 'arrived' });

	await signIn(page, p);
	await page.goto(APP + '/app/agenda');
	await page.getByRole('button', { name: new RegExp(`${now.time} Hela Materiel`) }).click();
	const dialog = page.getByRole('dialog', { name: 'Hela Materiel' });
	await dialog.getByRole('button', { name: 'Noter le matériel utilisé' }).click();
	const material = dialog.getByRole('region', { name: 'Matériel utilisé' });
	await material.getByLabel('Produit').selectOption({ label: 'Seringues 5 ml' });
	await material.getByLabel('Quantité').fill('2');
	await material.getByRole('button', { name: 'Ajouter' }).click();
	await expect(material.getByText('Noté : 2 pièces de Seringues 5 ml.')).toBeVisible();
	await axe(page);

	await page.goto(APP + '/app/statistiques');
	const figures = page.getByRole('region', { name: 'Matériel du mois' });
	await expect(figures.getByRole('table', { name: 'Coût du matériel par acte' })).toContainText(p.services[0].nameFr);
	await axe(page);

	await signIn(page, p, 'ar');
	await page.goto(APP + '/app/stock');
	await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
	await expect(page.getByRole('heading', { level: 1, name: 'المخزون' })).toBeVisible();
	await expect(page.getByRole('link', { name: 'استلام' })).toBeVisible();
	await axe(page);
	await page.setViewportSize({ width: 360, height: 780 });
	await noHorizontalScroll(page, 'stock ar 360');
});
