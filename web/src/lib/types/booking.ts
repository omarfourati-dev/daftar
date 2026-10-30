/** Public online booking (sections 11.3, 13): practice profile, free times, booking, the patient's own link. */
import type { WeeklyHours } from '../hours';

export interface PublicService {
	id: number;
	nameFr: string;
	nameAr: string;
	durationMin: number;
	priceMillimes: number | null;
}

export interface PublicPractitioner {
	id: number;
	name: string;
	title?: string;
	specialty?: string | null;
}

/** `GET /api/public/practices/{slug}` */
export interface PublicPracticeProfile {
	slug: string;
	name: string;
	nameAr: string;
	specialty: string;
	address: string;
	postalCode?: string;
	city: string;
	governorate: string | null;
	phone: string;
	whatsapp: string | null;
	mapsUrl: string;
	descriptionFr: string;
	descriptionAr: string;
	weeklyHours: WeeklyHours;
	brandColor?: string;
	onlineBookingEnabled: boolean;
	services: PublicService[];
	practitioners: PublicPractitioner[];
	horizonDays: number;
}

/** `GET /api/public/practices/{slug}/slots` */
export interface SlotsAnswer {
	date: string;
	slots: string[];
}

/** `POST /api/public/practices/{slug}/bookings` → 201 */
export interface BookingCreated {
	status: 'requested' | 'confirmed' | string;
	startsAt: string;
	serviceName: string;
	practitionerName: string | null;
	manageToken: string;
}

/** `GET /api/public/bookings/{token}` (contract addition: the fields below; `cancellable` optional). */
export interface ManagedBooking {
	status: string;
	startsAt: string;
	durationMin?: number;
	serviceName: string;
	practitionerName: string | null;
	cancellable?: boolean;
	practice: {
		slug: string;
		name: string;
		nameAr?: string;
		phone: string;
		whatsapp?: string | null;
		address?: string;
		city?: string;
		mapsUrl?: string;
		minNoticeHours?: number;
	};
}
