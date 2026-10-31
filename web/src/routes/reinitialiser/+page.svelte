<script lang="ts">
	/**
	 * `/reinitialiser#<token>` – a password reset link made by the owner (for a team member) or the admin (for an
	 * owner), story A3. The token stays in the fragment, so it never reaches server logs.
	 */
	import { onMount } from 'svelte';
	import { api, apiErrorMessage, deps } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { applyLocaleFromQuery, i18n, isLocale, t } from '#lib/i18n.svelte';
	import type { Session } from '#lib/types';
	import LanguageSwitch from '../../lib/components/LanguageSwitch.svelte';

	const MIN_PASSWORD = 10;
	applyLocaleFromQuery();
	const token = typeof location === 'undefined' ? '' : location.hash.slice(1);
	let preview = $state<{ email: string; practiceName: string | null } | null>(null);
	let loading = $state(!!token);
	let failed = $state(token ? '' : t('reset.incomplete'));
	let password = $state('');
	let repeat = $state('');
	let error = $state('');
	let busy = $state(false);

	onMount(async () => {
		if (!token) return;
		try {
			preview = await api<{ email: string; practiceName: string | null }>('/api/password-reset/preview', { method: 'POST', json: { token } });
		} catch (err) {
			failed = apiErrorMessage(err);
		} finally {
			loading = false;
		}
	});

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		if (password.length < MIN_PASSWORD) {
			error = t('errors.password_too_short');
			return;
		}
		if (password !== repeat) {
			error = t('errors.passwords_differ');
			return;
		}
		busy = true;
		try {
			const session = await api<Session>('/api/password-reset/accept', { method: 'POST', json: { token, password } });
			auth.set(session.token, session.user);
			if (isLocale(session.user.lang)) i18n.setLocale(session.user.lang);
			history.replaceState(history.state, '', '/reinitialiser'); // the used link leaves the address bar
			void deps.goto(session.user.role === 'admin' ? '/app/admin' : '/app');
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			busy = false;
		}
	}
</script>

<svelte:head><title>{t('reset.title')} · Daftar</title></svelte:head>

<main class="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-6 px-4 py-10">
	<div class="flex justify-end"><LanguageSwitch /></div>
	<div class="text-center">
		<img src="/favicon.svg" alt="" class="mx-auto h-14 w-14" />
		<h1 class="mt-3 text-2xl font-bold">{t('reset.title')}</h1>
	</div>
	{#if loading}
		<p class="text-center text-slate-600" role="status">{t('reset.checking')}</p>
	{:else if failed}
		<div class="card flex flex-col gap-3">
			<p role="alert" class="text-slate-800">{failed}</p>
			<a class="btn-secondary" href="/connexion">{t('reset.toLogin')}</a>
		</div>
	{:else if preview}
		<form class="card flex flex-col gap-4" novalidate onsubmit={submit}>
			<p class="text-slate-700">
				{preview.practiceName
					? t('reset.intro', { email: preview.email, practice: preview.practiceName })
					: t('reset.introAdmin', { email: preview.email })}
			</p>
			<input type="email" class="hidden" autocomplete="username" value={preview.email} readonly tabindex="-1" aria-hidden="true" />
			<label class="label">
				{t('reset.password')}
				<input class="input" type="password" autocomplete="new-password" dir="ltr" bind:value={password} aria-describedby="reset-hint" />
			</label>
			<label class="label">
				{t('reset.repeat')}
				<input class="input" type="password" autocomplete="new-password" dir="ltr" bind:value={repeat} />
			</label>
			<p id="reset-hint" class="text-sm text-slate-600">{t('reset.hint')}</p>
			{#if error}<p role="alert" class="text-sm text-red-700">{error}</p>{/if}
			<button class="btn-primary" type="submit" disabled={busy}>{busy ? t('reset.busy') : t('reset.submit')}</button>
		</form>
	{/if}
</main>
