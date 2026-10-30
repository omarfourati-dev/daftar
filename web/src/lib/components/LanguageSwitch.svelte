<script lang="ts">
	import { i18n, LOCALES, t, type Locale } from '../i18n.svelte';

	/** Called after the switch, e.g. to save the language on the account. */
	let { onchange }: { onchange?: (locale: Locale) => void } = $props();
	const labels: Record<Locale, () => string> = { fr: () => t('common.french'), ar: () => t('common.arabic') };

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
			class="min-h-9 rounded-md px-3 font-medium"
			class:bg-brand-700={i18n.locale === locale}
			class:text-white={i18n.locale === locale}
			aria-pressed={i18n.locale === locale}
			onclick={() => choose(locale)}>{labels[locale]()}</button
		>
	{/each}
</div>
