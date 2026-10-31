import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { clock } from '#lib/clock';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, labelInNameProblems, mockApi, noContent, sentJson, type Handler } from '#lib/test-utils';
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
			appointmentId: null, patientName: null, receiptId: null, reason: '', unitCostMillimes: 12000, createdBy: 'Nisrine', createdAt: '2026-10-30T09:00:00+01:00'
		};
		const fetch = stockApi({
			'GET /api/stock/movements?limit=100': () => json(200, [use]),
			'GET /api/audit-log?limit=20': () =>
				json(200, [{ id: 1, at: '2026-10-30T09:10:00+01:00', userName: 'Dr Amira', entity: 'stock_movement', action: 'delete', before: { kind: 'use', quantity: -2, product: 'Composite' }, reason: 'Doublon' }]),
			'DELETE /api/stock/movements/50': () => noContent()
		});
		history.replaceState(null, '', '/app/stock?tab=mouvements');
		render(Page);
		const moves = within(await screen.findByRole('list', { name: 'Derniers mouvements' }));
		expect(moves.getByText('Gants d’examen')).toBeInTheDocument();
		expect(moves.getByText(/par Nisrine/)).toBeInTheDocument();
		expect(await screen.findByText(/Dr Amira a supprimé : Sortie de 2 Composite\. Motif : Doublon/)).toBeInTheDocument();
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
});
