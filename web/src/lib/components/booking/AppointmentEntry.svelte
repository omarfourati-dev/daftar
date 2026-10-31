<script lang="ts">
	/**
	 * An appointment written into the practice's notebook: ruled paper with the red margin line, the day in words
	 * and the time large – shown after booking and on the patient's own link.
	 */
	import type { Snippet } from 'svelte';
	import { formatDate, formatTime } from '../../i18n.svelte';

	let {
		startsAt,
		service,
		practitioner = null,
		practice,
		address = '',
		badge
	}: { startsAt: string; service: string; practitioner?: string | null; practice: string; address?: string; badge?: Snippet } = $props();
</script>

<div class="entry rounded-2xl border border-slate-200 shadow-sm">
	<div class="flex flex-col gap-1 py-5 ps-14 pe-5">
		{#if badge}<div class="mb-1">{@render badge()}</div>{/if}
		<p class="text-lg font-semibold text-ink first-letter:uppercase">{formatDate(startsAt, 'long')}</p>
		<p class="text-4xl leading-tight font-bold tracking-tight text-brand-800 tabular-nums"><bdi>{formatTime(startsAt)}</bdi></p>
		<p class="mt-1 font-medium text-slate-800">{#each [service, practitioner].filter(Boolean) as part, i (i)}{#if i}{' · '}{/if}<bdi>{part}</bdi>{/each}</p>
		<p class="text-sm text-slate-600"><bdi>{practice}</bdi></p>
		{#if address}<p class="text-sm text-slate-600"><bdi>{address}</bdi></p>{/if}
	</div>
</div>

<style>
	.entry {
		--line: 1.75rem;
		background-color: #fff;
		background-image:
			linear-gradient(to right, transparent 2.6rem, rgb(225 29 72 / 0.35) 2.6rem, rgb(225 29 72 / 0.35) calc(2.6rem + 1px), transparent calc(2.6rem + 1px)),
			repeating-linear-gradient(to bottom, transparent 0 calc(var(--line) - 1px), rgb(15 118 110 / 0.12) calc(var(--line) - 1px) var(--line));
	}
	:global([dir='rtl']) .entry {
		background-image:
			linear-gradient(to left, transparent 2.6rem, rgb(225 29 72 / 0.35) 2.6rem, rgb(225 29 72 / 0.35) calc(2.6rem + 1px), transparent calc(2.6rem + 1px)),
			repeating-linear-gradient(to bottom, transparent 0 calc(var(--line) - 1px), rgb(15 118 110 / 0.12) calc(var(--line) - 1px) var(--line));
	}
</style>
