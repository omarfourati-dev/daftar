<script lang="ts">
	/** A QR code drawn locally (package `qrcode`, SVG) – no external service ever sees the address. */
	import QRCode from 'qrcode';

	let { text, label, class: klass = 'h-48 w-48' }: { text: string; label: string; class?: string } = $props();

	let svg = $state('');

	$effect(() => {
		const value = text;
		let current = true;
		QRCode.toString(value, { type: 'svg', margin: 1, errorCorrectionLevel: 'M', color: { dark: '#0f172a', light: '#ffffff' } })
			.then((drawn) => {
				if (current) svg = drawn;
			})
			.catch(() => {
				if (current) svg = '';
			});
		return () => {
			current = false;
		};
	});
</script>

<div role="img" aria-label={label} class="qr {klass} bg-white">
	<!-- eslint-disable-next-line svelte/no-at-html-tags -- SVG generated locally from our own text -->
	{@html svg}
</div>

<style>
	.qr :global(svg) {
		display: block;
		width: 100%;
		height: 100%;
	}
</style>
