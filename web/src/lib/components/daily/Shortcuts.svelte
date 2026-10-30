<script lang="ts">
	/**
	 * Keyboard shortcuts of the staff app (story B7): `/` → patient search in the header, `N` → new appointment
	 * (on the agenda right away, elsewhere via /app/agenda?nouveau=1), `T` → appointment on the phone (16.1).
	 * Ignored while typing or with Ctrl/Alt/⌘.
	 */
	import { deps } from '../../api';
	import { newAppointment, phoneBooking } from '../../agenda/requests.svelte';

	let { path }: { path: string } = $props();

	function typing(target: EventTarget | null): boolean {
		const el = target as HTMLElement | null;
		if (!el || !el.tagName) return false;
		return el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName);
	}

	function keydown(e: KeyboardEvent) {
		if (e.ctrlKey || e.metaKey || e.altKey || typing(e.target) || typing(document.activeElement)) return;
		if (document.querySelector('[aria-modal="true"]')) return; // a dialog is open
		if (e.key === '/') {
			const search = document.getElementById('global-search');
			if (!search) return;
			e.preventDefault();
			search.focus();
		} else if (e.key === 't' || e.key === 'T') {
			e.preventDefault();
			phoneBooking.open = true;
		} else if (e.key === 'n' || e.key === 'N') {
			e.preventDefault();
			if (path === '/app/agenda' || path === '/app/agenda/') newAppointment.request();
			else void deps.goto('/app/agenda?nouveau=1');
		}
	}
</script>

<svelte:window onkeydown={keydown} />
