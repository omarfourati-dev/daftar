<script lang="ts" module>
	export type IconName =
		| 'start' | 'end' | 'plus' | 'print' | 'search' | 'phone' | 'chat' | 'sms' | 'alert' | 'check' | 'close' | 'calendar'
		| 'screen' | 'qr' | 'receipt' | 'trash' | 'ticket' | 'external' | 'users' | 'wallet' | 'bell' | 'chart' | 'clock'
		| 'edit' | 'repeat' | 'logout';
</script>

<script lang="ts">
	/**
	 * Line icons of the daily-work pages (drawn here, no icon font, nothing loaded from outside). Decorative:
	 * the button or link next to them carries the text. `start`/`end` chevrons and `logout` mirror in Arabic (RTL).
	 */
	const PATHS: Record<IconName, string> = {
		start: 'M15 18l-6-6 6-6',
		end: 'M9 18l6-6-6-6',
		plus: 'M12 5v14M5 12h14',
		print: 'M6 9V3h12v6M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2M6 14h12v7H6z',
		search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3',
		phone:
			'M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z',
		chat: 'M21 11.5a8.4 8.4 0 0 1-12.5 7.3L3 20.5l1.7-5.4A8.4 8.4 0 1 1 21 11.5z',
		sms: 'M4 4h16a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H8l-4 4V5a1 1 0 0 1 1-1zM8 9h8M8 12h5',
		alert: 'M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01',
		check: 'M20 6 9 17l-5-5',
		close: 'M18 6 6 18M6 6l12 12',
		calendar: 'M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z',
		screen: 'M3 4h18v12H3zM8 20h8M12 16v4',
		qr: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h3v3h-3zM18 18h3v3h-3zM18 14h3M14 18v3',
		receipt: 'M5 2v20l2.5-1.5L10 22l2-1.5 2 1.5 2.5-1.5L19 22V2l-2.5 1.5L14 2l-2 1.5L10 2 7.5 3.5zM9 8h6M9 12h6M9 16h4',
		trash: 'M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6',
		ticket: 'M3 7a2 2 0 0 0 2-2h14a2 2 0 0 0 2 2v3a2 2 0 0 0 0 4v3a2 2 0 0 0-2 2H5a2 2 0 0 0-2-2v-3a2 2 0 0 0 0-4zM9 5v14',
		external: 'M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5',
		users: 'M16 20v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 10a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 20v-2a4 4 0 0 0-3-3.9M16 2.1a4 4 0 0 1 0 7.8',
		wallet: 'M3 7h18v13H3zM3 7l2-4h12l2 4M16 13.5h2',
		bell: 'M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0',
		chart: 'M3 3v18h18M8 17V10M13 17V6M18 17v-4',
		clock: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 6v6l4 2',
		edit: 'M12 20h9M16.5 3.5a2.1 2.1 0 1 1 3 3L7 19l-4 1 1-4z',
		repeat: 'M17 2l4 4-4 4M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4M21 13v2a3 3 0 0 1-3 3H3',
		logout: 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9'
	};

	let { name, class: extra = 'h-5 w-5' }: { name: IconName; class?: string } = $props();
	const mirrored = $derived(name === 'start' || name === 'end' || name === 'logout');
</script>

<svg
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width="2"
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
	focusable="false"
	class="shrink-0 {extra} {mirrored ? 'rtl:-scale-x-100' : ''}"><path d={PATHS[name]} /></svg
>
