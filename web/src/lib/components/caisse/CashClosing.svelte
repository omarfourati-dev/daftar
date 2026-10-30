<script lang="ts">
	/**
	 * Cash closing of a day (section 16.3): the desk counts the cash and enters it, the difference to the expected
	 * cash shows at once; the owner verifies the closing (`POST /api/cash/{day}/verify`).
	 */
	import { errorText } from '../../agenda/errors';
	import { untrack } from 'svelte';
	import { api } from '../../api';
	import { money } from '../../agenda/format';
	import { parseDinars } from '../../agenda/links';
	import { formatDateTime, formatTime, t } from '../../i18n.svelte';
	import type { CashClosing } from '../../types/patients';

	type Props = { day: string; expectedCash: number; closing: CashClosing | null; isOwner: boolean };
	let { day, expectedCash, closing: initial, isOwner }: Props = $props();

	let closing = $state<CashClosing | null>(untrack(() => initial));
	let editing = $state(untrack(() => !initial));
	let counted = $state('');
	let note = $state('');
	let error = $state('');
	let busy = $state(false);

	async function close(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		const countedCashMillimes = counted.trim() ? parseDinars(counted) : null;
		if (countedCashMillimes === null) return void (error = t('caisse.closing.invalid'));
		busy = true;
		try {
			closing = await api<CashClosing>('/api/cash/close', {
				method: 'POST',
				json: { day, countedCashMillimes, ...(note.trim() ? { note: note.trim() } : {}) }
			});
			editing = false;
		} catch (err) {
			error = errorText(err);
		} finally {
			busy = false;
		}
	}

	async function verify() {
		if (!closing) return;
		busy = true;
		error = '';
		try {
			const result = await api<{ verifiedBy: string; verifiedAt: string }>(`/api/cash/${day}/verify`, { method: 'POST' });
			closing = { ...closing, ...result };
		} catch (err) {
			error = errorText(err);
		} finally {
			busy = false;
		}
	}

	const diff = $derived(closing?.differenceMillimes ?? 0);
</script>

<section aria-labelledby="closing-title" class="card flex flex-col gap-3 p-5">
	<h2 id="closing-title" class="text-lg font-bold">{t('caisse.closing.title')}</h2>
	<dl class="grid grid-cols-2 gap-3">
		<div class="rounded-xl bg-slate-50 p-3 ring-1 ring-slate-200">
			<dt class="text-sm text-slate-600">{t('caisse.closing.expected')}</dt>
			<dd class="text-xl font-bold tabular-nums">{money(closing?.expectedCashMillimes ?? expectedCash)}</dd>
		</div>
		{#if closing && !editing}
			<div class="rounded-xl bg-slate-50 p-3 ring-1 ring-slate-200">
				<dt class="text-sm text-slate-600">{t('caisse.closing.countedShort')}</dt>
				<dd class="text-xl font-bold tabular-nums">{money(closing.countedCashMillimes)}</dd>
			</div>
		{/if}
	</dl>

	{#if closing && !editing}
		<p
			class="rounded-xl px-4 py-3 text-lg font-bold {diff === 0
				? 'bg-emerald-50 text-emerald-900 ring-1 ring-emerald-200'
				: diff < 0
					? 'bg-rose-50 text-rose-900 ring-1 ring-rose-200'
					: 'bg-amber-50 text-amber-900 ring-1 ring-amber-200'}"
		>
			{diff === 0 ? t('caisse.closing.exact') : diff < 0 ? t('caisse.closing.missing', { amount: money(-diff) }) : t('caisse.closing.surplus', { amount: money(diff) })}
		</p>
		{#if closing.stale && !closing.verifiedAt}
			<p class="rounded-lg bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900 ring-1 ring-amber-200">{t('caisse.closing.stale')}</p>
		{/if}
		{#if closing.note}<p class="text-sm text-slate-700">{closing.note}</p>{/if}
		<p class="text-sm text-slate-600">{t('caisse.closing.closedBy', { name: closing.closedBy ?? '–', time: formatTime(closing.closedAt) })}</p>
		{#if closing.verifiedAt}
			<p class="font-semibold text-emerald-800">{t('caisse.closing.verifiedBy', { name: closing.verifiedBy ?? '–', date: formatDateTime(closing.verifiedAt) })}</p>
		{:else if isOwner}
			<button type="button" class="btn-primary self-start" disabled={busy} onclick={verify}>{t('caisse.closing.verify')}</button>
		{:else}
			<p class="text-sm font-medium text-amber-900">{t('caisse.closing.waiting')}</p>
		{/if}
		{#if !closing.verifiedAt}
			<button type="button" class="self-start text-sm font-semibold text-brand-800 underline underline-offset-2" onclick={() => (editing = true)}
				>{t('caisse.closing.recount')}</button
			>
		{/if}
	{:else}
		<form class="flex flex-col gap-3" onsubmit={close} novalidate>
			<p class="text-sm text-slate-600">{t('caisse.closing.hint')}</p>
			<label class="label">{t('caisse.closing.counted')}<input class="input text-lg font-semibold" inputmode="decimal" bind:value={counted} autocomplete="off" /></label>
			<label class="label">{t('caisse.closing.note')}<input class="input" bind:value={note} maxlength="500" autocomplete="off" /></label>
			<button type="submit" class="btn-primary self-start" disabled={busy}>{t('caisse.closing.close')}</button>
		</form>
	{/if}
	{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}
</section>
