import { describe, expect, it } from 'vitest';
import { bookingDays } from './booking';

describe('bookingDays – the horizon in days from today (code review N9)', () => {
	it('offers today and the next `horizon` days – the last one the server still accepts', () => {
		const days = bookingDays('2026-10-30', 3);
		expect(days).toEqual(['2026-10-30', '2026-10-31', '2026-11-01', '2026-11-02']);
		expect(bookingDays('2026-10-30', 30)).toHaveLength(31);
		expect(bookingDays('2026-10-30', 30).at(-1)).toBe('2026-11-29');
	});

	it('stays sensible for odd values', () => {
		expect(bookingDays('2026-10-30', 0)).toEqual(['2026-10-30']);
		expect(bookingDays('2026-10-30', 1000)).toHaveLength(366);
	});
});
