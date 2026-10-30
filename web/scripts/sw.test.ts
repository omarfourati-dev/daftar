// @vitest-environment node
import { readFileSync } from 'node:fs';
import { describe, expect, it, vi } from 'vitest';

/**
 * static/sw.js in a fake worker scope. The app runs on app.<base> and on the practice sub-domains; the main domain
 * (landing with Google AdSense) must never be served by the worker – old registrations there remove themselves.
 */
const SOURCE = readFileSync(new URL('../static/sw.js', import.meta.url), 'utf8');

function worker(hostname: string) {
	const listeners: Record<string, (event: any) => void> = {};
	const self = {
		location: new URL(`https://${hostname}/sw.js`),
		addEventListener: (type: string, fn: (event: any) => void) => (listeners[type] = fn),
		skipWaiting: vi.fn(),
		clients: { claim: vi.fn(async () => undefined) },
		registration: { unregister: vi.fn(async () => true) }
	};
	const cache = { addAll: vi.fn(async () => undefined), put: vi.fn(), match: vi.fn() };
	const caches = {
		open: vi.fn(async () => cache),
		keys: vi.fn(async () => ['daftar-shell-old', 'autre']),
		delete: vi.fn(async () => true)
	};
	const network = vi.fn(async () => new Response('<!doctype html>', { headers: { 'Content-Type': 'text/html' } }));
	new Function('self', 'caches', 'fetch', SOURCE)(self, caches, network);

	async function lifecycle(type: 'install' | 'activate') {
		let done: Promise<unknown> = Promise.resolve();
		listeners[type]({ waitUntil: (p: Promise<unknown>) => (done = p) });
		await done;
	}
	function intercepts(path: string, mode = 'navigate'): boolean {
		const respondWith = vi.fn();
		listeners.fetch({ request: { method: 'GET', url: `https://${hostname}${path}`, mode }, respondWith });
		return respondWith.mock.calls.length > 0;
	}
	return { self, caches, lifecycle, intercepts };
}

describe('service worker on the main domain', () => {
	for (const host of ['daftar.omarfourati.de', 'localhost']) {
		it(`${host}: intercepts nothing`, () => {
			const sw = worker(host);
			for (const path of ['/', '/ar/', '/connexion', '/app', '/app/agenda', '/r/cabinet-lac']) expect(sw.intercepts(path), path).toBe(false);
			expect(sw.intercepts('/_app/immutable/entry/start.js', 'cors')).toBe(false);
			expect(sw.intercepts('/icons/icon-192.png', 'no-cors')).toBe(false);
		});

		it(`${host}: caches nothing and removes itself`, async () => {
			const sw = worker(host);
			await sw.lifecycle('install');
			expect(sw.caches.open).not.toHaveBeenCalled();
			expect(sw.self.skipWaiting).toHaveBeenCalled();
			await sw.lifecycle('activate');
			expect(sw.caches.delete).toHaveBeenCalledWith('daftar-shell-old');
			expect(sw.caches.delete).not.toHaveBeenCalledWith('autre');
			expect(sw.self.registration.unregister).toHaveBeenCalled();
		});
	}
});

describe('service worker of the app', () => {
	it('app host: app routes, shell cache, but "/" goes to the server (it redirects to /app)', async () => {
		const sw = worker('app.daftar.omarfourati.de');
		for (const path of ['/app', '/app/agenda', '/connexion', '/invitation', '/reinitialiser', '/r/cabinet-lac']) {
			expect(sw.intercepts(path), path).toBe(true);
		}
		expect(sw.intercepts('/')).toBe(false);
		expect(sw.intercepts('/api/auth/me', 'cors')).toBe(false);
		expect(sw.intercepts('/_app/immutable/entry/start.js', 'cors')).toBe(true);
		await sw.lifecycle('install');
		expect(sw.caches.open).toHaveBeenCalled();
		await sw.lifecycle('activate');
		expect(sw.self.registration.unregister).not.toHaveBeenCalled();
	});

	it('practice sub-domain: "/" is the booking page', () => {
		for (const host of ['cabinet-lac.daftar.omarfourati.de', 'cabinet-lac.localhost']) {
			const sw = worker(host);
			expect(sw.intercepts('/'), host).toBe(true);
			expect(sw.intercepts('/rdv/abc123'), host).toBe(true);
			expect(sw.intercepts('/api/public/practices/cabinet-lac', 'cors'), host).toBe(false);
		}
	});
});
