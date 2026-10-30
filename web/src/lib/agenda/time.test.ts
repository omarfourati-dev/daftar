import { describe, expect, it } from 'vitest';
import {
	agendaRange,
	closureOn,
	hhmm,
	isoWeekday,
	layoutLanes,
	minutesOfDay,
	parseHHMM,
	roundUp,
	tunisDayOf,
	weekDays,
	weekStart,
	windowsOn
} from './time';

const HOURS = {
	'1': [['08:00', '12:30'], ['14:00', '18:00']],
	'2': [['08:00', '12:30'], ['14:00', '18:00']],
	'3': [['08:00', '12:30']],
	'4': [['08:00', '12:30'], ['14:00', '18:00']],
	'5': [['08:00', '12:00'], ['14:30', '18:00']],
	'6': [['09:00', '13:00']],
	'7': []
} as Record<string, [string, string][]>;

describe('agenda time helpers (Africa/Tunis, UTC+1 all year)', () => {
	it('reads the wall-clock minutes and the day of an instant in Tunis', () => {
		expect(minutesOfDay('2026-10-30T09:30:00+01:00')).toBe(570);
		expect(minutesOfDay('2026-10-30T08:30:00Z')).toBe(570);
		expect(minutesOfDay('2026-10-30T23:15:00Z')).toBe(15); // 00:15 the next day in Tunis
		expect(tunisDayOf('2026-10-30T23:15:00Z')).toBe('2026-10-31');
		expect(tunisDayOf('2026-10-30T09:30:00+01:00')).toBe('2026-10-30');
	});

	it('converts between HH:MM and minutes', () => {
		expect(parseHHMM('08:30')).toBe(510);
		expect(parseHHMM('8:05')).toBe(485);
		expect(hhmm(510)).toBe('08:30');
		expect(hhmm(1439)).toBe('23:59');
		expect(roundUp(512, 15)).toBe(525);
		expect(roundUp(525, 15)).toBe(525);
	});

	it('knows ISO weekdays and weeks starting on Monday', () => {
		expect(isoWeekday('2026-10-30')).toBe(5); // Friday
		expect(isoWeekday('2026-11-01')).toBe(7); // Sunday
		expect(weekStart('2026-10-30')).toBe('2026-10-26');
		expect(weekStart('2026-11-01')).toBe('2026-10-26');
		expect(weekStart('2026-10-26')).toBe('2026-10-26');
		expect(weekDays('2026-10-30')).toEqual([
			'2026-10-26',
			'2026-10-27',
			'2026-10-28',
			'2026-10-29',
			'2026-10-30',
			'2026-10-31',
			'2026-11-01'
		]);
	});

	it('gives the opening windows of a day and the agenda range of the week', () => {
		expect(windowsOn(HOURS, '2026-10-30')).toEqual([
			[480, 720],
			[870, 1080]
		]);
		expect(windowsOn(HOURS, '2026-11-01')).toEqual([]);
		expect(windowsOn(undefined, '2026-10-30')).toEqual([]);
		expect(agendaRange(HOURS)).toEqual({ start: 480, end: 1080 });
		// no hours at all: a sensible default day
		expect(agendaRange({})).toEqual({ start: 480, end: 1080 });
		expect(agendaRange(undefined)).toEqual({ start: 480, end: 1080 });
	});

	it('finds the closure covering a day', () => {
		const closures = [
			{ id: 1, startsOn: '2026-11-02', endsOn: '2026-11-06', label: 'Congés' },
			{ id: 2, startsOn: '2026-12-25', endsOn: '2026-12-25', label: '' }
		];
		expect(closureOn(closures, '2026-11-02')?.id).toBe(1);
		expect(closureOn(closures, '2026-11-06')?.id).toBe(1);
		expect(closureOn(closures, '2026-11-07')).toBeNull();
		expect(closureOn(closures, '2026-12-25')?.id).toBe(2);
	});

	it('puts overlapping appointments side by side and the others full width', () => {
		const lanes = layoutLanes([
			{ id: 1, start: 540, end: 570 },
			{ id: 2, start: 555, end: 600 },
			{ id: 3, start: 600, end: 630 },
			{ id: 4, start: 560, end: 580 }
		]);
		expect(lanes.get(1)).toEqual({ lane: 0, lanes: 3 });
		expect(lanes.get(2)).toEqual({ lane: 1, lanes: 3 });
		expect(lanes.get(4)).toEqual({ lane: 2, lanes: 3 });
		expect(lanes.get(3)).toEqual({ lane: 0, lanes: 1 });
	});
});
