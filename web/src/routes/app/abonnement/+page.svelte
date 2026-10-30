<script lang="ts">
	/**
	 * `/app/abonnement` (section 11.4, story I1) – the owner's plan, status, paid-until and invoices; "Payer avec
	 * Flouci" only when online payment is available (otherwise bank transfer). Back from Flouci
	 * (`?invoice=<id>&payment=success|fail`) the payment is verified with the server, never trusted from the URL.
	 */
	import { onMount } from 'svelte';
	import { api, apiErrorMessage } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { formatDate, formatDay, formatMillimes, i18n, t, translate } from '#lib/i18n.svelte';
	import { navigation } from '#lib/navigate';
	import type { Me } from '#lib/types';
	import type { Billing, Invoice, Plan } from '#lib/types/billing';
	import LoadState from '../../../lib/components/LoadState.svelte';
	import StatusBadge from '../../../lib/components/practice/StatusBadge.svelte';
	import OwnerOnly from '../../../lib/components/reglages/OwnerOnly.svelte';

	const CONTACT = 'info@omarfourati.de';
	let billing = $state<Billing | null>(null);
	let loading = $state(true);
	let error = $state('');
	let notice = $state<{ kind: 'ok' | 'pending' | 'failed'; text: string } | null>(null);
	let verifying = $state(false);
	let paying = $state<number | null>(null);
	let payError = $state('');
	let returned: { id: string; failed: boolean } | null = null;

	async function load() {
		loading = true;
		error = '';
		try {
			billing = await api<Billing>('/api/billing');
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			loading = false;
		}
	}

	async function verify(id: string, failed: boolean) {
		verifying = true;
		try {
			const invoice = await api<Invoice>(`/api/billing/invoices/${encodeURIComponent(id)}/verify`, { method: 'POST' });
			notice =
				invoice?.status === 'paid'
					? { kind: 'ok', text: t('billing.paidOk') }
					: failed
						? { kind: 'failed', text: t('billing.paidFailed') }
						: { kind: 'pending', text: t('billing.paidPending') };
			if (invoice?.status === 'paid') void api<Me>('/api/auth/me').then((me) => auth.setUser(me)).catch(() => undefined);
		} catch (err) {
			notice = { kind: 'failed', text: apiErrorMessage(err) };
		} finally {
			verifying = false;
		}
	}

	onMount(async () => {
		if (auth.user?.role !== 'owner') return;
		const params = new URLSearchParams(location.search);
		const invoice = params.get('invoice');
		if (invoice && /^\d+$/.test(invoice)) {
			returned = { id: invoice, failed: params.get('payment') === 'fail' };
			history.replaceState(history.state, '', '/app/abonnement'); // no payment ids in the address bar
			await verify(returned.id, returned.failed);
		}
		await load();
	});

	async function pay(invoice: Invoice) {
		paying = invoice.id;
		payError = '';
		try {
			const { paymentUrl } = await api<{ paymentUrl: string }>(`/api/billing/invoices/${invoice.id}/pay`, { method: 'POST' });
			navigation.assign(paymentUrl);
		} catch (err) {
			payError = apiErrorMessage(err);
			paying = null;
		}
	}

	const plan = $derived<Plan | null>(
		!billing ? null : typeof billing.plan === 'string' ? (billing.plans.find((p) => p.code === billing!.plan) ?? null) : billing.plan
	);
	const planCode = $derived(!billing ? '' : typeof billing.plan === 'string' ? billing.plan : (billing.plan?.code ?? ''));
	const planName = (p: Plan | null, code: string) =>
		p ? (i18n.locale === 'ar' && p.nameAr ? p.nameAr : p.nameFr) : (translate(`admin.plans.${code}`) ?? code);
	const price = (p: Plan) =>
		p.priceMillimes === 0
			? t('billing.free')
			: p.periodMonths === 1
				? t('billing.perMonth', { price: formatMillimes(p.priceMillimes) })
				: t('billing.perMonths', { price: formatMillimes(p.priceMillimes), n: p.periodMonths });
	const mailto = $derived(
		`mailto:${CONTACT}?subject=${encodeURIComponent(`Abonnement Daftar – ${auth.user?.practice?.name ?? ''}`)}`
	);
	const noticeClass = { ok: 'bg-emerald-50 text-emerald-900 ring-emerald-200', pending: 'bg-amber-50 text-amber-950 ring-amber-200', failed: 'bg-rose-50 text-rose-900 ring-rose-200' };
</script>

<svelte:head><title>{t('billing.title')} · Daftar</title></svelte:head>

