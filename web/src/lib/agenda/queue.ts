/**
 * Links and texts of the waiting room: the patient's ticket page, the screen page, the WhatsApp message. Both public
 * pages live on the app host (a practice sub-domain does not serve them), so the links are absolute.
 */
import { ar } from '../i18n/ar';
import { fr } from '../i18n/fr';
import { appUrl } from '../links';
import type { QueueEntry } from '../types/queue';
import { patientLang } from './messages';

export const ticketPath = (token: string) => `/ticket/${encodeURIComponent(token)}`;
export const screenPath = (token: string) => `/salle/${encodeURIComponent(token)}`;
export const ticketUrl = (token: string) => appUrl(ticketPath(token));
export const screenUrl = (token: string) => appUrl(screenPath(token));

/**
 * "Bonjour, voici votre ticket au … : n° 14. Suivez votre tour ici : https://…/ticket/…" – in the patient's language
 * (code review N8), the screen's for a walk-in without a file.
 */
export function ticketMessage(entry: Pick<QueueEntry, 'ticketNo' | 'ticketToken' | 'patientLang'>, practice: string): string {
	const params: Record<string, string> = { practice, number: String(entry.ticketNo), url: ticketUrl(entry.ticketToken) };
	const text = (patientLang(entry.patientLang) === 'ar' ? ar : fr).salle.message;
	return text.replace(/\{(\w+)\}/g, (whole, name: string) => params[name] ?? whole);
}

const ORDER: Record<string, number> = { in_treatment: 0, called: 1, waiting: 2, done: 3, left: 3 };

/** Waiting tickets by position, the others by ticket number. */
export function byTicket(a: QueueEntry, b: QueueEntry): number {
	return (ORDER[a.status] ?? 9) - (ORDER[b.status] ?? 9) || (a.position ?? 0) - (b.position ?? 0) || a.ticketNo - b.ticketNo;
}
