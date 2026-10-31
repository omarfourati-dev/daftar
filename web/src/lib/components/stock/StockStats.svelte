<script lang="ts">
	/**
	 * The material of the month for the owner (spec stock-hygiène 4.3), below the practice statistics: what was bought
	 * (vs. last month, by supplier and category), what was used and lost, the material cost per act and per treatment,
	 * the most expensive material, and the month as CSV.
	 */
	import { api, apiBlob } from '../../api';
	import { money } from '../../agenda/format';
	import { saveBlob } from '../../download';
	import { i18n, t } from '../../i18n.svelte';
	import { categoryLabel, quantityText, stockError } from '../../stock';
	import type { StockStats } from '../../types/stock';

	let { month, previousName }: { month: string; previousName: string } = $props();

	let stats = $state<StockStats | null>(null);
	let error = $state('');
	let exporting = $state(false);
	let seq = 0;

	async function load(wanted: string) {
		const mine = ++seq;
		error = '';
		stats = null;
		try {
			const result = await api<StockStats>(`/api/stock/stats?month=${wanted}`);
			if (mine === seq) stats = result;
		} catch {
			if (mine === seq) error = t('stock.stats.loadError');
		}
	}

	$effect(() => {
		void load(month);
	});

	async function exportCsv() {
		exporting = true;
		error = '';
		try {
			saveBlob(await apiBlob(`/api/stock/export.csv?month=${month}`), `stock-${month}.csv`);
		} catch (err) {
			error = stockError(err);
		} finally {
			exporting = false;
		}
	}

	const delta = $derived(stats ? stats.spendingMillimes - stats.previousSpendingMillimes : 0);
	const deltaText = $derived(
		delta === 0
			? t('statistiques.same')
			: t(delta > 0 ? 'statistiques.up' : 'statistiques.down', { value: money(Math.abs(delta)), month: previousName })
	);
	const maxCategory = $derived(Math.max(1, ...(stats?.byCategory ?? []).map((c) => c.amountMillimes)));
	const empty = $derived(!!stats && stats.spendingMillimes === 0 && stats.usageMillimes === 0 && stats.wasteMillimes === 0);
	const number = (n: number) => new Intl.NumberFormat(i18n.locale === 'ar' ? 'ar-TN-u-nu-latn' : 'fr-TN').format(n);
</script>

