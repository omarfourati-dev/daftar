/** Arabic-Indic (٠–٩) and extended Arabic-Indic (۰–۹) digits – what Arabic keyboards type – as ASCII digits; the
 * server converts them the same way (daftar/phone.py). */
export function asciiDigits(text: string): string {
	return text.replace(/[٠-٩۰-۹]/g, (d) => String((d.charCodeAt(0) & 0xf) % 10));
}

/**
 * A quick plausibility check before sending a phone number (the backend normalises and has the last word,
 * 422 `invalid_phone`): Tunisian numbers with 8 digits (optionally +216 / 00216), others only with + or 00.
 */
export function looksLikePhone(raw: string): boolean {
	const text = asciiDigits(raw.trim());
	if (!/^[+\d][\d\s.\-()/]*$/.test(text)) return false;
	const digits = text.replace(/\D/g, '');
	if (text.startsWith('+') || digits.startsWith('00')) {
		const international = text.startsWith('+') ? digits : digits.slice(2);
		if (international.startsWith('216')) return international.length === 11;
		return international.length >= 8 && international.length <= 15;
	}
	return digits.length === 8;
}

/** "+21671123456" → "+216 71 123 456" (how Tunisians write numbers); other numbers unchanged. */
export function formatPhone(e164: string): string {
	const digits = e164.replace(/\D/g, '');
	if (e164.trim().startsWith('+') && digits.length === 11 && digits.startsWith('216')) {
		return `+216 ${digits.slice(3, 5)} ${digits.slice(5, 8)} ${digits.slice(8)}`;
	}
	return e164;
}
