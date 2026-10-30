<script lang="ts">
	/** Temporary content of a page that a feature agent will build. */
	import { t, type MessageKey } from '../i18n.svelte';

	let { title }: { title: MessageKey } = $props();
</script>

<svelte:head><title>{t(title)} · Daftar</title></svelte:head>

<h1 class="text-2xl font-bold">{t(title)}</h1>
<p class="mt-2 text-slate-600">{t('common.comingSoon')}</p>
