<script lang="ts">
	/**
	 * A new sterilisation cycle (spec stock-hygiène 5.3), made for the phone next to the autoclave: the autoclave and
	 * its next number are filled in, the program and the contents are one tap (the practice's last ones first), the
	 * result is two big buttons. "Conforme": the packs, then their labels. "Non conforme": no label – the load is
	 * sterilised again.
	 */
	import { onMount } from 'svelte';
	import { api } from '../../api';
	import { auth } from '../../auth.svelte';
	import { clock } from '../../clock';
	import { addDays, formatDay, t, todayTunis, tunisInstant } from '../../i18n.svelte';
	import { PACKAGINGS, labelsError } from '../../labels';
	import type { Cycle, CycleResult, CycleSetup, LabelSettings, Packaging } from '../../types/labels';
	import Icon from '../daily/Icon.svelte';
	import Modal from '../daily/Modal.svelte';

	type Props = { settings: LabelSettings; onsaved: (cycle: Cycle) => void; onclose: () => void };
	let { settings, onsaved, onclose }: Props = $props();

	type Line = { key: number; content: string; packaging: Packaging; quantity: number };
	const now = clock.now();
	const nowTime = new Intl.DateTimeFormat('en-GB', { timeZone: 'Africa/Tunis', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(now);

	let setup = $state<CycleSetup | null>(null);
	let loadError = $state('');
	let equipmentId = $state('');
	let number = $state<number | null>(null);
	let numberTouched = false;
	let day = $state(todayTunis(now));
	let time = $state(nowTime);
	let program = $state('');
	let result = $state<CycleResult | null>(null);
	let lines = $state<Line[]>([]);
	let load = $state(1);
	let note = $state('');
	let newAutoclave = $state('');
	let error = $state('');
	let busy = $state(false);
	let nextKey = 1;
	const manager = auth.role === 'owner' || auth.role === 'assistant';
	const id = `cycle-${Math.random().toString(36).slice(2, 8)}`;

	async function loadSetup() {
		loadError = '';
		try {
			setup = await api<CycleSetup>('/api/hygiene/cycles/setup');
			if (!equipmentId && setup.autoclaves.length) choose(String(setup.autoclaves[0].id));
			if (!program) program = setup.programs[0] ?? '';
		} catch (err) {
			loadError = labelsError(err);
		}
	}
	onMount(loadSetup);

	function choose(value: string) {
		equipmentId = value;
		const autoclave = setup?.autoclaves.find((a) => String(a.id) === value);
		if (autoclave && !numberTouched) number = autoclave.nextNumber;
	}

	async function addAutoclave() {
		if (!newAutoclave.trim()) return;
		busy = true;
		error = '';
		try {
			const made = await api<{ id: number }>('/api/hygiene/equipment', { method: 'POST', json: { name: newAutoclave.trim(), kind: 'autoclave' } });
			newAutoclave = '';
			await loadSetup();
			choose(String(made.id));
		} catch (err) {
			error = labelsError(err);
		} finally {
			busy = false;
		}
	}

	function addContent(content = '') {
		const same = content && lines.find((l) => l.content === content && l.packaging === 'sachet');
		if (same) same.quantity = Math.min(99, same.quantity + 1);
		else lines.push({ key: nextKey++, content, packaging: 'sachet', quantity: 1 });
	}

	const total = $derived(lines.reduce((sum, l) => sum + (Number.isInteger(l.quantity) ? l.quantity : 0), 0));
	const expiries = $derived(
		[...new Set(lines.map((l) => l.packaging))].map((p) => ({ packaging: p, date: addDays(day, settings.shelfLifeDays[p]) }))
	);
	const submitLabel = $derived(
		result === 'not_ok' ? t('labels.cycleDialog.saveNotOk') : total ? t('labels.cycleDialog.saveAndPrint', { count: total }) : t('labels.cycleDialog.save')
	);

	async function save(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		if (!equipmentId) return void (error = t('labels.cycleDialog.chooseAutoclave'));
		if (!result) return void (error = t('labels.cycleDialog.chooseResult'));
		if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || !/^\d{2}:\d{2}$/.test(time)) return void (error = t('labels.cycleDialog.whenInvalid'));
		if (number !== null && (!Number.isInteger(number) || number < 1)) return void (error = t('labels.cycleDialog.numberInvalid'));
		const packs = result === 'ok' ? lines.filter((l) => l.content.trim()) : [];
		if (packs.some((l) => !Number.isInteger(l.quantity) || l.quantity < 1)) return void (error = t('labels.cycleDialog.quantityInvalid'));
		busy = true;
		try {
			const cycle = await api<Cycle>('/api/hygiene/cycles', {
				method: 'POST',
				json: {
					equipmentId: Number(equipmentId),
					number,
					runAt: tunisInstant(day, time),
					program: program.trim(),
					result,
					packs: packs.map((l) => ({ content: l.content.trim(), packaging: l.packaging, quantity: l.quantity })),
					packCount: result === 'not_ok' ? load : null,
					note: note.trim()
				}
			});
			onsaved(cycle);
		} catch (err) {
			error = labelsError(err);
		} finally {
			busy = false;
		}
	}
</script>

<Modal title={t('labels.cycleDialog.title')} {onclose} guard wide>
	{#if loadError}
		<div class="flex flex-col items-start gap-3">
			<p role="alert" class="text-rose-900">{loadError}</p>
			<button type="button" class="btn-secondary" onclick={loadSetup}>{t('common.retry')}</button>
		</div>
	{:else if !setup}
		<p class="text-slate-600" aria-busy="true">{t('common.loading')}</p>
	{:else if !setup.autoclaves.length}
		<div class="flex flex-col gap-3">
			<p class="text-slate-700">{t('labels.cycleDialog.noAutoclave')}</p>
			{#if manager}
				<div class="flex flex-wrap items-end gap-2">
					<label class="label min-w-0 flex-1"
						>{t('labels.cycleDialog.autoclaveName')}<input class="input" bind:value={newAutoclave} maxlength="120" autocomplete="off" dir="auto" data-autofocus /></label
					>
					<button type="button" class="btn-primary" disabled={busy || !newAutoclave.trim()} onclick={addAutoclave}>{t('labels.cycleDialog.addAutoclave')}</button>
				</div>
			{:else}
				<p class="text-sm text-slate-600">{t('labels.cycleDialog.askAssistant')}</p>
			{/if}
			{#if error}<p role="alert" class="text-sm font-medium text-rose-900">{error}</p>{/if}
		</div>
	{:else}
		<form id={id} class="flex flex-col gap-5" onsubmit={save} novalidate>
			<div class="grid gap-3 sm:grid-cols-[2fr_1fr]">
				{#if setup.autoclaves.length > 1}
					<label class="label"
						>{t('labels.cycleDialog.autoclave')}
						<select class="input" value={equipmentId} onchange={(e) => choose(e.currentTarget.value)}>
							{#each setup.autoclaves as a (a.id)}<option value={String(a.id)}>{a.name}{a.labelCode ? ` (${a.labelCode})` : ''}</option>{/each}
						</select>
					</label>
				{:else}
					<p class="label">
						{t('labels.cycleDialog.autoclave')}
						<span class="flex min-h-11 items-center font-semibold text-ink" dir="auto">{setup.autoclaves[0].name}</span>
					</p>
				{/if}
				<label class="label"
					>{t('labels.cycleDialog.number')}
					<input class="input tabular-nums" type="number" inputmode="numeric" min="1" step="1" bind:value={number} oninput={() => (numberTouched = true)} />
				</label>
			</div>
			<div class="grid gap-3 sm:grid-cols-3">
				<label class="label">{t('labels.cycleDialog.day')}<input class="input" type="date" bind:value={day} max={todayTunis(now)} /></label>
				<label class="label">{t('labels.cycleDialog.time')}<input class="input" type="time" bind:value={time} /></label>
				<label class="label"
					>{t('labels.cycleDialog.program')}<input class="input" list="{id}-programs" bind:value={program} maxlength="60" autocomplete="off" dir="auto" /></label
				>
				<datalist id="{id}-programs">{#each setup.programs as p (p)}<option value={p}></option>{/each}</datalist>
			</div>

			<fieldset class="flex flex-col gap-2">
				<legend class="mb-1 text-sm font-semibold text-slate-700">{t('labels.cycleDialog.result')}</legend>
				<div class="grid grid-cols-2 gap-2">
					<label class="choice ok">
						<input type="radio" name="{id}-result" value="ok" bind:group={result} class="sr-only" />
						<Icon name="check" class="h-6 w-6" />{t('labels.cycleDialog.ok')}
					</label>
					<label class="choice not-ok">
						<input type="radio" name="{id}-result" value="not_ok" bind:group={result} class="sr-only" />
						<Icon name="alert" class="h-6 w-6" />{t('labels.cycleDialog.notOk')}
					</label>
				</div>
				<p class="text-sm text-slate-600">{t('labels.cycleDialog.resultHint')}</p>
			</fieldset>

			{#if result === 'ok'}
				<fieldset class="flex flex-col gap-3">
					<legend class="mb-1 font-semibold">{t('labels.cycleDialog.packs')}</legend>
					<div class="flex flex-wrap gap-2" role="group" aria-label={t('labels.cycleDialog.quickContents')}>
						{#each setup.contents.slice(0, 7) as c (c)}
							<button type="button" class="chip" onclick={() => addContent(c)}><Icon name="plus" class="h-4 w-4" /><span dir="auto">{c}</span></button>
						{/each}
					</div>
					{#if lines.length}
						<ul class="flex flex-col gap-2" aria-label={t('labels.cycleDialog.packs')}>
							{#each lines as line, i (line.key)}
								<li class="grid gap-2 rounded-xl bg-slate-50 p-3 ring-1 ring-slate-200 sm:grid-cols-[minmax(0,1fr)_10rem_auto] sm:items-end">
									<label class="label"
										>{t('labels.cycleDialog.content', { n: i + 1 })}<input
											class="input"
											list="{id}-contents"
											bind:value={line.content}
											maxlength="60"
											autocomplete="off"
											dir="auto"
										/></label
									>
									<label class="label"
										>{t('labels.cycleDialog.packaging')}
										<select class="input" bind:value={line.packaging}>
											{#each PACKAGINGS as p (p)}<option value={p}>{t(`labels.packagings.${p}`)}</option>{/each}
										</select>
									</label>
									<div class="flex items-end gap-2">
										<div class="flex items-center rounded-lg ring-1 ring-slate-300" role="group" aria-label={t('labels.cycleDialog.quantityOf', { content: line.content || '–' })}>
											<button
												type="button"
												class="btn min-h-11 min-w-11 px-2"
												aria-label={t('labels.cycleDialog.less')}
												onclick={() => (line.quantity > 1 ? (line.quantity -= 1) : lines.splice(i, 1))}><span aria-hidden="true">−</span></button
											>
											<input
												class="h-11 w-12 border-0 bg-transparent text-center font-semibold tabular-nums"
												type="number"
												inputmode="numeric"
												min="1"
												max="99"
												step="1"
												aria-label={t('labels.cycleDialog.quantity')}
												bind:value={line.quantity}
											/>
											<button type="button" class="btn min-h-11 min-w-11 px-2" aria-label={t('labels.cycleDialog.more')} onclick={() => (line.quantity = Math.min(99, line.quantity + 1))}
												><span aria-hidden="true">+</span></button
											>
										</div>
										<button
											type="button"
											class="btn min-h-11 min-w-11 px-2 text-slate-600 hover:text-rose-700"
											aria-label={t('labels.cycleDialog.removeLine', { n: i + 1 })}
											onclick={() => lines.splice(i, 1)}><Icon name="trash" class="h-4 w-4" /></button
										>
									</div>
								</li>
							{/each}
						</ul>
					{/if}
					<datalist id="{id}-contents">{#each setup.contents as c (c)}<option value={c}></option>{/each}</datalist>
					<button type="button" class="btn-secondary self-start text-sm" onclick={() => addContent()}><Icon name="plus" class="h-4 w-4" />{t('labels.cycleDialog.addLine')}</button>
					{#if total}
						<p class="text-sm font-semibold text-slate-700">
							{t('labels.cycleDialog.total', { count: total })}
							{#each expiries as e (e.packaging)}<span class="block font-normal text-slate-600"
									>{t('labels.cycleDialog.useBefore', { packaging: t(`labels.packagings.${e.packaging}`), date: formatDay(e.date) })}</span
								>{/each}
						</p>
					{:else}
						<p class="text-sm text-slate-600">{t('labels.cycleDialog.noPacks')}</p>
					{/if}
				</fieldset>
			{:else if result === 'not_ok'}
				<div class="flex flex-col gap-3 rounded-xl border border-rose-300 bg-rose-50 p-4">
					<p class="flex gap-2 font-semibold text-rose-900"><Icon name="alert" class="mt-0.5 h-5 w-5" />{t('labels.cycleDialog.notOkText')}</p>
					<label class="label text-rose-950"
						>{t('labels.cycleDialog.load')}<input class="input w-28 text-center tabular-nums" type="number" inputmode="numeric" min="0" max="99" step="1" bind:value={load} /></label
					>
				</div>
			{/if}

			<label class="label">{t('labels.cycleDialog.note')}<input class="input" bind:value={note} maxlength="500" autocomplete="off" dir="auto" /></label>
			{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}
		</form>
	{/if}
	{#snippet footer()}
		<button type="button" class="btn-secondary" onclick={onclose}>{t('common.cancel')}</button>
		{#if setup?.autoclaves.length}
			<button type="submit" form={id} class="btn-primary" disabled={busy}>{submitLabel}</button>
		{/if}
	{/snippet}
</Modal>

<style>
	.choice {
		display: flex;
		min-height: 3.5rem;
		cursor: pointer;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		border-radius: 0.75rem;
		border: 2px solid #cbd5e1;
		background: #fff;
		font-size: 1.05rem;
		font-weight: 700;
	}
	.choice.ok:has(:checked) {
		border-color: #047857;
		background: #ecfdf5;
		color: #022c22;
	}
	.choice.not-ok:has(:checked) {
		border-color: #be123c;
		background: #fff1f2;
		color: #4c0519;
	}
	.choice:has(:focus-visible) {
		outline: 2px solid var(--color-brand-700);
		outline-offset: 2px;
	}
	.chip {
		display: inline-flex;
		min-height: 2.75rem;
		align-items: center;
		gap: 0.35rem;
		border-radius: 9999px;
		padding: 0 0.9rem;
		background: #fff;
		box-shadow: inset 0 0 0 1px #cbd5e1;
		font-size: 0.9rem;
		font-weight: 600;
	}
	.chip:hover {
		background: #f0fdfa;
	}
	.chip:focus-visible {
		outline: 2px solid var(--color-brand-700);
		outline-offset: 2px;
	}
</style>
