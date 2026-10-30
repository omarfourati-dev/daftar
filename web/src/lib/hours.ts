/**
 * Opening hours as the API stores them (`practice.weekly_hours`, backend daftar/hours.py): ISO weekday "1" (Monday)
 * … "7" (Sunday) → list of `["HH:MM", "HH:MM"]` windows. A day without windows is closed; a break is the gap between
 * two windows. Used by the hours editor (admin wizard, settings) and the public booking page.
 */
export type Weekday = '1' | '2' | '3' | '4' | '5' | '6' | '7';
export type Window = [string, string];
export type WeeklyHours = Record<Weekday, Window[]>;
export type HoursProblem = 'missing' | 'order' | 'overlap';

export const WEEKDAYS: readonly Weekday[] = ['1', '2', '3', '4', '5', '6', '7'];
export const MAX_WINDOWS_PER_DAY = 6;

export function emptyWeeklyHours(): WeeklyHours {
	return { '1': [], '2': [], '3': [], '4': [], '5': [], '6': [], '7': [] };
}

/** Monday–Saturday 08:00–12:30 and 14:00–18:00, Sunday closed (backend `DEFAULT_WEEKLY_HOURS`). */
export function defaultWeeklyHours(): WeeklyHours {
	const h = emptyWeeklyHours();
	for (const day of WEEKDAYS.slice(0, 6)) {
		h[day] = [
			['08:00', '12:30'],
			['14:00', '18:00']
		];
	}
	return h;
}

const byStart = (a: Window, b: Window) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0);

/** A complete, sorted copy of whatever the API sent (missing days are closed). */
export function normalizeWeeklyHours(value: unknown): WeeklyHours {
	const h = emptyWeeklyHours();
	if (!value || typeof value !== 'object') return h;
	for (const day of WEEKDAYS) {
		const windows = (value as Record<string, unknown>)[day];
		if (!Array.isArray(windows)) continue;
		h[day] = windows
			.filter((w): w is [string, string] => Array.isArray(w) && w.length === 2)
			.map((w) => [String(w[0]), String(w[1])] as Window)
			.sort(byStart);
	}
	return h;
}

/** The first problem of each day that has one; `{}` when the week can be saved. */
export function hoursProblems(h: WeeklyHours): Partial<Record<Weekday, HoursProblem>> {
	const problems: Partial<Record<Weekday, HoursProblem>> = {};
	for (const day of WEEKDAYS) {
		const windows = h[day];
		if (windows.some(([a, b]) => !a || !b)) problems[day] = 'missing';
		else if (windows.some(([a, b]) => a >= b)) problems[day] = 'order';
		else {
			const sorted = [...windows].sort(byStart);
			if (sorted.some((w, i) => i > 0 && w[0] < sorted[i - 1][1])) problems[day] = 'overlap';
		}
	}
	return problems;
}

function cloneWindows(windows: Window[]): Window[] {
	return windows.map(([a, b]) => [a, b]);
}

export function cloneWeeklyHours(h: WeeklyHours): WeeklyHours {
	const copy = emptyWeeklyHours();
	for (const day of WEEKDAYS) copy[day] = cloneWindows(h[day]);
	return copy;
}

/** A copy of the week where every day in `to` gets the windows of `from`. */
export function copyDay(h: WeeklyHours, from: Weekday, to: readonly Weekday[]): WeeklyHours {
	const copy = cloneWeeklyHours(h);
	for (const day of to) copy[day] = cloneWindows(h[from]);
	return copy;
}

/** The week sorted and ready for the API. */
export function sortedWeeklyHours(h: WeeklyHours): WeeklyHours {
	const copy = cloneWeeklyHours(h);
	for (const day of WEEKDAYS) copy[day].sort(byStart);
	return copy;
}

export interface HoursLine {
	from: Weekday;
	to: Weekday;
	windows: Window[];
}

/** Consecutive days with identical hours grouped: "Lun.–Ven. 08:00–12:30, 14:00–18:00". */
export function hoursSummary(h: WeeklyHours): HoursLine[] {
	const lines: HoursLine[] = [];
	const key = (w: Window[]) => JSON.stringify(w);
	for (const day of WEEKDAYS) {
		const last = lines.at(-1);
		if (last && key(last.windows) === key(h[day])) last.to = day;
		else lines.push({ from: day, to: day, windows: cloneWindows(h[day]) });
	}
	return lines;
}

/** ISO weekday of a calendar day `YYYY-MM-DD` (independent of the device's time zone). */
export function weekdayOf(day: string): Weekday {
	const js = new Date(`${day}T12:00:00Z`).getUTCDay(); // 0 = Sunday
	return String(js === 0 ? 7 : js) as Weekday;
}

export function isOpenOn(h: WeeklyHours, day: string): boolean {
	return h[weekdayOf(day)].length > 0;
}
