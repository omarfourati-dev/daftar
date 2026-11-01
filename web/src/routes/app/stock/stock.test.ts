import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { clock } from '#lib/clock';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, labelInNameProblems, mockApi, noContent, problem, sentJson, type Handler } from '#lib/test-utils';
import { assistant, NOW, owner } from '#lib/agenda/fixtures';
import { dentist } from '#lib/testing/fixtures';
import type { Movement, Product, Supplier } from '#lib/types/stock';

function product(overrides: Partial<Product> = {}): Product {
	return {
		id: 1,
		name: 'Gants d’examen',
		category: 'hygiene',
		unit: 'boite',
		supplierId: 7,
		supplierName: 'Dentalia Sfax',
		minQuantity: 4,
		note: '',
		ean: null,
		active: true,
		quantity: 10,
		status: 'ok',
		hasHistory: true,
		expiresOn: null,
		expiry: null,
		averageCostMillimes: 12000,
		lastUsedAt: null,
		...overrides
	};
}

const gloves = product();
const carpules = product({
	id: 2,
	name: 'Carpules d’articaïne',
	category: 'anesthesie',
	unit: 'carpule',
	minQuantity: 50,
	quantity: 40,
	status: 'low',
	expiresOn: '2026-11-20',
	expiry: 'soon',
	lastUsedAt: '2026-10-30T08:40:00+01:00'
});
const composite = product({ id: 3, name: 'Composite', category: 'restauration', unit: 'piece', quantity: 0, status: 'empty', minQuantity: 2 });
const LOG = 'GET /api/audit-log?entity=stock_receipt,stock_receipt_line,stock_movement,stock_product,supplier&limit=30';
const receiptMove: Movement = {
	id: 60, productId: 1, productName: 'Gants d’examen', unit: 'boite', kind: 'receipt', quantity: 10, serviceId: null, serviceName: null,
	serviceNameAr: null, appointmentId: null, patientName: null, receiptId: 8, receiptLineId: 81, receivedOn: '2026-10-28', reason: '',
	unitCostMillimes: 13500000, createdBy: 'Nisrine', createdAt: '2026-11-01T09:00:00+01:00'
};
const supplier: Supplier = { id: 7, name: 'Dentalia Sfax', phone: '+21674000000', whatsapp: '+21620123456', note: 'Livre le mardi', active: true, products: 2 };

function stockApi(extra: Record<string, Handler> = {}, products: Product[] = [gloves, carpules, composite]) {
	return mockApi({
		'GET /api/stock/products': () => json(200, products),
		'GET /api/stock/suppliers': () => json(200, [supplier]),
		'GET /api/badges': () => json(200, { onlineRequests: 0, overdue: 0, stockToOrder: 2 }),
		...extra
	});
}

