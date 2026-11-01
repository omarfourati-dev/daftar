<script lang="ts">
	/**
	 * /app/etiquettes – the label print page (spec stock-hygiène 7): `?cycle=<id>` the sterilisation labels of a cycle
	 * (`&packs=1,2` some of them again), `?specimen=<id>` the tubes of a specimen print, `?test=1` a test page; `&format=`
	 * overrides the practice's format. The preview shows every label at its real size; printing goes through the
	 * browser like the receipt and the poster, with an `@page` of the chosen format (one label per page on rolls, the A4
	 * sheet of 3 × 8 from any start position). Everything else on the page disappears on paper.
	 */
	import { onMount } from 'svelte';
	import { api, ApiError } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { formatDate, t } from '#lib/i18n.svelte';
	import {
		FORMAT_SPECS,
		FORMATS,
		SHEET_SLOTS,
		isFormat,
		labelName,
		labelsError,
		nextStart,
		pageCss,
		printable,
		readStart,
		saveStart,
		sheets,
		specimenLabels,
		sterileLabels,
		type LabelData
	} from '#lib/labels';
	import type { Cycle, LabelFormat, LabelKind, LabelSettings, SpecimenPrint } from '#lib/types/labels';
	import Icon from '../../../lib/components/daily/Icon.svelte';
	import LoadState from '../../../lib/components/LoadState.svelte';
	import LabelView from '../../../lib/components/labels/LabelView.svelte';

	const params = new URLSearchParams(typeof location === 'undefined' ? '' : location.search);
	const cycleId = Number(params.get('cycle')) || null;
	const specimenId = Number(params.get('specimen')) || null;
	const wanted = params.get('format');
	const onlyPacks = (params.get('packs') ?? '')
		.split(',')
		.map(Number)
		.filter((n) => Number.isInteger(n) && n > 0);
	const kind: LabelKind | 'test' = cycleId ? 'sterile' : specimenId ? 'specimen' : 'test';
	const manager = $derived(auth.role === 'owner' || auth.role === 'assistant');
	const practiceName = $derived(auth.user?.practice?.name ?? '');

	let settings = $state<LabelSettings | null>(null);
	let cycle = $state<Cycle | null>(null);
	let specimen = $state<SpecimenPrint | null>(null);
	let format = $state<LabelFormat>(isFormat(wanted) ? wanted : 'roll62');
	let start = $state(readStart());
	let chosen = $state<number[]>([]);
	let choosing = $state(false);
	let loading = $state(true);
	let error = $state('');
	let notice = $state('');
	let saving = $state(false);
	/** The test page of the chosen format (also opened from a cycle or a specimen print, and back). */
	let testing = $state(kind === 'test');

	async function load() {
		loading = true;
		error = '';
		try {
			settings = await api<LabelSettings>('/api/labels/settings');
			if (!isFormat(wanted)) format = settings.formats[kind === 'test' ? 'sterile' : kind];
			if (cycleId) {
				cycle = await api<Cycle>(`/api/hygiene/cycles/${cycleId}`);
				chosen = cycle.packs.filter((p) => (onlyPacks.length ? onlyPacks.includes(p.id) : printable(p))).map((p) => p.id);
			}
			if (specimenId) specimen = await api<SpecimenPrint>(`/api/labels/specimens/${specimenId}`);
		} catch (err) {
			error = err instanceof ApiError && err.status === 404 ? t('labels.print.notFound') : labelsError(err);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		void load();
		document.documentElement.classList.add('label-printing');
		return () => document.documentElement.classList.remove('label-printing');
	});

	const labels = $derived.by((): LabelData[] => {
		if (testing) return testLabels();
		if (cycle) return sterileLabels(cycle, cycle.packs.filter((p) => chosen.includes(p.id)), practiceName);
		if (specimen) return specimenLabels(specimen, practiceName);
		return [];
	});
	const sheet = $derived(format === 'a4_3x8');
	const sheetStart = $derived(testing ? 1 : start);
	const pages = $derived(sheet ? sheets(labels, sheetStart) : labels.map((l) => [l]));
	const spec = $derived(FORMAT_SPECS[format]);
	const css = $derived(pageCss(format));
	const title = $derived(
		testing ? t('labels.print.titleTest') : kind === 'sterile' ? t('labels.print.titleSterile') : t('labels.print.titleSpecimen')
	);
	const back = $derived(kind === 'specimen' && specimen ? `/app/patients/${specimen.patient.id}` : '/app/hygiene?tab=sterilisation');

	function print() {
		notice = '';
		window.print();
		if (sheet && !testing) {
			start = nextStart(start, labels.length);
			saveStart(start);
			notice = t('labels.print.nextStart', { n: start });
		}
	}

	function pick(position: number) {
		start = position;
		saveStart(position);
	}

	async function makeDefault() {
		if (!settings || kind === 'test') return;
		saving = true;
		try {
			settings = await api<LabelSettings>('/api/labels/settings', { method: 'PATCH', json: { formats: { [kind]: format } } });
			notice = t('labels.print.defaultSaved');
		} catch (err) {
			error = labelsError(err);
		} finally {
			saving = false;
		}
	}

	function testLabels(): LabelData[] {
		const count = format === 'a4_3x8' ? SHEET_SLOTS : 1;
		return Array.from({ length: count }, (_, i) => ({ kind: 'test', code: 'DAFTAR-TEST', position: i + 1 }));
	}

	function showTest(on: boolean) {
		testing = on;
		notice = '';
	}

	function toggle(id: number) {
		chosen = chosen.includes(id) ? chosen.filter((x) => x !== id) : [...chosen, id];
	}
