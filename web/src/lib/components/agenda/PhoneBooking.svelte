<script lang="ts">
	/**
	 * "Rendez-vous par téléphone" (section 16.1, key T): the number first – known patients with this number appear
	 * (families share numbers), otherwise a new patient – then the service, and at once the next free times over the
	 * coming days (`GET /api/availability/next`). One click books; then a confirmation text to copy or send.
	 */
	import { onMount } from 'svelte';
	import { ApiError, api } from '../../api';
	import { loadAgendaBase, savedAppointment, type AgendaBase } from '../../agenda/data';
	import { errorText } from '../../agenda/errors';
	import { personName, practitionerLabel, serviceLabel, shortDay, slotLabel } from '../../agenda/format';
	import { displayPhone, phoneDigits, smsUrl, whatsappUrl } from '../../agenda/links';
	import { appointmentMessage } from '../../agenda/messages';
	import { hhmm, minutesOfDay, tunisDayOf } from '../../agenda/time';
	import { clock } from '../../clock';
	import { addDays, i18n, t, todayTunis } from '../../i18n.svelte';
	import type { Appointment, AppointmentSaved } from '../../types/agenda';
	import type { Patient, PatientPage, PatientSummary } from '../../types/patients';
	import Icon from '../daily/Icon.svelte';
	import Modal from '../daily/Modal.svelte';

	type Props = { onbooked: (a: Appointment) => void; onclose: () => void };
	let { onbooked, onclose }: Props = $props();

	type Free = { startsAt: string; practitionerId: number | null };

	let base = $state<AgendaBase | null>(null);
	let number = $state('');
	let matches = $state<PatientSummary[]>([]);
	let searched = $state(false);
	let patient = $state<PatientSummary | null>(null);
	let creating = $state(false);
	let firstName = $state('');
	let lastName = $state('');
	let lang = $state<string>(i18n.locale);
	let consent = $state(false);
	let serviceKey = $state('');
	let practitionerKey = $state('');
	let free = $state<Free[] | null>(null);
	let error = $state('');
	let busy = $state(false);
	let booked = $state<Appointment | null>(null);
	let copied = $state(false);
	let timer: ReturnType<typeof setTimeout> | undefined;
	let seq = 0;

	onMount(async () => {
		base = await loadAgendaBase().catch(() => null);
	});

	const services = $derived((base?.services ?? []).filter((s) => s.active !== false));
	const service = $derived(services.find((s) => String(s.id) === serviceKey) ?? null);
	const ready = $derived(!!patient || creating);

	function numberChanged() {
		clearTimeout(timer);
		patient = null;
		creating = false;
		const digits = phoneDigits(number);
		if (digits.length < 4) {
			matches = [];
			searched = false;
			return;
		}
		timer = setTimeout(async () => {
			const page = await api<PatientPage>(`/api/patients?q=${digits}&limit=8`).catch(() => ({ items: [], total: 0 }));
			if (phoneDigits(number) !== digits) return;
			matches = page.items;
			searched = true;
		}, 200);
	}

	async function loadFree() {
		const mine = ++seq;
		const params = new URLSearchParams();
		if (serviceKey) params.set('serviceId', serviceKey);
		if (practitionerKey) params.set('practitionerId', practitionerKey);
		if (patient) params.set('patientId', String(patient.id));
		params.set('limit', '8');
		try {
			const list = await api<Free[]>(`/api/availability/next?${params}`);
			if (mine === seq) free = list;
		} catch (err) {
			if (mine === seq) error = errorText(err);
		}
	}

	$effect(() => {
		void [serviceKey, practitionerKey, patient?.id];
		if (!ready) {
			free = null;
			return;
		}
		void loadFree();
	});

	const groups = $derived.by(() => {
		const today = todayTunis(clock.now());
		const out: { day: string; label: string; items: Free[] }[] = [];
		for (const f of free ?? []) {
			const day = tunisDayOf(f.startsAt);
			let g = out.find((x) => x.day === day);
			if (!g) {
				const label = day === today ? t('agenda.phone.today') : day === addDays(today, 1) ? t('agenda.phone.tomorrow') : shortDay(day);
				out.push((g = { day, label, items: [] }));
			}
			g.items.push(f);
		}
		return out;
	});

	function who(id: number | null): string {
		const p = base?.practitioners.find((x) => x.id === id);
		return p ? practitionerLabel(p) : '';
	}

	async function book(slot: Free) {
		error = '';
		busy = true;
		try {
			let chosen = patient;
			if (!chosen) {
				chosen = await api<Patient>('/api/patients', {
					method: 'POST',
					json: { firstName: firstName.trim(), lastName: lastName.trim(), phone: number.trim(), lang, reminderConsent: consent }
				});
				patient = chosen;
				creating = false;
			}
			const saved = await api<AppointmentSaved>('/api/appointments', {
				method: 'POST',
				json: {
					patientId: chosen.id,
					startsAt: slot.startsAt,
					reason: service ? serviceLabel(service) : '',
					serviceId: service?.id ?? null,
					practitionerId: slot.practitionerId,
					notes: '',
					depositRequiredMillimes: 0
				}
			});
			booked = savedAppointment(saved);
			onbooked(booked);
		} catch (err) {
			if (err instanceof ApiError && err.status === 409) {
				error = t('agenda.phone.takenMeanwhile');
				void loadFree();
			} else error = errorText(err);
		} finally {
			busy = false;
		}
	}

	const confirmation = $derived(
		booked && base ? appointmentMessage({ startsAt: booked.startsAt, patient: { firstName: patient?.firstName ?? booked.patient.firstName, lang: patient?.lang } }, 'confirmed', base.practice) : ''
	);
	const phoneOfPatient = $derived(patient?.phone ?? booked?.patient.phone ?? '');

	async function copy() {
		try {
			await navigator.clipboard.writeText(confirmation);
			copied = true;
		} catch {
			copied = false;
		}
	}

	function another() {
		booked = null;
		number = '';
		matches = [];
		searched = false;
		patient = null;
		creating = false;
		firstName = '';
		lastName = '';
		free = null;
		copied = false;
	}