describe('/app/stock – the material of the practice', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
		history.replaceState(null, '', '/app/stock');
	});

	it('lists the products with their stock, traffic light and expiry, and filters them', async () => {
		stockApi();
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'Stock' })).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Réception' })).toHaveAttribute('href', '/app/stock/reception');
		const list = within(await screen.findByRole('list', { name: 'Produits en stock' }));
		const row = (name: string) => list.getByText(name).closest('button') as HTMLElement;
		expect(row('Gants d’examen')).toHaveTextContent('10 boîtes');
		expect(row('Gants d’examen')).toHaveTextContent('En stock');
		expect(row('Carpules d’articaïne')).toHaveTextContent('40 carpules');
		expect(row('Carpules d’articaïne')).toHaveTextContent('À commander');
		expect(row('Carpules d’articaïne')).toHaveTextContent('Périme le 20/11/2026');
		expect(row('Composite')).toHaveTextContent('Épuisé');
		expect(screen.getByRole('button', { name: 'À commander 2' })).toBeInTheDocument();
		await fireEvent.input(screen.getByPlaceholderText('Rechercher un produit'), { target: { value: 'articaine' } });
		expect(list.queryByText('Gants d’examen')).not.toBeInTheDocument();
		expect(list.getByText('Carpules d’articaïne')).toBeInTheDocument();
		expect(labelInNameProblems()).toEqual([]);
	});

	it('records a use in three taps: Sortie, the product, Enregistrer', async () => {
		stockApi({
			'GET /api/services': () => json(200, []),
			'POST /api/stock/movements': () =>
				json(201, {
					movement: { id: 50, productId: 2, productName: 'Carpules d’articaïne', unit: 'carpule', kind: 'use', quantity: -1 } as Movement,
					product: { ...carpules, quantity: 39 }
				})
		});
		render(Page);
		await screen.findByRole('list', { name: 'Produits en stock' });
		await fireEvent.click(screen.getByRole('button', { name: 'Sortie' })); // 1
		const dialog = within(screen.getByRole('dialog', { name: 'Sortie de stock' }));
		const recent = within(dialog.getByRole('region', { name: 'Récemment utilisés' }));
		await fireEvent.click(recent.getByRole('button', { name: /Carpules d’articaïne/ })); // 2
		expect(dialog.getByText('En stock : 40 carpules')).toBeInTheDocument();
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer la sortie' })); // 3
		expect(sentJson('POST /api/stock/movements')).toEqual({ productId: 2, kind: 'use', quantity: 1 });
		expect(await screen.findByText('Sortie enregistrée : 1 carpule de Carpules d’articaïne. Reste 39 carpules.')).toBeInTheDocument();
		expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
	});

	it('proposes the start list when the stock is empty', async () => {
		let listed: Product[] = [];
		stockApi({
			'GET /api/stock/products': () => json(200, listed),
			'POST /api/stock/products/starter': () => {
				listed = [gloves];
				return json(200, { created: 12 });
			}
		});
		render(Page);
		expect(await screen.findByRole('heading', { name: 'Aucun produit pour l’instant' })).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Proposer une liste de départ' }));
		expect(await screen.findByText('12 produit(s) ajouté(s). Notez les quantités à la prochaine réception.')).toBeInTheDocument();
		expect(await screen.findByText('Gants d’examen')).toBeInTheDocument();
	});

	it('groups what to order by supplier with a ready WhatsApp message', async () => {
		stockApi({
			'GET /api/stock/to-order': () =>
				json(200, {
					count: 2,
					groups: [
						{ supplier: { id: 7, name: 'Dentalia Sfax', phone: '+21674000000', whatsapp: '+21620123456' }, items: [{ productId: 2, name: 'Carpules d’articaïne', unit: 'carpule', quantity: 40, minQuantity: 50, suggested: 60 }] },
						{ supplier: null, items: [{ productId: 3, name: 'Composite', unit: 'piece', quantity: 0, minQuantity: 2, suggested: 4 }] }
					]
				})
		});
		render(Page);
		await screen.findByRole('list', { name: 'Produits en stock' });
		await fireEvent.click(screen.getByRole('button', { name: 'À commander 2' }));
		const dentalia = within(await screen.findByRole('region', { name: 'Dentalia Sfax' }));
		expect(dentalia.getByText('Commander 60 carpules')).toBeInTheDocument();
		const link = dentalia.getByRole('link', { name: 'Commander par WhatsApp' });
		const text = decodeURIComponent(link.getAttribute('href') ?? '');
		expect(text.startsWith('https://wa.me/21620123456?text=Bonjour Dentalia Sfax, ici Cabinet du Lac.')).toBe(true);
		expect(text).toContain('– Carpules d’articaïne : 60 carpules');
		expect(dentalia.getByRole('link', { name: 'Appeler' })).toHaveAttribute('href', 'tel:+21674000000');
		const loose = within(screen.getByRole('region', { name: 'Sans fournisseur' }));
		expect(loose.queryByRole('link')).not.toBeInTheDocument();
		expect(location.search).toBe('?tab=commander');
	});

	it('counts the shelves and writes only the differences (inventory)', async () => {
		stockApi({ 'POST /api/stock/inventory': () => json(200, { adjusted: 1, products: [{ ...gloves, quantity: 8 }] }) });
		history.replaceState(null, '', '/app/stock?tab=inventaire');
		render(Page);
		const list = within(await screen.findByRole('list', { name: 'Inventaire' }));
		await fireEvent.input(list.getByLabelText(/Gants d’examen/), { target: { value: '8' } });
		await fireEvent.input(list.getByLabelText(/Composite/), { target: { value: '0' } });
		expect(screen.getByText('1 écart(s)')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer l’inventaire' }));
		expect(sentJson('POST /api/stock/inventory')).toEqual({
			reason: 'Inventaire du 30/10/2026',
			counts: [
				{ productId: 1, counted: 8 },
				{ productId: 3, counted: 0 }
			]
		});
		expect(await screen.findByText('Inventaire enregistré : 1 produit(s) corrigé(s).')).toBeInTheDocument();
	});

	it('lets the dentist record a use but not receive, count or see prices', async () => {
		auth.set('tok', dentist);
		stockApi();
		render(Page);
		await screen.findByRole('list', { name: 'Produits en stock' });
		expect(screen.queryByRole('link', { name: 'Réception' })).not.toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Sortie' })).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Inventaire' })).not.toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Nouveau produit' })).not.toBeInTheDocument();
	});

	it('lets the owner delete a movement with a reason and shows the change log', async () => {
		auth.set('tok', owner);
		const use: Movement = {
			id: 50, productId: 1, productName: 'Gants d’examen', unit: 'boite', kind: 'use', quantity: -3, serviceId: null, serviceName: null,
			appointmentId: null, patientName: null, receiptId: null, reason: '', unitCostMillimes: 12000, createdBy: 'Nisrine', createdAt: '2026-10-30T09:00:00+01:00',
			serviceNameAr: null, receiptLineId: null, receivedOn: null
		};
		const fetch = stockApi({
			'GET /api/stock/movements?limit=100': () => json(200, [use]),
			[LOG]: () =>
				json(200, [{ id: 1, at: '2026-10-30T09:10:00+01:00', userName: 'Dr Amira', entity: 'stock_movement', entityId: 7, action: 'delete', before: { kind: 'use', quantity: -2, product: 'Composite' }, after: null, reason: 'Doublon' }]),
			'DELETE /api/stock/movements/50': () => noContent()
		});
		history.replaceState(null, '', '/app/stock?tab=mouvements');
		render(Page);
		const moves = within(await screen.findByRole('list', { name: 'Derniers mouvements' }));
		expect(moves.getByText('Gants d’examen')).toBeInTheDocument();
		expect(moves.getByText(/par Nisrine/)).toBeInTheDocument();
		const log = within(await screen.findByRole('list', { name: 'Journal des corrections' }));
		expect(log.getByText('30/10/2026 09:10 – Dr Amira a supprimé : Sortie de 2 Composite')).toBeInTheDocument();
		expect(log.getByText('Motif : Doublon')).toBeInTheDocument();
		await fireEvent.click(moves.getByRole('button', { name: 'Supprimer' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Supprimer ce mouvement ?' }));
		await fireEvent.input(dialog.getByLabelText('Motif'), { target: { value: 'Saisi deux fois' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Supprimer' }));
		await vi.waitFor(() => expect(calls()).toContain('DELETE /api/stock/movements/50'));
		expect(sentJson('DELETE /api/stock/movements/50')).toEqual({ reason: 'Saisi deux fois' });
		expect(await screen.findByText('Supprimé. Le stock est à jour.')).toBeInTheDocument();
		expect(fetch).toHaveBeenCalled();
	});

	it('shows the suppliers with call and WhatsApp buttons', async () => {
		stockApi();
		history.replaceState(null, '', '/app/stock?tab=fournisseurs');
		render(Page);
		const list = within(await screen.findByRole('list', { name: 'Fournisseurs' }));
		expect(list.getByText('Livre le mardi')).toBeInTheDocument();
		expect(list.getByRole('link', { name: 'Appeler Dentalia Sfax' })).toHaveAttribute('href', 'tel:+21674000000');
		expect(list.getByRole('link', { name: 'WhatsApp Dentalia Sfax' })).toHaveAttribute('href', 'https://wa.me/21620123456');
	});

	it('shows a product never received in grey, never to order (start list)', async () => {
		const fresh = product({ id: 9, name: 'Pompes à salive', quantity: 0, status: 'unreceived', hasHistory: false, minQuantity: 2 });
		stockApi({}, [gloves, fresh]);
		render(Page);
		const list = within(await screen.findByRole('list', { name: 'Produits en stock' }));
		const row = list.getByText('Pompes à salive').closest('button') as HTMLElement;
		expect(row).toHaveTextContent('Pas encore reçu');
		expect(row).toHaveTextContent('notez sa première réception');
		expect(screen.getByRole('button', { name: 'À commander' })).toBeInTheDocument(); // no count: nothing to order
	});

	it('says when a part cannot load and tries again – never "nothing to order" (review N3)', async () => {
		let fail = true;
		stockApi({ 'GET /api/stock/to-order': () => (fail ? problem(500, 'server_error') : json(200, { count: 0, groups: [] })) });
		history.replaceState(null, '', '/app/stock?tab=commander');
		render(Page);
		const alert = await screen.findByRole('alert');
		expect(alert).toHaveTextContent('La liste à commander n’a pas pu être chargée.');
		expect(screen.queryByText('Rien à commander : tous les produits sont au-dessus de leur seuil.')).not.toBeInTheDocument();
		fail = false;
		await fireEvent.click(within(alert).getByRole('button', { name: 'Réessayer' }));
		expect(await screen.findByText('Rien à commander : tous les produits sont au-dessus de leur seuil.')).toBeInTheDocument();
	});

	it('opens no WhatsApp and no call in a demo practice but shows the order text (review N7)', async () => {
		auth.set('tok', { ...assistant, practice: { ...assistant.practice!, isDemo: true } });
		stockApi({
			'GET /api/stock/to-order': () =>
				json(200, { count: 1, groups: [{ supplier: { id: 7, name: 'Dentalia Sfax', phone: '+21674000000', whatsapp: '+21620123456' }, items: [{ productId: 2, name: 'Carpules d’articaïne', unit: 'carpule', quantity: 40, minQuantity: 50, suggested: 60 }] }] })
		});
		history.replaceState(null, '', '/app/stock?tab=commander');
		render(Page);
		const group = within(await screen.findByRole('region', { name: 'Dentalia Sfax' }));
		expect(group.getByText(/Démo : rien n’est envoyé/)).toBeInTheDocument();
		expect(group.getByText(/– Carpules d’articaïne : 60 carpules/)).toBeInTheDocument();
		expect(document.querySelector('a[href^="https://wa.me"]')).toBeNull();
		expect(document.querySelector('a[href^="tel:"]')).toBeNull();
		await fireEvent.click(screen.getByRole('button', { name: 'Fournisseurs' }));
		expect(await screen.findByText(/numéros fictifs/)).toBeInTheDocument();
		expect(document.querySelector('a[href^="https://wa.me"], a[href^="tel:"]')).toBeNull();
	});

	it('names the delivery day of a receipt and lets the owner correct its line (review N9, H2)', async () => {
		auth.set('tok', owner);
		stockApi({
			'GET /api/stock/movements?limit=100': () => json(200, [receiptMove]),
			[LOG]: () =>
				json(200, [{ id: 3, at: '2026-11-01T09:20:00+01:00', userName: 'Amira', entity: 'stock_receipt_line', entityId: 81, action: 'update',
					before: { product: 'Gants d’examen', unit: 'boite', receivedOn: '2026-10-28', unitPriceMillimes: 13500000 }, after: { unitPriceMillimes: 13500 }, reason: 'Virgule oubliée' }]),
			'PATCH /api/stock/receipts/8/lines/81': () => json(200, { id: 8 })
		});
		history.replaceState(null, '', '/app/stock?tab=mouvements');
		render(Page);
		const moves = within(await screen.findByRole('list', { name: 'Derniers mouvements' }));
		expect(moves.getByText(/Réception – 28\/10\/2026/)).toBeInTheDocument();
		const log = within(await screen.findByRole('list', { name: 'Journal des corrections' }));
		expect(log.getByText('01/11/2026 09:20 – Amira a corrigé la réception du 28/10/2026 : Gants d’examen')).toBeInTheDocument();
		expect(log.getByText('Prix unitaire : 13 500 DT → 13,500 DT')).toBeInTheDocument();
		await fireEvent.click(moves.getByRole('button', { name: 'Supprimer la réception' }));
		expect(screen.getByRole('dialog', { name: 'Supprimer toute la réception du 28/10/2026 ?' })).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Annuler' }));
		await fireEvent.click(moves.getByRole('button', { name: 'Corriger la réception : Gants d’examen' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Corriger la réception du 28/10/2026' }));
		const price = dialog.getByLabelText('Prix unitaire (DT)');
		expect(price).toHaveValue('13500');
		expect(dialog.getByText('Soit 13 500 DT par boîte')).toBeInTheDocument();
		await fireEvent.input(price, { target: { value: '13,5' } });
		expect(dialog.getByText('Soit 13,500 DT par boîte')).toBeInTheDocument();
		await fireEvent.input(dialog.getByLabelText('Motif'), { target: { value: 'Virgule oubliée' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer la correction' }));
		await vi.waitFor(() => expect(calls()).toContain('PATCH /api/stock/receipts/8/lines/81'));
		expect(sentJson('PATCH /api/stock/receipts/8/lines/81')).toEqual({ quantity: 10, unitPriceMillimes: 13500, reason: 'Virgule oubliée' });
		expect(await screen.findByText('Réception corrigée : le stock et les coûts sont à jour.')).toBeInTheDocument();
		expect(labelInNameProblems()).toEqual([]);
	});

	it('asks only for the stock entries of the change log and words them (review M3)', async () => {
		auth.set('tok', owner);
		stockApi({
			'GET /api/stock/movements?limit=100': () => json(200, []),
			[LOG]: () =>
				json(200, [{ id: 4, at: '2026-10-30T11:00:00+01:00', userName: 'Salma', entity: 'stock_product', entityId: 1, action: 'update',
					before: { product: 'Gants d’examen', minQuantity: 4, category: 'hygiene' }, after: { minQuantity: 6, category: 'bureau' }, reason: '' }])
		});
		history.replaceState(null, '', '/app/stock?tab=mouvements');
		render(Page);
		const log = within(await screen.findByRole('list', { name: 'Journal des corrections' }));
		expect(log.getByText('30/10/2026 11:00 – Salma a modifié le produit « Gants d’examen »')).toBeInTheDocument();
		expect(log.getByText('Seuil de commande : 4 → 6')).toBeInTheDocument();
		expect(log.getByText('Catégorie : Hygiène → Bureau')).toBeInTheDocument();
		expect(calls()).toContain(LOG);
		expect(document.body.textContent).not.toContain('de 0');
	});

	it('refuses half a box instead of rounding it (review N2)', async () => {
		stockApi({ 'GET /api/services': () => json(200, []) });
		render(Page);
		await screen.findByRole('list', { name: 'Produits en stock' });
		await fireEvent.click(screen.getByRole('button', { name: 'Sortie' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Sortie de stock' }));
		await fireEvent.click(dialog.getByRole('button', { name: /Gants d’examen/ }));
		await fireEvent.input(dialog.getByLabelText('Quantité'), { target: { value: '0.5' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer la sortie' }));
		expect(await dialog.findByRole('alert')).toHaveTextContent('Nombre entier seulement');
		expect(calls()).not.toContain('POST /api/stock/movements');
	});

	it('counts the shelves in whole numbers only (review N2)', async () => {
		stockApi();
		history.replaceState(null, '', '/app/stock?tab=inventaire');
		render(Page);
		const list = within(await screen.findByRole('list', { name: 'Inventaire' }));
		await fireEvent.input(list.getByLabelText(/Gants d’examen/), { target: { value: '2.5' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer l’inventaire' }));
		expect(await screen.findByText('Nombre entier seulement : pour une partie, comptez en pièces ou en ml.')).toBeInTheDocument();
		expect(calls()).not.toContain('POST /api/stock/inventory');
	});

	it('shows the act of a movement in Arabic (review N6)', async () => {
		i18n.setLocale('ar');
		const soin: Movement = { ...receiptMove, id: 61, kind: 'use', quantity: -1, receiptId: null, receiptLineId: null, receivedOn: null, serviceId: 11, serviceName: 'Soin carie', serviceNameAr: 'علاج تسوس' };
		stockApi({ 'GET /api/stock/movements?limit=100': () => json(200, [soin]) });
		history.replaceState(null, '', '/app/stock?tab=mouvements');
		render(Page);
		const moves = within(await screen.findByRole('list', { name: 'آخر الحركات' }));
		expect(moves.getByText('علاج تسوس')).toBeInTheDocument();
		expect(moves.queryByText('Soin carie')).not.toBeInTheDocument();
	});
});