</script>

<svelte:head>
	<title>{title} · Daftar</title>
	<!-- eslint-disable-next-line svelte/no-at-html-tags -- our own constant CSS: the paper size of the chosen format -->
	{@html `<style data-label-page>${css}</style>`}
</svelte:head>

<div class="flex flex-col gap-5 print:hidden">
	<a class="inline-flex min-h-11 items-center gap-1 self-start text-sm font-semibold text-brand-800 hover:underline" href={back}
		><Icon name="start" class="h-4 w-4" />{t('labels.print.back')}</a
	>
	<header class="flex flex-col gap-1">
		<h1 class="text-2xl font-bold">{title}</h1>
		{#if cycle}
			<p class="text-slate-600">
				{t('labels.print.cycle', { autoclave: `${cycle.equipmentName} (${cycle.labelCode})`, number: cycle.number, date: formatDate(cycle.runAt) })}
			</p>
		{:else if specimen}
			<p class="text-slate-600">
				{t('labels.print.specimenFor', { patient: labelName(specimen.patient.firstName, specimen.patient.lastName), count: specimen.labelCount })}
			</p>
		{/if}
		{#if testing}<p class="max-w-2xl text-slate-600">{t('labels.print.testIntro')}</p>{/if}
	</header>

	<LoadState {loading} {error} onretry={load} />

	{#if !loading && !error}
		{#if cycle && cycle.result !== 'ok' && !testing}
			<p role="alert" class="flex gap-2 rounded-xl border border-rose-300 bg-rose-50 px-4 py-3 font-semibold text-rose-900">
				<Icon name="alert" class="mt-0.5 h-5 w-5" />{t('labels.print.notOk')}
			</p>
		{/if}

		<div class="grid items-start gap-6 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
			<section aria-labelledby="print-settings" class="flex flex-col gap-4">
				<h2 id="print-settings" class="sr-only">{t('labels.print.settings')}</h2>
				<fieldset class="flex flex-col gap-2">
					<legend class="mb-1 text-sm font-semibold text-slate-700">{t('labels.print.format')}</legend>
					{#each FORMATS as f (f)}
						<label
							class="flex min-h-14 cursor-pointer items-center gap-3 rounded-xl border bg-white px-3 py-2 {format === f
								? 'border-brand-700 ring-2 ring-brand-700/30'
								: 'border-slate-300 hover:border-slate-400'}"
						>
							<input type="radio" name="format" value={f} bind:group={format} class="h-5 w-5 accent-brand-700" />
							<span class="flex min-w-0 flex-col">
								<span class="font-semibold">{t(`labels.formats.${f}`)}</span>
								<span class="text-sm text-slate-600">{t(`labels.formatHints.${f}`)}</span>
							</span>
						</label>
					{/each}
					{#if manager && settings && kind !== 'test' && settings.formats[kind] !== format}
						<button type="button" class="btn-secondary self-start text-sm" disabled={saving} onclick={makeDefault}>{t('labels.print.makeDefault')}</button>
					{/if}
				</fieldset>

				{#if sheet && !testing}
					<fieldset class="flex flex-col gap-2">
						<legend class="text-sm font-semibold text-slate-700">{t('labels.print.start')}</legend>
						<p class="text-sm text-slate-600">{t('labels.print.startHint')}</p>
						<div class="sheet-map" role="group" aria-label={t('labels.print.sheetMap')}>
							{#each Array.from({ length: SHEET_SLOTS }, (_, i) => i + 1) as n (n)}
								{@const used = n < start}
								{@const filled = n >= start && n < start + labels.length}
								<button
									type="button"
									class="slot {used ? 'used' : filled ? 'filled' : ''}"
									aria-pressed={n === start}
									aria-label={t('labels.print.startAt', { n })}
									onclick={() => pick(n)}><span aria-hidden="true">{n}</span></button
								>
							{/each}
						</div>
						<p class="text-sm text-slate-600">
							{t('labels.print.sheetCount', { count: pages.length })}
						</p>
					</fieldset>
				{/if}

				{#if cycle && cycle.packs.length && !testing}
					<div class="flex flex-col gap-2">
						<button type="button" class="btn-secondary self-start text-sm" aria-expanded={choosing} onclick={() => (choosing = !choosing)}
							>{t('labels.print.choose', { count: chosen.length, total: cycle.packs.length })}</button
						>
						{#if choosing}
							<fieldset class="flex flex-col gap-1 rounded-xl bg-white p-3 ring-1 ring-slate-200">
								<legend class="sr-only">{t('labels.print.chooseTitle')}</legend>
								{#each cycle.packs as p (p.id)}
									<label class="flex min-h-11 items-center gap-3 text-sm">
										<input type="checkbox" class="h-5 w-5 accent-brand-700" checked={chosen.includes(p.id)} onchange={() => toggle(p.id)} />
										<span class="font-semibold tabular-nums" dir="ltr">{p.code}</span>
										<span class="min-w-0 flex-1 truncate" dir="auto">{p.content}</span>
										{#if p.state !== 'usable'}<span class="rounded-full bg-slate-100 px-2 text-xs font-semibold text-slate-700">{t(`labels.states.${p.state}`)}</span>{/if}
									</label>
								{/each}
							</fieldset>
						{/if}
					</div>
				{/if}

				<div class="flex flex-wrap gap-2">
					{#if testing}
						<button type="button" class="btn-primary" onclick={print}><Icon name="print" />{t('labels.print.printTestNow')}</button>
						{#if kind !== 'test'}<button type="button" class="btn-secondary" onclick={() => showTest(false)}>{t('labels.print.backToLabels')}</button>{/if}
					{:else}
						<button type="button" class="btn-primary" disabled={!labels.length} onclick={print}
							><Icon name="print" />{t('labels.print.print', { count: labels.length })}</button
						>
						<button type="button" class="btn-secondary" onclick={() => showTest(true)}>{t('labels.print.printTest')}</button>
					{/if}
				</div>
				{#if notice}<p role="status" class="rounded-lg bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-900 ring-1 ring-emerald-200">{notice}</p>{/if}

				<details class="rounded-xl bg-white p-3 text-sm ring-1 ring-slate-200">
					<summary class="min-h-8 cursor-pointer font-semibold">{t('labels.print.tipsTitle')}</summary>
					<p class="mt-2 text-slate-700">{t(`labels.print.tips.${format}`)}</p>
					<p class="mt-2 text-slate-700">{t('labels.print.tipsCommon')}</p>
				</details>
			</section>

			<section aria-labelledby="preview-title" class="flex min-w-0 flex-col gap-2">
				<h2 id="preview-title" class="text-sm font-semibold text-slate-700">
					{t('labels.print.preview')}
				</h2>
				{#if labels.length}
					<ol class="liner {sheet ? 'sheet-liner' : format}" aria-label={t('labels.print.previewLabel')}>
						{#each labels as label, i (`${label.code}-${i}`)}
							<li class="die"><LabelView {label} {format} /></li>
						{/each}
					</ol>
				{:else}
					<p class="card text-slate-600">{t('labels.print.none')}</p>
				{/if}
			</section>
		</div>
	{/if}
</div>

<!-- What goes to the printer: laid out (invisible) off screen, so the text is fitted before printing. -->
<div class="print-area" aria-hidden="true" data-format={format}>
	{#each pages as page, p (p)}
		<div class="paper" style="width:{spec.page[0]}mm;height:{spec.page[1]}mm">
			{#if sheet && spec.sheet}
				<div class="sheet" style="padding-top:{spec.sheet.top}mm;grid-template-columns:repeat({spec.sheet.cols},{spec.label[0]}mm);grid-template-rows:repeat({spec.sheet.rows},{spec.label[1]}mm)">
					{#each page as slot, s (s)}
						<div class="slot-paper">{#if slot}<LabelView label={slot} {format} />{/if}</div>
					{/each}
				</div>
			{:else if page[0]}
				<LabelView label={page[0]} {format} />
			{/if}
		</div>
	{/each}
</div>

<style>
	.liner {
		display: flex;
		flex-wrap: wrap;
		gap: 3mm;
		align-self: flex-start;
		max-width: 100%;
		margin: 0;
		padding: 3mm;
		list-style: none;
		border-radius: 3mm;
		/* the backing paper of a label roll */
		background: #e7ecef;
		box-shadow: inset 0 0 0 1px rgb(15 23 42 / 0.08);
	}
	.liner.roll62 {
		flex-direction: column;
		gap: 0;
	}
	.liner.roll62 .die + .die {
		border-top: 1px dashed #64748b;
	}
	.liner.label57x32 {
		flex-direction: column;
	}
	.die {
		display: block;
		overflow: hidden;
		border-radius: 1.2mm;
		box-shadow:
			0 0 0 1px rgb(15 23 42 / 0.12),
			0 1px 2px rgb(15 23 42 / 0.1);
	}
	.liner.roll62 .die {
		border-radius: 0;
		box-shadow: none;
	}
	.sheet-liner {
		background: #f1f5f9;
	}
	.sheet-map {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 3px;
		width: 11rem;
		padding: 6px;
		aspect-ratio: 210 / 297;
		background: #fff;
		border-radius: 4px;
		box-shadow:
			0 0 0 1px rgb(15 23 42 / 0.15),
			0 2px 6px rgb(15 23 42 / 0.08);
	}
	.slot {
		display: grid;
		min-height: 24px;
		place-items: center;
		border-radius: 3px;
		background: #f8fafc;
		box-shadow: inset 0 0 0 1px #cbd5e1;
		color: #475569;
		font-size: 0.7rem;
		font-weight: 600;
		font-variant-numeric: tabular-nums;
	}
	.slot.used {
		background: repeating-linear-gradient(135deg, #e2e8f0 0 3px, #f8fafc 3px 6px);
		color: #64748b;
	}
	.slot.filled {
		background: var(--color-brand-700);
		box-shadow: none;
		color: #fff;
	}
	.slot[aria-pressed='true'] {
		outline: 2px solid var(--color-accent-500);
		outline-offset: 1px;
	}
	.slot:focus-visible {
		outline: 2px solid var(--color-brand-700);
		outline-offset: 2px;
	}
	.print-area {
		position: fixed;
		top: 0;
		left: -10000px;
		visibility: hidden;
		pointer-events: none;
	}
	.paper {
		overflow: hidden;
		break-inside: avoid;
	}
	.sheet {
		display: grid;
		box-sizing: border-box;
		height: 100%;
	}
	.slot-paper {
		overflow: hidden;
	}

	@media print {
		.print-area {
			position: static;
			left: auto;
			visibility: visible;
		}
		.paper {
			page: daftar-label;
			break-after: page;
		}
		.paper:last-child {
			break-after: auto;
		}
		:global(html.label-printing),
		:global(html.label-printing body) {
			margin: 0 !important;
			padding: 0 !important;
			background: #fff !important;
		}
		:global(html.label-printing main) {
			margin: 0 !important;
			padding: 0 !important;
			max-width: none !important;
		}
		:global(html.label-printing .min-h-screen) {
			min-height: 0 !important;
		}
	}
</style>
