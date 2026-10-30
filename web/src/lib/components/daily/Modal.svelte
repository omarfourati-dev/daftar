<script lang="ts">
	/**
	 * A dialog over the page: sheet from the bottom on phones, centred panel from the tablet up. Focus moves into
	 * the dialog, stays there (Tab cycles) and returns to the opener; Escape and the backdrop close it.
	 */
	import { onMount, type Snippet } from 'svelte';
	import Icon from './Icon.svelte';
	import { t } from '../../i18n.svelte';

	type Props = {
		title: string;
		onclose: () => void;
		children: Snippet;
		footer?: Snippet;
		wide?: boolean;
		/** Text under the title (e.g. the date of an appointment). */
		subtitle?: string;
	};
	let { title, onclose, children, footer, wide = false, subtitle = '' }: Props = $props();

	let panel: HTMLDivElement | undefined = $state();
	const id = `dlg-${Math.random().toString(36).slice(2, 9)}`;
	const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

	onMount(() => {
		const opener = document.activeElement as HTMLElement | null;
		const first = panel?.querySelector<HTMLElement>('[autofocus], [data-autofocus]') ?? panel?.querySelector<HTMLElement>(FOCUSABLE);
		(first ?? panel)?.focus();
		return () => opener?.focus?.();
	});

	function keydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.stopPropagation();
			onclose();
			return;
		}
		if (e.key !== 'Tab' || !panel) return;
		const items = [...panel.querySelectorAll<HTMLElement>(FOCUSABLE)];
		if (!items.length) return;
		const first = items[0];
		const last = items[items.length - 1];
		if (e.shiftKey && document.activeElement === first) {
			e.preventDefault();
			last.focus();
		} else if (!e.shiftKey && document.activeElement === last) {
			e.preventDefault();
			first.focus();
		}
	}
</script>

<div class="fixed inset-0 z-40 flex items-end justify-center bg-ink/45 sm:items-center sm:p-6 print:hidden">
	<button type="button" class="absolute inset-0 cursor-default" tabindex="-1" aria-label={t('common.close')} onclick={onclose}></button>
	<div
		bind:this={panel}
		role="dialog"
		aria-modal="true"
		aria-labelledby="{id}-title"
		tabindex="-1"
		class="relative flex max-h-[92vh] w-full flex-col rounded-t-2xl bg-white shadow-2xl outline-none sm:rounded-2xl {wide ? 'sm:max-w-3xl' : 'sm:max-w-xl'}"
		onkeydown={keydown}
	>
		<div class="flex items-start gap-3 border-b border-slate-200 px-5 py-4">
			<div class="min-w-0 flex-1">
				<h2 id="{id}-title" class="text-lg font-bold text-ink">{title}</h2>
				{#if subtitle}<p class="text-sm text-slate-600 first-letter:uppercase">{subtitle}</p>{/if}
			</div>
			<button type="button" class="btn -me-2 min-h-11 min-w-11 px-2 text-slate-600 hover:bg-slate-100" aria-label={t('common.close')} onclick={onclose}>
				<Icon name="close" />
			</button>
		</div>
		<div class="min-h-0 flex-1 overflow-y-auto px-5 py-4">{@render children()}</div>
		{#if footer}
			<div class="flex flex-wrap items-center justify-end gap-2 border-t border-slate-200 px-5 py-3">{@render footer()}</div>
		{/if}
	</div>
</div>
