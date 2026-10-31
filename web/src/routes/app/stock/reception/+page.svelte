<script lang="ts">
	/**
	 * /app/stock/reception – a delivery in under a minute on the phone (spec stock-hygiène 4.2): supplier (or a new one),
	 * then one line per product of the delivery note – search, tap, quantity with − / +, unit price (the last average
	 * price is proposed), lot and expiry folded away. The total follows live; one button saves everything. A product that
	 * does not exist yet is created from the search without leaving the page.
	 */
	import { onMount, tick } from 'svelte';
	import { api } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { badges } from '#lib/badges.svelte';
	import { clock } from '#lib/clock';
	import { money } from '#lib/agenda/format';
	import { t, todayTunis } from '#lib/i18n.svelte';
	import { dinarsText, parseDinars } from '#lib/money-input';
	import { matches, stockError, unitWord } from '#lib/stock';
	import type { Product, Receipt, Supplier } from '#lib/types/stock';
	import Icon from '../../../../lib/components/daily/Icon.svelte';
	import ProductDialog from '../../../../lib/components/stock/ProductDialog.svelte';
	import SupplierDialog from '../../../../lib/components/stock/SupplierDialog.svelte';

	type Line = { key: number; product: Product; quantity: number; price: string; lot: string; expiresOn: string; open: boolean };

	const today = todayTunis(clock.now());
	const manager = $derived(auth.role === 'owner' || auth.role === 'assistant');
	let products = $state<Product[] | null>(null);
	let suppliers = $state<Supplier[]>([]);
	let loadError = $state('');
	let supplierId = $state('');
	let receivedOn = $state(today);
	let reference = $state('');
	let note = $state('');
	let lines = $state<Line[]>([]);
	let query = $state('');
	let error = $state('');
	let busy = $state(false);
	let saved = $state<Receipt | null>(null);
	let creatingProduct = $state<string | null>(null);
	let creatingSupplier = $state(false);
	let nextKey = 1;

	async function load() {
		loadError = '';
		try {
			[products, suppliers] = await Promise.all([api<Product[]>('/api/stock/products'), api<Supplier[]>('/api/stock/suppliers')]);
			const active = suppliers.filter((s) => s.active);
			if (!supplierId && active.length === 1) supplierId = String(active[0].id);
		} catch {
			loadError = t('stock.loadError');
		}
	}
	onMount(load);

	const MATCHES = 6;
	const found = $derived(query.trim() ? (products ?? []).filter((p) => p.active && matches(p, query)).slice(0, MATCHES) : []);
	const exact = $derived((products ?? []).some((p) => p.name.trim().toLowerCase() === query.trim().toLowerCase()));
	const total = $derived(lines.reduce((sum, l) => sum + l.quantity * (Number(parseDinars(l.price)) || 0), 0));

	async function add(product: Product) {
		const key = nextKey++;
		lines = [...lines, { key, product, quantity: 1, price: dinarsText(product.averageCostMillimes), lot: '', expiresOn: '', open: false }];
		if (!supplierId && product.supplierId) supplierId = String(product.supplierId);
		query = '';
		error = '';
		await tick();
		const field = document.getElementById(`qty-${key}`) as HTMLInputElement | null;
		field?.focus();
		field?.select();
	}

	function step(line: Line, by: number) {
		line.quantity = Math.min(100000, Math.max(1, (Number(line.quantity) || 0) + by));
	}

	function remove(key: number) {
		lines = lines.filter((l) => l.key !== key);
	}

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		if (!lines.length) return void (error = t('stock.receipt.noLines'));
		const body = [];
		for (const line of lines) {
			const price = parseDinars(line.price);
			if (Number.isNaN(price)) return void (error = t('stock.receipt.invalidPrice', { product: line.product.name }));
			const quantity = Math.round(Number(line.quantity));
			if (!Number.isFinite(quantity) || quantity < 1) return void (error = t('errors.validation'));
			body.push({
				productId: line.product.id,
				quantity,
				unitPriceMillimes: price,
				lot: line.lot.trim(),
				expiresOn: line.expiresOn || null
			});
		}
		busy = true;
		try {
			saved = await api<Receipt>('/api/stock/receipts', {
				method: 'POST',
				json: { receivedOn, supplierId: supplierId ? Number(supplierId) : null, reference: reference.trim(), note: note.trim(), lines: body }
			});
			void badges.refresh();
		} catch (err) {
			error = stockError(err);
		} finally {
			busy = false;
		}
	}

	function again() {
		saved = null;
		lines = [];
		reference = '';
		note = '';
		receivedOn = today;
		void load();
	}
