import { afterEach, describe, expect, it, vi } from 'vitest';
import { Badges } from './badges.svelte';
import { auth } from './auth.svelte';
import { json, mockApi, problem } from './test-utils';
import { assistant } from './agenda/fixtures';

describe('badges in the navigation (GET /api/badges every 60 s)', () => {
	afterEach(() => vi.useRealTimers());

	it('loads the counts and sums what is waiting to be handled', async () => {
		auth.set('tok', assistant);
		mockApi({ 'GET /api/badges': () => json(200, { onlineRequests: 2, overdue: 1 }) });
		const badges = new Badges();
		await badges.refresh();
		expect(badges.onlineRequests).toBe(2);
		expect(badges.overdue).toBe(1);
		expect(badges.total).toBe(3);
	});

	it('counts the products to order apart: they belong to "Stock", not to "Aujourd’hui"', async () => {
		mockApi({ 'GET /api/badges': () => json(200, { onlineRequests: 1, overdue: 0, stockToOrder: 4, hygiene: 3 }) });
		const badges = new Badges();
		await badges.refresh();
		expect(badges.stockToOrder).toBe(4);
		expect(badges.hygiene).toBe(3);
		expect(badges.total).toBe(1);
		mockApi({ 'GET /api/badges': () => json(200, { onlineRequests: 0, overdue: 0 }) }); // an older server
		await badges.refresh();
		expect(badges.stockToOrder).toBe(0);
		expect(badges.hygiene).toBe(0);
	});

	it('keeps the last counts when the server does not answer', async () => {
		let fail = false;
		mockApi({ 'GET /api/badges': () => (fail ? problem(500, 'server_error') : json(200, { onlineRequests: 4, overdue: 0 })) });
		const badges = new Badges();
		await badges.refresh();
		fail = true;
		await badges.refresh();
		expect(badges.total).toBe(4);
	});

	it('polls every minute until stopped', async () => {
		vi.useFakeTimers();
		const fetch = mockApi({ 'GET /api/badges': () => json(200, { onlineRequests: 0, overdue: 0 }) });
		const badges = new Badges();
		badges.start();
		badges.start(); // a second start does not double the polling
		await vi.advanceTimersByTimeAsync(0);
		expect(fetch).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(60_000);
		expect(fetch).toHaveBeenCalledTimes(2);
		badges.stop();
		await vi.advanceTimersByTimeAsync(120_000);
		expect(fetch).toHaveBeenCalledTimes(2);
	});
});
