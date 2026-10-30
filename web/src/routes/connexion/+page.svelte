<script lang="ts">
	import { onMount } from 'svelte';
	import { api, apiErrorMessage, deps } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { currentPracticeSlug, loadPublicPractice, type PublicPractice } from '#lib/host';
	import { i18n, isLocale, t } from '#lib/i18n.svelte';
	import type { Session } from '#lib/types';
	import LanguageSwitch from '../../lib/components/LanguageSwitch.svelte';

	let email = $state('');
	let password = $state('');
	let error = $state('');
	let busy = $state(false);
	// On a practice sub-domain the page shows that practice (its own app, section 13).
	const slug = currentPracticeSlug();
	let practice = $state<PublicPractice | null>(null);

	onMount(async () => {
		if (slug) practice = await loadPublicPractice(slug);
	});

	const practiceName = $derived(practice ? (i18n.locale === 'ar' && practice.nameAr ? practice.nameAr : practice.name) : null);

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		busy = true;
		error = '';
		try {
			const session = await api<Session>('/api/auth/login', { method: 'POST', json: { email, password } });
			auth.set(session.token, session.user);
			if (isLocale(session.user.lang)) i18n.setLocale(session.user.lang);
			void deps.goto(session.user.role === 'admin' ? '/app/admin' : '/app');
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			busy = false;
		}
	}
</script>

<svelte:head><title>{t('auth.title')} · Daftar</title></svelte:head>

<main class="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-6 px-4 py-10">
	<div class="flex justify-end"><LanguageSwitch /></div>
	<div class="text-center">
		{#if slug}
			<img src="/icons/practice-192.png" alt={practiceName ?? 'Daftar'} class="mx-auto h-16 w-16 rounded-2xl" />
		{:else}
			<img src="/favicon.svg" alt="" class="mx-auto h-14 w-14" />
		{/if}
		{#if practiceName}
			<h1 class="mt-3 text-2xl font-bold">{practiceName}</h1>
			<p class="text-slate-600">{t('auth.title')}</p>
		{:else}
			<h1 class="mt-3 text-2xl font-bold">{t('auth.title')}</h1>
			<p class="text-slate-600">{t('auth.intro')}</p>
		{/if}
	</div>
	<form class="card flex flex-col gap-4" onsubmit={submit}>
		<label class="label"
			>{t('auth.email')}
			<input class="input" type="email" autocomplete="username" dir="ltr" required bind:value={email} />
		</label>
		<label class="label"
			>{t('auth.password')}
			<input class="input" type="password" autocomplete="current-password" dir="ltr" required bind:value={password} />
		</label>
		{#if error}<p role="alert" class="text-sm text-red-700">{error}</p>{/if}
		<button class="btn-primary" type="submit" disabled={busy}>{busy ? t('auth.busy') : t('auth.submit')}</button>
	</form>
	{#if !slug}
		<p class="text-center text-sm text-slate-600">
			{t('auth.noAccount')}
			<a class="font-semibold text-brand-700 underline" href="/app/demo">{t('auth.tryDemo')}</a>
		</p>
		<p class="text-center text-sm">
			<a class="text-slate-500 hover:text-brand-700" href="/" data-sveltekit-reload>{t('common.toLanding')}</a>
		</p>
	{/if}
</main>
