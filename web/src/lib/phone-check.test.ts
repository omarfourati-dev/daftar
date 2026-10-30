import { describe, expect, it } from 'vitest';
import { formatPhone, looksLikePhone } from './phone-check';

describe('phone numbers typed by people', () => {
	it('accepts Tunisian numbers in the usual spellings', () => {
		for (const raw of ['20 123 456', '20123456', '+216 20 123 456', '0021620123456', '+21620123456', '98-123-456']) {
			expect(looksLikePhone(raw), raw).toBe(true);
		}
	});

	it('accepts foreign numbers only with + or 00', () => {
		expect(looksLikePhone('+33 6 12 34 56 78')).toBe(true);
		expect(looksLikePhone('0033612345678')).toBe(true);
		expect(looksLikePhone('0612345678')).toBe(false);
	});

	it('rejects too short, letters and empty', () => {
		for (const raw of ['', '123', '20 12', 'abc', '+216 2012']) expect(looksLikePhone(raw), raw).toBe(false);
	});
});

describe('phone numbers shown to people', () => {
	it('groups Tunisian numbers as 2-3-3 after +216', () => {
		expect(formatPhone('+21671123456')).toBe('+216 71 123 456');
		expect(formatPhone('+216 20123456')).toBe('+216 20 123 456');
	});

	it('leaves other numbers as they are', () => {
		expect(formatPhone('+33612345678')).toBe('+33612345678');
		expect(formatPhone('')).toBe('');
	});
});
