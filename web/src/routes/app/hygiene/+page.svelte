<script lang="ts">
	/**
	 * /app/hygiene (spec stock-hygiène 5.2): "Aujourd'hui" (the tasks to tick, overdue first), "Équipements et tâches"
	 * (the plan – a typical plan of the specialty in one tap; set up by assistant and owner) and "Historique" (every due
	 * date with its proof or gap, filter by period and equipment, printable as an A4 register for an inspection).
	 * `?tab=taches|historique` opens a part directly. The sterilisation tab comes with the labels (phase 3).
	 */
	import { onMount } from 'svelte';
	import { api } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { clock } from '#lib/clock';
	import { frequencyText, hygieneError, kindLabel } from '#lib/hygiene';
	import { addDays, formatDateTime, formatDay, t, todayTunis } from '#lib/i18n.svelte';
	import type { Equipment, HygieneHistory, HygieneTask, HygieneToday } from '#lib/types/hygiene';
	import Icon from '../../../lib/components/daily/Icon.svelte';
	import EquipmentDialog from '../../../lib/components/hygiene/EquipmentDialog.svelte';
	import HygieneTodayList from '../../../lib/components/hygiene/HygieneToday.svelte';
	import TaskDialog from '../../../lib/components/hygiene/TaskDialog.svelte';

	type Tab = 'aujourdhui' | 'taches' | 'historique';
	const TABS: { key: Tab; label: 'hygiene.tabs.today' | 'hygiene.tabs.setup' | 'hygiene.tabs.history' }[] = [
		{ key: 'aujourdhui', label: 'hygiene.tabs.today' },
		{ key: 'taches', label: 'hygiene.tabs.setup' },
		{ key: 'historique', label: 'hygiene.tabs.history' }
	];
	const today = todayTunis(clock.now());
	const manager = $derived(auth.role === 'owner' || auth.role === 'assistant');

	function initialTab(): Tab {
		const wanted = typeof location === 'undefined' ? null : new URLSearchParams(location.search).get('tab');
		return TABS.some((x) => x.key === wanted) ? (wanted as Tab) : 'aujourdhui';
	}

	let tab = $state<Tab>(initialTab());
	let todayData = $state<HygieneToday | null>(null);
	let equipment = $state<Equipment[] | null>(null);
	let tasks = $state<HygieneTask[] | null>(null);
	let historyData = $state<HygieneHistory | null>(null);
	let from = $state(addDays(today, -29));
	let to = $state(today);
	let equipmentFilter = $state('');
	let error = $state('');
	let notice = $state('');
	let busy = $state(false);
	let editingTask = $state<{ task: HygieneTask | null } | null>(null);
	let editingEquipment = $state<{ item: Equipment | null } | null>(null);

	async function loadPlan() {
		[equipment, tasks] = await Promise.all([api<Equipment[]>('/api/hygiene/equipment'), api<HygieneTask[]>('/api/hygiene/tasks')]);
	}

	async function loadHistory() {
		const params = new URLSearchParams({ from, to });
		if (equipmentFilter) params.set('equipmentId', equipmentFilter);
		historyData = await api<HygieneHistory>(`/api/hygiene/history?${params}`);
	}

	async function load(which: Tab) {
		error = '';
		try {
			if (which === 'aujourdhui') todayData = await api<HygieneToday>('/api/hygiene/today');
			if (which === 'taches') await loadPlan();
			if (which === 'historique') {
				if (equipment === null) equipment = await api<Equipment[]>('/api/hygiene/equipment');
				await loadHistory();
			}
		} catch (err) {
			error = which === 'historique' ? hygieneError(err) : t('hygiene.loadError');
		}
	}

	onMount(() => void load(tab));

	function show(which: Tab) {
		tab = which;
		notice = '';
		try {
			const url = new URL(location.href);
			if (which === 'aujourdhui') url.searchParams.delete('tab');
			else url.searchParams.set('tab', which);
			history.replaceState(history.state, '', url);
		} catch {
			/* tests without a real location */
		}
		void load(which);
	}

	async function starter() {
		busy = true;
		error = '';
		try {
			const made = await api<{ equipment: number; tasks: number }>('/api/hygiene/starter', { method: 'POST' });
			notice = made.equipment || made.tasks ? t('hygiene.setup.starterDone', made) : t('hygiene.setup.starterNone');
			await loadPlan();
		} catch (err) {
			error = hygieneError(err);
		} finally {
			busy = false;
		}
	}

	function savedTask(task: HygieneTask) {
		tasks = tasks?.some((x) => x.id === task.id) ? tasks.map((x) => (x.id === task.id ? task : x)) : [...(tasks ?? []), task];
		editingTask = null;
		void api<Equipment[]>('/api/hygiene/equipment').then((list) => (equipment = list)).catch(() => undefined);
	}

	function savedEquipment(item: Equipment) {
		equipment = equipment?.some((x) => x.id === item.id) ? equipment.map((x) => (x.id === item.id ? item : x)) : [...(equipment ?? []), item];
		editingEquipment = null;
	}

	const counts = $derived({
		done: historyData?.rows.filter((r) => r.status === 'done').length ?? 0,
		missed: historyData?.rows.filter((r) => r.status === 'missed').length ?? 0
	});
	const practiceName = $derived(auth.user?.practice?.name ?? '');
	const STATUS_TONE = { done: 'text-emerald-800', missed: 'font-semibold text-rose-800', due: 'text-slate-700' } as const;
