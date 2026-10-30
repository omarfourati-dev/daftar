/**
 * Practice slugs (the sub-domain of the booking page) – the same rules as backend daftar/slugs.py, so the admin
 * wizard can explain a problem before asking the server (`GET /api/admin/slug-available` also checks uniqueness).
 */
export const SLUG_PATTERN = /^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$/;
export const RESERVED_SLUGS: ReadonlySet<string> = new Set([
	'www',
	'app',
	'api',
	'admin',
	'demo',
	'mail',
	'smtp',
	'static',
	'assets',
	'daftar',
	'status',
	'monitoring',
	'test'
]);
const MAX_LENGTH = 40;

/** What the live check in the admin forms knows about a sub-domain. */
export type SlugState = 'idle' | 'unchanged' | 'checking' | 'available' | 'taken' | 'reserved' | 'invalid' | 'error';

export function slugProblem(slug: string): 'invalid' | 'reserved' | null {
	if (!SLUG_PATTERN.test(slug)) return 'invalid';
	if (RESERVED_SLUGS.has(slug)) return 'reserved';
	return null;
}

/** A valid slug from a practice name: accents removed, words joined by hyphens, at most 40 characters. */
export function suggestSlug(name: string): string {
	const ascii = name
		.normalize('NFKD')
		.replace(/[^\x00-\x7f]/g, '')
		.toLowerCase();
	let slug = '';
	for (const word of ascii.match(/[a-z0-9]+/g) ?? []) {
		const candidate = slug ? `${slug}-${word}` : word;
		if (candidate.length > MAX_LENGTH) break;
		slug = candidate;
	}
	if (!slug) return 'cabinet';
	if (slugProblem(slug) !== null) slug = `${slug}-cabinet`.slice(0, MAX_LENGTH).replace(/^-+|-+$/g, '');
	return slug;
}
