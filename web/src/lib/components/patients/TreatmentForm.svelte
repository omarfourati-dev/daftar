<script lang="ts">
	/** "Nouvel acte": label (suggested from the practice's catalog, which also proposes the price), tooth for dentists, price, date. */
	import { errorText } from '../../agenda/errors';
	import { onMount } from 'svelte';
	import { api } from '../../api';
	import { clock } from '../../clock';
	import { serviceLabel } from '../../agenda/format';
	import { millimesToInput, parseDinars } from '../../agenda/links';
	import { t, todayTunis } from '../../i18n.svelte';
	import type { Service } from '../../types/agenda';
	import Modal from '../daily/Modal.svelte';

	type Props = { patientId: number; showTooth: boolean; onsaved: () => void; onclose: () => void };
	let { patientId, showTooth, onsaved, onclose }: Props = $props();

	let services = $state<Service[]>([]);
	let label = $state('');
	let tooth = $state('');
	let price = $state('');
	let day = $state(todayTunis(clock.now()));
	let error = $state('');
	let busy = $state(false);

	onMount(async () => {
		services = (await api<Service[]>('/api/services').catch(() => [] as Service[])).filter((s) => s.active !== false);
	});

	function labelChanged() {
		const match = services.find((s) => serviceLabel(s) === label.trim());
		if (match?.priceMillimes && !price.trim()) price = millimesToInput(match.priceMillimes);
	}

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		if (!label.trim()) return void (error = t('patients.treatmentForm.needLabel'));
		const priceMillimes = parseDinars(price.trim() || '0');
		if (priceMillimes === null) return void (error = t('patients.treatmentForm.invalidPrice'));
		busy = true;
		try {
			await api(`/api/patients/${patientId}/treatments`, {
				method: 'POST',
				json: { label: label.trim(), priceMillimes, performedOn: day, ...(tooth.trim() ? { tooth: tooth.trim() } : {}) }
			});
			onsaved();
		} catch (err) {
			error = errorText(err);
		} finally {
			busy = false;
		}
	}
</script>

<Modal title={t('patients.treatmentForm.title')} {onclose} guard>
	<form id="treatment-form" class="flex flex-col gap-4" onsubmit={submit} novalidate>
		<label class="label"
			>{t('patients.treatmentForm.label')}<input
				class="input"
				list="treatment-catalog"
				bind:value={label}
				onchange={labelChanged}
				maxlength="200"
				autocomplete="off"
				aria-describedby="treatment-hint"
				data-autofocus
			/></label
		>
		<datalist id="treatment-catalog">{#each services as s (s.id)}<option value={serviceLabel(s)}></option>{/each}</datalist>
		<p id="treatment-hint" class="-mt-2 text-xs text-slate-500">{t('patients.treatmentForm.labelHint')}</p>
		<div class="grid gap-3 {showTooth ? 'grid-cols-3' : 'grid-cols-2'}">
			{#if showTooth}<label class="label">{t('patients.treatmentForm.tooth')}<input class="input" bind:value={tooth} maxlength="20" autocomplete="off" /></label>{/if}
			<label class="label">{t('patients.treatmentForm.price')}<input class="input" inputmode="decimal" bind:value={price} placeholder="0" /></label>
			<label class="label">{t('patients.treatmentForm.date')}<input class="input" type="date" bind:value={day} /></label>
		</div>
		{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}
	</form>
	{#snippet footer()}
		<button type="button" class="btn-secondary" onclick={onclose}>{t('common.cancel')}</button>
		<button type="submit" form="treatment-form" class="btn-primary" disabled={busy}>{t('patients.treatmentForm.save')}</button>
	{/snippet}
</Modal>
