<script lang="ts">
	/**
	 * Create or change a hygiene task (assistant, owner): title, equipment, rhythm (daily on opening days, weekly on a
	 * day, monthly, yearly, every N days), first date, instructions. Deleting works only without proofs (409 task_in_use);
	 * otherwise the task is deactivated so the register stays complete.
	 */
	import { untrack } from 'svelte';
	import { api } from '../../api';
	import { clock } from '../../clock';
	import { FREQUENCIES, hygieneError, WEEKDAYS, weekdayName } from '../../hygiene';
	import { t, todayTunis, translate } from '../../i18n.svelte';
	import type { Equipment, Frequency, HygieneTask } from '../../types/hygiene';
	import Modal from '../daily/Modal.svelte';

	type Props = {
		task?: HygieneTask | null;
		equipment: Equipment[];
		onsaved: (t: HygieneTask) => void;
		ondeleted?: (id: number) => void;
		onclose: () => void;
	};
	let { task = null, equipment, onsaved, ondeleted, onclose }: Props = $props();

	const start = untrack(() => task);
	let title = $state(start?.title ?? '');
	let equipmentId = $state(start?.equipmentId ? String(start.equipmentId) : '');
	let frequency = $state<Frequency>(start?.frequency ?? 'daily');
	let weekday = $state(String(start?.weekday ?? 1));
	let intervalDays = $state<number>(start?.intervalDays ?? 7);
	let startsOn = $state(start?.startsOn ?? todayTunis(clock.now()));
	let instructions = $state(start?.instructions ?? '');
	let active = $state(start?.active ?? true);
	let error = $state('');
	let busy = $state(false);

	async function save(e: SubmitEvent) {
		e.preventDefault();
		if (!title.trim()) return void (error = t('errors.validation'));
		busy = true;
		error = '';
		const body: Record<string, unknown> = {
			title: title.trim(),
			equipmentId: equipmentId ? Number(equipmentId) : null,
			frequency,
			weekday: frequency === 'weekly' ? Number(weekday) : null,
			intervalDays: frequency === 'every_n_days' ? Math.round(Number(intervalDays)) : null,
			startsOn,
			instructions: instructions.trim()
		};
		if (start) body.active = active;
		try {
			onsaved(
				start
					? await api<HygieneTask>(`/api/hygiene/tasks/${start.id}`, { method: 'PATCH', json: body })
					: await api<HygieneTask>('/api/hygiene/tasks', { method: 'POST', json: body })
			);
		} catch (err) {
			error = hygieneError(err);
		} finally {
			busy = false;
		}
	}

	async function remove() {
		if (!start) return;
		busy = true;
		error = '';
		try {
			await api(`/api/hygiene/tasks/${start.id}`, { method: 'DELETE' });
			ondeleted?.(start.id);
		} catch (err) {
			error = hygieneError(err);
		} finally {
			busy = false;
		}
	}
</script>

<Modal title={start ? t('hygiene.task.editTitle') : t('hygiene.task.title')} {onclose} guard>
	<form id="task-form" class="flex flex-col gap-4" onsubmit={save} novalidate>
		<label class="label">{t('hygiene.task.name')}<input class="input" bind:value={title} maxlength="120" autocomplete="off" dir="auto" data-autofocus /></label>
		<label class="label"
			>{t('hygiene.task.equipment')}
			<select class="input" bind:value={equipmentId}>
				<option value="">{t('hygiene.task.noEquipment')}</option>
				{#each equipment.filter((e) => e.active || String(e.id) === equipmentId) as e (e.id)}<option value={String(e.id)}>{e.name}</option>{/each}
			</select>
		</label>
		<div class="grid grid-cols-2 gap-3">
			<label class="label"
				>{t('hygiene.task.frequency')}
				<select class="input" bind:value={frequency}>
					{#each FREQUENCIES as f (f)}<option value={f}>{translate(`hygiene.frequencies.${f}`)}</option>{/each}
				</select>
			</label>
			{#if frequency === 'weekly'}
				<label class="label"
					>{t('hygiene.task.weekday')}
					<select class="input" bind:value={weekday}>
						{#each WEEKDAYS as d (d)}<option value={d}>{weekdayName(d)}</option>{/each}
					</select>
				</label>
			{:else if frequency === 'every_n_days'}
				<label class="label"
					>{t('hygiene.task.interval')}<input class="input tabular-nums" type="number" inputmode="numeric" min="2" max="365" bind:value={intervalDays} /></label
				>
			{/if}
		</div>
		<label class="label">{t('hygiene.task.startsOn')}<input class="input" type="date" bind:value={startsOn} /></label>
		<label class="label">{t('hygiene.task.instructions')}<textarea class="input min-h-20" bind:value={instructions} maxlength="1000" dir="auto"></textarea></label>
		{#if start}
			<label class="inline-flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" class="h-5 w-5 accent-brand-700" bind:checked={active} />{t('hygiene.task.active')}</label>
		{/if}
		{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}
		{#if start}
			<button type="button" class="btn-secondary min-h-11 self-start text-sm text-rose-800" disabled={busy} onclick={remove}>{t('hygiene.task.delete')}</button>
		{/if}
	</form>
	{#snippet footer()}
		<button type="button" class="btn-secondary" onclick={onclose}>{t('common.cancel')}</button>
		<button type="submit" form="task-form" class="btn-primary" disabled={busy}>{t('hygiene.task.save')}</button>
	{/snippet}
</Modal>
