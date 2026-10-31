<script lang="ts">
	/**
	 * "Sortie" in three taps (spec stock-hygiène 4.2): open → tap the product (last used first) → "Enregistrer la sortie"
	 * with quantity 1. Optional: another quantity, the act it was for, or – for assistant and owner – a loss with its
	 * reason. Nothing to type in the usual case: the focus goes to the first product, not to the search field, so the
	 * phone keyboard stays closed.
	 */
	import { onMount, untrack } from 'svelte';
	import { api } from '../../api';
	import { auth } from '../../auth.svelte';
	import { serviceLabel } from '../../agenda/format';
	import { t } from '../../i18n.svelte';
	import { matches, quantityText, sortForUse, stockError, unitWord, STATUS_TONE } from '../../stock';
	import type { Service } from '../../types/agenda';
	import type { MovementResult, Product } from '../../types/stock';
	import Icon from '../daily/Icon.svelte';
	import Modal from '../daily/Modal.svelte';

	type Props = {
		products: Product[];
		preselected?: Product | null;
		onsaved: (result: MovementResult) => void;
		onclose: () => void;
	};
	let { products, preselected = null, onsaved, onclose }: Props = $props();

	const manager = $derived(auth.role === 'owner' || auth.role === 'assistant');
	let query = $state('');
	let chosen = $state<Product | null>(untrack(() => preselected));
	let quantity = $state(1);
	let serviceId = $state('');
	let waste = $state(false);
	let reason = $state('');
	let services = $state<Service[]>([]);
	let error = $state('');
	let busy = $state(false);

	const RECENT = 6;
	const choices = $derived(sortForUse(products).filter((p) => matches(p, query)));
	/** Without a search: the last used ones in their own short list on top. */
	const recent = $derived(query.trim() ? [] : choices.filter((p) => p.lastUsedAt).slice(0, RECENT));
	const others = $derived(choices.filter((p) => !recent.includes(p)));

	onMount(async () => {
		services = (await api<Service[]>('/api/services').catch(() => [])).filter((s) => s.active !== false);
	});

	function choose(p: Product) {
		chosen = p;
		quantity = 1;
		error = '';
	}

	function step(by: number) {
		quantity = Math.min(100000, Math.max(1, (Number(quantity) || 0) + by));
	}

	async function save() {
		if (!chosen) return;
		const amount = Math.round(Number(quantity));
		if (!Number.isFinite(amount) || amount < 1) return void (error = t('errors.validation'));
		busy = true;
		error = '';
		try {
			const body: Record<string, unknown> = { productId: chosen.id, kind: waste ? 'waste' : 'use', quantity: amount };
			if (!waste && serviceId) body.serviceId = Number(serviceId);
			if (waste && reason.trim()) body.reason = reason.trim();
			onsaved(await api<MovementResult>('/api/stock/movements', { method: 'POST', json: body }));
		} catch (err) {
			error = stockError(err);
		} finally {
			busy = false;
		}
	}
</script>

<Modal title={t('stock.useDialog.title')} {onclose}>
	{#if !chosen}
		{#if products.some((p) => p.active)}
			<div class="flex flex-col gap-3">
				<label class="label"
					><span class="sr-only">{t('stock.search')}</span>
					<input class="input" type="search" bind:value={query} placeholder={t('stock.search')} autocomplete="off" />
				</label>
				{#if choices.length}
					{#each [{ key: 'recent', label: t('stock.useDialog.recent'), list: recent }, { key: 'all', label: t('stock.useDialog.all'), list: others }] as part (part.key)}
						{#if part.list.length}
							<section class="flex flex-col gap-2" aria-labelledby="use-{part.key}">
								<h3 id="use-{part.key}" class="text-sm font-semibold text-slate-600">{part.label}</h3>
								<ul class="flex flex-col gap-2">
									{#each part.list as p (p.id)}
										<li>
											<button
												type="button"
												class="flex min-h-14 w-full items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2 text-start hover:border-brand-300 hover:bg-brand-50/50"
												data-autofocus={p === choices[0] ? true : undefined}
												onclick={() => choose(p)}
											>
												<span class="min-w-0 flex-1 font-semibold" dir="auto">{p.name}</span>
												<span class="shrink-0 rounded-full px-2 py-0.5 text-sm font-semibold tabular-nums ring-1 {STATUS_TONE[p.status]}"
													>{quantityText(p.quantity, p.unit)}</span
												>
											</button>
										</li>
									{/each}
								</ul>
							</section>
						{/if}
					{/each}
				{:else}
					<p class="text-slate-600">{t('stock.noMatch')}</p>
				{/if}
			</div>
		{:else}
			<p class="text-slate-700">{t('stock.useDialog.empty')}</p>
		{/if}
	{:else}
		<div class="flex flex-col gap-4">
			<div class="flex items-center gap-3 rounded-xl bg-brand-50 px-3 py-3 ring-1 ring-brand-100">
				<div class="min-w-0 flex-1">
					<p class="font-bold text-ink" dir="auto">{chosen.name}</p>
					<p class="text-sm text-slate-700">{t('stock.useDialog.left', { quantity: quantityText(chosen.quantity, chosen.unit) })}</p>
				</div>
				{#if !preselected}
					<button type="button" class="btn-secondary min-h-11 px-3 text-sm" onclick={() => (chosen = null)}>{t('stock.useDialog.change')}</button>
				{/if}
			</div>

			<div class="flex flex-col gap-1">
				<label for="use-quantity" class="text-sm font-medium text-slate-700">{t('stock.useDialog.quantity')}</label>
				<div class="flex items-center gap-2">
					<button type="button" class="btn-secondary min-h-12 min-w-12 px-0 text-xl" aria-label={t('stock.useDialog.less')} disabled={quantity <= 1} onclick={() => step(-1)}
						>−</button
					>
					<input id="use-quantity" class="input w-24 text-center text-lg font-bold tabular-nums" type="number" inputmode="numeric" min="1" bind:value={quantity} />
					<button type="button" class="btn-secondary min-h-12 min-w-12 px-0 text-xl" aria-label={t('stock.useDialog.more')} onclick={() => step(1)}>+</button>
					<span class="text-slate-600">{unitWord(Number(quantity) || 0, chosen.unit)}</span>
				</div>
			</div>

			{#if !waste && services.length}
				<label class="label"
					>{t('stock.useDialog.service')}
					<select class="input" bind:value={serviceId}>
						<option value="">{t('stock.useDialog.noService')}</option>
						{#each services as s (s.id)}<option value={String(s.id)}>{serviceLabel(s)}</option>{/each}
					</select>
				</label>
			{/if}

			{#if manager}
				<label class="inline-flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" class="h-5 w-5 accent-rose-700" bind:checked={waste} />{t('stock.useDialog.waste')}</label>
				{#if waste}
					<label class="label">{t('stock.useDialog.reason')}<input class="input" bind:value={reason} maxlength="300" autocomplete="off" /></label>
				{/if}
			{/if}
			{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}
		</div>
	{/if}
	{#snippet footer()}
		<button type="button" class="btn-secondary" onclick={onclose}>{t('common.cancel')}</button>
		<button type="button" class="btn-primary min-h-12" disabled={!chosen || busy} onclick={save}><Icon name="check" />{t('stock.useDialog.save')}</button>
	{/snippet}
</Modal>
