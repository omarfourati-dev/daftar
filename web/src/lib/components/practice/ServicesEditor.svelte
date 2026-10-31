<script lang="ts">
	/** Acts and prices of a new practice (wizard): name FR/AR, duration, optional price in dinars, bookable online. */
	import { t } from '../../i18n.svelte';
	import type { Problems, ServiceDraft } from '../../practice-form';

	let {
		value = $bindable(),
		problems = {},
		onedit
	}: { value: ServiceDraft[]; problems?: Problems; onedit?: () => void } = $props();

	const err = (key: string) => (problems[key] ? t(problems[key].key, problems[key].params) : '');
	const uid = Math.random().toString(36).slice(2, 9);

	function add() {
		value = [...value, { nameFr: '', nameAr: '', durationMin: '30', priceText: '', onlineBookable: false }];
		onedit?.();
	}
	function remove(i: number) {
		value = value.filter((_, j) => j !== i);
		onedit?.();
	}
	const described = (key: string) => (err(key) ? `sv-${uid}-${key}` : undefined);
</script>

<div class="flex flex-col gap-3">
	<div
		class="hidden gap-3 px-3 text-sm font-medium text-slate-600 lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_6rem_7rem_5rem_auto]"
		aria-hidden="true"
	>
		<span>{t('practice.services.nameFr')}</span><span>{t('practice.services.nameAr')}</span><span>{t('practice.services.duration')}</span><span
			>{t('practice.services.price')}</span
		><span>{t('practice.services.online')}</span><span class="w-11"></span>
	</div>
	<ol class="flex flex-col gap-3">
		{#each value as row, i (i)}
			<li
				class="grid grid-cols-2 gap-3 rounded-xl border border-slate-200 bg-white p-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_6rem_7rem_5rem_auto] lg:items-start"
			>
				<div class="col-span-2 flex flex-col gap-1 lg:col-span-1">
					<span class="text-xs font-medium text-slate-600 lg:hidden" aria-hidden="true">{t('practice.services.nameFr')}</span>
					<input
						class="input"
						bind:value={row.nameFr}
						oninput={() => onedit?.()}
						aria-label="{t('practice.services.nameFr')} {i + 1}"
						aria-invalid={err(`nameFr-${i}`) ? 'true' : undefined}
						aria-describedby={described(`nameFr-${i}`)}
						maxlength="120"
					/>
					{#if err(`nameFr-${i}`)}<p id="sv-{uid}-nameFr-{i}" class="text-sm font-medium text-red-700">{err(`nameFr-${i}`)}</p>{/if}
				</div>
				<div class="col-span-2 flex flex-col gap-1 lg:col-span-1">
					<span class="text-xs font-medium text-slate-600 lg:hidden" aria-hidden="true">{t('practice.services.nameAr')}</span>
					<input class="input" dir="rtl" bind:value={row.nameAr}
						oninput={() => onedit?.()} aria-label="{t('practice.services.nameAr')} {i + 1}" maxlength="120" />
				</div>
				<div class="flex flex-col gap-1">
					<span class="text-xs font-medium text-slate-600 lg:hidden" aria-hidden="true">{t('practice.services.duration')}</span>
					<input
						class="input"
						inputmode="numeric"
						dir="ltr"
						bind:value={row.durationMin}
						oninput={() => onedit?.()}
						aria-label="{t('practice.services.duration')} {i + 1}"
						aria-invalid={err(`durationMin-${i}`) ? 'true' : undefined}
						aria-describedby={described(`durationMin-${i}`)}
					/>
					{#if err(`durationMin-${i}`)}<p id="sv-{uid}-durationMin-{i}" class="text-sm font-medium text-red-700">
							{err(`durationMin-${i}`)}
						</p>{/if}
				</div>
				<div class="flex flex-col gap-1">
					<span class="text-xs font-medium text-slate-600 lg:hidden" aria-hidden="true">{t('practice.services.price')}</span>
					<input
						class="input"
						inputmode="decimal"
						dir="ltr"
						placeholder={t('practice.services.pricePlaceholder')}
						bind:value={row.priceText}
						oninput={() => onedit?.()}
						aria-label="{t('practice.services.price')} {i + 1}"
						aria-invalid={err(`price-${i}`) ? 'true' : undefined}
						aria-describedby={described(`price-${i}`)}
					/>
					{#if err(`price-${i}`)}<p id="sv-{uid}-price-{i}" class="text-sm font-medium text-red-700">{err(`price-${i}`)}</p>{/if}
				</div>
				<label class="flex min-h-11 cursor-pointer items-center gap-2 text-sm font-medium text-slate-700">
					<input
						type="checkbox"
						class="h-5 w-5 accent-brand-700"
						bind:checked={row.onlineBookable}
						aria-label="{t('practice.services.onlineLong')} {i + 1}"
						onchange={() => onedit?.()}
					/>
					<span aria-hidden="true" class="lg:sr-only">{t('practice.services.onlineLong')}</span>
				</label>
				<button
					type="button"
					class="inline-flex h-11 w-11 items-center justify-center rounded-lg text-slate-500 hover:bg-rose-50 hover:text-rose-700 focus-visible:outline-2 focus-visible:outline-brand-700 justify-self-end lg:self-start"
					aria-label={t('practice.services.remove', { name: row.nameFr.trim() || t('practice.services.unnamed') })}
					onclick={() => remove(i)}><svg viewBox="0 0 20 20" class="h-5 w-5" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="2" stroke-linecap="round" /></svg></button
				>
			</li>
		{/each}
	</ol>
	{#if problems.list}<p role="alert" class="text-sm font-medium text-red-700">{err('list')}</p>{/if}
	<button type="button" class="btn-secondary self-start" onclick={add}><span aria-hidden="true">+</span> {t('practice.services.add')}</button>
</div>
