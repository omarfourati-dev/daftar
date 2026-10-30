<script lang="ts">
	/**
	 * `/app/import` (section 14, story E5): 1 file (drag & drop) → 2 sheet and title row → 3 mapping of every Daftar
	 * field to a column of the file (suggestions pre-selected, required fields explained, options, saved templates)
	 * → 4 dry run with counters and the errors per row → 5 import (one transaction), report and template.
	 * Owner and assistant. Built for the desktop, still usable on a phone.
	 */
	import { onMount, tick } from 'svelte';
	import { api, apiBlob, ApiError, apiErrorMessage } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { saveBlob } from '#lib/download';
	import { columnLetter, DEFAULT_OPTIONS, FIELDS, mappingFor, missingRequired, sharedColumns, type MissingField } from '#lib/import-mapping';
	import { formatDateTime, formatMillimes, formatNumber, t, translate, type MessageKey } from '#lib/i18n.svelte';
	import type { ImportJob, ImportKind, ImportMapping, ImportOptions, ImportPreview, ImportResult, ImportTemplate } from '#lib/types/imports';

	const MAX_BYTES = 2 * 1024 * 1024;
	const EXTENSIONS = ['.xlsx', '.xls', '.csv', '.txt'];
	const STEPS = ['file', 'sheet', 'mapping', 'check', 'done'] as const;
	type Step = (typeof STEPS)[number];
	const allowed = ['owner', 'assistant'].includes(String(auth.user?.role));

	let step = $state<Step>('file');
	let kind = $state<ImportKind>('patients');
	let job = $state<ImportJob | null>(null);
	let fileError = $state('');
	let uploading = $state(false);
	let dragging = $state(false);
	let dropzone = $state<HTMLElement>();

	let sheet = $state('');
	let hasHeader = $state(true);
	let headerRow = $state(1);
	let sheetBusy = $state(false);
	let sheetError = $state('');

	let mapping = $state<ImportMapping>({});
	let options = $state<ImportOptions>({ ...DEFAULT_OPTIONS });
	let missing = $state<MissingField[]>([]);
	let templates = $state<ImportTemplate[]>([]);
	let templateId = $state('');
	let templateNotice = $state('');

	let preview = $state<ImportPreview | null>(null);
	let checking = $state(false);
	let checkError = $state('');
	let result = $state<ImportResult | null>(null);
	let committing = $state(false);
	let templateName = $state('');
	let templateSaved = $state('');
	let reportError = $state('');
	let heading = $state<HTMLHeadingElement>();

	onMount(async () => {
		if (!allowed) return;
		try {
			templates = await api<ImportTemplate[]>('/api/import-templates');
		} catch {
			templates = [];
		}
	});

	// drag & drop without making the zone itself an interactive element (the button inside is)
	$effect(() => {
		const zone = dropzone;
		if (!zone) return;
		const over = (e: DragEvent) => {
			e.preventDefault();
			dragging = true;
		};
		const leave = () => (dragging = false);
		const drop = (e: DragEvent) => {
			e.preventDefault();
			dragging = false;
			const file = e.dataTransfer?.files?.[0];
			if (file) void upload(file);
		};
		zone.addEventListener('dragover', over);
		zone.addEventListener('dragleave', leave);
		zone.addEventListener('drop', drop);
		return () => {
			zone.removeEventListener('dragover', over);
			zone.removeEventListener('dragleave', leave);
			zone.removeEventListener('drop', drop);
		};
	});

	async function go(next: Step) {
		step = next;
		await tick();
		heading?.focus();
	}

	function useJob(answer: ImportJob, keepMapping = false) {
		job = answer;
		sheet = answer.sheet;
		headerRow = typeof answer.headerRow === 'number' ? answer.headerRow : answer.headerRow ? 1 : 0;
		hasHeader = headerRow > 0;
		if (!keepMapping) mapping = mappingFor(kind, answer.suggestedMapping ?? {});
	}

	async function upload(file: File) {
		fileError = '';
		const name = file.name.toLowerCase();
		if (!EXTENSIONS.some((ext) => name.endsWith(ext))) {
			fileError = t('errors.unsupported_file');
			return;
		}
		if (file.size > MAX_BYTES) {
			fileError = t('errors.file_too_large');
			return;
		}
		uploading = true;
		try {
			const form = new FormData();
			form.append('file', file);
			useJob(await api<ImportJob>('/api/imports', { method: 'POST', body: form }));
			preview = null;
			result = null;
			await go('sheet');
		} catch (err) {
			fileError = apiErrorMessage(err);
		} finally {
			uploading = false;
		}
	}

	// sheet and title row: the server reads the file again (debounced, so typing a number sends one request)
	let sheetTimer: ReturnType<typeof setTimeout> | undefined;
	function sheetChanged() {
		if (!job) return;
		clearTimeout(sheetTimer);
		const id = job.id;
		sheetTimer = setTimeout(async () => {
			sheetBusy = true;
			sheetError = '';
			try {
				const row = hasHeader ? Math.min(20, Math.max(1, Math.round(headerRow) || 1)) : 0;
				useJob(await api<ImportJob>(`/api/imports/${id}/sheet`, { method: 'POST', json: { sheet, headerRow: row } }));
			} catch (err) {
				sheetError = apiErrorMessage(err);
			} finally {
				sheetBusy = false;
			}
		}, 400);
	}

	function chooseKind(next: ImportKind) {
		kind = next;
		if (job) mapping = mappingFor(kind, job.suggestedMapping ?? {});
		templateId = '';
	}

	const kindTemplates = $derived(templates.filter((tpl) => tpl.kind === kind));

	function applyTemplate() {
		const tpl = templates.find((x) => String(x.id) === templateId);
		if (!tpl) return;
		const width = job?.columns.length ?? 0;
		const fromTemplate = Object.fromEntries(Object.entries(tpl.mapping ?? {}).filter(([, i]) => typeof i === 'number' && i < width));
		mapping = mappingFor(kind, fromTemplate);
		options = { ...DEFAULT_OPTIONS, ...(tpl.options ?? {}) };
		templateNotice = t('importer.templateApplied', { name: tpl.name });
	}

	async function deleteTemplate() {
		const id = templateId;
		if (!id) return;
		try {
			await api(`/api/import-templates/${id}`, { method: 'DELETE' });
			templates = templates.filter((x) => String(x.id) !== id);
			templateId = '';
			templateNotice = t('importer.templateDeleted');
		} catch (err) {
			templateNotice = apiErrorMessage(err);
		}
	}

	function body() {
		const opts: ImportOptions = { ...options };
		if (kind === 'patients' || !opts.defaultDurationMin) delete opts.defaultDurationMin;
		return { kind, mapping: { ...mapping }, options: opts };
	}

	async function check() {
		missing = missingRequired(kind, mapping);
		if (missing.length || !job) return;
		checking = true;
		checkError = '';
		try {
			preview = await api<ImportPreview>(`/api/imports/${job.id}/preview`, { method: 'POST', json: body() });
			await go('check');
		} catch (err) {
			checkError = apiErrorMessage(err);
		} finally {
			checking = false;
		}
	}

	async function commit() {
		if (!job) return;
		committing = true;
		checkError = '';
		try {
			result = await api<ImportResult>(`/api/imports/${job.id}/commit`, { method: 'POST', json: body() });
			await go('done');
		} catch (err) {
			checkError = apiErrorMessage(err);
			if (err instanceof ApiError && err.code === 'import_conflict') preview = null;
		} finally {
			committing = false;
		}
	}

	async function downloadReport() {
		if (!job) return;
		reportError = '';
		try {
			saveBlob(await apiBlob(`/api/imports/${job.id}/report.csv`), `rapport-import-${job.filename.replace(/\.[^.]+$/, '')}.csv`);
		} catch (err) {
			reportError = apiErrorMessage(err);
		}
	}

	const csvCell = (v: unknown) => {
		let s = String(v ?? '');
		if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
		return /[;"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
	};
	function downloadErrors() {
		if (!preview) return;
		const lines = ['Ligne;Champ;Message;Valeur', ...preview.errors.map((e) => [e.row, fieldLabel(e.field), e.message, e.value].map(csvCell).join(';'))];
		saveBlob(new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' }), 'erreurs-import.csv');
	}

	async function saveTemplate(e: SubmitEvent) {
		e.preventDefault();
		templateSaved = '';
		if (!templateName.trim()) return;
		try {
			const saved = await api<ImportTemplate>('/api/import-templates', { method: 'POST', json: { name: templateName.trim(), ...body() } });
			templates = [...templates, saved];
			templateSaved = t('importer.templateSaved');
		} catch (err) {
			templateSaved = apiErrorMessage(err);
		}
	}

	function restart() {
		job = null;
		preview = null;
		result = null;
		templateName = '';
		templateSaved = '';
		void go('file');
	}

	const fieldLabel = (field: string) => translate(`importer.fields.${field.replace(/Millimes$/, '')}`) ?? field;
	/** normalised sample values: money in millimes, instants with offset */
	const sampleValue = (key: string, value: unknown) =>
		value === null || value === undefined
			? ''
			: key.endsWith('Millimes') && typeof value === 'number'
				? formatMillimes(value)
				: /^(startsAt|endsAt)$/.test(key) && typeof value === 'string'
					? formatDateTime(value)
					: String(value);
	const columnName = (index: number) => {
		const col = job?.columns.find((c) => c.index === index);
		return col?.header ? t('importer.columnOption', { letter: columnLetter(index), header: col.header }) : columnLetter(index);
	};
	const samplesOf = (index: number | null) =>
		index === null
			? ''
			: (job?.columns.find((c) => c.index === index)?.samples ?? [])
					.filter((s) => s !== '')
					.slice(0, 3)
					.join(', ');
	const NAME_FIELDS = ['lastName', 'firstName', 'fullName'];
	const WHEN_FIELDS = ['date', 'time', 'datetime'];
	const requiredNote = (field: string) =>
		NAME_FIELDS.includes(field)
			? t('importer.nameRule')
			: field === 'phone' && kind === 'patients'
				? t('importer.required')
				: kind === 'appointments' && WHEN_FIELDS.includes(field)
					? t('importer.whenRule')
					: '';
	const shared = $derived(sharedColumns(mapping));
	const usesFullName = $derived(typeof mapping.fullName === 'number');
	const usesDates = $derived(['birthDate', 'date', 'datetime'].some((f) => typeof mapping[f] === 'number'));
	const toImport = $derived(preview ? preview.willCreate + preview.willUpdate : 0);
	const sampleColumns = $derived(preview?.sample.length ? Object.keys(preview.sample[0]) : []);
	const stepIndex = $derived(STEPS.indexOf(step));
	const card = 'card flex flex-col gap-4';
</script>

<svelte:head><title>{t('importer.title')} · Daftar</title></svelte:head>

<div class="flex flex-col gap-6">
	<div class="flex max-w-3xl flex-col gap-2">
		<h1 class="text-2xl font-bold text-ink">{t('importer.title')}</h1>
		<p class="text-slate-700">{t('importer.intro')}</p>
	</div>

	{#if !allowed}
		<p class="card text-slate-700">{t('importer.forbidden')}</p>
	{:else}
		<ol aria-label={t('importer.stepsLabel')} class="flex flex-wrap gap-x-2 gap-y-1 text-sm">
			{#each STEPS as s, i (s)}
				<li
					aria-current={s === step ? 'step' : undefined}
					class="flex items-center gap-1.5 rounded-full px-3 py-1 font-medium {s === step
						? 'bg-brand-700 text-white'
						: i < stepIndex
							? 'bg-brand-50 text-brand-800'
							: 'bg-slate-100 text-slate-600'}"
				>
					<span class="tabular-nums">{i + 1}</span>{t(`importer.steps.${s}`)}
				</li>
			{/each}
		</ol>

		{#if step === 'file'}
			<section class={card} aria-labelledby="imp-file">
				<h2 id="imp-file" bind:this={heading} tabindex="-1" class="text-lg font-bold text-ink outline-none">{t('importer.steps.file')}</h2>
				<fieldset class="min-w-0">
					<legend class="mb-2 font-medium text-slate-800">{t('importer.kind')}</legend>
					<div class="grid gap-2 sm:grid-cols-2">
						{#each ['patients', 'appointments'] as const as k (k)}
							<label
								class="flex cursor-pointer items-start gap-3 rounded-xl border-[1.5px] bg-white p-4 has-checked:border-brand-700 has-checked:bg-brand-50 {kind ===
								k
									? 'border-brand-700'
									: 'border-slate-200'}"
							>
								<input type="radio" name="kind" class="mt-1 h-4 w-4 accent-brand-700" checked={kind === k} onchange={() => chooseKind(k)} />
								<span class="flex flex-col">
									<span class="font-semibold text-ink">{t(`importer.kinds.${k}`)}</span>
									<span class="text-sm text-slate-600">{t(`importer.kindsHint.${k}`)}</span>
								</span>
							</label>
						{/each}
					</div>
				</fieldset>
				<div
					bind:this={dropzone}
					class="flex flex-col items-center gap-3 rounded-2xl border-2 border-dashed px-4 py-10 text-center transition-colors {dragging
						? 'border-brand-700 bg-brand-50'
						: 'border-slate-300 bg-slate-50'}"
				>
					<svg viewBox="0 0 24 24" class="h-10 w-10 text-brand-700" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6"
						><path d="M7 3h7l5 5v13H7z M14 3v5h5 M10 13h6 M10 16h6" stroke-linejoin="round" /></svg
					>
					<p class="font-semibold text-ink">{t('importer.drop')}</p>
					<label class="btn-primary cursor-pointer">
						{uploading ? t('importer.uploading') : t('importer.browse')}
						<input
							type="file"
							class="sr-only"
							accept=".xlsx,.xls,.csv,.txt"
							aria-label={t('importer.browse')}
							disabled={uploading}
							onchange={(e) => {
								const file = e.currentTarget.files?.[0];
								e.currentTarget.value = '';
								if (file) void upload(file);
							}}
						/>
					</label>
					<p class="text-sm text-slate-600">{t('importer.formats')}</p>
				</div>
				{#if fileError}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 font-medium text-rose-900">{fileError}</p>{/if}
			</section>
		{:else if step === 'sheet' && job}
			<section class={card} aria-labelledby="imp-sheet">
				<h2 id="imp-sheet" bind:this={heading} tabindex="-1" class="text-lg font-bold text-ink outline-none">{t('importer.steps.sheet')}</h2>
				<p class="font-medium text-slate-800">{t('importer.fileInfo', { file: job.filename, rows: formatNumber(job.rowCount) })}</p>
				<div class="grid gap-4 sm:grid-cols-2">
					{#if job.sheets.length > 1}
						<label class="label">
							{t('importer.sheet')}
							<select class="input" bind:value={sheet} onchange={sheetChanged}>
								{#each job.sheets as name (name)}<option value={name}>{name}</option>{/each}
							</select>
						</label>
					{/if}
					<div class="flex flex-col gap-2">
						<label class="flex min-h-11 cursor-pointer items-center gap-3 font-medium text-slate-800">
							<input
								type="checkbox"
								class="h-5 w-5 accent-brand-700"
								bind:checked={hasHeader}
								onchange={() => {
									if (hasHeader && headerRow < 1) headerRow = 1;
									sheetChanged();
								}}
							/>
							{t('importer.headerRow')}
						</label>
						{#if hasHeader}
							<label class="label">
								{t('importer.headerRowNumber')}
								<input class="input w-24" type="number" min="1" max="20" dir="ltr" bind:value={headerRow} oninput={sheetChanged} aria-describedby="imp-header-hint" />
							</label>
							<p id="imp-header-hint" class="text-sm text-slate-600">{t('importer.headerHint')}</p>
						{/if}
					</div>
				</div>
				{#if sheetError}<p role="alert" class="font-medium text-red-700">{sheetError}</p>{/if}
				<div aria-busy={sheetBusy} class="overflow-x-auto rounded-xl border border-slate-200">
					<table class="w-full min-w-[32rem] text-start text-sm">
						<caption class="px-3 pt-3 text-start font-semibold text-ink">{t('importer.columnsFound')}</caption>
						<thead class="text-slate-600">
							<tr class="border-b border-slate-200">
								<th scope="col" class="px-3 py-2 text-start font-medium">{t('importer.fileColumn')}</th>
								<th scope="col" class="px-3 py-2 text-start font-medium">{t('importer.examples')}</th>
							</tr>
						</thead>
						<tbody>
							{#each job.columns as col (col.index)}
								<tr class="border-b border-slate-100 last:border-0">
									<td class="px-3 py-2 font-medium whitespace-nowrap">{columnName(col.index)}</td>
									<td class="px-3 py-2 text-slate-700">{samplesOf(col.index)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				<div class="flex flex-wrap justify-between gap-3">
					<button type="button" class="btn-secondary" onclick={() => go('file')}>{t('importer.back')}</button>
					<button type="button" class="btn-primary" disabled={sheetBusy} onclick={() => go('mapping')}>{t('importer.continue')}</button>
				</div>
			</section>
		{:else if step === 'mapping' && job}
			<section class={card} aria-labelledby="imp-map">
				<h2 id="imp-map" bind:this={heading} tabindex="-1" class="text-lg font-bold text-ink outline-none">{t('importer.steps.mapping')}</h2>
				<p class="max-w-3xl text-slate-700">{t('importer.mappingIntro')}</p>

				{#if kindTemplates.length}
					<div class="flex flex-wrap items-end gap-2 rounded-xl bg-slate-50 p-3">
						<label class="label">
							{t('importer.template')}
							<select class="input w-auto" bind:value={templateId}>
								<option value="">{t('importer.noTemplate')}</option>
								{#each kindTemplates as tpl (tpl.id)}<option value={String(tpl.id)}>{tpl.name}</option>{/each}
							</select>
						</label>
						<button type="button" class="btn-secondary" disabled={!templateId} onclick={applyTemplate}>{t('importer.applyTemplate')}</button>
						<button type="button" class="btn-secondary text-rose-700" disabled={!templateId} onclick={deleteTemplate}>{t('importer.deleteTemplate')}</button>
					</div>
				{/if}
				{#if templateNotice}<p role="status" class="text-sm font-medium text-brand-800">{templateNotice}</p>{/if}

				<div class="hidden gap-4 px-3 text-sm font-medium text-slate-600 lg:grid lg:grid-cols-[minmax(0,14rem)_minmax(0,18rem)_minmax(0,1fr)]" aria-hidden="true">
					<span>{t('importer.field')}</span><span>{t('importer.fileColumn')}</span><span>{t('importer.examples')}</span>
				</div>
				<ul class="flex flex-col divide-y divide-slate-100 rounded-xl border border-slate-200">
					{#each FIELDS[kind] as field (field)}
						{@const note = requiredNote(field)}
						<li class="grid gap-2 px-3 py-3 md:grid-cols-[minmax(0,12rem)_minmax(0,1fr)] md:items-center md:gap-x-4 lg:grid-cols-[minmax(0,14rem)_minmax(0,18rem)_minmax(0,1fr)]">
							<div class="flex flex-col">
								<label for="map-{field}" class="font-semibold text-ink">{fieldLabel(field)}</label>
								{#if note}<span class="text-xs font-medium text-amber-800">{note}</span>{/if}
							</div>
							<select
								id="map-{field}"
								class="input"
								value={mapping[field] === null ? '' : String(mapping[field])}
								onchange={(e) => {
									const v = e.currentTarget.value;
									mapping[field] = v === '' ? null : Number(v);
									missing = [];
								}}
							>
								<option value="">{t('importer.notImported')}</option>
								{#each job.columns as col (col.index)}<option value={String(col.index)}>{columnName(col.index)}</option>{/each}
							</select>
							<span class="truncate text-sm text-slate-600 md:col-start-2 lg:col-start-auto">{samplesOf(mapping[field] ?? null)}</span>
						</li>
					{/each}
				</ul>
				{#each missing as m (m)}<p role="alert" class="font-medium text-red-700">{t(`importer.missing.${m}`)}</p>{/each}
				{#each shared as col (col)}<p class="text-sm font-medium text-amber-800">{t('importer.shared', { column: columnLetter(col) })}</p>{/each}

				<fieldset class="flex min-w-0 flex-col gap-3 rounded-xl bg-slate-50 p-4">
					<legend class="px-1 font-semibold text-ink">{t('importer.options')}</legend>
					<div class="grid gap-4 md:grid-cols-2">
						{#if usesFullName}
							<label class="label">
								{t('importer.nameOrder')}
								<select class="input" bind:value={options.nameOrder}>
									{#each ['last_first', 'first_last'] as const as o (o)}<option value={o}>{t(`importer.nameOrders.${o}`)}</option>{/each}
								</select>
							</label>
						{/if}
						{#if usesDates}
							<label class="label">
								{t('importer.dateFormat')}
								<select class="input" bind:value={options.dateFormat}>
									{#each ['dmy', 'mdy', 'ymd'] as const as o (o)}<option value={o}>{t(`importer.dateFormats.${o}`)}</option>{/each}
								</select>
							</label>
						{/if}
						<label class="label">
							{t('importer.defaultLang')}
							<select class="input" bind:value={options.defaultLang}>
								<option value="fr">{t('common.french')}</option>
								<option value="ar">{t('common.arabic')}</option>
							</select>
						</label>
						{#if kind === 'patients'}
							<label class="label">
								{t('importer.duplicates')}
								<select class="input" bind:value={options.duplicates}>
									{#each ['skip', 'update', 'create'] as const as o (o)}<option value={o}>{t(`importer.duplicateRules.${o}`)}</option>{/each}
								</select>
							</label>
						{:else}
							<label class="label">
								{t('importer.defaultDuration')}
								<input class="input w-28" type="number" min="5" max="480" step="5" dir="ltr" bind:value={options.defaultDurationMin} />
							</label>
						{/if}
					</div>
					<label class="flex min-h-11 cursor-pointer items-center gap-3 text-slate-800">
						<input type="checkbox" class="h-5 w-5 accent-brand-700" bind:checked={options.reminderConsent} />
						{t('importer.reminderConsent')}
					</label>
				</fieldset>

				{#if checkError}<p role="alert" class="font-medium text-red-700">{checkError}</p>{/if}
				<div class="flex flex-wrap justify-between gap-3">
					<button type="button" class="btn-secondary" onclick={() => go('sheet')}>{t('importer.back')}</button>
					<button type="button" class="btn-primary" disabled={checking} onclick={check}>{checking ? t('importer.checking') : t('importer.check')}</button>
				</div>
			</section>
		{:else if step === 'check' && job && preview}
			<section class={card} aria-labelledby="imp-check">
				<h2 id="imp-check" bind:this={heading} tabindex="-1" class="text-lg font-bold text-ink outline-none">{t('importer.steps.check')}</h2>
				<p class="text-slate-700">{t('importer.checkIntro')}</p>
				<dl class="grid grid-cols-2 gap-2 sm:grid-cols-4">
					{#each [{ key: 'create', n: preview.willCreate, tone: 'text-brand-800' }, { key: 'update', n: preview.willUpdate, tone: 'text-sky-800' }, { key: 'skip', n: preview.willSkip, tone: 'text-slate-700' }, { key: 'errors', n: preview.errorCount, tone: preview.errorCount ? 'text-rose-700' : 'text-slate-700' }] as c (c.key)}
						<div class="flex flex-col-reverse rounded-xl border border-slate-200 bg-white px-4 py-3">
							<dt class="text-sm text-slate-600">{t(`importer.counts.${c.key}` as MessageKey)}</dt>
							<dd class="text-2xl font-bold tabular-nums {c.tone}">{formatNumber(c.n)}</dd>
						</div>
					{/each}
					{#if kind === 'appointments'}
						<div class="flex flex-col-reverse rounded-xl border border-slate-200 bg-white px-4 py-3">
							<dt class="text-sm text-slate-600">{t('importer.counts.patients')}</dt>
							<dd class="text-2xl font-bold tabular-nums text-ink">{formatNumber(preview.willCreatePatients)}</dd>
						</div>
					{/if}
				</dl>

				{#if preview.errors.length === 0}
					<p class="rounded-lg bg-emerald-50 px-3 py-2 font-medium text-emerald-900">{t('importer.noErrors')}</p>
				{:else}
					<div class="flex flex-col gap-2">
						<div class="flex flex-wrap items-center justify-between gap-2">
							<h3 class="font-semibold text-ink">{t('importer.errorsTitle')}</h3>
							<button type="button" class="btn-secondary min-h-9 py-1 text-sm" onclick={downloadErrors}>{t('importer.downloadErrors')}</button>
						</div>
						<p class="text-sm text-slate-600">{t('importer.errorsHint')}</p>
						<div class="max-h-96 overflow-auto rounded-xl border border-slate-200">
							<table class="w-full min-w-[36rem] text-start text-sm" aria-label={t('importer.errorsTitle')}>
								<thead class="sticky top-0 bg-white text-slate-600">
									<tr class="border-b border-slate-200">
										<th scope="col" class="px-3 py-2 text-start font-medium">{t('importer.row')}</th>
										<th scope="col" class="px-3 py-2 text-start font-medium">{t('importer.field')}</th>
										<th scope="col" class="px-3 py-2 text-start font-medium">{t('importer.problem')}</th>
										<th scope="col" class="px-3 py-2 text-start font-medium">{t('importer.value')}</th>
									</tr>
								</thead>
								<tbody>
									{#each preview.errors.slice(0, 100) as e, i (i)}
										<tr class="border-b border-slate-100 last:border-0">
											<td class="px-3 py-2 tabular-nums">{e.row}</td>
											<td class="px-3 py-2">{fieldLabel(e.field)}</td>
											<td class="px-3 py-2">{e.message}</td>
											<td class="px-3 py-2 font-mono text-slate-700" dir="auto">{e.value}</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
						{#if preview.errorCount > 100}<p class="text-sm text-slate-600">{t('importer.moreErrors', { n: preview.errorCount - 100 })}</p>{/if}
					</div>
				{/if}

				{#if preview.duplicates.length}
					<div class="flex flex-col gap-1">
						<h3 class="font-semibold text-ink">{t('importer.duplicatesTitle')}</h3>
						<ul class="flex max-h-60 flex-col gap-1 overflow-auto text-sm">
							{#each preview.duplicates.slice(0, 100) as d, i (i)}
								<li class="flex flex-wrap gap-x-3">
									<span>{t('importer.duplicateLine', { row: d.row, name: d.name })}</span>
									{#if d.patientId}<a class="font-medium text-brand-700 underline" href="/app/patients/{d.patientId}" target="_blank" rel="noopener"
											>{t('importer.openPatient')}</a
										>{/if}
								</li>
							{/each}
						</ul>
					</div>
				{/if}

				{#if preview.conflicts.length}
					<div class="flex flex-col gap-1">
						<h3 class="font-semibold text-ink">{t('importer.conflictsTitle')}</h3>
						<ul class="flex max-h-60 flex-col gap-1 overflow-auto text-sm">
							{#each preview.conflicts.slice(0, 100) as c, i (i)}<li>{t('importer.row')} {c.row} : {c.message}</li>{/each}
						</ul>
					</div>
				{/if}

				{#if sampleColumns.length}
					<div class="overflow-x-auto rounded-xl border border-slate-200">
						<table class="w-full text-start text-sm">
							<caption class="px-3 pt-3 text-start font-semibold text-ink">{t('importer.sampleTitle')}</caption>
							<thead class="text-slate-600">
								<tr class="border-b border-slate-200">
									{#each sampleColumns as key (key)}<th scope="col" class="px-3 py-2 text-start font-medium whitespace-nowrap">{fieldLabel(key)}</th>{/each}
								</tr>
							</thead>
							<tbody>
								{#each preview.sample as row, i (i)}
									<tr class="border-b border-slate-100 last:border-0">
										{#each sampleColumns as key (key)}<td class="px-3 py-2 whitespace-nowrap" dir="auto">{sampleValue(key, row[key])}</td>{/each}
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}

				{#if checkError}<p role="alert" class="font-medium text-red-700">{checkError}</p>{/if}
				{#if toImport === 0}<p class="font-medium text-amber-800">{t('importer.nothing')}</p>{/if}
				<div class="flex flex-wrap justify-between gap-3">
					<button type="button" class="btn-secondary" onclick={() => go('mapping')}>{t('importer.editMapping')}</button>
					<button type="button" class="btn-primary" disabled={committing || toImport === 0} onclick={commit}
						>{committing ? t('importer.importing') : t('importer.import', { n: formatNumber(toImport) })}</button
					>
				</div>
			</section>
		{:else if step === 'done' && result}
			<section class={card} aria-labelledby="imp-done">
				<h2 id="imp-done" bind:this={heading} tabindex="-1" class="text-xl font-bold text-ink outline-none">{t('importer.doneTitle')}</h2>
				<p class="text-lg text-slate-800">
					{t('importer.doneCounts', {
						created: formatNumber(result.created),
						updated: formatNumber(result.updated),
						skipped: formatNumber(result.skipped),
						errors: formatNumber(result.errorCount)
					})}
				</p>
				{#if result.patientsCreated}<p class="text-slate-700">{t('importer.donePatients', { n: formatNumber(result.patientsCreated) })}</p>{/if}
				<div class="flex flex-wrap gap-2">
					<button type="button" class="btn-secondary" onclick={downloadReport}>{t('importer.report')}</button>
					<a class="btn-primary" href={kind === 'patients' ? '/app/patients' : '/app/agenda'}>{kind === 'patients' ? t('importer.seePatients') : t('importer.seeAgenda')}</a>
				</div>
				{#if reportError}<p role="alert" class="text-sm font-medium text-red-700">{reportError}</p>{/if}
				<form class="flex flex-col gap-2 rounded-xl bg-slate-50 p-4" onsubmit={saveTemplate}>
					<p class="font-semibold text-ink">{t('importer.saveTemplate')}</p>
					<div class="flex flex-wrap items-end gap-2">
						<label class="label grow">
							{t('importer.templateName')}
							<input class="input" maxlength="120" bind:value={templateName} placeholder={t('importer.templatePlaceholder')} />
						</label>
						<button type="submit" class="btn-secondary" disabled={!templateName.trim()}>{t('importer.saveTemplateButton')}</button>
					</div>
					<p role="status" class="text-sm font-medium text-brand-800">{templateSaved}</p>
				</form>
				<button type="button" class="self-start font-semibold text-brand-700 underline-offset-4 hover:underline" onclick={restart}>{t('importer.again')}</button>
			</section>
		{/if}
	{/if}
</div>
