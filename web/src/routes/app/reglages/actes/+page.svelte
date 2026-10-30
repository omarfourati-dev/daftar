<script lang="ts">
	/** The practice's acts and prices (`/api/services`): duration, price, bookable online, active. */
	import { onMount, tick } from 'svelte';
	import { api, apiErrorMessage } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { formatMillimes, t } from '#lib/i18n.svelte';
	import { dinarsText, parseDinars } from '#lib/money-input';
	import { validDuration } from '#lib/practice-form';
	import type { Service } from '#lib/types/practice';
	import ConfirmDialog from '../../../../lib/components/ConfirmDialog.svelte';
	import LoadState from '../../../../lib/components/LoadState.svelte';
	import Modal from '../../../../lib/components/Modal.svelte';
	import TextField from '../../../../lib/components/form/TextField.svelte';
	import OwnerOnly from '../../../../lib/components/reglages/OwnerOnly.svelte';

	type Draft = { nameFr: string; nameAr: string; durationMin: string; priceText: string; onlineBookable: boolean; active: boolean };

	let items = $state<Service[]>([]);
	let loading = $state(true);
	let error = $state('');
	let notice = $state('');
	let editing = $state<Service | 'new' | null>(null);
	let draft = $state<Draft>(blank());
	let errors = $state<Partial<Record<keyof Draft | 'form', string>>>({});
	let busy = $state(false);
	let removing = $state<Service | null>(null);
	let removeError = $state('');

	function blank(): Draft {
		return { nameFr: '', nameAr: '', durationMin: '30', priceText: '', onlineBookable: false, active: true };
	}

	async function load() {
		loading = true;
		error = '';
		try {
			items = await api<Service[]>('/api/services');
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			loading = false;
		}
	}
	onMount(() => {
		if (auth.user?.role === 'owner') void load();
	});

	function open(item: Service | 'new') {
		errors = {};
		notice = '';
		editing = item;
		draft =
			item === 'new'
				? blank()
				: {
						nameFr: item.nameFr,
						nameAr: item.nameAr,
						durationMin: String(item.durationMin),
						priceText: dinarsText(item.priceMillimes),
						onlineBookable: item.onlineBookable,
						active: item.active
					};
	}

	async function save(e: SubmitEvent) {
		e.preventDefault();
		errors = {};
		if (!draft.nameFr.trim()) errors.nameFr = t('kit.fieldRequired');
		if (!validDuration(draft.durationMin)) errors.durationMin = t('practice.services.durationInvalid');
		const price = parseDinars(draft.priceText);
		if (Number.isNaN(price)) errors.priceText = t('kit.invalidAmount');
		if (Object.keys(errors).length) {
			await tick();
			document.querySelector<HTMLElement>('[role="dialog"] [aria-invalid="true"]')?.focus();
			return;
		}
		const body = {
			nameFr: draft.nameFr.trim(),
			nameAr: draft.nameAr.trim(),
			durationMin: Number(draft.durationMin),
			priceMillimes: price,
			onlineBookable: draft.onlineBookable,
			active: draft.active
		};
		busy = true;
		try {
			if (editing === 'new') {
				items = [...items, await api<Service>('/api/services', { method: 'POST', json: body })];
			} else if (editing) {
				const before = editing as unknown as Record<string, unknown>;
				const patch = Object.fromEntries(Object.entries(body).filter(([k, v]) => v !== before[k]));
				const id = editing.id;
				const updated = Object.keys(patch).length ? await api<Service>(`/api/services/${id}`, { method: 'PATCH', json: patch }) : editing;
				items = items.map((s) => (s.id === id ? { ...s, ...patch, ...updated } : s));
			}
			editing = null;
			notice = t('reglages.actes.saved');
		} catch (err) {
			errors = { form: apiErrorMessage(err) };
		} finally {
			busy = false;
		}
	}

	async function remove() {
		if (!removing) return;
		const id = removing.id;
		busy = true;
		removeError = '';
		try {
			await api(`/api/services/${id}`, { method: 'DELETE' });
			items = items.filter((s) => s.id !== id);
			removing = null;
			notice = t('reglages.actes.removed');
		} catch (err) {
			removeError = apiErrorMessage(err);
		} finally {
			busy = false;
		}
	}

	const sorted = $derived([...items].sort((a, b) => Number(b.active) - Number(a.active) || a.sort - b.sort));
	const iconButton =
		'inline-flex h-11 w-11 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-ink focus-visible:outline-2 focus-visible:outline-brand-700';
</script>

