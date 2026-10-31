<script lang="ts">
	/**
	 * /app/salle/suivant – "Patient suivant" for the desk or the doctor's tablet (section 16.2): who is next now and
	 * after, by the server's rule (`GET /api/queue/next`: the patient of the due appointment if present, else the first
	 * one waiting), one big button "Appeler le suivant" (`POST /api/queue/call-next`, race-safe), late appointments
	 * marked. Optionally for one practitioner (remembered on this device per practice; one that is not an active
	 * practitioner of this practice – a demo shown earlier on the same computer – is forgotten, code review N5).
	 * Refreshes every 15 s.
	 */
	import { onMount } from 'svelte';
	import { ApiError, api } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { errorText } from '#lib/agenda/errors';
	import { personName, practitionerLabel } from '#lib/agenda/format';
	import { telUrl } from '#lib/agenda/links';
	import { formatTime, t } from '#lib/i18n.svelte';
	import type { Appointment, Practitioner } from '#lib/types/agenda';
	import type { QueueEntry } from '#lib/types/queue';
	import Icon from '../../../../lib/components/daily/Icon.svelte';

	type Next = { entry: QueueEntry | null; reason: 'appointment' | 'waiting_list' | null; lateAppointments: Appointment[]; upcoming: QueueEntry[] };
	const KEY = `daftar.next.practitioner.${auth.user?.practice?.id ?? 0}`;
	const REFRESH_MS = 15_000;

	let practitioners = $state<Practitioner[]>([]);
	let selected = $state<number | null>(readSelected());
	let next = $state<Next | null>(null);
	let error = $state('');
	let notice = $state('');
	let busy = $state(false);
	let seq = 0;

	function readSelected(): number | null {
		try {
			return Number(localStorage.getItem(KEY)) || null;
		} catch {
			return null;
		}
	}

	function choose(id: number | null) {
		selected = id;
		try {
			if (id) localStorage.setItem(KEY, String(id));
			else localStorage.removeItem(KEY);
		} catch {
			/* private mode: this page only */
		}
		void load();
	}

	async function load() {
		const mine = ++seq;
		try {
			const result = await api<Next>(selected ? `/api/queue/next?practitionerId=${selected}` : '/api/queue/next');
			if (mine === seq) {
				next = result;
				error = '';
			}
		} catch (err) {
			if (mine !== seq) return;
			if (selected && err instanceof ApiError && err.status === 404) return choose(null); // not a practitioner here
			error = next ? errorText(err) : t('salle.next.loadError');
		}
	}

	onMount(() => {
		const remembered = selected; // checked against the practice's practitioners before it is used
		void api<Practitioner[]>('/api/practitioners')
			.then((list) => {
				practitioners = list.filter((p) => p.active !== false).sort((a, b) => (a.sort ?? 0) - (b.sort ?? 0));
				if (remembered && selected === remembered && !practitioners.some((p) => p.id === remembered)) choose(null);
				else if (remembered) void load();
			})
			.catch(() => {
				if (remembered) void load();
			});
		if (!remembered) void load();
		const timer = setInterval(load, REFRESH_MS);
		return () => clearInterval(timer);
	});

	async function callNext() {
		busy = true;
		error = '';
		try {
			const called = await api<QueueEntry>('/api/queue/call-next', { method: 'POST', json: selected ? { practitionerId: selected } : {} });
			notice = t('salle.next.called', { number: called.ticketNo, name: called.name });
			await load();
		} catch (err) {
			notice = '';
			error = errorText(err);
			void load();
		} finally {
			busy = false;
		}
	}

	function why(e: QueueEntry, reason: Next['reason'] | undefined): string {
		const byAppointment = reason ? reason === 'appointment' : !!e.appointmentAt;
		return byAppointment && e.appointmentAt
			? t('salle.next.reasonAppointment', { time: formatTime(e.appointmentAt) })
			: t('salle.next.reasonWaiting', { number: e.ticketNo });
	}
</script>

<svelte:head><title>{t('salle.next.title')} · Daftar</title></svelte:head>

