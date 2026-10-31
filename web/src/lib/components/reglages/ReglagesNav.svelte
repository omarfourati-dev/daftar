<script lang="ts">
	/**
	 * Sections of /app/reglages. The owner sees every section of the practice plus subscription, import and
	 * installation; other roles see their account (at /app/reglages), the import (assistant) and installation.
	 */
	import { auth } from '../../auth.svelte';
	import { t, type MessageKey } from '../../i18n.svelte';

	let { path }: { path: string } = $props();
	type Link = { href: string; key: MessageKey };

	const OWNER: Link[] = [
		{ href: '/app/reglages', key: 'reglages.nav.cabinet' },
		{ href: '/app/reglages/horaires', key: 'reglages.nav.horaires' },
		{ href: '/app/reglages/actes', key: 'reglages.nav.actes' },
		{ href: '/app/reglages/praticiens', key: 'reglages.nav.praticiens' },
		{ href: '/app/reglages/equipe', key: 'reglages.nav.equipe' },
		{ href: '/app/reglages/reservation', key: 'reglages.nav.reservation' },
		{ href: '/app/reglages/ecran', key: 'reglages.nav.ecran' },
		{ href: '/app/reglages/donnees', key: 'reglages.nav.donnees' },
		{ href: '/app/reglages/compte', key: 'reglages.nav.compte' }
	];
	const OWNER_MORE: Link[] = [
		{ href: '/app/abonnement', key: 'reglages.nav.abonnement' },
		{ href: '/app/import', key: 'reglages.nav.import' },
		{ href: '/app/installer', key: 'reglages.nav.installer' }
	];

	const role = $derived(auth.user?.role);
	const sections = $derived<Link[]>(role === 'owner' ? OWNER : [{ href: '/app/reglages', key: 'reglages.nav.compte' }]);
	const more = $derived<Link[]>(
		role === 'owner'
			? OWNER_MORE
			: role === 'assistant'
				? OWNER_MORE.slice(1)
				: role === 'dentist'
					? OWNER_MORE.slice(2)
					: []
	);
	/** On phones the sections scroll sideways: the current one is brought into view (e.g. after "Premiers pas"). */
	let nav = $state<HTMLElement>();
	$effect(() => {
		void path;
		nav?.querySelector<HTMLElement>('[aria-current="page"]')?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' });
	});
	const current = (href: string) => (href === '/app/reglages' ? path === href || path === href + '/' : path === href || path.startsWith(href + '/'));
	const linkClass = (href: string) =>
		`flex min-h-11 items-center whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium ${
			current(href) ? 'bg-brand-700 text-white' : 'bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-brand-50 lg:bg-transparent lg:ring-0'
		}`;
</script>

<nav bind:this={nav} aria-label={t('reglages.nav.label')} class="-mx-4 overflow-x-auto px-4 lg:mx-0 lg:px-0">
	<ul class="flex min-w-max gap-2 lg:min-w-0 lg:flex-col lg:gap-0.5">
		{#each sections as link (link.href)}
			<li><a href={link.href} class={linkClass(link.href)} aria-current={current(link.href) ? 'page' : undefined}>{t(link.key)}</a></li>
		{/each}
	</ul>
	{#if more.length}
		<p class="mt-4 mb-1 hidden px-3 text-xs font-semibold text-slate-500 lg:block">{t('reglages.nav.more')}</p>
		<ul class="mt-2 flex min-w-max gap-2 lg:mt-0 lg:min-w-0 lg:flex-col lg:gap-0.5">
			{#each more as link (link.href)}
				<li><a href={link.href} class={linkClass(link.href)}>{t(link.key)}</a></li>
			{/each}
		</ul>
	{/if}
</nav>
