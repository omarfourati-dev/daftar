<script lang="ts">
	/**
	 * `/` exists in the SPA only for practice sub-domains: `<slug>.<base>/` is that practice's booking page
	 * (section 11.3). On the main domain the server delivers the landing page, so a client-side visit to `/` reloads
	 * from the server – at most once every few seconds, so a dev server that answers `/` itself cannot loop.
	 */
	import { onMount } from 'svelte';
	import { bookingDeps, useBookingManifest } from '#lib/booking';
	import { currentPracticeSlug } from '#lib/host';
	import { applyLocaleFromQuery, t } from '#lib/i18n.svelte';
	import BookingPage from '../lib/components/booking/BookingPage.svelte';

	const slug = currentPracticeSlug();
	const KEY = 'daftar.rootRedirect';
	let stay = $state(false);
	applyLocaleFromQuery();

	if (!slug) {
		let last = 0;
		try {
			last = Number(sessionStorage.getItem(KEY) ?? 0);
			sessionStorage.setItem(KEY, String(Date.now()));
		} catch {
			/* private mode */
		}
		if (Date.now() - last < 5000) stay = true;
		else bookingDeps.replace('/');
	}

	onMount(() => {
		if (slug) useBookingManifest();
	});
</script>

{#if slug}
	<BookingPage {slug} />
{:else if stay}
	<main class="mx-auto max-w-sm px-4 py-16 text-center">
		<a class="font-semibold text-brand-700 underline" href="/" data-sveltekit-reload>{t('common.toLanding')}</a>
	</main>
{/if}
