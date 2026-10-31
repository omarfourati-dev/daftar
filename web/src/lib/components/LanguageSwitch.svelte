<script lang="ts">
	import { i18n, LOCALES, t, type Locale } from '../i18n.svelte';

	/**
	 * `onchange`: called after the switch, e.g. to save the language on the account. `compact`: below `lg` the buttons
	 * show "FR" / "ع" (the full names stay for screen readers) – the app header on phones and tablets. The short label
	 * is not hidden from screen readers: the name starts with what is visible ("FR Français", WCAG 2.5.3); from `lg`
	 * on it is `display: none` and the name is the full one.
	 */
	let { onchange, compact = false }: { onchange?: (locale: Locale) => void; compact?: boolean } = $props();
	const labels: Record<Locale, () => string> = { fr: () => t('common.french'), ar: () => t('common.arabic') };
	const SHORT: Record<Locale, string> = { fr: 'FR', ar: 'ع' };

	function choose(locale: Locale) {
		if (locale === i18n.locale) return;
		i18n.setLocale(locale);
		onchange?.(locale);
	}
</script>

<div class="inline-flex rounded-lg border border-slate-300 bg-white p-0.5 text-sm" role="group" aria-label={t('common.language')}>
	{#each LOCALES as locale (locale)}
		<button
			type="button"
			lang={locale}
			class="min-h-9 rounded-md font-medium {compact ? 'min-w-9 px-2 lg:px-3' : 'px-3'}"
			class:bg-brand-700={i18n.locale === locale}
			class:text-white={i18n.locale === locale}
			aria-pressed={i18n.locale === locale}
			onclick={() => choose(locale)}
			>{#if compact}<span class="lg:hidden">{SHORT[locale]}</span> <span class="max-lg:sr-only">{labels[locale]()}</span
				>{:else}{labels[locale]()}{/if}</button
		>
	{/each}
</div>
