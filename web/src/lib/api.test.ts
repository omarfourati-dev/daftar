import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError, apiErrorMessage, deps } from './api';
import { auth } from './auth.svelte';
import { i18n } from './i18n.svelte';

const res = (status: number, body: unknown, type = 'application/json') =>
	new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { 'Content-Type': type } });
const problem = (status: number, code: string, detail = 'Détail du serveur') =>
	res(status, { type: 'about:blank', title: 'x', status, detail, code }, 'application/problem+json');
const ME = { id: 1, email: 'a@b.tn', name: 'A', role: 'owner', lang: 'fr', practice: null } as const;

describe('api', () => {
	beforeEach(() => {
		auth.clear();
		i18n.setLocale('fr');
		deps.goto = vi.fn();
	});

	it('sends JSON with the bearer token', async () => {
		auth.set('tok', ME);
		deps.fetch = vi.fn(async () => res(200, { ok: true }));
		expect(await api('/api/x', { method: 'POST', json: { a: 1 } })).toEqual({ ok: true });
		const [url, init] = (deps.fetch as any).mock.calls[0];
		expect(url).toBe('/api/x');
		expect(init.headers.Authorization).toBe('Bearer tok');
		expect(init.headers['Content-Type']).toBe('application/json');
		expect(init.headers.Accept).toBe('application/json');
		expect(init.body).toBe('{"a":1}');
	});

	it('a 401 signs out and goes to /connexion', async () => {
		auth.set('tok', ME);
		deps.fetch = vi.fn(async () => problem(401, 'unauthorized'));
		await expect(api('/api/patients')).rejects.toBeInstanceOf(ApiError);
		expect(auth.token).toBeNull();
		expect(deps.goto).toHaveBeenCalledWith('/connexion');
	});

	it('a 401 for a stale token keeps the newer token of another tab', async () => {
		auth.set('old', ME);
		deps.fetch = vi.fn(async () => {
			localStorage.setItem('daftar.token', 'new');
			return problem(401, 'unauthorized');
		});
		await expect(api('/api/patients')).rejects.toBeInstanceOf(ApiError);
		expect(localStorage.getItem('daftar.token')).toBe('new');
		expect(deps.goto).not.toHaveBeenCalled();
	});

	it('a failed login does not redirect', async () => {
		deps.fetch = vi.fn(async () => problem(401, 'invalid_credentials'));
		await expect(api('/api/auth/login', { method: 'POST', json: {} })).rejects.toMatchObject({
			status: 401,
			code: 'invalid_credentials'
		});
		expect(deps.goto).not.toHaveBeenCalled();
	});

	it('keeps status, code and detail of problems; survives non-JSON errors and network failures', async () => {
		deps.fetch = vi.fn(async () => problem(409, 'email_taken', 'Un compte existe déjà.'));
		await expect(api('/api/x')).rejects.toMatchObject({ status: 409, code: 'email_taken', message: 'Un compte existe déjà.' });
		deps.fetch = vi.fn(async () => new Response('<html>Bad Gateway</html>', { status: 502 }));
		await expect(api('/api/x')).rejects.toMatchObject({ status: 502, code: null });
		deps.fetch = vi.fn(async () => {
			throw new TypeError('Failed to fetch');
		});
		await expect(api('/api/x')).rejects.toMatchObject({ status: 0, code: 'network' });
	});

	it('returns undefined for 204 and passes FormData through', async () => {
		deps.fetch = vi.fn(async () => new Response(null, { status: 204 }));
		const form = new FormData();
		expect(await api('/api/imports', { method: 'POST', body: form })).toBeUndefined();
		const [, init] = (deps.fetch as any).mock.calls[0];
		expect(init.headers['Content-Type']).toBeUndefined();
		expect(init.body).toBe(form);
	});

	it('turns a non-JSON 2xx body (the SPA shell) into an error', async () => {
		deps.fetch = vi.fn(async () => new Response('<!doctype html>', { status: 200 }));
		await expect(api('/api/unknown')).rejects.toMatchObject({ status: 200, code: 'unexpected' });
	});
});

describe('apiErrorMessage', () => {
	beforeEach(() => i18n.setLocale('fr'));

	it('translates known codes in the current language', () => {
		const err = new ApiError(401, 'E-mail ou mot de passe incorrect.', 'invalid_credentials');
		expect(apiErrorMessage(err)).toBe('E-mail ou mot de passe incorrect.');
		i18n.setLocale('ar');
		expect(apiErrorMessage(err)).toBe('البريد الإلكتروني أو كلمة المرور غير صحيحة.');
	});

	it('falls back to the server detail, then to a generic text', () => {
		expect(apiErrorMessage(new ApiError(422, 'Nom trop long.', 'some_new_code'))).toBe('Nom trop long.');
		expect(apiErrorMessage(new ApiError(503, '', null))).toBe(
			'Le serveur ne répond pas pour le moment. Veuillez réessayer dans un instant.'
		);
		expect(apiErrorMessage(new ApiError(0, '', 'network'))).toBe(
			'Pas de connexion au serveur. Vérifiez votre connexion internet.'
		);
		expect(apiErrorMessage(new Error('boom'))).toBe('Cela n’a pas fonctionné.');
	});
});
