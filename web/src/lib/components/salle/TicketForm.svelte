<script lang="ts">
	/**
	 * "Nouveau ticket": for a patient of the practice (search) or just a name and phone (walk-in). After creation the
	 * ticket number, its QR code and WhatsApp link are shown at once – the patient is standing at the desk.
	 */
	import { errorText } from '../../agenda/errors';
	import { api } from '../../api';
	import { personName } from '../../agenda/format';
	import { displayPhone } from '../../agenda/links';
	import { t } from '../../i18n.svelte';
	import type { PatientSummary } from '../../types/patients';
	import type { QueueEntry } from '../../types/queue';
	import Modal from '../daily/Modal.svelte';
	import PatientSearch from '../daily/PatientSearch.svelte';
	import TicketQr from './TicketQr.svelte';

	let { practice, oncreated, onclose }: { practice: string; oncreated: (e: QueueEntry) => void; onclose: () => void } = $props();

	let mode = $state<'patient' | 'name'>('patient');
	let patient = $state<PatientSummary | null>(null);
	let name = $state('');
	let phone = $state('');
	let error = $state('');
	let busy = $state(false);
	let created = $state<QueueEntry | null>(null);

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		const body = mode === 'patient' ? (patient ? { patientId: patient.id } : null) : name.trim() ? { name: name.trim(), ...(phone.trim() ? { phone: phone.trim() } : {}) } : null;
		if (!body) {
			error = t('salle.form.needName');
			return;
		}
		busy = true;
		try {
			created = await api<QueueEntry>('/api/queue', { method: 'POST', json: body });
			oncreated(created);
		} catch (err) {
			error = errorText(err);
		} finally {
			busy = false;
		}
	}

	function again() {
		created = null;
		patient = null;
		name = '';
		phone = '';
	}
</script>

<Modal title={t('salle.form.title')} {onclose} guard={!created}>
	{#if created}
		<div class="flex flex-col items-center gap-2">
			<p class="text-6xl font-bold text-brand-800 tabular-nums">{created.ticketNo}</p>
			<p class="text-lg font-semibold">{t('salle.form.created', { number: created.ticketNo, name: created.name })}</p>
			<TicketQr entry={created} {practice} />
		</div>
	{:else}
		<form id="ticket-form" class="flex flex-col gap-4" onsubmit={submit} novalidate>
			<div class="grid grid-cols-2 gap-1 rounded-lg bg-slate-100 p-1" role="radiogroup">
				{#each [['patient', t('salle.form.forPatient')], ['name', t('salle.form.walkIn')]] as [value, text] (value)}
					<label
						class="flex min-h-11 cursor-pointer items-center justify-center rounded-md px-3 text-sm font-semibold has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-brand-700 {mode ===
						value
							? 'bg-white text-brand-900 shadow-sm'
							: 'text-slate-600'}"
					>
						<input type="radio" class="sr-only" name="ticket-mode" {value} bind:group={mode} />{text}
					</label>
				{/each}
			</div>
			{#if mode === 'patient'}
				{#if patient}
					<div class="flex items-center gap-3 rounded-xl border border-brand-200 bg-brand-50 px-3 py-2.5">
						<div class="min-w-0 flex-1">
							<p class="font-semibold">{personName(patient)}</p>
							<p class="text-sm text-slate-600 tabular-nums" dir="ltr">{displayPhone(patient.phone)}</p>
						</div>
						<button type="button" class="btn-secondary min-h-10 px-3 text-sm" onclick={() => (patient = null)}>{t('agenda.form.changePatient')}</button>
					</div>
				{:else}
					<PatientSearch onpick={(p) => (patient = p)} autofocus />
				{/if}
			{:else}
				<label class="label">{t('salle.form.name')}<input class="input" bind:value={name} maxlength="120" autocomplete="off" data-autofocus /></label>
				<label class="label">{t('salle.form.phone')}<input class="input" type="tel" inputmode="tel" dir="ltr" bind:value={phone} autocomplete="off" /></label>
			{/if}
			{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}
		</form>
	{/if}

	{#snippet footer()}
		{#if created}
			<button type="button" class="btn-secondary" onclick={again}>{t('salle.newTicket')}</button>
			<button type="button" class="btn-primary" onclick={onclose}>{t('common.close')}</button>
		{:else}
			<button type="button" class="btn-secondary" onclick={onclose}>{t('common.cancel')}</button>
			<button type="submit" form="ticket-form" class="btn-primary" disabled={busy}>{t('salle.form.create')}</button>
		{/if}
	{/snippet}
</Modal>
