<script lang="ts">
	/**
	 * One column of the agenda grid (a practitioner on a day, or a day of the week). The background is ruled like
	 * the paper agenda it replaces (hour lines, fine quarter lines); closed hours are hatched ("Pause", "Fermé");
	 * free slots inside the opening hours are click targets; appointments sit on top, overlapping ones side by side.
	 */
	import AppointmentCard from './AppointmentCard.svelte';
	import { FREEING, practitionerLabel } from '../../agenda/format';
	import { hhmm, layoutLanes, minutesOfDay } from '../../agenda/time';
	import { t } from '../../i18n.svelte';
	import type { Appointment } from '../../types/agenda';

	type Props = {
		label: string;
		appointments: Appointment[];
		/** Opening windows of the day in minutes; empty = closed all day. */
		windows: [number, number][];
		/** A closure (holiday) covers the day: everything hatched, no slots. */
		closed?: boolean;
		closedLabel?: string;
		range: { start: number; end: number };
		ppm: number;
		slotMinutes: number;
		/** Practitioner of the column, used in the slot labels. */
		practitioner?: { name: string; title?: string } | null;
		showPractitioner?: (a: Appointment) => string | null;
		/** Narrow column (week): blocks show time and name only. */
		minimal?: boolean;
		/** Slots starting earlier are not offered (the server refuses the past with 422 in_past). */
		notBefore?: number;
		onslot?: (time: string) => void;
		onopen?: (a: Appointment) => void;
	};
	let {
		label,
		appointments,
		windows,
		closed = false,
		closedLabel = '',
		range,
		ppm,
		slotMinutes,
		practitioner = null,
		showPractitioner,
		minimal = false,
		notBefore = -Infinity,
		onslot,
		onopen
	}: Props = $props();

	const top = (min: number) => (min - range.start) * ppm;
	const span = (a: Appointment) => {
		const start = minutesOfDay(a.startsAt);
		return { id: a.id, start, end: start + Math.max(a.durationMin, 1) };
	};

	/** Hatched parts: before/after opening ("Fermé") and between windows ("Pause"). */
	const shut = $derived.by(() => {
		if (closed || windows.length === 0)
			return [{ from: range.start, to: range.end, text: closedLabel || t('agenda.closed') }];
		const parts: { from: number; to: number; text: string }[] = [];
		let cursor = range.start;
		windows.forEach(([from, to], i) => {
			if (from > cursor) parts.push({ from: cursor, to: from, text: i === 0 ? t('agenda.closed') : t('agenda.pause') });
			cursor = Math.max(cursor, to);
		});
		if (cursor < range.end) parts.push({ from: cursor, to: range.end, text: t('agenda.closed') });
		return parts;
	});

	const blocking = $derived(appointments.filter((a) => !FREEING.includes(a.status)).map(span));

	const slots = $derived.by(() => {
		if (closed) return [];
		const free: number[] = [];
		for (const [from, to] of windows) {
			for (let m = from; m + slotMinutes <= to; m += slotMinutes) {
				if (m >= notBefore && !blocking.some((b) => b.start < m + slotMinutes && b.end > m)) free.push(m);
			}
		}
		return free;
	});

	const lanes = $derived(layoutLanes(appointments.map(span)));
	const who = $derived(practitioner ? practitionerLabel(practitioner) : null);

	function place(a: Appointment): string {
		const s = span(a);
		const lane = lanes.get(a.id) ?? { lane: 0, lanes: 1 };
		const height = Math.max((s.end - s.start) * ppm - 2, 22);
		return `top:${top(s.start) + 1}px;height:${height}px;inset-inline-start:calc(${(lane.lane / lane.lanes) * 100}% + 2px);width:calc(${100 / lane.lanes}% - 4px)`;
	}
</script>

<section
	aria-label={label}
	class="ruled relative min-w-0 flex-1 border-s border-slate-200"
	style="height:{(range.end - range.start) * ppm}px;--hour:{60 * ppm}px;--offset:{-(range.start % 60) * ppm}px"
>
	{#each shut as part (part.from)}
		<div
			class="hatch absolute inset-x-0 flex items-center justify-center overflow-hidden text-xs font-medium text-slate-500"
			style="top:{top(part.from)}px;height:{(part.to - part.from) * ppm}px"
		>
			{#if (part.to - part.from) * ppm >= 28}<span class="rounded bg-white/80 px-2 py-0.5">{part.text}</span>{/if}
		</div>
	{/each}

	{#each slots as m (m)}
		<button
			type="button"
			tabindex="-1"
			class="slot absolute inset-x-0 flex items-start px-2 text-xs font-semibold text-brand-800 opacity-0 hover:bg-brand-50 hover:opacity-100 focus-visible:opacity-100"
			style="top:{top(m)}px;height:{slotMinutes * ppm}px"
			aria-label={who ? t('agenda.slotWith', { time: hhmm(m), practitioner: who }) : t('agenda.slot', { time: hhmm(m) })}
			onclick={() => onslot?.(hhmm(m))}><span aria-hidden="true">+ {hhmm(m)}</span></button
		>
	{/each}

	{#each appointments as a (a.id)}
		<AppointmentCard {a} {minimal} dense={minimal || Math.max(a.durationMin, 1) * ppm < 40} style={place(a)} practitioner={showPractitioner?.(a) ?? null} {onopen} />
	{/each}
</section>

<style>
	.ruled {
		background-color: #fff;
		background-image:
			linear-gradient(to bottom, rgb(203 213 225) 1px, transparent 1px),
			linear-gradient(to bottom, rgb(15 118 110 / 0.07) 1px, transparent 1px);
		background-size:
			100% var(--hour),
			100% calc(var(--hour) / 4);
		background-position:
			0 var(--offset),
			0 var(--offset);
	}
	.hatch {
		background-color: rgb(248 250 252 / 0.9);
		background-image: repeating-linear-gradient(135deg, rgb(148 163 184 / 0.22) 0 1px, transparent 1px 9px);
	}
</style>
