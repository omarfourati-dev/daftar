/**
 * Helpers of the stock pages (spec stock-hygiène 4): quantities with their unit, categories in the order of the
 * specialty, product search without accents, the "Sortie" order (last used first), the WhatsApp order to a supplier,
 * whole quantities only (review N2), the unusual-price check of a delivery (review H2), error texts.
 */
import { ApiError, apiErrorMessage } from './api';
import { serviceLabel } from './agenda/format';
import { whatsappUrl } from './agenda/links';
import { formatDay, t, translate, type MessageKey } from './i18n.svelte';
import type { Movement, OrderGroup, Product, StockCategory, StockUnit } from './types/stock';

export const CATEGORIES: readonly StockCategory[] = [
	'hygiene',
	'anesthesie',
	'restauration',
	'endodontie',
	'prothese',
	'chirurgie',
	'prelevements',
	'injection',
	'pansements',
	'bureau',
	'autre'
];
export const UNITS: readonly StockUnit[] = ['piece', 'boite', 'flacon', 'carpule', 'paquet', 'sachet', 'tube', 'rouleau', 'paire', 'ml', 'g'];

/** The categories a specialty uses most, first (the others follow in the usual order). */
const FIRST: Record<string, StockCategory[]> = {
	dentiste: ['hygiene', 'anesthesie', 'restauration', 'endodontie', 'prothese', 'chirurgie'],
	generaliste: ['hygiene', 'prelevements', 'injection', 'pansements'],
	pediatre: ['hygiene', 'injection', 'pansements', 'prelevements'],
	gynecologue: ['hygiene', 'prelevements', 'injection'],
	dermatologue: ['hygiene', 'chirurgie', 'pansements'],
	kinesitherapeute: ['hygiene', 'pansements']
};

export function categoriesFor(specialty: string | undefined | null): StockCategory[] {
	const first = FIRST[specialty ?? ''] ?? ['hygiene'];
	return [...first, ...CATEGORIES.filter((c) => !first.includes(c))];
}

export function categoryLabel(category: StockCategory): string {
	return translate(`stock.categories.${category}`) ?? category;
}

/** "boîte" or "boîtes" for this quantity (Arabic keeps one form). */
export function unitWord(quantity: number, unit: StockUnit): string {
	const key = Math.abs(quantity) > 1 ? `stock.unitsPlural.${unit}` : `stock.units.${unit}`;
	return translate(key) ?? unit;
}

/** "1 boîte", "12 boîtes". */
export function quantityText(quantity: number, unit: StockUnit): string {
	return `${quantity} ${unitWord(quantity, unit)}`;
}

export function unitLabel(unit: StockUnit): string {
	return translate(`stock.units.${unit}`) ?? unit;
}

const fold = (text: string) =>
	text
		.normalize('NFD')
		.replace(/[̀-ͯ]/g, '')
		.replace(/[’']/g, "'")
		.toLowerCase();

/** Search in the name (and category) of a product without case or accents. */
export function matches(product: Pick<Product, 'name' | 'category'>, query: string): boolean {
	const q = fold(query.trim());
	if (!q) return true;
	return fold(product.name).includes(q) || fold(categoryLabel(product.category)).includes(q);
}

/** Active products for a "Sortie": the ones used last first, then by name. */
export function sortForUse(products: Product[]): Product[] {
	return products
		.filter((p) => p.active)
		.sort((a, b) => {
			if (a.lastUsedAt && b.lastUsedAt) return b.lastUsedAt.localeCompare(a.lastUsedAt);
			if (a.lastUsedAt || b.lastUsedAt) return a.lastUsedAt ? -1 : 1;
			return a.name.localeCompare(b.name);
		});
}

/** The WhatsApp text of an order, in the language of the screen (the assistant writes it). */
export function orderMessage(group: OrderGroup, practiceName: string): string {
	const lines = group.items.map((item) => t('stock.toOrder.line', { product: item.name, quantity: quantityText(item.suggested, item.unit) }));
	return [t('stock.toOrder.greeting', { supplier: group.supplier?.name ?? '', practice: practiceName }), ...lines, t('stock.toOrder.closing')].join('\n');
}

/** `wa.me` link to the supplier (WhatsApp number, else phone), null without a number. */
export function orderUrl(group: OrderGroup, practiceName: string): string | null {
	const number = group.supplier?.whatsapp ?? group.supplier?.phone;
	return number ? whatsappUrl(number, orderMessage(group, practiceName)) : null;
}

export function inventoryReason(day: string): string {
	return t('stock.inventory.defaultReason', { date: formatDay(day) });
}

/** Error text for the stock endpoints: their own codes first (`stock.errors.<code>`), else the general one. */
export function stockError(err: unknown): string {
	if (err instanceof ApiError && err.code) {
		const own = translate(`stock.errors.${err.code}`);
		if (own) return own;
	}
	return apiErrorMessage(err);
}

export const STATUS_TONE: Record<string, string> = {
	ok: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
	low: 'bg-amber-50 text-amber-900 ring-amber-300',
	empty: 'bg-rose-50 text-rose-800 ring-rose-200',
	unreceived: 'bg-slate-100 text-slate-700 ring-slate-300'
};

/** The traffic-light bar of a product row. */
export const STATUS_BAR: Record<string, string> = {
	ok: 'bg-emerald-500',
	low: 'bg-amber-500',
	empty: 'bg-rose-500',
	unreceived: 'bg-slate-300'
};

/** "À commander" as the server counts it: active, with a threshold reached – and delivered, used or counted once. */
export function isToOrder(p: Pick<Product, 'active' | 'minQuantity' | 'quantity' | 'status'>): boolean {
	return p.active && p.status !== 'unreceived' && p.minQuantity > 0 && p.quantity <= p.minQuantity;
}

/** A whole quantity ≥ `min` from what was typed, null otherwise – never rounded in silence (review N2). */
export function wholeQuantity(value: unknown, min = 1): number | null {
	const text = String(value ?? '').trim().replace(',', '.');
	if (!/^\d+$/.test(text)) return null;
	const n = Number(text);
	return n >= min ? n : null;
}

/** More than this per unit asks before saving (13 500 DT typed for 13,500 DT). */
export const UNUSUAL_PRICE_MILLIMES = 500_000;

/** A unit price far from the current average (more than 3 ×, or less than a third) or above 500 DT (review H2). */
export function unusualPrice(price: number | null, average: number | null): boolean {
	if (price === null || Number.isNaN(price)) return false;
	if (price > UNUSUAL_PRICE_MILLIMES) return true;
	return average !== null && average > 0 && (price > 3 * average || price * 3 < average);
}

/** The act of a movement in the screen's language. */
export function movementService(m: Pick<Movement, 'serviceName' | 'serviceNameAr'>): string {
	return m.serviceName ? serviceLabel({ nameFr: m.serviceName, nameAr: m.serviceNameAr ?? '' }) : '';
}

export const KIND_KEY: Record<string, MessageKey> = {
	receipt: 'stock.movements.kinds.receipt',
	use: 'stock.movements.kinds.use',
	adjust: 'stock.movements.kinds.adjust',
	waste: 'stock.movements.kinds.waste'
};
