<script lang="ts">
	/**
	 * `/app/installer` (section 13, story A4): the practice's own app as a PWA – the browser's install button where
	 * there is one, the steps for this device first, the other devices below, and a QR code for the team's phones.
	 */
	import { api } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { currentPracticeSlug } from '#lib/host';
	import { t, type MessageKey } from '#lib/i18n.svelte';
	import { install, installDeps, platform, type Platform } from '#lib/install.svelte';
	import { practiceUrl } from '#lib/links';
	import QrCode from '../../../lib/components/QrCode.svelte';

	const slug = auth.user?.practice?.slug ?? null;
	const onOwnAddress = !slug || currentPracticeSlug() === slug;
	const mine = platform();
	const others = (['ios', 'android', 'desktop'] as Platform[]).filter((p) => p !== mine);
	const standalone = installDeps.standalone();
	let thanks = $state(false);

	const installed = $derived(standalone || install.installed);

	function done() {
		void api('/api/onboarding/install/done', { method: 'POST' }).catch(() => undefined);
	}

	if (standalone) done();

	async function ask() {
		if (await install.ask()) done();
	}

	function confirm() {
		done();
		thanks = true;
	}

	const stepKeys = ['1', '2', '3'] as const;
	const step = (p: Platform, n: (typeof stepKeys)[number]) => t(`installer.steps.${p}.${n}` as MessageKey);
</script>

<svelte:head><title>{t('installer.title')} · Daftar</title></svelte:head>

<div class="flex max-w-3xl flex-col gap-6">
	<div class="flex flex-col gap-2">
		<h1 class="text-2xl font-bold text-ink">{t('installer.title')}</h1>
		<p class="text-slate-700">{t('installer.intro')}</p>
	</div>

	{#if installed}
		<p role="status" class="rounded-xl bg-brand-50 px-4 py-3 font-semibold text-brand-900 ring-1 ring-brand-200">{t('installer.installed')}</p>
	{:else if !onOwnAddress && slug}
		<div class="card flex flex-col items-start gap-3 border-amber-200 bg-amber-50">
			<p class="text-amber-950">{t('installer.ownAddress')}</p>
			<a class="btn-primary" href={practiceUrl(slug, '/app/installer')}>{t('installer.openOwn')}</a>
		</div>
	{/if}

	{#if !installed && install.prompt}
		<button type="button" class="btn-primary self-start min-h-13 px-6 text-lg" onclick={ask}>{t('installer.install')}</button>
	{/if}

	<section class="card flex flex-col gap-3" aria-labelledby="inst-mine">
		<h2 id="inst-mine" class="text-lg font-bold text-ink">{t('installer.thisDevice')} : {t(`installer.platforms.${mine}`)}</h2>
		<ol class="flex flex-col gap-2">
			{#each stepKeys as n (n)}
				<li class="flex items-start gap-3">
					<span class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-700 text-sm font-bold text-white">{n}</span>
					<span class="pt-0.5 text-slate-800">{step(mine, n)}</span>
				</li>
			{/each}
		</ol>
		{#if thanks}
			<p role="status" class="font-medium text-brand-800">{t('installer.thanks')}</p>
		{:else}
			<button type="button" class="btn-secondary self-start" onclick={confirm}>{t('installer.done')}</button>
		{/if}
	</section>

	{#if slug}
		<section class="card flex flex-col items-start gap-4 sm:flex-row sm:items-center" aria-labelledby="inst-team">
			<div class="rounded-2xl border border-slate-200 bg-white p-3">
				<QrCode text={practiceUrl(slug, '/app')} label={t('installer.qr')} class="h-36 w-36" />
			</div>
			<div class="flex flex-col gap-1">
				<h2 id="inst-team" class="font-bold text-ink">{t('installer.team')}</h2>
				<p class="text-sm text-slate-700">{t('installer.teamText')}</p>
				<p class="font-mono text-sm text-slate-600" dir="ltr">{practiceUrl(slug, '/app').replace(/^https?:\/\//, '')}</p>
			</div>
		</section>
	{/if}

	<section class="flex flex-col gap-2" aria-labelledby="inst-others">
		<h2 id="inst-others" class="font-bold text-ink">{t('installer.otherDevices')}</h2>
		{#each others as p (p)}
			<details class="card">
				<summary class="cursor-pointer font-semibold text-ink">{t(`installer.platforms.${p}`)}</summary>
				<ol class="mt-3 flex list-decimal flex-col gap-1 ps-6 text-slate-700">
					{#each stepKeys as n (n)}<li>{step(p, n)}</li>{/each}
				</ol>
			</details>
		{/each}
	</section>
</div>
