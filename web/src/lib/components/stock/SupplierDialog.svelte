<script lang="ts">
	/** Create or change a supplier (assistant, owner): name, phone, WhatsApp (orders go there), note, active. */
	import { untrack } from 'svelte';
	import { api } from '../../api';
	import { t } from '../../i18n.svelte';
	import { stockError } from '../../stock';
	import type { Supplier } from '../../types/stock';
	import Modal from '../daily/Modal.svelte';

	type Props = {
		supplier?: Supplier | null;
		initialName?: string;
		onsaved: (s: Supplier) => void;
		ondeleted?: (id: number) => void;
		onclose: () => void;
	};
	let { supplier = null, initialName = '', onsaved, ondeleted, onclose }: Props = $props();

	const start = untrack(() => supplier);
	let name = $state(start?.name ?? untrack(() => initialName));
	let phone = $state(start?.phone ?? '');
	let whatsapp = $state(start?.whatsapp ?? '');
	let note = $state(start?.note ?? '');
	let active = $state(start?.active ?? true);
	let error = $state('');
	let busy = $state(false);

	async function save(e: SubmitEvent) {
		e.preventDefault();
		if (!name.trim()) return void (error = t('errors.validation'));
		busy = true;
		error = '';
		const body = { name: name.trim(), phone: phone.trim(), whatsapp: whatsapp.trim(), note: note.trim(), active };
		try {
			onsaved(
				start
					? await api<Supplier>(`/api/stock/suppliers/${start.id}`, { method: 'PATCH', json: body })
					: await api<Supplier>('/api/stock/suppliers', { method: 'POST', json: body })
			);
		} catch (err) {
			error = stockError(err);
		} finally {
			busy = false;
		}
	}

	async function remove() {
		if (!start) return;
		busy = true;
		error = '';
		try {
			await api(`/api/stock/suppliers/${start.id}`, { method: 'DELETE' });
			ondeleted?.(start.id);
		} catch (err) {
			error = stockError(err);
		} finally {
			busy = false;
		}
	}
</script>

<Modal title={start ? t('stock.suppliers.dialog.editTitle') : t('stock.suppliers.dialog.title')} {onclose} guard>
	<form id="supplier-form" class="flex flex-col gap-4" onsubmit={save} novalidate>
		<label class="label">{t('stock.suppliers.dialog.name')}<input class="input" bind:value={name} maxlength="120" autocomplete="off" data-autofocus /></label>
		<div class="grid gap-3 sm:grid-cols-2">
			<label class="label"
				>{t('stock.suppliers.dialog.phone')}<input class="input" type="tel" dir="ltr" inputmode="tel" bind:value={phone} maxlength="40" autocomplete="off" /></label
			>
			<label class="label"
				>{t('stock.suppliers.dialog.whatsapp')}<input class="input" type="tel" dir="ltr" inputmode="tel" bind:value={whatsapp} maxlength="40" autocomplete="off" /></label
			>
		</div>
		<label class="label">{t('stock.suppliers.dialog.note')}<input class="input" bind:value={note} maxlength="500" autocomplete="off" /></label>
		{#if start}
			<label class="inline-flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" class="h-5 w-5 accent-brand-700" bind:checked={active} />{t('stock.suppliers.dialog.active')}</label>
		{/if}
		{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}
		{#if start && start.products === 0}
			<button type="button" class="btn-secondary min-h-11 self-start text-sm text-rose-800" disabled={busy} onclick={remove}>{t('stock.suppliers.dialog.delete')}</button>
		{/if}
	</form>
	{#snippet footer()}
		<button type="button" class="btn-secondary" onclick={onclose}>{t('common.cancel')}</button>
		<button type="submit" form="supplier-form" class="btn-primary" disabled={busy}>{t('stock.suppliers.dialog.save')}</button>
	{/snippet}
</Modal>
