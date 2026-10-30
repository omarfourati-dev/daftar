/**
 * Helpers for the customer-area E2E tests (admin, settings, booking, import, subscription) against the real stack.
 *
 * - Every test gets its own client IP (`X-Forwarded-For`, trusted locally because there is no Caddy in front),
 *   so the per-IP limits of logins, demo and online bookings never leak between tests or reruns.
 * - Practices are created through the admin API with a unique slug; sessions are put into localStorage
 *   instead of logging in through the form (the form login is tested once in admin.spec.ts).
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, request as playwrightRequest, type APIRequestContext, type Page } from '@playwright/test';

export const BASE = process.env.E2E_BASE_URL ?? 'http://localhost:18083';
export const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? 'admin@daftar.test';
export const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'local-admin-password-123';

export type Session = { token: string; user: { id: number; role: string; practice: { id: number; slug: string } | null; [k: string]: unknown } };

export function freshIp(): string {
	const n = () => Math.floor(Math.random() * 250) + 2;
	return `10.${n()}.${n()}.${n()}`;
}

export function uniqueSlug(prefix = 'e2e'): string {
	return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

/** The address of a practice sub-domain on the local stack: `http://<slug>.localhost:<port>`. */
export function practiceOrigin(slug: string): string {
	const url = new URL(BASE);
	return `${url.protocol}//${slug}.${url.host}`;
}

export async function apiContext(ip = freshIp(), token?: string): Promise<APIRequestContext> {
	return playwrightRequest.newContext({
		baseURL: BASE,
		extraHTTPHeaders: { 'X-Forwarded-For': ip, ...(token ? { Authorization: `Bearer ${token}` } : {}) }
	});
}

export async function adminSession(): Promise<Session> {
	const api = await apiContext();
	const res = await api.post('/api/auth/login', { data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD } });
	expect(res.status(), await res.text()).toBe(200);
	const session = (await res.json()) as Session;
	await api.dispose();
	return session;
}

const ALL_DAY = Object.fromEntries(['1', '2', '3', '4', '5', '6', '7'].map((d) => [d, [['00:00', '23:59']]]));

export interface PracticeSetup {
	name?: string;
	slug?: string;
	specialty?: string;
	onlineBooking?: boolean;
	allDay?: boolean;
	practitioners?: { name: string; title?: string }[];
	extra?: Record<string, unknown>;
}

/** Creates a practice through the admin API and returns it with the owner's invitation token. */
export async function createPractice(admin: Session, setup: PracticeSetup = {}) {
	const api = await apiContext(freshIp(), admin.token);
	const slug = setup.slug ?? uniqueSlug();
	const res = await api.post('/api/admin/practices', {
		data: {
			name: setup.name ?? `Cabinet E2E ${slug}`,
			nameAr: 'عيادة الاختبار',
			slug,
			specialty: setup.specialty ?? 'generaliste',
			contactName: 'Dr Amira Ben Salah',
			phone: '+21671123456',
			whatsapp: '+21620123456',
			address: '14 avenue Habib Bourguiba',
			city: 'Sousse',
			governorate: 'sousse',
			status: 'pilot',
			planCode: 'pilot',
			...(setup.allDay ? { weeklyHours: ALL_DAY } : {}),
			practitioners: setup.practitioners ?? [{ title: 'Dr.', name: 'Amira Ben Salah' }],
			onlineBooking: { enabled: setup.onlineBooking ?? false, autoConfirm: false, horizonDays: 14, minNoticeHours: 0, maxPerDay: 50, blockNoShows: 2 },
			...setup.extra
		}
	});
	expect(res.status(), await res.text()).toBe(201);
	const created = (await res.json()) as { practice: { id: number; slug: string; name: string }; invitation: { token: string } };
	await api.dispose();
	return { ...created, slug };
}

/** Accepts an invitation through the API: the owner (or team member) session. */
export async function acceptInvitation(token: string, name = 'Dr Amira Ben Salah', email = `${uniqueSlug('owner')}@cabinet.test`) {
	const api = await apiContext();
	const res = await api.post('/api/invitations/accept', { data: { token, name, email, password: 'mot-de-passe-solide-123', lang: 'fr' } });
	expect(res.status(), await res.text()).toBe(201);
	const session = (await res.json()) as Session;
	await api.dispose();
	return { ...session, email, password: 'mot-de-passe-solide-123' };
}

/** A practice with its owner signed in (API). */
export async function practiceWithOwner(admin: Session, setup: PracticeSetup = {}) {
	const created = await createPractice(admin, setup);
	const owner = await acceptInvitation(created.invitation.token);
	return { ...created, owner };
}

/** Puts a session into the localStorage of `origin` and gives the page its own client IP. */
export async function signInAs(page: Page, session: Session, origin = BASE, lang = 'fr') {
	await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': freshIp() });
	await page.goto(`${origin}/connexion`);
	await page.evaluate(
		([token, user, l]) => {
			localStorage.setItem('daftar.token', token);
			localStorage.setItem('daftar.user', user);
			localStorage.setItem('daftar.lang', l);
		},
		[session.token, JSON.stringify(session.user), lang] as const
	);
}

/** Console errors and uncaught exceptions of the page (failed requests the test provokes are filtered by the caller). */
export function watchConsole(page: Page): string[] {
	const problems: string[] = [];
	page.on('console', (msg) => {
		if (msg.type() === 'error') problems.push(msg.text());
	});
	page.on('pageerror', (err) => problems.push(err.message));
	return problems;
}

/** axe-core: no "serious" or "critical" violations (Definition of Done 6). */
export async function expectAccessible(page: Page, label: string) {
	const results = await new AxeBuilder({ page }).analyze();
	const bad = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
	expect(
		bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`),
		`${label} – axe serious/critical`
	).toEqual([]);
}

/** No horizontal scroll bar at the current viewport (Definition of Done 5). */
export async function expectNoHorizontalScroll(page: Page, label: string) {
	const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
	expect(overflow, `${label} – horizontal overflow in px`).toBeLessThanOrEqual(0);
}
