<script lang="ts">
	/** "Une idée ? Un problème ?" in the app shell (story J2): a short message with the current page → admin. */
	import { api, apiErrorMessage } from '../api';
	import { t } from '../i18n.svelte';
	import Modal from './Modal.svelte';

	/** `menu`: a full-width row for the phone's "Plus" sheet; `icon`: the header button */
	let { path, variant = 'icon' }: { path: string; variant?: 'icon' | 'menu' } = $props();
	const MAX = 2000;
	let open = $state(false);
	let message = $state('');
	let error = $state('');
	let fieldError = $state('');
	let sent = $state(false);
	let busy = $state(false);

	function show() {
		sent = false;
		error = '';
		fieldError = '';
		open = true;
	}

	async function send(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		fieldError = message.trim() ? '' : t('feedback.empty');
		if (fieldError) return;
		busy = true;
		try {
			await api('/api/feedback', { method: 'POST', json: { message: message.trim(), page: path } });
			sent = true;
			message = '';
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			busy = false;
		}
	}
</script>

<button
	type="button"
	class={variant === 'menu'
		? 'flex w-full items-center gap-2 rounded-lg px-3 py-3 text-start font-medium text-slate-700'
		: 'hidden min-h-9 items-center gap-1.5 rounded-lg px-2 text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-ink focus-visible:outline-2 focus-visible:outline-brand-700 md:inline-flex'}
	aria-label={t('feedback.button')}
	onclick={show}
>
	<svg viewBox="0 0 20 20" class="h-5 w-5" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7"
		><path d="M4 4h12v9H8l-4 3z" stroke-linejoin="round" /></svg
	>
	<span class={variant === 'menu' ? '' : 'hidden lg:inline'}>{t('feedback.button')}</span>
</button>

<Modal {open} title={t('feedback.title')} onclose={() => (open = false)}>
	{#if sent}
		<p role="status" class="rounded-lg bg-brand-50 px-3 py-2 font-medium text-brand-900">{t('feedback.sent')}</p>
		<button type="button" class="btn-secondary self-end" onclick={() => (open = false)}>{t('common.close')}</button>
	{:else}
		<form class="flex flex-col gap-3" novalidate onsubmit={send}>
			<p class="text-sm text-slate-600">{t('feedback.intro')}</p>
			<label for="feedback-message" class="text-sm font-medium text-slate-700">{t('feedback.message')}</label>
			<textarea
				id="feedback-message"
				class="input min-h-32"
				rows="5"
				maxlength={MAX}
				bind:value={message}
				aria-invalid={fieldError ? 'true' : undefined}
				aria-describedby="feedback-count{fieldError ? ' feedback-error' : ''}"
			></textarea>
			<div class="flex justify-between gap-3 text-sm">
				{#if fieldError}<p id="feedback-error" class="font-medium text-red-700">{fieldError}</p>{:else}<span></span>{/if}
				<span id="feedback-count" class="text-slate-500 tabular-nums" dir="ltr">{t('feedback.count', { n: message.length })}</span>
			</div>
			{#if error}<p role="alert" class="text-sm font-medium text-red-700">{error}</p>{/if}
			<div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
				<button type="button" class="btn-secondary" onclick={() => (open = false)}>{t('common.cancel')}</button>
				<button type="submit" class="btn-primary" disabled={busy}>{busy ? t('feedback.sending') : t('feedback.send')}</button>
			</div>
		</form>
	{/if}
</Modal>
