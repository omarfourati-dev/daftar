<script lang="ts">
	/** Loading and error state of a page section: a calm status line, or the error with "Réessayer". */
	import { t } from '../i18n.svelte';

	let { loading, error, onretry }: { loading: boolean; error: string; onretry?: () => void } = $props();
</script>

{#if loading}
	<div role="status" class="flex items-center gap-3 py-8 text-slate-600">
		<span class="h-5 w-5 animate-spin rounded-full border-2 border-brand-200 border-t-brand-700 motion-reduce:animate-none" aria-hidden="true"
		></span>
		{t('common.loading')}
	</div>
{:else if error}
	<div class="card flex flex-col items-start gap-3 border-rose-200 bg-rose-50">
		<p role="alert" class="text-rose-900">{error}</p>
		{#if onretry}<button type="button" class="btn-secondary" onclick={onretry}>{t('common.retry')}</button>{/if}
	</div>
{/if}
