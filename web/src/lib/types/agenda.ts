/**
 * API shapes of the agenda, appointments and the dashboard (design sections 5, 11, 12, 15).
 * Fields marked optional are tolerated as missing so the page keeps working with an older backend.
 */
import type { AppointmentStatus } from '../status';

/** ISO weekday "1" (Monday) … "7" (Sunday) → opening windows `[["08:00","12:30"], …]`. */
export type WeeklyHours = Record<string, [string, string][]>;

/** `GET /api/practice` (the parts the agenda uses). */
export interface PracticeSettings {
	id: number;
	name: string;
	nameAr?: string;
	address?: string;
	city?: string;
	phone?: string;
	specialty?: string;
	weeklyHours?: WeeklyHours;
	slotMinutes: number;
	defaultDurationMin: number;
	displayToken?: string;
	isDemo?: boolean;
	slug?: string;
}

/** `GET /api/practitioners` – the people who treat (not user accounts, section 11.2). */
export interface Practitioner {
	id: number;
	name: string;
	title?: string;
	color?: string | null;
	specialty?: string | null;
	active?: boolean;
	sort?: number;
}

/** `GET /api/services` – catalog of acts / consultations. */
export interface Service {
	id: number;
	nameFr: string;
	nameAr: string;
	durationMin: number;
	priceMillimes: number | null;
	onlineBookable?: boolean;
	color?: string | null;
	active?: boolean;
	sort?: number;
}

/** `GET /api/closures` – days without appointments. */
export interface Closure {
	id: number;
	startsOn: string;
	endsOn: string;
	label: string;
}

export interface AppointmentPatient {
	id: number;
	firstName: string;
	lastName: string;
	phone: string;
	noShows: number;
	alerts?: string;
	lang?: string;
}

export interface Appointment {
	id: number;
	patient: AppointmentPatient;
	practitionerId: number | null;
	practitionerName: string | null;
	serviceId?: number | null;
	serviceName?: string | null;
	startsAt: string;
	endsAt?: string;
	durationMin: number;
	reason: string;
	status: AppointmentStatus;
	source?: 'staff' | 'online' | string;
	notes: string;
	patientNote?: string;
	depositRequiredMillimes: number;
	depositPaidMillimes: number;
	reminderSentAt: string | null;
	createdAt?: string;
	seriesId?: string | null;
}

/** Body of a create/update: `POST /api/appointments`, `PATCH /api/appointments/{id}`. */
export interface AppointmentInput {
	patientId: number;
	startsAt: string;
	durationMin: number;
	reason: string;
	serviceId?: number | null;
	practitionerId?: number | null;
	notes?: string;
	depositRequiredMillimes?: number;
}

/** 201/200 of create/update; older contract: `{appointment, conflicts}`, tolerated: the bare appointment. */
export type AppointmentSaved = { appointment: Appointment; conflicts?: unknown[] } | Appointment;

export interface ConflictItem {
	id: number;
	startsAt: string;
	endsAt?: string;
	patientName: string;
}

/** 409 problem body when a slot is taken (sections 11.1 and 15). */
export interface ConflictProblem {
	title?: string;
	detail?: string;
	code?: string;
	conflicts?: ConflictItem[];
	suggestions?: string[];
}

export interface SeriesRule {
	weekdays: number[];
	count: number;
}

export interface SeriesOccurrence {
	startsAt: string;
	endsAt: string;
	conflict: { id: number; startsAt: string; patientName: string } | null;
	closed: boolean;
}

export interface SeriesCreated {
	seriesId: string;
	created: Appointment[];
	skipped: { startsAt: string; reason: 'conflict' | 'closed' }[];
}

/** `GET /api/badges` (polled every 60 s). */
export interface Badges {
	onlineRequests: number;
	overdue: number;
}

/** `GET /api/dashboard`. */
export interface Dashboard {
	today: string;
	appointments: { total: number; byStatus: Partial<Record<AppointmentStatus, number>> };
	upcoming: Appointment[];
	queue: { waiting: number; called: number };
	cashTodayMillimes: number;
	remindersPending: number;
	dueTotalMillimes: number;
	patientsCount: number;
	/** Owner only (section 16.3, field name is a contract addition): closed cash days not verified yet. */
	unverifiedCashDays?: { day: string; differenceMillimes: number }[];
}

export type OnboardingKey = 'hours' | 'services' | 'practitioners' | 'team' | 'booking' | 'import' | 'install' | 'poster';

/** `GET /api/onboarding`. */
export interface Onboarding {
	steps: { key: OnboardingKey | string; done: boolean }[];
	dismissed: boolean;
}
