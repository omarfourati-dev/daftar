<script lang="ts">
	/**
	 * "Hygiène du jour" (spec stock-hygiène 5.2): one big row per task – overdue ones first in red – ticked with one tap
	 * on "Fait". A failed check ("non conforme") or a note goes through "Résultat et note". A done row says who and when;
	 * its author can undo a wrong tap for 15 minutes, the owner always – with a reason once it is not her own quick
	 * undo. When a colleague was quicker or the day changed (409 / 422), the list is loaded again (review N4). Used on
	 * "Aujourd'hui" and on /app/hygiene.
	 */
	import { untrack } from 'svelte';
	import { api, ApiError } from '../../api';
	import { auth } from '../../auth.svelte';
	import { badges } from '../../badges.svelte';
	import { dueText, hygieneError } from '../../hygiene';
	import { formatDay, formatTime, t } from '../../i18n.svelte';
	import type { HygieneItem, HygieneResult, HygieneToday } from '../../types/hygiene';
	import Icon from '../daily/Icon.svelte';

	type Props = { data: HygieneToday; compact?: boolean; onchange?: (data: HygieneToday) => void };
	let { data, compact = false, onchange }: Props = $props();

	let items = $state<HygieneItem[]>(untrack(() => data.items));
	let expanded = $state<string | null>(null);
	let result = $state<HygieneResult>('ok');
	let note = $state('');
	let busy = $state<string | null>(null);
	let error = $state('');
	let notice = $state('');
	/** The row whose undo waits for a reason (the owner, after the author's 15 minutes). */
	let asking = $state<string | null>(null);
	let undoReason = $state('');
	const keyOf = (item: HygieneItem) => `${item.taskId}-${item.dueOn}`;
	const manager = $derived(auth.role === 'owner' || auth.role === 'assistant');
	const open = $derived(items.filter((i) => i.state !== 'done').length);

	function publish(next: HygieneItem[]) {
		items = next;
		onchange?.({ ...data, items: next, open: next.filter((i) => i.state !== 'done').length });
		void badges.refresh();
	}

	/** The list as the server sees it now; on a loading problem the list on screen stays. */
	async function reload() {
		try {
			const fresh = await api<HygieneToday>('/api/hygiene/today');
			publish(fresh.items);
		} catch {
			/* keep what is shown; the error above already explains */
		}
	}

	function toggle(item: HygieneItem) {
		expanded = expanded === keyOf(item) ? null : keyOf(item);
		result = 'ok';
		note = '';
	}

	async function tick(item: HygieneItem, withDetails = false) {
		busy = keyOf(item);
		error = '';
		notice = '';
		try {
			const body = { dueOn: item.dueOn, result: withDetails ? result : 'ok', note: withDetails ? note.trim() : '' };
			const done = await api<HygieneItem>(`/api/hygiene/tasks/${item.taskId}/done`, { method: 'POST', json: body });
			expanded = null;
			publish(items.map((i) => (keyOf(i) === keyOf(item) ? done : i)));
		} catch (err) {
			error = hygieneError(err);
			if (err instanceof ApiError && (err.code === 'already_done' || err.code === 'not_due')) await reload();
		} finally {
			busy = null;
		}
	}

	async function undo(item: HygieneItem, reason = '') {
		if (!item.done) return;
		busy = keyOf(item);
		error = '';
		try {
			await api(`/api/hygiene/done/${item.done.id}`, { method: 'DELETE', json: reason ? { reason } : undefined });
			asking = null;
			undoReason = '';
			const state = item.dueOn < data.day ? 'overdue' : 'due';
			publish(items.map((i) => (keyOf(i) === keyOf(item) ? { ...i, state, done: null } : i)));
			notice = t('hygiene.today.undone', { task: item.title });
			void reload();
		} catch (err) {
			if (err instanceof ApiError && err.code === 'reason_required') {
				asking = keyOf(item);
				return;
			}
			error = hygieneError(err);
		} finally {
			busy = null;
		}
	}

	function confirmUndo(item: HygieneItem) {
		if (!undoReason.trim()) return void (error = t('hygiene.errors.reason_required'));
		void undo(item, undoReason.trim());
	}

	function doneText(item: HygieneItem): string {
		if (!item.done) return '';
		const day = item.done.doneAt.slice(0, 10);
		return day === data.day
			? t('hygiene.today.doneBy', { name: item.done.doneBy, time: formatTime(item.done.doneAt) })
			: t('hygiene.today.doneByOn', { name: item.done.doneBy, date: formatDay(day) });
	}
</script>

