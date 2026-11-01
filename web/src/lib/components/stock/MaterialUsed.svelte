<script lang="ts">
	/**
	 * "Matériel utilisé" in the appointment dialog (spec stock-hygiène 4.2): never required and folded away – the desk
	 * never waits for it. Opened, it lists what was noted for this appointment and adds a product in two taps (the last
	 * used product is preselected, quantity 1); the server links the appointment's act by itself.
	 */
	import { api } from '../../api';
	import { t } from '../../i18n.svelte';
	import { quantityText, sortForUse, stockError, wholeQuantity } from '../../stock';
	import type { Movement, MovementResult, Product } from '../../types/stock';
	import Icon from '../daily/Icon.svelte';

	let { appointmentId }: { appointmentId: number } = $props();

	let open = $state(false);
	let used = $state<Movement[] | null>(null);
	let products = $state<Product[]>([]);
	let productId = $state('');
	let quantity = $state(1);
	let notice = $state('');
	let error = $state('');
	let busy = $state(false);
	const id = `material-${Math.random().toString(36).slice(2, 8)}`;

	const choices = $derived(sortForUse(products));

	async function toggle() {
		open = !open;
		if (!open || used !== null) return;
		try {
			const [moves, list] = await Promise.all([
				api<Movement[]>(`/api/stock/movements?appointmentId=${appointmentId}`),
				api<Product[]>('/api/stock/products')
			]);
			used = moves.filter((m) => m.kind === 'use');
			products = list;
			productId = choices[0] ? String(choices[0].id) : '';
		} catch (err) {
			used = [];
			error = stockError(err);
		}
	}

	async function add() {
		const amount = wholeQuantity(quantity);
		if (!productId) return void (error = t('errors.validation'));
		if (amount === null) return void (error = t('stock.wholeNumber'));
		busy = true;
		error = '';
		notice = '';
		try {
			const result = await api<MovementResult>('/api/stock/movements', {
				method: 'POST',
				json: { productId: Number(productId), kind: 'use', quantity: amount, appointmentId }
			});
			used = [result.movement, ...(used ?? [])];
			products = products.map((p) => (p.id === result.product.id ? result.product : p));
			notice = t('stock.material.added', { quantity: quantityText(-result.movement.quantity, result.movement.unit), product: result.movement.productName });
			quantity = 1;
		} catch (err) {
			error = stockError(err);
		} finally {
			busy = false;
		}
	}
</script>

<div class="flex flex-col gap-2">
	<button
		type="button"
		class="inline-flex min-h-11 items-center gap-2 self-start rounded-lg px-1 text-sm font-semibold text-brand-800 underline-offset-2 hover:underline"
		aria-expanded={open}
		aria-controls={id}
		onclick={toggle}><Icon name={open ? 'close' : 'plus'} class="h-4 w-4" />{t('stock.material.open')}</button
	>
	{#if open}
		<section {id} aria-labelledby="{id}-title" class="flex flex-col gap-3 rounded-lg bg-slate-50 p-3 ring-1 ring-slate-200">
			<div>
				<h3 id="{id}-title" class="font-semibold">{t('stock.material.title')}</h3>
				<p class="text-sm text-slate-600">{t('stock.material.hint')}</p>
			</div>
			{#if used === null}
				<p class="text-sm text-slate-500" aria-busy="true">{t('common.loading')}</p>
			{:else}
				{#if used.length}
					<ul class="flex flex-col gap-1 text-sm">
						{#each used as m (m.id)}
							<li class="flex gap-2"><span class="font-semibold tabular-nums">{quantityText(-m.quantity, m.unit)}</span> <span dir="auto">{m.productName}</span></li>
						{/each}
					</ul>
				{:else}
					<p class="text-sm text-slate-600">{t('stock.material.none')}</p>
				{/if}
				{#if choices.length}
					<div class="flex flex-wrap items-end gap-2">
						<label class="label min-w-0 flex-1"
							>{t('stock.material.product')}
							<select class="input" bind:value={productId}>
								{#each choices as p (p.id)}<option value={String(p.id)}>{p.name}</option>{/each}
							</select>
						</label>
						<label class="label w-24"
							>{t('stock.material.quantity')}<input class="input text-center tabular-nums" type="number" inputmode="numeric" min="1" step="1" bind:value={quantity} /></label
						>
						<button type="button" class="btn-secondary min-h-11" disabled={busy} onclick={add}>{t('stock.material.add')}</button>
					</div>
				{/if}
			{/if}
			{#if notice}<p role="status" class="text-sm font-medium text-emerald-800">{notice}</p>{/if}
			{#if error}<p role="alert" class="text-sm font-medium text-rose-800">{error}</p>{/if}
		</section>
	{/if}
</div>
