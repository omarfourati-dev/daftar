/**
 * `api<T>(path, init)` – the one way to call the backend:
 *
 *   const patients = await api<PatientPage>('/api/patients?q=ben');
 *   const created = await api<Patient>('/api/patients', { method: 'POST', json: { firstName, lastName, phone } });
 *
 * Sends the bearer token, JSON in/out, throws `ApiError {status, code, message}` for problem+json answers.
 * A 401 (except on the login itself) signs out and goes to /connexion. Show errors with `apiErrorMessage(err)` –
 * it translates the problem `code` (dictionary `errors.<code>`) into the current language.
 */
import { goto } from '$app/navigation';
import { auth } from './auth.svelte';
import { t, translate } from './i18n.svelte';

export class ApiError extends Error {
	constructor(
		public status: number,
		message: string,
		public code: string | null = null,
		public body: unknown = null
	) {
		super(message);
	}
}

/** Swappable in tests (see `mockApi` in src/test-utils.ts). */
export const deps = {
	fetch: (...a: Parameters<typeof fetch>) => fetch(...a),
	goto: (url: string, opts?: { replaceState?: boolean }): unknown => goto(url, opts)
};

type Init = RequestInit & { json?: unknown };

export async function api<T>(path: string, init: Init = {}): Promise<T> {
	const res = await request(path, init, 'application/json');
	if (res.status === 204) return undefined as T;
	try {
		return (await res.json()) as T;
	} catch {
		// e.g. the SPA shell answering a path that is not an API route
		throw new ApiError(res.status, t('errors.unexpected'), 'unexpected');
	}
}

/** Binary or text downloads (export, CSV report) with the same auth and error handling. */
export async function apiBlob(path: string, init: Init = {}): Promise<Blob> {
	return (await request(path, init, '*/*')).blob();
}

async function request(path: string, init: Init, accept: string): Promise<Response> {
	const { json, ...rest } = init;
	const headers: Record<string, string> = { Accept: accept, ...(rest.headers as Record<string, string>) };
	const sent = auth.token;
	if (sent) headers.Authorization = `Bearer ${sent}`;
	let body = rest.body;
	if (json !== undefined) {
		headers['Content-Type'] = 'application/json';
		body = JSON.stringify(json);
	}
	let res: Response;
	try {
		res = await deps.fetch(path, { ...rest, headers, body });
	} catch {
		throw new ApiError(0, t('errors.network'), 'network');
	}
	if (res.status === 401 && path !== '/api/auth/login') {
		// a stale tab must not wipe a newer token that another tab stored (e.g. after a password change)
		const stored = auth.stored();
		if (auth.token === sent && (stored === null || stored === sent)) {
			auth.clear();
			void deps.goto('/connexion');
		}
	}
	if (!res.ok) throw await problem(res);
	return res;
}

async function problem(res: Response): Promise<ApiError> {
	try {
		const body = await res.json();
		const code = typeof body?.code === 'string' ? body.code : null;
		const detail = typeof body?.detail === 'string' && body.detail ? body.detail : '';
		return new ApiError(res.status, detail || fallback(res.status), code, body);
	} catch {
		return new ApiError(res.status, fallback(res.status), null); // not JSON, e.g. a proxy error page
	}
}

function fallback(status: number): string {
	return status >= 500 ? t('errors.server') : t('errors.generic');
}

/** A message for the user in the current language: translated `code`, else the server detail, else generic. */
export function apiErrorMessage(err: unknown): string {
	if (err instanceof ApiError) {
		const known = err.code ? translate(`errors.${err.code}`) : undefined;
		if (known) return known;
		if (err.message) return err.message;
		return fallback(err.status);
	}
	return t('errors.generic');
}
