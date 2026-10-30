<script lang="ts">
	/** Opening hours (same editor as the admin wizard) and exceptional closures (holidays, days off). */
	import { onMount } from 'svelte';
	import { api, apiErrorMessage } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { hoursProblems, normalizeWeeklyHours, sortedWeeklyHours, type WeeklyHours } from '#lib/hours';
	import { formatDay, t, todayTunis } from '#lib/i18n.svelte';
	import type { Closure, Practice } from '#lib/types/practice';
	import HoursEditor from '../../../../lib/components/HoursEditor.svelte';
	import LoadState from '../../../../lib/components/LoadState.svelte';
	import OwnerOnly from '../../../../lib/components/reglages/OwnerOnly.svelte';

	let hours = $state<WeeklyHours | null>(null);
	let saved = '';
	let closures = $state<Closure[]>([]);
	let loading = $state(true);
	let error = $state('');
	let notice = $state('');
	let hoursError = $state('');
	let busy = $state(false);

	let from = $state('');
	let to = $state('');
	let label = $state('');
	let closureErrors = $state<{ from?: string; to?: string; form?: string }>({});
	let closureNotice = $state('');

	async function load() {
		loading = true;
		error = '';
		try {
			const [practice, list] = await Promise.all([api<Practice>('/api/practice'), api<Closure[]>('/api/closures')]);
			hours = normalizeWeeklyHours(practice.weeklyHours);
			saved = JSON.stringify(sortedWeeklyHours(hours));
			closures = list;
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			loading = false;
		}
	}
	onMount(() => {
		if (auth.user?.role === 'owner') void load();
	});

	async function saveHours() {
		if (!hours) return;
		notice = '';
		hoursError = '';
		if (Object.keys(hoursProblems(hours)).length) {
			hoursError = t('kit.hours.fixFirst');
			return;
		}
		const weeklyHours = sortedWeeklyHours(hours);
		if (JSON.stringify(weeklyHours) === saved) {
			notice = t('admin.edit.nothingToSave');
			return;
		}
		busy = true;
		try {
			await api<Practice>('/api/practice', { method: 'PATCH', json: { weeklyHours } });
			saved = JSON.stringify(weeklyHours);
			notice = t('kit.saved');
		} catch (err) {
			hoursError = apiErrorMessage(err);
		} finally {
			busy = false;
		}
	}

	const today = $derived(todayTunis());
	const sorted = $derived([...closures].sort((a, b) => (a.startsOn < b.startsOn ? -1 : 1)));
	const upcoming = $derived(sorted.filter((c) => c.endsOn >= today));
	const past = $derived(sorted.filter((c) => c.endsOn < today).reverse());
	const when = (c: Closure) =>
		c.startsOn === c.endsOn ? t('reglages.horaires.single', { date: formatDay(c.startsOn) }) : t('reglages.horaires.range', { from: formatDay(c.startsOn), to: formatDay(c.endsOn) });
	const whenIn = (c: Closure) =>
		c.startsOn === c.endsOn
			? t('reglages.horaires.singleIn', { date: formatDay(c.startsOn) })
			: t('reglages.horaires.rangeIn', { from: formatDay(c.startsOn), to: formatDay(c.endsOn) });

	async function addClosure(e: SubmitEvent) {
		e.preventDefault();
		closureNotice = '';
		closureErrors = {};
		const end = to || from;
		if (!from) closureErrors.from = t('kit.fieldRequired');
		else if (end < from) closureErrors.to = t('reglages.horaires.endBeforeStart');
		if (Object.keys(closureErrors).length) return;
		try {
			const created = await api<Closure & { affectedAppointments?: number }>('/api/closures', {
				method: 'POST',
				json: { startsOn: from, endsOn: end, label: label.trim() }
			});
			const { affectedAppointments = 0, ...closure } = created;
			closures = [...closures, closure];
			from = to = label = '';
			closureNotice = affectedAppointments
				? `${t('reglages.horaires.added')} ${t('reglages.horaires.affected', { n: affectedAppointments })}`
				: t('reglages.horaires.added');
		} catch (err) {
			closureErrors = { form: apiErrorMessage(err) };
		}
	}

	async function removeClosure(c: Closure) {
		closureNotice = '';
		try {
			await api(`/api/closures/${c.id}`, { method: 'DELETE' });
			closures = closures.filter((x) => x.id !== c.id);
			closureNotice = t('reglages.horaires.removed');
		} catch (err) {
			closureErrors = { form: apiErrorMessage(err) };
		}
	}
</script>

