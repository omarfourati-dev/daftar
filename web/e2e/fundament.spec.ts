import { expect, test, type Page } from '@playwright/test';

/**
 * What the foundation can do, end to end against the real stack (backend + built SPA + Postgres).
 * The app lives on its own origin app.<BASE_DOMAIN> (fixlist 1); E2E_BASE_URL is the main domain (landing only).
 * Browsers resolve app.localhost; Node on Windows does not (getaddrinfo ENOTFOUND) → API requests from Node go to
 * BASE with the app's Host header.
 */

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? 'admin@daftar.test';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'local-admin-password-123';
const BASE = process.env.E2E_BASE_URL ?? 'http://localhost:18083';
const APP_HOST = `app.${new URL(BASE).host}`;
const APP = `${new URL(BASE).protocol}//${APP_HOST}`;
const ON_APP = { headers: { host: APP_HOST } };

/** Fails the test on any console error or uncaught exception of the page. */
function watchConsole(page: Page): string[] {
	const problems: string[] = [];
	page.on('console', (msg) => {
		if (msg.type() === 'error') problems.push(msg.text());
	});
	page.on('pageerror', (err) => problems.push(err.message));
	return problems;
}

async function signIn(page: Page, email = ADMIN_EMAIL, password = ADMIN_PASSWORD) {
	await page.goto(APP + '/connexion');
	await page.getByLabel('E-mail').fill(email);
	await page.getByLabel('Mot de passe').fill(password);
	await page.getByRole('button', { name: 'Se connecter' }).click();
}

test('/connexion loads in French and switches to Arabic (right to left)', async ({ page }) => {
	const problems = watchConsole(page);
	await page.goto(APP + '/connexion');
	await expect(page.getByRole('heading', { name: 'Connexion' })).toBeVisible();
	await expect(page.locator('html')).toHaveAttribute('lang', 'fr');
	await expect(page.locator('html')).toHaveAttribute('dir', 'ltr');
	await page.getByRole('button', { name: 'العربية' }).click();
	await expect(page.getByRole('heading', { name: 'تسجيل الدخول' })).toBeVisible();
	await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
	await expect(page.locator('html')).toHaveAttribute('lang', 'ar');
	await page.reload(); // the choice is remembered
	await expect(page.getByRole('heading', { name: 'تسجيل الدخول' })).toBeVisible();
	await page.getByRole('button', { name: 'Français' }).click();
	await expect(page.getByRole('heading', { name: 'Connexion' })).toBeVisible();
	expect(problems).toEqual([]);
});

test('/connexion?lang=ar on the main domain opens the app host in Arabic', async ({ page }) => {
	await page.goto('/connexion?lang=ar');
	await expect(page).toHaveURL(`${APP}/connexion?lang=ar`);
	await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
	await page.getByRole('button', { name: 'Français' }).click();
});

test('a wrong password shows an error', async ({ page }) => {
	const problems = watchConsole(page);
	await signIn(page, ADMIN_EMAIL, 'certainement-pas-le-bon');
	await expect(page.getByRole('alert')).toHaveText('E-mail ou mot de passe incorrect.');
	await expect(page).toHaveURL(/\/connexion$/);
	// the browser logs the failed request itself; everything else must be clean
	expect(problems.filter((p) => !p.includes('401'))).toEqual([]);
});

test('the admin signs in, lands in the app (administration) and signs out', async ({ page }) => {
	const problems = watchConsole(page);
	await signIn(page);
	await expect(page).toHaveURL(/\/app\/admin$/);
	await expect(page.getByRole('heading', { level: 1, name: 'Administration' })).toBeVisible();
	const nav = page.getByRole('navigation', { name: 'Navigation principale' });
	await expect(nav.getByRole('link', { name: 'Administration' })).toHaveAttribute('aria-current', 'page');
	await page.reload(); // the session survives a reload
	await expect(page.getByRole('heading', { level: 1, name: 'Administration' })).toBeVisible();

	await page.getByRole('button', { name: 'Se déconnecter' }).click();
	await expect(page).toHaveURL(/\/connexion$/);
	await page.goto(APP + '/app/agenda');
	await expect(page).toHaveURL(/\/connexion$/); // the guard keeps signed-out visitors out
	expect(problems).toEqual([]);
});

test('/invitation with an unknown token explains the problem', async ({ page }) => {
	await page.goto(APP + '/invitation#ceci-n-est-pas-une-invitation');
	await expect(page.getByRole('alert')).toHaveText('Cette invitation n’est pas valide, a expiré ou a déjà été utilisée.');
	await page.getByRole('link', { name: 'Aller à la connexion' }).click();
	await expect(page).toHaveURL(/\/connexion$/);
});

test('/invitation without a token does not ask the server', async ({ page }) => {
	const requests: string[] = [];
	page.on('request', (r) => requests.push(new URL(r.url()).pathname));
	await page.goto(APP + '/invitation');
	await expect(page.getByRole('alert')).toContainText('Ce lien est incomplet.');
	expect(requests.filter((p) => p.startsWith('/api'))).toEqual([]);
});

