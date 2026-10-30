<script lang="ts">
	/**
	 * /app/agenda/imprimer?date=YYYY-MM-DD – the day as a paper list (story B6), one table per practitioner,
	 * for practices that like a sheet on the desk. The app frame and the buttons disappear when printing.
	 */
	import { onMount } from 'svelte';
	import { clock } from '#lib/clock';
	import { loadAgendaBase, loadAppointments, type AgendaBase } from '#lib/agenda/data';
	import { personName, practitionerLabel, statusLabel } from '#lib/agenda/format';
	import { displayPhone } from '#lib/agenda/links';
	import { formatDateTime, formatDay, formatTime, t, todayTunis } from '#lib/i18n.svelte';
	import type { Appointment } from '#lib/types/agenda';
	import Icon from '../../../../lib/components/daily/Icon.svelte';

	const requested = new URLSearchParams(location.search).get('date') ?? '';
	const day = /^\d{4}-\d{2}-\d{2}$/.test(requested) ? requested : todayTunis(clock.now());

	let base = $state<AgendaBase | null>(null);
	let list = $state<Appointment[]>([]);
	let error = $state('');

	onMount(async () => {
		try {
			[base, list] = await Promise.all([loadAgendaBase(), loadAppointments(day, day)]);
		} catch {
			error = t('agenda.loadError');
		}
	});

	const groups = $derived.by(() => {
		const kept = list.filter((a) => a.status !== 'cancelled').sort((a, b) => a.startsAt.localeCompare(b.startsAt));
		const result: { key: string; label: string; items: Appointment[] }[] = [];
		for (const a of kept) {
			const p = base?.practitioners.find((x) => x.id === a.practitionerId);
			const label = p ? practitionerLabel(p) : (a.practitionerName ?? t('agenda.noPractitioner'));
			const key = String(a.practitionerId ?? 'none');
			let group = result.find((g) => g.key === key);
			if (!group) result.push((group = { key, label, items: [] }));
			group.items.push(a);
		}
		const order = (key: string) => base?.practitioners.findIndex((p) => String(p.id) === key) ?? -1;
		return result.sort((a, b) => (order(a.key) < 0 ? 99 : order(a.key)) - (order(b.key) < 0 ? 99 : order(b.key)));
	});
</script>

<svelte:head><title>{t('agenda.print.title', { date: formatDay(day, 'long') })} · Daftar</title></svelte:head>

<div class="sheet mx-auto flex max-w-4xl flex-col gap-5">
	<div class="flex flex-wrap items-center gap-2 print:hidden">
		<a class="btn-secondary" href="/app/agenda?date={day}"><Icon name="start" />{t('agenda.print.back')}</a>
		<button type="button" class="btn-primary ms-auto" onclick={() => window.print()}><Icon name="print" />{t('agenda.print.button')}</button>
	</div>

	<header class="flex flex-wrap items-end justify-between gap-2 border-b-2 border-ink pb-3">
		<div>
			<p class="font-semibold text-slate-600">{base?.practice.name ?? ''}</p>
			<h1 class="text-2xl font-bold">{t('agenda.print.title', { date: formatDay(day, 'long') })}</h1>
		</div>
		<p class="text-xs text-slate-500">{t('agenda.print.printedAt', { date: formatDateTime(clock.now()) })}</p>
	</header>

	{#if error}
		<p role="alert" class="text-rose-800">{error}</p>
	{:else if !base}
		<p class="text-slate-600">{t('common.loading')}</p>
	{:else if !groups.length}
		<p class="text-slate-600">{t('agenda.print.empty')}</p>
	{:else}
		{#each groups as group (group.key)}
			<section class="break-inside-avoid-page">
				<h2 id="print-{group.key}" class="mb-2 text-lg font-bold">{group.label}</h2>
				<table aria-labelledby="print-{group.key}" class="w-full table-fixed border-collapse text-sm">
					<colgroup><col class="w-16" /><col class="w-[22%]" /><col class="w-[17%]" /><col class="w-[18%]" /><col class="w-[14%]" /><col /></colgroup>
					<thead>
						<tr class="border-b border-slate-400 text-start">
							<th scope="col" class="py-1.5 pe-2 text-start">{t('agenda.print.time')}</th>
							<th scope="col" class="py-1.5 pe-2 text-start">{t('agenda.print.patient')}</th>
							<th scope="col" class="py-1.5 pe-2 text-start">{t('agenda.print.phone')}</th>
							<th scope="col" class="py-1.5 pe-2 text-start">{t('agenda.print.reason')}</th>
							<th scope="col" class="py-1.5 pe-2 text-start">{t('agenda.print.status')}</th>
							<th scope="col" class="py-1.5 text-start">{t('agenda.print.notes')}</th>
						</tr>
					</thead>
					<tbody>
						{#each group.items as a (a.id)}
							<tr class="border-b border-slate-200 align-top">
								<td class="py-2 pe-2 font-semibold tabular-nums">{formatTime(a.startsAt)}</td>
								<td class="py-2 pe-2 font-semibold">
									{personName(a.patient)}
									{#if a.patient.alerts}<span class="block text-xs font-bold text-rose-800">⚠ {a.patient.alerts}</span>{/if}
								</td>
								<td class="py-2 pe-2 tabular-nums" dir="ltr">{displayPhone(a.patient.phone)}</td>
								<td class="py-2 pe-2">{a.reason}</td>
								<td class="py-2 pe-2">{statusLabel(a.status)}</td>
								<td class="py-2">{a.notes}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</section>
		{/each}
	{/if}
</div>

<style>
	@media print {
		:global(body) {
			background: #fff;
		}
		.sheet {
			max-width: none;
			font-size: 11pt;
		}
		@page {
			margin: 14mm;
		}
	}
</style>
