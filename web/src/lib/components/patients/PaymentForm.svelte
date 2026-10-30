<script lang="ts">
	/**
	 * "Nouveau paiement": cash in instalments (the amount due is proposed), payment method, date (today unless changed),
	 * optionally the deposit of a coming appointment, a note. The page offers the receipt afterwards.
	 */
	import { untrack } from 'svelte';
	import { api, apiErrorMessage } from '../../api';
	import { clock } from '../../clock';
	import { shortDay } from '../../agenda/format';
	import { millimesToInput, parseDinars } from '../../agenda/links';
	import { PAYMENT_METHODS } from '../../agenda/payments';
	import { formatTime, t, todayTunis, translate, tunisInstant } from '../../i18n.svelte';
	import type { Appointment } from '../../types/agenda';
	import type { Payment } from '../../types/patients';
	import Modal from '../daily/Modal.svelte';

	type Props = { patientId: number; due: number; appointments: Appointment[]; onsaved: (p: Payment) => void; onclose: () => void };
	let { patientId, due, appointments, onsaved, onclose }: Props = $props();

	const today = todayTunis(clock.now());
	let amount = $state(untrack(() => millimesToInput(Math.max(due, 0))));
	let method = $state<string>('cash');
	let day = $state(today);
	let deposit = $state(false);
	let appointmentKey = $state('');
	let note = $state('');
	let error = $state('');
	let busy = $state(false);

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		const amountMillimes = parseDinars(amount);
		if (!amountMillimes) return void (error = t('patients.paymentForm.invalidAmount'));
		const body: Record<string, unknown> = { amountMillimes, method, note: note.trim() };
		// a payment of another day is dated at noon of that day (the exact time does not matter for the cash book)
		if (day && day !== today) body.paidAt = tunisInstant(day, '12:00');
		if (deposit && appointmentKey) {
			body.isDeposit = true;
			body.appointmentId = Number(appointmentKey);
		}
		busy = true;
		try {
			onsaved(await api<Payment>(`/api/patients/${patientId}/payments`, { method: 'POST', json: body }));
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			busy = false;
		}
	}
</script>

<Modal title={t('patients.paymentForm.title')} {onclose}>
	<form id="payment-form" class="flex flex-col gap-4" onsubmit={submit} novalidate>
		<div class="grid grid-cols-2 gap-3">
			<label class="label"
				>{t('patients.paymentForm.amount')}<input class="input text-lg font-semibold" inputmode="decimal" bind:value={amount} data-autofocus autocomplete="off" /></label
			>
			<label class="label"
				>{t('patients.paymentForm.method')}
				<select class="input" bind:value={method}>
					{#each PAYMENT_METHODS as m (m)}<option value={m}>{translate(`paymentMethod.${m}`)}</option>{/each}
				</select>
			</label>
		</div>
		<label class="label">{t('patients.paymentForm.date')}<input class="input" type="date" bind:value={day} max={today} /></label>
		{#if appointments.length}
			<label class="inline-flex min-h-11 items-center gap-3 text-sm"
				><input type="checkbox" bind:checked={deposit} class="h-5 w-5 accent-brand-700" />{t('patients.paymentForm.deposit')}</label
			>
			{#if deposit}
				<label class="label"
					>{t('patients.paymentForm.appointment')}
					<select class="input" bind:value={appointmentKey}>
						<option value=""></option>
						{#each appointments as a (a.id)}<option value={String(a.id)}>{shortDay(a.startsAt)} {formatTime(a.startsAt)} – {a.reason}</option>{/each}
					</select>
				</label>
			{/if}
		{/if}
		<label class="label">{t('patients.paymentForm.note')}<input class="input" bind:value={note} maxlength="500" autocomplete="off" /></label>
		{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}
	</form>
	{#snippet footer()}
		<button type="button" class="btn-secondary" onclick={onclose}>{t('common.cancel')}</button>
		<button type="submit" form="payment-form" class="btn-primary" disabled={busy}>{t('patients.paymentForm.save')}</button>
	{/snippet}
</Modal>
