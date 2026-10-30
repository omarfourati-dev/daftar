<script lang="ts">
	/** Practitioners (`/api/practitioners`): the people who treat patients – not accounts (section 11.2). */
	import { onMount, tick } from 'svelte';
	import { api, apiErrorMessage } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { SPECIALTIES } from '#lib/catalog';
	import { t, translate } from '#lib/i18n.svelte';
	import type { Practitioner } from '#lib/types/practice';
	import ConfirmDialog from '../../../../lib/components/ConfirmDialog.svelte';
	import LoadState from '../../../../lib/components/LoadState.svelte';
	import Modal from '../../../../lib/components/Modal.svelte';
	import TextField from '../../../../lib/components/form/TextField.svelte';
	import OwnerOnly from '../../../../lib/components/reglages/OwnerOnly.svelte';

	const COLORS = ['#0f766e', '#0369a1', '#4338ca', '#7c3aed', '#be185d', '#b45309', '#15803d', '#334155'];
	type Draft = { title: string; name: string; specialty: string; color: string; onlineBookable: boolean; active: boolean };

	let items = $state<Practitioner[]>([]);
	let loading = $state(true);
	let error = $state('');
	let notice = $state('');
	let editing = $state<Practitioner | 'new' | null>(null);
	let draft = $state<Draft>(blank());
	let errors = $state<{ name?: string; form?: string }>({});
	let busy = $state(false);
	let removing = $state<Practitioner | null>(null);
	let removeError = $state('');

	function blank(): Draft {
		const used = new Set(items.map((p) => p.color));
		return { title: 'Dr.', name: '', specialty: '', color: COLORS.find((c) => !used.has(c)) ?? COLORS[0], onlineBookable: true, active: true };
	}

	async function load() {
		loading = true;
		error = '';
		try {
			items = await api<Practitioner[]>('/api/practitioners');
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			loading = false;
		}
	}
	onMount(() => {
		if (auth.user?.role === 'owner') void load();
	});

	const fullName = (p: { title: string; name: string }) => `${p.title ?? ''} ${p.name}`.trim();

	function open(item: Practitioner | 'new') {
		errors = {};
		notice = '';
		editing = item;
		draft =
			item === 'new'
				? blank()
				: { title: item.title ?? '', name: item.name, specialty: item.specialty ?? '', color: item.color, onlineBookable: item.onlineBookable, active: item.active };
	}

	async function save(e: SubmitEvent) {
		e.preventDefault();
		errors = draft.name.trim() ? {} : { name: t('kit.fieldRequired') };
		if (errors.name) {
			await tick();
			document.querySelector<HTMLElement>('[role="dialog"] [aria-invalid="true"]')?.focus();
			return;
		}
		const body = {
			title: draft.title.trim(),
			name: draft.name.trim(),
			specialty: draft.specialty || null,
			color: draft.color,
			onlineBookable: draft.onlineBookable,
			active: draft.active
		};
		busy = true;
		try {
			if (editing === 'new') {
				items = [...items, await api<Practitioner>('/api/practitioners', { method: 'POST', json: body })];
			} else if (editing) {
				const before = editing as unknown as Record<string, unknown>;
				const patch = Object.fromEntries(Object.entries(body).filter(([k, v]) => v !== (before[k] ?? (k === 'specialty' ? null : before[k]))));
				const id = editing.id;
				const updated = Object.keys(patch).length ? await api<Practitioner>(`/api/practitioners/${id}`, { method: 'PATCH', json: patch }) : editing;
				items = items.map((p) => (p.id === id ? { ...p, ...patch, ...updated } : p));
			}
			editing = null;
			notice = t('reglages.praticiens.saved');
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
			await api(`/api/practitioners/${id}`, { method: 'DELETE' });
			items = items.filter((p) => p.id !== id);
			removing = null;
			notice = t('reglages.praticiens.removed');
		} catch (err) {
			removeError = apiErrorMessage(err);
		} finally {
			busy = false;
		}
	}

	const specialtyOptions = $derived([
		{ value: '', label: t('practice.practitioners.samePractice') },
		...SPECIALTIES.map((s) => ({ value: s, label: t(`specialty.${s}`) }))
	]);
	const iconButton =
		'inline-flex h-11 w-11 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-ink focus-visible:outline-2 focus-visible:outline-brand-700';
</script>

