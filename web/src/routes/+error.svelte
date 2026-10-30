<script lang="ts">
	import { page } from '$app/state';
	import { t } from '#lib/i18n.svelte';
</script>

<main class="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-4 px-4 text-center">
	<p class="text-5xl font-bold text-brand-700">{page.status}</p>
	<h1 class="text-xl font-semibold">{page.status === 404 ? t('errors.not_found') : t('errors.generic')}</h1>
	<a class="btn-primary" href="/app">{t('nav.today')}</a>
</main>
