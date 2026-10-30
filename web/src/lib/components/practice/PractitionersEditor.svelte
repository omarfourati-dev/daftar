<script lang="ts">
	/** Practitioners of a new practice (wizard): title, name, optional own specialty. */
	import { SPECIALTIES } from '../../catalog';
	import { t } from '../../i18n.svelte';
	import { defaultTitle, type PractitionerDraft, type Problems } from '../../practice-form';

	let {
		value = $bindable(),
		specialty,
		problems = {}
	}: { value: PractitionerDraft[]; specialty: string; problems?: Problems } = $props();

	const err = (key: string) => (problems[key] ? t(problems[key].key, problems[key].params) : '');
	const uid = Math.random().toString(36).slice(2, 9);

	function add() {
		value = [...value, { title: defaultTitle(specialty), name: '', specialty: '' }];
	}
	function remove(i: number) {
		value = value.filter((_, j) => j !== i);
	}
</script>

<div class="flex flex-col gap-3">
	<p class="text-sm text-slate-600">{t('practice.practitioners.hint')}</p>
	<datalist id="titles-{uid}">
		<option value="Dr."></option>
		<option value="Pr."></option>
		<option value="M."></option>
		<option value="Mme"></option>
	</datalist>
	<ol class="flex flex-col gap-3">
		{#each value as row, i (i)}
			{@const nameError = err(`name-${i}`)}
			<li class="grid gap-3 rounded-xl border border-slate-200 bg-white p-3 sm:grid-cols-[7rem_1fr_14rem_auto] sm:items-end">
				<label class="label">
					<span aria-hidden="true">{t('practice.practitioners.title')}</span>
					<input class="input" list="titles-{uid}" bind:value={row.title} aria-label="{t('practice.practitioners.title')} {i + 1}" maxlength="20" />
				</label>
				<div class="flex flex-col gap-1">
					<label class="label">
						<span aria-hidden="true">{t('practice.practitioners.name')}</span>
						<input
							class="input"
							bind:value={row.name}
							aria-label="{t('practice.practitioners.name')} {i + 1}"
							aria-invalid={nameError ? 'true' : undefined}
							aria-describedby={nameError ? `pr-name-${uid}-${i}` : undefined}
							maxlength="120"
						/>
					</label>
					{#if nameError}<p id="pr-name-{uid}-{i}" class="text-sm font-medium text-red-700">{nameError}</p>{/if}
				</div>
				<label class="label">
					<span aria-hidden="true">{t('practice.practitioners.specialty')}</span>
					<select class="input" bind:value={row.specialty} aria-label="{t('practice.practitioners.specialty')} {i + 1}">
						<option value="">{t('practice.practitioners.samePractice')}</option>
						{#each SPECIALTIES as s (s)}<option value={s}>{t(`specialty.${s}`)}</option>{/each}
					</select>
				</label>
				<button
					type="button"
					class="inline-flex h-11 w-11 items-center justify-center rounded-lg text-slate-500 hover:bg-rose-50 hover:text-rose-700 focus-visible:outline-2 focus-visible:outline-brand-700 justify-self-end lg:self-start"
					aria-label={t('practice.practitioners.remove', { name: row.name.trim() || t('practice.practitioners.unnamed') })}
					onclick={() => remove(i)}><svg viewBox="0 0 20 20" class="h-5 w-5" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="2" stroke-linecap="round" /></svg></button
				>
			</li>
		{/each}
	</ol>
	{#if problems.list}<p role="alert" class="text-sm font-medium text-red-700">{err('list')}</p>{/if}
	<button type="button" class="btn-secondary self-start" onclick={add}><span aria-hidden="true">+</span> {t('practice.practitioners.add')}</button>
</div>