<OwnerOnly>
	<div class="flex flex-col gap-4">
		<div class="flex flex-wrap items-end justify-between gap-3">
			<div class="flex max-w-2xl flex-col gap-1">
				<h2 class="text-xl font-bold text-ink">{t('reglages.praticiens.title')}</h2>
				<p class="text-slate-600">{t('reglages.praticiens.intro')}</p>
			</div>
			<button type="button" class="btn-primary" onclick={() => open('new')}>{t('reglages.praticiens.add')}</button>
		</div>
		<p role="status" class="min-h-5 text-sm font-medium text-brand-800">{notice}</p>
		<LoadState {loading} {error} onretry={load} />
		{#if !loading && !error}
			{#if items.length === 0}
				<p class="card text-slate-700">{t('reglages.praticiens.empty')}</p>
			{:else}
				<ul class="grid gap-2 md:grid-cols-2">
					{#each items as item (item.id)}
						<li class="card flex items-center gap-3 py-3 {item.active ? '' : 'bg-slate-50'}">
							<span class="h-9 w-2 shrink-0 rounded-full" style="background:{item.color}" aria-hidden="true"></span>
							<div class="flex min-w-0 flex-1 flex-col gap-1">
								<h3 class="font-semibold {item.active ? 'text-ink' : 'text-slate-500'}">{fullName(item)}</h3>
								<div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-700">
									{#if item.specialty}<span>{translate(`specialty.${item.specialty}`) ?? item.specialty}</span>{/if}
									{#if item.onlineBookable}<span class="rounded-full bg-brand-50 px-2 py-0.5 font-medium text-brand-800 ring-1 ring-brand-200"
											>{t('reglages.actes.online')}</span
										>{/if}
									{#if !item.active}<span class="rounded-full bg-slate-200 px-2 py-0.5 font-medium text-slate-700">{t('reglages.praticiens.inactive')}</span>{/if}
								</div>
							</div>
							<button type="button" class={iconButton} aria-label={t('reglages.praticiens.edit', { name: fullName(item) })} onclick={() => open(item)}>
								<svg viewBox="0 0 20 20" class="h-5 w-5" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8"
									><path d="M13.5 3.5l3 3L7 16H4v-3z" stroke-linejoin="round" /></svg
								>
							</button>
							<button
								type="button"
								class="{iconButton} hover:bg-rose-50 hover:text-rose-700"
								aria-label={t('reglages.praticiens.remove', { name: fullName(item) })}
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
		title={editing === 'new' ? t('reglages.praticiens.add') : editing ? t('reglages.praticiens.edit', { name: fullName(editing) }) : ''}
		onclose={() => (editing = null)}
	>
		<form class="flex flex-col gap-4" novalidate onsubmit={save}>
			<div class="grid grid-cols-[6rem_minmax(0,1fr)] gap-4">
				<TextField label={t('practice.practitioners.title')} bind:value={draft.title} maxlength={20} />
				<TextField label={t('practice.practitioners.name')} bind:value={draft.name} error={errors.name} maxlength={120} />
			</div>
			<TextField label={t('practice.practitioners.specialty')} bind:value={draft.specialty} options={specialtyOptions} />
			<fieldset class="flex flex-col gap-2">
				<legend class="text-sm font-medium text-slate-700">{t('reglages.praticiens.color')}</legend>
				<div class="flex flex-wrap gap-2">
					{#each COLORS as color (color)}
						<label class="cursor-pointer">
							<input type="radio" name="pr-color" value={color} bind:group={draft.color} class="peer sr-only" aria-label={color} />
							<span
								class="block h-9 w-9 rounded-lg ring-offset-2 peer-checked:ring-2 peer-checked:ring-ink peer-focus-visible:outline-2 peer-focus-visible:outline-offset-4 peer-focus-visible:outline-brand-700"
								style="background:{color}"
							></span>
						</label>
					{/each}
				</div>
			</fieldset>
			<label class="flex min-h-11 cursor-pointer items-center gap-3 font-medium text-slate-700">
				<input type="checkbox" class="h-5 w-5 accent-brand-700" bind:checked={draft.onlineBookable} />
				{t('reglages.praticiens.onlineBookable')}
			</label>
			<label class="flex min-h-11 cursor-pointer items-center gap-3 font-medium text-slate-700">
				<input type="checkbox" class="h-5 w-5 accent-brand-700" bind:checked={draft.active} />
				{t('reglages.praticiens.active')}
			</label>
			{#if errors.form}<p role="alert" class="text-sm font-medium text-red-700">{errors.form}</p>{/if}
			<div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
				<button type="button" class="btn-secondary" onclick={() => (editing = null)}>{t('common.cancel')}</button>
				<button type="submit" class="btn-primary" disabled={busy}>{t('reglages.praticiens.save')}</button>
			</div>
		</form>
	</Modal>

	<ConfirmDialog
		open={!!removing}
		title={removing ? t('reglages.praticiens.removeTitle', { name: fullName(removing) }) : ''}
		message={t('reglages.praticiens.removeMessage')}
		confirmLabel={t('reglages.praticiens.removeConfirm')}
		danger
		{busy}
		error={removeError}
		onconfirm={remove}
		oncancel={() => (removing = null)}
	/>
</OwnerOnly>
