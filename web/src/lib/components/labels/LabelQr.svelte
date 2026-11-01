<script lang="ts" module>
	import QRCode from 'qrcode';

	/** Quiet zone around the code, in modules – the full four of the standard, so small printers still read it. */
	export const QUIET_ZONE = 4;

	/** The dark modules as one SVG path (runs of a row merged), drawn at once – the label is complete before printing. */
	export function qrPath(text: string): { size: number; path: string } {
		const qr = QRCode.create(text, { errorCorrectionLevel: 'M' });
		const n = qr.modules.size;
		let path = '';
		for (let y = 0; y < n; y++) {
			let x = 0;
			while (x < n) {
				if (!qr.modules.get(y, x)) {
					x++;
					continue;
				}
				const from = x;
				while (x < n && qr.modules.get(y, x)) x++;
				path += `M${from + QUIET_ZONE} ${y + QUIET_ZONE}h${x - from}v1h${from - x}z`;
			}
		}
		return { size: n + 2 * QUIET_ZONE, path };
	}
</script>

<script lang="ts">
	/** The QR code of a label: black on white, crisp edges, quiet zone included in its square. Drawn locally. */
	let { text, class: klass = '' }: { text: string; class?: string } = $props();
	const drawn = $derived(qrPath(text));
</script>

<svg
	class={klass}
	viewBox="0 0 {drawn.size} {drawn.size}"
	shape-rendering="crispEdges"
	aria-hidden="true"
	focusable="false"
	data-qr={text}
	xmlns="http://www.w3.org/2000/svg"
	><rect width={drawn.size} height={drawn.size} fill="#fff" /><path fill="#000" d={drawn.path} /></svg
>
