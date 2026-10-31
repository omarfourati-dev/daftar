<script lang="ts">
	/** Heading and sections of the administration (practices, subscriptions, pilot requests, feedback). */
	import { t } from '../../i18n.svelte';

	type Tab = 'practices' | 'billing' | 'pilots' | 'feedback';
	let { current }: { current: Tab } = $props();
	const TABS: { key: Tab; href: string }[] = [
		{ key: 'practices', href: '/app/admin' },
		{ key: 'billing', href: '/app/admin/abonnements' },
		{ key: 'pilots', href: '/app/admin/demandes' },
		{ key: 'feedback', href: '/app/admin/retours' }
	];
</script>

<div class="mb-6 flex flex-col gap-4">
	<h1 class="text-2xl font-bold text-ink">{t('admin.title')}</h1>
	<nav aria-label={t('admin.tabs.label')} class="-mx-4 overflow-x-auto px-4">
		<ul class="flex min-w-max gap-1 border-b border-slate-200">
			{#each TABS as tab (tab.key)}
				<li>
					<a
						href={tab.href}
						aria-current={tab.key === current ? 'page' : undefined}
						class="-mb-px inline-flex min-h-11 items-center border-b-2 px-3 font-medium {tab.key === current
							? 'border-brand-700 text-brand-800'
							: 'border-transparent text-slate-600 hover:text-brand-800'}">{t(`admin.tabs.${tab.key}`)}</a
					>
				</li>
			{/each}
		</ul>
	</nav>
</div>
