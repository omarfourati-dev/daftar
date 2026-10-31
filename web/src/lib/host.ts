/**
 * Hosts (fixlist 1): the app runs on its own origin `app.daftar.omarfourati.de` (admin, every practice's staff, demo,
 * booking pages `/r/<slug>`) and on the practice sub-domains: on `cabinet-lac.daftar.omarfourati.de` the app belongs
 * to the practice `cabinet-lac` (its booking page at `/`, its staff app at `/app`). The main domain only has the
 * landing (with Google AdSense) – the server sends app paths from there to the app host. Locally `app.localhost` and
 * `<slug>.localhost` work the same way when the backend runs with BASE_DOMAIN=localhost (docker-compose.yml).
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

export type HostKind = 'app' | 'practice' | 'main';

/** `app` for app.<base>, `practice` for a practice sub-domain, `main` for the main domain and every other host. */
export function hostKind(hostname: string, bases: readonly string[] = BASE_DOMAINS): HostKind {
	const host = hostname.toLowerCase().replace(/\.$/, '');
	if (bases.some((base) => host === 'app.' + base)) return 'app';
	return practiceSlugFromHost(host, bases) ? 'practice' : 'main';
}

/** Swappable in tests: the host name and origin the page runs on. */
export const hostDeps = {
	hostname: (): string => (typeof location === 'undefined' ? '' : location.hostname),
	origin: (): string => (typeof location === 'undefined' ? '' : location.origin)
};

/** The landing as seen from this page: from the app host the main domain (same scheme and port), else `/`. */
export function landingUrl(): string {
	const origin = hostDeps.origin();
	if (!origin) return '/';
	const url = new URL(origin);
	if (hostKind(url.hostname) !== 'app') return '/';
	url.hostname = url.hostname.replace(/^app\./i, '');
	return url.origin + '/';
}

/** What the page we are on is: the app host, a practice sub-domain or the main domain. */
export function currentHostKind(): HostKind {
	return hostKind(hostDeps.hostname());
}

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
