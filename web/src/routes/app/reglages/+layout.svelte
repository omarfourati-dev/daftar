<script lang="ts">
	import { page } from '$app/state';
	import { t } from '#lib/i18n.svelte';
	import ReglagesNav from '../../../lib/components/reglages/ReglagesNav.svelte';

	let { children } = $props();
</script>

<svelte:head><title>{t('reglages.title')} · Daftar</title></svelte:head>

<h1 class="mb-4 text-2xl font-bold text-ink">{t('reglages.title')}</h1>
<div class="grid gap-6 lg:grid-cols-[13rem_minmax(0,1fr)] lg:items-start">
	<div class="min-w-0 lg:sticky lg:top-4">
		<ReglagesNav path={page.url.pathname} />
	</div>
	<div class="min-w-0">{@render children()}</div>
</div>
