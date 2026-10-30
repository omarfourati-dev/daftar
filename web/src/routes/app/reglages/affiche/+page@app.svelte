<script lang="ts">
	/**
	 * A4 poster "Prenez rendez-vous en ligne" in French and Arabic with the QR code of the booking page (story C3).
	 * Sized in container units, so the preview and the printed sheet (210 × 297 mm) are the same design.
	 * The QR code is drawn locally – no external service.
	 */
	import { onMount } from 'svelte';
	import { api, apiErrorMessage } from '#lib/api';
	import { t } from '#lib/i18n.svelte';
	import { ar } from '#lib/i18n/ar';
	import { fr } from '#lib/i18n/fr';
	import { initials } from '#lib/initials';
	import { practiceUrl } from '#lib/links';
	import { formatPhone } from '#lib/phone-check';
	import { POSTER_TEXT } from '#lib/poster-text';
	import type { Practice } from '#lib/types/practice';
	import LoadState from '../../../../lib/components/LoadState.svelte';
	import QrCode from '../../../../lib/components/QrCode.svelte';

	let practice = $state<Practice | null>(null);
	let loading = $state(true);
	let error = $state('');

	async function load() {
		loading = true;
		error = '';
		try {
			practice = await api<Practice>('/api/practice');
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			loading = false;
		}
	}
	onMount(load);

	function print() {
		window.print();
		void api('/api/onboarding/poster/done', { method: 'POST' }).catch(() => undefined);
	}

	const url = $derived(practice ? practiceUrl(practice.slug, '/') : '');
	const shownUrl = $derived(url.replace(/^https?:\/\//, '').replace(/\/$/, ''));
	const color = $derived(practice?.brandColor && /^#[0-9a-f]{6}$/i.test(practice.brandColor) ? practice.brandColor : '#0f766e');
	// the poster is bilingual whatever language the app is in
	const specialty = $derived.by(() => {
		const key = practice?.specialty as keyof typeof fr.specialty | undefined;
		return key && key in fr.specialty ? [fr.specialty[key], ar.specialty[key]] : [];
	});
</script>

<svelte:head><title>{t('poster.title')} · Daftar</title></svelte:head>

<div class="flex flex-col gap-4 print:hidden">
	<a href="/app/reglages/reservation" class="inline-flex min-h-11 items-center self-start text-sm font-medium text-brand-700 hover:underline">
		<span aria-hidden="true" class="me-1 rtl:rotate-180">‹</span>{t('poster.back')}
	</a>
	<div class="flex flex-wrap items-end justify-between gap-3">
		<div class="flex max-w-2xl flex-col gap-1">
			<h1 class="text-2xl font-bold text-ink">{t('poster.title')}</h1>
			<p class="text-slate-600">{t('poster.intro')}</p>
			<p class="text-sm text-slate-500">{t('poster.tip')}</p>
		</div>
		<button type="button" class="btn-primary" disabled={!practice} onclick={print}>{t('poster.print')}</button>
	</div>
	<LoadState {loading} {error} onretry={load} />
</div>

{#if practice}
	<div class="sheet-wrap">
		<article class="sheet" dir="ltr" aria-label={t('poster.title')} style="--brand:{color}">
			<header class="band">
				<span class="badge" aria-hidden="true">{initials(practice.name)}</span>
				<div class="names">
					<p class="name-fr" lang="fr" dir="ltr">{practice.name}</p>
					{#if practice.nameAr}<p class="name-ar" lang="ar" dir="rtl">{practice.nameAr}</p>{/if}
					<p class="meta">{[...specialty, practice.city].filter(Boolean).join(' · ')}</p>
				</div>
			</header>

			<div class="headlines">
				<p class="headline" lang="fr" dir="ltr">{POSTER_TEXT.fr.headline}</p>
				<p class="headline ar" lang="ar" dir="rtl">{POSTER_TEXT.ar.headline}</p>
			</div>

			<div class="qr-block">
				<div class="qr-tile">
					<QrCode text={url} label={t('poster.qr')} class="qr" />
				</div>
				<p class="url" dir="ltr">{shownUrl}</p>
			</div>

			<div class="steps">
				<ol lang="fr" dir="ltr">
					{#each POSTER_TEXT.fr.steps as step, i (i)}<li><span class="num">{i + 1}</span><span>{step}</span></li>{/each}
				</ol>
				<ol lang="ar" dir="rtl">
					{#each POSTER_TEXT.ar.steps as step, i (i)}<li><span class="num">{i + 1}</span><span>{step}</span></li>{/each}
				</ol>
			</div>

			<footer class="foot">
				<p dir="ltr"><span lang="fr">{POSTER_TEXT.fr.call}</span> · <span lang="ar">{POSTER_TEXT.ar.call}</span></p>
				<p class="phone" dir="ltr">{formatPhone(practice.phone)}</p>
			</footer>
		</article>
	</div>
{/if}

<style>
	.sheet-wrap {
		margin-top: 1.5rem;
		display: flex;
		justify-content: center;
	}
	.sheet {
		container-type: inline-size;
		position: relative;
		display: flex;
		flex-direction: column;
		width: min(100%, 210mm);
		aspect-ratio: 210 / 297;
		overflow: hidden;
		color: #0f172a;
		/* the Seyès notebook ruling of the landing page: the practice's "daftar" */
		background-color: #fff;
		background-image:
			linear-gradient(to right, transparent calc(9cqw - 1px), rgb(225 29 72 / 0.32) calc(9cqw - 1px), rgb(225 29 72 / 0.32) 9cqw, transparent 9cqw),
			repeating-linear-gradient(to bottom, transparent 0 calc(4cqw - 1px), rgb(15 118 110 / 0.13) calc(4cqw - 1px) 4cqw),
			repeating-linear-gradient(to bottom, transparent 0 calc(1cqw - 1px), rgb(15 118 110 / 0.05) calc(1cqw - 1px) 1cqw);
		box-shadow:
			0 1px 2px rgb(15 23 42 / 0.08),
			0 12px 32px rgb(15 23 42 / 0.12);
		border-radius: 4px;
		print-color-adjust: exact;
		-webkit-print-color-adjust: exact;
	}
	.band {
		display: flex;
		align-items: center;
		gap: 4cqw;
		padding: 5cqw 7cqw 4cqw;
		background: var(--brand);
		color: #fff;
	}
	.badge {
		display: inline-flex;
		flex-shrink: 0;
		align-items: center;
		justify-content: center;
		width: 14cqw;
		height: 14cqw;
		border-radius: 3.5cqw;
		background: #fff;
		color: var(--brand);
		font-size: 6.5cqw;
		font-weight: 700;
		letter-spacing: 0.02em;
	}
	.names {
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 0.6cqw;
	}
	.name-fr {
		font-size: 5.6cqw;
		font-weight: 700;
		line-height: 1.1;
	}
	.name-ar {
		font-size: 5cqw;
		font-weight: 700;
		line-height: 1.35;
		text-align: left;
	}
	.meta {
		font-size: 2.6cqw;
		opacity: 0.9;
	}
	.headlines {
		padding: 4.5cqw 7cqw 0;
		text-align: center;
	}
	.headline {
		font-size: 5.8cqw;
		font-weight: 700;
		line-height: 1.15;
		letter-spacing: -0.01em;
	}
	.headline.ar {
		margin-top: 1cqw;
		font-size: 5.4cqw;
		line-height: 1.45;
		letter-spacing: 0;
	}
	.qr-block {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2cqw;
		padding-top: 3.5cqw;
	}
	.qr-tile {
		padding: 2.6cqw;
		background: #fff;
		border: 0.7cqw solid var(--brand);
		border-radius: 4cqw;
	}
	.qr-tile :global(.qr) {
		width: 32cqw;
		height: 32cqw;
	}
	.url {
		font-family: ui-monospace, 'Cascadia Mono', Menlo, monospace;
		font-size: 2.9cqw;
		font-weight: 600;
		background: #fff;
		padding: 0.4cqw 1.6cqw;
		border-radius: 1cqw;
	}
	.steps {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 4cqw;
		margin: 3.5cqw 6cqw 0 11cqw;
		padding: 2cqw 3cqw;
		background: rgb(255 255 255 / 0.94);
		border-radius: 2cqw;
	}
	.steps ol {
		display: flex;
		flex-direction: column;
		gap: 1.6cqw;
		list-style: none;
		margin: 0;
		padding: 0;
		font-size: 2.45cqw;
		line-height: 1.25;
	}
	.steps ol[lang='ar'] {
		font-size: 2.6cqw;
		line-height: 1.4;
	}
	.steps li {
		display: flex;
		align-items: center;
		gap: 1.8cqw;
	}
	.num {
		display: inline-flex;
		flex-shrink: 0;
		align-items: center;
		justify-content: center;
		width: 4.4cqw;
		height: 4.4cqw;
		border-radius: 50%;
		background: var(--brand);
		color: #fff;
		font-weight: 700;
	}
	.foot {
		margin-top: auto;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.6cqw;
		padding: 1.5cqw 7cqw 3.5cqw;
		font-size: 2.6cqw;
		text-align: center;
	}
	.foot p {
		background: rgb(255 255 255 / 0.9);
		padding: 0 1.4cqw;
		border-radius: 1cqw;
	}
	.phone {
		font-size: 4.6cqw;
		font-weight: 700;
		letter-spacing: 0.02em;
		font-variant-numeric: tabular-nums;
	}

	@media print {
		@page {
			size: A4 portrait;
			margin: 0;
		}
		.sheet-wrap {
			margin: 0;
		}
		.sheet {
			width: 210mm;
			height: 297mm;
			aspect-ratio: auto;
			box-shadow: none;
			border-radius: 0;
		}
	}
</style>
