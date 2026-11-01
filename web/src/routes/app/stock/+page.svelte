<script lang="ts">
	/**
	 * /app/stock – the material of the practice (spec stock-hygiène 4.2): two big buttons on top ("Réception" for the
	 * delivery, "Sortie" for what was used – three taps), then the products with their stock and traffic light, and the
	 * parts "À commander" (by supplier, order by WhatsApp), "Mouvements" (owner: correct a delivery line or delete with
	 * a reason, the change log of the stock), "Fournisseurs" and "Inventaire" (count the shelves, only the differences
	 * are written). `?tab=commander|mouvements|fournisseurs|inventaire` opens a part directly (card on "Aujourd'hui").
	 * A product never received is grey ("Pas encore reçu"), never "à commander". A loading problem says so with
	 * "Réessayer" – never an empty list. In a demo practice nothing opens WhatsApp or a call (fictitious numbers).
	 */
	import { onMount } from 'svelte';
	import { api } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { badges } from '#lib/badges.svelte';
	import { clock } from '#lib/clock';
	import { STOCK_ENTITIES, type AuditEntry } from '#lib/audit';
	import { displayPhone, telUrl, whatsappUrl } from '#lib/agenda/links';
	import { formatDateTime, formatDay, t, todayTunis, translate } from '#lib/i18n.svelte';
	import {
		categoriesFor,
		categoryLabel,
		inventoryReason,
		isToOrder,
		KIND_KEY,
		matches,
		movementService,
		orderMessage,
		orderUrl,
		quantityText,
		STATUS_BAR,
		stockError,
		STATUS_TONE,
		wholeQuantity
	} from '#lib/stock';
	import type { Movement, MovementResult, Product, Supplier, ToOrder } from '#lib/types/stock';
	import ChangeLog from '../../../lib/components/ChangeLog.svelte';
	import Icon from '../../../lib/components/daily/Icon.svelte';
	import Modal from '../../../lib/components/daily/Modal.svelte';
	import ProductDialog from '../../../lib/components/stock/ProductDialog.svelte';
	import ProductSheet from '../../../lib/components/stock/ProductSheet.svelte';
	import ReceiptLineDialog from '../../../lib/components/stock/ReceiptLineDialog.svelte';
	import SupplierDialog from '../../../lib/components/stock/SupplierDialog.svelte';
	import UseDialog from '../../../lib/components/stock/UseDialog.svelte';

	type Tab = 'produits' | 'commander' | 'mouvements' | 'fournisseurs' | 'inventaire';
	const TABS: Tab[] = ['produits', 'commander', 'mouvements', 'fournisseurs', 'inventaire'];
	const TAB_LABEL = {
		produits: 'stock.tabs.products',
		commander: 'stock.tabs.toOrder',
		mouvements: 'stock.tabs.movements',
		fournisseurs: 'stock.tabs.suppliers',
		inventaire: 'stock.tabs.inventory'
	} as const;

	const manager = $derived(auth.role === 'owner' || auth.role === 'assistant');
	const isOwner = $derived(auth.role === 'owner');
	const isDemo = $derived(!!auth.user?.practice?.isDemo);
	const tabs = $derived(TABS.filter((x) => x !== 'inventaire' || manager));
	const today = todayTunis(clock.now());

	function initialTab(): Tab {
		const wanted = typeof location === 'undefined' ? null : new URLSearchParams(location.search).get('tab');
		return TABS.includes(wanted as Tab) ? (wanted as Tab) : 'produits';
	}

	let tab = $state<Tab>(initialTab());
	let products = $state<Product[] | null>(null);
	let suppliers = $state<Supplier[]>([]);
	let loadError = $state('');
	let query = $state('');
	let category = $state('');
	let showInactive = $state(false);
	let notice = $state('');
	let pageError = $state('');

	let using = $state<{ product: Product | null } | null>(null);
	let sheet = $state<Product | null>(null);
	let editing = $state<{ product: Product | null; name?: string } | null>(null);
	let supplierEditing = $state<{ supplier: Supplier | null } | null>(null);

	let toOrder = $state<ToOrder | null>(null);
	let movements = $state<Movement[] | null>(null);
	let log = $state<AuditEntry[] | null>(null);
	let tabError = $state('');
	let logError = $state('');
	let deleting = $state<Movement | null>(null);
	let correcting = $state<Movement | null>(null);
	let deleteReason = $state('');
	let deleteError = $state('');
	let counts = $state<Record<number, string>>({});
	let countReason = $state(inventoryReason(today));
	let busy = $state(false);

	async function load() {
		loadError = '';
		try {
			[products, suppliers] = await Promise.all([api<Product[]>('/api/stock/products'), api<Supplier[]>('/api/stock/suppliers')]);
		} catch {
			loadError = t('stock.loadError');
		}
	}

	async function loadLog() {
		logError = '';
		try {
			log = await api<AuditEntry[]>(`/api/audit-log?entity=${STOCK_ENTITIES}&limit=30`);
		} catch {
			logError = t('audit.loadError');
		}
	}

	/** A part that cannot load says so (review N3): no "Rien à commander" when the network is down. */
	async function loadTab(which: Tab) {
		tabError = '';
		try {
			if (which === 'commander') toOrder = await api<ToOrder>('/api/stock/to-order');
			if (which === 'mouvements') {
				if (isOwner) void loadLog();
				movements = await api<Movement[]>('/api/stock/movements?limit=100');
			}
		} catch {
			tabError = t(which === 'commander' ? 'stock.toOrder.loadError' : 'stock.movements.loadError');
		}
	}

	onMount(() => {
		void load();
		void loadTab(tab);
	});

	function show(which: Tab) {
		tab = which;
		notice = '';
		try {
			const url = new URL(location.href);
			if (which === 'produits') url.searchParams.delete('tab');
			else url.searchParams.set('tab', which);
			history.replaceState(history.state, '', url);
		} catch {
			/* tests without a real location */
		}
		void loadTab(which);
	}

	const visible = $derived(
		(products ?? []).filter((p) => (showInactive || p.active) && (!category || p.category === category) && matches(p, query))
	);
	const orderCount = $derived((products ?? []).filter(isToOrder).length);
	const usedCategories = $derived(categoriesFor(auth.user?.practice?.specialty).filter((c) => (products ?? []).some((p) => p.category === c)));
	const practiceName = $derived(auth.user?.practice?.name ?? '');

	function replace(next: Product) {
		products = products?.some((p) => p.id === next.id) ? products.map((p) => (p.id === next.id ? next : p)) : [...(products ?? []), next];
	}

	function used(result: MovementResult) {
		replace(result.product);
		using = null;
		sheet = null;
		const m = result.movement;
		notice = t('stock.useDialog.saved', {
			quantity: quantityText(-m.quantity, m.unit),
			product: m.productName,
			left: quantityText(result.product.quantity, result.product.unit)
		});
		void badges.refresh();
		if (tab !== 'produits') void loadTab(tab);
	}

	async function starter() {
		busy = true;
		pageError = '';
		try {
			const { created } = await api<{ created: number }>('/api/stock/products/starter', { method: 'POST' });
			notice = created ? t('stock.starterDone', { count: created }) : t('stock.starterNone');
			await load();
		} catch (err) {
			pageError = stockError(err);
		} finally {
			busy = false;
		}
	}

	async function confirmDelete() {
		if (!deleting) return;
		if (!deleteReason.trim()) return void (deleteError = t('errors.validation'));
		busy = true;
		deleteError = '';
		const path = deleting.kind === 'receipt' && deleting.receiptId ? `/api/stock/receipts/${deleting.receiptId}` : `/api/stock/movements/${deleting.id}`;
		try {
			await api(path, { method: 'DELETE', json: { reason: deleteReason.trim() } });
			deleting = null;
			deleteReason = '';
			notice = t('stock.movements.deleted');
			await Promise.all([load(), loadTab('mouvements')]);
			void badges.refresh();
		} catch (err) {
			deleteError = stockError(err);
		} finally {
			busy = false;
		}
	}

	const typed = $derived(Object.entries(counts).filter(([, v]) => v.trim() !== ''));
	/** Whole numbers only – "2,5" is refused with a hint, never rounded in silence (review N2). */
	const countEntries = $derived(
		typed.flatMap(([id, v]) => {
			const counted = wholeQuantity(v, 0);
			return counted === null ? [] : [{ productId: Number(id), counted }];
		})
	);
	const notWhole = $derived(typed.length !== countEntries.length);
	const differences = $derived(countEntries.filter((c) => c.counted !== products?.find((p) => p.id === c.productId)?.quantity).length);

	async function saveInventory(e: SubmitEvent) {
		e.preventDefault();
		pageError = '';
		if (notWhole) return void (pageError = t('stock.wholeNumber'));
		if (!countEntries.length) return void (pageError = t('stock.inventory.none'));
		if (!countReason.trim()) return void (pageError = t('errors.validation'));
		busy = true;
		try {
			const result = await api<{ adjusted: number; products: Product[] }>('/api/stock/inventory', {
				method: 'POST',
				json: { reason: countReason.trim(), counts: countEntries }
			});
			result.products.forEach(replace);
			counts = {};
			notice = t('stock.inventory.saved', { count: result.adjusted });
			void badges.refresh();
		} catch (err) {
			pageError = stockError(err);
		} finally {
			busy = false;
		}
	}

	function savedSupplier(s: Supplier) {
		suppliers = suppliers.some((x) => x.id === s.id) ? suppliers.map((x) => (x.id === s.id ? s : x)) : [...suppliers, s];
		supplierEditing = null;
	}

	async function corrected() {
		correcting = null;
		notice = t('stock.movements.corrected');
		await Promise.all([load(), loadTab('mouvements')]);
		void badges.refresh();
	}

	/** The day a movement stands for: a delivery by its delivery day (review N9). */
	const movementDay = (m: Movement) => m.receivedOn ?? m.createdAt.slice(0, 10);

	const sign = (n: number) => (n > 0 ? `+${n}` : String(n));