<OwnerOnly>
	<div class="flex flex-col gap-4">
		<div class="flex flex-wrap items-end justify-between gap-3">
			<div class="flex max-w-2xl flex-col gap-1">
				<h2 class="text-xl font-bold text-ink">{t('reglages.actes.title')}</h2>
				<p class="text-slate-600">{t('reglages.actes.intro')}</p>
			</div>
			<button type="button" class="btn-primary" onclick={() => open('new')}>{t('reglages.actes.add')}</button>
		</div>
		<p role="status" class="min-h-5 text-sm font-medium text-brand-800">{notice}</p>
		<LoadState {loading} {error} onretry={load} />
		{#if !loading && !error}
			{#if items.length === 0}
				<p class="card text-slate-700">{t('reglages.actes.empty')}</p>
			{:else}
				<ul class="flex flex-col gap-2">
					{#each sorted as item (item.id)}
						<li class="card flex items-center gap-3 py-3 {item.active ? '' : 'bg-slate-50'}">
							<div class="flex min-w-0 flex-1 flex-col gap-1">
								<div class="flex flex-wrap items-baseline gap-x-3">
									<h3 class="font-semibold {item.active ? 'text-ink' : 'text-slate-500'}">{item.nameFr}</h3>
									{#if item.nameAr}<span lang="ar" dir="rtl" class="text-sm text-slate-600">{item.nameAr}</span>{/if}
								</div>
								<div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-700">
									<span class="tabular-nums">{t('kit.minutes', { n: item.durationMin })}</span>
									<span class="tabular-nums">{item.priceMillimes === null ? t('reglages.actes.noPrice') : formatMillimes(item.priceMillimes)}</span>
									{#if item.onlineBookable}<span class="rounded-full bg-brand-50 px-2 py-0.5 font-medium text-brand-800 ring-1 ring-brand-200"
											>{t('reglages.actes.online')}</span
										>{/if}
									{#if !item.active}<span class="rounded-full bg-slate-200 px-2 py-0.5 font-medium text-slate-700">{t('reglages.actes.inactive')}</span>{/if}
								</div>
							</div>
							<button type="button" class={iconButton} aria-label={t('reglages.actes.edit', { name: item.nameFr })} onclick={() => open(item)}>
								<svg viewBox="0 0 20 20" class="h-5 w-5" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8"
									><path d="M13.5 3.5l3 3L7 16H4v-3z" stroke-linejoin="round" /></svg
								>
							</button>
							<button
								type="button"
								class="{iconButton} hover:bg-rose-50 hover:text-rose-700"
								aria-label={t('reglages.actes.remove', { name: item.nameFr })}
								onclick={() => {
									removeError = '';
									removing = item;
								}}
							>
								<svg viewBox="0 0 20 20" class="h-5 w-5" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8"
									><path d="M4 6h12M8 6V4h4v2m-6 0l1 10h6l1-10" stroke-linejoin="round" stroke-linecap="round" /></svg
								>
							</button>
						</li>
					{/each}
				</ul>
			{/if}
		{/if}
	</div>

	<Modal
		open={editing !== null}
		title={editing === 'new' ? t('reglages.actes.add') : editing ? t('reglages.actes.edit', { name: editing.nameFr }) : ''}
		onclose={() => (editing = null)}
	>
		<form class="flex flex-col gap-4" novalidate onsubmit={save}>
			<TextField label={t('practice.services.nameFr')} bind:value={draft.nameFr} error={errors.nameFr} maxlength={120} />
			<TextField label={t('practice.services.nameAr')} bind:value={draft.nameAr} optional dir="rtl" maxlength={120} />
			<div class="grid grid-cols-2 gap-4">
				<TextField label={t('practice.services.duration')} bind:value={draft.durationMin} error={errors.durationMin} inputmode="numeric" dir="ltr" />
				<TextField
					label={t('practice.services.price')}
					bind:value={draft.priceText}
					error={errors.priceText}
					optional
					inputmode="decimal"
					dir="ltr"
					placeholder="35,500"
				/>
			</div>
			<label class="flex min-h-11 cursor-pointer items-center gap-3 font-medium text-slate-700">
				<input type="checkbox" class="h-5 w-5 accent-brand-700" bind:checked={draft.onlineBookable} />
				{t('practice.services.onlineLong')}
			</label>
			<label class="flex min-h-11 cursor-pointer items-center gap-3 font-medium text-slate-700">
				<input type="checkbox" class="h-5 w-5 accent-brand-700" bind:checked={draft.active} />
				{t('reglages.actes.active')}
			</label>
			{#if errors.form}<p role="alert" class="text-sm font-medium text-red-700">{errors.form}</p>{/if}
			<div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
				<button type="button" class="btn-secondary" onclick={() => (editing = null)}>{t('common.cancel')}</button>
				<button type="submit" class="btn-primary" disabled={busy}>{t('reglages.actes.save')}</button>
			</div>
		</form>
	</Modal>

	<ConfirmDialog
		open={!!removing}
		title={removing ? t('reglages.actes.removeTitle', { name: removing.nameFr }) : ''}
		message={t('reglages.actes.removeMessage')}
		confirmLabel={t('reglages.actes.removeConfirm')}
		danger
		{busy}
		error={removeError}
		onconfirm={remove}
		oncancel={() => (removing = null)}
	/>
</OwnerOnly>
