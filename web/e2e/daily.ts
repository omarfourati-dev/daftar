/**
 * Helpers of the daily-work E2E tests (agenda, waiting room, patients, cash, reminders, statistics): each test gets
 * its own practice (created by the admin over the API, owner via the invitation), data is created over the API,
 * the browser starts signed in (token in localStorage – no UI login, so the login throttle is never hit).
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, type APIRequestContext, type Page } from '@playwright/test';

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? 'admin@daftar.test';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'local-admin-password-123';
const PASSWORD = 'mot-de-passe-e2e-solide';
const ALL_DAY = Object.fromEntries(['1', '2', '3', '4', '5', '6', '7'].map((d) => [d, [['00:00', '23:59']]]));

let adminToken: string | null = null;

/** One admin login per worker process. */
export async function admin(request: APIRequestContext): Promise<string> {
	if (adminToken) return adminToken;
	const res = await request.post('/api/auth/login', { data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD } });
	expect(res.status(), await res.text()).toBe(200);
	adminToken = (await res.json()).token as string;
	return adminToken;
}

export interface Api {
	get<T = any>(path: string): Promise<T>;
	post<T = any>(path: string, data?: unknown): Promise<T>;
	patch<T = any>(path: string, data: unknown): Promise<T>;
}

/** JSON calls with a bearer token; any non-2xx answer fails the test with the server's message. */
export function api(request: APIRequestContext, token: string): Api {
	const headers = { Authorization: `Bearer ${token}` };
	// eslint-disable-next-line @typescript-eslint/no-explicit-any -- test data of any endpoint
	const read = async (res: Awaited<ReturnType<APIRequestContext['get']>>, what: string): Promise<any> => {
		expect(res.ok(), `${what} → ${res.status()} ${await res.text()}`).toBeTruthy();
		return res.status() === 204 ? undefined : res.json();
	};
	return {
		get: async (path) => read(await request.get(path, { headers }), `GET ${path}`),
		post: async (path, data) => read(await request.post(path, { headers, data: data ?? {} }), `POST ${path}`),
		patch: async (path, data) => read(await request.patch(path, { headers, data }), `PATCH ${path}`)
	};
}

export interface Practice {
	id: number;
	slug: string;
	name: string;
	token: string;
	user: Record<string, unknown>;
	email: string;
	practitioners: { id: number; name: string; title: string }[];
	services: { id: number; nameFr: string; durationMin: number; onlineBookable: boolean }[];
	displayToken: string;
	api: Api;
}

let counter = 0;

/** A fresh practice (open every day 00:00–23:59, two practitioners) and its signed-in owner. */
export async function newPractice(request: APIRequestContext, options: { onlineBooking?: boolean } = {}): Promise<Practice> {
	const tag = `${Date.now().toString(36)}${(counter++).toString(36)}${Math.random().toString(36).slice(2, 6)}`;
	const slug = `e2e-${tag}`;
	const name = `Cabinet E2E ${tag}`;
	const adminApi = api(request, await admin(request));
	const created = await adminApi.post('/api/admin/practices', {
		name,
		slug,
		specialty: 'generaliste',
		contactName: 'Dr Test',
		phone: '+21600000099',
		address: '1 rue du Test',
		city: 'Tunis',
		governorate: 'tunis',
		weeklyHours: ALL_DAY,
		practitioners: [
			{ name: 'Amira Ben Salem', title: 'Dr' },
			{ name: 'Karim Jaziri', title: 'Dr' }
		],
		onlineBooking: { enabled: !!options.onlineBooking, autoConfirm: false, minNoticeHours: 0, horizonDays: 30, maxPerDay: 50, blockNoShows: 0 }
	});
	const email = `owner-${tag}@e2e.daftar.test`;
	const accepted = await request.post('/api/invitations/accept', {
		data: { token: created.invitation.token, name: 'Dr Amira Ben Salem', email, password: PASSWORD }
	});
	expect(accepted.status(), await accepted.text()).toBe(201);
	const session = await accepted.json();
	const ownerApi = api(request, session.token);
	const practice = await ownerApi.get('/api/practice');
	return {
		id: created.practice.id,
		slug,
		name,
		token: session.token,
		user: session.user,
		email,
		practitioners: await ownerApi.get('/api/practitioners'),
		services: await ownerApi.get('/api/services'),
		displayToken: practice.displayToken,
		api: ownerApi
	};
}

