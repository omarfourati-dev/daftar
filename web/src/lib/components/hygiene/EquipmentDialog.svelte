<script lang="ts">
	/** Create or change a piece of equipment (assistant, owner): name, type, serial number, note, in service. */
	import { untrack } from 'svelte';
	import { api } from '../../api';
	import { hygieneError, KINDS, kindLabel } from '../../hygiene';
	import { t } from '../../i18n.svelte';
	import type { Equipment, EquipmentKind } from '../../types/hygiene';
	import Modal from '../daily/Modal.svelte';

	type Props = { item?: Equipment | null; onsaved: (e: Equipment) => void; ondeleted?: (id: number) => void; onclose: () => void };
	let { item = null, onsaved, ondeleted, onclose }: Props = $props();

	const start = untrack(() => item);
	let name = $state(start?.name ?? '');
	let kind = $state<EquipmentKind>(start?.kind ?? 'autre');
	let serialNumber = $state(start?.serialNumber ?? '');
	let note = $state(start?.note ?? '');
	let active = $state(start?.active ?? true);
	let error = $state('');
	let busy = $state(false);

	async function save(e: SubmitEvent) {
		e.preventDefault();
		if (!name.trim()) return void (error = t('errors.validation'));
		busy = true;
		error = '';
		const body = { name: name.trim(), kind, serialNumber: serialNumber.trim(), note: note.trim(), active };
		try {
			onsaved(
				start
					? await api<Equipment>(`/api/hygiene/equipment/${start.id}`, { method: 'PATCH', json: body })
					: await api<Equipment>('/api/hygiene/equipment', { method: 'POST', json: body })
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
			await api(`/api/hygiene/equipment/${start.id}`, { method: 'DELETE' });
			ondeleted?.(start.id);
		} catch (err) {
			error = hygieneError(err);
		} finally {
			busy = false;
		}
	}
</script>

<Modal title={start ? t('hygiene.equipmentDialog.editTitle') : t('hygiene.equipmentDialog.title')} {onclose} guard>
	<form id="equipment-form" class="flex flex-col gap-4" onsubmit={save} novalidate>
		<label class="label">{t('hygiene.equipmentDialog.name')}<input class="input" bind:value={name} maxlength="120" autocomplete="off" dir="auto" data-autofocus /></label>
		<div class="grid grid-cols-2 gap-3">
			<label class="label"
				>{t('hygiene.equipmentDialog.kind')}
				<select class="input" bind:value={kind}>
					{#each KINDS as k (k)}<option value={k}>{kindLabel(k)}</option>{/each}
				</select>
			</label>
			<label class="label">{t('hygiene.equipmentDialog.serialNumber')}<input class="input" bind:value={serialNumber} maxlength="60" autocomplete="off" dir="ltr" /></label>
		</div>
		<label class="label">{t('hygiene.equipmentDialog.note')}<input class="input" bind:value={note} maxlength="500" autocomplete="off" dir="auto" /></label>
		{#if start}
			<label class="inline-flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" class="h-5 w-5 accent-brand-700" bind:checked={active} />{t('hygiene.equipmentDialog.active')}</label>
		{/if}
		{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}
		{#if start && start.tasks === 0}
			<button type="button" class="btn-secondary min-h-11 self-start text-sm text-rose-800" disabled={busy} onclick={remove}>{t('hygiene.equipmentDialog.delete')}</button>
		{/if}
	</form>
	{#snippet footer()}
		<button type="button" class="btn-secondary" onclick={onclose}>{t('common.cancel')}</button>
		<button type="submit" form="equipment-form" class="btn-primary" disabled={busy}>{t('hygiene.equipmentDialog.save')}</button>
	{/snippet}
</Modal>
