/**
 * Ready-made texts sent to a patient by click (wa.me / sms:), in the patient's language – not the language of the
 * screen. Dates as `jj/mm/aaaa`, times `HH:MM` (as the reminder templates of the backend).
 */
import { ar } from '../i18n/ar';
import { fr } from '../i18n/fr';
import { i18n } from '../i18n.svelte';
import { hhmm, minutesOfDay, tunisDayOf } from './time';

export type PatientMessage = keyof typeof fr.agenda.messages;

/** `2026-10-30T09:00:00+01:00` → `{date: '30/10/2026', time: '09:00'}`. */
export function dateAndTime(iso: string): { date: string; time: string } {
	const [y, m, d] = tunisDayOf(iso).split('-');
	return { date: `${d}/${m}/${y}`, time: hhmm(minutesOfDay(iso)) };
}

/** The patient's language when known (`fr`/`ar`), else the screen's. */
export function patientLang(lang: string | null | undefined): 'fr' | 'ar' {
	return lang === 'ar' || lang === 'fr' ? lang : i18n.locale;
}

export function messageIn(lang: string | null | undefined, key: PatientMessage, params: Record<string, string>): string {
	const text = (patientLang(lang) === 'ar' ? ar : fr).agenda.messages[key];
	return text.replace(/\{(\w+)\}/g, (whole, name: string) => params[name] ?? whole);
}
