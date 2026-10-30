<script lang="ts">
	/** Renders its content only for the practice owner; everybody else reads why. */
	import type { Snippet } from 'svelte';
	import { auth } from '../../auth.svelte';
	import { t } from '../../i18n.svelte';

	let { children }: { children: Snippet } = $props();
</script>

{#if auth.user?.role === 'owner'}
	{@render children()}
{:else}
	<p class="card text-slate-700">{t('kit.ownerOnly')}</p>
{/if}
