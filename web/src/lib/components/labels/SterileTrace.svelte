<script lang="ts">
	/**
	 * "Traçabilité stérilisation" in the appointment dialog (spec stock-hygiène 5.3): which sterile pack was opened for
	 * this patient. Folded away and never required – the desk never waits for it. Opened: type the code of the label (a
	 * desk scanner types it too, then Enter) or tap one of the packs ready to use; an expired pack, one of a
	 * "non conforme" or of a cancelled cycle is refused with the reason, before and after choosing it. Taking a pack
	 * back asks why (a tap on a usual reason) – the change log keeps it (review M1).
	 */
	import { tick } from 'svelte';
	import { api } from '../../api';
	import { formatDay, formatTime, t } from '../../i18n.svelte';
	import { labelsError, patientOfUse } from '../../labels';
	import type { PackFound, PackUse } from '../../types/labels';
	import Icon from '../daily/Icon.svelte';
	import StateChip from './StateChip.svelte';

	let { appointmentId }: { appointmentId: number } = $props();

	let open = $state(false);
	let uses = $state<PackUse[] | null>(null);
	let found = $state<PackFound[]>([]);
	let code = $state('');
	let notice = $state('');
	let error = $state('');
	let busy = $state(false);
	/** The pack being taken back, and why. */
	let removing = $state<PackUse | null>(null);
	let why = $state('');
	let timer: ReturnType<typeof setTimeout> | undefined;
	let seq = 0;
	const id = `trace-${Math.random().toString(36).slice(2, 8)}`;

	async function toggle() {
		open = !open;
		if (!open || uses !== null) return;
		try {
			[uses, found] = await Promise.all([
				api<PackUse[]>(`/api/hygiene/pack-uses?appointmentId=${appointmentId}`),
				api<PackFound[]>('/api/hygiene/packs')
			]);
		} catch (err) {
			uses = [];
			error = labelsError(err);
		}
	}

	function typed() {
		clearTimeout(timer);
		const q = code.trim();
		timer = setTimeout(() => void search(q), 200);
	}

	async function search(q: string) {
		const mine = ++seq;
		try {
			const list = await api<PackFound[]>(`/api/hygiene/packs${q ? `?q=${encodeURIComponent(q)}` : ''}`);
			if (mine === seq) found = list;
		} catch {
			/* the suggestions are only a help */
		}
	}

	async function add(value: string) {
		if (!value.trim()) return;
		busy = true;
		error = '';
		notice = '';
		try {
			const used = await api<PackUse>('/api/hygiene/pack-uses', { method: 'POST', json: { code: value.trim(), appointmentId } });
			uses = [used, ...(uses ?? [])];
			notice = t('labels.use.added', { code: used.code, content: used.content });
			code = '';
			void search('');
		} catch (err) {
			error = labelsError(err);
		} finally {
			busy = false;
		}
	}

	async function askWhy(use: PackUse) {
		removing = use;
		why = '';
		error = '';
		notice = '';
		await tick();
		document.getElementById(`${id}-why`)?.focus();
	}

	async function remove(e: SubmitEvent) {
		e.preventDefault();
		const use = removing;
		if (!use) return;
		if (!why.trim()) return void (error = t('labels.errors.reason_required'));
		busy = true;
		error = '';
		try {
			await api(`/api/hygiene/pack-uses/${use.id}`, { method: 'DELETE', json: { reason: why.trim() } });
			uses = (uses ?? []).filter((u) => u.id !== use.id);
			notice = t('labels.use.removed', { code: use.code });
			removing = null;
			void search(code.trim());
		} catch (err) {
			error = labelsError(err);
		} finally {
			busy = false;
		}
	}

	function used(p: PackFound) {
		const patient = p.use ? patientOfUse(p.use) : '';
		return patient ? t('labels.use.usedFor', { patient }) : t('labels.use.usedAlready');
	}

	const reason = (p: PackFound) =>
		p.state === 'expired'
			? t('labels.use.expiredOn', { date: formatDay(p.expiresOn) })
			: p.state === 'used'
				? used(p)
				: p.state === 'cancelled'
					? t('labels.use.cancelled', { reason: p.cancelReason ?? '' })
					: t('labels.use.notSterile');
</script>

