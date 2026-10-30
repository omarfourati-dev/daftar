import { beforeEach, describe, expect, it, vi } from 'vitest';
import { deps } from './api';
import { loadPublicPractice, practiceSlugFromHost } from './host';

describe('practiceSlugFromHost', () => {
	it.each([
		['cabinet-lac.daftar.omarfourati.de', 'cabinet-lac'],
		['CABINET-LAC.daftar.omarfourati.de', 'cabinet-lac'],
		['cabinet-lac.localhost', 'cabinet-lac'],
		['daftar.omarfourati.de', null],
		['localhost', null],
		['127.0.0.1', null],
		['a.b.daftar.omarfourati.de', null],
		['www.daftar.omarfourati.de', null],
		['evil-daftar.omarfourati.de', null],
		['cabinet-lac.example.com', null]
	])('%s → %s', (host, slug) => {
		expect(practiceSlugFromHost(host)).toBe(slug);
	});

	it('accepts another base domain', () => {
		expect(practiceSlugFromHost('dr-amira.rdv.example.tn', ['rdv.example.tn'])).toBe('dr-amira');
	});
});

describe('loadPublicPractice', () => {
	beforeEach(() => {
		deps.goto = vi.fn();
	});

	it('returns the public profile', async () => {
		deps.fetch = vi.fn(
			async () =>
				new Response(JSON.stringify({ name: 'Cabinet du Lac', nameAr: 'عيادة البحيرة', brandColor: '#1d4ed8' }), {
					status: 200,
					headers: { 'Content-Type': 'application/json' }
				})
		);
		expect(await loadPublicPractice('cabinet-lac')).toMatchObject({ name: 'Cabinet du Lac', brandColor: '#1d4ed8' });
		expect((deps.fetch as any).mock.calls[0][0]).toBe('/api/public/practices/cabinet-lac');
	});

	it('falls back to null while the endpoint does not exist or fails', async () => {
		deps.fetch = vi.fn(async () => new Response(JSON.stringify({ status: 404 }), { status: 404 }));
		expect(await loadPublicPractice('cabinet-lac')).toBeNull();
		deps.fetch = vi.fn(async () => {
			throw new TypeError('offline');
		});
		expect(await loadPublicPractice('cabinet-lac')).toBeNull();
	});
});
