<script lang="ts">
	/**
	 * Search a patient by name or phone digits (`GET /api/patients?q=…&limit=8`, debounced) and pick one.
	 * Used by the appointment dialog and the waiting room ("ticket for a patient").
	 */
	import { errorText } from '../../agenda/errors';
	import Icon from './Icon.svelte';
	import { api } from '../../api';
	import { displayPhone } from '../../agenda/links';
	import { personName } from '../../agenda/format';
	import { t } from '../../i18n.svelte';
	import type { PatientPage, PatientSummary } from '../../types/patients';

	type Props = {
		onpick: (p: PatientSummary) => void;
		/** The text typed so far (e.g. to prefill a new patient). */
		query?: string;
		autofocus?: boolean;
	};
	let { onpick, query = $bindable(''), autofocus = false }: Props = $props();

	let results = $state<PatientSummary[]>([]);
	let searched = $state(false);
	let error = $state('');
	let timer: ReturnType<typeof setTimeout> | undefined;
	let seq = 0;
	const id = `ps-${Math.random().toString(36).slice(2, 8)}`;

	function changed() {
		clearTimeout(timer);
		const q = query.trim();
		if (q.length < 2) {
			results = [];
			searched = false;
			return;
		}
		timer = setTimeout(() => run(q), 200);
	}

	async function run(q: string) {
		const mine = ++seq;
		try {
			const page = await api<PatientPage>(`/api/patients?q=${encodeURIComponent(q)}&limit=8`);
			if (mine !== seq) return;
			results = page.items;
			error = '';
		} catch (err) {
			if (mine === seq) error = errorText(err);
		} finally {
			if (mine === seq) searched = true;
		}
	}
</script>

<div class="flex flex-col gap-2">
	<label class="label" for={id}>{t('agenda.form.searchPatient')}</label>
	<div class="relative">
		<span class="pointer-events-none absolute inset-y-0 start-3 flex items-center text-slate-400"><Icon name="search" /></span>
		<input
			{id}
			class="input ps-10"
			type="search"
			autocomplete="off"
			inputmode="search"
			bind:value={query}
			oninput={changed}
			data-autofocus={autofocus ? '' : undefined}
			aria-describedby="{id}-hint"
		/>
	</div>
	<p id="{id}-hint" class="text-xs text-slate-500">{t('agenda.form.searchHint')}</p>
	{#if error}<p class="text-sm text-rose-700">{error}</p>{/if}
	{#if results.length}
		<ul class="flex flex-col divide-y divide-slate-100 overflow-hidden rounded-lg border border-slate-200">
			{#each results as p (p.id)}
				<li>
					<button type="button" class="flex min-h-12 w-full flex-wrap items-center gap-x-3 gap-y-0.5 px-3 py-2 text-start hover:bg-brand-50" onclick={() => onpick(p)}>
						<span class="font-semibold">{personName(p)}</span>
						<span class="text-sm text-slate-600 tabular-nums" dir="ltr">{displayPhone(p.phone)}</span>
						{#if p.hasAlerts}<span class="rounded-full bg-rose-600 px-1.5 text-xs font-bold text-white" title={t('agenda.alert')}
								><span aria-hidden="true">!</span><span class="sr-only">{t('agenda.alert')}</span></span
							>{/if}
						{#if p.noShows >= 2}<span class="rounded-full bg-rose-100 px-2 text-xs font-semibold text-rose-800">{t('agenda.noShows', { count: p.noShows })}</span>{/if}
					</button>
				</li>
			{/each}
		</ul>
	{:else if searched && query.trim().length >= 2}
		<p class="text-sm text-slate-600">{t('agenda.form.noMatch')}</p>
	{/if}
</div>
