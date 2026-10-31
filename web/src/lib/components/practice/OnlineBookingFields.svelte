<script lang="ts">
	/** Online booking switches and limits (section 11.2). Numbers are bound as numbers. */
	import { t } from '../../i18n.svelte';
	import type { OnlineBooking } from '../../online-booking';
	import type { Problems } from '../../practice-form';

	let { value = $bindable(), problems = {} }: { value: OnlineBooking; problems?: Problems } = $props();
	const err = (field: string) => (problems[field] ? t(problems[field].key, problems[field].params) : '');
	const uid = Math.random().toString(36).slice(2, 9);

	type NumberField = { key: 'horizonDays' | 'minNoticeHours' | 'maxPerDay' | 'blockNoShows'; label: string; hint?: string };
	const numbers = $derived<NumberField[]>([
		{ key: 'horizonDays', label: t('practice.online.horizonDays') },
		{ key: 'minNoticeHours', label: t('practice.online.minNoticeHours') },
		{ key: 'maxPerDay', label: t('practice.online.maxPerDay') },
		{ key: 'blockNoShows', label: t('practice.online.blockNoShows'), hint: t('practice.online.blockHint') }
	]);
</script>

<div class="flex flex-col gap-4">
	{#each [{ key: 'enabled', label: t('practice.online.enabled'), hint: t('practice.online.enabledHint') }, { key: 'autoConfirm', label: t('practice.online.autoConfirm'), hint: t('practice.online.autoConfirmHint') }] as toggle (toggle.key)}
		<div class="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-4">
			{#if toggle.key === 'enabled'}
				<input
					id="ob-{toggle.key}-{uid}"
					type="checkbox"
					class="mt-0.5 h-5 w-5 shrink-0 accent-brand-700"
					bind:checked={value.enabled}
					aria-describedby="ob-{toggle.key}-{uid}-hint"
				/>
			{:else}
				<input
					id="ob-{toggle.key}-{uid}"
					type="checkbox"
					class="mt-0.5 h-5 w-5 shrink-0 accent-brand-700"
					bind:checked={value.autoConfirm}
					aria-describedby="ob-{toggle.key}-{uid}-hint"
				/>
			{/if}
			<div class="flex flex-col gap-0.5">
				<label for="ob-{toggle.key}-{uid}" class="cursor-pointer font-semibold text-ink">{toggle.label}</label>
				<p id="ob-{toggle.key}-{uid}-hint" class="text-sm text-slate-600">{toggle.hint}</p>
			</div>
		</div>
	{/each}
	<div class="grid gap-4 sm:grid-cols-2">
		{#each numbers as field (field.key)}
			{@const error = err(field.key)}
			<div class="flex flex-col gap-1">
				<label for="ob-{field.key}-{uid}" class="text-sm font-medium text-slate-700">{field.label}</label>
				<input
					id="ob-{field.key}-{uid}"
					class="input w-32"
					type="number"
					inputmode="numeric"
					dir="ltr"
					min="0"
					bind:value={value[field.key]}
					aria-invalid={error ? 'true' : undefined}
					aria-describedby={[field.hint ? `ob-${field.key}-${uid}-hint` : '', error ? `ob-${field.key}-${uid}-error` : ''].filter(Boolean).join(' ') ||
						undefined}
				/>
				{#if field.hint}<p id="ob-{field.key}-{uid}-hint" class="text-sm text-slate-600">{field.hint}</p>{/if}
				{#if error}<p id="ob-{field.key}-{uid}-error" class="text-sm font-medium text-red-700">{error}</p>{/if}
			</div>
		{/each}
	</div>
</div>
