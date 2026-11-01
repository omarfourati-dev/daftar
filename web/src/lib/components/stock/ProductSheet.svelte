<script lang="ts">
	/**
	 * A product opened from the list: stock, threshold, supplier, average price (assistant and owner), soonest expiry,
	 * the last movements, and the actions "Sortie", "Compter" (inventory of this one product, with a reason) and
	 * "Modifier" for those who set up the stock.
	 */
	import { onMount, untrack } from 'svelte';
	import { api } from '../../api';
	import { auth } from '../../auth.svelte';
	import { money } from '../../agenda/format';
	import { clock } from '../../clock';
	import { formatDateTime, formatDay, t, todayTunis } from '../../i18n.svelte';
	import {
		categoryLabel,
		inventoryReason,
		KIND_KEY,
		movementService,
		quantityText,
		stockError,
		STATUS_TONE,
		unitLabel,
		wholeQuantity
	} from '../../stock';
	import type { Movement, Product } from '../../types/stock';
	import Icon from '../daily/Icon.svelte';
	import Modal from '../daily/Modal.svelte';

	type Props = {
		product: Product;
		onuse: (p: Product) => void;
		onedit: (p: Product) => void;
		onchanged: (p: Product) => void;
		onclose: () => void;
	};
	let { product, onuse, onedit, onchanged, onclose }: Props = $props();

	const manager = $derived(auth.role === 'owner' || auth.role === 'assistant');
	let p = $state(untrack(() => product));
	let movements = $state<Movement[] | null>(null);
	let movementsError = $state('');
	let counting = $state(false);
	let counted = $state<number>(untrack(() => Math.max(product.quantity, 0)));
	let reason = $state(inventoryReason(todayTunis(clock.now())));
	let notice = $state('');
	let error = $state('');
	let busy = $state(false);

	async function loadMovements() {
		movementsError = '';
		try {
			movements = await api<Movement[]>(`/api/stock/movements?productId=${p.id}&limit=10`);
		} catch {
			movementsError = t('stock.sheet.movementsError');
		}
	}
	onMount(loadMovements);

	async function count(e: SubmitEvent) {
		e.preventDefault();
		const value = wholeQuantity(counted, 0);
		if (value === null) return void (error = t('stock.wholeNumber'));
		if (!reason.trim()) return void (error = t('errors.validation'));
		busy = true;
		error = '';
		try {
			const result = await api<{ adjusted: number; products: Product[] }>('/api/stock/inventory', {
				method: 'POST',
				json: { reason: reason.trim(), counts: [{ productId: p.id, counted: value }] }
			});
			const next = result.products.find((x) => x.id === p.id) ?? p;
			notice = result.adjusted ? t('stock.count.done', { quantity: quantityText(next.quantity, next.unit) }) : t('stock.count.same');
			p = next;
			counting = false;
			onchanged(next);
			void loadMovements();
		} catch (err) {
			error = stockError(err);
		} finally {
			busy = false;
		}
	}

	const sign = (n: number) => (n > 0 ? `+${n}` : String(n));
</script>

