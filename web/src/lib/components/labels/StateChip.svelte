<script lang="ts">
	/** The state of a sterile pack as a small chip: to use (green), expired (amber), used (grey), not sterile (red),
	 * of a cancelled cycle (grey, struck through). */
	import { t } from '../../i18n.svelte';
	import type { PackState } from '../../types/labels';

	let { state }: { state: PackState } = $props();
	const TONE: Record<PackState, string> = {
		usable: 'bg-emerald-100 text-emerald-950',
		expired: 'bg-amber-100 text-amber-950',
		used: 'bg-slate-200 text-slate-900',
		not_sterile: 'bg-rose-100 text-rose-950',
		cancelled: 'bg-slate-100 text-slate-800 line-through'
	};
</script>

<span class="inline-flex shrink-0 items-center rounded-full px-2 text-xs font-bold {TONE[state]}">{t(`labels.states.${state}`)}</span>
