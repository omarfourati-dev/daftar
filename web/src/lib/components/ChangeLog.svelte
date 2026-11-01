<script lang="ts">
	/**
	 * The change log of a module for the owner (spec stock-hygiène 8, review M3): one entry per change – who, when,
	 * what, old → new in words, and the reason. A loading problem says so and offers to try again (never an empty log).
	 */
	import { auditChanges, auditSummary, type AuditEntry } from '../audit';
	import { t } from '../i18n.svelte';

	type Props = { entries: AuditEntry[] | null; error?: string; label: string; onretry?: () => void };
	let { entries, error = '', label, onretry }: Props = $props();
</script>

{#if error}
	<div role="alert" class="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-900 ring-1 ring-rose-200">
		<p>{error}</p>
		{#if onretry}<button type="button" class="btn-secondary min-h-11" onclick={onretry}>{t('common.retry')}</button>{/if}
	</div>
{:else if entries === null}
	<p class="text-sm text-slate-600" aria-busy="true">{t('common.loading')}</p>
{:else if entries.length === 0}
	<p class="text-sm text-slate-600">{t('audit.empty')}</p>
{:else}
	<ul class="flex flex-col divide-y divide-slate-100 text-sm" aria-label={label}>
		{#each entries as entry (entry.id)}
			{@const changes = auditChanges(entry)}
			<li class="flex flex-col gap-0.5 py-2 break-inside-avoid">
				<p class="text-ink" dir="auto">{auditSummary(entry)}</p>
				{#if changes.length}
					<ul class="ms-4 list-disc text-slate-700">
						{#each changes as line, i (i)}<li dir="auto">{line}</li>{/each}
					</ul>
				{/if}
				{#if entry.reason}<p class="text-slate-600" dir="auto">{t('audit.reason', { reason: entry.reason })}</p>{/if}
			</li>
		{/each}
	</ul>
{/if}
