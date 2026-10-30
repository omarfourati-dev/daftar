<script lang="ts">
	/**
	 * New or moved appointment in one dialog (story B2, "un rendez-vous en 10 secondes"): find the patient by name or
	 * phone or create them right here, the service sets duration and reason, then time, practitioner, deposit, note.
	 * The medical alert is shown in red, ≥ 2 no-shows suggest a deposit. A taken slot (409) lists the conflict and
	 * the next free start times – one click books one of them.
	 */
	import { untrack } from 'svelte';
	import { ApiError, api, apiErrorMessage } from '../../api';
	import type { AgendaBase } from '../../agenda/data';
	import { savedAppointment } from '../../agenda/data';
	import { money, personName, practitionerLabel, serviceLabel, slotLabel } from '../../agenda/format';
	import { displayPhone, millimesToInput, parseDinars } from '../../agenda/links';
	import { hhmm, minutesOfDay, tunisDayOf } from '../../agenda/time';
	import { formatTime, i18n, t, tunisInstant } from '../../i18n.svelte';
	import type { Appointment, AppointmentSaved, ConflictProblem } from '../../types/agenda';
	import type { Patient, PatientSummary } from '../../types/patients';
	import Icon from '../daily/Icon.svelte';
	import Modal from '../daily/Modal.svelte';
	import PatientSearch from '../daily/PatientSearch.svelte';

	type Chosen = Pick<PatientSummary, 'id' | 'firstName' | 'lastName' | 'phone' | 'noShows'> & { hasAlerts?: boolean; alerts?: string };
	type Props = {
		base: AgendaBase;
		/** Editing (moving) an existing appointment. */
		appointment?: Appointment | null;
		/** New appointment: proposed day, time and practitioner (from the clicked slot). */
		day?: string;
		time?: string;
		practitionerId?: number | null;
		/** New appointment for a known patient (from the patient file). */
		patient?: Chosen | null;
		onsaved: (a: Appointment) => void;
		onclose: () => void;
	};
	let { base, appointment = null, day: startDay, time: startTime, practitionerId: startPractitioner = null, patient: startPatient = null, onsaved, onclose }: Props =
		$props();

	// The dialog is created for one appointment/slot: its fields start from the props once.
	const init = untrack(() => ({ appointment, day: startDay, time: startTime, practitionerId: startPractitioner, patient: startPatient, base }));
	const editing = !!init.appointment;
	const services = init.base.services.filter((s) => s.active !== false || s.id === init.appointment?.serviceId);
	const current = init.appointment;

	let patient = $state<Chosen | null>(current ? { ...current.patient } : init.patient);
	let query = $state('');
	let creating = $state(false);
	let firstName = $state('');
	let lastName = $state('');
	let phone = $state('');
	let lang = $state<string>(i18n.locale);
	let consent = $state(false);

	let day = $state(current ? tunisDayOf(current.startsAt) : (init.day ?? ''));
	let time = $state(current ? hhmm(minutesOfDay(current.startsAt)) : (init.time ?? ''));
	let duration = $state(current?.durationMin ?? init.base.practice.defaultDurationMin ?? 30);
	let serviceKey = $state(current?.serviceId ? String(current.serviceId) : '');
	let practitionerKey = $state(current ? (current.practitionerId ? String(current.practitionerId) : '') : init.practitionerId ? String(init.practitionerId) : '');
	let reason = $state(current?.reason ?? '');
	let deposit = $state(millimesToInput(current?.depositRequiredMillimes ?? 0));
	let notes = $state(current?.notes ?? '');

	let error = $state('');
	let conflict = $state<ConflictProblem | null>(null);
	let busy = $state(false);

	const service = $derived(services.find((s) => String(s.id) === serviceKey) ?? null);

	// The red medical alert: the search result only says "has alerts", the file has the text.
	$effect(() => {
		const p = patient;
		if (!p || p.alerts !== undefined || !p.hasAlerts) return;
		void api<Patient>(`/api/patients/${p.id}`)
			.then((full) => {
				if (patient?.id === full.id) patient = { ...patient, alerts: full.alerts ?? '' };
			})
			.catch(() => undefined);
	});

	function pick(p: PatientSummary) {
		patient = { ...p };
		error = '';
	}

	function startCreating() {
		const text = query.trim();
		if (/\d/.test(text) && !/[a-zA-Z؀-ۿ]/.test(text)) phone = text;
		else if (text) {
			const words = text.split(/\s+/);
			if (words.length > 1) {
				firstName = words[0];
				lastName = words.slice(1).join(' ');
			} else lastName = text;
		}
		creating = true;
		error = '';
	}

	function chooseService(value: string) {
		const previous = service ? serviceLabel(service) : '';
		serviceKey = value;
		const next = services.find((s) => String(s.id) === value);
		if (!next) return;
		duration = next.durationMin;
		if (!reason.trim() || reason === previous) reason = serviceLabel(next);
	}

	async function save(at?: string) {
		error = '';
		if (at) {
			day = tunisDayOf(at);
			time = hhmm(minutesOfDay(at));
		}
		conflict = null;
		if (!patient && !creating) {
			error = t('agenda.form.pickPatient');
			return;
		}
		const depositMillimes = deposit.trim() ? parseDinars(deposit) : 0;
		if (depositMillimes === null) {
			error = t('agenda.form.invalidAmount');
			return;
		}
		busy = true;
		try {
			if (!patient) {
				const created = await api<Patient>('/api/patients', {
					method: 'POST',
					json: { firstName: firstName.trim(), lastName: lastName.trim(), phone: phone.trim(), lang, reminderConsent: consent }
				});
				patient = created;
				creating = false;
			}
			const body = {
				patientId: patient.id,
				startsAt: tunisInstant(day, time),
				durationMin: Number(duration),
				reason: reason.trim() || (service ? serviceLabel(service) : ''),
				serviceId: service?.id ?? null,
				practitionerId: practitionerKey ? Number(practitionerKey) : null,
				notes: notes.trim(),
				depositRequiredMillimes: depositMillimes
			};
			const saved = current
				? await api<AppointmentSaved>(`/api/appointments/${current.id}`, { method: 'PATCH', json: body })
				: await api<AppointmentSaved>('/api/appointments', { method: 'POST', json: body });
			onsaved(savedAppointment(saved));
		} catch (err) {
			if (err instanceof ApiError && err.status === 409 && err.body && typeof err.body === 'object') conflict = err.body as ConflictProblem;
			else error = apiErrorMessage(err);
		} finally {
			busy = false;
		}
	}

	function submit(e: SubmitEvent) {
		e.preventDefault();
		void save();
	}
