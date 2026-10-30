import { beforeEach, describe, expect, it, vi } from 'vitest';

const noMarks = (s: string) => s.replace(/[‎‏؜]/g, '');
const ARABIC_INDIC = /[٠-٩۰-۹]/;

async function fresh() {
	vi.resetModules();
	return import('./i18n.svelte');
}

describe('i18n', () => {
	beforeEach(() => {
		localStorage.clear();
		document.documentElement.lang = '';
		document.documentElement.dir = '';
	});

	it('starts in French and translates keys', async () => {
		const { i18n, t } = await fresh();
		expect(i18n.locale).toBe('fr');
		expect(i18n.dir).toBe('ltr');
		expect(t('nav.agenda')).toBe('Agenda');
		expect(t('auth.submit')).toBe('Se connecter');
	});

	it('switches to Arabic, right-to-left, persisted and applied to <html>', async () => {
		const { i18n, t } = await fresh();
		i18n.setLocale('ar');
		expect(t('auth.submit')).toBe('تسجيل الدخول');
		expect(i18n.dir).toBe('rtl');
		expect(document.documentElement.lang).toBe('ar');
		expect(document.documentElement.dir).toBe('rtl');
		expect(localStorage.getItem('daftar.lang')).toBe('ar');
		const again = await fresh(); // a new page load reads the saved choice
		expect(again.i18n.locale).toBe('ar');
	});

	it('ignores unknown saved languages and survives blocked storage', async () => {
		localStorage.setItem('daftar.lang', 'de');
		expect((await fresh()).i18n.locale).toBe('fr');
		vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
			throw new Error('blocked');
		});
		vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
			throw new Error('blocked');
		});
		const { i18n } = await fresh();
		i18n.setLocale('ar');
		expect(i18n.locale).toBe('ar');
		vi.restoreAllMocks();
	});

	it('fills {placeholders}', async () => {
		const { t } = await fresh();
		expect(t('invitation.intro', { practice: 'Cabinet Lac 2', role: 'assistant(e)' })).toBe(
			'Vous êtes invité(e) à rejoindre Cabinet Lac 2 en tant que assistant(e).'
		);
	});

	it('looks up dynamic keys without throwing', async () => {
		const { translate } = await fresh();
		expect(translate('errors.invalid_credentials')).toBe('E-mail ou mot de passe incorrect.');
		expect(translate('errors.no_such_code')).toBeUndefined();
		expect(translate('nav')).toBeUndefined(); // a namespace is not a text
	});

	it('formats money in millimes', async () => {
		const { formatMillimes, i18n } = await fresh();
		expect(formatMillimes(120_000)).toBe('120 DT');
		expect(formatMillimes(12_500)).toBe('12,500 DT');
		expect(formatMillimes(500)).toBe('0,500 DT');
		expect(formatMillimes(0)).toBe('0 DT');
		expect(formatMillimes(1_250_000)).toBe('1 250 DT');
		expect(formatMillimes(-1_500)).toBe('-1,500 DT');
		i18n.setLocale('ar');
		expect(formatMillimes(12_500)).toBe('12,500 DT'); // same digits and format in Arabic
	});

	it('formats instants in Tunis time with western digits', async () => {
		const { formatDate, formatTime, formatDateTime, i18n } = await fresh();
		const at = '2026-10-30T23:30:00Z'; // already 31 October, 00:30 in Tunis
		expect(formatDate(at)).toBe('31/10/2026');
		expect(formatTime(at)).toBe('00:30');
		expect(formatDateTime(at)).toBe('31/10/2026 00:30');
		expect(formatDate(at, 'long')).toBe('samedi 31 octobre 2026');
		i18n.setLocale('ar');
		expect(noMarks(formatDate(at))).toBe('31/10/2026');
		expect(formatTime(new Date('2026-10-30T08:05:00Z'))).toBe('09:05');
		const long = formatDate(at, 'long');
		expect(long).toContain('31');
		expect(long).toContain('2026');
		expect(long).not.toMatch(ARABIC_INDIC);
	});

	it('formats calendar days without shifting them', async () => {
		const { formatDay } = await fresh();
		expect(formatDay('2026-10-30')).toBe('30/10/2026');
		expect(formatDay('2026-01-01', 'long')).toBe('jeudi 1 janvier 2026');
	});

	it('knows today in Tunis and builds instants with the Tunis offset', async () => {
		const { todayTunis, addDays, tunisInstant } = await fresh();
		expect(todayTunis(new Date('2026-10-30T22:59:00Z'))).toBe('2026-10-30');
		expect(todayTunis(new Date('2026-10-30T23:00:00Z'))).toBe('2026-10-31');
		expect(addDays('2026-10-30', 2)).toBe('2026-11-01');
		expect(addDays('2026-03-01', -1)).toBe('2026-02-28');
		expect(tunisInstant('2026-10-30', '09:30')).toBe('2026-10-30T09:30:00+01:00');
	});

	it('formats numbers with western digits in both languages', async () => {
		const { formatNumber, i18n } = await fresh();
		expect(formatNumber(42)).toBe('42');
		i18n.setLocale('ar');
		expect(formatNumber(1234)).not.toMatch(ARABIC_INDIC);
	});
});
