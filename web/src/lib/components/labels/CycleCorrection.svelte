<script lang="ts">
	/**
	 * The owner corrects a cycle – a biological indicator read "non conforme" the next day recalls its packs – or cancels
	 * a cycle entered by mistake (only while none of its packs was used): it stays in the register with its number, its
	 * codes are never given again, its printed labels are to be thrown away (review H1). Always with a reason; the
	 * change log keeps who, when, old → new and why.
	 */
	import { untrack } from 'svelte';
	import { api } from '../../api';
	import { formatDate, t } from '../../i18n.svelte';
	import { labelsError } from '../../labels';
	import type { Cycle, CycleResult } from '../../types/labels';
	import Modal from '../daily/Modal.svelte';

	type Props = { cycle: Cycle; onsaved: (message: string, cycle: Cycle | null) => void; onclose: () => void };
	let { cycle, onsaved, onclose }: Props = $props();

	const start = untrack(() => cycle);
	let result = $state<CycleResult>(start.result);
	let program = $state(start.program);
	let note = $state(start.note);
	let reason = $state('');
	let error = $state('');
	let busy = $state(false);
	/** "Annuler ce cycle…" was tapped: the consequences and the last button are shown. */
	let cancelling = $state(false);
	const used = start.packs.some((p) => p.use);

	async function send(cancel: boolean) {
		if (!reason.trim()) return void (error = t('labels.errors.reason_required'));
		busy = true;
		error = '';
		try {
			const path = `/api/hygiene/cycles/${start.id}`;
			if (cancel) {
				const cancelled = await api<Cycle>(`${path}/cancel`, { method: 'POST', json: { reason: reason.trim() } });
				onsaved(t('labels.correction.cancelled'), cancelled);
			} else {
				const saved = await api<Cycle>(path, { method: 'PATCH', json: { result, program: program.trim(), note: note.trim(), reason: reason.trim() } });
				onsaved(t('labels.correction.saved'), saved);
			}
		} catch (err) {
			error = labelsError(err);
		} finally {
			busy = false;
		}
	}
</script>

<Modal
	title={t('labels.correction.title')}
	subtitle={t('labels.cycles.name', { code: start.labelCode, number: start.number }) + ' – ' + formatDate(start.runAt)}
	{onclose}
	guard
>
	<form id="cycle-correction" class="flex flex-col gap-4" onsubmit={(e) => (e.preventDefault(), void send(false))} novalidate>
		<p class="text-sm text-slate-700">{t('labels.correction.text')}</p>
		<fieldset class="flex flex-wrap gap-4">
			<legend class="mb-1 text-sm font-medium text-slate-700">{t('labels.cycleDialog.result')}</legend>
			<label class="inline-flex min-h-11 items-center gap-2"
				><input type="radio" name="correction-result" value="ok" bind:group={result} class="h-5 w-5 accent-brand-700" />{t('labels.cycleDialog.ok')}</label
			>
			<label class="inline-flex min-h-11 items-center gap-2"
				><input type="radio" name="correction-result" value="not_ok" bind:group={result} class="h-5 w-5 accent-rose-700" />{t('labels.cycleDialog.notOk')}</label
			>
		</fieldset>
		{#if result === 'not_ok' && start.result === 'ok' && start.packs.length}
			<p class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-900 ring-1 ring-rose-200">{t('labels.correction.recall', { count: start.packs.length })}</p>
		{/if}
		<label class="label">{t('labels.cycleDialog.program')}<input class="input" bind:value={program} maxlength="60" autocomplete="off" dir="auto" /></label>
		<label class="label">{t('labels.cycleDialog.note')}<input class="input" bind:value={note} maxlength="500" autocomplete="off" dir="auto" /></label>
		<label class="label">{t('labels.correction.reason')}<input class="input" bind:value={reason} maxlength="300" autocomplete="off" dir="auto" data-autofocus /></label>
		{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}
		{#if used}
			<p class="text-sm text-slate-600">{t('labels.correction.inUse')}</p>
		{:else if !cancelling}
			<button type="button" class="btn-secondary min-h-11 self-start text-sm text-rose-800" disabled={busy} onclick={() => (cancelling = true)}
				>{t('labels.correction.cancel')}</button
			>
		{:else}
			<div class="flex flex-col gap-3 rounded-xl border border-rose-300 bg-rose-50 p-3" role="group" aria-labelledby="cycle-cancel-title">
				<p id="cycle-cancel-title" class="font-semibold text-rose-950">
					{t('labels.correction.cancelTitle', { code: start.labelCode, number: start.number })}
				</p>
				<p class="text-sm text-rose-950">{t('labels.correction.cancelText')}</p>
				<div class="flex flex-wrap gap-2">
					<button type="button" class="btn min-h-11 bg-rose-700 text-sm text-white hover:bg-rose-800" disabled={busy} onclick={() => send(true)}
						>{t('labels.correction.cancelConfirm')}</button
					>
					<button type="button" class="btn-secondary min-h-11 text-sm" onclick={() => (cancelling = false)}>{t('labels.correction.cancelBack')}</button>
				</div>
			</div>
		{/if}
	</form>
	{#snippet footer()}
		<button type="button" class="btn-secondary" onclick={onclose}>{t('common.back')}</button>
		<button type="submit" form="cycle-correction" class="btn-primary" disabled={busy}>{t('labels.correction.save')}</button>
	{/snippet}
</Modal>
