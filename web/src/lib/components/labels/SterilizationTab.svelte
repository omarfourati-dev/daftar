<script lang="ts">
	/**
	 * Tab "Stérilisation" of /app/hygiene (spec stock-hygiène 5.2, 5.3): a new cycle in a few taps (its labels come right
	 * after), the cycles of a period with their packs – who got which one (the owner; the desk sees "used") –, the
	 * owner's traceability search, corrections and cancellations, the label settings, and the cycle register on A4 for
	 * an inspection. A cancelled cycle stays in the list and the register, marked, without labels.
	 */
	import { onMount } from 'svelte';
	import { api, deps } from '../../api';
	import { auth } from '../../auth.svelte';
	import { clock } from '../../clock';
	import { addDays, formatDate, formatDateTime, formatDay, formatTime, t, todayTunis } from '../../i18n.svelte';
	import { labelsError, patientOfUse } from '../../labels';
	import type { Cycle, CycleList, LabelSettings } from '../../types/labels';
	import Icon from '../daily/Icon.svelte';
	import CycleCorrection from './CycleCorrection.svelte';
	import CycleDialog from './CycleDialog.svelte';
	import LabelSettingsDialog from './LabelSettingsDialog.svelte';
	import StateChip from './StateChip.svelte';
	import TraceSearch from './TraceSearch.svelte';

	const today = todayTunis(clock.now());
	const manager = $derived(auth.role === 'owner' || auth.role === 'assistant');
	const isOwner = $derived(auth.role === 'owner');
	const practiceName = $derived(auth.user?.practice?.name ?? '');

	let settings = $state<LabelSettings | null>(null);
	let list = $state<CycleList | null>(null);
	let from = $state(addDays(today, -29));
	let to = $state(today);
	let error = $state('');
	let notice = $state('');
	let creating = $state(false);
	let editingSettings = $state(false);
	let correcting = $state<Cycle | null>(null);
	let open = $state<number[]>([]);

	async function load() {
		error = '';
		try {
			[settings, list] = await Promise.all([
				api<LabelSettings>('/api/labels/settings'),
				api<CycleList>(`/api/hygiene/cycles?${new URLSearchParams({ from, to })}`)
			]);
		} catch (err) {
			error = labelsError(err);
		}
	}
	onMount(load);

	function saved(cycle: Cycle) {
		creating = false;
		if (cycle.result === 'ok' && cycle.packs.length) {
			void deps.goto(`/app/etiquettes?cycle=${cycle.id}`);
			return;
		}
		notice = cycle.result === 'ok' ? t('labels.cycles.savedNoPacks') : t('labels.cycles.savedNotOk');
		void load();
	}

	function corrected(message: string) {
		correcting = null;
		notice = message;
		void load();
	}

	function toggle(id: number) {
		open = open.includes(id) ? open.filter((x) => x !== id) : [...open, id];
	}

	const counts = (c: Cycle) => ({
		usable: c.packs.filter((p) => p.state === 'usable').length,
		used: c.packs.filter((p) => p.state === 'used').length,
		expired: c.packs.filter((p) => p.state === 'expired').length
	});
	const valid = $derived(list?.cycles.filter((c) => !c.cancelledAt) ?? []);
	const summary = $derived({
		cycles: valid.length,
		notOk: valid.filter((c) => c.result !== 'ok').length,
		packs: valid.reduce((sum, c) => sum + c.packs.length, 0)
	});
	const cancelledCount = $derived((list?.cycles.length ?? 0) - valid.length);
</script>

