/**
 * Click-to-send links (no messaging API, design section 1): WhatsApp `wa.me`, `sms:` and `tel:`, plus the
 * money input used in all forms (dinars typed by people → millimes for the API).
 */

/** `+216 20 123 456` → `21620123456` (what wa.me expects). */
export function phoneDigits(phone: string): string {
	return phone.replace(/\D/g, '');
}

export function whatsappUrl(phone: string, text?: string): string {
	const base = `https://wa.me/${phoneDigits(phone)}`;
	return text ? `${base}?text=${encodeURIComponent(text)}` : base;
}

/** `sms:+216…?&body=…` – the `?&` form opens the message on Android and on iPhone. */
export function smsUrl(phone: string, text: string): string {
	return `sms:+${phoneDigits(phone)}?&body=${encodeURIComponent(text)}`;
}

export function telUrl(phone: string): string {
	return `tel:+${phoneDigits(phone)}`;
}

/** `+21620123456` → `+216 20 123 456`; other numbers stay as stored. */
export function displayPhone(phone: string | null | undefined): string {
	if (!phone) return '';
	const m = /^\+216(\d{2})(\d{3})(\d{3})$/.exec(phone);
	return m ? `+216 ${m[1]} ${m[2]} ${m[3]}` : phone;
}

/** What people type ("12", "12,5", "12.500", "1 250") → millimes; null when it is not an amount. */
export function parseDinars(text: string): number | null {
	const clean = text.replace(/[\s  ]/g, '').replace(',', '.');
	if (!/^\d+(\.\d{1,3})?$/.test(clean)) return null;
	const [whole, frac = ''] = clean.split('.');
	return Number(whole) * 1000 + Number(frac.padEnd(3, '0'));
}

/** 12500 → "12,5" (empty for 0, so the field shows its placeholder). */
export function millimesToInput(millimes: number): string {
	if (!millimes) return '';
	const whole = Math.floor(millimes / 1000);
	const frac = String(millimes % 1000).padStart(3, '0').replace(/0+$/, '');
	return frac ? `${whole},${frac}` : String(whole);
}
