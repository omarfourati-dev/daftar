import { describe, expect, it } from 'vitest';
import { slugProblem, suggestSlug } from './slug';

describe('practice slugs (mirror of backend daftar/slugs.py)', () => {
	it('accepts 3–40 lower-case letters, digits and inner hyphens', () => {
		expect(slugProblem('cabinet-lac')).toBeNull();
		expect(slugProblem('ab1')).toBeNull();
		expect(slugProblem('a'.repeat(40))).toBeNull();
	});

	it('rejects bad formats and reserved names', () => {
		expect(slugProblem('ab')).toBe('invalid');
		expect(slugProblem('a'.repeat(41))).toBe('invalid');
		expect(slugProblem('-lac')).toBe('invalid');
		expect(slugProblem('Cabinet')).toBe('invalid');
		expect(slugProblem('cab inet')).toBe('invalid');
		expect(slugProblem('admin')).toBe('reserved');
		expect(slugProblem('www')).toBe('reserved');
	});

	it('suggests a slug from the practice name', () => {
		expect(suggestSlug('Cabinet Dr Ben Salah')).toBe('cabinet-dr-ben-salah');
		expect(suggestSlug('Cabinet Médical Él-Ménzah 6')).toBe('cabinet-medical-el-menzah-6');
		expect(suggestSlug('عيادة')).toBe('cabinet');
		expect(suggestSlug('Admin')).toBe('admin-cabinet');
		expect(suggestSlug('Cabinet de kinésithérapie et de rééducation fonctionnelle')).toBe('cabinet-de-kinesitherapie-et-de');
	});
});
