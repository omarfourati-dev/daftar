<script lang="ts">
	/**
	 * In the patient file: specimen labels (spec stock-hygiène 6) with the proof of the last prints and a reprint, and –
	 * for the owner – the sterile packs this patient got (traceability "which packs did patient Y get?").
	 */
	import { onMount } from 'svelte';
	import { api } from '../../api';
	import { auth } from '../../auth.svelte';
	import { formatDate, formatDateTime, formatTime, t } from '../../i18n.svelte';
	import { labelsError, specimenName } from '../../labels';
	import type { PackUse, SpecimenPrint } from '../../types/labels';
	import Icon from '../daily/Icon.svelte';
	import SpecimenForm from './SpecimenForm.svelte';

	type Props = { patientId: number; birthDate: string | null };
	let { patientId, birthDate }: Props = $props();

	const isOwner = auth.role === 'owner';
	let prints = $state<SpecimenPrint[] | null>(null);
	let packs = $state<PackUse[] | null>(null);
	let error = $state('');

	async function load() {
		error = '';
		try {
			const [p, u] = await Promise.all([
				api<SpecimenPrint[]>(`/api/labels/specimens?patientId=${patientId}`),
				isOwner ? api<PackUse[]>(`/api/hygiene/pack-uses?patientId=${patientId}`) : Promise.resolve(null)
			]);
			prints = p;
			packs = u;
		} catch (err) {
			error = labelsError(err);
		}
	}
	onMount(load);

	const tubes = (p: SpecimenPrint) => p.items.map((i) => `${i.count} × ${specimenName(i.kind, i.label)}`).join(', ');
</script>

<section aria-labelledby="specimen-title" class="card flex flex-col gap-3 p-5">
	<h2 id="specimen-title" class="font-bold">{t('labels.patient.specimens')}</h2>
	<SpecimenForm {patientId} {birthDate} />
	{#if error}
		<p role="alert" class="text-sm text-rose-900">{error} <button type="button" class="font-semibold underline" onclick={load}>{t('common.retry')}</button></p>
	{:else if prints === null}
		<p class="text-sm text-slate-500" aria-busy="true">{t('common.loading')}</p>
	{:else if prints.length}
		<ul class="flex flex-col divide-y divide-slate-100 text-sm" aria-label={t('labels.patient.printed')}>
			{#each prints as p (p.id)}
				<li class="flex flex-wrap items-center gap-x-2 gap-y-1 py-2">
					<span class="min-w-0 flex-1">
						<span class="block font-semibold">{tubes(p)}</span>
						<span class="block text-slate-600"
							>{t('labels.patient.printedBy', { date: `${formatDate(p.printedAt)} ${formatTime(p.printedAt)}`, by: p.printedBy })}</span
						>
					</span>
					<a class="btn-secondary min-h-10 px-3 text-sm" href="/app/etiquettes?specimen={p.id}"
						><Icon name="print" class="h-4 w-4" />{t('labels.patient.reprint')}<span class="sr-only"> – {tubes(p)}</span></a
					>
				</li>
			{/each}
		</ul>
	{:else}
		<p class="text-sm text-slate-600">{t('labels.patient.noPrints')}</p>
	{/if}
</section>

{#if isOwner && packs?.length}
	<section aria-labelledby="packs-title" class="card flex flex-col gap-3 p-5">
		<h2 id="packs-title" class="font-bold">{t('labels.patient.packs')}</h2>
		<ul class="flex flex-col divide-y divide-slate-100 text-sm">
			{#each packs as u (u.id)}
				<li class="flex flex-col py-2">
					<span class="flex flex-wrap gap-2"><span class="font-bold tabular-nums" dir="ltr">{u.code}</span><span dir="auto">{u.content}</span></span>
					<span class="text-slate-600">{t('labels.trace.usedWhen', { date: formatDateTime(u.usedAt), by: u.usedBy })}</span>
					{#if u.cycle.result !== 'ok'}<span class="font-semibold text-rose-800">{t('labels.patient.recalled')}</span>{/if}
				</li>
			{/each}
		</ul>
	</section>
{/if}
