<script lang="ts">
	import '../app.css';
	import '@fontsource/ibm-plex-sans-arabic/400.css';
	import '@fontsource/ibm-plex-sans-arabic/600.css';
	import '@fontsource/ibm-plex-sans-arabic/700.css';
	import { dev } from '$app/env';
	import { i18n, t } from '#lib/i18n.svelte';
	import { pwa } from '#lib/pwa.svelte';

	let { children } = $props();
	let pwaStarted = false;

	// <html lang dir> follows the chosen language (also on the first paint after a reload)
	$effect(() => {
		void i18n.locale;
		i18n.apply();
	});

	$effect(() => {
		if (dev || pwaStarted) return;
		pwaStarted = true;
		void pwa.register().catch(() => undefined);
	});
</script>

{#if pwa.updateReady}
	<p role="status" class="flex items-center justify-center gap-3 bg-brand-700 px-4 py-2 text-sm text-white print:hidden">
		{t('shell.updateReady')}
		<button type="button" class="rounded bg-white px-3 py-1 font-semibold text-brand-700" onclick={() => pwa.applyUpdate()}
			>{t('shell.reload')}</button
		>
	</p>
{/if}
{@render children()}
