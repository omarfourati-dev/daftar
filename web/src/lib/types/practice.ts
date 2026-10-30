/**
 * The practice as its owner sees and edits it (`GET/PATCH /api/practice`, sections 5, 11.2, 13) and the lists the
 * owner keeps in /app/reglages: practitioners, services, closures, team, invitations.
 */
import type { WeeklyHours } from '../hours';
import type { OnlineBooking } from '../online-booking';
import type { Specialty } from '../types';

/** Contact and address fields shared by the admin wizard and the owner settings. */
export interface PracticeProfileFields {
	name: string;
	nameAr: string;
	specialty: Specialty | string;
	contactName: string;
	phone: string;
	whatsapp: string | null;
	email: string | null;
	address: string;
	postalCode: string;
	city: string;
	governorate: string | null;
	mapsUrl: string;
	descriptionFr: string;
	descriptionAr: string;
	taxId: string;
}

/** `GET /api/practice` – everything except the admin fields (slug read-only, no status/plan/notes). */
export interface Practice extends PracticeProfileFields {
	id: number;
	slug: string;
	brandColor: string;
	weeklyHours: WeeklyHours;
	slotMinutes: number;
	defaultDurationMin: number;
	reminderTemplateFr: string;
	reminderTemplateAr: string;
	displayToken: string;
	isDemo: boolean;
	/** nested (preferred); flat columns are read too – see `readOnlineBooking` */
	onlineBooking?: OnlineBooking;
	[key: string]: unknown;
}

/** `GET /api/practitioners` – people who treat patients (not accounts, section 11.2). */
export interface Practitioner {
	id: number;
	name: string;
	title: string;
	specialty: Specialty | string | null;
	color: string;
	/** an account of the practice this practitioner works with (optional) */
	userId?: number | null;
	onlineBookable: boolean;
	active: boolean;
	sort: number;
}

export type PractitionerInput = Omit<Practitioner, 'id' | 'sort'>;

/** `GET /api/services` – the practice's catalog of acts / consultations. */
export interface Service {
	id: number;
	nameFr: string;
	nameAr: string;
	durationMin: number;
	priceMillimes: number | null;
	onlineBookable: boolean;
	color: string | null;
	active: boolean;
	sort: number;
}

export type ServiceInput = Omit<Service, 'id' | 'sort' | 'color'>;

/** `GET /api/closures` – holidays, days off: no appointments, no online bookings. */
export interface Closure {
	id: number;
	startsOn: string;
	endsOn: string;
	label: string;
}

/** `GET /api/staff` */
export interface StaffMember {
	id: number;
	name: string;
	email: string;
	role: 'owner' | 'dentist' | 'assistant' | string;
	createdAt: string;
}

/** `GET /api/staff/invitations` */
export interface StaffInvitation {
	id: number;
	role: 'dentist' | 'assistant' | string;
	createdAt: string;
	expiresAt: string;
}

/** A one-time link: invitation (`POST /api/staff/invitations`) or password reset (`…/reset-link`). */
export interface OneTimeLink {
	id?: number;
	token: string;
	expiresAt: string;
}
