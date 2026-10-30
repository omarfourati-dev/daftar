/** Helpers of the public booking pages (section 11.3): days, labels, error texts, manifest. */
import { ApiError, apiErrorMessage } from './api';
import { addDays, i18n, TIME_ZONE, translate } from './i18n.svelte';
import type { PublicService } from './types/booking';

/** Swappable in tests. */
export const bookingDeps = {
	replace: (url: string): void => location.replace(url)
};

/** The bookable calendar days: today and the next `horizon - 1` days (`YYYY-MM-DD`). */
export function bookingDays(today: string, horizon: number): string[] {
	return Array.from({ length: Math.max(1, Math.min(horizon, 365)) }, (_, i) => addDays(today, i));
}

function intl(): string {
	return i18n.locale === 'ar' ? 'ar-TN-u-nu-latn' : 'fr-TN';
}

/** "lun.", "2", "nov.", "novembre 2026" – parts of a calendar day in the current language (Tunis). */
export function dayParts(day: string): { weekday: string; day: string; month: string; monthYear: string } {
	const at = new Date(`${day}T12:00:00+01:00`);
	const f = (o: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat(intl(), { timeZone: TIME_ZONE, ...o }).format(at);
	return { weekday: f({ weekday: 'short' }), day: f({ day: 'numeric' }), month: f({ month: 'short' }), monthYear: f({ month: 'long', year: 'numeric' }) };
}

export function serviceName(service: Pick<PublicService, 'nameFr' | 'nameAr'>): string {
	return i18n.locale === 'ar' && service.nameAr ? service.nameAr : service.nameFr;
}

/** The text of a failed booking or cancellation, in the patient's language. */
export function bookingErrorMessage(err: unknown): string {
	if (err instanceof ApiError) {
		const known = err.code ? translate(`booking.errors.${err.code}`) : undefined;
		if (known) return known;
		if (err.status === 409) return translate('booking.errors.slot_unavailable') ?? '';
		if (err.status === 429) return translate('booking.errors.too_many_requests') ?? '';
	}
	return apiErrorMessage(err);
}

/** On a practice sub-domain the page installs as the booking app (`/booking.webmanifest`, section 13). */
export function useBookingManifest(): void {
	const link = document.querySelector<HTMLLinkElement>('link[rel=manifest]');
	if (link) link.setAttribute('href', '/booking.webmanifest');
}
