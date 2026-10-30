<script lang="ts">
	/**
	 * /app/salle – today's waiting room at the desk (story D1): tickets by step (in consultation, called, waiting,
	 * finished), one big button for the next step, WhatsApp link and QR code to the patient's ticket page, a preview of
	 * the waiting-room screen (numbers only) and the link to open that screen on the TV. Refreshes every 20 s.
	 */
	import { errorText } from '#lib/agenda/errors';
	import { onMount } from 'svelte';
	import { api } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { clock } from '#lib/clock';
	import { byTicket, screenUrl, ticketMessage } from '#lib/agenda/queue';
	import { whatsappUrl } from '#lib/agenda/links';
	import { formatDay, formatTime, t, todayTunis, translate, type MessageKey } from '#lib/i18n.svelte';
	import type { PracticeSettings } from '#lib/types/agenda';
	import type { QueueEntry, QueueStatus } from '#lib/types/queue';
	import Icon from '../../../lib/components/daily/Icon.svelte';
	import Modal from '../../../lib/components/daily/Modal.svelte';
	import TicketForm from '../../../lib/components/salle/TicketForm.svelte';
	import TicketQr from '../../../lib/components/salle/TicketQr.svelte';

	const REFRESH_MS = 20_000;
	let entries = $state<QueueEntry[] | null>(null);
	let practice = $state<PracticeSettings | null>(null);
	let error = $state('');
	let notice = $state('');
	let busy = $state<number | null>(null);
	let creating = $state(false);
	let qrFor = $state<QueueEntry | null>(null);

	const practiceName = $derived(practice?.name ?? auth.user?.practice?.name ?? '');

	async function load() {
		try {
			entries = await api<QueueEntry[]>('/api/queue');
			error = '';
		} catch {
			error = t('salle.loadError');
		}
	}

	onMount(() => {
		void load();
		void api<PracticeSettings>('/api/practice')
			.then((p) => (practice = p))
			.catch(() => undefined);
		const timer = setInterval(load, REFRESH_MS);
		return () => clearInterval(timer);
	});

	async function setStatus(e: QueueEntry, status: QueueStatus) {
		busy = e.id;
		try {
			await api<QueueEntry>(`/api/queue/${e.id}/status`, { method: 'POST', json: { status } });
			await load();
			notice = t('salle.updated', { number: e.ticketNo, status: translate(`queueStatus.${status}`) ?? status });
		} catch (err) {
			notice = '';
			error = errorText(err);
		} finally {
			busy = null;
		}
	}

	const sorted = $derived([...(entries ?? [])].sort(byTicket));
	type Section = { key: 'in_treatment' | 'called' | 'waiting' | 'finished'; title: MessageKey; items: QueueEntry[] };
	const sections = $derived.by((): Section[] =>
		(
			[
				{ key: 'in_treatment', title: 'salle.sections.in_treatment', items: sorted.filter((e) => e.status === 'in_treatment') },
				{ key: 'called', title: 'salle.sections.called', items: sorted.filter((e) => e.status === 'called') },
				{ key: 'waiting', title: 'salle.sections.waiting', items: sorted.filter((e) => e.status === 'waiting') },
				{ key: 'finished', title: 'salle.sections.finished', items: sorted.filter((e) => e.status === 'done' || e.status === 'left') }
			] as Section[]
		).filter((s) => s.items.length)
	);

	type Step = { status: QueueStatus; key: MessageKey; primary?: boolean };
	const STEPS: Record<string, Step[]> = {
		waiting: [
			{ status: 'called', key: 'salle.actions.call', primary: true },
			{ status: 'left', key: 'salle.actions.left' }
		],
		called: [
			{ status: 'in_treatment', key: 'salle.actions.start', primary: true },
			{ status: 'left', key: 'salle.actions.left' }
		],
		in_treatment: [{ status: 'done', key: 'salle.actions.done', primary: true }]
	};

	const NUMBER_TONE: Record<string, string> = {
		in_treatment: 'bg-violet-100 text-violet-800',
		called: 'bg-amber-100 text-amber-800',
		waiting: 'bg-brand-50 text-brand-800',
		done: 'bg-slate-100 text-slate-500',
		left: 'bg-slate-100 text-slate-400'
	};

	/** The screen preview: last called number (or in consultation), then the next waiting ones. */
	const latestFirst = (a: QueueEntry, b: QueueEntry) => (b.calledAt ?? '').localeCompare(a.calledAt ?? '') || b.ticketNo - a.ticketNo;
	const shownCalled = $derived(
		[...sorted.filter((e) => e.status === 'called').sort(latestFirst), ...sorted.filter((e) => e.status === 'in_treatment').sort(latestFirst)][0] ?? null
	);
	const nextWaiting = $derived(sorted.filter((e) => e.status === 'waiting').slice(0, 3));
	const waitingCount = $derived(sorted.filter((e) => e.status === 'waiting').length);

	function meta(e: QueueEntry): string[] {
		const parts = [e.appointmentAt ? t('salle.appointmentAt', { time: formatTime(e.appointmentAt) }) : t('salle.walkIn')];
		if (e.status === 'waiting') {
			if (e.position) parts.push(t('salle.position', { position: e.position }));
			if (e.estimatedWaitMin) parts.push(t('salle.wait', { min: e.estimatedWaitMin }));
		} else if (e.status === 'in_treatment' && e.calledAt) parts.push(t('salle.since', { time: formatTime(e.calledAt) }));
		return parts;
	}
