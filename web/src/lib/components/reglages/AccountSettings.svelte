<script lang="ts">
	/** "Mon compte" – name, language, password and sign-out everywhere; for every role (section 6). */
	import { api, ApiError, apiErrorMessage, deps } from '../../api';
	import { auth } from '../../auth.svelte';
	import { t, translate } from '../../i18n.svelte';
	import type { Me } from '../../types';
	import ConfirmDialog from '../ConfirmDialog.svelte';
	import LanguageSwitch from '../LanguageSwitch.svelte';
	import TextField from '../form/TextField.svelte';

	const MIN_PASSWORD = 10;
	let name = $state(auth.user?.name ?? '');
	let nameError = $state('');
	let nameNotice = $state('');

	let current = $state('');
	let next = $state('');
	let repeat = $state('');
	let pwErrors = $state<{ current?: string; next?: string; repeat?: string; form?: string }>({});
	let pwNotice = $state('');
	let pwBusy = $state(false);

	let confirmLogout = $state(false);
	let logoutError = $state('');

	async function saveName(e: SubmitEvent) {
		e.preventDefault();
		nameNotice = '';
		nameError = name.trim() ? '' : t('kit.fieldRequired');
		if (nameError) return;
		try {
			auth.setUser(await api<Me>('/api/auth/me', { method: 'PATCH', json: { name: name.trim() } }));
			nameNotice = t('reglages.compte.nameSaved');
		} catch (err) {
			nameError = apiErrorMessage(err);
		}
	}

	function saveLanguage(lang: string) {
		void api<Me>('/api/auth/me', { method: 'PATCH', json: { lang } })
			.then((me) => auth.setUser(me))
			.catch(() => undefined);
	}

	async function changePassword(e: SubmitEvent) {
		e.preventDefault();
		pwNotice = '';
		pwErrors = {};
		if (!current) pwErrors.current = t('kit.fieldRequired');
		if (next.length < MIN_PASSWORD) pwErrors.next = t('errors.password_too_short');
		else if (next !== repeat) pwErrors.repeat = t('errors.passwords_differ');
		if (Object.keys(pwErrors).length) return;
		pwBusy = true;
		try {
			const answer = await api<{ token: string }>('/api/auth/password', { method: 'POST', json: { current, next } });
			auth.setToken(answer.token);
			current = next = repeat = '';
			pwNotice = t('reglages.compte.passwordChanged');
		} catch (err) {
			const message = apiErrorMessage(err);
			if (err instanceof ApiError && err.code === 'wrong_password') pwErrors = { current: message };
			else if (err instanceof ApiError && err.code?.startsWith('password_')) pwErrors = { next: message };
			else pwErrors = { form: message };
		} finally {
			pwBusy = false;
		}
	}

	async function logoutAll() {
		logoutError = '';
		try {
			await api('/api/auth/logout-all', { method: 'POST' });
			confirmLogout = false;
			auth.clear();
			void deps.goto('/connexion');
		} catch (err) {
			logoutError = apiErrorMessage(err);
		}
	}

	const card = 'card flex flex-col gap-4';
</script>

<div class="flex flex-col gap-6">
	<h2 class="text-xl font-bold text-ink">{t('reglages.compte.title')}</h2>

	<form class={card} novalidate onsubmit={saveName}>
		<h3 class="font-semibold text-ink">{t('reglages.compte.profile')}</h3>
		<dl class="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
			<dt class="text-slate-500">{t('reglages.compte.email')}</dt>
			<dd dir="ltr" class="text-start">{auth.user?.email}</dd>
			<dt class="text-slate-500">{t('reglages.compte.role')}</dt>
			<dd>{translate(`roles.${auth.user?.role}`) ?? auth.user?.role}</dd>
		</dl>
		<TextField label={t('reglages.compte.name')} bind:value={name} error={nameError} autocomplete="name" maxlength={120} />
		<div class="flex flex-wrap items-center gap-3">
			<button type="submit" class="btn-primary">{t('reglages.compte.saveName')}</button>
			<p role="status" class="text-sm font-medium text-brand-800">{nameNotice}</p>
		</div>
	</form>

	<section class={card} aria-labelledby="account-lang">
		<h3 id="account-lang" class="font-semibold text-ink">{t('reglages.compte.language')}</h3>
		<p class="text-sm text-slate-600">{t('reglages.compte.languageHint')}</p>
		<div><LanguageSwitch onchange={saveLanguage} /></div>
	</section>

	<form class={card} novalidate onsubmit={changePassword}>
		<h3 class="font-semibold text-ink">{t('reglages.compte.password')}</h3>
		<div class="grid gap-4 sm:grid-cols-3">
			<TextField label={t('reglages.compte.current')} bind:value={current} type="password" autocomplete="current-password" dir="ltr" error={pwErrors.current} />
			<TextField
				label={t('reglages.compte.next')}
				bind:value={next}
				type="password"
				autocomplete="new-password"
				dir="ltr"
				hint={t('reglages.compte.nextHint')}
				error={pwErrors.next}
			/>
			<TextField label={t('reglages.compte.repeat')} bind:value={repeat} type="password" autocomplete="new-password" dir="ltr" error={pwErrors.repeat} />
		</div>
		{#if pwErrors.form}<p role="alert" class="text-sm font-medium text-red-700">{pwErrors.form}</p>{/if}
		<div class="flex flex-wrap items-center gap-3">
			<button type="submit" class="btn-primary" disabled={pwBusy}>{t('reglages.compte.changePassword')}</button>
			<p role="status" class="text-sm font-medium text-brand-800">{pwNotice}</p>
		</div>
	</form>

	<section class={card} aria-labelledby="account-sessions">
		<h3 id="account-sessions" class="font-semibold text-ink">{t('reglages.compte.sessions')}</h3>
		<p class="text-sm text-slate-600">{t('reglages.compte.logoutAllText')}</p>
		<button type="button" class="btn-secondary self-start" onclick={() => (confirmLogout = true)}>{t('reglages.compte.logoutAll')}</button>
	</section>
</div>

<ConfirmDialog
	open={confirmLogout}
	title={t('reglages.compte.logoutAllTitle')}
	message={t('reglages.compte.logoutAllMessage')}
	confirmLabel={t('reglages.compte.logoutAll')}
	error={logoutError}
	onconfirm={logoutAll}
	oncancel={() => (confirmLogout = false)}
/>
