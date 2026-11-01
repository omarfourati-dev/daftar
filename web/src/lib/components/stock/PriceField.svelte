<script lang="ts">
	/**
	 * A unit price typed in dinars, read back while typing (review H2): "Soit 13 500 DT par boîte" – so "13500" for
	 * "13,500" shows at once. An unusual price (above 500 DT or far from the average) is marked; the page asks before
	 * saving.
	 */
	import { money } from '../../agenda/format';
	import { t } from '../../i18n.svelte';
	import { parseDinars } from '../../money-input';
	import { unitLabel, unusualPrice } from '../../stock';
	import type { StockUnit } from '../../types/stock';

	type Props = { id: string; label: string; value: string; unit: StockUnit; average?: number | null; class?: string };
	let { id, label, value = $bindable(), unit, average = null, class: extra = '' }: Props = $props();

	const millimes = $derived(parseDinars(value));
	const valid = $derived(millimes !== null && !Number.isNaN(millimes));
	const unusual = $derived(valid && unusualPrice(millimes, average));
</script>

<div class="flex flex-col gap-1 {extra}">
	<label class="text-sm font-medium text-slate-700" for={id}>{label}</label>
	<input
		{id}
		class="input tabular-nums {unusual ? 'ring-2 ring-amber-400' : ''}"
		inputmode="decimal"
		bind:value
		autocomplete="off"
		dir="ltr"
		aria-describedby="{id}-reads"
	/>
	<p id="{id}-reads" class="min-h-4 text-xs {unusual ? 'font-semibold text-amber-900' : 'text-slate-600'}">
		{#if valid && millimes !== null}{t('stock.receipt.reads', { price: money(millimes), unit: unitLabel(unit) })}{/if}
	</p>
</div>
