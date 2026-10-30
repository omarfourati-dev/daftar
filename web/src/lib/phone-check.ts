/**
 * A quick plausibility check before sending a phone number (the backend normalises and has the last word,
 * 422 `invalid_phone`): Tunisian numbers with 8 digits (optionally +216 / 00216), others only with + or 00.
 */
export function looksLikePhone(raw: string): boolean {
	const text = raw.trim();
	if (!/^[+\d][\d\s.\-()/]*$/.test(text)) return false;
	const digits = text.replace(/\D/g, '');
	if (text.startsWith('+') || digits.startsWith('00')) {
		const international = text.startsWith('+') ? digits : digits.slice(2);
		if (international.startsWith('216')) return international.length === 11;
		return international.length >= 8 && international.length <= 15;
	}
	return digits.length === 8;
}
