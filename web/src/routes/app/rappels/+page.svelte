<script lang="ts">
	/**
	 * /app/rappels – reminders by click (story G1): the appointments of the next opening day (code review M6: on
	 * Saturday Monday's, before a holiday the day after it – or another day) with the message ready in the patient's
	 * language; WhatsApp (`wa.me`) and SMS (`sms:`) open with it and the reminder is noted as sent.
	 * Without consent the buttons are greyed out; in demo practices nothing opens, a note explains instead.
	 * Code review N7 (two assistants, two devices): once sent ("Envoyé le jj/mm à HH:MM") a card offers only
	 * "Renvoyer", after a question; the list is loaded again whenever the page comes back into view.
	 */
	import { onMount } from 'svelte';
	import { api } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { clock } from '#lib/clock';
	import { errorText } from '#lib/agenda/errors';
	import { personName } from '#lib/agenda/format';
	import { smsUrl, whatsappUrl } from '#lib/agenda/links';
	import { nextOpenDay, tunisDayOf } from '#lib/agenda/time';
	import { addDays, formatDay, formatTime, t, todayTunis } from '#lib/i18n.svelte';
	import type { Appointment, Closure, PracticeSettings } from '#lib/types/agenda';
	import ConfirmDialog from '../../../lib/components/ConfirmDialog.svelte';
	import Icon from '../../../lib/components/daily/Icon.svelte';

	type Reminder = { appointment: Appointment; patientLang: string; reminderConsent: boolean; phoneDigits: string; message: string };

	const tomorrow = addDays(todayTunis(clock.now()), 1);
	/** The day whose reminders go out today; tomorrow until the opening hours are known (or when they cannot be read). */
	let openDay = $state(tomorrow);
	let day = $state(tomorrow);
	let items = $state<Reminder[] | null>(null);
	let error = $state('');
	let demoNote = $state<number | null>(null);
	let rowError = $state<{ id: number; text: string } | null>(null);
	/** "Renvoyer?" asked for this reminder; the ones confirmed show their buttons again. */
	let asking = $state<Reminder | null>(null);
	let resending = $state<number[]>([]);
	let seq = 0;

	const isDemo = $derived(!!auth.user?.practice?.isDemo);
	const sentCount = $derived((items ?? []).filter((r) => r.appointment.reminderSentAt).length);

	async function load() {
		const mine = ++seq;
		error = '';
		try {
			const list = await api<Reminder[]>(`/api/reminders?day=${day}`);
			if (mine === seq) items = list.sort((a, b) => a.appointment.startsAt.localeCompare(b.appointment.startsAt));
		} catch {
			if (mine === seq) error = t('rappels.loadError');
		}
	}

	/** Back on the page (another tab, the phone unlocked): what the other device sent meanwhile. */
	function refresh() {
		if (items !== null && document.visibilityState !== 'hidden') void load();
	}

	/** "le 30/10 à 09:12" of an instant, Tunis time. */
	function sentWhen(at: string) {
		const [, month, dayOfMonth] = tunisDayOf(at).split('-');
		return { date: `${dayOfMonth}/${month}`, time: formatTime(at) };
	}

	function resend() {
		if (asking) resending = [...resending, asking.appointment.id];
		asking = null;
	}
	onMount(async () => {
		try {
			const [practice, closures] = await Promise.all([api<PracticeSettings>('/api/practice'), api<Closure[]>('/api/closures')]);
			openDay = nextOpenDay(practice.weeklyHours, closures, todayTunis(clock.now()));
			if (day === tomorrow) day = openDay;
		} catch {
			// the opening hours are only a convenience: tomorrow then, as before
		}
		await load();
	});

	function go(next: string) {
		day = next;
		items = null;
		void load();
	}

	async function markSent(r: Reminder) {
		rowError = null;
		try {
			const updated = await api<Appointment>(`/api/appointments/${r.appointment.id}/reminder`, { method: 'POST' });
			items = (items ?? []).map((x) => (x.appointment.id === r.appointment.id ? { ...x, appointment: { ...x.appointment, ...updated } } : x));
			resending = resending.filter((id) => id !== r.appointment.id);
		} catch (err) {
			rowError = { id: r.appointment.id, text: errorText(err) };
		}
	}

	function demoClick(r: Reminder) {
		demoNote = r.appointment.id;
		void markSent(r);
	}
</script>

<svelte:head><title>{t('rappels.title')} · Daftar</title></svelte:head>
<svelte:window onfocus={refresh} />
<svelte:document onvisibilitychange={refresh} />

