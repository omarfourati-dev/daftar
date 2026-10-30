/** Subscriptions (section 11.4): plans, invoices, the owner's billing page and the admin overview. */
import type { PracticeStatus } from '../types';

export type InvoiceStatus = 'open' | 'paid' | 'void';
export type InvoiceMethod = 'flouci' | 'virement' | 'especes' | 'autre';
export const INVOICE_METHODS: readonly InvoiceMethod[] = ['virement', 'especes', 'flouci', 'autre'];
export const PLAN_CODES = ['pilot', 'cabinet_mensuel', 'cabinet_annuel'] as const;

export interface Plan {
	code: string;
	nameFr: string;
	nameAr: string;
	priceMillimes: number;
	periodMonths: number;
	active?: boolean;
}

export interface Invoice {
	id: number;
	number: string;
	planCode: string;
	periodStart: string;
	periodEnd: string;
	amountMillimes: number;
	status: InvoiceStatus | string;
	dueOn: string;
	paidAt: string | null;
	method: InvoiceMethod | string | null;
	createdAt?: string;
}

/** `GET /api/billing` (owner). `plan` may come as the plan object or just its code. */
export interface Billing {
	plan: Plan | string | null;
	status: PracticeStatus | string;
	paidUntil: string | null;
	plans: Plan[];
	invoices: Invoice[];
	onlinePaymentAvailable: boolean;
}

/** One practice of `GET /api/admin/billing`; `invoices` (newest first) is a contract addition of this web part. */
export interface AdminBillingRow {
	practiceId: number;
	name: string;
	slug?: string;
	planCode: string;
	status: PracticeStatus | string;
	paidUntil: string | null;
	openInvoices?: number;
	openMillimes: number;
	invoices?: Invoice[];
}
