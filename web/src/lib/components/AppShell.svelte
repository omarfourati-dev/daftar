<script lang="ts">
	/**
	 * Frame of every /app page: guard (→ /connexion), account refresh, navigation (sidebar on desktop, bottom bar
	 * on phones), language switch, banners (demo, suspended subscription, offline). Pages render as `children`.
	 * Printable pages (receipt) hide the frame with `print:hidden` automatically.
	 */
	import { onMount, type Snippet } from 'svelte';
	import { api, deps } from '../api';
	import { auth } from '../auth.svelte';
	import { t, type MessageKey } from '../i18n.svelte';
	import { pwa } from '../pwa.svelte';
	import type { Me } from '../types';
	import LanguageSwitch from './LanguageSwitch.svelte';
	import { badges } from '../badges.svelte';
	import GlobalSearch from './daily/GlobalSearch.svelte';
	import Shortcuts from './daily/Shortcuts.svelte';

	let { path, children }: { path: string; children: Snippet } = $props();

	type Item = { href: string; key: MessageKey; short?: MessageKey; ownerOnly?: boolean };
	const STAFF: Item[] = [
		{ href: '/app', key: 'nav.today' },
		{ href: '/app/agenda', key: 'nav.agenda' },
		{ href: '/app/salle', key: 'nav.salle', short: 'nav.salleShort' },
		{ href: '/app/patients', key: 'nav.patients' },
		{ href: '/app/caisse', key: 'nav.caisse' },
		{ href: '/app/rappels', key: 'nav.rappels' },
		{ href: '/app/statistiques', key: 'nav.statistiques', ownerOnly: true },
		{ href: '/app/reglages', key: 'nav.reglages' }
	];
	const ADMIN: Item[] = [
		{ href: '/app/admin', key: 'nav.admin' },
		{ href: '/app/reglages', key: 'nav.reglages' }
	];

	const isAdmin = $derived(auth.user?.role === 'admin');
	const items = $derived(isAdmin ? ADMIN : STAFF.filter((i) => !i.ownerOnly || auth.user?.role === 'owner'));
	/** Online requests + overdue appointments, shown next to "Aujourd'hui" (they are handled there). */
	const badgeFor = (href: string) => (href === '/app' && !isAdmin ? badges.total : 0);
	const bottom = $derived(items.slice(0, isAdmin ? items.length : 4));
	const more = $derived(isAdmin ? [] : items.slice(4));
	const practice = $derived(auth.user?.practice ?? null);
	let moreOpen = $state(false);

	const active = (href: string) => (href === '/app' ? path === '/app' || path === '/app/' : path === href || path.startsWith(href + '/'));

	$effect(() => {
		if (!auth.token) void deps.goto('/connexion');
		else if (isAdmin && (path === '/app' || path === '/app/')) void deps.goto('/app/admin');
	});

	onMount(() => {
		if (auth.token && !isAdmin) badges.start();
		return () => badges.stop();
	});

	onMount(async () => {
		if (!auth.token) return;
		try {
			auth.setUser(await api<Me>('/api/auth/me'));
		} catch {
			/* 401 is handled by api(); offline: keep the stored account */
		}
	});

	function saveLanguage(lang: string) {
		void api('/api/auth/me', { method: 'PATCH', json: { lang } }).catch(() => undefined);
	}

	function logout() {
		auth.clear();
		void deps.goto('/connexion');
	}
</script>