<Modal title={p.name} subtitle={categoryLabel(p.category)} {onclose}>
	<div class="flex flex-col gap-4">
		<div class="flex flex-wrap items-center gap-3">
			<span class="text-3xl font-bold text-ink tabular-nums">{quantityText(p.quantity, p.unit)}</span>
			<span class="rounded-full px-2.5 py-0.5 text-sm font-semibold ring-1 {STATUS_TONE[p.status]}">{p.active ? t(`stock.status.${p.status}`) : t('stock.inactive')}</span>
		</div>
		{#if p.status === 'unreceived' && p.active}<p class="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700 ring-1 ring-slate-200">{t('stock.unreceivedHint')}</p>{/if}
		{#if p.quantity < 0}<p class="rounded-lg bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-950 ring-1 ring-amber-300">{t('stock.negative')}</p>{/if}
		<dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
			<dt class="text-slate-600">{t('stock.sheet.min')}</dt>
			<dd class="font-semibold tabular-nums">{quantityText(p.minQuantity, p.unit)}</dd>
			<dt class="text-slate-600">{t('stock.sheet.supplier')}</dt>
			<dd class="font-semibold" dir="auto">{p.supplierName ?? '–'}</dd>
			{#if p.averageCostMillimes !== null}
				<dt class="text-slate-600">{t('stock.sheet.price')}</dt>
				<dd class="font-semibold">{t('stock.sheet.perUnit', { price: money(p.averageCostMillimes), unit: unitLabel(p.unit) })}</dd>
			{/if}
			{#if p.expiresOn}
				<dt class="text-slate-600">{t('stock.sheet.expiresOn')}</dt>
				<dd class="font-semibold {p.expiry === 'expired' ? 'text-rose-800' : p.expiry === 'soon' ? 'text-amber-900' : ''}">{formatDay(p.expiresOn)}</dd>
			{/if}
		</dl>
		{#if p.note}<p class="text-sm text-slate-700" dir="auto">{p.note}</p>{/if}
		{#if notice}<p role="status" class="rounded-lg bg-emerald-50 px-3 py-2 font-medium text-emerald-900">{notice}</p>{/if}

		{#if counting}
			<form class="flex flex-col gap-3 rounded-xl bg-slate-50 p-3 ring-1 ring-slate-200" onsubmit={count} novalidate>
				<label class="label"
					>{t('stock.count.counted')}<input class="input w-32 text-lg font-bold tabular-nums" type="number" inputmode="numeric" min="0" step="1" bind:value={counted} data-autofocus /></label
				>
				<label class="label">{t('stock.count.reason')}<input class="input" bind:value={reason} maxlength="300" autocomplete="off" /></label>
				{#if error}<p role="alert" class="text-sm font-medium text-rose-800">{error}</p>{/if}
				<div class="flex flex-wrap gap-2">
					<button type="button" class="btn-secondary" onclick={() => (counting = false)}>{t('common.cancel')}</button>
					<button type="submit" class="btn-primary" disabled={busy}>{t('stock.count.save')}</button>
				</div>
			</form>
		{/if}

		<section aria-labelledby="sheet-moves" class="flex flex-col gap-2">
			<h3 id="sheet-moves" class="text-sm font-semibold text-slate-600">{t('stock.sheet.lastMovements')}</h3>
			{#if movementsError}
				<div role="alert" class="flex flex-wrap items-center justify-between gap-2 text-sm text-rose-800">
					<p>{movementsError}</p>
					<button type="button" class="btn-secondary min-h-11 text-sm" onclick={loadMovements}>{t('common.retry')}</button>
				</div>
			{:else if movements === null}
				<p class="text-sm text-slate-500" aria-busy="true">{t('common.loading')}</p>
			{:else if movements.length}
				<ul class="flex flex-col divide-y divide-slate-100 text-sm">
					{#each movements as m (m.id)}
						<li class="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 py-2">
							<span class="w-14 shrink-0 font-bold tabular-nums {m.quantity > 0 ? 'text-emerald-800' : 'text-rose-800'}" dir="ltr">{sign(m.quantity)}</span>
							<span class="font-medium">{t(KIND_KEY[m.kind])}</span>
							{#if m.serviceName}<span class="text-slate-600" dir="auto">{movementService(m)}</span>{/if}
							<span class="ms-auto text-slate-500 tabular-nums">{formatDateTime(m.createdAt)}</span>
						</li>
					{/each}
				</ul>
			{:else}
				<p class="text-sm text-slate-600">{t('stock.sheet.noMovements')}</p>
			{/if}
		</section>
	</div>
	{#snippet footer()}
		{#if manager}
			<button type="button" class="btn-secondary" onclick={() => onedit(p)}><Icon name="edit" />{t('stock.sheet.edit')}</button>
			<button type="button" class="btn-secondary" onclick={() => ((counting = true), (error = ''), (notice = ''))}>{t('stock.sheet.count')}</button>
		{/if}
		{#if p.active}
			<button type="button" class="btn-primary" onclick={() => onuse(p)}>{t('stock.use')}</button>
		{/if}
	{/snippet}
</Modal>
