<script lang="ts">
	import { onMount } from 'svelte';
	import { api, apiErrorMessage, deps } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { i18n, t, translate } from '#lib/i18n.svelte';
	import type { Session } from '#lib/types';
	import LanguageSwitch from '../../lib/components/LanguageSwitch.svelte';

	const MIN_PASSWORD = 10;
	// The token travels in the URL fragment (#…): browsers never send it to the server or into its logs.
	let token = '';
	let invite = $state<{ practiceName: string; role: string } | null>(null);
	let loading = $state(true);
	let failed = $state('');
	let name = $state('');
	let email = $state('');
	let password = $state('');
	let repeat = $state('');
	let error = $state('');
	let busy = $state(false);

	onMount(async () => {
		token = location.hash.slice(1);
		if (!token) {
			failed = t('errors.invitation_incomplete');
			loading = false;
			return;
		}
		try {
			invite = await api<{ practiceName: string; role: string }>('/api/invitations/preview', {
				method: 'POST',
				json: { token }
			});
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
			const session = await api<Session>('/api/invitations/accept', {
				method: 'POST',
				json: { token, name, email, password, lang: i18n.locale }
			});
			auth.set(session.token, session.user);
			history.replaceState(history.state, '', '/invitation'); // the used link leaves the address bar
			void deps.goto('/app');
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			busy = false;
		}
	}
</script>

<svelte:head><title>{t('invitation.title')} · Daftar</title></svelte:head>

<main class="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-6 px-4 py-10">
	<div class="flex justify-end"><LanguageSwitch /></div>
	<div class="text-center">
		<img src="/favicon.svg" alt="" class="mx-auto h-14 w-14" />
		<h1 class="mt-3 text-2xl font-bold">{t('invitation.title')}</h1>
	</div>
	{#if loading}
		<p class="text-center text-slate-600" role="status">{t('invitation.checking')}</p>
	{:else if failed}
		<div class="card flex flex-col gap-3">
			<p role="alert" class="text-sm text-red-700">{failed}</p>
			<a class="btn-primary" href="/connexion">{t('invitation.toLogin')}</a>
		</div>
	{:else if invite}
		<form class="card flex flex-col gap-4" onsubmit={submit}>
			<p class="text-sm">
				{t('invitation.intro', {
					practice: invite.practiceName,
					role: translate(`roles.${invite.role}`) ?? invite.role
				})}
			</p>
			<label class="label"
				>{t('invitation.name')}
				<input class="input" autocomplete="name" required maxlength="120" bind:value={name} />
			</label>
			<label class="label"
				>{t('invitation.email')}
				<input class="input" type="email" autocomplete="username" dir="ltr" required bind:value={email} />
			</label>
			<label class="label"
				>{t('invitation.password')}
				<input class="input" type="password" autocomplete="new-password" dir="ltr" required bind:value={password} />
			</label>
			<label class="label"
				>{t('invitation.repeat')}
				<input class="input" type="password" autocomplete="new-password" dir="ltr" required bind:value={repeat} />
			</label>
			<p class="text-xs text-slate-500">{t('invitation.passwordHint')}</p>
			{#if auth.token && auth.user}
				<p class="text-xs text-amber-800">{t('invitation.signedInWarning', { email: auth.user.email })}</p>
			{/if}
			{#if error}<p role="alert" class="text-sm text-red-700">{error}</p>{/if}
			<button class="btn-primary" type="submit" disabled={busy}>{t('invitation.submit')}</button>
		</form>
	{/if}
</main>
