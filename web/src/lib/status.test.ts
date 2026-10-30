import { describe, expect, it } from 'vitest';
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
