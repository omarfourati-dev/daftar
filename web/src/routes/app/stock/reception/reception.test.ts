import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { clock } from '#lib/clock';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, problem, sentJson, type Handler } from '#lib/test-utils';
import { assistant, NOW } from '#lib/agenda/fixtures';
import { dentist } from '#lib/testing/fixtures';
import type { Product, Supplier } from '#lib/types/stock';

const base: Omit<Product, 'id' | 'name'> = {
	category: 'hygiene',
	unit: 'boite',
	supplierId: null,
	supplierName: null,
	minQuantity: 4,
	note: '',
	ean: null,
	active: true,
	quantity: 2,
	status: 'low',
	hasHistory: true,
	expiresOn: null,
	expiry: null,
	averageCostMillimes: null,
	lastUsedAt: null
};
const gloves: Product = { ...base, id: 1, name: 'Gants d’examen', supplierId: 7, averageCostMillimes: 12500 };
const carpules: Product = { ...base, id: 2, name: 'Carpules d’articaïne', unit: 'carpule', category: 'anesthesie' };
const suppliers: Supplier[] = [
	{ id: 7, name: 'Dentalia Sfax', phone: null, whatsapp: '+21620123456', note: '', active: true, products: 1 },
	{ id: 8, name: 'Médical Sud', phone: null, whatsapp: null, note: '', active: true, products: 0 }
];

function receptionApi(extra: Record<string, Handler> = {}) {
	return mockApi({
		'GET /api/stock/products': () => json(200, [gloves, carpules]),
		'GET /api/stock/suppliers': () => json(200, suppliers),
		'GET /api/badges': () => json(200, { onlineRequests: 0, overdue: 0, stockToOrder: 0 }),
		...extra
	});
}

async function addLine(name: string, search: string) {
	await fireEvent.input(await screen.findByLabelText('Ajouter un produit reçu'), { target: { value: search } });
	await fireEvent.click(screen.getByRole('button', { name: name }));
}