<OwnerOnly>
	<div class="flex max-w-3xl flex-col gap-6">
		<h1 class="text-2xl font-bold text-ink">{t('billing.title')}</h1>

		{#if verifying}<p role="status" class="text-slate-600">{t('billing.checking')}</p>{/if}
		{#if notice}
			<div class="flex flex-wrap items-center gap-3 rounded-xl px-4 py-3 ring-1 {noticeClass[notice.kind]}">
				<p role="status" class="font-medium">{notice.text}</p>
				{#if notice.kind === 'pending' && returned}
					<button type="button" class="btn-secondary min-h-9 py-1 text-sm" onclick={() => returned && verify(returned.id, returned.failed)}
						>{t('billing.verifyAgain')}</button
					>
				{/if}
			</div>
		{/if}

		<LoadState {loading} {error} onretry={load} />

		{#if billing}
			<section class="card flex flex-col gap-4" aria-labelledby="bill-plan">
				<div class="flex flex-wrap items-start justify-between gap-3">
					<div class="flex flex-col gap-1">
						<h2 id="bill-plan" class="text-sm font-medium text-slate-600">{t('billing.plan')}</h2>
						<p class="text-xl font-bold text-ink">{planName(plan, planCode)}</p>
						{#if plan}<p class="text-slate-700">{price(plan)}</p>{/if}
					</div>
					<dl class="grid grid-cols-[auto_auto] items-center gap-x-4 gap-y-2 text-sm">
						<dt class="text-slate-600">{t('billing.status')}</dt>
						<dd><StatusBadge status={billing.status} /></dd>
						<dt class="text-slate-600">{t('billing.paidUntil')}</dt>
						<dd class="font-semibold tabular-nums">{billing.paidUntil ? formatDay(billing.paidUntil) : t('kit.none')}</dd>
					</dl>
				</div>
				{#if billing.status === 'pilot'}
					<p class="rounded-lg bg-sky-50 px-3 py-2 text-sky-950">
						{billing.paidUntil ? t('billing.pilotInfo', { date: formatDay(billing.paidUntil) }) : t('billing.pilotInfoNoDate')}
					</p>
				{:else if billing.status === 'suspended'}
					<p class="rounded-lg bg-rose-50 px-3 py-2 text-rose-950">{t('billing.suspendedInfo')}</p>
				{:else if billing.status === 'past_due'}
					<p class="rounded-lg bg-amber-50 px-3 py-2 text-amber-950">{t('billing.pastDue')}</p>
				{/if}
			</section>

			<section class="card flex flex-col gap-3" aria-labelledby="bill-invoices">
				<h2 id="bill-invoices" class="text-lg font-bold text-ink">{t('billing.invoices')}</h2>
				{#if billing.invoices.length === 0}
					<p class="text-slate-600">{t('billing.noInvoices')}</p>
				{:else}
					<ul class="flex flex-col divide-y divide-slate-100">
						{#each billing.invoices as invoice (invoice.id)}
							<li class="flex flex-wrap items-center gap-x-4 gap-y-2 py-3">
								<div class="flex min-w-0 flex-1 flex-col">
									<span class="font-mono font-semibold" dir="ltr">{invoice.number}</span>
									<span class="text-sm text-slate-600 tabular-nums">{formatDay(invoice.periodStart)} – {formatDay(invoice.periodEnd)}</span>
								</div>
								<span class="font-semibold tabular-nums">{formatMillimes(invoice.amountMillimes)}</span>
								<span class="flex flex-col text-sm">
									{#if invoice.status === 'paid'}
										<span class="font-medium text-emerald-800">{t('billing.paidOn', { date: invoice.paidAt ? formatDate(invoice.paidAt) : '' })}</span>
									{:else}
										<span class={invoice.status === 'open' ? 'font-semibold text-amber-800' : 'text-slate-500 line-through'}
											>{translate(`billing.invoiceStatus.${invoice.status}`) ?? invoice.status}</span
										>
										{#if invoice.status === 'open'}<span class="text-slate-600">{t('billing.dueOn', { date: formatDay(invoice.dueOn) })}</span>{/if}
									{/if}
								</span>
								{#if invoice.status === 'open' && billing.onlinePaymentAvailable}
									<button
										type="button"
										class="btn-primary"
										disabled={paying !== null}
										aria-label={t('billing.payLabel', { number: invoice.number })}
										onclick={() => pay(invoice)}>{paying === invoice.id ? t('billing.paying') : t('billing.pay')}</button
									>
								{/if}
							</li>
						{/each}
					</ul>
				{/if}
				{#if payError}<p role="alert" class="text-sm font-medium text-red-700">{payError}</p>{/if}
				{#if !billing.onlinePaymentAvailable}
					<div class="flex flex-col items-start gap-2 rounded-lg bg-slate-50 p-3">
						<p class="text-slate-700">{t('billing.transfer')}</p>
						<a class="btn-secondary" href={mailto}>{t('billing.contact')}</a>
					</div>
				{/if}
			</section>

			{#if billing.plans.length}
				<section class="flex flex-col gap-2" aria-labelledby="bill-plans">
					<h2 id="bill-plans" class="font-bold text-ink">{t('billing.plans')}</h2>
					<ul class="grid gap-2 sm:grid-cols-2">
						{#each billing.plans.filter((p) => p.active !== false) as p (p.code)}
							<li class="card flex items-center justify-between gap-3 py-3 {p.code === planCode ? 'ring-2 ring-brand-700' : ''}">
								<span class="font-semibold">{planName(p, p.code)}</span>
								<span class="text-sm text-slate-700">{price(p)}</span>
							</li>
						{/each}
					</ul>
					<p class="text-sm text-slate-600">{t('billing.changePlan')} <a class="font-medium text-brand-700 underline" href={mailto}>{CONTACT}</a></p>
				</section>
			{/if}
		{/if}
	</div>
</OwnerOnly>
