/** API shapes of the stock module (spec stock-hygiène 4; backend daftar/stock*.py). Money in millimes. */

export type StockCategory =
	| 'hygiene'
	| 'anesthesie'
	| 'restauration'
	| 'endodontie'
	| 'prothese'
	| 'chirurgie'
	| 'prelevements'
	| 'injection'
	| 'pansements'
	| 'bureau'
	| 'autre';
export type StockUnit = 'piece' | 'boite' | 'flacon' | 'carpule' | 'paquet' | 'sachet' | 'tube' | 'rouleau' | 'paire' | 'ml' | 'g';
/** `unreceived`: nothing delivered, used or counted yet (grey, never "à commander"). */
export type StockStatus = 'ok' | 'low' | 'empty' | 'unreceived';
export type ExpiryState = 'expired' | 'soon';
export type MovementKind = 'receipt' | 'use' | 'adjust' | 'waste';

/** `GET /api/stock/products` – a product with its stock (sum of its movements). */
export interface Product {
	id: number;
	name: string;
	category: StockCategory;
	unit: StockUnit;
	supplierId: number | null;
	supplierName: string | null;
	minQuantity: number;
	note: string;
	ean: string | null;
	active: boolean;
	quantity: number;
	status: StockStatus;
	/** Something was delivered, used or counted: the unit is locked (409 unit_in_use). */
	hasHistory: boolean;
	expiresOn: string | null;
	expiry: ExpiryState | null;
	/** Moving average of what is in stock; null for the dentist and without any priced delivery. */
	averageCostMillimes: number | null;
	lastUsedAt: string | null;
}

export interface ProductInput {
	name: string;
	category: StockCategory;
	unit: StockUnit;
	supplierId: number | null;
	minQuantity: number;
	note: string;
}

export interface Supplier {
	id: number;
	name: string;
	phone: string | null;
	whatsapp: string | null;
	note: string;
	active: boolean;
	products: number;
}

export interface ReceiptLine {
	id: number;
	productId: number;
	productName: string;
	unit: StockUnit;
	quantity: number;
	unitPriceMillimes: number | null;
	lot: string;
	expiresOn: string | null;
}

export interface Receipt {
	id: number;
	receivedOn: string;
	supplierId: number | null;
	supplierName: string | null;
	reference: string;
	note: string;
	createdBy: string | null;
	createdAt: string;
	lines: ReceiptLine[];
	totalMillimes: number;
}

export interface Movement {
	id: number;
	productId: number;
	productName: string;
	unit: StockUnit;
	kind: MovementKind;
	quantity: number;
	serviceId: number | null;
	serviceName: string | null;
	serviceNameAr: string | null;
	appointmentId: number | null;
	patientName: string | null;
	receiptId: number | null;
	receiptLineId: number | null;
	/** Delivery day of a receipt (may be earlier than `createdAt`). */
	receivedOn: string | null;
	reason: string;
	unitCostMillimes: number | null;
	createdBy: string | null;
	createdAt: string;
}

/** 201 of `POST /api/stock/movements`. */
export interface MovementResult {
	movement: Movement;
	product: Product;
}

export interface OrderItem {
	productId: number;
	name: string;
	unit: StockUnit;
	quantity: number;
	minQuantity: number;
	suggested: number;
}

export interface OrderGroup {
	supplier: { id: number; name: string; phone: string | null; whatsapp: string | null } | null;
	items: OrderItem[];
}

export interface ToOrder {
	count: number;
	groups: OrderGroup[];
}

export interface UsageItem {
	productId: number;
	name: string;
	unit: StockUnit;
	quantity: number;
	costMillimes: number;
}

export interface StockStats {
	month: string;
	spendingMillimes: number;
	previousSpendingMillimes: number;
	unpricedLines: number;
	/** Uses of the month without any known price (cost 0). */
	unpricedUses: number;
	bySupplier: { name: string | null; amountMillimes: number }[];
	byCategory: { category: StockCategory; amountMillimes: number }[];
	usageMillimes: number;
	wasteMillimes: number;
	byService: {
		serviceId: number | null;
		name: string | null;
		nameAr: string | null;
		treatments: number;
		materialCostMillimes: number;
		perTreatmentMillimes: number | null;
		items: UsageItem[];
	}[];
	topMaterials: UsageItem[];
}
