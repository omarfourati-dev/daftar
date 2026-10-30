<script lang="ts">
	/** Admin – feedback sent from the practices with the "Une idée ? Un problème ?" button (story J2). */
	import { onMount } from 'svelte';
	import { api, apiErrorMessage } from '#lib/api';
	import { formatDateTime, t } from '#lib/i18n.svelte';
	import type { FeedbackItem } from '#lib/types/admin';
	import AdminTabs from '../../../../lib/components/admin/AdminTabs.svelte';
	import ConfirmDialog from '../../../../lib/components/ConfirmDialog.svelte';
	import LoadState from '../../../../lib/components/LoadState.svelte';

	let items = $state<FeedbackItem[]>([]);
	let loading = $state(true);
	let error = $state('');
	let removing = $state<FeedbackItem | null>(null);
	let removeError = $state('');
	let busy = $state(false);

	async function load() {
		loading = true;
		error = '';
		try {
			items = await api<FeedbackItem[]>('/api/admin/feedback');
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			loading = false;
		}
	}
	onMount(load);

	async function remove() {
		if (!removing) return;
		busy = true;
		removeError = '';
		try {
			await api(`/api/admin/feedback/${removing.id}`, { method: 'DELETE' });
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

<svelte:head><title>{t('admin.feedback.title')} · Daftar</title></svelte:head>

<AdminTabs current="feedback" />
<h2 class="sr-only">{t('admin.feedback.title')}</h2>

<LoadState {loading} {error} onretry={load} />

{#if !loading && !error}
	{#if items.length === 0}
		<p class="card text-slate-700">{t('admin.feedback.empty')}</p>
	{:else}
		<div class="flex flex-col gap-3">
			{#each items as item (item.id)}
				<article class="card flex flex-col gap-2">
					<p class="whitespace-pre-line text-ink">{item.message}</p>
					<div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-600">
						<span>{t('admin.feedback.from', { practice: item.practiceName ?? t('admin.feedback.unknown'), user: item.userName ?? '—' })}</span>
						<span dir="auto">{t('admin.feedback.page', { page: item.page })}</span>
						<span class="tabular-nums">{formatDateTime(item.createdAt)}</span>
						<button
							type="button"
							class="ms-auto min-h-9 font-semibold text-rose-700 hover:underline"
							aria-label={t('admin.feedback.deleteLabel', { date: formatDateTime(item.createdAt) })}
							onclick={() => {
								removeError = '';
								removing = item;
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
	title={t('admin.feedback.deleteTitle')}
	message={t('admin.feedback.deleteMessage')}
	confirmLabel={t('admin.feedback.deleteConfirm')}
	danger
	{busy}
	error={removeError}
	onconfirm={remove}
	oncancel={() => (removing = null)}
/>
