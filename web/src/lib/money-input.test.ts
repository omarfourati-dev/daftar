import { describe, expect, it } from 'vitest';
import { dinarsText, parseDinars } from './money-input';

describe('amounts typed in dinars', () => {
	it('reads dinars with comma or point into millimes', () => {
		expect(parseDinars('35')).toBe(35000);
		expect(parseDinars('35,5')).toBe(35500);
		expect(parseDinars(' 12.250 ')).toBe(12250);
		expect(parseDinars('1 250')).toBe(1250000);
		expect(parseDinars('0')).toBe(0);
	});

	it('gives null for an empty field and NaN for nonsense', () => {
		expect(parseDinars('')).toBeNull();
		expect(parseDinars('  ')).toBeNull();
		expect(parseDinars('abc')).toBeNaN();
		expect(parseDinars('-5')).toBeNaN();
		expect(parseDinars('1,2345')).toBeNaN(); // below one millime
	});

	it('writes millimes back as an editable dinar text', () => {
		expect(dinarsText(35000)).toBe('35');
		expect(dinarsText(35500)).toBe('35,5');
		expect(dinarsText(12250)).toBe('12,25');
		expect(dinarsText(null)).toBe('');
	});
});