<section aria-labelledby="material-title" class="flex flex-col gap-4">
	<div class="flex flex-wrap items-center justify-between gap-3">
		<h2 id="material-title" class="text-xl font-bold">{t('stock.stats.title')}</h2>
		<button type="button" class="btn-secondary min-h-11 text-sm" disabled={exporting} onclick={exportCsv}>{t('stock.stats.export')}</button>
	</div>
	{#if error}
		<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>
	{/if}
	{#if !stats}
		{#if !error}<p class="card text-slate-600" aria-busy="true">{t('common.loading')}</p>{/if}
	{:else if empty}
		<p class="card text-slate-700">{t('stock.stats.none')}</p>
	{:else}
		<ul class="grid grid-cols-2 gap-3 md:grid-cols-3">
			<li class="flex flex-col gap-1 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
				<span class="text-sm font-semibold text-slate-600">{t('stock.stats.spending')}</span>
				<span class="text-2xl font-bold whitespace-nowrap text-ink tabular-nums">{money(stats.spendingMillimes)}</span>
				<span class="text-xs font-semibold text-slate-600">{deltaText}</span>
			</li>
			<li class="flex flex-col gap-1 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
				<span class="text-sm font-semibold text-slate-600">{t('stock.stats.usage')}</span>
				<span class="text-2xl font-bold whitespace-nowrap text-ink tabular-nums">{money(stats.usageMillimes)}</span>
			</li>
			<li class="flex flex-col gap-1 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
				<span class="text-sm font-semibold text-slate-600">{t('stock.stats.waste')}</span>
				<span class="text-2xl font-bold whitespace-nowrap text-ink tabular-nums">{money(stats.wasteMillimes)}</span>
			</li>
		</ul>
		{#if stats.unpricedLines}<p class="text-sm text-slate-600">{t('stock.stats.unpriced', { count: stats.unpricedLines })}</p>{/if}

		{#if stats.byService.length}
			<div class="card overflow-x-auto p-0">
				<table class="w-full text-sm">
					<caption class="px-4 pt-4 text-start text-lg font-bold">{t('stock.stats.byService')}</caption>
					<thead>
						<tr class="border-b border-slate-200 text-slate-600">
							<th scope="col" class="px-4 py-2 text-start font-semibold">{t('stock.stats.service')}</th>
							<th scope="col" class="px-2 py-2 text-end font-semibold">{t('stock.stats.treatments')}</th>
							<th scope="col" class="px-2 py-2 text-end font-semibold">{t('stock.stats.cost')}</th>
							<th scope="col" class="px-4 py-2 text-end font-semibold">{t('stock.stats.perTreatment')}</th>
						</tr>
					</thead>
					<tbody>
						{#each stats.byService as s (s.serviceId ?? 0)}
							<tr class="border-b border-slate-100 align-top last:border-0">
								<th scope="row" class="px-4 py-2 text-start font-semibold">
									<span dir="auto">{s.name ?? t('stock.stats.noService')}</span>
									{#if s.items.length}
										<span class="block text-xs font-normal text-slate-600"
											>{s.items.map((i) => `${quantityText(i.quantity, i.unit)} ${i.name}`).join(', ')}</span
										>
									{/if}
								</th>
								<td class="px-2 py-2 text-end tabular-nums">{s.serviceId === null ? '–' : number(s.treatments)}</td>
								<td class="px-2 py-2 text-end whitespace-nowrap tabular-nums">{money(s.materialCostMillimes)}</td>
								<td class="px-4 py-2 text-end font-semibold whitespace-nowrap tabular-nums">{s.perTreatmentMillimes === null ? '–' : money(s.perTreatmentMillimes)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}

		<div class="grid items-start gap-4 lg:grid-cols-3">
			<section aria-labelledby="material-categories" class="card flex flex-col gap-2">
				<h3 id="material-categories" class="font-bold">{t('stock.stats.byCategory')}</h3>
				<ul class="flex flex-col gap-2 text-sm">
					{#each stats.byCategory as c (c.category)}
						<li class="grid grid-cols-[minmax(0,8rem)_1fr_auto] items-center gap-2">
							<span class="truncate">{categoryLabel(c.category)}</span>
							<span class="h-2.5 overflow-hidden rounded-full bg-slate-100" aria-hidden="true"
								><span class="block h-full rounded-full bg-brand-600" style="width:{(c.amountMillimes / maxCategory) * 100}%"></span></span
							>
							<span class="font-semibold whitespace-nowrap tabular-nums">{money(c.amountMillimes)}</span>
						</li>
					{/each}
				</ul>
			</section>
			<section aria-labelledby="material-suppliers" class="card flex flex-col gap-2">
				<h3 id="material-suppliers" class="font-bold">{t('stock.stats.bySupplier')}</h3>
				<ul class="flex flex-col gap-1 text-sm">
					{#each stats.bySupplier as s (s.name ?? '')}
						<li class="flex justify-between gap-2"><span dir="auto">{s.name ?? t('stock.stats.noSupplier')}</span><span class="font-semibold whitespace-nowrap tabular-nums">{money(s.amountMillimes)}</span></li>
					{/each}
				</ul>
			</section>
			<section aria-labelledby="material-top" class="card flex flex-col gap-2">
				<h3 id="material-top" class="font-bold">{t('stock.stats.top')}</h3>
				<ol class="flex flex-col gap-1 text-sm">
					{#each stats.topMaterials as m (m.productId)}
						<li class="flex justify-between gap-2">
							<span><span dir="auto">{m.name}</span> <span class="text-slate-600">({quantityText(m.quantity, m.unit)})</span></span>
							<span class="font-semibold whitespace-nowrap tabular-nums">{money(m.costMillimes)}</span>
						</li>
					{/each}
				</ol>
			</section>
		</div>
	{/if}
</section>
