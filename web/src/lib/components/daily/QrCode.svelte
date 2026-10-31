<script lang="ts">
	/** A QR code drawn locally as SVG (package `qrcode`, nothing sent to any service). */
	import QRCode from 'qrcode';

	let { value, label, class: extra = 'h-48 w-48' }: { value: string; label: string; class?: string } = $props();
	let svg = $state('');

	$effect(() => {
		const text = value;
		void QRCode.toString(text, { type: 'svg', margin: 1, errorCorrectionLevel: 'M', color: { dark: '#0f172a', light: '#ffffff' } }).then((out) => {
			if (text === value) svg = out;
		});
	});
</script>

<div role="img" aria-label={label} class="rounded-lg bg-white p-2 ring-1 ring-slate-200 [&>svg]:h-full [&>svg]:w-full {extra}">
	{@html svg}
</div>
