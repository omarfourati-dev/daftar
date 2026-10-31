/**
 * Prices typed in dinars ("35", "35,5", "1 250") ↔ millimes (the API's integer unit, 1 DT = 1000 millimes).
 * For display use `formatMillimes` from i18n; these two are for editable fields.
 */
const DINARS = /^\d+(?:[.,]\d{1,3})?$/;

/** Millimes, null for an empty field, NaN when the text is not an amount. */
export function parseDinars(text: string): number | null {
	const clean = text.replace(/[\s  ]/g, '');
	if (!clean) return null;
	if (!DINARS.test(clean)) return NaN;
	const [whole, fraction = ''] = clean.split(/[.,]/);
	return Number(whole) * 1000 + Number(fraction.padEnd(3, '0'));
}

/** "35", "35,5", "12,25" – millimes as the user would type them again. */
export function dinarsText(millimes: number | null | undefined): string {
	if (millimes === null || millimes === undefined) return '';
	const whole = Math.floor(millimes / 1000);
	const rest = String(millimes % 1000).padStart(3, '0').replace(/0+$/, '');
	return rest ? `${whole},${rest}` : String(whole);
}
