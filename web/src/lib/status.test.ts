import { describe, expect, it } from 'vitest';
import { ar } from './i18n/ar';
import { fr } from './i18n/fr';
import { APPOINTMENT_STATUSES, appointmentStatusClass } from './status';

describe('appointment status colours (design section 6)', () => {
	it('has a colour for every status', () => {
		expect(APPOINTMENT_STATUSES).toEqual([
			'requested', 'scheduled', 'confirmed', 'arrived', 'in_treatment', 'done', 'no_show', 'cancelled'
		]);
		for (const s of APPOINTMENT_STATUSES) expect(appointmentStatusClass(s)).toMatch(/bg-/);
	});

	it.each([
		['scheduled', 'slate'],
		['confirmed', 'sky'],
		['arrived', 'amber'],
		['in_treatment', 'violet'],
		['done', 'emerald'],
		['no_show', 'rose'],
		['cancelled', 'zinc']
	] as const)('%s is %s', (status, colour) => {
		expect(appointmentStatusClass(status)).toContain(colour);
	});

	it('strikes cancelled appointments through and dashes online requests', () => {
		expect(appointmentStatusClass('cancelled')).toContain('line-through');
		expect(appointmentStatusClass('requested')).toContain('border-dashed');
	});
});

describe('the word for in_treatment (fixlist 2)', () => {
	/** Every text under a key `in_treatment`, anywhere in the messages of a language. */
	function inTreatment(messages: unknown, found: string[] = []): string[] {
		if (messages && typeof messages === 'object') {
			for (const [key, value] of Object.entries(messages)) {
				if (key === 'in_treatment' && typeof value === 'string') found.push(value);
				else inTreatment(value, found);
			}
		}
		return found;
	}

	it('is "En consultation" in French and "في الفحص" in Arabic, on every screen', () => {
		expect(fr.appointmentStatus.in_treatment).toBe('En consultation');
		expect(fr.queueStatus.in_treatment).toBe('En consultation');
		expect(ar.appointmentStatus.in_treatment).toBe('في الفحص');
		expect(ar.queueStatus.in_treatment).toBe('في الفحص');
		const french = inTreatment(fr);
		const arabic = inTreatment(ar);
		expect(french.length).toBeGreaterThan(4);
		for (const text of french) expect(text, text).toMatch(/consultation/i);
		for (const text of arabic) expect(text, text).toContain('في الفحص');
	});
});
