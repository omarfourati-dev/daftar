/**
 * Checks and conversions of the practice forms (admin wizard, admin edit page, owner settings). A problem is a
 * text key with parameters so the page shows it at the field in the current language.
 */
import type { MessageKey, Params } from './i18n.svelte';
import type { OnlineBooking } from './online-booking';
import { parseDinars, dinarsText } from './money-input';
import { looksLikePhone } from './phone-check';
import type { CatalogService } from './catalog';
import type { PracticeProfileFields } from './types/practice';
import type { Specialty } from './types';

export interface Problem {
	key: MessageKey;
	params?: Params;
}
export type Problems = Record<string, Problem>;
export type ProfileGroup = 'identity' | 'address' | 'presentation';

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const REQUIRED: Problem = { key: 'kit.fieldRequired' };

export function emptyProfile(specialty: Specialty | string = 'generaliste'): PracticeProfileFields {
	return {
		name: '',
		nameAr: '',
		specialty,
		contactName: '',
		phone: '',
		whatsapp: '',
		email: '',
		address: '',
		postalCode: '',
		city: '',
		governorate: '',
		mapsUrl: '',
		descriptionFr: '',
		descriptionAr: '',
		taxId: ''
	};
}

const blank = (v: string | null | undefined) => !v || !v.trim();

export function profileProblems(p: PracticeProfileFields, groups: readonly ProfileGroup[]): Problems {
	const problems: Problems = {};
	if (groups.includes('identity')) {
		if (blank(p.name)) problems.name = REQUIRED;
		if (blank(p.contactName)) problems.contactName = REQUIRED;
		if (blank(p.phone)) problems.phone = REQUIRED;
		else if (!looksLikePhone(p.phone)) problems.phone = { key: 'kit.invalidPhone' };
		if (!blank(p.whatsapp) && !looksLikePhone(p.whatsapp ?? '')) problems.whatsapp = { key: 'kit.invalidPhone' };
		if (!blank(p.email) && !EMAIL.test((p.email ?? '').trim())) problems.email = { key: 'kit.invalidEmail' };
	}
	if (groups.includes('address')) {
		if (blank(p.address)) problems.address = REQUIRED;
		if (blank(p.city)) problems.city = REQUIRED;
		if (blank(p.governorate)) problems.governorate = REQUIRED;
		if (!blank(p.mapsUrl) && !/^https:\/\/\S+$/.test(p.mapsUrl.trim())) problems.mapsUrl = { key: 'kit.invalidUrl' };
	}
	return problems;
}

/** The profile as the API takes it: trimmed, empty optional contacts as null. */
export function profileBody(p: PracticeProfileFields): PracticeProfileFields {
	const trim = (v: string | null | undefined) => (v ?? '').trim();
	const orNull = (v: string | null | undefined) => (blank(v) ? null : trim(v));
	return {
		name: trim(p.name),
		nameAr: trim(p.nameAr),
		specialty: p.specialty,
		contactName: trim(p.contactName),
		phone: trim(p.phone),
		whatsapp: orNull(p.whatsapp),
		email: orNull(p.email),
		address: trim(p.address),
		postalCode: trim(p.postalCode),
		city: trim(p.city),
		governorate: orNull(p.governorate),
		mapsUrl: trim(p.mapsUrl),
		descriptionFr: trim(p.descriptionFr),
		descriptionAr: trim(p.descriptionAr),
		taxId: trim(p.taxId)
	};
}

// --- practitioners --------------------------------------------------------------------------------------------

export interface PractitionerDraft {
	title: string;
	name: string;
	/** '' = the practice's specialty */
	specialty: string;
}

const NO_TITLE: readonly string[] = ['kinesitherapeute', 'psychologue', 'autre'];

export function defaultTitle(specialty: string): string {
	return NO_TITLE.includes(specialty) ? '' : 'Dr.';
}

/** "Dr Amira Ben Salah" → title "Dr.", name "Amira Ben Salah". */
export function practitionerFromContact(contact: string, specialty: string): PractitionerDraft {
	const match = contact.trim().match(/^(dr|docteur|pr|professeur)\.?\s+(.+)$/i);
	if (!match) return { title: defaultTitle(specialty), name: contact.trim(), specialty: '' };
	const title = /^p/i.test(match[1]) ? 'Pr.' : 'Dr.';
	return { title, name: match[2].trim(), specialty: '' };
}

export function practitionerProblems(list: readonly PractitionerDraft[]): Problems {
	if (!list.length) return { list: { key: 'practice.practitioners.atLeastOne' } };
	const problems: Problems = {};
	list.forEach((p, i) => {
		if (blank(p.name)) problems[`name-${i}`] = REQUIRED;
	});
	return problems;
}

// --- services ---------------------------------------------------------------------------------------------------

export interface ServiceDraft {
	nameFr: string;
	nameAr: string;
	durationMin: string;
	priceText: string;
	onlineBookable: boolean;
}

export function serviceDrafts(list: readonly CatalogService[]): ServiceDraft[] {
	return list.map((s) => ({
		nameFr: s.nameFr,
		nameAr: s.nameAr,
		durationMin: String(s.durationMin),
		priceText: dinarsText(s.priceMillimes),
		onlineBookable: s.onlineBookable
	}));
}

export function validDuration(text: string): boolean {
	const n = Number(text);
	return /^\d+$/.test(text.trim()) && n >= 5 && n <= 480;
}

export function serviceProblems(list: readonly ServiceDraft[]): Problems {
	if (!list.length) return { list: { key: 'practice.services.atLeastOne' } };
	const problems: Problems = {};
	list.forEach((s, i) => {
		if (blank(s.nameFr)) problems[`nameFr-${i}`] = REQUIRED;
		if (!validDuration(s.durationMin)) problems[`durationMin-${i}`] = { key: 'practice.services.durationInvalid' };
		if (Number.isNaN(parseDinars(s.priceText))) problems[`price-${i}`] = { key: 'kit.invalidAmount' };
	});
	return problems;
}

export function servicesBody(list: readonly ServiceDraft[]): CatalogService[] {
	return list.map((s) => ({
		nameFr: s.nameFr.trim(),
		nameAr: s.nameAr.trim(),
		durationMin: Number(s.durationMin),
		priceMillimes: parseDinars(s.priceText),
		onlineBookable: s.onlineBookable
	}));
}

// --- online booking --------------------------------------------------------------------------------------------

export const BOOKING_LIMITS: Record<'horizonDays' | 'minNoticeHours' | 'maxPerDay' | 'blockNoShows', [number, number]> = {
	horizonDays: [1, 365],
	minNoticeHours: [0, 168],
	maxPerDay: [1, 200],
	blockNoShows: [0, 10]
};

export function bookingProblems(b: OnlineBooking): Problems {
	const problems: Problems = {};
	for (const [field, [min, max]] of Object.entries(BOOKING_LIMITS)) {
		const value = b[field as keyof typeof BOOKING_LIMITS];
		if (!Number.isInteger(value) || value < min || value > max) problems[field] = { key: 'kit.invalidNumber', params: { min, max } };
	}
	return problems;
}
