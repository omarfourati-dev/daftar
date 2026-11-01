<script lang="ts">
	/**
	 * "Étiquettes de prélèvement" (spec stock-hygiène 6) in the patient file and the appointment dialog: how many tubes
	 * of which kind, when and by whom – then the label page. Folded away; the print is kept as a small proof (who, when,
	 * which tubes, how many) – never a result. The time of collection is "now" when "Préparer" is tapped, and the form
	 * shows it moving on, until the user sets another one (review M2): a file opened at 08:40 does not label the blood
	 * taken at 09:25 with 08:40.
	 */
	import { onDestroy } from 'svelte';
	import { api, deps } from '../../api';
	import { auth } from '../../auth.svelte';
	import { clock } from '../../clock';
	import { t, todayTunis, tunisInstant } from '../../i18n.svelte';
	import { SPECIMEN_KINDS, labelsError } from '../../labels';
	import type { SpecimenKind, SpecimenPrint } from '../../types/labels';
	import Icon from '../daily/Icon.svelte';

	type Props = { patientId: number; appointmentId?: number | null; birthDate?: string | null; birthKnown?: boolean };
	let { patientId, appointmentId = null, birthDate = null, birthKnown = true }: Props = $props();

	const clockTime = (at: Date) =>
		new Intl.DateTimeFormat('en-GB', { timeZone: 'Africa/Tunis', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(at);
	let open = $state(false);
	let counts = $state<Record<SpecimenKind, number>>(Object.fromEntries(SPECIMEN_KINDS.map((k) => [k, 0])) as Record<SpecimenKind, number>);
	let other = $state('');
	let day = $state(todayTunis(clock.now()));
	let time = $state(clockTime(clock.now()));
	/** The user set the day or the time: from then on it stays as typed. */
	let chosen = $state(false);
	let by = $state(auth.user?.name ?? '');
	let error = $state('');
	let busy = $state(false);
	const id = `specimen-${Math.random().toString(36).slice(2, 8)}`;

	const total = $derived(SPECIMEN_KINDS.reduce((sum, k) => sum + counts[k], 0));

	/** "Now" again, unless the user set the time herself. */
	function follow() {
		if (chosen) return;
		const now = clock.now();
		day = todayTunis(now);
		time = clockTime(now);
	}
	let ticking: ReturnType<typeof setInterval> | undefined;
	function toggle() {
		open = !open;
		clearInterval(ticking);
		if (!open) return;
		follow();
		ticking = setInterval(follow, 20_000);
	}
	onDestroy(() => clearInterval(ticking));

	function step(kind: SpecimenKind, delta: number) {
		counts[kind] = Math.max(0, Math.min(20, counts[kind] + delta));
	}

	async function prepare(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		if (!total) return void (error = t('labels.specimenForm.chooseOne'));
		if (counts.autre && !other.trim()) return void (error = t('labels.errors.specimen_label_required'));
		follow();
		busy = true;
		try {
			const made = await api<SpecimenPrint>('/api/labels/specimens', {
				method: 'POST',
				json: {
					patientId,
					appointmentId,
					items: SPECIMEN_KINDS.filter((k) => counts[k] > 0).map((k) => ({ kind: k, count: counts[k], label: k === 'autre' ? other.trim() : '' })),
					collectedAt: tunisInstant(day, time),
					collectedBy: by.trim()
				}
			});
			void deps.goto(`/app/etiquettes?specimen=${made.id}`);
		} catch (err) {
			error = labelsError(err);
		} finally {
			busy = false;
		}
	}
</script>

<div class="flex flex-col gap-2">
	<button
		type="button"
		class="inline-flex min-h-11 items-center gap-2 self-start rounded-lg px-1 text-sm font-semibold text-brand-800 underline-offset-2 hover:underline"
		aria-expanded={open}
		aria-controls={id}
		onclick={toggle}><Icon name={open ? 'close' : 'print'} class="h-4 w-4" />{t('labels.specimenForm.open')}</button
	>
	{#if open}
		<form {id} class="flex flex-col gap-4 rounded-lg bg-slate-50 p-3 ring-1 ring-slate-200" onsubmit={prepare} novalidate>
			<p class="text-sm text-slate-600">{t('labels.specimenForm.hint')}</p>
			{#if !birthDate && birthKnown}
				<p class="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-950 ring-1 ring-amber-200">{t('labels.specimenForm.noBirthDate')}</p>
			{/if}
			<fieldset>
				<legend class="mb-2 text-sm font-semibold text-slate-700">{t('labels.specimenForm.tubes')}</legend>
				<ul class="grid gap-2 sm:grid-cols-2">
					{#each SPECIMEN_KINDS as k (k)}
						<li class="flex min-h-12 items-center gap-2 rounded-lg bg-white px-3 ring-1 {counts[k] ? 'ring-brand-700' : 'ring-slate-200'}">
							<span class="min-w-0 flex-1 text-sm font-semibold" id="{id}-{k}">{t(`labels.kinds.${k}`)}</span>
							<button type="button" class="btn min-h-10 min-w-10 px-2" aria-label={t('labels.specimenForm.less', { kind: t(`labels.kinds.${k}`) })} onclick={() => step(k, -1)}
								><span aria-hidden="true">−</span></button
							>
							<output class="w-6 text-center font-bold tabular-nums" aria-labelledby="{id}-{k}">{counts[k]}</output>
							<button type="button" class="btn min-h-10 min-w-10 px-2" aria-label={t('labels.specimenForm.more', { kind: t(`labels.kinds.${k}`) })} onclick={() => step(k, 1)}
								><span aria-hidden="true">+</span></button
							>
						</li>
					{/each}
				</ul>
			</fieldset>
			{#if counts.autre}
				<label class="label">{t('labels.specimenForm.otherName')}<input class="input" bind:value={other} maxlength="30" autocomplete="off" dir="auto" /></label>
			{/if}
			<div class="grid gap-3 sm:grid-cols-3">
				<label class="label">{t('labels.specimenForm.day')}<input class="input" type="date" bind:value={day} oninput={() => (chosen = true)} /></label>
				<label class="label">{t('labels.specimenForm.time')}<input class="input" type="time" bind:value={time} oninput={() => (chosen = true)} /></label>
				<label class="label">{t('labels.specimenForm.by')}<input class="input" bind:value={by} maxlength="120" autocomplete="off" dir="auto" /></label>
			</div>
			{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}
			<button type="submit" class="btn-primary self-start" disabled={busy || !total}><Icon name="print" />{t('labels.specimenForm.prepare', { count: total })}</button>
		</form>
	{/if}
</div>
