/** The current time, swappable in tests (`clock.now = () => new Date('2026-10-30T10:10:00+01:00')`). */
export const clock = {
	now: (): Date => new Date()
};
