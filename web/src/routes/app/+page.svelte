<script lang="ts">
	/**
	 * /app "Aujourd'hui" – the desk's start page: the day in five numbers, online requests to confirm or decline (with a
	 * WhatsApp message), appointments whose time has passed without arrival ("Non venus ?", story B5), the next
	 * appointments, and for the owner the "Premiers pas" checklist (story A5) until it is done or hidden.
	 */
	import { errorText } from '#lib/agenda/errors';
	import { onMount } from 'svelte';
	import { api } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { badges } from '#lib/badges.svelte';
	import { clock } from '#lib/clock';
	import { money, personName, practitionerLabel, shortDay, statusLabel } from '#lib/agenda/format';
	import { whatsappUrl } from '#lib/agenda/links';
	import { appointmentMessage, type PatientMessage } from '#lib/agenda/messages';
	import { addDays, formatDay, formatTime, t, todayTunis, type MessageKey } from '#lib/i18n.svelte';
	import type { AppointmentStatus } from '#lib/status';
	import type { Appointment, Dashboard, Onboarding, PracticeSettings } from '#lib/types/agenda';
	import Icon, { type IconName } from '../../lib/components/daily/Icon.svelte';
	import StatusPill from '../../lib/components/agenda/StatusPill.svelte';

	const STEP_LINKS: Record<string, string> = {
		hours: '/app/reglages#horaires',
		services: '/app/reglages#actes',
		practitioners: '/app/reglages#praticiens',
		team: '/app/reglages#equipe',
		booking: '/app/reglages#reservation',
		import: '/app/import',
		install: '/app/installer',
		poster: '/app/reglages/affiche'
	};
	/** Steps the server cannot see in the data – the owner ticks them. */
	const MANUAL = new Set(['install', 'poster']);

	const today = todayTunis(clock.now());
	let data = $state<Dashboard | null>(null);
	let practice = $state<PracticeSettings | null>(null);
	let requests = $state<Appointment[]>([]);
	let overdue = $state<Appointment[]>([]);
	let onboarding = $state<Onboarding | null>(null);
	let error = $state('');
	/** Per appointment: what was done here (shown in place of the buttons) and the message to send. */
	let handled = $state<Record<number, { text: string; message?: PatientMessage; appointment: Appointment }>>({});
	let busy = $state<number | null>(null);
	let rowError = $state('');

	async function load() {
		error = '';
		try {
			const [d, late, coming, p] = await Promise.all([
				api<Dashboard>('/api/dashboard'),
				api<Appointment[]>('/api/appointments/overdue'),
				api<Appointment[]>(`/api/appointments?from=${today}&to=${addDays(today, 60)}`),
				api<PracticeSettings>('/api/practice').catch(() => null)
			]);
			data = d;
			overdue = late;
			requests = coming.filter((a) => a.status === 'requested').sort((a, b) => a.startsAt.localeCompare(b.startsAt));
			practice = p;
		} catch {
			error = t('today.loadError');
		}
		if (auth.role === 'owner') onboarding = await api<Onboarding>('/api/onboarding').catch(() => null);
	}
	onMount(load);

	async function setStatus(a: Appointment, status: AppointmentStatus, doneKey: MessageKey) {
		busy = a.id;
		rowError = '';
		const wasRequest = a.status === 'requested';
		try {
			const next = await api<Appointment>(`/api/appointments/${a.id}/status`, { method: 'POST', json: { status } });
			const message: PatientMessage | undefined = wasRequest ? (status === 'confirmed' ? 'confirmed' : 'rejected') : undefined;
			handled = { ...handled, [a.id]: { text: t(doneKey, { patient: personName(a.patient), status: statusLabel(status) }), message, appointment: next } };
			void badges.refresh();
		} catch (err) {
			rowError = errorText(err);
		} finally {
			busy = null;
		}
	}

	async function markStep(key: string) {
		if (!onboarding) return;
		onboarding = { ...onboarding, steps: onboarding.steps.map((s) => (s.key === key ? { ...s, done: true } : s)) };
		await api(`/api/onboarding/${key}/done`, { method: 'POST' }).catch(() => undefined);
	}

	async function dismiss() {
		onboarding = null;
		await api('/api/onboarding/dismiss', { method: 'POST' }).catch(() => undefined);
	}

	const byStatus = $derived(data?.appointments.byStatus ?? {});
	const doneCount = $derived(byStatus.done ?? 0);
	const leftCount = $derived((byStatus.scheduled ?? 0) + (byStatus.confirmed ?? 0) + (byStatus.requested ?? 0));
	const stepsDone = $derived(onboarding?.steps.filter((s) => s.done).length ?? 0);
	const showSteps = $derived(!!onboarding && !onboarding.dismissed && stepsDone < onboarding.steps.length);

	type Tile = { href: string; icon: IconName; label: string; value: string; hint: string; tone: string };
	const tiles = $derived.by((): Tile[] => {
		if (!data) return [];
		return [
			{
				href: '/app/agenda',
				icon: 'calendar',
				label: t('today.tiles.appointments'),
				value: String(data.appointments.total),
				hint: t('today.tiles.appointmentsHint', { done: doneCount, left: leftCount }),
				tone: 'text-brand-800'
			},
			{
				href: '/app/salle',
				icon: 'ticket',
				label: t('today.tiles.waiting'),
				value: String(data.queue.waiting),
				hint: t('today.tiles.waitingHint', { called: data.queue.called }),
				tone: 'text-violet-800'
			},
			{ href: '/app/caisse', icon: 'wallet', label: t('today.tiles.cash'), value: money(data.cashTodayMillimes), hint: formatDay(today), tone: 'text-emerald-800' },
			{
				href: '/app/rappels',
				icon: 'bell',
				label: t('today.tiles.reminders'),
				value: String(data.remindersPending),
				hint: t('today.tiles.remindersHint'),
				tone: 'text-amber-800'
			},
			{
				href: '/app/caisse#impayes',
				icon: 'receipt',
				label: t('today.tiles.due'),
				value: money(data.dueTotalMillimes),
				hint: t('today.tiles.dueHint'),
				tone: 'text-rose-800'
			}
		];
	});
