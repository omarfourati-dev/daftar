<script lang="ts">
	import { page } from '$app/state';
	import AppShell from '../../lib/components/AppShell.svelte';
	import '#lib/install.svelte'; // keeps the browser's install prompt for /app/installer (it fires once, early)

	let { children } = $props();
</script>

<!-- Pages that must work without a session (e.g. /app/demo) opt out with `+page@.svelte`. -->
<AppShell path={page.url.pathname}>{@render children()}</AppShell>