let phoneSeq = 0;
/** A fake Tunisian number (+216 00 …, the 00 prefix does not exist). */
export function fakePhone(): string {
	const n = (Date.now() % 1_000_000) * 10 + (phoneSeq++ % 10);
	return `+21600${String(n).padStart(6, '0').slice(-6)}`;
}

export async function newPatient(p: Practice, data: Record<string, unknown> = {}): Promise<{ id: number; firstName: string; lastName: string; phone: string }> {
	return p.api.post('/api/patients', { firstName: 'Sami', lastName: `Trabelsi${phoneSeq}`, phone: fakePhone(), lang: 'fr', reminderConsent: true, ...data });
}

/** Wall clock in Tunis (UTC+1, no DST). */
export function tunisNow(): { day: string; minutes: number } {
	const now = new Date(Date.now() + 60 * 60_000);
	return { day: now.toISOString().slice(0, 10), minutes: now.getUTCHours() * 60 + now.getUTCMinutes() };
}

export function addDays(day: string, n: number): string {
	const d = new Date(`${day}T00:00:00Z`);
	d.setUTCDate(d.getUTCDate() + n);
	return d.toISOString().slice(0, 10);
}

export const hhmm = (m: number) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
export const iso = (day: string, time: string) => `${day}T${time}:00+01:00`;

/**
 * A start time `offset` minutes from now on a quarter (today), or tomorrow 10:00 when that would run past the
 * opening hours (late evening runs).
 */
export function slot(offset = 60, duration = 30): { day: string; time: string; startsAt: string } {
	const now = tunisNow();
	const start = Math.ceil((now.minutes + offset) / 15) * 15;
	if (start + duration > 23 * 60 + 59) {
		const day = addDays(now.day, 1);
		return { day, time: '10:00', startsAt: iso(day, '10:00') };
	}
	return { day: now.day, time: hhmm(start), startsAt: iso(now.day, hhmm(start)) };
}

/** The running quarter of today (bookable: the server allows up to 15 minutes in the past). */
export function currentQuarter(): { day: string; time: string; startsAt: string } {
	const now = tunisNow();
	const start = Math.floor(now.minutes / 15) * 15;
	return { day: now.day, time: hhmm(start), startsAt: iso(now.day, hhmm(start)) };
}

/** The browser starts signed in as the owner of `p`, in French. */
export async function signIn(page: Page, p: Practice, lang: 'fr' | 'ar' = 'fr') {
	await page.addInitScript(
		([token, user, l]) => {
			localStorage.setItem('daftar.token', token as string);
			localStorage.setItem('daftar.user', JSON.stringify(user));
			localStorage.setItem('daftar.lang', l as string);
		},
		[p.token, p.user, lang] as const
	);
}

/** Fails on serious or critical accessibility violations. */
export async function axe(page: Page) {
	const result = await new AxeBuilder({ page }).analyze();
	const bad = result.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
	expect(bad.map((v) => `${v.id}: ${v.help} (${v.nodes.map((n) => n.target.join(' ')).join(', ')})`)).toEqual([]);
}

/** Collects console errors and uncaught exceptions (the browser's own failed-request lines excluded by the caller). */
export function watchConsole(page: Page): string[] {
	const problems: string[] = [];
	page.on('console', (msg) => {
		if (msg.type() === 'error') problems.push(msg.text());
	});
	page.on('pageerror', (err) => problems.push(err.message));
	return problems;
}