<OwnerOnly>
	<div class="flex flex-col gap-6">
		<section class="flex flex-col gap-4" aria-labelledby="h-hours">
			<h2 id="h-hours" class="text-xl font-bold text-ink">{t('reglages.horaires.title')}</h2>
			<p class="max-w-2xl text-slate-600">{t('reglages.horaires.intro')}</p>
			<LoadState {loading} {error} onretry={load} />
			{#if hours}
				<HoursEditor bind:value={hours} />
				<div class="flex flex-wrap items-center gap-3">
					<button type="button" class="btn-primary" disabled={busy} onclick={saveHours}>{t('reglages.horaires.save')}</button>
					<p role="status" class="text-sm font-medium text-brand-800">{notice}</p>
					{#if hoursError}<p role="alert" class="text-sm font-medium text-red-700">{hoursError}</p>{/if}
				</div>
			{/if}
		</section>

		{#if !loading && !error}
			<section class="card flex flex-col gap-4" aria-labelledby="h-closures">
				<h2 id="h-closures" class="text-lg font-bold text-ink">{t('reglages.horaires.closures')}</h2>
				<p class="text-sm text-slate-600">{t('reglages.horaires.closuresIntro')}</p>
				{#if upcoming.length === 0}
					<p class="text-slate-600">{t('reglages.horaires.none')}</p>
				{/if}
				<ul aria-label={t('reglages.horaires.closures')} class="flex flex-col divide-y divide-slate-100">
					{#each upcoming as c (c.id)}
						<li class="flex items-center gap-3 py-2">
							<div class="flex min-w-0 flex-1 flex-col">
								<span class="font-semibold tabular-nums text-ink">{when(c)}</span>
								{#if c.label}<span class="text-sm text-slate-600">{c.label}</span>{/if}
							</div>
							<button
								type="button"
								class="inline-flex h-11 w-11 items-center justify-center rounded-lg text-slate-500 hover:bg-rose-50 hover:text-rose-700"
								aria-label={t('reglages.horaires.remove', { when: whenIn(c) })}
								onclick={() => removeClosure(c)}
							>
								<svg viewBox="0 0 20 20" class="h-5 w-5" aria-hidden="true"
									><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="2" stroke-linecap="round" /></svg
								>
							</button>
						</li>
					{/each}
				</ul>
				{#if past.length}
					<details class="text-sm text-slate-600">
						<summary class="cursor-pointer py-1 font-medium">{t('reglages.horaires.past')}</summary>
						<ul class="mt-1 flex flex-col gap-1 ps-4">
							{#each past as c (c.id)}<li><span class="tabular-nums">{when(c)}</span>{c.label ? ` – ${c.label}` : ''}</li>{/each}
						</ul>
					</details>
				{/if}
				<form class="grid gap-3 rounded-xl bg-slate-50 p-3 sm:grid-cols-[10rem_10rem_minmax(0,1fr)_auto] sm:items-end" novalidate onsubmit={addClosure}>
					<div class="flex flex-col gap-1">
						<label for="cl-from" class="text-sm font-medium text-slate-700">{t('reglages.horaires.from')}</label>
						<input
							id="cl-from"
							type="date"
							class="input"
							min={today}
							bind:value={from}
							aria-invalid={closureErrors.from ? 'true' : undefined}
							aria-describedby={closureErrors.from ? 'cl-from-error' : undefined}
						/>
						{#if closureErrors.from}<p id="cl-from-error" class="text-sm font-medium text-red-700">{closureErrors.from}</p>{/if}
					</div>
					<div class="flex flex-col gap-1">
						<label for="cl-to" class="text-sm font-medium text-slate-700">{t('reglages.horaires.to')}</label>
						<input
							id="cl-to"
							type="date"
							class="input"
							min={from || today}
							bind:value={to}
							aria-invalid={closureErrors.to ? 'true' : undefined}
							aria-describedby={closureErrors.to ? 'cl-to-error' : undefined}
						/>
						{#if closureErrors.to}<p id="cl-to-error" class="text-sm font-medium text-red-700">{closureErrors.to}</p>{/if}
					</div>
					<label class="label">
						<span>{t('reglages.horaires.label')} <span class="font-normal text-slate-500">({t('kit.optional')})</span></span>
						<input class="input" bind:value={label} maxlength="120" placeholder={t('reglages.horaires.labelPlaceholder')} />
					</label>
					<button type="submit" class="btn-secondary">{t('reglages.horaires.add')}</button>
				</form>
				<p role="status" class="text-sm font-medium text-brand-800">{closureNotice}</p>
				{#if closureErrors.form}<p role="alert" class="text-sm font-medium text-red-700">{closureErrors.form}</p>{/if}
			</section>
		{/if}
	</div>
</OwnerOnly>
