<script lang="ts">
	/**
	 * Traceability for the owner (spec stock-hygiène 5.3): "who got pack X?" – the code from the label – and "which packs
	 * did patient Y get?" – the patient by name or phone. Each answer names the cycle (autoclave, number, date, result),
	 * so a recall after a "non conforme" cycle finds every patient.
	 */
	import { api, ApiError } from '../../api';
	import { formatDate, formatDay, formatDateTime, t } from '../../i18n.svelte';
	import { labelsError, patientOfUse } from '../../labels';
	import type { PackTrace, PackUse, PatientTrace } from '../../types/labels';
	import type { PatientSummary } from '../../types/patients';
	import Icon from '../daily/Icon.svelte';
	import PatientSearch from '../daily/PatientSearch.svelte';
	import StateChip from './StateChip.svelte';

	let mode = $state<'pack' | 'patient'>('pack');
	let code = $state('');
	let query = $state('');
	let packResult = $state<PackTrace | null>(null);
	let patientResult = $state<PatientTrace | null>(null);
	let error = $state('');
	let busy = $state(false);

	function show(next: 'pack' | 'patient') {
		mode = next;
		error = '';
	}

	async function findPack(e: SubmitEvent) {
		e.preventDefault();
		if (!code.trim()) return;
		busy = true;
		error = '';
		packResult = null;
		try {
			packResult = await api<PackTrace>(`/api/hygiene/trace?code=${encodeURIComponent(code.trim())}`);
		} catch (err) {
			error = err instanceof ApiError && err.status === 404 ? t('labels.trace.noPack') : labelsError(err);
		} finally {
			busy = false;
		}
	}

	async function findPatient(p: PatientSummary) {
		busy = true;
		error = '';
		patientResult = null;
		try {
			patientResult = await api<PatientTrace>(`/api/hygiene/trace?patientId=${p.id}`);
		} catch (err) {
			error = labelsError(err);
		} finally {
			busy = false;
		}
	}

	const cycleText = (u: Pick<PackUse, 'cycle'>) =>
		t('labels.trace.cycle', { code: u.cycle.labelCode, number: u.cycle.number, date: formatDate(u.cycle.runAt) });
</script>

<section aria-labelledby="trace-title" class="card flex flex-col gap-4">
	<div>
		<h2 id="trace-title" class="text-lg font-bold">{t('labels.trace.title')}</h2>
		<p class="text-sm text-slate-600">{t('labels.trace.intro')}</p>
	</div>
	<div class="flex flex-wrap gap-2" role="group" aria-label={t('labels.trace.mode')}>
		<button type="button" class="seg" aria-pressed={mode === 'pack'} onclick={() => show('pack')}>{t('labels.trace.byPack')}</button>
		<button type="button" class="seg" aria-pressed={mode === 'patient'} onclick={() => show('patient')}>{t('labels.trace.byPatient')}</button>
	</div>

	{#if mode === 'pack'}
		<form class="flex flex-wrap items-end gap-2" onsubmit={findPack}>
			<label class="label min-w-0 flex-1"
				>{t('labels.trace.code')}<input
					class="input font-semibold tracking-wide uppercase tabular-nums"
					dir="ltr"
					bind:value={code}
					maxlength="40"
					autocomplete="off"
					placeholder="A1-0412-07"
				/></label
			>
			<button type="submit" class="btn-primary" disabled={busy}><Icon name="search" />{t('labels.trace.find')}</button>
		</form>
		{#if packResult}
			{@const pack = packResult.pack}
			<div class="flex flex-col gap-2 rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200" role="status">
				<p class="flex flex-wrap items-center gap-2">
					<span class="text-lg font-bold tabular-nums" dir="ltr">{pack.code}</span>
					<span dir="auto">{pack.content}</span>
					<StateChip state={pack.state} />
				</p>
				<p class="text-sm text-slate-700">
					{t('labels.trace.cycle', { code: pack.labelCode, number: pack.number, date: formatDate(pack.runAt) })}
					– {t('labels.trace.useBefore', { date: formatDay(pack.expiresOn) })}
				</p>
				{#if packResult.use}
					<p class="font-semibold">
						{t('labels.trace.usedFor')}
						{#if packResult.use.patientId !== null}
							<a class="text-brand-800 underline-offset-2 hover:underline" href="/app/patients/{packResult.use.patientId}">{packResult.use.patientName}</a>
						{:else}
							<span>{patientOfUse(packResult.use)}</span>
						{/if}
					</p>
					<p class="text-sm text-slate-700">{t('labels.trace.usedWhen', { date: formatDateTime(packResult.use.usedAt), by: packResult.use.usedBy })}</p>
				{:else}
					<p class="text-sm text-slate-700">{t('labels.trace.notUsed')}</p>
				{/if}
			</div>
		{/if}
	{:else}
		<PatientSearch onpick={findPatient} bind:query />
		{#if patientResult}
			<div class="flex flex-col gap-2" role="status">
				<p class="font-semibold">{t('labels.trace.packsOf', { patient: patientResult.patient.name, count: patientResult.uses.length })}</p>
				{#if patientResult.uses.length}
					<ul class="flex flex-col divide-y divide-slate-100 rounded-xl bg-slate-50 px-3 ring-1 ring-slate-200">
						{#each patientResult.uses as u (u.id)}
							<li class="flex flex-col gap-0.5 py-2 text-sm">
								<span class="flex flex-wrap items-center gap-2"
									><span class="font-bold tabular-nums" dir="ltr">{u.code}</span><span dir="auto">{u.content}</span>{#if u.cycle.result !== 'ok'}<StateChip state="not_sterile" />{/if}</span
								>
								<span class="text-slate-700">{cycleText(u)}</span>
								<span class="text-slate-600">{t('labels.trace.usedWhen', { date: formatDateTime(u.usedAt), by: u.usedBy })}</span>
							</li>
						{/each}
					</ul>
				{/if}
			</div>
		{/if}
	{/if}
	{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}
</section>

<style>
	.seg {
		min-height: 2.75rem;
		border-radius: 9999px;
		padding: 0 1rem;
		font-size: 0.875rem;
		font-weight: 600;
		background: #fff;
		color: #334155;
		box-shadow: inset 0 0 0 1px #cbd5e1;
	}
	.seg[aria-pressed='true'] {
		background: var(--color-brand-700);
		color: #fff;
		box-shadow: none;
	}
	.seg:focus-visible {
		outline: 2px solid var(--color-brand-700);
		outline-offset: 2px;
	}
</style>