<div class="flex flex-col gap-2">
	<button
		type="button"
		class="inline-flex min-h-11 items-center gap-2 self-start rounded-lg px-1 text-sm font-semibold text-brand-800 underline-offset-2 hover:underline"
		aria-expanded={open}
		aria-controls={id}
		onclick={toggle}><Icon name={open ? 'close' : 'plus'} class="h-4 w-4" />{t('labels.use.open')}</button
	>
	{#if open}
		<section {id} aria-labelledby="{id}-title" class="flex flex-col gap-3 rounded-lg bg-slate-50 p-3 ring-1 ring-slate-200">
			<div>
				<h3 id="{id}-title" class="font-semibold">{t('labels.use.title')}</h3>
				<p class="text-sm text-slate-600">{t('labels.use.hint')}</p>
			</div>
			{#if uses === null}
				<p class="text-sm text-slate-500" aria-busy="true">{t('common.loading')}</p>
			{:else}
				{#if uses.length}
					<ul class="flex flex-col gap-1 text-sm" aria-label={t('labels.use.usedList')}>
						{#each uses as u (u.id)}
							<li class="flex flex-wrap items-center gap-2">
								<Icon name="check" class="h-4 w-4 text-emerald-700" />
								<span class="font-bold tabular-nums" dir="ltr">{u.code}</span>
								<span dir="auto">{u.content}</span>
								<span class="text-slate-500 tabular-nums">{formatTime(u.usedAt)}</span>
								{#if u.undoable}
									<button
										type="button"
										class="btn ms-auto min-h-9 px-2 text-xs text-slate-600 hover:text-rose-700"
										disabled={busy}
										aria-expanded={removing?.id === u.id}
										aria-label={t('labels.use.removeLabel', { code: u.code })}
										onclick={() => askWhy(u)}>{t('labels.use.remove')}</button
									>
								{/if}
								{#if removing?.id === u.id}
									<form class="flex w-full flex-col gap-2 rounded-lg bg-white p-2 ring-1 ring-slate-200" onsubmit={remove} novalidate>
										<label class="label" for="{id}-why">{t('labels.use.reason')}</label>
										<div class="flex flex-wrap gap-2" role="group" aria-label={t('labels.use.reasonsQuick')}>
											{#each [t('labels.use.reasonWrongPack'), t('labels.use.reasonWrongPatient')] as quick (quick)}
												<button type="button" class="btn-secondary min-h-9 px-3 text-xs" onclick={() => (why = quick)}>{quick}</button>
											{/each}
										</div>
										<input id="{id}-why" class="input" bind:value={why} maxlength="300" autocomplete="off" dir="auto" aria-required="true" />
										<div class="flex flex-wrap gap-2">
											<button type="submit" class="btn-primary min-h-10 text-sm" disabled={busy}>{t('labels.use.removeConfirm')}</button>
											<button type="button" class="btn-secondary min-h-10 text-sm" onclick={() => ((removing = null), (error = ''))}>{t('labels.use.keep')}</button>
										</div>
									</form>
								{/if}
							</li>
						{/each}
					</ul>
				{:else}
					<p class="text-sm text-slate-600">{t('labels.use.none')}</p>
				{/if}
				<form class="flex flex-wrap items-end gap-2" onsubmit={(e) => (e.preventDefault(), void add(code))}>
					<label class="label min-w-0 flex-1"
						>{t('labels.use.code')}<input
							class="input font-semibold tracking-wide uppercase tabular-nums"
							dir="ltr"
							bind:value={code}
							oninput={typed}
							maxlength="40"
							autocomplete="off"
							placeholder="A1-0412-07"
						/></label
					>
					<button type="submit" class="btn-secondary min-h-11" disabled={busy || !code.trim()}>{t('labels.use.add')}</button>
				</form>
				{#if found.length}
					<ul class="flex flex-col gap-1" aria-label={code.trim() ? t('labels.use.matches') : t('labels.use.ready')}>
						{#each found as p (p.id)}
							<li>
								{#if p.state === 'usable'}
									<button
										type="button"
										class="flex min-h-11 w-full items-center gap-2 rounded-lg bg-white px-3 py-1.5 text-start text-sm ring-1 ring-slate-200 hover:ring-brand-700"
										disabled={busy}
										onclick={() => add(p.code)}
										><span class="font-bold tabular-nums" dir="ltr">{p.code}</span><span class="min-w-0 flex-1 truncate" dir="auto">{p.content}</span><span
											class="text-xs text-slate-600">{t('labels.trace.useBefore', { date: formatDay(p.expiresOn) })}</span
										></button
									>
								{:else}
									<p class="flex flex-wrap items-center gap-2 rounded-lg px-3 py-1.5 text-sm text-slate-700 ring-1 ring-slate-200">
										<span class="font-bold tabular-nums" dir="ltr">{p.code}</span><span dir="auto">{p.content}</span><StateChip state={p.state} /><span
											class="w-full text-xs">{reason(p)}</span
										>
									</p>
								{/if}
							</li>
						{/each}
					</ul>
				{:else if code.trim()}
					<p class="text-sm text-slate-600">{t('labels.use.noMatch')}</p>
				{/if}
			{/if}
			{#if notice}<p role="status" class="text-sm font-medium text-emerald-800">{notice}</p>{/if}
			{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}
		</section>
	{/if}
</div>
