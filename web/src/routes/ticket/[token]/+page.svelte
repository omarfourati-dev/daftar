<script lang="ts">
	/**
	 * /ticket/[ticketToken] – opened by the patient from the QR code or the WhatsApp link (story D1): their number,
	 * how many people are ahead and the expected wait, refreshed every 20 s. No names, ever.
	 */
	import { onMount } from 'svelte';
	import { ApiError, api } from '#lib/api';
	import { clock } from '#lib/clock';
	import { telUrl } from '#lib/agenda/links';
	import { applyLocaleFromQuery, formatDay, formatTime, t, todayTunis } from '#lib/i18n.svelte';
	import type { PublicTicket } from '#lib/types/queue';
	import LanguageSwitch from '../../../lib/components/LanguageSwitch.svelte';
	import Icon from '../../../lib/components/daily/Icon.svelte';

	const REFRESH_MS = 20_000;
	const token = decodeURIComponent(location.pathname.split('/').filter(Boolean)[1] ?? '');
	applyLocaleFromQuery();

	let data = $state<PublicTicket | null>(null);
	let invalid = $state(false);
	let offline = $state(false);
	let updatedAt = $state<Date | null>(null);

	const expired = $derived(!!data && data.day !== todayTunis(clock.now()));
	const finished = $derived(!!data && (data.status === 'done' || data.status === 'left'));

	async function load() {
		try {
			data = await api<PublicTicket>(`/api/public/ticket/${encodeURIComponent(token)}`);
			offline = false;
			updatedAt = clock.now();
		} catch (err) {
			if (err instanceof ApiError && err.status === 404) invalid = true;
			else offline = true;
		}
	}

	onMount(() => {
		void load();
		const timer = setInterval(() => {
			if (!invalid && !expired && !finished) void load();
		}, REFRESH_MS);
		return () => clearInterval(timer);
	});
</script>

<svelte:head><title>{t('ticket.title')}{data ? ` ${data.ticketNo}` : ''} · Daftar</title></svelte:head>

<main class="mx-auto flex min-h-screen max-w-md flex-col gap-5 px-4 py-6">
	<div class="flex items-center justify-between gap-3">
		<p class="font-semibold text-slate-600">{t('ticket.title')}</p>
		<LanguageSwitch />
	</div>

	{#if invalid}
		<p role="alert" class="card text-lg font-semibold text-rose-900">{t('ticket.invalid')}</p>
	{:else if !data}
		<p class="card text-slate-600" aria-busy="true">{t('common.loading')}</p>
	{:else}
		<section class="overflow-hidden rounded-3xl bg-brand-900 text-center text-white shadow-lg">
			<p class="px-4 pt-5 text-lg font-semibold text-brand-100">{data.practiceName}</p>
			<p class="mt-2 text-sm font-semibold text-brand-200">{t('ticket.number')}</p>
			<p class="pb-6 text-[7rem] leading-none font-bold tabular-nums {data.status === 'called' ? 'text-accent-400' : 'text-white'}">{data.ticketNo}</p>
		</section>

		{#if expired}
			<p class="card text-lg font-semibold text-slate-700">{t('ticket.expired', { date: formatDay(data.day) })}</p>
		{:else if data.status === 'waiting'}
			<div class="card flex flex-col gap-3 text-center">
				<div>
					<p class="text-sm font-semibold text-slate-600">{t('ticket.ahead')}</p>
					<p class="text-6xl font-bold text-brand-800 tabular-nums">{data.peopleAhead ?? 0}</p>
				</div>
				{#if !data.peopleAhead}
					<p class="text-lg font-semibold text-brand-900">{t('ticket.next')}</p>
				{:else if data.estimatedWaitMin}
					<p class="text-lg font-semibold">{t('ticket.wait', { min: data.estimatedWaitMin })}</p>
				{/if}
			</div>
		{:else}
			<p
				role="status"
				class="rounded-2xl px-4 py-5 text-center text-xl font-bold {data.status === 'called'
					? 'bg-accent-400 text-ink'
					: data.status === 'in_treatment'
						? 'bg-violet-100 text-violet-900'
						: 'bg-slate-100 text-slate-700'}"
			>
				{t(data.status === 'called' ? 'ticket.called' : data.status === 'in_treatment' ? 'ticket.in_treatment' : data.status === 'done' ? 'ticket.done' : 'ticket.left')}
			</p>
		{/if}

		{#if data.practicePhone}
			<a class="btn-secondary min-h-12" href={telUrl(data.practicePhone)}><Icon name="phone" />{t('ticket.call')}</a>
		{/if}
		<div class="text-center text-sm text-slate-500">
			{#if offline}<p class="font-semibold text-amber-800">{t('ticket.reconnecting')}</p>{/if}
			{#if !expired && !finished}<p>{t('ticket.auto')}</p>{/if}
			{#if updatedAt}<p>{t('ticket.updated', { time: formatTime(updatedAt) })}</p>{/if}
		</div>
	{/if}
</main>