<div class="flex flex-col gap-5">
	<div class="flex flex-wrap items-end justify-between gap-3">
		<div>
			<a class="inline-flex items-center gap-1 text-sm font-semibold text-brand-800 hover:underline" href="/app/salle"><Icon name="start" class="h-4 w-4" />{t('salle.title')}</a>
			<h1 class="text-2xl font-bold">{t('salle.next.title')}</h1>
		</div>
		{#if practitioners.length > 1}
			<div class="flex flex-wrap gap-2" role="group" aria-label={t('agenda.practitioners')}>
				<button
					type="button"
					class="min-h-11 rounded-full border px-4 text-sm font-semibold {selected === null ? 'border-brand-700 bg-brand-700 text-white' : 'border-slate-300 bg-white text-slate-700'}"
					aria-pressed={selected === null}
					onclick={() => choose(null)}>{t('salle.next.everyone')}</button
				>
				{#each practitioners as p (p.id)}
					<button
						type="button"
						class="min-h-11 rounded-full border px-4 text-sm font-semibold {selected === p.id ? 'border-brand-700 bg-brand-700 text-white' : 'border-slate-300 bg-white text-slate-700'}"
						aria-pressed={selected === p.id}
						onclick={() => choose(p.id)}>{practitionerLabel(p)}</button
					>
				{/each}
			</div>
		{/if}
	</div>

	{#if notice}<p role="status" class="rounded-lg bg-emerald-50 px-4 py-3 text-lg font-semibold text-emerald-900 ring-1 ring-emerald-200">{notice}</p>{/if}
	{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-4 py-3 font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}

	{#if !next && !error}
		<p class="card text-slate-600" aria-busy="true">{t('common.loading')}</p>
	{:else if next}
		<div class="grid items-start gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
			<section aria-labelledby="now-title" class="flex flex-col gap-4 rounded-3xl bg-brand-900 p-6 text-white shadow-lg">
				<h2 id="now-title" class="text-lg font-semibold text-brand-200">{t('salle.next.now')}</h2>
				{#if next.entry}
					<div class="flex flex-wrap items-center gap-6">
						<span class="text-8xl leading-none font-bold text-accent-400 tabular-nums">{next.entry.ticketNo}</span>
						<div class="min-w-0">
							<p class="text-3xl font-bold">{next.entry.name}</p>
							<p class="text-lg text-brand-100">{why(next.entry, next.reason)}</p>
						</div>
					</div>
					{#if next.entry.alerts}
						<p class="flex items-center gap-2 self-start rounded-lg bg-rose-600 px-3 py-2 font-semibold text-white">
							<Icon name="alert" class="h-5 w-5" /><span class="sr-only">{t('agenda.alert')} – </span>{next.entry.alerts}
						</p>
					{/if}
				{:else}
					<p class="text-2xl font-semibold text-brand-100">{t('salle.next.nobody')}</p>
				{/if}
				<button
					type="button"
					class="btn mt-2 min-h-16 self-stretch bg-accent-400 text-xl text-ink hover:bg-accent-500 focus-visible:outline-white sm:self-start sm:px-10"
					disabled={busy || !next.entry}
					onclick={callNext}>{t('salle.next.call')}</button
				>
			</section>

			<div class="flex flex-col gap-5">
				{#if next.entry}
				<section aria-labelledby="then-title" class="card flex flex-col gap-3 p-5">
					<h2 id="then-title" class="text-lg font-bold">{t('salle.next.then')}</h2>
					{#if next.upcoming.length}
						<ul class="flex flex-col gap-2">
							{#each next.upcoming as e (e.id)}
								<li class="flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-2 ring-1 ring-slate-200">
									<span class="grid h-12 w-14 shrink-0 place-items-center rounded-lg bg-white text-2xl font-bold text-brand-800 tabular-nums ring-1 ring-brand-100">{e.ticketNo}</span>
									<span class="min-w-0">
										<span class="block truncate font-semibold">{e.name}</span>
										<span class="block text-sm text-slate-600">{why(e, undefined)}</span>
									</span>
								</li>
							{/each}
						</ul>
					{:else}
						<p class="text-slate-600">{t('salle.next.nobody')}</p>
					{/if}
				</section>
				{/if}

				{#if next.lateAppointments.length}
					<section aria-labelledby="late-title" class="card flex flex-col gap-2 border-amber-300 bg-amber-50/60 p-5">
						<h2 id="late-title" class="text-lg font-bold">{t('salle.next.late')}</h2>
						<p class="text-sm text-slate-600">{t('salle.next.lateHint')}</p>
						<ul class="flex flex-col divide-y divide-amber-100">
							{#each next.lateAppointments as a (a.id)}
								<li class="flex items-center gap-3 py-2">
									<span class="font-semibold tabular-nums">{formatTime(a.startsAt)}</span>
									<span class="min-w-0 flex-1 truncate font-semibold">{personName(a.patient)}</span>
									<a class="btn-secondary min-h-10 px-3 text-sm" href={telUrl(a.patient.phone)} aria-label="{t('agenda.detail.call')} {personName(a.patient)}"
										><Icon name="phone" class="h-4 w-4" />{t('agenda.detail.call')}</a
									>
								</li>
							{/each}
						</ul>
					</section>
				{/if}
			</div>
		</div>
	{/if}
</div>
