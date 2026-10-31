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
	minNoticeHours?: number;
	/** A demo practice: banner and noindex on its page (security review N3). */
	isDemo?: boolean;
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
	endsAt?: string;
	serviceName: string;
	practitionerName: string | null;
	manageToken: string;
}

/** `POST /api/public/bookings/lookup {token}` (and `…/cancel`) – never patient data. */
export interface ManagedBooking {
	status: string;
	startsAt: string;
	endsAt?: string;
	serviceName: string;
	practitionerName: string | null;
	canCancel?: boolean;
	/** last instant for cancelling online (startsAt − minimum notice) */
	cancelUntil?: string;
	practice: {
		slug: string;
		name: string;
		nameAr?: string;
		phone: string;
		whatsapp?: string | null;
		address?: string;
		city?: string;
		mapsUrl?: string;
	};
}
