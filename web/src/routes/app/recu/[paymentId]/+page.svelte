<script lang="ts">
	/** /app/recu/[paymentId] – a receipt for the patient (story F1), A5-friendly, printed with one click. */
	import { ApiError, api } from '#lib/api';
	import { money } from '#lib/agenda/format';
	import { displayPhone } from '#lib/agenda/links';
	import { formatDate, formatTime, i18n, t, translate } from '#lib/i18n.svelte';
	import type { Receipt } from '#lib/types/patients';
	import Icon from '../../../../lib/components/daily/Icon.svelte';

	let { data }: { data?: { paymentId: number } } = $props();
	const paymentId = $derived(data?.paymentId ?? Number(location.pathname.split('/').filter(Boolean)[2]));

	let receipt = $state<Receipt | null>(null);
	let error = $state('');

	$effect(() => {
		const target = paymentId;
		receipt = null;
		error = '';
		api<Receipt>(`/api/payments/${target}`)
			.then((r) => (receipt = r))
			.catch((err) => (error = err instanceof ApiError && err.status === 404 ? t('recu.notFound') : t('recu.loadError')));
	});

	const practiceName = $derived(receipt ? (i18n.locale === 'ar' && receipt.practice.nameAr ? receipt.practice.nameAr : receipt.practice.name) : '');
</script>

<svelte:head><title>{t('recu.number', { id: paymentId })} · Daftar</title></svelte:head>

<div class="mx-auto flex max-w-xl flex-col gap-4">
	{#if error}
		<p role="alert" class="card text-lg font-semibold">{error}</p>
	{:else if !receipt}
		<p class="card text-slate-600" aria-busy="true">{t('common.loading')}</p>
	{:else}
		<div class="flex flex-wrap items-center gap-2 print:hidden">
			<a class="btn-secondary" href="/app/patients/{receipt.patientId}"><Icon name="start" />{t('recu.back')}</a>
			<button type="button" class="btn-primary ms-auto" onclick={() => window.print()}><Icon name="print" />{t('recu.print')}</button>
		</div>

		<article class="receipt rounded-2xl border border-slate-300 bg-white p-6 shadow-sm print:border-0 print:shadow-none">
			<header class="flex flex-col gap-0.5 border-b-2 border-ink pb-4">
				<p class="text-xl font-bold">{practiceName}</p>
				<p class="text-sm text-slate-700">{[receipt.practice.address, receipt.practice.city].filter(Boolean).join(', ')}</p>
				{#if receipt.practice.phone}<p class="text-sm text-slate-700 tabular-nums" dir="ltr">{displayPhone(receipt.practice.phone)}</p>{/if}
				{#if receipt.practice.taxId}<p class="text-xs text-slate-500">MF {receipt.practice.taxId}</p>{/if}
			</header>

			<h1 class="mt-5 text-2xl font-bold">{t('recu.number', { id: receipt.id })}</h1>
			{#if receipt.isDeposit}<p class="mt-1 inline-block rounded-full bg-amber-100 px-3 py-0.5 text-sm font-semibold text-amber-900">{t('recu.deposit')}</p>{/if}

			<dl class="mt-5 grid grid-cols-[auto_1fr] gap-x-6 gap-y-3">
				<dt class="text-slate-600">{t('recu.date')}</dt>
				<dd class="font-semibold tabular-nums">{formatDate(receipt.paidAt)} {formatTime(receipt.paidAt)}</dd>
				<dt class="text-slate-600">{t('recu.patient')}</dt>
				<dd class="font-semibold">{receipt.patientName}</dd>
				<dt class="text-slate-600">{t('recu.method')}</dt>
				<dd class="font-semibold">{translate(`paymentMethod.${receipt.method}`) ?? receipt.method}</dd>
				{#if receipt.receivedByName}
					<dt class="text-slate-600">{t('recu.receivedBy')}</dt>
					<dd class="font-semibold">{receipt.receivedByName}</dd>
				{/if}
				{#if receipt.note}
					<dt class="text-slate-600">{t('recu.note')}</dt>
					<dd>{receipt.note}</dd>
				{/if}
				<dt class="self-center text-slate-600">{t('recu.amount')}</dt>
				<dd class="text-3xl font-bold tabular-nums">{money(receipt.amountMillimes)}</dd>
			</dl>

			<div class="mt-12 flex justify-end">
				<p class="w-56 border-t border-slate-400 pt-2 text-center text-sm text-slate-600">{t('recu.signature')}</p>
			</div>
		</article>
	{/if}
</div>

<style>
	@media print {
		:global(body) {
			background: #fff;
		}
		@page {
			size: A5;
			margin: 12mm;
		}
	}
</style>