</script>

<Modal title={t('agenda.phone.title')} {onclose} wide>
	{#if booked}
		<div class="flex flex-col gap-4">
			<p role="status" class="rounded-xl bg-emerald-50 px-4 py-3 text-lg font-semibold text-emerald-900 ring-1 ring-emerald-200 first-letter:uppercase">
				{t('agenda.phone.booked', { when: `${slotLabel(booked.startsAt)}${booked.practitionerId ? ` – ${who(booked.practitionerId) || booked.practitionerName}` : ''}` })}
			</p>
			<label class="label">{t('agenda.phone.message')}<textarea class="input min-h-28" readonly value={confirmation}></textarea></label>
			<div class="flex flex-wrap items-center gap-2">
				<button type="button" class="btn-primary" onclick={copy}>{t('agenda.phone.copy')}</button>
				{#if phoneOfPatient}
					<a class="btn min-h-11 bg-[#25d366] text-ink hover:bg-[#1ebe5b]" href={whatsappUrl(phoneOfPatient, confirmation)} target="_blank" rel="noopener noreferrer"
						><Icon name="chat" />{t('agenda.phone.whatsapp')}</a
					>
					<a class="btn-secondary" href={smsUrl(phoneOfPatient, confirmation)}><Icon name="sms" />{t('agenda.phone.sms')}</a>
				{/if}
				{#if copied}<span class="text-sm font-medium text-emerald-800">{t('agenda.phone.copied')}</span>{/if}
			</div>
		</div>
	{:else}
		<div class="grid gap-5 md:grid-cols-2">
			<div class="flex min-w-0 flex-col gap-3">
				<label class="label"
					>{t('agenda.phone.number')}<input
						class="input min-h-12 text-lg tabular-nums"
						type="tel"
						inputmode="tel"
						dir="ltr"
						bind:value={number}
						oninput={numberChanged}
						autocomplete="off"
						aria-describedby="phone-number-hint"
						data-autofocus
					/></label
				>
				<p id="phone-number-hint" class="-mt-2 text-xs text-slate-500">{t('agenda.phone.numberHint')}</p>
				{#if patient}
					<div class="flex items-center gap-3 rounded-xl border border-brand-200 bg-brand-50 px-3 py-2.5">
						<div class="min-w-0 flex-1">
							<p class="font-semibold">{personName(patient)}</p>
							<p class="text-sm text-slate-600 tabular-nums" dir="ltr">{displayPhone(patient.phone)}</p>
						</div>
						<button type="button" class="btn-secondary min-h-10 px-3 text-sm" onclick={() => (patient = null)}>{t('agenda.form.changePatient')}</button>
					</div>
					{#if patient.noShows >= 2}<p class="rounded-lg bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900 ring-1 ring-amber-200">{t('agenda.form.noShowWarning', { count: patient.noShows })}</p>{/if}
				{:else if creating}
					<div class="grid grid-cols-2 gap-3">
						<label class="label">{t('agenda.form.firstName')}<input class="input" bind:value={firstName} autocomplete="off" /></label>
						<label class="label">{t('agenda.form.lastName')}<input class="input" bind:value={lastName} autocomplete="off" /></label>
					</div>
					<div class="flex flex-wrap items-center gap-4">
						<label class="inline-flex min-h-11 items-center gap-2"><input type="radio" bind:group={lang} value="fr" class="h-5 w-5 accent-brand-700" />{t('common.french')}</label>
						<label class="inline-flex min-h-11 items-center gap-2" lang="ar"><input type="radio" bind:group={lang} value="ar" class="h-5 w-5 accent-brand-700" />{t('common.arabic')}</label>
					</div>
					<label class="inline-flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" bind:checked={consent} class="h-5 w-5 accent-brand-700" />{t('agenda.form.consent')}</label>
				{:else if searched}
					{#if matches.length}
						<p class="text-sm font-semibold text-slate-600">{t('agenda.phone.samePhone')}</p>
						<ul class="flex flex-col divide-y divide-slate-100 overflow-hidden rounded-lg border border-slate-200">
							{#each matches as m (m.id)}
								<li>
									<button type="button" class="flex min-h-12 w-full flex-wrap items-center gap-x-3 px-3 py-2 text-start hover:bg-brand-50" onclick={() => (patient = m)}>
										<span class="font-semibold">{personName(m)}</span>
										<span class="text-sm text-slate-600 tabular-nums" dir="ltr">{displayPhone(m.phone)}</span>
									</button>
								</li>
							{/each}
						</ul>
					{/if}
					<button type="button" class="btn-secondary self-start" onclick={() => (creating = true)}><Icon name="plus" />{t('agenda.phone.newPatient')}</button>
				{/if}

				<div class="grid grid-cols-2 gap-3">
					<label class="label"
						>{t('agenda.phone.service')}
						<select class="input" bind:value={serviceKey}>
							<option value="">{t('agenda.form.noService')}</option>
							{#each services as s (s.id)}<option value={String(s.id)}>{serviceLabel(s)}</option>{/each}
						</select>
					</label>
					<label class="label"
						>{t('agenda.phone.practitioner')}
						<select class="input" bind:value={practitionerKey}>
							<option value="">{t('agenda.phone.anyPractitioner')}</option>
							{#each base?.practitioners ?? [] as p (p.id)}<option value={String(p.id)}>{practitionerLabel(p)}</option>{/each}
						</select>
					</label>
				</div>
			</div>

			<section aria-labelledby="phone-free-title" class="flex min-w-0 flex-col gap-2">
				<h2 id="phone-free-title" class="font-bold">{t('agenda.phone.free')}</h2>
				{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}
				{#if !ready}
					<p class="text-sm text-slate-500">{t('agenda.phone.numberHint')}</p>
				{:else if free === null}
					<p class="text-sm text-slate-600" aria-busy="true">{t('agenda.phone.loading')}</p>
				{:else if !free.length}
					<p class="text-sm text-slate-700">{t('agenda.phone.none')}</p>
				{:else}
					<p class="text-xs text-slate-500">{t('agenda.phone.freeHint')}</p>
					{#each groups as g (g.day)}
						<h3 class="mt-1 text-sm font-semibold text-slate-600 first-letter:uppercase">{g.label}</h3>
						<div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
							{#each g.items as f (f.startsAt + (f.practitionerId ?? ''))}
								<button
									type="button"
									class="btn-secondary min-h-12 justify-start border-brand-200 text-start"
									disabled={busy || (creating && (!firstName.trim() || !lastName.trim()))}
									onclick={() => book(f)}
									>{f.practitionerId ? t('agenda.phone.slot', { time: hhmm(minutesOfDay(f.startsAt)), practitioner: who(f.practitionerId) }) : hhmm(minutesOfDay(f.startsAt))}</button
								>
							{/each}
						</div>
					{/each}
				{/if}
			</section>
		</div>
	{/if}

	{#snippet footer()}
		{#if booked}
			<button type="button" class="btn-secondary" onclick={another}>{t('agenda.phone.another')}</button>
		{/if}
		<button type="button" class={booked ? 'btn-primary' : 'btn-secondary'} onclick={onclose}>{t('common.close')}</button>
	{/snippet}
</Modal>