test('security headers and CSP on the app and the API', async ({ request }) => {
	for (const path of ['/connexion', '/healthz', '/api/auth/me']) {
		const res = await request.get(path, ON_APP);
		const h = res.headers();
		expect(h['x-content-type-options'], path).toBe('nosniff');
		expect(h['referrer-policy'], path).toBe('strict-origin-when-cross-origin');
		expect(h['permissions-policy'], path).toBe('camera=(), microphone=(), geolocation=()');
		const csp = h['content-security-policy'];
		expect(csp, path).toContain("default-src 'self'");
		expect(csp, path).toContain("frame-ancestors 'none'");
		expect(csp, path).toMatch(/script-src 'self' 'sha256-[A-Za-z0-9+/=]+'/); // the SPA bootstrap script, nothing else
		expect(csp, path).not.toContain('http');
		expect(h['strict-transport-security'], path).toBeUndefined(); // HSTS only over HTTPS (behind Caddy)
	}
	expect((await request.get('/connexion', ON_APP)).headers()['cache-control']).toBe('no-cache');
});

test('the main domain keeps only the landing: app paths move to the app host with 301', async ({ request }) => {
	for (const path of ['/connexion?lang=ar', '/app/demo', '/invitation', '/r/cabinet-test']) {
		const res = await request.get(path, { maxRedirects: 0 });
		expect(res.status(), path).toBe(301);
		expect(res.headers()['location'], path).toBe(`${APP}${path}`);
	}
	expect((await request.get('/200.html', { maxRedirects: 0 })).status()).toBe(404);
	const home = await request.get('/', { maxRedirects: 0 });
	expect(home.status()).toBe(200);
	expect(await home.text()).not.toContain('__sveltekit');
	const appRoot = await request.get('/', { ...ON_APP, maxRedirects: 0 });
	expect([appRoot.status(), appRoot.headers()['location']]).toEqual([302, '/app']);
	expect((await request.get(`/api/public/tls-check?domain=${new URL(APP).hostname}`)).status()).toBe(200);
});

test('nobody signs in on the main domain, the admin does on the app host', async ({ request }) => {
	const data = { email: ADMIN_EMAIL, password: ADMIN_PASSWORD };
	const main = await request.post('/api/auth/login', { data });
	expect(main.status()).toBe(401);
	expect(await main.json()).toMatchObject({ code: 'invalid_credentials' });
	const app = await request.post('/api/auth/login', { data, ...ON_APP });
	expect(app.status()).toBe(200);
	expect((await app.json()).user.role).toBe('admin');
});

test('health, metrics and unknown API paths', async ({ request }) => {
	const health = await request.get('/healthz');
	expect(health.status()).toBe(200);
	expect(await health.json()).toEqual({ status: 'ok' });

	const metrics = await (await request.get('/metrics')).text();
	expect(metrics).toContain('daftar_logins_total{result="ok"}');
	expect(metrics).toContain('daftar_practices{kind="pilot"}');
	expect(metrics).toContain('daftar_http_requests_total');

	const missing = await request.get('/api/x');
	expect(missing.status()).toBe(404);
	expect(missing.headers()['content-type']).toContain('application/problem+json');
	expect(await missing.json()).toMatchObject({ status: 404, code: 'not_found' });
	expect((await request.get('/api/auth/me')).status()).toBe(401);
});

test('installable app: manifest, icons and a stamped service worker that never caches the API', async ({ page, request }) => {
	const manifest = await (await request.get('/manifest.webmanifest', ON_APP)).json();
	expect(manifest).toMatchObject({
		name: 'Daftar – agenda du cabinet médical',
		short_name: 'Daftar',
		start_url: '/app',
		scope: '/',
		display: 'standalone',
		theme_color: '#0f766e'
	});
	for (const icon of manifest.icons as { src: string }[]) expect((await request.get(icon.src, ON_APP)).ok(), icon.src).toBeTruthy();
	const sw = await request.get('/sw.js', ON_APP);
	expect(sw.headers()['cache-control']).toBe('no-cache');
	expect(await sw.text()).not.toContain('__BUILD__');

	await signIn(page);
	await expect(page.getByRole('heading', { level: 1, name: 'Administration' })).toBeVisible();
	await page.evaluate(async () => navigator.serviceWorker.ready);
	const cached = await page.evaluate(async () => {
		const paths: string[] = [];
		for (const name of await caches.keys()) for (const r of await (await caches.open(name)).keys()) paths.push(new URL(r.url).pathname);
		return paths;
	});
	expect(cached).toContain('/200.html');
	expect(cached.filter((p) => p.startsWith('/api'))).toEqual([]);
	expect(page.url().startsWith(APP + '/')).toBeTruthy(); // the token lives on the app's origin only
	expect(await page.evaluate(() => navigator.serviceWorker.controller?.scriptURL)).toBe(`${APP}/sw.js`);
});

test('the main domain stores no token and runs no service worker', async ({ page }) => {
	await page.route((url) => !url.origin.startsWith(new URL(BASE).origin), (route) => route.abort('blockedbyclient'));
	await page.goto('/');
	await page.waitForLoadState('networkidle');
	expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([]);
	expect(await page.evaluate(async () => (await navigator.serviceWorker.getRegistrations()).length)).toBe(0);
});

test('an unknown practice sub-domain is 404', async ({ request }) => {
	const url = new URL(BASE);
	test.skip(url.hostname !== 'localhost', 'needs BASE_DOMAIN=localhost (docker-compose.yml)');
	// Host header instead of DNS: Node on Windows does not resolve *.localhost (getaddrinfo ENOTFOUND)
	const res = await request.get('/app', { headers: { host: `inconnu.localhost:${url.port}` } });
	expect(res.status()).toBe(404);
	const tls = await request.get('/api/public/tls-check?domain=inconnu.localhost');
	expect(tls.status()).toBe(404);
});
