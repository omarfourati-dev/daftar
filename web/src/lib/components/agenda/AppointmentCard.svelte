<script lang="ts">
	/**
	 * One appointment as a button: a block in the agenda grid (`variant="block"`, positioned by the column) or a
	 * row in the phone list. Shows time, patient, reason, status and the warnings that matter at the desk:
	 * medical alert, ≥ 2 no-shows, unpaid deposit, online request (dashed). Short blocks (`dense`) keep one line.
	 */
	import { FREEING, personName, STATUS_ACCENT, STATUS_TINT } from '../../agenda/format';
	import { formatMillimes, formatTime, t } from '../../i18n.svelte';
	import type { Appointment } from '../../types/agenda';
	import StatusPill from './StatusPill.svelte';

	type Props = {
		a: Appointment;
		variant?: 'block' | 'row';
		/** One line only (short block in the grid). */
		dense?: boolean;
		/** Narrow week column: time and name only, the status is read out but not shown. */
		minimal?: boolean;
		/** Position in the grid (top, height, inline start, width). */
		style?: string;
		/** Practitioner shown in the row (week list, mixed columns). */
		practitioner?: string | null;
		onopen?: (a: Appointment) => void;
	};
	let { a, variant = 'block', dense = false, minimal = false, style = '', practitioner = null, onopen }: Props = $props();

	const freed = $derived(FREEING.includes(a.status));
	const depositDue = $derived(!freed && a.depositRequiredMillimes > 0 && a.depositPaidMillimes < a.depositRequiredMillimes);
	const depositPaid = $derived(!freed && a.depositRequiredMillimes > 0 && !depositDue);
	const struck = $derived(a.status === 'cancelled');
</script>

<button
	type="button"
	class="flex w-full min-w-0 items-center gap-x-2 gap-y-1 overflow-hidden rounded-lg border border-s-4 text-start text-sm leading-5 text-ink transition-shadow hover:shadow-md focus-visible:z-20 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-700 {STATUS_TINT[
		a.status
	] ?? 'border-slate-200 bg-white'} {STATUS_ACCENT[a.status] ?? ''} {variant === 'block' ? 'absolute z-10 px-2' : 'px-3 py-3'} {dense
		? 'flex-nowrap py-0'
		: 'flex-wrap content-start py-1'}"
	{style}
	onclick={() => onopen?.(a)}
>
	<span class="shrink-0 font-semibold tabular-nums" class:line-through={struck}>{formatTime(a.startsAt)}</span>
	<span class="min-w-0 truncate font-semibold" class:line-through={struck}>{personName(a.patient)}</span>
	{#if a.reason && !dense}<span class="min-w-0 truncate text-slate-600">{a.reason}</span>{/if}
	{#if practitioner && !dense}<span class="min-w-0 truncate text-slate-500">{practitioner}</span>{/if}
	{#if a.patient.alerts}
		<span class="inline-grid h-5 min-w-5 shrink-0 place-items-center rounded-full bg-rose-600 px-1 text-xs font-bold text-white" title={a.patient.alerts}
			><span aria-hidden="true">!</span><span class="sr-only">{t('agenda.alert')}</span></span
		>
	{/if}
	<StatusPill status={a.status} class={minimal ? 'sr-only' : dense ? 'ms-auto py-0' : ''} />
	{#if a.patient.noShows >= 2 && !minimal}
		<span class="shrink-0 rounded-full bg-rose-100 px-2 text-xs font-semibold text-rose-800">{t('agenda.noShows', { count: a.patient.noShows })}</span>
	{/if}
	{#if depositDue && !dense}
		<span class="rounded-full bg-amber-100 px-2 text-xs font-semibold text-amber-900"
			>{t('agenda.depositDue', { amount: formatMillimes(a.depositRequiredMillimes - a.depositPaidMillimes) })}</span
		>
	{:else if depositPaid && !dense}
		<span class="rounded-full bg-emerald-100 px-2 text-xs font-semibold text-emerald-900">{t('agenda.depositPaid')}</span>
	{/if}
</button>
