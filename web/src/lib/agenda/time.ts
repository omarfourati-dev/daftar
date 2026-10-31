/**
 * Calendar math of the agenda. All business times are Africa/Tunis, which is UTC+1 all year (no daylight saving
 * time), so a fixed offset is exact. Days are `YYYY-MM-DD`, times of day are minutes since midnight.
 */
import { addDays, todayTunis } from '../i18n.svelte';
import type { Closure, WeeklyHours } from '../types/agenda';

const OFFSET_MIN = 60;
const DAY_MIN = 1440;
/** Agenda range when the practice has no opening hours at all. */
const DEFAULT_RANGE = { start: 8 * 60, end: 18 * 60 };

/** Minutes since midnight in Tunis of an instant (`2026-10-30T09:30:00+01:00` → 570). */
export function minutesOfDay(iso: string | Date): number {
	const ms = (iso instanceof Date ? iso : new Date(iso)).getTime();
	const minutes = Math.floor(ms / 60000) + OFFSET_MIN;
	return ((minutes % DAY_MIN) + DAY_MIN) % DAY_MIN;
}

/** The Tunis calendar day of an instant. */
export function tunisDayOf(iso: string | Date): string {
	return todayTunis(iso instanceof Date ? iso : new Date(iso));
}

/** `'08:30'` → 510. */
export function parseHHMM(text: string): number {
	const [h, m] = text.split(':').map(Number);
	return h * 60 + (m || 0);
}

/** 510 → `'08:30'`. */
export function hhmm(minutes: number): string {
	const h = Math.floor(minutes / 60);
	const m = minutes % 60;
	return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

/** The next multiple of `step` (or the value itself). */
export function roundUp(minutes: number, step: number): number {
	return Math.ceil(minutes / step) * step;
}

/** ISO weekday: Monday 1 … Sunday 7. */
export function isoWeekday(day: string): number {
	const d = new Date(`${day}T00:00:00Z`).getUTCDay();
	return d === 0 ? 7 : d;
}

/** The Monday of the week of `day`. */
export function weekStart(day: string): string {
	return addDays(day, 1 - isoWeekday(day));
}

/** Monday … Sunday of the week of `day`. */
export function weekDays(day: string): string[] {
	const monday = weekStart(day);
	return Array.from({ length: 7 }, (_, i) => addDays(monday, i));
}

/** Opening windows of a day as `[startMin, endMin]`, sorted. */
export function windowsOn(hours: WeeklyHours | undefined | null, day: string): [number, number][] {
	const list = hours?.[String(isoWeekday(day))] ?? [];
	return list
		.map(([from, to]) => [parseHHMM(from), parseHHMM(to)] as [number, number])
		.sort((a, b) => a[0] - b[0]);
}

/** Earliest opening to latest closing over the week (the visible part of the day grid). */
export function agendaRange(hours: WeeklyHours | undefined | null): { start: number; end: number } {
	let start = Infinity;
	let end = -Infinity;
	for (const list of Object.values(hours ?? {})) {
		for (const [from, to] of list ?? []) {
			start = Math.min(start, parseHHMM(from));
			end = Math.max(end, parseHHMM(to));
		}
	}
	return Number.isFinite(start) && end > start ? { start, end } : { ...DEFAULT_RANGE };
}

/** The closure (holiday, leave) covering `day`, if any. */
export function closureOn(closures: readonly Closure[], day: string): Closure | null {
	return closures.find((c) => c.startsOn <= day && day <= c.endsOn) ?? null;
}

/**
 * The first day after `today` with opening hours that is not a closing day – the day whose reminders go out today
 * (code review M6: on Saturday it is Monday). Same rule as the server; tomorrow when nothing opens within 31 days.
 */
export function nextOpenDay(hours: WeeklyHours | undefined | null, closures: readonly Closure[], today: string): string {
	for (let offset = 1; offset <= 31; offset++) {
		const day = addDays(today, offset);
		if (windowsOn(hours, day).length && !closureOn(closures, day)) return day;
	}
	return addDays(today, 1);
}

export interface Span {
	id: number;
	start: number;
	end: number;
}

/**
 * Side-by-side layout of overlapping appointments: each cluster of overlapping items shares the width,
 * every item gets the first free lane. Items that overlap nothing stay full width.
 */
export function layoutLanes(items: readonly Span[]): Map<number, { lane: number; lanes: number }> {
	const result = new Map<number, { lane: number; lanes: number }>();
	const sorted = [...items].sort((a, b) => a.start - b.start || b.end - a.end || a.id - b.id);
	let cluster: { span: Span; lane: number }[] = [];
	let clusterEnd = -Infinity;
	const flush = () => {
		const lanes = Math.max(0, ...cluster.map((c) => c.lane)) + 1;
		for (const c of cluster) result.set(c.span.id, { lane: c.lane, lanes });
		cluster = [];
	};
	for (const span of sorted) {
		if (cluster.length && span.start >= clusterEnd) flush();
		const busy = new Set(cluster.filter((c) => c.span.end > span.start).map((c) => c.lane));
		let lane = 0;
		while (busy.has(lane)) lane++;
		cluster.push({ span, lane });
		clusterEnd = cluster.length === 1 ? span.end : Math.max(clusterEnd, span.end);
	}
	if (cluster.length) flush();
	return result;
}

/**
 * Pixels per minute of the grid: `base`, or more when the shortest appointment (or the slot) would be lower than
 * `minHeight` – blocks must not overlap their neighbours – but never more than `max`.
 */
export function pixelsPerMinute(durations: readonly number[], slotMinutes: number, o: { base: number; minHeight: number; max: number }): number {
	const shortest = Math.min(slotMinutes || 15, ...durations.filter((d) => d > 0));
	return Math.min(o.max, Math.max(o.base, Math.round((o.minHeight / shortest) * 100) / 100));
}
