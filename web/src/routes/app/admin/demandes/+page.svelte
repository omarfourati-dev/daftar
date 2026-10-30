<script lang="ts">
	/** Admin – pilot requests from the landing form (story I2): call back, start the wizard pre-filled, delete. */
	import { onMount } from 'svelte';
	import { api, apiErrorMessage, deps } from '#lib/api';
	import { formatDateTime, t } from '#lib/i18n.svelte';
	import { telUrl, whatsappUrl } from '#lib/links';
	import type { PilotRequest } from '#lib/types/admin';
	import AdminTabs from '../../../../lib/components/admin/AdminTabs.svelte';
	import ConfirmDialog from '../../../../lib/components/ConfirmDialog.svelte';
	import LoadState from '../../../../lib/components/LoadState.svelte';

	let items = $state<PilotRequest[]>([]);
	let loading = $state(true);
	let error = $state('');
	let removing = $state<PilotRequest | null>(null);
	let removeError = $state('');
	let busy = $state(false);

	async function load() {
		loading = true;
		error = '';
		try {
			items = await api<PilotRequest[]>('/api/admin/pilot-requests');
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			loading = false;
		}
	}
	onMount(load);

	function startWizard(request: PilotRequest) {
		try {
			sessionStorage.setItem(
				'daftar.wizardPrefill',
				JSON.stringify({ name: request.name, practice: request.practice, city: request.city, phone: request.phone, email: request.email })
			);
		} catch {
			/* private mode: the wizard starts empty */
		}
		void deps.goto('/app/admin/cabinets/nouveau');
	}

	async function remove() {
		if (!removing) return;
		busy = true;
		removeError = '';
		try {
			await api(`/api/admin/pilot-requests/${removing.id}`, { method: 'DELETE' });
			const gone = removing.id;
			items = items.filter((i) => i.id !== gone);
			removing = null;
		} catch (err) {
			removeError = apiErrorMessage(err);
		} finally {
			busy = false;
		}
	}
</script>

<svelte:head><title>{t('admin.pilots.title')} · Daftar</title></svelte:head>

<AdminTabs current="pilots" />
<h2 class="sr-only">{t('admin.pilots.title')}</h2>

<LoadState {loading} {error} onretry={load} />

{#if !loading && !error}
	{#if items.length === 0}
		<p class="card text-slate-700">{t('admin.pilots.empty')}</p>
	{:else}
		<div class="grid gap-4 lg:grid-cols-2">
			{#each items as request (request.id)}
				<article class="card flex flex-col gap-3">
					<header class="flex flex-col gap-0.5">
						<h3 class="text-lg font-bold text-ink">{request.practice}</h3>
						<p class="text-slate-700">{request.name} · {request.city}</p>
						<p class="flex flex-wrap gap-x-3 text-sm text-slate-500">
							<span>{t('admin.pilots.received', { date: formatDateTime(request.createdAt) })}</span>
							<span>{t('admin.pilots.language', { lang: request.lang === 'ar' ? t('common.arabic') : t('common.french') })}</span>
						</p>
					</header>
					{#if request.message}<p class="rounded-lg bg-slate-50 p-3 whitespace-pre-line text-slate-800">{request.message}</p>{/if}
					<p class="flex flex-wrap gap-x-4 text-sm">
						<span dir="ltr" class="tabular-nums">{request.phone}</span>
						{#if request.email}<a class="text-brand-700 underline" href="mailto:{request.email}">{request.email}</a>{/if}
					</p>
					<div class="flex flex-wrap gap-2">
						<a class="btn-secondary" href={telUrl(request.phone)}>{t('admin.pilots.call')}</a>
						<a class="btn-secondary" href={whatsappUrl('', request.phone)} target="_blank" rel="noopener">{t('admin.pilots.whatsapp')}</a>
						<button
							type="button"
							class="btn-primary"
							aria-label={t('admin.pilots.createLabel', { name: request.practice })}
							onclick={() => startWizard(request)}>{t('admin.pilots.createPractice')}</button
						>
						<button
							type="button"
							class="btn-secondary text-rose-700"
							aria-label={t('admin.pilots.deleteLabel', { name: request.practice })}
							onclick={() => {
								removeError = '';
								removing = request;
							}}>{t('common.delete')}</button
						>
					</div>
				</article>
			{/each}
		</div>
	{/if}
{/if}

<ConfirmDialog
	open={!!removing}
	title={removing ? t('admin.pilots.deleteTitle', { name: removing.name }) : ''}
	message={t('admin.pilots.deleteMessage')}
	confirmLabel={t('admin.pilots.deleteConfirm')}
	danger
	{busy}
	error={removeError}
	onconfirm={remove}
	oncancel={() => (removing = null)}
/>
