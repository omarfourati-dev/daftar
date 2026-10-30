import { describe, expect, it } from 'vitest';
import {
	WEEKDAYS,
	copyDay,
	defaultWeeklyHours,
	emptyWeeklyHours,
	hoursProblems,
	hoursSummary,
	isOpenOn,
	normalizeWeeklyHours,
	weekdayOf
} from './hours';

describe('opening hours', () => {
	it('starts with Monday to Saturday 08:00–12:30 and 14:00–18:00, Sunday closed (like the backend)', () => {
		const h = defaultWeeklyHours();
		expect(WEEKDAYS).toEqual(['1', '2', '3', '4', '5', '6', '7']);
		expect(h['1']).toEqual([
			['08:00', '12:30'],
			['14:00', '18:00']
		]);
		expect(h['6']).toEqual(h['1']);
		expect(h['7']).toEqual([]);
		h['1'][0][0] = '09:00';
		expect(defaultWeeklyHours()['1'][0][0]).toBe('08:00'); // a fresh copy each time
	});

	it('fills missing days and sorts the windows of a day', () => {
		expect(normalizeWeeklyHours({ '2': [['14:00', '18:00'], ['08:00', '12:00']] })).toEqual({
			...emptyWeeklyHours(),
			'2': [
				['08:00', '12:00'],
				['14:00', '18:00']
			]
		});
		expect(normalizeWeeklyHours(null)).toEqual(emptyWeeklyHours());
	});

	it('finds empty, reversed and overlapping windows per day', () => {
		const h = emptyWeeklyHours();
		h['1'] = [['08:00', '12:00']];
		h['2'] = [['12:00', '09:00']];
		h['3'] = [
			['08:00', '12:00'],
			['11:30', '15:00']
		];
		h['4'] = [['', '12:00']];
		expect(hoursProblems(h)).toEqual({ '2': 'order', '3': 'overlap', '4': 'missing' });
		expect(hoursProblems(defaultWeeklyHours())).toEqual({});
	});

	it('copies one day to other days without sharing arrays', () => {
		const h = defaultWeeklyHours();
		h['1'] = [['09:00', '13:00']];
		const copied = copyDay(h, '1', ['2', '3']);
		expect(copied['2']).toEqual([['09:00', '13:00']]);
		expect(copied['3']).toEqual([['09:00', '13:00']]);
		expect(copied['4']).toEqual(h['4']);
		copied['2'][0][0] = '10:00';
		expect(copied['1'][0][0]).toBe('09:00');
	});

	it('summarises the week for patients: consecutive days with the same hours are grouped', () => {
		const h = defaultWeeklyHours();
		h['6'] = [['08:00', '13:00']];
		expect(hoursSummary(h)).toEqual([
			{
				from: '1',
				to: '5',
				windows: [
					['08:00', '12:30'],
					['14:00', '18:00']
				]
			},
			{ from: '6', to: '6', windows: [['08:00', '13:00']] },
			{ from: '7', to: '7', windows: [] }
		]);
	});

	it('knows the ISO weekday of a calendar day and whether the practice opens', () => {
		expect(weekdayOf('2026-10-30')).toBe('5'); // a Friday
		expect(weekdayOf('2026-11-01')).toBe('7');
		const h = defaultWeeklyHours();
		expect(isOpenOn(h, '2026-10-30')).toBe(true);
		expect(isOpenOn(h, '2026-11-01')).toBe(false);
	});
});
