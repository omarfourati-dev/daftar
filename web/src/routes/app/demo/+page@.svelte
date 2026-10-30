<script lang="ts">
	/**
	 * `/app/demo` – every visitor gets their own fictitious practice (24 h). A short choice of the specialty first
	 * (section 12); `?lang=ar|fr` and `?specialty=` come from the landing page links.
	 */
	import { api, ApiError, apiErrorMessage, deps } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { DEMO_SPECIALTIES } from '#lib/catalog';
	import { applyLocaleFromQuery, i18n, t } from '#lib/i18n.svelte';
	import type { Session, Specialty } from '#lib/types';
	import LanguageSwitch from '../../../lib/components/LanguageSwitch.svelte';

	applyLocaleFromQuery();
	const wanted = typeof location === 'undefined' ? null : new URLSearchParams(location.search).get('specialty');
	let specialty = $state<Specialty>(DEMO_SPECIALTIES.includes(wanted as Specialty) ? (wanted as Specialty) : 'generaliste');
	let busy = $state(false);
	let error = $state('');

	const practice = auth.user?.practice;
	const running = !!auth.token && !!practice?.isDemo && (!practice.demoExpiresAt || new Date(practice.demoExpiresAt).getTime() > Date.now());

	async function start() {
		busy = true;
		error = '';
		try {
			const session = await api<Session>('/api/demo', { method: 'POST', json: { lang: i18n.locale, specialty } });
			auth.set(session.token, session.user);
			void deps.goto('/app');
		} catch (err) {
			error = err instanceof ApiError && err.status === 429 ? t('demo.tooMany') : apiErrorMessage(err);
		} finally {
			busy = false;
		}
	}
</script>

<svelte:head><title>{t('demo.title')} · Daftar</title></svelte:head>

<main class="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-6 px-4 py-10">
	<div class="flex items-center justify-between">
		<a href="/" data-sveltekit-reload class="flex items-center gap-2 text-lg font-bold text-brand-800"
			><img src="/favicon.svg" alt="" class="h-8 w-8" />{t('common.appName')}</a
		>
		<LanguageSwitch />
	</div>
	<div class="flex flex-col gap-2">
		<h1 class="text-3xl leading-tight font-bold text-ink">{t('demo.heading')}</h1>
		<p class="text-lg text-slate-700">{t('demo.intro')}</p>
	</div>

	{#if running}
		<a class="btn-secondary self-start" href="/app">{t('demo.resume')}</a>
	{/if}

	<fieldset class="min-w-0">
		<legend class="mb-3 font-semibold text-slate-800">{t('demo.choose')}</legend>
		<div class="grid grid-cols-2 gap-2 sm:grid-cols-3">
			{#each DEMO_SPECIALTIES as s (s)}
				<label
					class="flex min-h-14 cursor-pointer items-center gap-3 rounded-xl border-[1.5px] bg-white px-4 py-3 font-semibold has-checked:border-brand-700 has-checked:bg-brand-50 has-focus-visible:outline-3 has-focus-visible:outline-offset-2 has-focus-visible:outline-brand-900 {specialty ===
					s
						? 'border-brand-700'
						: 'border-slate-200'}"
				>
					<input type="radio" name="specialty" value={s} bind:group={specialty} class="h-4 w-4 accent-brand-700" />
					{t(`specialty.${s}`)}
				</label>
			{/each}
		</div>
	</fieldset>

	{#if error}<p role="alert" class="rounded-xl bg-amber-50 px-4 py-3 text-amber-900 ring-1 ring-amber-200">{error}</p>{/if}
	<div class="flex flex-col gap-3 sm:flex-row sm:items-center">
		<button type="button" class="btn-primary min-h-13 px-6 text-lg" disabled={busy} onclick={start}>{busy ? t('demo.starting') : t('demo.start')}</button>
		<p class="text-sm text-slate-600">{t('demo.noAccount')}</p>
	</div>
	<a class="self-start text-sm font-medium text-brand-700 underline" href="/connexion">{t('demo.login')}</a>
</main>
