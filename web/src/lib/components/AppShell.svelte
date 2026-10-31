<script lang="ts">
	/**
	 * Frame of every /app page: guard (→ /connexion), account refresh, navigation (sidebar on desktop, bottom bar
	 * on phones), language switch, banners (demo, suspended subscription, offline). Pages render as `children`.
	 * Tools (import, subscription, installer) sit below the main navigation and in the phone menu "Plus", which also
	 * opens the phone booking and the patient search (folded away on phones until asked for) – fixlist 2.
	 * Printable pages (receipt) hide the frame with `print:hidden` automatically.
	 */
	import { onMount, untrack, type Snippet } from 'svelte';
	import { api, deps } from '../api';
	import { auth } from '../auth.svelte';
	import { t, type MessageKey } from '../i18n.svelte';
	import { pwa } from '../pwa.svelte';
	import type { Me } from '../types';
	import FeedbackButton from './FeedbackButton.svelte';
	import LanguageSwitch from './LanguageSwitch.svelte';
	import { badges } from '../badges.svelte';
	import GlobalSearch from './daily/GlobalSearch.svelte';
	import Shortcuts from './daily/Shortcuts.svelte';
	import Icon from './daily/Icon.svelte';
	import PhoneBooking from './agenda/PhoneBooking.svelte';
	import { agendaChanges, patientSearch, phoneBooking } from '../agenda/requests.svelte';

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
	/** Less frequent pages, by role (as in the sections of /app/reglages). */
	const TOOLS: (Item & { roles: string[] })[] = [
		{ href: '/app/import', key: 'nav.import', roles: ['owner', 'assistant'] },
		{ href: '/app/abonnement', key: 'nav.abonnement', roles: ['owner'] },
		{ href: '/app/installer', key: 'nav.installer', roles: ['owner', 'assistant', 'dentist'] }
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
	const tools = $derived(isAdmin ? [] : TOOLS.filter((i) => i.roles.includes(String(auth.user?.role))));
	const practice = $derived(auth.user?.practice ?? null);
	let moreOpen = $state(false);

	const active = (href: string) => (href === '/app' ? path === '/app' || path === '/app/' : path === href || path.startsWith(href + '/'));

	// every new page folds the phone search away again
	$effect(() => {
		void path;
		untrack(() => (patientSearch.open = false));
	});

	function fromMenu(action: () => void) {
		moreOpen = false;
		action();
	}

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
	{#if phoneBooking.open && !isAdmin}
		<PhoneBooking onbooked={() => agendaChanges.bump()} onclose={() => (phoneBooking.open = false)} />
	{/if}
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
			{#if tools.length}
				<nav aria-labelledby="nav-tools" class="flex flex-col gap-0.5 border-t border-slate-200 pt-3">
					<p id="nav-tools" class="px-3 pb-1 text-xs font-semibold tracking-wide text-slate-500 uppercase">{t('nav.tools')}</p>
					{#each tools as item (item.href)}
						<a
							href={item.href}
							class="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-brand-50 hover:text-brand-800"
							class:bg-brand-50={active(item.href)}
							class:text-brand-800={active(item.href)}
							aria-current={active(item.href) ? 'page' : undefined}>{t(item.key)}</a
						>
					{/each}
				</nav>
			{/if}
		</aside>

		<div class="flex min-w-0 flex-1 flex-col">
			<header class="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-slate-200 bg-white px-4 py-2 print:hidden">
				<span dir="auto" class="min-w-0 flex-1 truncate font-semibold text-slate-800 rtl:text-right">{practice?.name ?? t('common.appName')}</span>
				{#if !isAdmin}
					<!-- on phones a row of its own, shown from the menu "Plus" or the button on "Aujourd'hui" -->
					<div data-search class="{patientSearch.open ? 'block' : 'hidden'} order-last w-full min-w-0 sm:order-none sm:block sm:w-auto sm:flex-1">
						<GlobalSearch />
					</div>
					<button
						type="button"
						class="btn-secondary hidden min-h-10 px-3 text-sm sm:inline-flex"
						aria-label={t('agenda.phone.button')}
						title="{t('agenda.phone.button')} (T)"
						onclick={() => (phoneBooking.open = true)}><Icon name="phone" class="h-4 w-4" /><span class="hidden xl:inline">{t('agenda.phone.button')}</span></button
					>
					<FeedbackButton {path} />
				{/if}
				<LanguageSwitch onchange={saveLanguage} compact />
				<button type="button" class="btn-secondary min-h-9 px-2.5 py-1 text-sm lg:px-3" title={t('common.logout')} onclick={logout}
					><Icon name="logout" class="h-4 w-4 lg:hidden" /><span class="max-lg:sr-only">{t('common.logout')}</span></button
				>
			</header>
			{#if practice?.isDemo}
				<p class="bg-accent-400 px-4 py-2 text-center text-sm font-medium text-ink print:hidden">{t('shell.demoBanner')}</p>
			{/if}
			{#if practice?.status === 'suspended'}
				<p class="bg-rose-100 px-4 py-2 text-center text-sm text-rose-900 print:hidden">{t('shell.suspended')}</p>
			{:else if practice?.status === 'past_due'}
				<p class="bg-amber-100 px-4 py-2 text-center text-sm text-amber-950 print:hidden">
					{auth.user?.role === 'owner' ? t('billing.pastDue') : t('billing.pastDueStaff')}
					{#if auth.user?.role === 'owner'}<a class="ms-1 font-semibold underline" href="/app/abonnement">{t('billing.pastDueLink')}</a>{/if}
				</p>
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
				class="fixed inset-x-0 bottom-14 z-20 flex max-h-[calc(100dvh-4.5rem)] flex-col gap-1 overflow-y-auto border-t border-slate-200 bg-white p-3 shadow-lg md:hidden"
			>
				<div class="grid grid-cols-2 gap-2 pb-1">
					<button type="button" class="btn-secondary min-h-12 px-2 text-sm" onclick={() => fromMenu(() => (phoneBooking.open = true))}
						><Icon name="phone" class="h-4 w-4 shrink-0" />{t('agenda.phone.button')}</button
					>
					<button type="button" class="btn-secondary min-h-12 px-2 text-sm" onclick={() => fromMenu(() => patientSearch.show())}
						><Icon name="search" class="h-4 w-4 shrink-0" />{t('patients.globalSearch')}</button
					>
				</div>
				{#each more as item (item.href)}
					<a href={item.href} class="rounded-lg px-3 py-3 font-medium text-slate-700" onclick={() => (moreOpen = false)}
						>{t(item.key)}</a
					>
				{/each}
				{#if tools.length}
					<div class="my-1 border-t border-slate-200" role="presentation"></div>
					{#each tools as item (item.href)}
						<a href={item.href} class="rounded-lg px-3 py-2.5 text-sm font-medium text-slate-600" onclick={() => (moreOpen = false)}
							>{t(item.key)}</a
						>
					{/each}
				{/if}
				<FeedbackButton {path} variant="menu" />
			</div>
		{/if}
	</div>
{/if}
