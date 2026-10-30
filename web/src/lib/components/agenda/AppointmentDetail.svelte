<script lang="ts">
	/**
	 * An appointment opened from the agenda (story B3): who, when, warnings, and the next steps as big buttons
	 * (requested → confirmed → arrived → in consultation → done, or no-show / cancelled). Online requests are confirmed
	 * or declined with a ready WhatsApp message in the patient's language. Deposit can be collected here.
	 */
	import { untrack } from 'svelte';
	import { api, apiErrorMessage } from '../../api';
	import type { AgendaBase } from '../../agenda/data';
	import { money, personName, practitionerLabel, statusLabel } from '../../agenda/format';
	import { telUrl, whatsappUrl, displayPhone } from '../../agenda/links';
	import { dateAndTime, messageIn, patientLang, type PatientMessage } from '../../agenda/messages';
	import { hhmm, minutesOfDay } from '../../agenda/time';
	import { formatDate, formatDateTime, t, type MessageKey } from '../../i18n.svelte';
	import type { AppointmentStatus } from '../../status';
	import type { Appointment } from '../../types/agenda';
	import Icon from '../daily/Icon.svelte';
	import Modal from '../daily/Modal.svelte';
	import StatusPill from './StatusPill.svelte';

	type Props = {
		appointment: Appointment;
		base: AgendaBase;
		onchanged: (a: Appointment) => void;
		onmove: (a: Appointment) => void;
		onclose: () => void;
		/** Series cancellation (story B4) – shown for appointments of a series. */
		oncancelseries?: (a: Appointment) => void;
	};
	let { appointment, base, onchanged, onmove, onclose, oncancelseries }: Props = $props();

	let a = $state(untrack(() => appointment));
	let busy = $state(false);
	let error = $state('');
	let notice = $state('');
	let confirmingCancel = $state(false);
	/** After confirming/declining a request: the message to send. */
	let sendMessage = $state<PatientMessage | null>(null);
	let receiptId = $state<number | null>(null);

	type Action = { status: AppointmentStatus; key: MessageKey; primary?: boolean };
	const NEXT: Record<string, Action[]> = {
		requested: [
			{ status: 'confirmed', key: 'agenda.actions.confirm', primary: true },
			{ status: 'cancelled', key: 'agenda.actions.reject' }
		],
		scheduled: [
			{ status: 'confirmed', key: 'agenda.actions.confirm' },
			{ status: 'arrived', key: 'agenda.actions.arrived', primary: true },
			{ status: 'no_show', key: 'agenda.actions.no_show' }
		],
		confirmed: [
			{ status: 'arrived', key: 'agenda.actions.arrived', primary: true },
			{ status: 'no_show', key: 'agenda.actions.no_show' }
		],
		arrived: [
			{ status: 'in_treatment', key: 'agenda.actions.in_treatment', primary: true },
			{ status: 'done', key: 'agenda.actions.done' }
		],
		in_treatment: [{ status: 'done', key: 'agenda.actions.done', primary: true }],
		done: [],
		no_show: [{ status: 'scheduled', key: 'agenda.actions.reopen' }],
		cancelled: [{ status: 'scheduled', key: 'agenda.actions.reopen' }]
	};
	const actions = $derived(NEXT[a.status] ?? []);
	const start = $derived(minutesOfDay(a.startsAt));
	const remaining = $derived(Math.max(a.depositRequiredMillimes - a.depositPaidMillimes, 0));
	const practitioner = $derived.by(() => {
		const p = base.practitioners.find((x) => x.id === a.practitionerId);
		return p ? practitionerLabel(p) : a.practitionerName;
	});
	const cancellable = $derived(!['cancelled', 'no_show', 'done'].includes(a.status));
	const when = $derived(dateAndTime(a.startsAt));

	const whatsappMessage = $derived.by(() => {
		if (!sendMessage) return '';
		const lang = patientLang(a.patient.lang);
		const practice = lang === 'ar' && base.practice.nameAr ? base.practice.nameAr : base.practice.name;
		return messageIn(lang, sendMessage, { patient: a.patient.firstName, practice, ...dateAndTime(a.startsAt) });
	});

	function update(next: Appointment) {
		a = next;
		onchanged(next);
	}

	async function setStatus(status: AppointmentStatus) {
		const wasRequest = a.status === 'requested';
		busy = true;
		error = '';
		notice = '';
		try {
			update(await api<Appointment>(`/api/appointments/${a.id}/status`, { method: 'POST', json: { status } }));
			notice = t('agenda.detail.statusChanged', { status: statusLabel(status) });
			sendMessage = wasRequest ? (status === 'confirmed' ? 'confirmed' : status === 'cancelled' ? 'rejected' : null) : null;
			confirmingCancel = false;
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			busy = false;
		}
	}

	async function collectDeposit() {
		busy = true;
		error = '';
		try {
			const amount = remaining;
			const payment = await api<{ id: number }>(`/api/patients/${a.patient.id}/payments`, {
				method: 'POST',
				json: { amountMillimes: amount, method: 'cash', appointmentId: a.id, isDeposit: true }
			});
			receiptId = payment.id;
			update({ ...a, depositPaidMillimes: a.depositPaidMillimes + amount });
			notice = t('agenda.detail.depositCollected');
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			busy = false;
		}
	}
