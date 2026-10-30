<script lang="ts">
	/**
	 * Admin – subscriptions of all practices (section 11.4, story I1): plan, status, paid until, open amount,
	 * invoices; create the next invoice, record a manual payment, void an invoice.
	 */
	import { onMount } from 'svelte';
	import { api, apiErrorMessage } from '#lib/api';
	import { formatDate, formatDay, formatMillimes, t, translate } from '#lib/i18n.svelte';
	import { INVOICE_METHODS, type AdminBillingRow, type Invoice } from '#lib/types/billing';
	import AdminTabs from '../../../../lib/components/admin/AdminTabs.svelte';
	import ConfirmDialog from '../../../../lib/components/ConfirmDialog.svelte';
	import LoadState from '../../../../lib/components/LoadState.svelte';
	import Modal from '../../../../lib/components/Modal.svelte';
	import StatusBadge from '../../../../lib/components/practice/StatusBadge.svelte';

	let rows = $state<AdminBillingRow[]>([]);
	let loading = $state(true);
	let error = $state('');
	let notice = $state('');
	let actionError = $state('');
	let paying = $state<Invoice | null>(null);
	let method = $state('virement');
	let voiding = $state<Invoice | null>(null);
	let busy = $state(false);

	async function load(quiet = false) {
		if (!quiet) loading = true;
		error = '';
		try {
			const answer = await api<AdminBillingRow[] | { practices: AdminBillingRow[] }>('/api/admin/billing');
			rows = (Array.isArray(answer) ? answer : (answer.practices ?? [])).map((r) => ({ ...r, invoices: r.invoices ?? [] }));
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			loading = false;
		}
	}
	onMount(() => load());

	async function act(path: string, json: unknown, done: (result: Invoice) => string) {
		busy = true;
		actionError = '';
		notice = '';
		try {
			const result = await api<Invoice>(path, { method: 'POST', json });
			notice = done(result);
			paying = null;
			voiding = null;
			await load(true);
		} catch (err) {
			actionError = apiErrorMessage(err);
		} finally {
			busy = false;
		}
	}

	const markPaid = () => paying && act(`/api/admin/invoices/${paying.id}/mark-paid`, { method }, () => t('admin.billing.paidDone'));
	const voidInvoice = () => voiding && act(`/api/admin/invoices/${voiding.id}/void`, undefined, () => t('admin.billing.voidDone'));
	const nextInvoice = (row: AdminBillingRow) =>
		act(`/api/admin/practices/${row.id}/invoices`, undefined, (inv) => t('admin.billing.invoiceCreated', { number: inv.number }));

	const methodName = (m: string | null) => (m ? (translate(`admin.billing.methods.${m}`) ?? m) : '');
</script>

<svelte:head><title>{t('admin.billing.title')} · Daftar</title></svelte:head>

