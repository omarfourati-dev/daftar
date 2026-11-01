import { beforeEach, describe, expect, it } from 'vitest';
import { i18n } from './i18n.svelte';
import { ApiError } from './api';
import { categoriesFor, inventoryReason, matches, orderMessage, orderUrl, quantityText, sortForUse, stockError } from './stock';
import type { OrderGroup, Product } from './types/stock';

function product(overrides: Partial<Product> = {}): Product {
	return {
		id: 1,
		name: 'Gants d’examen',
		category: 'hygiene',
		unit: 'boite',
		supplierId: null,
		supplierName: null,
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

const group: OrderGroup = {
	supplier: { id: 3, name: 'Dentalia Sfax', phone: '+21674000000', whatsapp: '+21620123456' },
	items: [
		{ productId: 1, name: 'Gants d’examen', unit: 'boite', quantity: 3, minQuantity: 4, suggested: 5 },
		{ productId: 2, name: 'Carpules d’articaïne', unit: 'carpule', quantity: 1, minQuantity: 50, suggested: 99 }
	]
};

describe('stock helpers', () => {
	beforeEach(() => i18n.setLocale('fr'));

	it('names quantities with their unit, singular and plural', () => {
		expect(quantityText(1, 'boite')).toBe('1 boîte');
		expect(quantityText(12, 'boite')).toBe('12 boîtes');
		expect(quantityText(0, 'piece')).toBe('0 pièce');
		expect(quantityText(-2, 'carpule')).toBe('-2 carpules');
		expect(quantityText(250, 'ml')).toBe('250 ml');
		i18n.setLocale('ar');
		expect(quantityText(12, 'boite')).toBe('12 علبة');
	});

	it('puts the categories of the specialty first', () => {
		expect(categoriesFor('dentiste').slice(0, 4)).toEqual(['hygiene', 'anesthesie', 'restauration', 'endodontie']);
		expect(categoriesFor('generaliste').slice(0, 3)).toEqual(['hygiene', 'prelevements', 'injection']);
		for (const s of ['dentiste', 'generaliste', 'psychologue', undefined]) expect(new Set(categoriesFor(s)).size).toBe(11);
	});

	it('finds products without caring about case or accents', () => {
		expect(matches(product(), 'gants')).toBe(true);
		expect(matches(product({ name: 'Carpules d’articaïne' }), 'ARTICAINE')).toBe(true);
		expect(matches(product(), 'compo')).toBe(false);
		expect(matches(product(), '  ')).toBe(true);
	});

	it('offers the last used products first for the "Sortie"', () => {
		const list = sortForUse([
			product({ id: 1, name: 'Bavoirs' }),
			product({ id: 2, name: 'Composite', lastUsedAt: '2026-10-29T10:00:00+01:00' }),
			product({ id: 3, name: 'Carpules', lastUsedAt: '2026-10-30T09:00:00+01:00' }),
			product({ id: 4, name: 'Ancien', active: false }),
			product({ id: 5, name: 'Aiguilles' })
		]);
		expect(list.map((p) => p.id)).toEqual([3, 2, 5, 1]);
	});

	it('writes the order to the supplier, in the screen’s language', () => {
		expect(orderMessage(group, 'Cabinet Dr Fadoua')).toBe(
			'Bonjour Dentalia Sfax, ici Cabinet Dr Fadoua. Nous souhaitons commander :\n– Gants d’examen : 5 boîtes\n– Carpules d’articaïne : 99 carpules\nMerci de nous confirmer la livraison.'
		);
		expect(orderUrl(group, 'Cabinet')?.startsWith('https://wa.me/21620123456?text=Bonjour')).toBe(true);
		expect(orderUrl({ ...group, supplier: { ...group.supplier!, whatsapp: null } }, 'Cabinet')?.startsWith('https://wa.me/21674000000')).toBe(true);
		expect(orderUrl({ ...group, supplier: { ...group.supplier!, whatsapp: null, phone: null } }, 'Cabinet')).toBeNull();
		expect(orderUrl({ ...group, supplier: null }, 'Cabinet')).toBeNull();
		i18n.setLocale('ar');
		expect(orderMessage(group, 'عيادة')).toContain('نرغب في طلب');
	});

	it('proposes the reason of an inventory and translates the stock errors', () => {
		expect(inventoryReason('2026-10-31')).toBe('Inventaire du 31/10/2026');
		expect(stockError(new ApiError(409, 'x', 'product_exists'))).toBe('Un produit porte déjà ce nom. Choisissez-le dans la liste ou changez le nom.');
		expect(stockError(new ApiError(0, 'x', 'network'))).toBe('Pas de connexion au serveur. Vérifiez votre connexion internet.');
	});
});
