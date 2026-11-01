<script lang="ts">
	/**
	 * Create or change a product (assistant, owner): name, category (those of the specialty first), unit, usual supplier,
	 * order threshold, note. Editing also (de)activates or deletes it – deleting works only without history (409
	 * product_in_use); otherwise the product is deactivated so the past stays readable. Once something was recorded the
	 * unit is locked (review M2: 2 boxes must not become 2 pieces) – the dialog says why and offers a new product.
	 */
	import { untrack } from 'svelte';
	import { api } from '../../api';
	import { auth } from '../../auth.svelte';
	import { t } from '../../i18n.svelte';
	import { categoriesFor, categoryLabel, stockError, UNITS, unitLabel } from '../../stock';
	import type { Product, StockCategory, StockUnit, Supplier } from '../../types/stock';
	import Modal from '../daily/Modal.svelte';

	type Props = {
		product?: Product | null;
		initialName?: string;
		suppliers: Supplier[];
		onsaved: (p: Product) => void;
		ondeleted?: (id: number) => void;
		/** "Créer un nouveau produit" instead of changing a locked unit. */
		onnew?: (name: string) => void;
		onclose: () => void;
	};
	let { product = null, initialName = '', suppliers, onsaved, ondeleted, onnew, onclose }: Props = $props();

	const start = untrack(() => product);
	let name = $state(start?.name ?? untrack(() => initialName));
	let category = $state<StockCategory>(start?.category ?? 'hygiene');
	let unit = $state<StockUnit>(start?.unit ?? 'boite');
	let supplierId = $state(start?.supplierId ? String(start.supplierId) : '');
	let minQuantity = $state<number>(start?.minQuantity ?? 0);
	let note = $state(start?.note ?? '');
	let error = $state('');
	let busy = $state(false);

	const locked = !!start?.hasHistory;
	const categories = $derived(categoriesFor(auth.user?.practice?.specialty));
	const choosable = $derived(suppliers.filter((s) => s.active || String(s.id) === supplierId));

	async function save(e?: SubmitEvent, extra: Record<string, unknown> = {}) {
		e?.preventDefault();
		if (!name.trim()) return void (error = t('errors.validation'));
		busy = true;
		error = '';
		const body = {
			name: name.trim(),
			category,
			unit,
			supplierId: supplierId ? Number(supplierId) : null,
			minQuantity: Math.max(0, Math.round(Number(minQuantity) || 0)),
			note: note.trim(),
			...extra
		};
		try {
			const saved = start
				? await api<Product>(`/api/stock/products/${start.id}`, { method: 'PATCH', json: body })
				: await api<Product>('/api/stock/products', { method: 'POST', json: body });
			onsaved(saved);
		} catch (err) {
			error = stockError(err);
		} finally {
			busy = false;
		}
	}

	async function remove() {
		if (!start) return;
		busy = true;
		error = '';
		try {
			await api(`/api/stock/products/${start.id}`, { method: 'DELETE' });
			ondeleted?.(start.id);
		} catch (err) {
			error = stockError(err);
		} finally {
			busy = false;
		}
	}
</script>

<Modal title={start ? t('stock.product.editTitle') : t('stock.product.title')} {onclose} guard>
	<form id="product-form" class="flex flex-col gap-4" onsubmit={save} novalidate>
		<label class="label">{t('stock.product.name')}<input class="input" bind:value={name} maxlength="120" autocomplete="off" required data-autofocus /></label>
		<div class="grid grid-cols-2 gap-3">
			<label class="label"
				>{t('stock.category')}
				<select class="input" bind:value={category}>
					{#each categories as c (c)}<option value={c}>{categoryLabel(c)}</option>{/each}
				</select>
			</label>
			<label class="label"
				>{t('stock.product.unit')}
				<select class="input" bind:value={unit} disabled={locked} aria-describedby={locked ? 'product-unit-locked' : undefined}>
					{#each UNITS as u (u)}<option value={u}>{unitLabel(u)}</option>{/each}
				</select>
			</label>
		</div>
		{#if locked}
			<div class="flex flex-col items-start gap-2 rounded-lg bg-slate-50 px-3 py-2 ring-1 ring-slate-200">
				<p id="product-unit-locked" class="text-sm text-slate-700">{t('stock.product.unitLocked')}</p>
				{#if onnew}
					<button type="button" class="btn-secondary min-h-11 text-sm" onclick={() => onnew?.(name.trim())}>{t('stock.product.newInstead')}</button>
				{/if}
			</div>
		{/if}
		<label class="label"
			>{t('stock.product.supplier')}
			<select class="input" bind:value={supplierId}>
				<option value="">{t('stock.product.noSupplier')}</option>
				{#each choosable as s (s.id)}<option value={String(s.id)}>{s.name}</option>{/each}
			</select>
		</label>
		<div class="flex flex-col gap-1">
			<label class="text-sm font-medium text-slate-700" for="product-min">{t('stock.product.minQuantity')}</label>
			<input id="product-min" class="input w-32 tabular-nums" type="number" inputmode="numeric" min="0" max="100000" bind:value={minQuantity} aria-describedby="product-min-hint" />
			<p id="product-min-hint" class="text-sm text-slate-600">{t('stock.product.minHint')}</p>
		</div>
		<label class="label">{t('stock.product.note')}<input class="input" bind:value={note} maxlength="500" autocomplete="off" /></label>
		{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}
		{#if start}
			<div class="flex flex-wrap gap-2 border-t border-slate-200 pt-3">
				<button type="button" class="btn-secondary min-h-11 text-sm" disabled={busy} onclick={() => save(undefined, { active: !start.active })}
					>{start.active ? t('stock.product.deactivate') : t('stock.product.reactivate')}</button
				>
				<button type="button" class="btn-secondary min-h-11 text-sm text-rose-800" disabled={busy} onclick={remove}>{t('stock.product.delete')}</button>
			</div>
		{/if}
	</form>
	{#snippet footer()}
		<button type="button" class="btn-secondary" onclick={onclose}>{t('common.cancel')}</button>
		<button type="submit" form="product-form" class="btn-primary" disabled={busy}>{t('stock.product.save')}</button>
	{/snippet}
</Modal>
