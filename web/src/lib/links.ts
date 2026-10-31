/**
 * Addresses we hand out (invitation, booking page, waiting-room screen) and click-to-chat links.
 * A practice lives on its own sub-domain `<slug>.<base>`, the app on `app.<base>`, the landing on `<base>`; the base
 * is taken from the page we are on, so the same code works on the app host, on a practice's sub-domain, on the main
 * domain and locally on `[app.]localhost:<port>`.
 */
import { hostKind, practiceSlugFromHost } from './host';

function here(): URL {
	return new URL(typeof location === 'undefined' ? 'http://localhost/' : location.href);
}

const IP = /^(?:\d{1,3}(?:\.\d{1,3}){3}|\[[0-9a-f:]+\])$/i;

/** host[:port] of the main domain for the page at `at` (`app.<base>` and `<slug>.<base>` → `<base>`). */
function mainHost(at: URL): string {
	if (hostKind(at.hostname) === 'app') return at.host.slice('app.'.length);
	const slug = practiceSlugFromHost(at.hostname);
	return slug ? at.host.slice(slug.length + 1) : at.host;
}

/**
 * `https://<slug>.<base><path>`. Where sub-domains cannot exist (an IP address) the booking page falls back to
 * `/r/<slug>` and other paths stay on the current origin.
 */
export function practiceUrl(slug: string, path = '/', at: URL = here()): string {
	if (IP.test(at.hostname)) return `${at.protocol}//${at.host}${path === '/' ? `/r/${slug}` : path}`;
	return `${at.protocol}//${slug}.${mainHost(at)}${path}`;
}

/** An address on the main domain (landing, legal texts). */
export function mainUrl(path: string, at: URL = here()): string {
	return `${at.protocol}//${mainHost(at)}${path}`;
}

/** An address on the app host `app.<base>` (waiting-room screen, ticket pages); on an IP address the same origin. */
export function appUrl(path: string, at: URL = here()): string {
	if (IP.test(at.hostname)) return `${at.protocol}//${at.host}${path}`;
	return `${at.protocol}//app.${mainHost(at)}${path}`;
}

/** Digits of an international number for wa.me (no +, no spaces); 8 Tunisian digits get the 216 prefix. */
export function phoneDigits(phone: string): string {
	const digits = phone.replace(/\D/g, '');
	if (!phone.trim().startsWith('+') && digits.length === 8) return `216${digits}`;
	return digits.startsWith('00') ? digits.slice(2) : digits;
}

/** WhatsApp with a ready message – to a number, or (without number) to a contact the user picks. */
export function whatsappUrl(text: string, phone?: string | null): string {
	return `https://wa.me/${phone ? phoneDigits(phone) : ''}?text=${encodeURIComponent(text)}`;
}

export function telUrl(phone: string): string {
	return `tel:+${phoneDigits(phone)}`;
}
