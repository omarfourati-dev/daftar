/** Shapes of the admin API (sections 5, 11.2, 11.4, 15): practices, wizard input, pilot requests, feedback. */
import type { WeeklyHours } from '../hours';
import type { OnlineBooking } from '../online-booking';
import type { PracticeStatus, Specialty } from '../types';
import type { PracticeProfileFields } from './practice';

/** One row of `GET /api/admin/practices` (status/plan/paidUntil/slug: contract addition, shown as "—" if absent). */
export interface AdminPracticeRow {
	id: number;
	name: string;
	city: string;
	isDemo: boolean;
	createdAt: string;
	users: number;
	patients: number;
	appointments: number;
	/** appointments of the last 7 days */
	appointmentsWeek?: number;
	lastActivityAt: string | null;
	slug?: string;
	governorate?: string | null;
	specialty?: Specialty | string;
	status?: PracticeStatus | string;
	planCode?: string;
	paidUntil?: string | null;
}

export interface WizardPractitioner {
	title: string;
	name: string;
	specialty?: Specialty | string | null;
}

export interface WizardService {
	nameFr: string;
	nameAr: string;
	durationMin: number;
	priceMillimes: number | null;
	onlineBookable: boolean;
}

/** `POST /api/admin/practices` (section 11.2; plan/status/paidUntil from 11.4). */
export interface AdminPracticeInput extends PracticeProfileFields {
	slug: string;
	status: PracticeStatus | string;
	planCode: string;
	paidUntil: string | null;
	/** same date, name of section 11.2 (the backend ignores unknown fields) */
	pilotUntil: string | null;
	adminNotes: string;
	weeklyHours: WeeklyHours;
	practitioners: WizardPractitioner[];
	services: WizardService[];
	onlineBooking: OnlineBooking;
}

/** `GET /api/admin/practices/{id}` – everything. */
export interface AdminPractice extends PracticeProfileFields {
	id: number;
	slug: string;
	brandColor: string;
	status: PracticeStatus | string;
	planCode: string;
	paidUntil: string | null;
	adminNotes: string;
	weeklyHours: WeeklyHours;
	isDemo: boolean;
	createdAt: string;
	onlineBooking?: OnlineBooking;
	/** the owner account, null until the invitation is accepted */
	owner?: { id: number; name: string; email: string } | null;
	pilotUntil?: string | null;
	bookingUrl?: string;
	[key: string]: unknown;
}

/** `POST /api/admin/practices` → 201 */
export interface AdminPracticeCreated {
	practice: { id: number; slug: string; name: string; [key: string]: unknown };
	invitation: { token: string; expiresAt: string };
}

/** `GET /api/admin/slug-available?slug=` */
export interface SlugCheck {
	available: boolean;
	reason?: 'invalid' | 'reserved' | 'taken' | string;
}

/** `GET /api/admin/pilot-requests` */
export interface PilotRequest {
	id: number;
	name: string;
	practice: string;
	city: string;
	phone: string;
	email: string | null;
	message: string;
	lang: string;
	createdAt: string;
}

/** `GET /api/admin/feedback` (practiceName/userName: contract addition, optional). */
export interface FeedbackItem {
	id: number;
	practiceId: number | null;
	practiceName?: string | null;
	userName?: string | null;
	message: string;
	page: string;
	createdAt: string;
}
