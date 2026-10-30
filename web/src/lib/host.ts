/**
 * Practice sub-domains: on `cabinet-lac.daftar.omarfourati.de` the app belongs to the practice `cabinet-lac`
 * (its booking page at `/`, its staff app at `/app`). Locally `<slug>.localhost` works the same way when the
 * backend runs with BASE_DOMAIN=localhost (docker-compose.yml).
 */
import { api } from './api';

const SLUG = /^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$/;
const RESERVED = new Set(['www', 'app', 'api', 'admin', 'demo', 'mail', 'smtp', 'static', 'assets', 'daftar', 'status', 'monitoring', 'test']);
export const BASE_DOMAINS: readonly string[] = [import.meta.env.VITE_BASE_DOMAIN ?? 'daftar.omarfourati.de', 'localhost'];

/** The practice slug of a host name, or null on the main domain (and for anything that is not a practice). */
export function practiceSlugFromHost(hostname: string, bases: readonly string[] = BASE_DOMAINS): string | null {
	const host = hostname.toLowerCase().replace(/\.$/, '');
	for (const base of bases) {
		if (!host.endsWith('.' + base)) continue;
		const label = host.slice(0, -(base.length + 1));
		return SLUG.test(label) && !RESERVED.has(label) ? label : null;
	}
	return null;
}

/** Swappable in tests: the host name the page runs on. */
export const hostDeps = {
	hostname: (): string => (typeof location === 'undefined' ? '' : location.hostname)
};

/** The practice slug of the page we are on, or null on the main domain. */
export function currentPracticeSlug(): string | null {
	return practiceSlugFromHost(hostDeps.hostname());
}

/** Public profile of a practice (`GET /api/public/practices/{slug}`, section 11.3). */
export interface PublicPractice {
	name: string;
	nameAr?: string;
	brandColor?: string;
	[key: string]: unknown;
}

/** The public profile, or null when it cannot be loaded (endpoint not there yet, unknown slug, offline). */
export async function loadPublicPractice(slug: string): Promise<PublicPractice | null> {
	try {
		return await api<PublicPractice>(`/api/public/practices/${encodeURIComponent(slug)}`);
	} catch {
		return null;
	}
}