<div class="flex flex-col gap-3">
	{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}
	{#if notice}<p role="status" class="rounded-lg bg-slate-50 px-3 py-2 text-sm font-medium text-slate-800 ring-1 ring-slate-200">{notice}</p>{/if}
	{#if items.length === 0}
		<p class="text-slate-700">{manager ? t('hygiene.today.empty') : t('hygiene.today.emptyStaff')}</p>
	{:else}
		{#if open === 0}
			<p class="flex items-center gap-2 font-semibold text-emerald-800"><Icon name="check" />{t('hygiene.today.allDone')}</p>
		{/if}
		<ul class="flex flex-col gap-2" aria-label={t('hygiene.today.label')}>
			{#each items as item (keyOf(item))}
				<li
					class="flex flex-col gap-2 rounded-xl border p-3 {item.state === 'overdue'
						? 'border-rose-300 bg-rose-50'
						: item.state === 'done'
							? 'border-emerald-200 bg-emerald-50/60'
							: 'border-slate-200 bg-white'}"
				>
					<div class="flex items-start gap-3">
						<span
							class="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full {item.state === 'done'
								? 'bg-emerald-600 text-white'
								: item.state === 'overdue'
									? 'bg-rose-600 text-white'
									: 'border-2 border-slate-300 text-transparent'}"
							aria-hidden="true"><Icon name={item.state === 'overdue' ? 'alert' : 'check'} class="h-4 w-4" /></span
						>
						<div class="min-w-0 flex-1">
							<p class="font-semibold text-ink" dir="auto">{item.title}</p>
							<p class="text-sm {item.state === 'overdue' ? 'font-semibold text-rose-800' : 'text-slate-600'}">
								{#if item.equipmentName}<span dir="auto">{item.equipmentName}</span>{' – '}{/if}{item.state === 'done' ? doneText(item) : dueText(item)}
							</p>
							{#if item.done?.result === 'not_ok'}
								<p class="mt-1 inline-block rounded bg-rose-100 px-1.5 text-xs font-bold text-rose-900">{t('hygiene.today.notOk')}</p>
							{/if}
							{#if item.done?.note}<p class="text-sm text-slate-700" dir="auto">{item.done.note}</p>{/if}
							{#if !compact && item.instructions && item.state !== 'done'}<p class="mt-1 text-sm text-slate-600" dir="auto">{item.instructions}</p>{/if}
						</div>
						{#if item.state !== 'done'}
							<button
								type="button"
								class="btn-primary min-h-12 shrink-0 px-4"
								aria-label="{t('hygiene.today.done')} – {item.title}"
								disabled={busy === keyOf(item)}
								onclick={() => tick(item)}><Icon name="check" />{t('hygiene.today.done')}</button
							>
						{:else if item.done?.undoable}
							<button
								type="button"
								class="btn-secondary min-h-11 shrink-0 px-3 text-sm"
								aria-label="{t('hygiene.today.undo')} – {item.title}"
								disabled={busy === keyOf(item)}
								onclick={() => undo(item)}>{t('hygiene.today.undo')}</button
							>
						{/if}
					</div>
					{#if asking === keyOf(item)}
						<form class="flex flex-wrap items-end gap-2 rounded-lg bg-white p-3 ring-1 ring-slate-200" onsubmit={(e) => (e.preventDefault(), confirmUndo(item))}>
							<label class="label min-w-0 flex-1"
								>{t('hygiene.today.undoReason')}<input class="input" bind:value={undoReason} maxlength="300" autocomplete="off" dir="auto" data-autofocus /></label
							>
							<button type="submit" class="btn-secondary min-h-11 text-rose-800" disabled={busy === keyOf(item)}>{t('hygiene.today.undoConfirm')}</button>
						</form>
					{/if}
					{#if item.state !== 'done'}
						<button
							type="button"
							class="min-h-10 self-start text-sm font-semibold text-brand-800 underline-offset-2 hover:underline"
							aria-expanded={expanded === keyOf(item)}
							aria-label="{t('hygiene.today.more')} – {item.title}"
							onclick={() => toggle(item)}>{t('hygiene.today.more')}</button
						>
						{#if expanded === keyOf(item)}
							<div class="flex flex-col gap-3 rounded-lg bg-white p-3 ring-1 ring-slate-200">
								<fieldset class="flex flex-wrap gap-4">
									<legend class="mb-1 text-sm font-medium text-slate-700">{t('hygiene.today.result')}</legend>
									<label class="inline-flex min-h-11 items-center gap-2"
										><input type="radio" name="result-{item.taskId}" value="ok" bind:group={result} class="h-5 w-5 accent-brand-700" />{t('hygiene.today.resultOk')}</label
									>
									<label class="inline-flex min-h-11 items-center gap-2"
										><input type="radio" name="result-{item.taskId}" value="not_ok" bind:group={result} class="h-5 w-5 accent-rose-700" />{t('hygiene.today.resultNotOk')}</label
									>
								</fieldset>
								<label class="label">{t('hygiene.today.note')}<input class="input" bind:value={note} maxlength="500" autocomplete="off" dir="auto" /></label>
								<button type="button" class="btn-primary self-start" disabled={busy === keyOf(item)} onclick={() => tick(item, true)}>{t('hygiene.today.save')}</button>
							</div>
						{/if}
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
</div>
