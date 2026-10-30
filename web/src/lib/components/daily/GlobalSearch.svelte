<script lang="ts">
	/**
	 * Patient search in the header (story B7): name or phone digits, results as you type, arrows + Enter to open a
	 * file, the last option opens the full list. The key `/` focuses it from anywhere (Shortcuts.svelte).
	 * Combobox pattern (ARIA 1.2): the input owns a listbox; the active option is `aria-activedescendant`.
	 */
	import Icon from './Icon.svelte';
	import { api, deps } from '../../api';
	import { personName } from '../../agenda/format';
	import { displayPhone } from '../../agenda/links';
	import { t } from '../../i18n.svelte';
	import type { PatientPage, PatientSummary } from '../../types/patients';

	let query = $state('');
	let results = $state<PatientSummary[]>([]);
	let open = $state(false);
	let searched = $state(false);
	let active = $state(-1);
	let timer: ReturnType<typeof setTimeout> | undefined;
	let seq = 0;

	const allHref = $derived(`/app/patients?q=${encodeURIComponent(query.trim())}`);
	/** Options: the patients, then "all results". */
	const count = $derived(results.length + 1);

	function changed() {
		clearTimeout(timer);
		const q = query.trim();
		active = -1;
		if (q.length < 2) {
			open = false;
			results = [];
			return;
		}
		timer = setTimeout(() => search(q), 200);
	}

	async function search(q: string) {
		const mine = ++seq;
		try {
			const page = await api<PatientPage>(`/api/patients?q=${encodeURIComponent(q)}&limit=8`);
			if (mine !== seq) return;
			results = page.items;
		} catch {
			if (mine === seq) results = [];
		}
		if (mine === seq) {
			searched = true;
			open = true;
		}
	}

	function go(href: string) {
		open = false;
		query = '';
		results = [];
		active = -1;
		void deps.goto(href);
	}

	function choose(index: number) {
		if (index < 0) return;
		go(index < results.length ? `/app/patients/${results[index].id}` : allHref);
	}

	function keydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			open = false;
			active = -1;
			return;
		}
		if (!open) return;
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			active = (active + 1) % count;
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			active = active <= 0 ? count - 1 : active - 1;
		} else if (e.key === 'Enter') {
			e.preventDefault();
			choose(active < 0 ? (results.length === 1 ? 0 : results.length) : active);
		}
	}
</script>

<div class="relative w-full max-w-sm">
	<label for="global-search" class="sr-only">{t('patients.globalSearch')}</label>
	<span class="pointer-events-none absolute inset-y-0 start-3 flex items-center text-slate-400"><Icon name="search" class="h-4 w-4" /></span>
	<input
		id="global-search"
		type="search"
		role="combobox"
		autocomplete="off"
		aria-expanded={open}
		aria-controls="global-search-list"
		aria-autocomplete="list"
		aria-activedescendant={open && active >= 0 ? `global-search-${active}` : undefined}
		placeholder={t('patients.globalSearchHint')}
		class="min-h-10 w-full rounded-lg border border-slate-300 bg-slate-50 ps-9 pe-3 text-sm text-ink placeholder:text-slate-500 focus-visible:border-brand-700 focus-visible:bg-white focus-visible:outline-2 focus-visible:outline-brand-700"
		bind:value={query}
		oninput={changed}
		onkeydown={keydown}
		onblur={() => setTimeout(() => (open = false), 150)}
	/>
	{#if open}
		<ul
			id="global-search-list"
			role="listbox"
			aria-label={t('patients.globalSearch')}
			class="absolute inset-x-0 top-full z-40 mt-1 max-h-96 overflow-y-auto rounded-xl border border-slate-200 bg-white py-1 shadow-xl"
		>
			{#if searched && !results.length}
				<li class="px-3 py-2 text-sm text-slate-600" role="presentation">{t('patients.globalSearchEmpty')}</li>
			{/if}
			{#each results as p, i (p.id)}
				<!-- svelte-ignore a11y_click_events_have_key_events (keyboard: arrows + Enter on the combobox input) -->
				<li
					id="global-search-{i}"
					role="option"
					aria-selected={active === i}
					class="flex cursor-pointer flex-wrap items-baseline gap-x-2 px-3 py-2 {active === i ? 'bg-brand-50' : 'hover:bg-slate-50'}"
					onmousedown={(e) => e.preventDefault()}
					onclick={() => choose(i)}
				>
					<span class="font-semibold">{personName(p)}</span>
					<span class="text-sm text-slate-600 tabular-nums" dir="ltr">{displayPhone(p.phone)}</span>
				</li>
			{/each}
			<!-- svelte-ignore a11y_click_events_have_key_events (keyboard: arrows + Enter on the combobox input) -->
			<li
				id="global-search-{results.length}"
				role="option"
				aria-selected={active === results.length}
				class="cursor-pointer border-t border-slate-100 px-3 py-2 text-sm font-semibold text-brand-800 {active === results.length ? 'bg-brand-50' : 'hover:bg-slate-50'}"
				onmousedown={(e) => e.preventDefault()}
				onclick={() => choose(results.length)}
			>
				{t('patients.globalSearchAll', { q: query.trim() })}
			</li>
		</ul>
	{/if}
</div>