{#if auth.token}
	{#if !isAdmin}<Shortcuts {path} />{/if}
	<div class="min-h-screen md:flex">
		<aside class="hidden w-60 shrink-0 flex-col gap-4 border-e border-slate-200 bg-white p-4 md:flex print:hidden">
			<a href={isAdmin ? '/app/admin' : '/app'} class="flex items-center gap-2 text-lg font-bold text-brand-800">
				<img src="/favicon.svg" alt="" class="h-8 w-8" />Daftar
			</a>
			<nav aria-label={t('nav.label')} class="flex flex-col gap-1">
				{#each items as item (item.href)}
					<a
						href={item.href}
						class="rounded-lg px-3 py-2.5 font-medium text-slate-700 hover:bg-brand-50 hover:text-brand-800"
						class:bg-brand-50={active(item.href)}
						class:text-brand-800={active(item.href)}
						aria-current={active(item.href) ? 'page' : undefined}
						>{t(item.key)}{#if badgeFor(item.href)}<span class="ms-2 rounded-full bg-accent-400 px-2 text-xs font-bold text-ink tabular-nums"
								><span aria-hidden="true">{badgeFor(item.href)}</span><span class="sr-only"> – {t('nav.toHandle', { count: badgeFor(item.href) })}</span></span
							>{/if}</a
					>
				{/each}
			</nav>
		</aside>

		<div class="flex min-w-0 flex-1 flex-col">
			<header class="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-2 print:hidden">
				<span class="min-w-0 flex-1 truncate font-semibold text-slate-800">{practice?.name ?? t('common.appName')}</span>
				{#if !isAdmin}<div class="hidden min-w-0 flex-1 sm:block"><GlobalSearch /></div>{/if}
				<LanguageSwitch onchange={saveLanguage} />
				<button type="button" class="btn-secondary min-h-9 px-3 py-1 text-sm" onclick={logout}>{t('common.logout')}</button>
			</header>
			{#if practice?.isDemo}
				<p class="bg-accent-400 px-4 py-2 text-center text-sm font-medium text-ink print:hidden">{t('shell.demoBanner')}</p>
			{/if}
			{#if practice?.status === 'suspended'}
				<p class="bg-rose-100 px-4 py-2 text-center text-sm text-rose-900 print:hidden">{t('shell.suspended')}</p>
			{/if}
			{#if pwa.offline}
				<p class="bg-amber-100 px-4 py-2 text-center text-sm text-amber-900 print:hidden">
					<strong>{t('shell.offline')}</strong> – {t('shell.offlineHint')}
				</p>
			{/if}
			<main class="mx-auto w-full max-w-6xl flex-1 px-4 pt-6 pb-24 md:pb-8">{@render children()}</main>
		</div>

		<nav
			aria-label={t('nav.mobileLabel')}
			class="fixed inset-x-0 bottom-0 z-10 flex border-t border-slate-200 bg-white md:hidden print:hidden"
		>
			{#each bottom as item (item.href)}
				<a
					href={item.href}
					class="flex min-h-14 flex-1 items-center justify-center px-1 text-center text-xs font-medium text-slate-600"
					class:text-brand-800={active(item.href)}
					aria-current={active(item.href) ? 'page' : undefined}
					>{t(item.short ?? item.key)}{#if badgeFor(item.href)}<span class="ms-1 rounded-full bg-accent-400 px-1.5 text-[0.7rem] font-bold text-ink tabular-nums"
							><span aria-hidden="true">{badgeFor(item.href)}</span><span class="sr-only"> – {t('nav.toHandle', { count: badgeFor(item.href) })}</span></span
						>{/if}</a
				>
			{/each}
			{#if more.length}
				<button
					type="button"
					class="flex min-h-14 flex-1 items-center justify-center text-xs font-medium text-slate-600"
					aria-expanded={moreOpen}
					onclick={() => (moreOpen = !moreOpen)}>{t('nav.more')}</button
				>
			{/if}
		</nav>
		{#if moreOpen}
			<div
				role="dialog"
				aria-label={t('nav.more')}
				class="fixed inset-x-0 bottom-14 z-20 flex flex-col gap-1 border-t border-slate-200 bg-white p-3 shadow-lg md:hidden"
			>
				{#each more as item (item.href)}
					<a href={item.href} class="rounded-lg px-3 py-3 font-medium text-slate-700" onclick={() => (moreOpen = false)}
						>{t(item.key)}</a
					>
				{/each}
			</div>
		{/if}
	</div>
{/if}