<div class="flex flex-col gap-5">
	<div class="flex flex-wrap items-center gap-2 print:hidden">
		<button type="button" class="btn-primary" onclick={() => (creating = true)}><Icon name="plus" />{t('labels.cycles.new')}</button>
		{#if manager && settings}
			<button type="button" class="btn-secondary" onclick={() => (editingSettings = true)}>{t('labels.cycles.settings')}</button>
		{/if}
		<a class="btn-secondary" href="/app/etiquettes?test=1"><Icon name="print" />{t('labels.cycles.test')}</a>
	</div>

	{#if notice}<p role="status" class="rounded-lg bg-emerald-50 px-3 py-2 font-medium text-emerald-900 ring-1 ring-emerald-200 print:hidden">{notice}</p>{/if}
	{#if error}
		<div role="alert" class="card flex flex-wrap items-center justify-between gap-3 border-rose-200 bg-rose-50 text-rose-900 print:hidden">
			<p>{error}</p>
			<button type="button" class="btn-secondary" onclick={load}>{t('common.retry')}</button>
		</div>
	{/if}

	<div class="grid items-start gap-5 {isOwner ? 'lg:grid-cols-[minmax(0,1fr)_22rem]' : ''}">
	<section aria-labelledby="cycles-title" class="flex min-w-0 flex-col gap-3">
		<h2 id="cycles-title" class="text-lg font-bold print:hidden">{t('labels.cycles.title')}</h2>
		<form class="flex flex-wrap items-end gap-3 print:hidden" onsubmit={(e) => (e.preventDefault(), void load())}>
			<label class="label">{t('hygiene.history.from')}<input class="input" type="date" bind:value={from} max={to} /></label>
			<label class="label">{t('hygiene.history.to')}<input class="input" type="date" bind:value={to} /></label>
			<button type="submit" class="btn-secondary">{t('hygiene.history.show')}</button>
			<button type="button" class="btn-secondary" onclick={() => window.print()}><Icon name="print" />{t('labels.cycles.print')}</button>
		</form>

		{#if list}
			<div class="hidden print:block">
				<p class="text-xl font-bold" dir="auto">{t('labels.cycles.printTitle', { practice: practiceName })}</p>
				<p>{t('hygiene.history.printPeriod', { from: formatDay(list.from), to: formatDay(list.to) })}</p>
				<p class="text-sm">{t('hygiene.history.printedOn', { date: formatDateTime(clock.now()) })}</p>
			</div>
			<p class="text-sm font-semibold text-slate-700">{t('labels.cycles.summary', summary)}</p>
			{#if cancelledCount}<p class="-mt-2 text-sm text-slate-600">{t('labels.cycles.cyclesCancelled', { count: cancelledCount })}</p>{/if}
			{#if list.cycles.length}
				<ul class="flex flex-col gap-3 print:hidden" aria-label={t('labels.cycles.title')}>
					{#each list.cycles as c (c.id)}
						{@const n = counts(c)}
						<li class="card flex flex-col gap-3 {c.cancelledAt ? 'border-dashed bg-slate-50' : c.result === 'ok' ? '' : 'border-rose-300 bg-rose-50/50'}">
							<div class="flex items-start gap-3">
								<div class="grid w-16 shrink-0 place-items-center rounded-lg bg-slate-50 py-1.5 ring-1 ring-slate-200" aria-hidden="true">
									<span class="text-xs font-semibold text-slate-600" dir="ltr">{c.labelCode}</span>
									<span class="text-xl leading-tight font-bold tabular-nums" dir="ltr">{c.number}</span>
								</div>
								<div class="min-w-0 flex-1">
									<h3 class="font-semibold">
										{t('labels.cycles.name', { code: c.labelCode, number: c.number })}
										<span class="font-normal text-slate-600 tabular-nums">{formatDate(c.runAt)} {formatTime(c.runAt)}</span>
									</h3>
									<p class="text-sm text-slate-600">
										<span dir="auto">{c.equipmentName}</span>{#if c.program}{' – '}<span dir="auto">{c.program}</span>{/if}{' – '}<span dir="auto">{c.performedBy}</span
										>{#if c.recordedBy && c.recordedBy !== c.performedBy}{' '}({t('labels.cycles.recordedBy', { by: c.recordedBy })}){/if}
									</p>
									{#if c.cancelledAt}
										<p class="mt-1 flex flex-wrap items-center gap-2 text-sm">
											<span class="rounded-full bg-slate-200 px-2 text-xs font-bold text-slate-900">{t('labels.cycles.cancelledShort')}</span>
											<span>{t('labels.cycles.cancelled', { date: formatDateTime(c.cancelledAt), by: c.cancelledBy ?? '', reason: c.cancelReason ?? '' })}</span>
										</p>
									{:else if c.result === 'ok'}
										<p class="mt-1 flex flex-wrap items-center gap-2 text-sm">
											<span class="inline-flex items-center gap-1 font-semibold text-emerald-800"><Icon name="check" class="h-4 w-4" />{t('labels.cycleDialog.ok')}</span>
											<span>{c.packs.length ? t('labels.cycles.packs', { count: c.packs.length, ...n }) : t('labels.cycles.noPacks')}</span>
										</p>
									{:else}
										<p class="mt-1 flex flex-wrap items-center gap-2 text-sm font-semibold text-rose-900">
											<Icon name="alert" class="h-4 w-4" />{t('labels.cycleDialog.notOk')}
											<span class="font-normal">{c.packs.length ? t('labels.cycles.recalled', { count: c.packs.length }) : t('labels.cycles.redo', { count: c.packCount })}</span>
										</p>
									{/if}
									{#if c.note}<p class="mt-1 text-sm text-slate-700" dir="auto">{c.note}</p>{/if}
								</div>
							</div>
							<div class="flex flex-wrap gap-2">
								{#if c.result === 'ok' && !c.cancelledAt && c.packs.length}
									<a class="btn-secondary min-h-10 px-3 text-sm" href="/app/etiquettes?cycle={c.id}"
										><Icon name="print" class="h-4 w-4" />{t('labels.cycles.labels', { code: c.labelCode, number: c.number })}</a
									>
								{/if}
								{#if c.packs.length}
									<button type="button" class="btn-secondary min-h-10 px-3 text-sm" aria-expanded={open.includes(c.id)} onclick={() => toggle(c.id)}
										>{open.includes(c.id) ? t('labels.cycles.hidePacks') : t('labels.cycles.showPacks')}</button
									>
								{/if}
								{#if isOwner && !c.cancelledAt}
									<button
										type="button"
										class="btn-secondary min-h-10 px-3 text-sm"
										aria-label={t('labels.cycles.correctLabel', { code: c.labelCode, number: c.number })}
										onclick={() => (correcting = c)}>{t('labels.cycles.correct')}</button
									>
								{/if}
							</div>
							{#if open.includes(c.id)}
								<ul class="flex flex-col divide-y divide-slate-100 rounded-lg bg-white px-3 ring-1 ring-slate-200" aria-label={t('labels.cycles.packsOf', { code: c.labelCode, number: c.number })}>
									{#each c.packs as p (p.id)}
										<li class="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-sm">
											<span class="font-bold tabular-nums" dir="ltr">{p.code}</span>
											<span class="min-w-0 flex-1" dir="auto">{p.content}</span>
											<StateChip state={p.state} />
											<span class="w-full text-slate-600">
												{t('labels.trace.useBefore', { date: formatDay(p.expiresOn) })}{#if p.use}{' – '}{#if p.use.patientId !== null}{t('labels.cycles.usedFor')}
														<a class="font-semibold text-brand-800 underline-offset-2 hover:underline" href="/app/patients/{p.use.patientId}">{p.use.patientName}</a>
														<span class="tabular-nums">({formatDate(p.use.usedAt)})</span>{:else if p.use.patientDeleted && p.use.patientNo !== null}{t('labels.cycles.usedFor')}
														{patientOfUse(p.use)} <span class="tabular-nums">({formatDate(p.use.usedAt)})</span>{:else}{t('labels.cycles.usedOn', {
															date: formatDate(p.use.usedAt)
														})}{/if}{/if}
											</span>
										</li>
									{/each}
								</ul>
							{/if}
						</li>
					{/each}
				</ul>
				<table class="hidden w-full text-sm print:table">
					<caption class="sr-only">{t('labels.cycles.title')}</caption>
					<thead>
						<tr class="border-b border-slate-400 text-start">
							<th scope="col" class="px-2 py-1 text-start">{t('labels.cycles.colDate')}</th>
							<th scope="col" class="px-2 py-1 text-start">{t('labels.cycles.colCycle')}</th>
							<th scope="col" class="px-2 py-1 text-start">{t('labels.cycleDialog.program')}</th>
							<th scope="col" class="px-2 py-1 text-start">{t('labels.cycleDialog.result')}</th>
							<th scope="col" class="px-2 py-1 text-start">{t('labels.cycleDialog.packs')}</th>
							<th scope="col" class="px-2 py-1 text-start">{t('hygiene.history.by')}</th>
							<th scope="col" class="px-2 py-1 text-start">{t('labels.cycleDialog.note')}</th>
						</tr>
					</thead>
					<tbody>
						{#each list.cycles as c (c.id)}
							<tr class="border-b border-slate-200 align-top break-inside-avoid">
								<td class="px-2 py-1 whitespace-nowrap tabular-nums">{formatDateTime(c.runAt)}</td>
								<th scope="row" class="px-2 py-1 text-start font-semibold"><span dir="auto">{c.equipmentName}</span> {c.labelCode} n° {c.number}</th>
								<td class="px-2 py-1" dir="auto">{c.program}</td>
								<td class="px-2 py-1"
									>{c.cancelledAt
										? t('labels.cycles.cancelled', { date: formatDateTime(c.cancelledAt), by: c.cancelledBy ?? '', reason: c.cancelReason ?? '' })
										: c.result === 'ok'
											? t('labels.cycleDialog.ok')
											: t('labels.cycleDialog.notOk')}</td
								>
								<td class="px-2 py-1 tabular-nums">{c.packCount}</td>
								<td class="px-2 py-1" dir="auto">{c.performedBy}</td>
								<td class="px-2 py-1" dir="auto">{c.note}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			{:else}
				<div class="card flex flex-col items-start gap-3 border-dashed border-brand-300 bg-brand-50/40">
					<p class="text-slate-700">{t('labels.cycles.empty')}</p>
					<button type="button" class="btn-primary" onclick={() => (creating = true)}><Icon name="plus" />{t('labels.cycles.new')}</button>
				</div>
			{/if}
		{:else if !error}
			<p class="card text-slate-600" aria-busy="true">{t('common.loading')}</p>
		{/if}
	</section>
	{#if isOwner}<div class="print:hidden lg:sticky lg:top-4"><TraceSearch /></div>{/if}
	</div>
</div>

{#if creating && settings}
	<CycleDialog {settings} onsaved={saved} onclose={() => (creating = false)} />
{/if}
{#if editingSettings && settings}
	<LabelSettingsDialog
		{settings}
		onsaved={(s) => ((settings = s), (editingSettings = false), (notice = t('labels.settings.saved')))}
		onclose={() => (editingSettings = false)}
	/>
{/if}
{#if correcting}
	<CycleCorrection cycle={correcting} onsaved={corrected} onclose={() => (correcting = null)} />
{/if}