<div class="flex flex-col gap-5">
	<div class="flex flex-wrap items-end justify-between gap-3">
		<div>
			<h1 class="text-2xl font-bold">{t('rappels.title')}</h1>
			<p class="text-slate-600">{t('rappels.subtitle', { date: formatDay(day, 'long') })}</p>
		</div>
		<div class="flex items-center gap-1">
			<button type="button" class="btn-secondary min-w-11 px-2" aria-label={t('rappels.previousDay')} onclick={() => go(addDays(day, -1))}><Icon name="start" /></button>
			<button type="button" class="btn-secondary" disabled={day === openDay} onclick={() => go(openDay)}
				>{openDay === tomorrow ? t('rappels.tomorrow') : t('rappels.nextOpenDay')}</button
			>
			<button type="button" class="btn-secondary min-w-11 px-2" aria-label={t('rappels.nextDay')} onclick={() => go(addDays(day, 1))}><Icon name="end" /></button>
		</div>
	</div>

	<p class="rounded-xl bg-brand-50 px-4 py-3 text-brand-900 ring-1 ring-brand-100">{t('rappels.intro')}</p>

	{#if error}
		<div role="alert" class="card flex flex-wrap items-center justify-between gap-3 border-rose-200 bg-rose-50 text-rose-900">
			<p>{error}</p>
			<button type="button" class="btn-secondary" onclick={load}>{t('common.retry')}</button>
		</div>
	{:else if items === null}
		<p class="card text-slate-600" aria-busy="true">{t('common.loading')}</p>
	{:else if !items.length}
		<p class="card text-slate-600">{t('rappels.empty')}</p>
	{:else}
		<p class="font-semibold text-slate-700">{t('rappels.summary', { count: items.length, sent: sentCount })}</p>
		<ul class="grid gap-3 lg:grid-cols-2">
			{#each items as r (r.appointment.id)}
				{@const a = r.appointment}
				{@const consent = r.reminderConsent}
				{@const sent = !!a.reminderSentAt && !resending.includes(a.id)}
				<li class="flex flex-col gap-3 rounded-2xl border bg-white p-4 shadow-sm {consent ? 'border-slate-200' : 'border-slate-200 bg-slate-50'}">
					<div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
						<h2 class="text-lg font-bold {consent ? '' : 'text-slate-500'}"><span class="tabular-nums">{formatTime(a.startsAt)}</span> {personName(a.patient)}</h2>
						{#if a.reminderSentAt}
							<span class="ms-auto inline-flex items-center gap-1 font-semibold text-emerald-800"><Icon name="check" class="h-4 w-4" />{t('rappels.sentAt', sentWhen(a.reminderSentAt))}</span>
						{:else if !consent}
							<span class="ms-auto text-sm font-semibold text-slate-500">{t('rappels.noConsent')}</span>
						{/if}
					</div>
					<p class="text-sm {consent ? 'text-slate-600' : 'text-slate-500'}">{[a.reason, a.practitionerName].filter(Boolean).join(' – ')}</p>
					{#if consent}
						<p class="rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-800" lang={r.patientLang} dir={r.patientLang === 'ar' ? 'rtl' : 'ltr'}>{r.message}</p>
					{/if}
					{#if consent && sent}
						<button type="button" class="btn-secondary self-start" onclick={() => (asking = r)}><Icon name="repeat" class="h-4 w-4" />{t('rappels.resend')}</button>
					{:else}
					<div class="grid grid-cols-2 gap-2">
						{#if !consent}
							<button type="button" class="btn-secondary min-h-12" disabled>{t('rappels.whatsapp')}</button>
							<button type="button" class="btn-secondary min-h-12" disabled>{t('rappels.sms')}</button>
						{:else if isDemo}
							<button type="button" class="btn min-h-12 border border-emerald-300 bg-emerald-50 text-emerald-900 hover:bg-emerald-100" onclick={() => demoClick(r)}
								><Icon name="chat" />{t('rappels.whatsapp')}</button
							>
							<button type="button" class="btn-secondary min-h-12" onclick={() => demoClick(r)}><Icon name="sms" />{t('rappels.sms')}</button>
						{:else}
							<a
								class="btn min-h-12 border border-emerald-300 bg-emerald-50 text-emerald-900 hover:bg-emerald-100"
								href={whatsappUrl(r.phoneDigits, r.message)}
								target="_blank"
								rel="noopener noreferrer"
								onclick={() => void markSent(r)}><Icon name="chat" />{t('rappels.whatsapp')}</a
							>
							<a class="btn-secondary min-h-12" href={smsUrl(r.phoneDigits, r.message)} onclick={() => void markSent(r)}><Icon name="sms" />{t('rappels.sms')}</a>
						{/if}
					</div>
					{/if}
					{#if consent && !a.reminderSentAt && !isDemo}
						<button type="button" class="self-start text-sm font-semibold text-brand-800 underline underline-offset-2" onclick={() => markSent(r)}>{t('rappels.markSent')}</button>
					{/if}
					{#if demoNote === a.id}<p role="status" class="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900 ring-1 ring-amber-200">{t('rappels.demo')}</p>{/if}
					{#if rowError?.id === a.id}<p role="alert" class="text-sm text-rose-800">{rowError.text}</p>{/if}
				</li>
			{/each}
		</ul>
	{/if}
</div>

<ConfirmDialog
	open={!!asking}
	title={t('rappels.resendTitle')}
	message={asking?.appointment.reminderSentAt
		? t('rappels.resendMessage', { patient: personName(asking.appointment.patient), ...sentWhen(asking.appointment.reminderSentAt) })
		: ''}
	confirmLabel={t('rappels.resendConfirm')}
	onconfirm={resend}
	oncancel={() => (asking = null)}
/>