</script>

<svelte:head><title>{t('hygiene.title')} · Daftar</title></svelte:head>

<div class="flex flex-col gap-5">
	<div class="print:hidden">
		<h1 class="text-2xl font-bold">{t('hygiene.title')}</h1>
		<p class="text-slate-600">{t('hygiene.intro')}</p>
	</div>

	<div role="group" aria-label={t('hygiene.tabs.label')} class="flex flex-wrap gap-2 print:hidden">
		{#each TABS as item (item.key)}
			<button
				type="button"
				class="min-h-11 rounded-full px-4 text-sm font-semibold ring-1 transition-colors {tab === item.key
					? 'bg-brand-700 text-white ring-brand-700'
					: 'bg-white text-slate-700 ring-slate-300 hover:bg-slate-50'}"
				aria-pressed={tab === item.key}
				onclick={() => show(item.key)}>{t(item.label)}</button
			>
		{/each}
	</div>

	{#if notice}<p role="status" class="rounded-lg bg-emerald-50 px-3 py-2 font-medium text-emerald-900 ring-1 ring-emerald-200 print:hidden">{notice}</p>{/if}
	{#if error}
		<div role="alert" class="card flex flex-wrap items-center justify-between gap-3 border-rose-200 bg-rose-50 text-rose-900 print:hidden">
			<p>{error}</p>
			<button type="button" class="btn-secondary" onclick={() => load(tab)}>{t('common.retry')}</button>
		</div>
	{/if}

	{#if tab === 'aujourdhui'}
		{#if todayData}
			<section class="card" aria-labelledby="hygiene-today-title">
				<h2 id="hygiene-today-title" class="mb-3 text-lg font-bold">{t('hygiene.today.title')}</h2>
				<HygieneTodayList data={todayData} onchange={(d) => (todayData = d)} />
				{#if todayData.items.length === 0 && manager}
					<button type="button" class="btn-secondary mt-3" onclick={() => show('taches')}>{t('hygiene.tabs.setup')}</button>
				{/if}
			</section>
		{:else if !error}
			<p class="card text-slate-600" aria-busy="true">{t('common.loading')}</p>
		{/if}
	{:else if tab === 'taches'}
		{#if tasks === null || equipment === null}
			{#if !error}<p class="card text-slate-600" aria-busy="true">{t('common.loading')}</p>{/if}
		{:else}
			{#if !manager}<p class="text-sm text-slate-600">{t('hygiene.setup.readOnly')}</p>{/if}
			{#if manager && tasks.length === 0}
				<section class="card flex flex-col items-start gap-3 border-dashed border-brand-300 bg-brand-50/40 p-5">
					<p class="text-slate-700">{t('hygiene.setup.starterHint')}</p>
					<button type="button" class="btn-primary" disabled={busy} onclick={starter}>{t('hygiene.setup.starter')}</button>
				</section>
			{/if}
			<div class="grid items-start gap-5 lg:grid-cols-[2fr_1fr]">
				<section aria-labelledby="tasks-title" class="flex flex-col gap-3">
					<div class="flex flex-wrap items-center justify-between gap-2">
						<h2 id="tasks-title" class="text-lg font-bold">{t('hygiene.setup.tasks')}</h2>
						{#if manager}
							<button type="button" class="btn-secondary" onclick={() => (editingTask = { task: null })}><Icon name="plus" />{t('hygiene.setup.addTask')}</button>
						{/if}
					</div>
					{#if tasks.length}
						<ul class="flex flex-col gap-2" aria-label={t('hygiene.setup.tasks')}>
							{#each tasks as task (task.id)}
								<li class="card flex items-start gap-3 {task.active ? '' : 'opacity-70'}">
									<div class="min-w-0 flex-1">
										<p class="font-semibold" dir="auto">{task.title}</p>
										<p class="text-sm text-slate-600">
											{frequencyText(task)}{#if task.equipmentName}<span dir="auto"> – {task.equipmentName}</span>{/if}
										</p>
										<p class="text-sm text-slate-600">
											{task.active ? (task.nextDueOn ? t('hygiene.setup.next', { date: formatDay(task.nextDueOn) }) : '') : t('hygiene.setup.inactive')}
										</p>
									</div>
									{#if manager}
										<button
											type="button"
											class="btn -me-2 min-h-11 min-w-11 px-2 text-slate-600 hover:bg-slate-100"
											aria-label={t('hygiene.setup.edit', { name: task.title })}
											onclick={() => (editingTask = { task })}><Icon name="edit" /></button
										>
									{/if}
								</li>
							{/each}
						</ul>
					{:else}
						<p class="text-slate-600">{t('hygiene.setup.noTasks')}</p>
					{/if}
				</section>
				<section aria-labelledby="equipment-title" class="flex flex-col gap-3">
					<div class="flex flex-wrap items-center justify-between gap-2">
						<h2 id="equipment-title" class="text-lg font-bold">{t('hygiene.setup.equipment')}</h2>
						{#if manager}
							<button type="button" class="btn-secondary" onclick={() => (editingEquipment = { item: null })}><Icon name="plus" />{t('hygiene.setup.addEquipment')}</button>
						{/if}
					</div>
					{#if equipment.length}
						<ul class="flex flex-col gap-2" aria-label={t('hygiene.setup.equipment')}>
							{#each equipment as item (item.id)}
								<li class="card flex items-start gap-3 {item.active ? '' : 'opacity-70'}">
									<div class="min-w-0 flex-1">
										<p class="font-semibold" dir="auto">{item.name}</p>
										<p class="text-sm text-slate-600">
											{kindLabel(item.kind)} – {t('hygiene.setup.taskCount', { count: item.tasks })}{#if item.serialNumber}<span dir="ltr"> – {item.serialNumber}</span>{/if}
										</p>
									</div>
									{#if manager}
										<button
											type="button"
											class="btn -me-2 min-h-11 min-w-11 px-2 text-slate-600 hover:bg-slate-100"
											aria-label={t('hygiene.setup.edit', { name: item.name })}
											onclick={() => (editingEquipment = { item })}><Icon name="edit" /></button
										>
									{/if}
								</li>
							{/each}
						</ul>
					{:else}
						<p class="text-slate-600">{t('hygiene.setup.noEquipment')}</p>
					{/if}
				</section>
			</div>
		{/if}
	{:else if tab === 'historique'}
		<form class="flex flex-wrap items-end gap-3 print:hidden" onsubmit={(e) => (e.preventDefault(), void load('historique'))}>
			<label class="label">{t('hygiene.history.from')}<input class="input" type="date" bind:value={from} max={to} /></label>
			<label class="label">{t('hygiene.history.to')}<input class="input" type="date" bind:value={to} /></label>
			<label class="label min-w-48"
				>{t('hygiene.history.equipment')}
				<select class="input" bind:value={equipmentFilter}>
					<option value="">{t('hygiene.history.allEquipment')}</option>
					{#each equipment ?? [] as item (item.id)}<option value={String(item.id)}>{item.name}</option>{/each}
				</select>
			</label>
			<button type="submit" class="btn-secondary">{t('hygiene.history.show')}</button>
			<button type="button" class="btn-primary" onclick={() => window.print()}><Icon name="print" />{t('hygiene.history.print')}</button>
		</form>
		{#if historyData}
			<div class="hidden print:block">
				<p class="text-xl font-bold" dir="auto">{t('hygiene.history.printTitle', { practice: practiceName })}</p>
				<p>{t('hygiene.history.printPeriod', { from: formatDay(historyData.from), to: formatDay(historyData.to) })}</p>
				<p class="text-sm">{t('hygiene.history.printedOn', { date: formatDateTime(clock.now()) })}</p>
			</div>
			<p class="text-sm font-semibold text-slate-700">{t('hygiene.history.summary', counts)}</p>
			{#if historyData.rows.length}
				<!-- on a phone the register scrolls sideways inside its card: focusable, so keyboards can scroll it too -->
				<div
					class="card overflow-x-auto p-0 print:overflow-visible print:border-0 print:shadow-none"
					role="region"
					aria-label={t('hygiene.history.label')}
					tabindex="0"
				>
					<table class="w-full text-sm">
						<caption class="sr-only">{t('hygiene.history.label')}</caption>
						<thead>
							<tr class="border-b border-slate-200 text-slate-600">
								<th scope="col" class="px-3 py-2 text-start font-semibold">{t('hygiene.history.date')}</th>
								<th scope="col" class="px-3 py-2 text-start font-semibold">{t('hygiene.history.task')}</th>
								<th scope="col" class="px-3 py-2 text-start font-semibold">{t('hygiene.history.status')}</th>
								<th scope="col" class="px-3 py-2 text-start font-semibold">{t('hygiene.history.by')}</th>
								<th scope="col" class="px-3 py-2 text-start font-semibold">{t('hygiene.history.note')}</th>
							</tr>
						</thead>
						<tbody>
							{#each historyData.rows as row (`${row.taskId}-${row.dueOn}`)}
								<tr class="border-b border-slate-100 align-top break-inside-avoid last:border-0 {row.status === 'missed' ? 'bg-rose-50/60' : ''}">
									<td class="px-3 py-2 whitespace-nowrap tabular-nums">{formatDay(row.dueOn)}</td>
									<th scope="row" class="px-3 py-2 text-start font-medium">
										<span dir="auto">{row.title}</span>{#if row.equipmentName}<span class="block text-xs font-normal text-slate-600" dir="auto">{row.equipmentName}</span>{/if}
									</th>
									<td class="px-3 py-2 {STATUS_TONE[row.status]}">
										{t(`hygiene.history.statuses.${row.status}`)}{#if row.done?.result === 'not_ok'}<span class="ms-1 rounded bg-rose-100 px-1 text-xs font-bold text-rose-900">{t('hygiene.today.notOk')}</span>{/if}
									</td>
									<td class="px-3 py-2">
										{#if row.done}<span dir="auto">{row.done.doneBy}</span>
											<span class="block text-xs text-slate-600 tabular-nums"
												>{row.late ? t('hygiene.history.late', { date: formatDay(row.done.doneAt.slice(0, 10)) }) : formatDateTime(row.done.doneAt)}</span
											>{/if}
									</td>
									<td class="px-3 py-2" dir="auto">{row.done?.note ?? ''}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{:else}
				<p class="card text-slate-700">{t('hygiene.history.empty')}</p>
			{/if}
		{:else if !error}
			<p class="card text-slate-600" aria-busy="true">{t('common.loading')}</p>
		{/if}
	{/if}
</div>

{#if editingTask && equipment}
	<TaskDialog
		task={editingTask.task}
		{equipment}
		onsaved={savedTask}
		ondeleted={(id) => ((tasks = (tasks ?? []).filter((x) => x.id !== id)), (editingTask = null))}
		onclose={() => (editingTask = null)}
	/>
{/if}
{#if editingEquipment}
	<EquipmentDialog
		item={editingEquipment.item}
		onsaved={savedEquipment}
		ondeleted={(id) => ((equipment = (equipment ?? []).filter((x) => x.id !== id)), (editingEquipment = null))}
		onclose={() => (editingEquipment = null)}
	/>
{/if}
