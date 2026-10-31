<script lang="ts">
	/**
	 * New or moved appointment in one dialog (story B2, "un rendez-vous en 10 secondes"): find the patient by name or
	 * phone or create them right here, the service sets duration and reason, then time, practitioner, deposit, note.
	 * The medical alert is shown in red, ≥ 2 no-shows suggest a deposit. A taken slot (409) lists the conflict and
	 * the next free start times – one click books one of them.
	 * Practitioner (code review H1): with one active practitioner it is always that one (no "Non attribué"); with
	 * several "Premier disponible" sends null and the server takes the first one free at that time.
	 */
	import { errorText } from '../../agenda/errors';
	import { tick, untrack } from 'svelte';
	import { ApiError, api } from '../../api';
	import type { AgendaBase } from '../../agenda/data';
	import { savedAppointment } from '../../agenda/data';
	import { money, personName, practitionerLabel, serviceLabel, slotLabel } from '../../agenda/format';
	import { displayPhone, millimesToInput, parseDinars } from '../../agenda/links';
	import { hhmm, isoWeekday, minutesOfDay, tunisDayOf, weekDays } from '../../agenda/time';
	import { formatTime, i18n, t, tunisInstant } from '../../i18n.svelte';
	import type { Appointment, AppointmentSaved, ConflictProblem, SeriesCreated, SeriesOccurrence } from '../../types/agenda';
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
		/** The saved appointment (the first one of a series) and an optional summary for the page. */
		onsaved: (a: Appointment, note?: string) => void;
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
	const doctors = init.base.practitioners;
	/** With exactly one active practitioner every appointment is theirs. */
	const onlyDoctor = doctors.length === 1 ? String(doctors[0].id) : '';
	const givenDoctor = current ? current.practitionerId : init.practitionerId;
	let practitionerKey = $state(givenDoctor ? String(givenDoctor) : onlyDoctor);
	let reason = $state(current?.reason ?? '');
	let deposit = $state(millimesToInput(current?.depositRequiredMillimes ?? 0));
	let notes = $state(current?.notes ?? '');

	// Series (story B4): weekdays (ISO 1–7) and number of sessions, checked by the server before saving.
	let repeat = $state(false);
	let weekdays = $state<number[]>(init.day ? [isoWeekday(init.day)] : []);
	let count = $state(10);
	let occurrences = $state<SeriesOccurrence[] | null>(null);
	let seriesList: HTMLUListElement | undefined = $state();
	const blocked = $derived(occurrences?.filter((o) => o.conflict || o.closed).length ?? 0);
	const WEEK = weekDays('2026-10-26'); // a Monday … Sunday, only for the names
	const weekdayName = (i: number, style: 'long' | 'short') =>
		new Intl.DateTimeFormat(i18n.locale === 'ar' ? 'ar-TN' : 'fr-TN', { weekday: style, timeZone: 'Africa/Tunis' }).format(new Date(`${WEEK[i - 1]}T12:00:00+01:00`));

	// any change of what is repeated needs a new check
	$effect(() => {
		void [day, time, duration, practitionerKey, serviceKey, patient?.id, count, weekdays.length, repeat];
		occurrences = null;
	});

	function toggleWeekday(d: number) {
		weekdays = weekdays.includes(d) ? weekdays.filter((x) => x !== d) : [...weekdays, d].sort();
	}

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

	/** The patient of the dialog, created on the server first when it is a new one. */
	async function ensurePatient(): Promise<Chosen> {
		if (patient) return patient;
		const created = await api<Patient>('/api/patients', {
			method: 'POST',
			json: { firstName: firstName.trim(), lastName: lastName.trim(), phone: phone.trim(), lang, reminderConsent: consent }
		});
		patient = created;
		creating = false;
		return created;
	}

	function common(patientId: number) {
		return {
			patientId,
			startsAt: tunisInstant(day, time),
			durationMin: Number(duration),
			reason: reason.trim() || (service ? serviceLabel(service) : ''),
			serviceId: service?.id ?? null,
			practitionerId: practitionerKey ? Number(practitionerKey) : null,
			notes: notes.trim()
		};
	}

	/**
	 * Editing: only what really changed (code review N1) – a note or a deposit on an appointment that has already
	 * started would otherwise send its time again and be refused as "in the past".
	 */
	function changedFields(before: Appointment, body: ReturnType<typeof common> & { depositRequiredMillimes: number }) {
		const changes: Partial<typeof body> = {};
		if (Date.parse(body.startsAt) !== Date.parse(before.startsAt)) changes.startsAt = body.startsAt;
		if (body.durationMin !== before.durationMin) changes.durationMin = body.durationMin;
		if (body.reason !== before.reason) changes.reason = body.reason;
		if (body.serviceId !== (before.serviceId ?? null)) changes.serviceId = body.serviceId;
		if (body.practitionerId !== (before.practitionerId ?? null)) changes.practitionerId = body.practitionerId;
		if (body.notes !== before.notes) changes.notes = body.notes;
		if (body.depositRequiredMillimes !== before.depositRequiredMillimes) changes.depositRequiredMillimes = body.depositRequiredMillimes;
		if (body.patientId !== before.patient.id) changes.patientId = body.patientId;
		return changes;
	}

	/** Checks before any request; false (with the message shown) when something is missing. */
	function ready(): boolean {
		error = '';
		conflict = null;
		if (!patient && !creating) {
			error = t('agenda.form.pickPatient');
			return false;
		}
		return true;
	}

	function failed(err: unknown) {
		if (err instanceof ApiError && err.status === 409 && err.body && typeof err.body === 'object') conflict = err.body as ConflictProblem;
		else error = errorText(err);
	}

	async function save(at?: string) {
		if (at) {
			day = tunisDayOf(at);
			time = hhmm(minutesOfDay(at));
		}
		if (!ready()) return;
		const depositMillimes = deposit.trim() ? parseDinars(deposit) : 0;
		if (depositMillimes === null) {
			error = t('agenda.form.invalidAmount');
			return;
		}
		busy = true;
		try {
			const body = { ...common((await ensurePatient()).id), depositRequiredMillimes: depositMillimes };
			if (current) {
				const changes = changedFields(current, body);
				const saved = Object.keys(changes).length
					? await api<AppointmentSaved>(`/api/appointments/${current.id}`, { method: 'PATCH', json: changes })
					: current;
				onsaved(savedAppointment(saved));
			} else onsaved(savedAppointment(await api<AppointmentSaved>('/api/appointments', { method: 'POST', json: body })));
		} catch (err) {
			failed(err);
		} finally {
			busy = false;
		}
	}

	async function previewSeries() {
		if (!ready()) return;
		busy = true;
		try {
			const body = { ...common((await ensurePatient()).id), rule: { weekdays, count: Number(count) } };
			const result = await api<{ occurrences: SeriesOccurrence[] }>('/api/appointments/series/preview', { method: 'POST', json: body });
			occurrences = result.occurrences;
		} catch (err) {
			failed(err);
		} finally {
			busy = false;
		}
		if (!occurrences) return;
		await tick();
		seriesList?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' });
	}

	async function createSeries() {
		if (!ready() || !patient) return;
		busy = true;
		try {
			const body = { ...common(patient.id), rule: { weekdays, count: Number(count) }, skipConflicts: blocked > 0 };
			const result = await api<SeriesCreated>('/api/appointments/series', { method: 'POST', json: body });
			const note = [t('agenda.series.created', { count: result.created.length })];
			if (result.skipped.length) note.push(t('agenda.series.skipped', { count: result.skipped.length }));
			if (result.created[0]) onsaved(result.created[0], note.join(' '));
			else onclose();
		} catch (err) {
			failed(err);
		} finally {
			busy = false;
		}
	}

	const submitLabel = $derived.by(() => {
		if (busy) return repeat && !occurrences ? t('agenda.series.previewing') : t('agenda.form.saving');
		if (!repeat) return t('agenda.form.save');
		if (!occurrences) return t('agenda.series.preview');
		return blocked ? t('agenda.series.createSkipping', { count: occurrences.length - blocked }) : t('agenda.series.create', { count: occurrences.length });
	});

	function submit(e: SubmitEvent) {
		e.preventDefault();
		if (!repeat) void save();
		else if (occurrences) void createSeries();
		else void previewSeries();
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
						{#if doctors.length !== 1}
							<option value="">{doctors.length ? t('agenda.form.firstFree') : t('agenda.form.anyPractitioner')}</option>
						{/if}
						{#each doctors as p (p.id)}<option value={String(p.id)}>{practitionerLabel(p)}</option>{/each}
						{#if current?.practitionerId && !doctors.some((p) => p.id === current?.practitionerId)}
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
			{#if !editing}
				<label class="inline-flex min-h-11 items-center gap-3 font-medium"
					><input type="checkbox" bind:checked={repeat} class="h-5 w-5 accent-brand-700" /><Icon name="repeat" class="h-4 w-4 text-slate-500" />{t(
						'agenda.form.repeat'
					)}</label
				>
			{/if}
		</fieldset>
		{#if repeat}
			<fieldset class="flex flex-col gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 md:col-span-2">
				<legend class="px-1 text-sm font-semibold text-slate-600">{t('agenda.series.title')}</legend>
				<div class="flex flex-wrap items-end gap-4">
					<div class="flex flex-col gap-1">
						<span class="text-sm font-medium text-slate-700">{t('agenda.series.weekdays')}</span>
						<div class="flex flex-wrap gap-1.5">
							{#each [1, 2, 3, 4, 5, 6, 7] as d (d)}
								<button
									type="button"
									class="min-h-11 min-w-12 rounded-lg border px-2 text-sm font-semibold first-letter:uppercase {weekdays.includes(d)
										? 'border-brand-700 bg-brand-700 text-white'
										: 'border-slate-300 bg-white text-slate-700'}"
									aria-pressed={weekdays.includes(d)}
									aria-label={weekdayName(d, 'long')}
									onclick={() => toggleWeekday(d)}>{weekdayName(d, 'short')}</button
								>
							{/each}
						</div>
					</div>
					<label class="label w-36">{t('agenda.series.count')}<input class="input" type="number" min="1" max="52" bind:value={count} /></label>
				</div>
				{#if occurrences}
					<p class="text-sm font-semibold {blocked ? 'text-amber-900' : 'text-emerald-800'}">
						{blocked ? t('agenda.series.someBlocked', { count: blocked }) : t('agenda.series.allFree')}
					</p>
					<ul bind:this={seriesList} aria-label={t('agenda.series.title')} class="grid gap-1.5 sm:grid-cols-2">
						{#each occurrences as o (o.startsAt)}
							<li
								class="flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm {o.conflict || o.closed
									? 'bg-rose-50 text-rose-900 ring-1 ring-rose-200'
									: 'bg-white ring-1 ring-slate-200'}"
							>
								<span class="font-medium first-letter:uppercase">{slotLabel(o.startsAt)}</span>
								<span class="font-semibold"
									>{o.closed ? t('agenda.series.closed') : o.conflict ? t('agenda.series.conflict', { patient: o.conflict.patientName }) : t('agenda.series.ok')}</span
								>
							</li>
						{/each}
					</ul>
				{/if}
			</fieldset>
		{/if}
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
		<button
			type="submit"
			form="appointment-form"
			class="btn-primary"
			disabled={busy || (repeat && (!weekdays.length || (!!occurrences && occurrences.length === blocked)))}>{submitLabel}</button
		>
	{/snippet}
</Modal>
