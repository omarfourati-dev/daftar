<script lang="ts">
	/** `/r/<slug>` – the same booking page on the main domain (links, tests, fallback; section 11.3). */
	import { applyLocaleFromQuery } from '#lib/i18n.svelte';
	import BookingPage from '../../../lib/components/booking/BookingPage.svelte';

	let { data }: { data: { slug: string } } = $props();
	applyLocaleFromQuery();
</script>

<BookingPage slug={data.slug} />
