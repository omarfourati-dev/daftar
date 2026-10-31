<script lang="ts">
	/** "Supprimer l’acte ?" – a question, its consequence and a button named after the action. */
	import Modal from './Modal.svelte';
	import { t } from '../i18n.svelte';

	let {
		open,
		title,
		message,
		confirmLabel,
		danger = false,
		busy = false,
		typeToConfirm,
		error = '',
		onconfirm,
		oncancel = () => {}
	}: {
		open: boolean;
		title: string;
		message: string;
		confirmLabel: string;
		danger?: boolean;
		busy?: boolean;
		/** the user must type this text (e.g. the practice name) before the button works */
		typeToConfirm?: string;
		error?: string;
		onconfirm: () => void;
		oncancel?: () => void;
	} = $props();

	let typed = $state('');
	const ready = $derived(!typeToConfirm || typed.trim() === typeToConfirm.trim());

	$effect(() => {
		if (!open) typed = '';
	});
</script>

<Modal {open} {title} onclose={oncancel}>
	<p class="text-slate-700">{message}</p>
	{#if typeToConfirm}
		<label class="label">
			{t('kit.typeToConfirm', { text: typeToConfirm })}
			<input class="input" bind:value={typed} autocomplete="off" />
		</label>
	{/if}
	{#if error}<p role="alert" class="text-sm text-red-700">{error}</p>{/if}
	<div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
		<button type="button" class="btn-secondary" onclick={oncancel}>{t('common.cancel')}</button>
		<button
			type="button"
			class={danger ? 'btn bg-rose-700 text-white hover:bg-rose-800' : 'btn-primary'}
			disabled={!ready || busy}
			onclick={onconfirm}>{confirmLabel}</button
		>
	</div>
</Modal>
