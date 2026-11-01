/** API shapes of patients and money (design sections 4, 5, 15). */
import type { PaymentMethod } from '../agenda/payments';

/** `GET /api/patients` items. */
export interface PatientSummary {
	id: number;
	firstName: string;
	lastName: string;
	phone: string;
	birthYear: number | null;
	/** Optional full date (`YYYY-MM-DD`); when set, `birthYear` is its year. */
	birthDate?: string | null;
	lang: string;
	reminderConsent: boolean;
	noShows: number;
	attended: number;
	dueMillimes: number;
	nextAppointmentAt: string | null;
	hasAlerts?: boolean;
}

export interface PatientPage {
	items: PatientSummary[];
	total: number;
}

/** `GET /api/patients/{id}`. */
export interface Patient extends PatientSummary {
	notes: string;
	alerts?: string;
	createdAt: string;
	cancelled: number;
	totalMillimes: number;
	paidMillimes: number;
	samePhone?: { id: number; firstName: string; lastName: string }[];
}

/** Body of `POST /api/patients` and `PATCH /api/patients/{id}`. */
export interface PatientInput {
	firstName: string;
	lastName: string;
	phone: string;
	birthYear?: number | null;
	birthDate?: string | null;
	lang: string;
	reminderConsent: boolean;
	notes?: string;
	alerts?: string;
}

export interface Treatment {
	id: number;
	label: string;
	tooth: string | null;
	priceMillimes: number;
	performedOn: string | null;
	appointmentId: number | null;
	createdAt: string;
}

export interface Payment {
	id: number;
	patientId: number;
	patientName: string;
	amountMillimes: number;
	method: PaymentMethod | string;
	paidAt: string;
	appointmentId: number | null;
	isDeposit: boolean;
	note: string;
	receivedByName: string | null;
}

/** `GET /api/patients/{id}/ledger`. */
export interface Ledger {
	treatments: Treatment[];
	payments: Payment[];
	totalMillimes: number;
	paidMillimes: number;
	dueMillimes: number;
}

/** `GET /api/payments/{id}` – a payment with the practice for the receipt. */
export interface Receipt extends Payment {
	practice: { name: string; nameAr?: string; address: string; city: string; phone: string; taxId?: string };
}

/** Cash closing of a day (section 16.3); names are display names. */
export interface CashClosing {
	expectedCashMillimes: number;
	countedCashMillimes: number;
	differenceMillimes: number;
	note?: string;
	closedBy: string | null;
	closedAt: string;
	verifiedBy?: string | null;
	verifiedAt?: string | null;
	/** Payments of the day changed after the closing: count again. */
	stale?: boolean;
}

/** `GET /api/cash?day=`. */
export interface CashDay {
	day: string;
	totalMillimes: number;
	byMethod: Record<string, number>;
	payments: Payment[];
	closing?: CashClosing | null;
}

/** `GET /api/balances` items. */
export interface Balance {
	patientId: number;
	name: string;
	phone: string;
	dueMillimes: number;
	lastPaymentAt: string | null;
}

/** `GET /api/balances/summary` – every positive balance of the practice (code review M7). */
export interface BalancesSummary {
	totalMillimes: number;
	patients: number;
}
