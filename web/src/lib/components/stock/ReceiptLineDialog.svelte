<script lang="ts">
	/**
	 * The owner corrects one line of a delivery (review H2): quantity and unit price, with a reason. The stock and every
	 * material cost that depended on it are computed again by the server; the change log keeps old → new.
	 */
	import { untrack } from 'svelte';
	import { api } from '../../api';
	import { formatDay, t } from '../../i18n.svelte';
	import { dinarsText, parseDinars } from '../../money-input';
	import { stockError, unitWord, wholeQuantity } from '../../stock';
	import type { Movement, Receipt } from '../../types/stock';
	import Modal from '../daily/Modal.svelte';
	import PriceField from './PriceField.svelte';

	type Props = { movement: Movement; onsaved: (receipt: Receipt) => void; onclose: () => void };
	let { movement, onsaved, onclose }: Props = $props();

	const start = untrack(() => movement);
	let quantity = $state<string>(String(start.quantity));
	let price = $state(dinarsText(start.unitCostMillimes));
	let reason = $state('');
	let error = $state('');
	let busy = $state(false);

	async function save(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		const amount = wholeQuantity(quantity);
		if (amount === null) return void (error = t('stock.wholeNumber'));
		const millimes = parseDinars(price);
		if (Number.isNaN(millimes)) return void (error = t('stock.receipt.invalidPrice', { product: start.productName }));
		if (!reason.trim()) return void (error = t('errors.validation'));
		busy = true;
		try {
			const receipt = await api<Receipt>(`/api/stock/receipts/${start.receiptId}/lines/${start.receiptLineId}`, {
				method: 'PATCH',
				json: { quantity: amount, unitPriceMillimes: millimes, reason: reason.trim() }
			});
			onsaved(receipt);
		} catch (err) {
			error = stockError(err);
		} finally {
			busy = false;
		}
	}
</script>

<Modal title={t('stock.movements.correctTitle', { date: formatDay(start.receivedOn ?? start.createdAt.slice(0, 10)) })} subtitle={start.productName} {onclose} guard>
	<form id="line-form" class="flex flex-col gap-4" onsubmit={save} novalidate>
		<p class="text-sm text-slate-700">{t('stock.movements.correctText')}</p>
		<div class="flex flex-wrap items-start gap-4">
			<div class="flex flex-col gap-1">
				<label class="text-sm font-medium text-slate-700" for="line-quantity">{t('stock.movements.quantity')}</label>
				<div class="flex items-center gap-2">
					<input id="line-quantity" class="input w-24 text-center tabular-nums" type="number" inputmode="numeric" min="1" step="1" bind:value={quantity} data-autofocus />
					<span class="text-sm text-slate-600">{unitWord(Number(quantity) || 0, start.unit)}</span>
				</div>
			</div>
			<PriceField id="line-price" label={t('stock.movements.unitPrice')} bind:value={price} unit={start.unit} class="w-48" />
		</div>
		<label class="label">{t('stock.movements.reason')}<input class="input" bind:value={reason} maxlength="300" autocomplete="off" dir="auto" /></label>
		{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}
	</form>
	{#snippet footer()}
		<button type="button" class="btn-secondary" onclick={onclose}>{t('common.cancel')}</button>
		<button type="submit" form="line-form" class="btn-primary" disabled={busy}>{t('stock.movements.saveCorrection')}</button>
	{/snippet}
</Modal>
