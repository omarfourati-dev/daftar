<script lang="ts">
	/** Export of all practice data as JSON (story E4) and the way to the Excel import (E5). Owner only. */
	import { apiBlob, apiErrorMessage } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { saveBlob } from '#lib/download';
	import { t, todayTunis } from '#lib/i18n.svelte';
	import OwnerOnly from '../../../../lib/components/reglages/OwnerOnly.svelte';

	let busy = $state(false);
	let notice = $state('');
	let error = $state('');

	async function download() {
		busy = true;
		notice = '';
		error = '';
		try {
			const blob = await apiBlob('/api/practice/export');
			saveBlob(blob, `daftar-export-${auth.user?.practice?.slug ?? 'cabinet'}-${todayTunis()}.json`);
			notice = t('reglages.donnees.exported');
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			busy = false;
		}
	}
</script>

<OwnerOnly>
	<div class="flex flex-col gap-6">
		<h2 class="text-xl font-bold text-ink">{t('reglages.donnees.title')}</h2>
		<section class="card flex flex-col gap-3" aria-labelledby="d-export">
			<h3 id="d-export" class="font-semibold text-ink">{t('reglages.donnees.exportTitle')}</h3>
			<p class="max-w-2xl text-sm text-slate-600">{t('reglages.donnees.exportText')}</p>
			<div class="flex flex-wrap items-center gap-3">
				<button type="button" class="btn-primary" disabled={busy} onclick={download}
					>{busy ? t('reglages.donnees.exporting') : t('reglages.donnees.exportButton')}</button
				>
				<p role="status" class="text-sm font-medium text-brand-800">{notice}</p>
			</div>
			{#if error}<p role="alert" class="text-sm font-medium text-red-700">{error}</p>{/if}
		</section>
		<section class="card flex flex-col gap-3" aria-labelledby="d-import">
			<h3 id="d-import" class="font-semibold text-ink">{t('reglages.donnees.importTitle')}</h3>
			<p class="max-w-2xl text-sm text-slate-600">{t('reglages.donnees.importText')}</p>
			<a class="btn-secondary self-start" href="/app/import">{t('reglages.donnees.importLink')}</a>
		</section>
	</div>
</OwnerOnly>