</script>

<svelte:head><title>{t('today.title')} · Daftar</title></svelte:head>

<div class="flex flex-col gap-6">
	<div class="flex flex-wrap items-end justify-between gap-3">
		<div>
			<h1 class="text-2xl font-bold">{t('today.title')}</h1>
			<p class="text-slate-600 first-letter:uppercase">{formatDay(today, 'long')}</p>
		</div>
		<div class="flex flex-wrap gap-2">
			<a class="btn-secondary" href="/app/salle"><Icon name="ticket" />{t('today.newTicket')}</a>
			<a class="btn-primary" href="/app/agenda?nouveau=1"><Icon name="plus" />{t('today.newAppointment')}</a>
		</div>
	</div>

	{#if error}
		<div role="alert" class="card flex flex-wrap items-center justify-between gap-3 border-rose-200 bg-rose-50 text-rose-900">
			<p>{error}</p>
			<button type="button" class="btn-secondary" onclick={load}>{t('common.retry')}</button>
		</div>
	{/if}

	{#if showSteps && onboarding}
		<section aria-labelledby="steps-title" class="rounded-2xl border border-brand-200 bg-brand-50 p-4 sm:p-5">
			<div class="flex flex-wrap items-center gap-3">
				<h2 id="steps-title" class="text-lg font-bold text-brand-900">{t('today.onboarding.title')}</h2>
				<p class="text-sm font-medium text-brand-800">{t('today.onboarding.progress', { done: stepsDone, total: onboarding.steps.length })}</p>
				<button type="button" class="ms-auto min-h-10 px-2 text-sm font-semibold text-brand-900 underline underline-offset-2" onclick={dismiss}
					>{t('today.onboarding.hide')}</button
				>
			</div>
			<div class="mt-3 h-2 overflow-hidden rounded-full bg-white" aria-hidden="true">
				<div class="h-full rounded-full bg-brand-600" style="width:{(stepsDone / onboarding.steps.length) * 100}%"></div>
			</div>
			<ol class="mt-4 grid gap-2 sm:grid-cols-2">
				{#each onboarding.steps as step (step.key)}
					<li class="flex min-h-12 items-center gap-3 rounded-xl bg-white px-3 py-2 ring-1 ring-brand-100">
						<span
							class="grid h-7 w-7 shrink-0 place-items-center rounded-full {step.done ? 'bg-brand-700 text-white' : 'border-2 border-slate-300 text-transparent'}"
							aria-hidden="true"><Icon name="check" class="h-4 w-4" /></span
						>
						{#if step.done}
							<span class="text-slate-500 line-through">{t(`today.onboarding.steps.${step.key}` as MessageKey)}</span>
						{:else}
							<a class="font-semibold text-ink underline-offset-2 hover:underline" href={STEP_LINKS[step.key] ?? '/app/reglages'}
								>{t(`today.onboarding.steps.${step.key}` as MessageKey)}</a
							>
							{#if MANUAL.has(step.key)}
								<button type="button" class="ms-auto min-h-10 rounded-lg px-3 text-sm font-semibold text-brand-800 hover:bg-brand-50" onclick={() => markStep(step.key)}
									>{t('today.onboarding.markDone')}</button
								>
							{/if}
						{/if}
					</li>
				{/each}
			</ol>
		</section>
	{/if}

	{#if data}
		<ul aria-label={t('today.tiles.label')} class="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
			{#each tiles as tile (tile.href)}
				<li>
					<a
						href={tile.href}
						class="flex h-full flex-col gap-1 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition-colors hover:border-brand-300 hover:bg-brand-50/40"
					>
						<span class="flex items-center gap-2 text-sm font-semibold text-slate-600"><Icon name={tile.icon} class="h-4 w-4" />{tile.label}</span>
						<span class="text-2xl font-bold whitespace-nowrap tabular-nums {tile.tone}">{tile.value}</span>
						<span class="text-xs text-slate-500">{tile.hint}</span>
					</a>
				</li>
			{/each}
		</ul>
	{:else if !error}
		<p class="card text-slate-600" aria-busy="true">{t('common.loading')}</p>
	{/if}

	{#if rowError}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-rose-900 ring-1 ring-rose-200">{rowError}</p>{/if}

	{#if auth.role === 'owner' && data?.unverifiedCashDays?.length}
		<section aria-labelledby="cash-check-title" class="card flex flex-col gap-2 border-amber-300">
			<h2 id="cash-check-title" class="text-lg font-bold">{t('today.cashCheck.title')}</h2>
			<ul class="flex flex-wrap gap-2">
				{#each data.unverifiedCashDays as c (c.day)}
					<li>
						<a
							class="inline-flex min-h-11 items-center rounded-lg px-3 font-semibold ring-1 hover:bg-slate-50 {c.differenceMillimes ? 'text-rose-800 ring-rose-200' : 'text-emerald-800 ring-emerald-200'}"
							href="/app/caisse?day={c.day}"
							>{c.differenceMillimes
								? t('today.cashCheck.difference', { date: formatDay(c.day), amount: money(c.differenceMillimes) })
								: t('today.cashCheck.exact', { date: formatDay(c.day) })}</a
						>
					</li>
				{/each}
			</ul>
		</section>
	{/if}

	<div class="grid items-start gap-6 lg:grid-cols-2">
		{#if requests.length}
			<section aria-labelledby="requests-title" class="card flex flex-col gap-3 border-dashed border-brand-600">
				<div>
					<h2 id="requests-title" class="text-lg font-bold">{t('today.requests.title')}</h2>
					<p class="text-sm text-slate-600">{t('today.requests.hint')}</p>
				</div>
				<ul class="flex flex-col divide-y divide-slate-100">
					{#each requests as r (r.id)}
						{@const done = handled[r.id]}
						<li class="flex flex-col gap-2 py-3">
							<div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
								<span class="font-semibold tabular-nums first-letter:uppercase">{shortDay(r.startsAt)} {formatTime(r.startsAt)}</span>
								<span class="font-semibold">{personName(r.patient)}</span>
								<span class="text-slate-600">{r.reason}</span>
								{#if r.practitionerName}<span class="text-sm text-slate-500">{r.practitionerName}</span>{/if}
							</div>
							{#if r.patientNote}<p class="text-sm text-slate-700">{r.patientNote}</p>{/if}
							{#if done}
								<p class="font-medium text-emerald-800">{done.text}</p>
								{#if done.message && practice}
									<a
										class="btn min-h-11 self-start bg-[#25d366] text-ink hover:bg-[#1ebe5b]"
										href={whatsappUrl(r.patient.phone, appointmentMessage(r, done.message, practice))}
										target="_blank"
										rel="noopener noreferrer"><Icon name="chat" />{t('agenda.actions.confirmWhatsapp')}</a
									>
								{/if}
							{:else}
								<div class="flex flex-wrap gap-2">
									<button type="button" class="btn-primary min-h-11" disabled={busy === r.id} onclick={() => setStatus(r, 'confirmed', 'today.requests.done')}
										>{t('agenda.actions.confirm')}</button
									>
									<button type="button" class="btn-secondary min-h-11" disabled={busy === r.id} onclick={() => setStatus(r, 'cancelled', 'today.requests.done')}
										>{t('agenda.actions.reject')}</button
									>
								</div>
							{/if}
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		{#if overdue.length}
			<section aria-labelledby="overdue-title" class="card flex flex-col gap-3 border-amber-300 bg-amber-50/60">
				<div>
					<h2 id="overdue-title" class="text-lg font-bold">{t('today.overdue.title')}</h2>
					<p class="text-sm text-slate-600">{t('today.overdue.hint')}</p>
				</div>
				<ul class="flex flex-col divide-y divide-amber-100">
					{#each overdue as a (a.id)}
						{@const done = handled[a.id]}
						<li class="flex flex-wrap items-center gap-x-3 gap-y-2 py-3">
							<span class="font-semibold tabular-nums">{formatTime(a.startsAt)}</span>
							<span class="min-w-0 flex-1 font-semibold">{personName(a.patient)}</span>
							{#if done}
								<span class="font-medium text-emerald-800">{done.text}</span>
							{:else}
								<button type="button" class="btn min-h-11 bg-rose-700 text-white hover:bg-rose-800" disabled={busy === a.id} onclick={() => setStatus(a, 'no_show', 'today.overdue.done')}
									>{t('today.overdue.noShow')}</button
								>
								<button type="button" class="btn-secondary min-h-11" disabled={busy === a.id} onclick={() => setStatus(a, 'done', 'today.overdue.done')}
									>{t('today.overdue.came')}</button
								>
							{/if}
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		{#if data}
			<section aria-labelledby="upcoming-title" class="card flex flex-col gap-3">
				<div class="flex items-center justify-between gap-2">
					<h2 id="upcoming-title" class="text-lg font-bold">{t('today.upcoming.title')}</h2>
					<a class="text-sm font-semibold text-brand-800 underline-offset-2 hover:underline" href="/app/agenda">{t('today.upcoming.all')}</a>
				</div>
				{#if data.upcoming.length}
					<ul class="flex flex-col divide-y divide-slate-100">
						{#each data.upcoming as a (a.id)}
							<li class="grid grid-cols-[3rem_1fr] items-center gap-x-3 gap-y-1 py-2.5 sm:grid-cols-[3rem_1fr_auto]">
								<span class="font-semibold tabular-nums">{formatTime(a.startsAt)}</span>
								<span class="min-w-0">
									<span class="font-semibold">{personName(a.patient)}</span>
									<span class="block text-sm text-slate-600"
										>{[a.reason, a.practitionerName && practitionerLabel({ name: a.practitionerName })].filter(Boolean).join(' – ')}</span
									>
								</span>
								<StatusPill status={a.status} class="col-start-2 justify-self-start sm:col-start-3" />
							</li>
						{/each}
					</ul>
				{:else}
					<p class="text-slate-600">{t('today.upcoming.empty')}</p>
				{/if}
			</section>
		{/if}
	</div>
</div>
