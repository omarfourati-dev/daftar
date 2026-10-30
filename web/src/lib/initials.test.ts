import { describe, expect, it } from 'vitest';
import { initials } from './initials';

describe('initials of a practice (same rule as the app icon, backend daftar/branding.py)', () => {
	it('takes the first and last meaningful word', () => {
		expect(initials('Cabinet Dr Ben Salah')).toBe('BS');
		expect(initials('Kiné Yasmine Haddad')).toBe('KH');
		expect(initials('Cabinet Dentaire du Lac')).toBe('L');
		expect(initials('Centre Médical El Menzah')).toBe('M');
	});

	it('falls back to D (Daftar) without Latin letters', () => {
		expect(initials('عيادة النور')).toBe('D');
		expect(initials('')).toBe('D');
	});
});
