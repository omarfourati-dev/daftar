/** Test data for the customer pages (never imported by app code). */
import { defaultWeeklyHours } from '../hours';
import type { Me } from '../types';
import type { Practice, Practitioner, Service } from '../types/practice';

export const practiceBrief = {
	id: 1,
	name: 'Cabinet du Lac',
	slug: 'cabinet-lac',
	specialty: 'dentiste',
	status: 'active',
	brandColor: '#0f766e',
	isDemo: false,
	demoExpiresAt: null
};

export const owner: Me = { id: 2, email: 'amira@cabinet.tn', name: 'Amira Ben Salah', role: 'owner', lang: 'fr', practice: practiceBrief };
export const assistant: Me = { id: 5, email: 'salma@cabinet.tn', name: 'Salma', role: 'assistant', lang: 'fr', practice: practiceBrief };
export const dentist: Me = { id: 6, email: 'karim@cabinet.tn', name: 'Karim', role: 'dentist', lang: 'fr', practice: practiceBrief };
export const adminUser: Me = { id: 1, email: 'admin@daftar.test', name: 'Omar', role: 'admin', lang: 'fr', practice: null };

export function practice(overrides: Partial<Practice> = {}): Practice {
	return {
		id: 1,
		name: 'Cabinet du Lac',
		nameAr: 'عيادة البحيرة',
		slug: 'cabinet-lac',
		specialty: 'dentiste',
		contactName: 'Dr Amira Ben Salah',
		phone: '+21671123456',
		whatsapp: '+21620123456',
		email: 'contact@cabinet-lac.tn',
		address: '12 rue du Lac Léman',
		postalCode: '1053',
		city: 'Les Berges du Lac',
		governorate: 'tunis',
		mapsUrl: '',
		descriptionFr: '',
		descriptionAr: '',
		taxId: '',
		brandColor: '#0f766e',
		weeklyHours: defaultWeeklyHours(),
		slotMinutes: 15,
		defaultDurationMin: 30,
		reminderTemplateFr: 'Bonjour {patient}, rappel de votre rendez-vous le {date} à {time}.',
		reminderTemplateAr: 'مرحبًا {patient}، نذكّرك بموعدك يوم {date} على الساعة {time}.',
		displayToken: 'disp-token-1',
		isDemo: false,
		onlineBooking: { enabled: true, autoConfirm: false, horizonDays: 30, minNoticeHours: 2, maxPerDay: 20, blockNoShows: 2 },
		...overrides
	};
}

export const services: Service[] = [
	{ id: 11, nameFr: 'Consultation', nameAr: 'معاينة', durationMin: 30, priceMillimes: 40000, onlineBookable: true, color: null, active: true, sort: 1 },
	{ id: 12, nameFr: 'Détartrage', nameAr: 'إزالة الجير', durationMin: 45, priceMillimes: null, onlineBookable: true, color: null, active: true, sort: 2 },
	{ id: 13, nameFr: 'Blanchiment', nameAr: 'تبييض الأسنان', durationMin: 60, priceMillimes: 250000, onlineBookable: false, color: null, active: false, sort: 3 }
];

export const practitioners: Practitioner[] = [
	{ id: 21, name: 'Amira Ben Salah', title: 'Dr.', specialty: null, color: '#0f766e', onlineBookable: true, active: true, sort: 1 },
	{ id: 22, name: 'Karim Trabelsi', title: 'Dr.', specialty: 'orl', color: '#7c3aed', onlineBookable: false, active: true, sort: 2 }
];
