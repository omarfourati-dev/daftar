<script lang="ts">
	/** The address of the waiting-room screen (`/salle/<displayToken>`, only ticket numbers) and a way to renew it. */
	import { onMount } from 'svelte';
	import { api, apiErrorMessage } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { t } from '#lib/i18n.svelte';
	import { mainUrl } from '#lib/links';
	import type { Practice } from '#lib/types/practice';
	import ConfirmDialog from '../../../../lib/components/ConfirmDialog.svelte';
	import CopyLink from '../../../../lib/components/CopyLink.svelte';
	import LoadState from '../../../../lib/components/LoadState.svelte';
	import OwnerOnly from '../../../../lib/components/reglages/OwnerOnly.svelte';

	let token = $state('');
	let loading = $state(true);
	let error = $state('');
	let confirming = $state(false);
	let busy = $state(false);
	let actionError = $state('');
	let notice = $state('');

	async function load() {
		loading = true;
		error = '';
		try {
			token = (await api<Practice>('/api/practice')).displayToken;
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			loading = false;
		}
	}
	onMount(() => {
		if (auth.user?.role === 'owner') void load();
	});

	async function regenerate() {
		busy = true;
		actionError = '';
		try {
			const answer = await api<{ displayToken?: string; token?: string }>('/api/practice/display-token', { method: 'POST' });
			token = answer.displayToken ?? answer.token ?? token;
			confirming = false;
			notice = t('reglages.ecran.regenerated');
		} catch (err) {
			actionError = apiErrorMessage(err);
		} finally {
			busy = false;
		}
	}
</script>

<OwnerOnly>
	<div class="flex flex-col gap-4">
		<h2 class="text-xl font-bold text-ink">{t('reglages.ecran.title')}</h2>
		<p class="max-w-2xl text-slate-600">{t('reglages.ecran.intro')}</p>
		<LoadState {loading} {error} onretry={load} />
		{#if token}
			<div class="card flex flex-col gap-4">
				<CopyLink label={t('reglages.ecran.link')} url={mainUrl(`/salle/${token}`)} openable />
				<button type="button" class="btn-secondary self-start" onclick={() => (confirming = true)}>{t('reglages.ecran.regenerate')}</button>
				<p role="status" class="text-sm font-medium text-brand-800">{notice}</p>
			</div>
		{/if}
	</div>
	<ConfirmDialog
		open={confirming}
		title={t('reglages.ecran.regenerateTitle')}
		message={t('reglages.ecran.regenerateMessage')}
		confirmLabel={t('reglages.ecran.regenerateConfirm')}
		{busy}
		error={actionError}
		onconfirm={regenerate}
		oncancel={() => (confirming = false)}
	/>
</OwnerOnly>