describe('/app/stock/reception – a delivery in under a minute', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
	});

	it('enters a delivery line by line with the live total and the last price proposed', async () => {
		receptionApi({
			'POST /api/stock/receipts': () =>
				json(201, { id: 9, receivedOn: '2026-10-30', supplierId: 7, supplierName: 'Dentalia Sfax', reference: 'BL 44', note: '', createdBy: 'Salma', createdAt: NOW, lines: [{}, {}], totalMillimes: 137500 })
		});
		render(Page);
		await addLine('Gants d’examen', 'gan');
		// the supplier of the product is taken over, the last average price is proposed
		expect(screen.getByLabelText('Fournisseur')).toHaveValue('7');
		expect(screen.getByLabelText('Prix unitaire (DT)')).toHaveValue('12,5');
		await fireEvent.click(screen.getByRole('button', { name: 'Un de plus' }));
		await addLine('Carpules d’articaïne', 'carp');
		const prices = screen.getAllByLabelText('Prix unitaire (DT)');
		const quantities = screen.getAllByLabelText('Quantité');
		await fireEvent.input(quantities[1], { target: { value: '50' } });
		await fireEvent.input(prices[1], { target: { value: '0,95' } });
		await fireEvent.click(screen.getAllByRole('button', { name: 'Lot et péremption' })[1]);
		await fireEvent.input(screen.getByLabelText('Lot'), { target: { value: 'A123' } });
		await fireEvent.input(screen.getByLabelText('À utiliser avant'), { target: { value: '2027-03-31' } });
		await fireEvent.input(screen.getByLabelText('N° du bon ou de la facture'), { target: { value: 'BL 44' } });
		expect(screen.getByText('72,500 DT')).toBeInTheDocument(); // 2 × 12,5 + 50 × 0,95
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer la réception' }));
		expect(sentJson('POST /api/stock/receipts')).toEqual({
			receivedOn: '2026-10-30',
			supplierId: 7,
			reference: 'BL 44',
			note: '',
			lines: [
				{ productId: 1, quantity: 2, unitPriceMillimes: 12500, lot: '', expiresOn: null },
				{ productId: 2, quantity: 50, unitPriceMillimes: 950, lot: 'A123', expiresOn: '2027-03-31' }
			]
		});
		expect(await screen.findByText('Réception enregistrée : 2 produit(s), 137,500 DT.')).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Retour au stock' })).toHaveAttribute('href', '/app/stock');
	});

	it('creates a product that does not exist yet without leaving the page', async () => {
		const created: Product = { ...base, id: 5, name: 'Fil de suture', category: 'chirurgie', quantity: 0, status: 'empty' };
		receptionApi({ 'POST /api/stock/products': () => json(201, created) });
		render(Page);
		await fireEvent.input(await screen.findByLabelText('Ajouter un produit reçu'), { target: { value: 'Fil de suture' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Créer « Fil de suture »' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Nouveau produit' }));
		expect(dialog.getByLabelText('Nom')).toHaveValue('Fil de suture');
		await fireEvent.change(dialog.getByLabelText('Catégorie'), { target: { value: 'chirurgie' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer le produit' }));
		expect(sentJson('POST /api/stock/products')).toMatchObject({ name: 'Fil de suture', category: 'chirurgie' });
		expect(await screen.findByRole('button', { name: 'Retirer Fil de suture' })).toBeInTheDocument();
	});

	it('explains what is missing or wrong', async () => {
		receptionApi({ 'POST /api/stock/receipts': () => problem(422, 'day_in_future') });
		render(Page);
		await screen.findByLabelText('Ajouter un produit reçu');
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer la réception' }));
		expect(screen.getByRole('alert')).toHaveTextContent('Ajoutez au moins un produit reçu.');
		await addLine('Gants d’examen', 'gan');
		await fireEvent.input(screen.getByLabelText('Prix unitaire (DT)'), { target: { value: '12,5x' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer la réception' }));
		expect(screen.getByRole('alert')).toHaveTextContent('Prix invalide à la ligne Gants d’examen');
		await fireEvent.input(screen.getByLabelText('Prix unitaire (DT)'), { target: { value: '' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer la réception' }));
		expect(await screen.findByText('La date de réception ne peut pas être dans le futur.')).toBeInTheDocument();
	});

	it('is not for the dentist', async () => {
		auth.set('tok', dentist);
		receptionApi();
		render(Page);
		expect(screen.getByText('Vous n’avez pas accès à cette action.')).toBeInTheDocument();
	});

	it('reads every price back as dinars and asks about an unusual one before saving (review H2)', async () => {
		receptionApi({
			'POST /api/stock/receipts': () =>
				json(201, { id: 9, receivedOn: '2026-10-30', supplierId: 7, supplierName: 'Dentalia Sfax', reference: '', note: '', createdBy: 'Salma', createdAt: NOW, lines: [{}], totalMillimes: 13500 })
		});
		render(Page);
		await addLine('Gants d’examen', 'gan');
		const price = screen.getByLabelText('Prix unitaire (DT)');
		expect(price).toHaveAccessibleDescription('Soit 12,500 DT par boîte');
		await fireEvent.input(price, { target: { value: '13500' } }); // meant 13,500
		expect(price).toHaveAccessibleDescription('Soit 13 500 DT par boîte');
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer la réception' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Prix inhabituel' }));
		expect(dialog.getByText('Gants d’examen : 13 500 DT par boîte ?')).toBeInTheDocument();
		expect(dialog.getByText('plus de 500 DT par boîte')).toBeInTheDocument();
		expect(calls()).not.toContain('POST /api/stock/receipts');
		await fireEvent.click(dialog.getByRole('button', { name: 'Corriger le prix' }));
		expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
		await vi.waitFor(() => expect(document.activeElement).toBe(price));
		await fireEvent.input(price, { target: { value: '40' } }); // 3 × more than 12,5 DT on average
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer la réception' }));
		const again = within(screen.getByRole('dialog', { name: 'Prix inhabituel' }));
		expect(again.getByText('prix moyen actuel : 12,500 DT')).toBeInTheDocument();
		await fireEvent.click(again.getByRole('button', { name: 'Oui, ce prix est juste' }));
		await vi.waitFor(() => expect(calls()).toContain('POST /api/stock/receipts'));
		expect((sentJson('POST /api/stock/receipts') as { lines: { unitPriceMillimes: number }[] }).lines[0].unitPriceMillimes).toBe(40000);
	});

	it('takes whole quantities only (review N2)', async () => {
		receptionApi();
		render(Page);
		await addLine('Gants d’examen', 'gan');
		await fireEvent.input(screen.getByLabelText('Quantité'), { target: { value: '2.5' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer la réception' }));
		expect(screen.getByRole('alert')).toHaveTextContent('Nombre entier seulement');
		expect(calls()).not.toContain('POST /api/stock/receipts');
	});
});