</script>

<Modal title={editing ? t('agenda.form.editTitle') : t('agenda.form.newTitle')} {onclose} wide>
	<form id="appointment-form" class="grid gap-5 md:grid-cols-2" onsubmit={submit} novalidate>
		<fieldset class="flex min-w-0 flex-col gap-3">
			<legend class="mb-1 text-sm font-semibold text-slate-500">{t('agenda.form.patient')}</legend>
			{#if patient}
				<div class="flex items-center gap-3 rounded-xl border border-brand-200 bg-brand-50 px-3 py-2.5">
					<div class="min-w-0 flex-1">
						<p class="truncate font-semibold">{personName(patient)}</p>
						<p class="text-sm text-slate-600 tabular-nums" dir="ltr">{displayPhone(patient.phone)}</p>
					</div>
					{#if !editing}
						<button type="button" class="btn-secondary min-h-10 px-3 text-sm" onclick={() => (patient = null)}>{t('agenda.form.changePatient')}</button>
					{/if}
				</div>
				{#if patient.alerts}
					<p class="flex gap-2 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-800">
						<Icon name="alert" class="mt-0.5 h-4 w-4" /><span><span class="sr-only">{t('agenda.alert')} – </span>{patient.alerts}</span>
					</p>
				{/if}
				{#if patient.noShows >= 2}
					<div class="flex flex-wrap items-center gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900 ring-1 ring-amber-200">
						<span class="font-semibold">{t('agenda.form.noShowWarning', { count: patient.noShows })}</span>
						{#if service?.priceMillimes}
							<button type="button" class="btn-secondary min-h-9 px-3 text-sm" onclick={() => (deposit = millimesToInput(service?.priceMillimes ?? 0))}
								>{t('agenda.form.applyDeposit', { amount: money(service.priceMillimes) })}</button
							>
						{/if}
					</div>
				{/if}
			{:else if creating}
				<div class="grid grid-cols-2 gap-3">
					<label class="label">{t('agenda.form.firstName')}<input class="input" bind:value={firstName} autocomplete="off" data-autofocus /></label>
					<label class="label">{t('agenda.form.lastName')}<input class="input" bind:value={lastName} autocomplete="off" /></label>
				</div>
				<label class="label"
					>{t('agenda.form.phone')}<input class="input" type="tel" inputmode="tel" dir="ltr" bind:value={phone} placeholder={t('agenda.form.phoneHint')} autocomplete="off" /></label
				>
				<div class="flex flex-wrap items-center gap-4">
					<span class="text-sm font-medium text-slate-700">{t('agenda.form.lang')}</span>
					<label class="inline-flex min-h-11 items-center gap-2"><input type="radio" bind:group={lang} value="fr" class="h-5 w-5 accent-brand-700" />{t('common.french')}</label>
					<label class="inline-flex min-h-11 items-center gap-2" lang="ar"
						><input type="radio" bind:group={lang} value="ar" class="h-5 w-5 accent-brand-700" />{t('common.arabic')}</label
					>
				</div>
				<label class="inline-flex min-h-11 items-center gap-3 text-sm"
					><input type="checkbox" bind:checked={consent} class="h-5 w-5 accent-brand-700" />{t('agenda.form.consent')}</label
				>
				<button type="button" class="self-start text-sm font-semibold text-brand-800 underline underline-offset-2" onclick={() => (creating = false)}
					>{t('agenda.form.choosePatient')}</button
				>
			{:else}
				<PatientSearch onpick={pick} bind:query autofocus />
				<button type="button" class="btn-secondary self-start" onclick={startCreating}><Icon name="plus" />{t('agenda.form.newPatient')}</button>
			{/if}
		</fieldset>

		<fieldset class="flex min-w-0 flex-col gap-3">
			<legend class="sr-only">{t('agenda.detail.title')}</legend>
			<label class="label"
				>{t('agenda.form.service')}
				<select class="input" value={serviceKey} onchange={(e) => chooseService(e.currentTarget.value)}>
					<option value="">{t('agenda.form.noService')}</option>
					{#each services as s (s.id)}<option value={String(s.id)}>{serviceLabel(s)}</option>{/each}
				</select>
			</label>
			<label class="label">{t('agenda.form.reason')}<input class="input" bind:value={reason} maxlength="200" /></label>
			<div class="grid grid-cols-2 gap-3">
				<label class="label">{t('agenda.form.date')}<input class="input" type="date" bind:value={day} required /></label>
				<label class="label"
					>{t('agenda.form.time')}<input class="input" type="time" bind:value={time} step={(init.base.practice.slotMinutes || 15) * 60} required /></label
				>
				<label class="label">{t('agenda.form.duration')}<input class="input" type="number" min="5" max="480" step="5" bind:value={duration} required /></label>
				<label class="label"
					>{t('agenda.form.practitioner')}
					<select class="input" bind:value={practitionerKey}>
						<option value="">{t('agenda.form.anyPractitioner')}</option>
						{#each init.base.practitioners as p (p.id)}<option value={String(p.id)}>{practitionerLabel(p)}</option>{/each}
						{#if current?.practitionerId && !init.base.practitioners.some((p) => p.id === current?.practitionerId)}
							<option value={String(current.practitionerId)}>{current.practitionerName}</option>
						{/if}
					</select>
				</label>
			</div>
			<label class="label"
				>{t('agenda.form.deposit')}<input
					class="input {patient && patient.noShows >= 2 ? 'border-amber-400 ring-1 ring-amber-300' : ''}"
					inputmode="decimal"
					bind:value={deposit}
					placeholder="0"
					aria-describedby="deposit-hint"
				/></label
			>
			<p id="deposit-hint" class="-mt-2 text-xs text-slate-500">{t('agenda.form.depositHint')}</p>
			<label class="label">{t('agenda.form.notes')}<textarea class="input min-h-20" bind:value={notes} maxlength="2000"></textarea></label>
		</fieldset>
	</form>

	{#if error}
		<p role="alert" class="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900">{error}</p>
	{/if}
	{#if conflict}
		<div role="alert" class="mt-4 flex flex-col gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-3 text-sm text-rose-950">
			<p class="font-semibold">{t('agenda.form.conflictTitle')}</p>
			{#each conflict.conflicts ?? [] as c (c.id)}
				<p>{t('agenda.form.conflictWith', { time: formatTime(c.startsAt), patient: c.patientName })}</p>
			{/each}
			{#if conflict.suggestions?.length}
				<p class="mt-1 font-medium text-ink">{t('agenda.form.suggestions')}</p>
				<div class="flex flex-wrap gap-2">
					{#each conflict.suggestions as s (s)}
						<button type="button" class="btn-secondary min-h-10 border-brand-300 px-3 text-sm text-brand-900" onclick={() => save(s)}>{slotLabel(s)}</button>
					{/each}
				</div>
			{:else}
				<p>{t('agenda.form.noSuggestion')}</p>
			{/if}
		</div>
	{/if}

	{#snippet footer()}
		<button type="button" class="btn-secondary" onclick={onclose}>{t('common.cancel')}</button>
		<button type="submit" form="appointment-form" class="btn-primary" disabled={busy}>{busy ? t('agenda.form.saving') : t('agenda.form.save')}</button>
	{/snippet}
</Modal>
