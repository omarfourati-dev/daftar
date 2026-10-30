<script lang="ts">
	/** The agenda on phones: one list per day instead of the time grid (design section 10). */
	import AppointmentCard from './AppointmentCard.svelte';
	import { formatDay, t } from '../../i18n.svelte';
	import type { Appointment } from '../../types/agenda';

	type Props = {
		days: string[];
		byDay: Map<string, Appointment[]>;
		closedText: (day: string) => string | null;
		practitionerOf: (a: Appointment) => string | null;
		onopen: (a: Appointment) => void;
	};
	let { days, byDay, closedText, practitionerOf, onopen }: Props = $props();
</script>

<div class="flex flex-col gap-5">
	{#each days as day (day)}
		{@const list = byDay.get(day) ?? []}
		{@const closed = closedText(day)}
		<div class="flex flex-col gap-2">
			{#if days.length > 1}
				<h2 class="text-sm font-semibold text-slate-600 first-letter:uppercase">{formatDay(day, 'long')}</h2>
			{/if}
			{#if closed}
				<p class="hatch rounded-lg px-3 py-2 text-sm font-medium text-slate-600">{closed}</p>
			{/if}
			{#if list.length}
				<ul aria-label={formatDay(day, 'long')} class="flex flex-col gap-2">
					{#each list as a (a.id)}
						<li><AppointmentCard {a} variant="row" practitioner={practitionerOf(a)} {onopen} /></li>
					{/each}
				</ul>
			{:else if days.length > 1 && !closed}
				<p class="text-sm text-slate-500">{t('agenda.emptyDay')}</p>
			{/if}
		</div>
	{/each}
</div>

<style>
	.hatch {
		background-color: rgb(248 250 252);
		background-image: repeating-linear-gradient(135deg, rgb(148 163 184 / 0.22) 0 1px, transparent 1px 9px);
	}
</style>
