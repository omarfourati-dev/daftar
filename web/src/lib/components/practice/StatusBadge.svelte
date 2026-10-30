<script lang="ts">
	/** Subscription status of a practice as a small coloured label. */
	import { translate } from '../../i18n.svelte';

	let { status }: { status: string | null | undefined } = $props();
	const COLORS: Record<string, string> = {
		pilot: 'bg-sky-50 text-sky-900 ring-sky-200',
		trial: 'bg-violet-50 text-violet-900 ring-violet-200',
		active: 'bg-emerald-50 text-emerald-900 ring-emerald-200',
		past_due: 'bg-amber-50 text-amber-900 ring-amber-300',
		suspended: 'bg-rose-50 text-rose-900 ring-rose-200',
		canceled: 'bg-zinc-100 text-zinc-700 ring-zinc-300'
	};
</script>

{#if status}
	<span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-sm font-semibold ring-1 ring-inset {COLORS[status] ?? COLORS.canceled}"
		>{translate(`admin.status.${status}`) ?? status}</span
	>
{/if}
