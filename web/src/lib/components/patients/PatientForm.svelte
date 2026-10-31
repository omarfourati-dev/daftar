<script lang="ts">
	/** New patient or edit of a file: identity, phone (families may share one), language, consent, medical alert, notes. */
	import { errorText } from '../../agenda/errors';
	import { untrack } from 'svelte';
	import { api } from '../../api';
	import { clock } from '../../clock';
	import { i18n, t } from '../../i18n.svelte';
	import type { Patient } from '../../types/patients';
	import Modal from '../daily/Modal.svelte';

	type Props = { patient?: Patient | null; onsaved: (p: Patient) => void; onclose: () => void };
	let { patient = null, onsaved, onclose }: Props = $props();

	const start = untrack(() => patient);
	let firstName = $state(start?.firstName ?? '');
	let lastName = $state(start?.lastName ?? '');
	let phone = $state(start?.phone ?? '');
	let birthYear = $state(start?.birthYear ? String(start.birthYear) : '');
	let lang = $state<string>(start?.lang ?? i18n.locale);
	let consent = $state(start?.reminderConsent ?? false);
	let alerts = $state(start?.alerts ?? '');
	let notes = $state(start?.notes ?? '');
	let error = $state('');
	let busy = $state(false);

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		const year = birthYear.trim() ? Number(birthYear) : null;
		if (year !== null && (!Number.isInteger(year) || year < 1900 || year > clock.now().getFullYear())) {
			error = t('patients.form.invalidYear');
			return;
		}
		const body = {
			firstName: firstName.trim(),
			lastName: lastName.trim(),
			phone: phone.trim(),
			birthYear: year,
			lang,
			reminderConsent: consent,
			notes: notes.trim(),
			alerts: alerts.trim()
		};
		busy = true;
		try {
			const saved = start
				? await api<Patient>(`/api/patients/${start.id}`, { method: 'PATCH', json: body })
				: await api<Patient>('/api/patients', { method: 'POST', json: body });
			onsaved(saved);
		} catch (err) {
			error = errorText(err);
		} finally {
			busy = false;
		}
	}
</script>

<Modal title={start ? t('patients.form.editTitle') : t('patients.form.newTitle')} {onclose} guard>
	<form id="patient-form" class="flex flex-col gap-4" onsubmit={submit} novalidate>
		<div class="grid gap-3 sm:grid-cols-2">
			<label class="label">{t('patients.form.firstName')}<input class="input" bind:value={firstName} maxlength="120" required autocomplete="off" data-autofocus /></label>
			<label class="label">{t('patients.form.lastName')}<input class="input" bind:value={lastName} maxlength="120" required autocomplete="off" /></label>
		</div>
		<div class="grid gap-3 sm:grid-cols-[2fr_1fr]">
			<label class="label"
				>{t('patients.form.phone')}<input class="input" type="tel" inputmode="tel" dir="ltr" bind:value={phone} required autocomplete="off" aria-describedby="phone-hint" /></label
			>
			<label class="label">{t('patients.form.birthYear')}<input class="input" inputmode="numeric" maxlength="4" bind:value={birthYear} autocomplete="off" /></label>
		</div>
		<p id="phone-hint" class="-mt-2 text-xs text-slate-500">{t('patients.form.phoneHint')}</p>
		<fieldset class="flex flex-wrap items-center gap-4">
			<legend class="sr-only">{t('patients.form.lang')}</legend>
			<span class="text-sm font-medium text-slate-700" aria-hidden="true">{t('patients.form.lang')}</span>
			<label class="inline-flex min-h-11 items-center gap-2"><input type="radio" bind:group={lang} value="fr" class="h-5 w-5 accent-brand-700" />{t('common.french')}</label>
			<label class="inline-flex min-h-11 items-center gap-2" lang="ar"><input type="radio" bind:group={lang} value="ar" class="h-5 w-5 accent-brand-700" />{t('common.arabic')}</label>
		</fieldset>
		<label class="inline-flex min-h-11 items-center gap-3 text-sm"
			><input type="checkbox" bind:checked={consent} class="h-5 w-5 accent-brand-700" />{t('patients.form.consent')}</label
		>
		<label class="label text-rose-900"
			>{t('patients.form.alerts')}<textarea class="input min-h-16 border-rose-200" bind:value={alerts} maxlength="500" aria-describedby="alerts-hint"></textarea></label
		>
		<p id="alerts-hint" class="-mt-2 text-xs text-slate-500">{t('patients.form.alertsHint')}</p>
		<label class="label">{t('patients.form.notes')}<textarea class="input min-h-20" bind:value={notes} maxlength="2000"></textarea></label>
		{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}
	</form>
	{#snippet footer()}
		<button type="button" class="btn-secondary" onclick={onclose}>{t('common.cancel')}</button>
		<button type="submit" form="patient-form" class="btn-primary" disabled={busy}>{t('patients.form.save')}</button>
	{/snippet}
</Modal>