</script>

<Modal title={personName(a.patient)} subtitle={formatDate(a.startsAt, 'long')} {onclose}>
	<div class="flex flex-col gap-4">
		<div class="flex flex-wrap items-center gap-2">
			<StatusPill status={a.status} class="px-3 py-1 text-sm" />
			<span class="font-semibold tabular-nums">{t('agenda.detail.time', { start: hhmm(start), end: hhmm(start + a.durationMin), duration: a.durationMin })}</span>
			{#if practitioner}<span class="text-slate-600">{t('agenda.detail.with', { practitioner })}</span>{/if}
		</div>
		{#if a.reason}<p class="text-lg font-semibold">{a.reason}</p>{/if}

		{#if a.patient.alerts}
			<p class="flex gap-2 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 font-semibold text-rose-800">
				<Icon name="alert" class="mt-0.5 h-5 w-5" /><span><span class="sr-only">{t('agenda.alert')} – </span>{a.patient.alerts}</span>
			</p>
		{/if}
		{#if a.patient.noShows >= 2}
			<p class="rounded-lg bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900 ring-1 ring-amber-200">
				{t('agenda.form.noShowWarning', { count: a.patient.noShows })}
			</p>
		{/if}

		<div class="flex flex-wrap gap-2">
			<a class="btn-secondary min-h-10 px-3 text-sm" href="/app/patients/{a.patient.id}">{t('agenda.detail.openFile')}</a>
			<a class="btn-secondary min-h-10 px-3 text-sm" href={telUrl(a.patient.phone)}
				><Icon name="phone" class="h-4 w-4" />{t('agenda.detail.call')}</a
			>
			<a class="btn-secondary min-h-10 px-3 text-sm" href={whatsappUrl(a.patient.phone)} target="_blank" rel="noopener noreferrer"
				><Icon name="chat" class="h-4 w-4" />{t('agenda.detail.whatsapp')}</a
			>
			<span class="self-center text-sm text-slate-600 tabular-nums" dir="ltr">{displayPhone(a.patient.phone)}</span>
		</div>

		{#if a.source === 'online' || a.status === 'requested'}
			<div class="rounded-lg border border-dashed border-brand-600 bg-brand-50 px-3 py-2 text-sm">
				<p class="font-semibold text-brand-900">{t('agenda.detail.online')}</p>
				{#if a.patientNote}<p class="mt-1"><span class="text-slate-600">{t('agenda.detail.patientNote')}</span> {a.patientNote}</p>{/if}
			</div>
		{/if}
		{#if a.notes}
			<p class="text-sm"><span class="font-semibold text-slate-600">{t('agenda.detail.notes')}</span> {a.notes}</p>
		{/if}

		{#if a.depositRequiredMillimes > 0}
			<div class="flex flex-wrap items-center gap-3 rounded-lg bg-slate-50 px-3 py-2 ring-1 ring-slate-200">
				<span class="text-sm font-semibold text-slate-600">{t('agenda.detail.deposit')}</span>
				<span class="font-semibold">{t('agenda.detail.depositState', { paid: money(a.depositPaidMillimes), required: money(a.depositRequiredMillimes) })}</span>
				{#if remaining > 0 && !['cancelled', 'no_show'].includes(a.status)}
					<button type="button" class="btn-accent ms-auto min-h-10 px-3 text-sm" disabled={busy} onclick={collectDeposit}>{t('agenda.detail.collectDeposit')}</button>
				{/if}
				{#if receiptId}<a class="text-sm font-semibold text-brand-800 underline" href="/app/recu/{receiptId}">{t('agenda.detail.receipt')}</a>{/if}
			</div>
		{/if}
		{#if a.reminderSentAt}
			<p class="text-sm text-slate-600">{t('agenda.detail.reminderSent', { date: formatDateTime(a.reminderSentAt) })}</p>
		{/if}

		{#if notice}<p role="status" class="rounded-lg bg-emerald-50 px-3 py-2 font-medium text-emerald-900">{notice}</p>{/if}
		{#if sendMessage && whatsappMessage}
			<a class="btn min-h-12 bg-[#25d366] text-ink hover:bg-[#1ebe5b]" href={whatsappUrl(a.patient.phone, whatsappMessage)} target="_blank" rel="noopener noreferrer"
				><Icon name="chat" />{t(sendMessage === 'confirmed' ? 'agenda.actions.confirmWhatsapp' : 'agenda.actions.rejectWhatsapp')}</a
			>
		{/if}
		{#if error}<p role="alert" class="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900">{error}</p>{/if}

		{#if actions.length}
			<div class="flex flex-col gap-2">
				<p class="text-sm font-semibold text-slate-500">{t('agenda.detail.statusTitle')}</p>
				<div class="grid grid-cols-2 gap-2 sm:grid-cols-3">
					{#each actions as action (action.status)}
						<button
							type="button"
							class="{action.primary ? 'btn-primary' : 'btn-secondary'} min-h-14 text-base"
							disabled={busy}
							onclick={() => setStatus(action.status)}>{t(action.key)}</button
						>
					{/each}
				</div>
			</div>
		{/if}

		{#if confirmingCancel}
			<div class="flex flex-col gap-3 rounded-lg border border-rose-200 bg-rose-50 p-3">
				<p class="font-semibold text-rose-950">{t('agenda.detail.cancelConfirm', { patient: personName(a.patient), date: when.date, time: when.time })}</p>
				<div class="flex flex-wrap gap-2">
					<button type="button" class="btn-secondary" onclick={() => (confirmingCancel = false)}>{t('agenda.detail.keep')}</button>
					<button type="button" class="btn bg-rose-700 text-white hover:bg-rose-800" disabled={busy} onclick={() => setStatus('cancelled')}
						>{t('agenda.detail.confirmCancel')}</button
					>
				</div>
			</div>
		{/if}
	</div>

	{#snippet footer()}
		{#if a.seriesId && cancellable && oncancelseries}
			<button type="button" class="btn-secondary me-auto text-rose-800" onclick={() => oncancelseries?.(a)}><Icon name="repeat" />{t('agenda.series.cancelFrom')}</button>
		{/if}
		{#if cancellable && a.status !== 'requested'}
			<button type="button" class="btn-secondary text-rose-800" onclick={() => (confirmingCancel = true)}>{t('agenda.detail.cancelAppointment')}</button>
		{/if}
		{#if a.status !== 'done' && a.status !== 'cancelled'}
			<button type="button" class="btn-secondary" onclick={() => onmove(a)}><Icon name="edit" />{t('agenda.detail.move')}</button>
		{/if}
	{/snippet}
</Modal>
