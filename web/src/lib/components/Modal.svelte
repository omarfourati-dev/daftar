<script lang="ts">
	/**
	 * A modal dialog: role="dialog" + aria-modal, focus moves in on open and back on close, Escape and the backdrop
	 * close it, Tab stays inside. Rendered only while `open`.
	 */
	import { tick, type Snippet } from 'svelte';
	import { t } from '../i18n.svelte';

	let {
		open,
		title,
		onclose,
		children,
		wide = false
	}: { open: boolean; title: string; onclose: () => void; children: Snippet; wide?: boolean } = $props();

	const titleId = `dialog-${Math.random().toString(36).slice(2, 9)}`;
	let panel = $state<HTMLDivElement>();
	let returnTo: Element | null = null;

	$effect(() => {
		if (!open) return;
		returnTo = document.activeElement;
		void tick().then(() => {
			const first = panel?.querySelector<HTMLElement>('[data-autofocus], input, textarea, select, button:not([data-close])');
			(first ?? panel)?.focus();
		});
		return () => {
			if (returnTo instanceof HTMLElement) returnTo.focus();
		};
	});

	function keydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.stopPropagation();
			onclose();
			return;
		}
		if (e.key !== 'Tab' || !panel) return;
		const focusable = [...panel.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input:not([disabled]), select, textarea')];
		if (!focusable.length) return;
		const first = focusable[0];
		const last = focusable[focusable.length - 1];
		if (e.shiftKey && document.activeElement === first) {
			e.preventDefault();
			last.focus();
		} else if (!e.shiftKey && document.activeElement === last) {
			e.preventDefault();
			first.focus();
		}
	}
</script>

{#if open}
	<div class="fixed inset-0 z-40 flex items-end justify-center bg-slate-900/50 p-0 sm:items-center sm:p-4 print:hidden">
		<button type="button" class="absolute inset-0 cursor-default" tabindex="-1" aria-label={t('kit.closeDialog')} data-close onclick={onclose}
		></button>
		<div
			bind:this={panel}
			role="dialog"
			aria-modal="true"
			aria-labelledby={titleId}
			tabindex="-1"
			onkeydown={keydown}
			class="relative flex max-h-[92vh] w-full flex-col gap-4 overflow-y-auto rounded-t-2xl bg-white p-5 shadow-xl outline-none sm:rounded-2xl {wide
				? 'sm:max-w-2xl'
				: 'sm:max-w-md'}"
		>
			<div class="flex items-start justify-between gap-3">
				<h2 id={titleId} class="text-lg font-bold text-ink">{title}</h2>
				<button
					type="button"
					data-close
					class="-me-2 -mt-1 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-brand-700"
					aria-label={t('kit.closeDialog')}
					onclick={onclose}
				>
					<svg viewBox="0 0 20 20" class="h-5 w-5" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="2" stroke-linecap="round" /></svg>
				</button>
			</div>
			{@render children()}
		</div>
	</div>
{/if}