</script>

<svelte:head><title>{t('stock.title')} · Daftar</title></svelte:head>

<div class="flex flex-col gap-5">
	<div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
		<div>
			<h1 class="text-2xl font-bold">{t('stock.title')}</h1>
			<p class="text-slate-600">{t('stock.intro')}</p>
		</div>
		<div class="grid grid-cols-2 gap-2 sm:flex">
			{#if manager}
				<a class="btn-primary min-h-14 text-base sm:min-h-12" href="/app/stock/reception"><Icon name="plus" />{t('stock.receive')}</a>
			{/if}
			<button type="button" class="btn-accent min-h-14 text-base sm:min-h-12 {manager ? '' : 'col-span-2'}" onclick={() => (using = { product: null })}
				><Icon name="end" />{t('stock.use')}</button
			>
		</div>
	</div>

	{#if notice}<p role="status" class="rounded-lg bg-emerald-50 px-3 py-2 font-medium text-emerald-900 ring-1 ring-emerald-200">{notice}</p>{/if}
	{#if pageError}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 font-medium text-rose-900 ring-1 ring-rose-200">{pageError}</p>{/if}

	<div role="group" aria-label={t('stock.tabs.label')} class="flex flex-wrap gap-2">
		{#each tabs as which (which)}
			<button
				type="button"
				class="min-h-11 rounded-full px-4 text-sm font-semibold ring-1 transition-colors {tab === which
					? 'bg-brand-700 text-white ring-brand-700'
					: 'bg-white text-slate-700 ring-slate-300 hover:bg-slate-50'}"
				aria-pressed={tab === which}
				onclick={() => show(which)}
				>{t(TAB_LABEL[which])}{#if which === 'commander' && orderCount}{' '}<span
						class="ms-2 rounded-full px-1.5 text-xs font-bold tabular-nums {tab === which ? 'bg-white text-brand-800' : 'bg-accent-400 text-ink'}">{orderCount}</span
					>{/if}</button
			>
		{/each}
	</div>

	{#if loadError}
		<div role="alert" class="card flex flex-wrap items-center justify-between gap-3 border-rose-200 bg-rose-50 text-rose-900">
			<p>{loadError}</p>
			<button type="button" class="btn-secondary" onclick={load}>{t('common.retry')}</button>
		</div>
	{:else if products === null}
		<p class="card text-slate-600" aria-busy="true">{t('common.loading')}</p>
	{:else if tab === 'produits'}
		{#if products.length === 0}
			<section class="card flex flex-col items-start gap-3 border-dashed border-brand-300 bg-brand-50/40 p-5">
				<h2 class="text-lg font-bold">{t('stock.empty.title')}</h2>
				<p class="text-slate-700">{t('stock.empty.text')}</p>
				{#if manager}
					<div class="flex flex-wrap gap-2">
						<button type="button" class="btn-primary" disabled={busy} onclick={starter}>{t('stock.empty.starter')}</button>
						<button type="button" class="btn-secondary" onclick={() => (editing = { product: null })}><Icon name="plus" />{t('stock.empty.add')}</button>
					</div>
				{/if}
			</section>
		{:else}
			<div class="flex flex-col gap-2 sm:flex-row sm:items-end">
				<label class="label flex-1"
					><span class="sr-only">{t('stock.search')}</span>
					<input class="input" type="search" bind:value={query} placeholder={t('stock.search')} autocomplete="off" />
				</label>
				<label class="label sm:w-56"
					><span class="sr-only">{t('stock.category')}</span>
					<select class="input" bind:value={category}>
						<option value="">{t('stock.allCategories')}</option>
						{#each usedCategories as c (c)}<option value={c}>{categoryLabel(c)}</option>{/each}
					</select>
				</label>
				{#if manager}
					<button type="button" class="btn-secondary" onclick={() => (editing = { product: null })}><Icon name="plus" />{t('stock.addProduct')}</button>
				{/if}
			</div>
			{#if visible.length}
				<ul class="flex flex-col gap-2" aria-label={t('stock.listLabel')}>
					{#each visible as p (p.id)}
						<li>
							<button
								type="button"
								class="flex w-full items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 text-start shadow-sm hover:border-brand-300 hover:bg-brand-50/40 {p.active ? '' : 'opacity-70'}"
								onclick={() => (sheet = p)}
							>
								<span class="h-10 w-1.5 shrink-0 rounded-full {STATUS_BAR[p.status]}" aria-hidden="true"></span>
								<span class="min-w-0 flex-1">
									<span class="block font-semibold text-ink" dir="auto">{p.name}</span>
									<span class="block text-sm text-slate-600"
										>{categoryLabel(p.category)}{#if p.supplierName}{' – '}<span dir="auto">{p.supplierName}</span>{/if}</span
									>
									{#if p.status === 'unreceived' && p.active}
										<span class="block text-xs text-slate-600">{t('stock.unreceivedHint')}</span>
									{/if}
									{#if p.expiry && p.expiresOn}
										<span class="mt-1 inline-block rounded px-1.5 text-xs font-semibold {p.expiry === 'expired' ? 'bg-rose-100 text-rose-900' : 'bg-amber-100 text-amber-950'}"
											>{t(p.expiry === 'expired' ? 'stock.expiry.expired' : 'stock.expiry.soon', { date: formatDay(p.expiresOn) })}</span
										>
									{/if}
								</span>
								<span class="flex shrink-0 flex-col items-end gap-1">
									<span class="text-lg font-bold text-ink tabular-nums">{quantityText(p.quantity, p.unit)}</span>
									<span class="rounded-full px-2 py-0.5 text-xs font-semibold ring-1 {STATUS_TONE[p.status]}"
										>{p.active ? translate(`stock.status.${p.status}`) : t('stock.inactive')}</span
									>
								</span>
							</button>
						</li>
					{/each}
				</ul>
			{:else}
				<p class="card text-slate-600">{t('stock.noMatch')}</p>
			{/if}
			{#if products.some((p) => !p.active)}
				<label class="inline-flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" class="h-5 w-5 accent-brand-700" bind:checked={showInactive} />{t('stock.showInactive')}</label>
			{/if}
		{/if}
	{:else if tabError && (tab === 'commander' || tab === 'mouvements')}
		<div role="alert" class="card flex flex-wrap items-center justify-between gap-3 border-rose-200 bg-rose-50 text-rose-900">
			<p>{tabError}</p>
			<button type="button" class="btn-secondary" onclick={() => loadTab(tab)}>{t('common.retry')}</button>
		</div>
	{:else if tab === 'commander'}
		{#if toOrder === null}
			<p class="card text-slate-600" aria-busy="true">{t('common.loading')}</p>
		{:else if toOrder.groups.length === 0}
			<p class="card text-slate-700">{t('stock.toOrder.empty')}</p>
		{:else}
			<div class="grid gap-4 lg:grid-cols-2">
				{#each toOrder.groups as group (group.supplier?.id ?? 0)}
					{@const url = orderUrl(group, practiceName)}
					<section class="card flex flex-col gap-3" aria-labelledby="order-{group.supplier?.id ?? 0}">
						<h2 id="order-{group.supplier?.id ?? 0}" class="text-lg font-bold" dir="auto">{group.supplier?.name ?? t('stock.toOrder.noSupplier')}</h2>
						<ul class="flex flex-col divide-y divide-slate-100">
							{#each group.items as item (item.productId)}
								<li class="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 py-2">
									<span class="font-semibold" dir="auto">{item.name}</span>
									<span class="text-sm text-slate-600">{t('stock.toOrder.stock', { quantity: quantityText(item.quantity, item.unit), min: item.minQuantity })}</span>
									<span class="w-full font-semibold text-brand-800">{t('stock.toOrder.suggested', { quantity: quantityText(item.suggested, item.unit) })}</span>
								</li>
							{/each}
						</ul>
						{#if group.supplier && isDemo}
							<p class="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900 ring-1 ring-amber-200">{t('stock.toOrder.demo')}</p>
							<p class="rounded-lg bg-slate-50 px-3 py-2 text-sm whitespace-pre-line text-slate-800" dir="auto">{orderMessage(group, practiceName)}</p>
						{:else if group.supplier}
							<div class="flex flex-wrap gap-2">
								{#if url}
									<a class="btn min-h-12 bg-[#25d366] text-ink hover:bg-[#1ebe5b]" href={url} target="_blank" rel="noopener noreferrer"
										><Icon name="chat" />{t('stock.toOrder.whatsapp')}</a
									>
								{/if}
								{#if group.supplier.phone}
									<a class="btn-secondary min-h-12" href={telUrl(group.supplier.phone)}><Icon name="phone" />{t('stock.toOrder.call')}</a>
								{/if}
							</div>
						{:else}
							<p class="text-sm text-slate-600">{t('stock.toOrder.noSupplierHint')}</p>
						{/if}
					</section>
				{/each}
			</div>
		{/if}
	{:else if tab === 'mouvements'}
		{#if movements === null}
			<p class="card text-slate-600" aria-busy="true">{t('common.loading')}</p>
		{:else if movements.length === 0}
			<p class="card text-slate-700">{t('stock.movements.empty')}</p>
		{:else}
			<ul class="card flex flex-col divide-y divide-slate-100 p-0" aria-label={t('stock.movements.label')}>
				{#each movements as m (m.id)}
					<li class="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3">
						<span class="w-16 shrink-0 text-lg font-bold tabular-nums {m.quantity > 0 ? 'text-emerald-800' : 'text-rose-800'}" dir="ltr">{sign(m.quantity)}</span>
						<span class="min-w-0 flex-1">
							<span class="block font-semibold" dir="auto">{m.productName}</span>
							<span class="block text-sm text-slate-600"
								>{t(KIND_KEY[m.kind])}{#if m.receivedOn}{' – '}{formatDay(m.receivedOn)}{/if}{#if m.serviceName}{' – '}<span dir="auto">{movementService(m)}</span>{/if}{#if m.patientName}{' – '}<span dir="auto">{m.patientName}</span
									>{/if}{#if m.reason}{' – '}<span dir="auto">{m.reason}</span>{/if}</span
							>
							<span class="block text-xs text-slate-500"
								>{formatDateTime(m.createdAt)}{#if m.createdBy}<span dir="auto"> {t('stock.movements.by', { name: m.createdBy })}</span>{/if}</span
							>
						</span>
						{#if isOwner}
							<span class="flex flex-wrap gap-2">
								{#if m.kind === 'receipt' && m.receiptLineId}
									<button
										type="button"
										class="btn-secondary min-h-11 px-3 text-sm"
										aria-label={t('stock.movements.correctLabel', { product: m.productName })}
										onclick={() => (correcting = m)}>{t('stock.movements.correct')}</button
									>
								{/if}
								<button
									type="button"
									class="btn-secondary min-h-11 px-3 text-sm text-rose-800"
									onclick={() => ((deleting = m), (deleteReason = ''), (deleteError = ''))}
									>{m.kind === 'receipt' ? t('stock.movements.deleteReceipt') : t('stock.movements.delete')}</button
								>
							</span>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
		{#if isOwner}
			<section aria-labelledby="stock-log" class="flex flex-col gap-2">
				<h2 id="stock-log" class="text-lg font-bold">{t('stock.movements.log')}</h2>
				<ChangeLog entries={log} error={logError} label={t('stock.movements.log')} onretry={loadLog} />
			</section>
		{/if}
	{:else if tab === 'fournisseurs'}
		{#if manager}
			<button type="button" class="btn-secondary self-start" onclick={() => (supplierEditing = { supplier: null })}><Icon name="plus" />{t('stock.suppliers.add')}</button>
		{/if}
		{#if suppliers.length === 0}
			<p class="card text-slate-700">{t('stock.suppliers.empty')}</p>
		{:else}
			<ul class="grid gap-3 md:grid-cols-2" aria-label={t('stock.suppliers.label')}>
				{#each suppliers as s (s.id)}
					<li class="card flex flex-col gap-2 {s.active ? '' : 'opacity-70'}">
						<div class="flex items-start justify-between gap-2">
							<div class="min-w-0">
								<p class="font-bold" dir="auto">{s.name}</p>
								<p class="text-sm text-slate-600">
									{t('stock.suppliers.products', { count: s.products })}{#if !s.active}{' – '}{t('stock.suppliers.inactive')}{/if}
								</p>
								{#if s.note}<p class="text-sm text-slate-700" dir="auto">{s.note}</p>{/if}
							</div>
							{#if manager}
								<button
									type="button"
									class="btn -me-2 min-h-11 min-w-11 px-2 text-slate-600 hover:bg-slate-100"
									aria-label={t('stock.suppliers.edit', { name: s.name })}
									onclick={() => (supplierEditing = { supplier: s })}><Icon name="edit" /></button
								>
							{/if}
						</div>
						{#if isDemo && (s.phone || s.whatsapp)}
							<p class="text-sm text-slate-600"><span dir="ltr">{displayPhone(s.phone ?? s.whatsapp)}</span> – {t('stock.suppliers.demo')}</p>
						{:else}
						<div class="flex flex-wrap gap-2">
							{#if s.phone}
								<a class="btn-secondary min-h-11 text-sm" href={telUrl(s.phone)} aria-label={t('stock.suppliers.call', { name: s.name })}
									><Icon name="phone" class="h-4 w-4" /><span dir="ltr">{displayPhone(s.phone)}</span></a
								>
							{/if}
							{#if s.whatsapp}
								<a class="btn-secondary min-h-11 text-sm" href={whatsappUrl(s.whatsapp)} target="_blank" rel="noopener noreferrer"
									><Icon name="chat" class="h-4 w-4" />{t('stock.suppliers.whatsapp', { name: s.name })}</a
								>
							{/if}
						</div>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	{:else if tab === 'inventaire' && manager}
		<form class="flex flex-col gap-3" onsubmit={saveInventory} novalidate>
			<p class="text-slate-700">{t('stock.inventory.intro')}</p>
			<label class="label sm:max-w-md">{t('stock.inventory.reason')}<input class="input" bind:value={countReason} maxlength="300" autocomplete="off" /></label>
			<ul class="card flex flex-col divide-y divide-slate-100 p-0" aria-label={t('stock.inventory.label')}>
				{#each products.filter((p) => p.active) as p (p.id)}
					<li class="flex items-center gap-3 px-4 py-2">
						<label for="count-{p.id}" class="min-w-0 flex-1">
							<span class="block font-semibold" dir="auto">{p.name}</span>
							<span class="block text-sm text-slate-600">{t('stock.inventory.expected', { quantity: quantityText(p.quantity, p.unit) })}</span>
						</label>
						<input
							id="count-{p.id}"
							class="input w-24 text-center tabular-nums"
							type="number"
							inputmode="numeric"
							min="0"
							step="1"
							placeholder={String(Math.max(p.quantity, 0))}
							value={counts[p.id] ?? ''}
							oninput={(e) => (counts = { ...counts, [p.id]: (e.currentTarget as HTMLInputElement).value })}
						/>
					</li>
				{/each}
			</ul>
			<div class="sticky bottom-16 flex flex-wrap items-center justify-end gap-3 rounded-xl bg-white/95 p-2 md:bottom-2">
				<span class="text-sm font-semibold text-slate-700">{t('stock.inventory.differences', { count: differences })}</span>
				<button type="submit" class="btn-primary min-h-12" disabled={busy}>{t('stock.inventory.save')}</button>
			</div>
		</form>
	{/if}
</div>

{#if using}
	<UseDialog products={products ?? []} preselected={using.product} onsaved={used} onclose={() => (using = null)} />
{/if}
{#if sheet}
	<ProductSheet
		product={sheet}
		onuse={(p) => ((sheet = null), (using = { product: p }))}
		onedit={(p) => ((sheet = null), (editing = { product: p }))}
		onchanged={replace}
		onclose={() => (sheet = null)}
	/>
{/if}
{#if editing}
	{#key editing}
	<ProductDialog
		product={editing.product}
		initialName={editing.name ?? ''}
		{suppliers}
		onnew={(name) => (editing = { product: null, name })}
		onsaved={(p) => {
			replace(p);
			editing = null;
			notice = t('stock.product.saved');
		}}
		ondeleted={(id) => {
			products = (products ?? []).filter((p) => p.id !== id);
			editing = null;
			notice = t('stock.product.deleted');
		}}
		onclose={() => (editing = null)}
	/>
	{/key}
{/if}
{#if supplierEditing}
	<SupplierDialog
		supplier={supplierEditing.supplier}
		onsaved={savedSupplier}
		ondeleted={(id) => ((suppliers = suppliers.filter((s) => s.id !== id)), (supplierEditing = null))}
		onclose={() => (supplierEditing = null)}
	/>
{/if}
{#if correcting}
	<ReceiptLineDialog movement={correcting} onsaved={corrected} onclose={() => (correcting = null)} />
{/if}
{#if deleting}
	<Modal
		title={deleting.kind === 'receipt' ? t('stock.movements.deleteReceiptTitle', { date: formatDay(movementDay(deleting)) }) : t('stock.movements.deleteTitle')}
		subtitle={`${deleting.productName} ${sign(deleting.quantity)}`}
		onclose={() => (deleting = null)}
	>
		<div class="flex flex-col gap-3">
			<p class="text-slate-700">{t('stock.movements.deleteText')}</p>
			<label class="label">{t('stock.movements.reason')}<input class="input" bind:value={deleteReason} maxlength="300" autocomplete="off" data-autofocus /></label>
			{#if deleteError}<p role="alert" class="text-sm font-medium text-rose-800">{deleteError}</p>{/if}
		</div>
		{#snippet footer()}
			<button type="button" class="btn-secondary" onclick={() => (deleting = null)}>{t('common.cancel')}</button>
			<button type="button" class="btn bg-rose-700 text-white hover:bg-rose-800" disabled={busy} onclick={confirmDelete}>{t('stock.movements.confirm')}</button>
		{/snippet}
	</Modal>
{/if}
