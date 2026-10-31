/**
 * Helpers for component and route tests (never imported by app code).
 *
 *   mockApi({
 *     'POST /api/auth/login': () => json(200, session),
 *     '/api/auth/me': () => json(200, me),                  // any method
 *     'GET /api/patients?q=ben': () => json(200, page),
 *     'POST /api/invitations/accept': () => problem(409, 'email_taken'),
 *   });
 *   ...
 *   expect(sentJson('POST /api/invitations/accept')).toEqual({ token: 'x', ... });
 *
 * An unexpected call throws (the test fails with the URL), so every request of a page is explicit.
 */
import { vi } from 'vitest';
import { deps } from './api';

export type Handler = (init: RequestInit | undefined, url: string) => Response | Promise<Response>;

export function json(status: number, body: unknown): Response {
	return new Response(body === undefined ? null : JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

export function problem(status: number, code: string, detail = ''): Response {
	return new Response(JSON.stringify({ type: 'about:blank', title: 'Error', status, detail, code }), {
		status,
		headers: { 'Content-Type': 'application/problem+json' }
	});
}

export function noContent(): Response {
	return new Response(null, { status: 204 });
}

/** Replaces `deps.fetch` (and `deps.goto` with a spy) for the current test. */
export function mockApi(handlers: Record<string, Handler>) {
	const fetch = vi.fn(async (url: string, init?: RequestInit) => {
		const method = (init?.method ?? 'GET').toUpperCase();
		const handler = handlers[`${method} ${url}`] ?? handlers[url];
		if (!handler) throw new Error(`unexpected request: ${method} ${url}`);
		return handler(init, url);
	});
	deps.fetch = fetch as unknown as typeof deps.fetch;
	deps.goto = vi.fn();
	return fetch;
}

/** The calls made so far as `"METHOD /url"`. */
export function calls(): string[] {
	const fetch = deps.fetch as unknown as ReturnType<typeof vi.fn>;
	return fetch.mock.calls.map(([url, init]) => `${((init as RequestInit | undefined)?.method ?? 'GET').toUpperCase()} ${url}`);
}

/** The parsed JSON body of the first call to `"METHOD /url"`. */
export function sentJson(key: string): unknown {
	const fetch = deps.fetch as unknown as ReturnType<typeof vi.fn>;
	const call = fetch.mock.calls.find(
		([url, init]) => `${((init as RequestInit | undefined)?.method ?? 'GET').toUpperCase()} ${url}` === key
	);
	if (!call) throw new Error(`no request ${key}; made: ${calls().join(', ')}`);
	return JSON.parse((call[1] as RequestInit).body as string);
}

const normalized = (text: string | null | undefined) => (text ?? '').replace(/\s+/g, ' ').trim().toLowerCase();

/**
 * WCAG 2.5.3 "label in name" (axe `label-content-name-mismatch`, stricter): every button or link with an `aria-label`
 * must start its accessible name with its visible text, so "click <what I see>" works with voice control. Parts
 * hidden from sight or from screen readers (`aria-hidden`, `sr-only`) are not visible text. Returns the mismatches as
 * `"visible" → "name"`; expect `[]`.
 */
export function labelInNameProblems(root: ParentNode = document.body): string[] {
	const problems: string[] = [];
	for (const element of root.querySelectorAll<HTMLElement>('button[aria-label], a[aria-label]')) {
		const copy = element.cloneNode(true) as HTMLElement;
		copy.querySelectorAll('[aria-hidden="true"], .sr-only').forEach((node) => node.remove());
		const visible = normalized(copy.textContent);
		const name = normalized(element.getAttribute('aria-label'));
		if (visible && !name.startsWith(visible)) problems.push(`"${visible}" → "${name}"`);
	}
	return problems;
}
