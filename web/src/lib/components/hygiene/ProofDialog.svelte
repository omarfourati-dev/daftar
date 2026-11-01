<script lang="ts">
	/**
	 * The owner corrects a proof of the register (review N8): result and note – a Bowie-Dick test seen "non conforme"
	 * the next day – or takes it back; always with a reason. The change log keeps who, when, old → new and why; the due
	 * date stays in the register.
	 */
	import { untrack } from 'svelte';
	import { api } from '../../api';
	import { hygieneError } from '../../hygiene';
	import { formatDay, t } from '../../i18n.svelte';
	import type { HistoryRow, HygieneResult } from '../../types/hygiene';
	import Modal from '../daily/Modal.svelte';

	type Props = { row: HistoryRow; onsaved: (message: string) => void; onclose: () => void };
	let { row, onsaved, onclose }: Props = $props();

	const start = untrack(() => row);
	let result = $state<HygieneResult>(start.done?.result ?? 'ok');
	let note = $state(start.done?.note ?? '');
	let reason = $state('');
	let error = $state('');
	let busy = $state(false);

	async function send(remove: boolean) {
		if (!start.done) return;
		if (!reason.trim()) return void (error = t('hygiene.errors.reason_required'));
		busy = true;
		error = '';
		try {
			const path = `/api/hygiene/done/${start.done.id}`;
			if (remove) await api(path, { method: 'DELETE', json: { reason: reason.trim() } });
			else await api(path, { method: 'PATCH', json: { result, note: note.trim(), reason: reason.trim() } });
			onsaved(t(remove ? 'hygiene.history.deleted' : 'hygiene.history.corrected'));
		} catch (err) {
			error = hygieneError(err);
		} finally {
			busy = false;
		}
	}
</script>

<Modal title={t('hygiene.history.correctTitle')} subtitle={`${start.title} – ${formatDay(start.dueOn)}`} {onclose} guard>
	<form id="proof-form" class="flex flex-col gap-4" onsubmit={(e) => (e.preventDefault(), void send(false))} novalidate>
		<p class="text-sm text-slate-700">{t('hygiene.history.correctText')}</p>
		<fieldset class="flex flex-wrap gap-4">
			<legend class="mb-1 text-sm font-medium text-slate-700">{t('hygiene.today.result')}</legend>
			<label class="inline-flex min-h-11 items-center gap-2"
				><input type="radio" name="proof-result" value="ok" bind:group={result} class="h-5 w-5 accent-brand-700" />{t('hygiene.today.resultOk')}</label
			>
			<label class="inline-flex min-h-11 items-center gap-2"
				><input type="radio" name="proof-result" value="not_ok" bind:group={result} class="h-5 w-5 accent-rose-700" />{t('hygiene.today.resultNotOk')}</label
			>
		</fieldset>
		<label class="label">{t('hygiene.today.note')}<input class="input" bind:value={note} maxlength="500" autocomplete="off" dir="auto" /></label>
		<label class="label">{t('hygiene.history.reason')}<input class="input" bind:value={reason} maxlength="300" autocomplete="off" dir="auto" data-autofocus /></label>
		{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}
		<button type="button" class="btn-secondary min-h-11 self-start text-sm text-rose-800" disabled={busy} onclick={() => send(true)}>{t('hygiene.history.deleteProof')}</button>
	</form>
	{#snippet footer()}
		<button type="button" class="btn-secondary" onclick={onclose}>{t('common.cancel')}</button>
		<button type="submit" form="proof-form" class="btn-primary" disabled={busy}>{t('hygiene.history.saveCorrection')}</button>
	{/snippet}
</Modal>
