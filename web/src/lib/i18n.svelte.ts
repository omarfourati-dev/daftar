/**
 * Languages: French (default) and Arabic (right-to-left). Dictionaries live in ./i18n/{fr,ar}/*.ts.
 *
 *   import { t, i18n, formatMillimes, formatDate } from '#lib/i18n.svelte';
 *   <h1>{t('agenda.title')}</h1>   ·   {t('invitation.intro', { practice, role })}   ·   {formatMillimes(12500)}
 *
 * `t` reads reactive state, so templates update when the language changes. All dates and times are shown in
 * Africa/Tunis (UTC+1, no daylight saving time) with western digits, also in Arabic.
 */
import { ar } from './i18n/ar';
import { fr, type Messages } from './i18n/fr';

export type Locale = 'fr' | 'ar';
export const LOCALES: readonly Locale[] = ['fr', 'ar'];
export const TIME_ZONE = 'Africa/Tunis';
const STORAGE_KEY = 'daftar.lang';
const DICTIONARIES: Record<Locale, Messages> = { fr, ar };

type Leaves<T, P extends string = ''> = {
	[K in keyof T & string]: T[K] extends string ? `${P}${K}` : Leaves<T[K], `${P}${K}.`>;
}[keyof T & string];

/** Every existing text key, e.g. `'auth.submit'`. */
export type MessageKey = Leaves<Messages>;
export type Params = Record<string, string | number>;

export function isLocale(value: unknown): value is Locale {
	return value === 'fr' || value === 'ar';
}

function readStored(): Locale {
	try {
		const value = localStorage.getItem(STORAGE_KEY);
		return isLocale(value) ? value : 'fr';
	} catch {
		return 'fr';
	}
}

class I18n {
	locale = $state<Locale>(readStored());

	get dir(): 'ltr' | 'rtl' {
		return this.locale === 'ar' ? 'rtl' : 'ltr';
	}

	/** Switches the language, remembers it on this device and updates `<html lang dir>`. */
	setLocale(locale: Locale) {
		this.locale = locale;
		try {
			localStorage.setItem(STORAGE_KEY, locale);
		} catch {
			/* private mode: this page only */
		}
		this.apply();
	}

	/** Writes `lang` and `dir` to `<html>` (called by the root layout on start). */
	apply() {
		if (typeof document === 'undefined') return;
		document.documentElement.lang = this.locale;
		document.documentElement.dir = this.dir;
	}
}

export const i18n = new I18n();

function lookup(dictionary: Messages, key: string): string | undefined {
	let node: unknown = dictionary;
	for (const part of key.split('.')) {
		if (node === null || typeof node !== 'object' || !(part in node)) return undefined;
		node = (node as Record<string, unknown>)[part];
	}
	return typeof node === 'string' ? node : undefined;
}

function fill(text: string, params?: Params): string {
	if (!params) return text;
	return text.replace(/\{(\w+)\}/g, (whole, name: string) => (name in params ? String(params[name]) : whole));
}

/** The text of `key` in the current language, with `{placeholders}` filled in. */
export function t(key: MessageKey, params?: Params): string {
	return translate(key, params) ?? key;
}

/** Like `t` for keys built at runtime (e.g. `errors.${code}`); undefined when the key does not exist. */
export function translate(key: string, params?: Params): string | undefined {
	const text = lookup(DICTIONARIES[i18n.locale], key) ?? lookup(fr, key);
	return text === undefined ? undefined : fill(text, params);
}

// --- numbers and money ------------------------------------------------------------------------------------------

function intlLocale(): string {
	return i18n.locale === 'ar' ? 'ar-TN-u-nu-latn' : 'fr-TN';
}

export function formatNumber(value: number): string {
	return new Intl.NumberFormat(intlLocale()).format(value);
}

/**
 * Money is stored in millimes (1 DT = 1000 millimes): 120000 → "120 DT", 12500 → "12,500 DT",
 * 1250000 → "1 250 DT". Same format in both languages (as Tunisian price tags write it).
 */
export function formatMillimes(millimes: number): string {
	const sign = millimes < 0 ? '-' : '';
	const abs = Math.abs(Math.round(millimes));
	const dinars = Math.floor(abs / 1000);
	const rest = abs % 1000;
	const grouped = String(dinars).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
	return rest === 0 ? `${sign}${grouped} DT` : `${sign}${grouped},${String(rest).padStart(3, '0')} DT`;
}

// --- dates and times (always Africa/Tunis) ----------------------------------------------------------------------

type DateInput = Date | string | number;
const toDate = (value: DateInput) => (value instanceof Date ? value : new Date(value));

function dateFormat(style: 'short' | 'long'): Intl.DateTimeFormatOptions {
	return style === 'long'
		? { timeZone: TIME_ZONE, weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }
		: { timeZone: TIME_ZONE, day: '2-digit', month: '2-digit', year: 'numeric' };
}

/** "31/10/2026" or (long) "samedi 31 octobre 2026" – the Tunis date of an instant. */
export function formatDate(value: DateInput, style: 'short' | 'long' = 'short'): string {
	return new Intl.DateTimeFormat(intlLocale(), dateFormat(style)).format(toDate(value));
}

/** "09:30" – 24 h, Tunis time. */
export function formatTime(value: DateInput): string {
	return new Intl.DateTimeFormat(intlLocale(), {
		timeZone: TIME_ZONE,
		hour: '2-digit',
		minute: '2-digit',
		hourCycle: 'h23'
	}).format(toDate(value));
}

export function formatDateTime(value: DateInput): string {
	return `${formatDate(value)} ${formatTime(value)}`;
}

/** A calendar day `YYYY-MM-DD` (no instant, no shifting): "30/10/2026" or "vendredi 30 octobre 2026". */
export function formatDay(day: string, style: 'short' | 'long' = 'short'): string {
	return formatDate(`${day}T12:00:00+01:00`, style);
}

/** Today in Tunis as `YYYY-MM-DD`. */
export function todayTunis(now: Date = new Date()): string {
	return new Intl.DateTimeFormat('en-CA', {
		timeZone: TIME_ZONE,
		year: 'numeric',
		month: '2-digit',
		day: '2-digit'
	}).format(now);
}

/** `addDays('2026-10-30', 2)` → `'2026-11-01'`. */
export function addDays(day: string, days: number): string {
	const date = new Date(`${day}T00:00:00Z`);
	date.setUTCDate(date.getUTCDate() + days);
	return date.toISOString().slice(0, 10);
}

/** The instant of a wall-clock time in Tunis, as the API expects it: `2026-10-30T09:30:00+01:00`. */
export function tunisInstant(day: string, time: string): string {
	return `${day}T${time}:00+01:00`;
}

/** `?lang=ar|fr` in the address (links from the landing page) switches the language; returns the locale applied. */
export function applyLocaleFromQuery(search: string = typeof location === 'undefined' ? '' : location.search): Locale | null {
	const value = new URLSearchParams(search).get('lang');
	if (!isLocale(value)) return null;
	i18n.setLocale(value);
	return value;
}