</script>

<svelte:head><title>{t('salle.title')} · Daftar</title></svelte:head>

<div class="flex flex-col gap-5">
	<div class="flex flex-wrap items-end justify-between gap-3">
		<div>
			<h1 class="text-2xl font-bold">{t('salle.title')}</h1>
			<p class="text-slate-600 first-letter:uppercase">{formatDay(todayTunis(clock.now()), 'long')}</p>
		</div>
		<div class="flex flex-wrap gap-2">
			{#if practice?.displayToken}
				<a class="btn-secondary" href={screenUrl(practice.displayToken)} target="_blank" rel="noopener noreferrer"><Icon name="screen" />{t('salle.screen')}</a>
			{/if}
			<a class="btn-secondary" href="/app/salle/suivant"><Icon name="users" />{t('salle.next.link')}</a>
			<button type="button" class="btn-primary" onclick={() => (creating = true)}><Icon name="plus" />{t('salle.newTicket')}</button>
		</div>
	</div>

	{#if notice}<p role="status" class="rounded-lg bg-emerald-50 px-4 py-2 font-medium text-emerald-900 ring-1 ring-emerald-200">{notice}</p>{/if}
	{#if error}
		<div role="alert" class="card flex flex-wrap items-center justify-between gap-3 border-rose-200 bg-rose-50 text-rose-900">
			<p>{error}</p>
			<button type="button" class="btn-secondary" onclick={load}>{t('common.retry')}</button>
		</div>
	{/if}

	<div class="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
		<div class="flex min-w-0 flex-col gap-5">
			{#if entries === null && !error}
				<p class="card text-slate-600" aria-busy="true">{t('common.loading')}</p>
			{:else if entries && !entries.length}
				<div class="card flex flex-col items-start gap-2 py-8">
					<p class="text-lg font-semibold">{t('salle.empty')}</p>
					<p class="text-slate-600">{t('salle.emptyHint')}</p>
				</div>
			{/if}
			{#each sections as section (section.key)}
				<section aria-labelledby="queue-{section.key}" class="flex flex-col gap-2">
					<h2 class="flex items-center gap-2 font-bold text-slate-700">
						<span id="queue-{section.key}">{t(section.title)}</span><span class="rounded-full bg-slate-200 px-2 text-xs tabular-nums">{section.items.length}</span>
					</h2>
					<ul class="flex flex-col gap-2">
						{#each section.items as e (e.id)}
							<li
								class="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border bg-white p-3 shadow-sm {section.key === 'finished'
									? 'border-slate-200 opacity-80'
									: 'border-slate-200'}"
							>
								<span class="grid h-14 w-16 shrink-0 place-items-center rounded-xl text-3xl font-bold tabular-nums {NUMBER_TONE[e.status]}"
									><span class="sr-only">{t('salle.ticket', { number: '' })}</span>{e.ticketNo}</span
								>
								<div class="min-w-[10rem] flex-1">
									<p class="truncate font-semibold">{e.name}</p>
									<p class="text-sm text-slate-600">{meta(e).join(' – ')}</p>
									{#if e.alerts}
										<p class="mt-1 inline-flex items-center gap-1 rounded bg-rose-50 px-2 py-0.5 text-sm font-semibold text-rose-800 ring-1 ring-rose-200">
											<Icon name="alert" class="h-4 w-4" /><span class="sr-only">{t('agenda.alert')} – </span>{e.alerts}
										</p>
									{/if}
								</div>
								<div class="flex w-full flex-wrap items-center gap-2 sm:w-auto">
									{#if e.status === 'waiting' || e.status === 'called'}
										{#if e.phone}
											<a
												class="btn min-h-11 border border-emerald-200 bg-emerald-50 px-3 text-sm text-emerald-900 hover:bg-emerald-100"
												href={whatsappUrl(e.phone, ticketMessage(e, practiceName))}
												target="_blank"
												rel="noopener noreferrer"><Icon name="chat" class="h-4 w-4" />{t('salle.actions.whatsapp')}</a
											>
										{/if}
										<button type="button" class="btn-secondary min-h-11 px-3 text-sm" onclick={() => (qrFor = e)}><Icon name="qr" class="h-4 w-4" />{t('salle.actions.qr')}</button>
									{/if}
									{#each STEPS[e.status] ?? [] as step (step.status)}
										<button
											type="button"
											class="{step.primary ? 'btn-primary' : 'btn-secondary'} min-h-11"
											disabled={busy === e.id}
											onclick={() => setStatus(e, step.status)}>{t(step.key)}</button
										>
									{/each}
									{#if e.status === 'done' || e.status === 'left'}
										<span class="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">{translate(`queueStatus.${e.status}`)}</span>
									{/if}
								</div>
							</li>
						{/each}
					</ul>
				</section>
			{/each}
		</div>

		<aside class="flex flex-col gap-4 lg:sticky lg:top-4">
			<section aria-labelledby="preview-title" class="rounded-2xl bg-brand-900 p-5 text-white shadow-lg">
				<h2 id="preview-title" class="font-semibold text-brand-200">{t('salle.preview.title')}</h2>
				<p class="mt-3 text-sm text-brand-100">{t('salle.preview.called')}</p>
				<p class="text-8xl leading-none font-bold text-accent-400 tabular-nums">{shownCalled?.ticketNo ?? '–'}</p>
				<p class="mt-4 text-sm text-brand-100">{t('salle.preview.next')}</p>
				<div class="mt-2 grid grid-cols-3 gap-2">
					{#each nextWaiting as e (e.id)}
						<span class="grid h-14 place-items-center rounded-xl bg-white/10 text-3xl font-bold tabular-nums">{e.ticketNo}</span>
					{/each}
				</div>
				<p class="mt-4 border-t border-white/15 pt-3 text-sm text-brand-100">{t('salle.preview.waiting', { count: waitingCount })}</p>
			</section>
		</aside>
	</div>
</div>

{#if creating}
	<TicketForm practice={practiceName} oncreated={() => void load()} onclose={() => (creating = false)} />
{/if}

{#if qrFor}
	<Modal title={t('salle.qr.title', { number: qrFor.ticketNo })} onclose={() => (qrFor = null)}>
		<TicketQr entry={qrFor} practice={practiceName} />
	</Modal>
{/if}
