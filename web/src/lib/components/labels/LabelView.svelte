<script lang="ts">
	/**
	 * One label at its real size (millimetres and points – the same on screen and on paper), black on white, at least
	 * 7 pt. Sterilisation: practice, content, "stérilisé le", "à utiliser avant", autoclave and initials, code with QR.
	 * Specimen: NOM Prénom, birth date (or year) and file number, kind of specimen, when and by whom, practice, code
	 * with QR. Test: the edge of the label, the safe area, the smallest text and a QR code. Codes and dates stay left to
	 * right in Arabic; the QR code sits on the side where reading starts.
	 */
	import { fit } from '../../fit';
	import { i18n, t } from '../../i18n.svelte';
	import { FORMAT_SPECS, type LabelData } from '../../labels';
	import type { LabelFormat } from '../../types/labels';
	import LabelQr from './LabelQr.svelte';

	let { label, format }: { label: LabelData; format: LabelFormat } = $props();

	const spec = $derived(FORMAT_SPECS[format]);
	const qr = $derived(label.kind === 'specimen' ? spec.qr.specimen : spec.qr.sterile);
	const vars = $derived(
		`--lw:${spec.label[0]}mm;--lh:${spec.label[1]}mm;--px:${spec.pad[0]}mm;--py:${spec.pad[1]}mm;--qr:${qr}mm`
	);
	const name = $derived(label.kind === 'test' ? t('labels.test.label', { n: label.position }) : t('labels.print.label', { code: label.code }));
</script>

<article class="label {label.kind}" style={vars} dir={i18n.dir} lang={i18n.locale} aria-label={name} data-label={label.code}>
	{#if label.kind === 'sterile'}
		<p class="head" data-critical>{label.practice}</p>
		<div class="body">
			<div class="qr-col">
				<LabelQr text={label.code} class="qr" />
				<p class="code" dir="ltr" data-critical>{label.code}</p>
			</div>
			<div class="info">
				<p class="strong" use:fit={{ max: 9, key: [label.content, format] }} data-critical>{label.content}</p>
				<p data-critical>{t('labels.sterile.sterilizedOn')} <span class="ltr" dir="ltr">{label.sterilizedOn}</span></p>
				<div>
					<p>{t('labels.sterile.useBefore')}</p>
					<p class="big" data-critical><span class="ltr" dir="ltr">{label.useBefore}</span></p>
				</div>
				<p data-critical>{t('labels.sterile.autoclave', { code: label.autoclave })} – {label.initials}</p>
			</div>
		</div>
	{:else if label.kind === 'specimen'}
		<p class="strong name" use:fit={{ max: 9.5, key: [label.name, format] }} data-critical>{label.name}</p>
		<div class="body">
			<div class="qr-col">
				<LabelQr text={label.code} class="qr" />
				<p class="code" dir="ltr" data-critical>{label.code}</p>
			</div>
			<div class="info">
				<p data-critical>{label.birth}{label.birth ? ' – ' : ''}{t('labels.specimen.fileNo', { no: label.fileNo })}</p>
				<p class="strong" use:fit={{ max: 9, key: [label.specimen, format] }} data-critical>{label.specimen}</p>
				<p data-critical>{label.collected}</p>
				<p class="practice">{label.practice}</p>
			</div>
		</div>
	{:else}
		<div class="safe" aria-hidden="true"></div>
		<div class="body">
			<div class="qr-col">
				<LabelQr text={label.code} class="qr" />
				<p class="code" dir="ltr">{label.code}</p>
			</div>
			<div class="info">
				<p class="big">{t('labels.test.title')}</p>
				<p><span class="ltr" dir="ltr">{spec.label[0]} × {spec.label[1]} mm</span></p>
				<p>{t('labels.test.sample')} <span class="ltr" dir="ltr">Aa 0123456789</span></p>
				<p class="strong">{t('labels.test.position', { n: label.position })}</p>
			</div>
		</div>
	{/if}
</article>

<style>
	.label {
		box-sizing: border-box;
		display: flex;
		flex-direction: column;
		gap: 0.5mm;
		width: var(--lw);
		height: var(--lh);
		padding: var(--py) var(--px);
		overflow: hidden;
		background: #fff;
		color: #000;
		font-family: 'IBM Plex Sans Arabic', ui-sans-serif, system-ui, sans-serif;
		font-size: 7pt;
		font-weight: 500;
		line-height: 1.12;
		text-align: start;
		print-color-adjust: exact;
		-webkit-print-color-adjust: exact;
	}
	.label p {
		margin: 0;
	}
	.head,
	.practice {
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.body {
		display: flex;
		flex: 1;
		gap: 1.8mm;
		min-height: 0;
	}
	.qr-col {
		display: flex;
		flex: none;
		flex-direction: column;
		align-items: center;
		gap: 0.4mm;
		width: var(--qr);
	}
	.qr-col :global(.qr) {
		display: block;
		width: var(--qr);
		height: var(--qr);
	}
	.code {
		font-size: 8pt;
		font-weight: 700;
		letter-spacing: 0.01em;
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
	}
	.info {
		display: flex;
		flex: 1;
		flex-direction: column;
		justify-content: space-between;
		min-width: 0;
		overflow-wrap: anywhere;
	}
	.strong {
		display: -webkit-box;
		overflow: hidden;
		font-size: 9pt;
		font-weight: 700;
		line-height: 1.1;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 2;
		line-clamp: 2;
	}
	.name {
		flex: none;
	}
	.big {
		font-size: 10.5pt;
		font-weight: 700;
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
	}
	.ltr {
		unicode-bidi: isolate;
		font-variant-numeric: tabular-nums;
	}
	.test {
		position: relative;
		outline: 0.25mm solid #000;
		outline-offset: -0.25mm;
	}
	.safe {
		position: absolute;
		inset: var(--py) var(--px);
		border: 0.2mm dashed #000;
	}
	.test .body {
		position: relative;
		padding: 0.6mm;
	}
	.test .qr-col :global(.qr) {
		width: calc(var(--qr) - 2mm);
		height: calc(var(--qr) - 2mm);
	}
</style>
