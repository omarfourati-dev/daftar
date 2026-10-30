<script lang="ts">
	/**
	 * /app/caisse – the cash book (story F2): what came in on a day, split by payment method, each payment with its
	 * receipt; the cash closing with difference and owner verification (section 16.3); what patients still owe.
	 * Address: `?day=YYYY-MM-DD`.
	 */
	import { onMount } from 'svelte';
	import { api } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { clock } from '#lib/clock';
	import { money } from '#lib/agenda/format';
	import { displayPhone } from '#lib/agenda/links';
	import { PAYMENT_METHODS } from '#lib/agenda/payments';
	import { addDays, formatDate, formatDay, formatTime, t, todayTunis, translate } from '#lib/i18n.svelte';
	import type { Balance, CashDay } from '#lib/types/patients';
	import Icon from '../../../lib/components/daily/Icon.svelte';
	import CashClosing from '../../../lib/components/caisse/CashClosing.svelte';

	const DAY = /^\d{4}-\d{2}-\d{2}$/;
	const today = todayTunis(clock.now());
	const asked = new URLSearchParams(location.search).get('day') ?? '';
	let day = $state(DAY.test(asked) ? asked : today);
	let cash = $state<CashDay | null>(null);
	let balances = $state<Balance[] | null>(null);
	let error = $state('');
	let seq = 0;

	async function load() {
		const mine = ++seq;
		error = '';
		try {
			const result = await api<CashDay>(`/api/cash?day=${day}`);
			if (mine === seq) cash = result;
		} catch {
			if (mine === seq) error = t('caisse.loadError');
		}
	}

	onMount(() => {
		void load();
		void api<Balance[]>('/api/balances?limit=100')
			.then((b) => (balances = b))
			.catch(() => (balances = []));
	});

	function go(next: string) {
		if (!DAY.test(next) || next > today) return;
		day = next;
		cash = null;
		void load();
	}

	const methods = $derived(
		cash
			? PAYMENT_METHODS.filter((m) => (cash?.byMethod[m] ?? 0) > 0)
					.map((m) => ({ method: m, amount: cash?.byMethod[m] ?? 0 }))
					.sort((a, b) => b.amount - a.amount)
			: []
	);
	const dueTotal = $derived((balances ?? []).reduce((sum, b) => sum + b.dueMillimes, 0));
</script>

<svelte:head><title>{t('caisse.title')} · Daftar</title></svelte:head>