</script>

<svelte:head><title>{t('stock.receipt.title')} · Daftar</title></svelte:head>

<div class="mx-auto flex w-full max-w-2xl flex-col gap-5">
	<div>
		<a class="inline-flex min-h-11 items-center gap-1 text-sm font-semibold text-brand-800" href="/app/stock"><Icon name="start" class="h-4 w-4" />{t('stock.title')}</a>
		<h1 class="text-2xl font-bold">{t('stock.receipt.title')}</h1>
		<p class="text-slate-600">{t('stock.receipt.subtitle')}</p>
	</div>

	{#if !manager}
		<p class="card text-slate-700">{t('errors.forbidden')}</p>
	{:else if loadError}
		<div role="alert" class="card flex flex-wrap items-center justify-between gap-3 border-rose-200 bg-rose-50 text-rose-900">
			<p>{loadError}</p>
			<button type="button" class="btn-secondary" onclick={load}>{t('common.retry')}</button>
		</div>
	{:else if products === null}
		<p class="card text-slate-600" aria-busy="true">{t('common.loading')}</p>
	{:else if saved}
		<section class="card flex flex-col gap-3 border-emerald-200 bg-emerald-50/60 p-5" aria-live="polite">
			<p class="flex items-center gap-2 text-lg font-bold text-emerald-900">
				<Icon name="check" />{t('stock.receipt.saved', { lines: saved.lines.length, total: money(saved.totalMillimes) })}
			</p>
			<div class="flex flex-wrap gap-2">
				<a class="btn-primary" href="/app/stock">{t('stock.receipt.back')}</a>
				<button type="button" class="btn-secondary" onclick={again}><Icon name="plus" />{t('stock.receipt.another')}</button>
			</div>
		</section>
	{:else}
		<form class="flex flex-col gap-4 pb-24 md:pb-4" onsubmit={submit} novalidate>
			<section class="card flex flex-col gap-3">
				<div class="flex items-end gap-2">
					<label class="label flex-1"
						>{t('stock.receipt.supplier')}
						<select class="input" bind:value={supplierId}>
							<option value="">{t('stock.receipt.chooseSupplier')}</option>
							{#each suppliers.filter((s) => s.active || String(s.id) === supplierId) as s (s.id)}<option value={String(s.id)}>{s.name}</option>{/each}
						</select>
					</label>
					<button type="button" class="btn-secondary min-h-11 px-3" onclick={() => (creatingSupplier = true)}
						><Icon name="plus" class="h-4 w-4" /><span class="max-sm:sr-only">{t('stock.receipt.newSupplier')}</span></button
					>
				</div>
				<div class="grid grid-cols-2 gap-3">
					<label class="label">{t('stock.receipt.date')}<input class="input" type="date" bind:value={receivedOn} max={today} /></label>
					<label class="label">{t('stock.receipt.reference')}<input class="input" bind:value={reference} maxlength="60" autocomplete="off" dir="auto" /></label>
				</div>
			</section>

			<section class="card flex flex-col gap-3" aria-labelledby="receipt-lines">
				<h2 id="receipt-lines" class="text-lg font-bold">{t('stock.receipt.lines')}</h2>
				{#if lines.length}
					<ul class="flex flex-col gap-3">
						{#each lines as line (line.key)}
							<li class="flex flex-col gap-2 rounded-xl border border-slate-200 p-3">
								<div class="flex items-start gap-2">
									<p class="min-w-0 flex-1 pt-2 font-semibold" dir="auto">{line.product.name}</p>
									<button
										type="button"
										class="btn -me-1 min-h-11 min-w-11 px-2 text-slate-600 hover:bg-slate-100"
										aria-label={t('stock.receipt.remove', { product: line.product.name })}
										onclick={() => remove(line.key)}><Icon name="trash" /></button
									>
								</div>
								<div class="flex flex-wrap items-end gap-3">
									<div class="flex flex-col gap-1">
										<label class="text-sm font-medium text-slate-700" for="qty-{line.key}">{t('stock.receipt.quantity')}</label>
										<div class="flex items-center gap-1">
											<button type="button" class="btn-secondary min-h-11 min-w-11 px-0 text-lg" aria-label={t('stock.useDialog.less')} onclick={() => step(line, -1)}>−</button>
											<input id="qty-{line.key}" class="input w-20 text-center font-bold tabular-nums" type="number" inputmode="numeric" min="1" bind:value={line.quantity} />
											<button type="button" class="btn-secondary min-h-11 min-w-11 px-0 text-lg" aria-label={t('stock.useDialog.more')} onclick={() => step(line, 1)}>+</button>
											<span class="ms-1 text-sm text-slate-600">{unitWord(Number(line.quantity) || 0, line.product.unit)}</span>
										</div>
									</div>
									<label class="label w-32">{t('stock.receipt.unitPrice')}<input class="input tabular-nums" inputmode="decimal" bind:value={line.price} autocomplete="off" dir="ltr" /></label>
								</div>
								<button type="button" class="min-h-11 self-start text-sm font-semibold text-brand-800 underline-offset-2 hover:underline" aria-expanded={line.open} onclick={() => (line.open = !line.open)}
									>{t('stock.receipt.more')}</button
								>
								{#if line.open}
									<div class="grid grid-cols-2 gap-3">
										<label class="label">{t('stock.receipt.lot')}<input class="input" bind:value={line.lot} maxlength="60" autocomplete="off" dir="ltr" /></label>
										<label class="label">{t('stock.receipt.expiresOn')}<input class="input" type="date" bind:value={line.expiresOn} /></label>
									</div>
								{/if}
							</li>
						{/each}
					</ul>
				{/if}
				<div class="flex flex-col gap-2">
					<label class="label"
						>{t('stock.receipt.searchProduct')}
						<input class="input" type="search" bind:value={query} placeholder={t('stock.receipt.searchPlaceholder')} autocomplete="off" />
					</label>
					{#if query.trim()}
						<ul class="flex flex-col gap-1">
							{#each found as p (p.id)}
								<li>
									<button type="button" class="flex min-h-12 w-full items-center gap-2 rounded-lg px-3 text-start hover:bg-brand-50" onclick={() => add(p)}
										><Icon name="plus" class="h-4 w-4 text-brand-700" /><span class="font-medium" dir="auto">{p.name}</span></button
									>
								</li>
							{/each}
							{#if !exact}
								<li>
									<button type="button" class="flex min-h-12 w-full items-center gap-2 rounded-lg px-3 text-start font-semibold text-brand-800 hover:bg-brand-50" onclick={() => (creatingProduct = query.trim())}
										><Icon name="plus" class="h-4 w-4" />{t('stock.receipt.create', { name: query.trim() })}</button
									>
								</li>
							{/if}
						</ul>
					{/if}
				</div>
			</section>

			<label class="label">{t('stock.receipt.note')}<input class="input" bind:value={note} maxlength="500" autocomplete="off" dir="auto" /></label>
			{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}

			<div class="fixed inset-x-0 bottom-14 z-10 flex items-center gap-3 border-t border-slate-200 bg-white px-4 py-2 md:static md:rounded-xl md:border md:px-4">
				<p class="flex-1 text-sm text-slate-600">
					{t('stock.receipt.total')} <span class="block text-xl font-bold text-ink tabular-nums">{money(total)}</span>
				</p>
				<button type="submit" class="btn-primary min-h-12" disabled={busy}><Icon name="check" />{t('stock.receipt.save')}</button>
			</div>
		</form>
	{/if}
</div>

{#if creatingProduct !== null}
	<ProductDialog
		initialName={creatingProduct}
		{suppliers}
		onsaved={(p) => {
			products = [...(products ?? []), p];
			creatingProduct = null;
			void add(p);
		}}
		onclose={() => (creatingProduct = null)}
	/>
{/if}
{#if creatingSupplier}
	<SupplierDialog
		onsaved={(s) => {
			suppliers = [...suppliers, s];
			supplierId = String(s.id);
			creatingSupplier = false;
		}}
		onclose={() => (creatingSupplier = false)}
	/>
{/if}
