/** Links and texts of the waiting room: the patient's ticket page, the screen page, the WhatsApp message. */
import { t } from '../i18n.svelte';
import type { QueueEntry } from '../types/queue';

const origin = () => (typeof location === 'undefined' ? '' : location.origin);

export const ticketPath = (token: string) => `/ticket/${encodeURIComponent(token)}`;
export const screenPath = (token: string) => `/salle/${encodeURIComponent(token)}`;
export const ticketUrl = (token: string) => `${origin()}${ticketPath(token)}`;

/** "Bonjour, voici votre ticket au … : n° 14. Suivez votre tour ici : https://…/ticket/…" */
export function ticketMessage(entry: Pick<QueueEntry, 'ticketNo' | 'ticketToken'>, practice: string): string {
	return t('salle.message', { practice, number: entry.ticketNo, url: ticketUrl(entry.ticketToken) });
}

const ORDER: Record<string, number> = { in_treatment: 0, called: 1, waiting: 2, done: 3, left: 3 };

/** Waiting tickets by position, the others by ticket number. */
export function byTicket(a: QueueEntry, b: QueueEntry): number {
	return (ORDER[a.status] ?? 9) - (ORDER[b.status] ?? 9) || (a.position ?? 0) - (b.position ?? 0) || a.ticketNo - b.ticketNo;
}
