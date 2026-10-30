<script lang="ts">
	/**
	 * Label + input/textarea/select + hint + error at the field (aria-invalid, aria-describedby). Optional fields
	 * carry "(facultatif)"; required ones are not decorated (most fields are required).
	 */
	import { t } from '../../i18n.svelte';

	type Option = { value: string; label: string };
	let {
		label,
		value = $bindable(),
		error = '',
		hint = '',
		optional = false,
		type = 'text',
		multiline = false,
		rows = 3,
		options,
		placeholder,
		dir,
		autocomplete,
		inputmode,
		maxlength,
		min,
		max,
		step,
		id = `f-${Math.random().toString(36).slice(2, 9)}`,
		class: klass = ''
	}: {
		label: string;
		value: string | number | null | undefined;
		error?: string;
		hint?: string;
		optional?: boolean;
		type?: string;
		multiline?: boolean;
		rows?: number;
		options?: Option[];
		placeholder?: string;
		dir?: 'ltr' | 'rtl' | 'auto';
		autocomplete?: AutoFill;
		inputmode?: 'text' | 'tel' | 'email' | 'numeric' | 'decimal' | 'url';
		maxlength?: number;
		min?: number | string;
		max?: number | string;
		step?: number | string;
		id?: string;
		class?: string;
	} = $props();

	const hintId = $derived(hint ? `${id}-hint` : '');
	const errorId = $derived(error ? `${id}-error` : '');
	const describedby = $derived([hintId, errorId].filter(Boolean).join(' ') || undefined);
</script>

<div class="flex flex-col gap-1 {klass}">
	<label for={id} class="text-sm font-medium text-slate-700">
		{label}
		{#if optional}<span class="font-normal text-slate-500">({t('kit.optional')})</span>{/if}
	</label>
	{#if options}
		<select {id} class="input" bind:value aria-invalid={error ? 'true' : undefined} aria-describedby={describedby}>
			{#each options as option (option.value)}
				<option value={option.value}>{option.label}</option>
			{/each}
		</select>
	{:else if multiline}
		<textarea
			{id}
			class="input min-h-24"
			{rows}
			{placeholder}
			{dir}
			{maxlength}
			bind:value
			aria-invalid={error ? 'true' : undefined}
			aria-describedby={describedby}
		></textarea>
	{:else}
		<input
			{id}
			class="input"
			{type}
			{placeholder}
			{dir}
			{autocomplete}
			{inputmode}
			{maxlength}
			{min}
			{max}
			{step}
			bind:value
			aria-invalid={error ? 'true' : undefined}
			aria-describedby={describedby}
		/>
	{/if}
	{#if hint}<p id={hintId} class="text-sm text-slate-600">{hint}</p>{/if}
	{#if error}<p id={errorId} class="text-sm font-medium text-red-700">{error}</p>{/if}
</div>