<AdminTabs current="billing" />
<p class="mb-4 max-w-3xl text-slate-600">{t('admin.billing.intro')}</p>
<p role="status" class="mb-2 min-h-6 font-medium text-brand-800">{notice}</p>
{#if actionError && !paying && !voiding}<p role="alert" class="mb-2 font-medium text-red-700">{actionError}</p>{/if}

<LoadState {loading} {error} onretry={() => load()} />

{#if !loading && !error}
	{#if rows.length === 0}
		<p class="card text-slate-700">{t('admin.billing.empty')}</p>
	{:else}
		<div class="flex flex-col gap-4">
			{#each rows as row (row.id)}
				<article class="card flex flex-col gap-4">
					<header class="flex flex-wrap items-start justify-between gap-3">
						<div class="flex flex-col gap-1">
							<h2 class="text-lg font-bold text-ink">{row.name}</h2>
							<div class="flex flex-wrap items-center gap-2 text-sm text-slate-700">
								<StatusBadge status={row.status} />
								<span>{translate(`admin.plans.${row.planCode}`) ?? row.planCode}</span>
							</div>
						</div>
						<dl class="grid grid-cols-[auto_auto] gap-x-4 text-sm">
							<dt class="text-slate-500">{t('admin.billing.paidUntil')}</dt>
							<dd class="font-semibold">{row.paidUntil ? formatDay(row.paidUntil) : t('kit.none')}</dd>
							<dt class="text-slate-500">{t('admin.billing.open')}</dt>
							<dd class="font-semibold tabular-nums {row.openMillimes > 0 ? 'text-amber-800' : ''}">{formatMillimes(row.openMillimes)}</dd>
						</dl>
					</header>

					{#if row.invoices.length === 0}
						<p class="text-sm text-slate-600">{t('admin.billing.noInvoices')}</p>
					{:else}
						<div class="flex flex-col">
							<h3 class="sr-only">{t('admin.billing.invoices')} – {row.name}</h3>
							<div
								class="hidden gap-3 border-b border-slate-200 pb-2 text-sm text-slate-600 md:grid md:grid-cols-[9rem_minmax(0,1.4fr)_6rem_6.5rem_minmax(0,1.4fr)_auto]"
								aria-hidden="true"
							>
								<span>{t('admin.billing.number')}</span><span>{t('admin.billing.period')}</span><span class="text-end"
									>{t('admin.billing.amount')}</span
								><span>{t('admin.billing.dueOn')}</span><span>{t('admin.billing.state')}</span><span></span>
							</div>
							<ul class="divide-y divide-slate-100">
								{#each row.invoices as invoice (invoice.id)}
									<li class="grid grid-cols-2 gap-x-3 gap-y-1 py-3 text-sm md:grid-cols-[9rem_minmax(0,1.4fr)_6rem_6.5rem_minmax(0,1.4fr)_auto] md:items-center">
										<span class="font-mono font-semibold" dir="ltr">{invoice.number}</span>
										<span class="text-end tabular-nums md:order-none md:text-start"
											>{formatDay(invoice.periodStart)} – {formatDay(invoice.periodEnd)}</span
										>
										<span class="tabular-nums md:text-end">{formatMillimes(invoice.amountMillimes)}</span>
										<span class="text-end tabular-nums md:text-start"
											><span class="text-slate-500 md:sr-only">{t('admin.billing.dueOn')} </span>{formatDay(invoice.dueOn)}</span
										>
										<span class="col-span-2 md:col-span-1">
											{#if invoice.status === 'paid'}
												<span class="text-emerald-800"
													>{t('admin.billing.paidOn', { date: invoice.paidAt ? formatDate(invoice.paidAt) : '', method: methodName(invoice.method) })}</span
												>
											{:else}
												<span class={invoice.status === 'open' ? 'font-semibold text-amber-800' : 'text-slate-500 line-through'}
													>{translate(`admin.billing.invoiceStatus.${invoice.status}`) ?? invoice.status}</span
												>
											{/if}
										</span>
										<span class="col-span-2 flex flex-wrap gap-2 md:col-span-1 md:justify-end">
											{#if invoice.status === 'open'}
												<button
													type="button"
													class="btn-primary min-h-10 px-3 py-1 text-sm"
													aria-label={t('admin.billing.markPaidLabel', { number: invoice.number })}
													onclick={() => {
														method = 'virement';
														actionError = '';
														paying = invoice;
													}}>{t('admin.billing.markPaid')}</button
												>
												<button
													type="button"
													class="btn-secondary min-h-10 px-3 py-1 text-sm"
													aria-label={t('admin.billing.voidLabel', { number: invoice.number })}
													onclick={() => {
														actionError = '';
														voiding = invoice;
													}}>{t('admin.billing.void')}</button
												>
											{/if}
										</span>
									</li>
								{/each}
							</ul>
						</div>
					{/if}

					<div class="flex flex-wrap gap-3">
						<button
							type="button"
							class="btn-secondary"
							disabled={busy}
							aria-label={t('admin.billing.createInvoiceLabel', { name: row.name })}
							onclick={() => nextInvoice(row)}>{t('admin.billing.createInvoice')}</button
						>
						<a class="btn-secondary" href="/app/admin/cabinets/{row.id}">{t('admin.billing.editPractice')}</a>
					</div>
				</article>
			{/each}
		</div>
	{/if}
{/if}

<Modal open={!!paying} title={paying ? t('admin.billing.markPaidTitle', { number: paying.number }) : ''} onclose={() => (paying = null)}>
	{#if paying}
		<p class="text-slate-700">{t('admin.billing.markPaidMessage', { amount: formatMillimes(paying.amountMillimes) })}</p>
		<label class="label">
			{t('admin.billing.method')}
			<select class="input" bind:value={method}>
				{#each INVOICE_METHODS as m (m)}<option value={m}>{methodName(m)}</option>{/each}
			</select>
		</label>
		{#if actionError}<p role="alert" class="text-sm text-red-700">{actionError}</p>{/if}
		<div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
			<button type="button" class="btn-secondary" onclick={() => (paying = null)}>{t('common.cancel')}</button>
			<button type="button" class="btn-primary" disabled={busy} onclick={markPaid}>{t('admin.billing.confirmPaid')}</button>
		</div>
	{/if}
</Modal>

<ConfirmDialog
	open={!!voiding}
	title={voiding ? t('admin.billing.voidTitle', { number: voiding.number }) : ''}
	message={t('admin.billing.voidMessage')}
	confirmLabel={t('admin.billing.confirmVoid')}
	danger
	{busy}
	error={actionError}
	onconfirm={voidInvoice}
	oncancel={() => (voiding = null)}
/>