<div class="flex flex-col gap-5">
	<div class="flex flex-wrap items-end justify-between gap-3">
		<div>
			<h1 class="text-2xl font-bold">{t('caisse.title')}</h1>
			<p class="text-slate-600 first-letter:uppercase">{formatDay(day, 'long')}</p>
		</div>
		<div class="flex flex-wrap items-center gap-1">
			<button type="button" class="btn-secondary min-w-11 px-2" aria-label={t('caisse.previousDay')} onclick={() => go(addDays(day, -1))}><Icon name="start" /></button>
			<button type="button" class="btn-secondary" onclick={() => go(today)} disabled={day === today}>{t('caisse.today')}</button>
			<button type="button" class="btn-secondary min-w-11 px-2" aria-label={t('caisse.nextDay')} onclick={() => go(addDays(day, 1))} disabled={day >= today}
				><Icon name="end" /></button
			>
			<label class="sr-only" for="cash-day">{t('caisse.pickDay')}</label>
			<input id="cash-day" type="date" class="input ms-1 w-auto" value={day} max={today} onchange={(e) => go(e.currentTarget.value)} />
		</div>
	</div>

	{#if error}
		<div role="alert" class="card flex flex-wrap items-center justify-between gap-3 border-rose-200 bg-rose-50 text-rose-900">
			<p>{error}</p>
			<button type="button" class="btn-secondary" onclick={load}>{t('common.retry')}</button>
		</div>
	{:else if !cash}
		<p class="card text-slate-600" aria-busy="true">{t('common.loading')}</p>
	{:else}
		<div class="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
			<div class="flex min-w-0 flex-col gap-5">
				<section class="card flex flex-col gap-4 p-5">
					<div>
						<p class="text-sm font-semibold text-slate-600">{t('caisse.total')}</p>
						<p class="text-4xl font-bold text-emerald-800 tabular-nums">{money(cash.totalMillimes)}</p>
					</div>
					{#if methods.length}
						<ul aria-label={t('caisse.byMethod')} class="flex flex-col gap-2">
							{#each methods as m (m.method)}
								<li class="grid grid-cols-[7rem_1fr_auto] items-center gap-3 text-sm">
									<span class="font-medium">{translate(`paymentMethod.${m.method}`)}</span>
									<span class="h-3 overflow-hidden rounded-full bg-slate-100" aria-hidden="true"
										><span class="block h-full rounded-full bg-brand-600" style="width:{(m.amount / cash.totalMillimes) * 100}%"></span></span
									>
									<span class="font-semibold tabular-nums">{money(m.amount)}</span>
								</li>
							{/each}
						</ul>
					{/if}
				</section>

				<section class="card p-0">
					<h2 id="payments-title" class="px-5 pt-4 pb-2 text-lg font-bold">{t('caisse.payments')}</h2>
					{#if cash.payments.length}
						<div class="overflow-x-auto px-2 pb-2">
							<table aria-labelledby="payments-title" class="w-full text-sm">
								<tbody>
									{#each cash.payments as p (p.id)}
										<tr class="border-t border-slate-100">
											<td class="py-2.5 ps-3 pe-3 font-semibold tabular-nums">{formatTime(p.paidAt)}</td>
											<td class="py-2.5 pe-3">
												<a class="font-semibold hover:underline" href="/app/patients/{p.patientId}">{p.patientName}</a>
												{#if p.isDeposit}<span class="ms-1 rounded-full bg-amber-100 px-2 text-xs font-semibold text-amber-900">{t('caisse.deposit')}</span>{/if}
											</td>
											<td class="py-2.5 pe-3 text-slate-600">{translate(`paymentMethod.${p.method}`) ?? p.method}</td>
											<td class="py-2.5 pe-3 text-end font-semibold tabular-nums">{money(p.amountMillimes)}</td>
											<td class="py-2.5 pe-3 text-end"
												><a class="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700 hover:bg-slate-200" href="/app/recu/{p.id}">{t('caisse.receipt')}</a></td
											>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{:else}
						<p class="px-5 pb-5 text-slate-600">{t('caisse.noPayments')}</p>
					{/if}
				</section>
			</div>

			{#key day + (cash.closing?.closedAt ?? '')}
				<CashClosing {day} expectedCash={cash.byMethod.cash ?? 0} closing={cash.closing ?? null} isOwner={auth.user?.role === 'owner'} />
			{/key}
		</div>
	{/if}

	<section id="impayes" aria-labelledby="balances-title" class="card flex flex-col gap-3 p-5">
		<div class="flex flex-wrap items-baseline justify-between gap-2">
			<h2 id="balances-title" class="text-lg font-bold">{t('caisse.balances.title')}</h2>
			{#if balances?.length}<p class="font-semibold text-rose-800">{t('caisse.balances.total', { amount: money(dueTotal) })}</p>{/if}
		</div>
		<p class="text-sm text-slate-600">{t('caisse.balances.hint')}</p>
		{#if balances === null}
			<p class="text-slate-600" aria-busy="true">{t('common.loading')}</p>
		{:else if !balances.length}
			<p class="text-slate-600">{t('caisse.balances.empty')}</p>
		{:else}
			<ul class="divide-y divide-slate-100">
				{#each balances as b (b.patientId)}
					<li>
						<a class="flex flex-wrap items-center gap-x-4 gap-y-1 py-2.5 hover:bg-brand-50/40" href="/app/patients/{b.patientId}">
							<span class="min-w-0 flex-1 font-semibold">{b.name}</span>
							<span class="text-sm text-slate-600 tabular-nums" dir="ltr">{displayPhone(b.phone)}</span>
							<span class="text-sm text-slate-500"
								>{b.lastPaymentAt ? t('caisse.balances.lastPayment', { date: formatDate(b.lastPaymentAt) }) : t('caisse.balances.never')}</span
							>
							<span class="w-28 text-end font-bold text-rose-800 tabular-nums">{money(b.dueMillimes)}</span>
						</a>
					</li>
				{/each}
			</ul>
		{/if}
	</section>
</div>
