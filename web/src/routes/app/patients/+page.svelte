<script lang="ts">
	/**
	 * /app/patients – the patient list (story E1): search by name or phone digits (`?q=`), next appointment, no-shows,
	 * alert and what is owed per row, 50 at a time; "Nouveau patient" opens the form and then the new file.
	 */
	import { onMount } from 'svelte';
	import { api, deps } from '#lib/api';
	import { money, personName, slotLabel } from '#lib/agenda/format';
	import { displayPhone } from '#lib/agenda/links';
	import { t } from '#lib/i18n.svelte';
	import type { Patient, PatientPage, PatientSummary } from '#lib/types/patients';
	import Icon from '../../../lib/components/daily/Icon.svelte';
	import PatientForm from '../../../lib/components/patients/PatientForm.svelte';

	const PAGE = 50;
	let query = $state(new URLSearchParams(location.search).get('q') ?? '');
	let items = $state<PatientSummary[]>([]);
	let total = $state(0);
	let loaded = $state(false);
	let error = $state('');
	let adding = $state(false);
	let searched = $state('');
	let timer: ReturnType<typeof setTimeout> | undefined;
	let seq = 0;

	async function load(offset = 0) {
		const mine = ++seq;
		const q = query.trim();
		try {
			const page = await api<PatientPage>(`/api/patients?q=${encodeURIComponent(q)}&limit=${PAGE}&offset=${offset}`);
			if (mine !== seq) return;
			items = offset ? [...items, ...page.items] : page.items;
			total = page.total;
			searched = q;
			error = '';
		} catch {
			if (mine === seq) error = t('patients.loadError');
		} finally {
			if (mine === seq) loaded = true;
		}
	}

	onMount(() => void load());

	function changed() {
		clearTimeout(timer);
		timer = setTimeout(() => void load(), 250);
	}

	function created(p: Patient) {
		adding = false;
		void deps.goto(`/app/patients/${p.id}`);
	}
</script>

<svelte:head><title>{t('patients.title')} · Daftar</title></svelte:head>

<div class="flex flex-col gap-5">
	<div class="flex flex-wrap items-end justify-between gap-3">
		<div>
			<h1 class="text-2xl font-bold">{t('patients.title')}</h1>
			{#if loaded && !error}<p class="text-slate-600">{t('patients.count', { count: total })}</p>{/if}
		</div>
		<button type="button" class="btn-primary" onclick={() => (adding = true)}><Icon name="plus" />{t('patients.add')}</button>
	</div>

	<div class="relative max-w-xl">
		<span class="pointer-events-none absolute inset-y-0 start-3 flex items-center text-slate-400"><Icon name="search" /></span>
		<input
			type="search"
			class="input min-h-12 ps-11 text-base"
			aria-label={t('patients.search')}
			placeholder={t('patients.search')}
			bind:value={query}
			oninput={changed}
			autocomplete="off"
		/>
	</div>

	{#if error}
		<div role="alert" class="card flex flex-wrap items-center justify-between gap-3 border-rose-200 bg-rose-50 text-rose-900">
			<p>{error}</p>
			<button type="button" class="btn-secondary" onclick={() => load()}>{t('common.retry')}</button>
		</div>
	{:else if !loaded}
		<p class="card text-slate-600" aria-busy="true">{t('common.loading')}</p>
	{:else if !items.length}
		<div class="card flex flex-col items-start gap-3 py-8">
			{#if searched}
				<p class="text-lg font-semibold">{t('patients.noMatch', { q: searched })}</p>
			{:else}
				<p class="text-lg font-semibold">{t('patients.empty')}</p>
				<p class="text-slate-600">{t('patients.emptyHint')}</p>
				<a class="btn-secondary" href="/app/import">{t('patients.import')}</a>
			{/if}
		</div>
	{:else}
		<div class="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
			<div
				class="hidden grid-cols-[minmax(0,2fr)_minmax(0,1.3fr)_minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)] gap-3 border-b border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold text-slate-600 md:grid"
				aria-hidden="true"
			>
				<span>{t('patients.columns.name')}</span><span>{t('patients.columns.phone')}</span><span>{t('patients.columns.next')}</span><span
					>{t('patients.columns.reliability')}</span
				><span class="text-end">{t('patients.columns.due')}</span>
			</div>
			<ul class="divide-y divide-slate-100">
				{#each items as p (p.id)}
					<li>
						<a
							href="/app/patients/{p.id}"
							class="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1 px-4 py-3 hover:bg-brand-50/50 md:grid-cols-[minmax(0,2fr)_minmax(0,1.3fr)_minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)] md:items-center"
						>
							<span class="flex min-w-0 items-center gap-2 font-semibold">
								<span class="truncate">{personName(p)}</span>
								{#if p.hasAlerts}<span class="inline-grid h-5 min-w-5 place-items-center rounded-full bg-rose-600 px-1 text-xs font-bold text-white"
										><span aria-hidden="true">!</span><span class="sr-only">{t('agenda.alert')}</span></span
									>{/if}
							</span>
							<span class="text-sm text-slate-600 tabular-nums md:order-none" dir="ltr">{displayPhone(p.phone)}</span>
							<span class="text-sm text-slate-600 first-letter:uppercase">{p.nextAppointmentAt ? slotLabel(p.nextAppointmentAt) : ''}</span>
							<span class="text-sm">
								{#if p.noShows >= 2}<span class="rounded-full bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-800">{t('agenda.noShows', { count: p.noShows })}</span>{/if}
							</span>
							<span class="text-sm font-semibold tabular-nums md:text-end {p.dueMillimes > 0 ? 'text-rose-800' : 'text-slate-400'}"
								>{p.dueMillimes > 0 ? money(p.dueMillimes) : ''}</span
							>
						</a>
					</li>
				{/each}
			</ul>
		</div>
		{#if items.length < total}
			<button type="button" class="btn-secondary self-center" onclick={() => load(items.length)}>{t('patients.more')}</button>
		{/if}
	{/if}
</div>

{#if adding}
	<PatientForm onsaved={created} onclose={() => (adding = false)} />
{/if}
