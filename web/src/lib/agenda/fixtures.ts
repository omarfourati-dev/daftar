/**
 * Test data shared by the component and route tests of the daily work pages (never imported by app code).
 * The practice is "Cabinet du Lac", a Friday 30 October 2026, 10:10 in Tunis.
 */
import type { Me } from '../types';
import type { Appointment, PracticeSettings, Practitioner, Service } from '../types/agenda';

export const NOW = '2026-10-30T10:10:00+01:00';
export const TODAY = '2026-10-30';

export const practiceBrief = {
	id: 1,
	name: 'Cabinet du Lac',
	slug: 'cabinet-lac',
	specialty: 'generaliste',
	status: 'pilot',
	brandColor: '#0f766e',
	isDemo: false,
	demoExpiresAt: null
};

export const assistant: Me = { id: 5, email: 'salma@cabinet.tn', name: 'Salma', role: 'assistant', lang: 'fr', practice: practiceBrief };
export const owner: Me = { id: 2, email: 'amira@cabinet.tn', name: 'Amira', role: 'owner', lang: 'fr', practice: practiceBrief };

export const weeklyHours = {
	'1': [['08:00', '12:30'], ['14:00', '18:00']],
	'2': [['08:00', '12:30'], ['14:00', '18:00']],
	'3': [['08:00', '12:30']],
	'4': [['08:00', '12:30'], ['14:00', '18:00']],
	'5': [['08:00', '12:00'], ['14:30', '18:00']],
	'6': [['09:00', '13:00']],
	'7': []
} as Record<string, [string, string][]>;

export const practice: PracticeSettings = {
	id: 1,
	name: 'Cabinet du Lac',
	phone: '+21671000000',
	address: '12 rue du Lac',
	city: 'Tunis',
	specialty: 'generaliste',
	weeklyHours,
	slotMinutes: 15,
	defaultDurationMin: 30,
	displayToken: 'ecran-0123456789abcdef',
	isDemo: false,
	slug: 'cabinet-lac'
};

export const practitioners: Practitioner[] = [
	{ id: 11, name: 'Amira Ben Salem', title: 'Dr', color: '#0f766e', active: true, sort: 1 },
	{ id: 12, name: 'Karim Jaziri', title: 'Dr', color: '#7c3aed', active: true, sort: 2 }
];

export const services: Service[] = [
	{ id: 21, nameFr: 'Consultation', nameAr: 'استشارة', durationMin: 30, priceMillimes: 40000, active: true, sort: 1 },
	{ id: 22, nameFr: 'Contrôle', nameAr: 'مراقبة', durationMin: 20, priceMillimes: null, active: true, sort: 2 },
	{ id: 23, nameFr: 'Ancien acte', nameAr: 'خدمة قديمة', durationMin: 15, priceMillimes: null, active: false, sort: 3 }
];

let nextId = 100;

/** An appointment of today 09:00 with Dr Amira, overridable field by field. */
export function appt(over: Partial<Appointment> = {}): Appointment {
	const id = over.id ?? nextId++;
	return {
		id,
		patient: { id: 500 + id, firstName: 'Sami', lastName: 'Trabelsi', phone: '+21620123456', noShows: 0, lang: 'fr', alerts: '' },
		practitionerId: 11,
		practitionerName: 'Amira Ben Salem',
		serviceId: 21,
		serviceName: 'Consultation',
		startsAt: '2026-10-30T09:00:00+01:00',
		endsAt: '2026-10-30T09:30:00+01:00',
		durationMin: 30,
		reason: 'Consultation',
		status: 'scheduled',
		source: 'staff',
		notes: '',
		patientNote: '',
		depositRequiredMillimes: 0,
		depositPaidMillimes: 0,
		reminderSentAt: null,
		createdAt: '2026-10-20T10:00:00+01:00',
		seriesId: null,
		...over
	};
}
