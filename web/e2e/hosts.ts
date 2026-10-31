/**
 * The hosts of the stack under test (docker-compose.yml runs it with BASE_DOMAIN=localhost; backend/daftar/hosts.py
 * and static.py decide what each host serves):
 *
 * - main domain `BASE` (E2E_BASE_URL): landing and legal texts only – app paths move to the app host (301), nobody
 *   signs in there;
 * - app host `APP` = `app.<base>`: the whole SPA (admin, every practice's staff, demo, /r/<slug>, /rdv, /salle, /ticket);
 * - practice sub-domains `<slug>.<base>`: the booking page `/`, `/rdv` and the practice's own app (only its staff signs in).
 *
 * Chromium resolves `*.localhost` itself, so pages open `APP + path` directly. Node on Windows does not
 * (getaddrinfo ENOTFOUND): requests from Node go to `BASE` with the Host header of the wanted host.
 */
export const BASE = process.env.E2E_BASE_URL ?? 'http://localhost:18083';
const base = new URL(BASE);

export const APP_HOST = `app.${base.host}`;
export const APP = `${base.protocol}//${APP_HOST}`;

/** `<slug>.localhost:<port>` – the Host header of a practice sub-domain. */
export const practiceHost = (slug: string): string => `${slug}.${base.host}`;
/** `http://<slug>.localhost:<port>` – the address of a practice sub-domain (for the browser). */
export const practiceOrigin = (slug: string): string => `${base.protocol}//${practiceHost(slug)}`;

/** A client IP of its own (`X-Forwarded-For`, trusted locally – no Caddy in front), so per-IP limits never collide. */
export function freshIp(): string {
	const n = () => Math.floor(Math.random() * 250) + 2;
	return `10.${n()}.${n()}.${n()}`;
}

/** Options of a Node request on the app host, from a client IP of its own. */
export const onApp = (headers: Record<string, string> = {}) => ({ headers: { host: APP_HOST, 'X-Forwarded-For': freshIp(), ...headers } });
