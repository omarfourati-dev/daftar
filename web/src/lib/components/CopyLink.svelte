<script lang="ts">
	/**
	 * A link to hand out (invitation, booking page, screen): read-only field, "Copier", optionally WhatsApp with a
	 * ready message and "Ouvrir". The address is always shown left-to-right, also in Arabic.
	 */
	import { t } from '../i18n.svelte';
	import { whatsappUrl } from '../links';

	let {
		label,
		url,
		whatsappText,
		whatsappTo = null,
		openable = false,
		note
	}: {
		label: string;
		url: string;
		whatsappText?: string;
		whatsappTo?: string | null;
		openable?: boolean;
		note?: string;
	} = $props();

	const id = `link-${Math.random().toString(36).slice(2, 9)}`;
	let feedback = $state('');
	let field: HTMLInputElement;

	async function copy() {
		try {
			await navigator.clipboard.writeText(url);
			feedback = t('kit.copied');
		} catch {
			field?.select();
			feedback = t('kit.copyFailed');
		}
		setTimeout(() => (feedback = ''), 4000);
	}
</script>

<div class="flex flex-col gap-1.5">
	<label for={id} class="text-sm font-medium text-slate-700">{label}</label>
	<div class="flex flex-col gap-2 sm:flex-row">
		<input
			{id}
			bind:this={field}
			class="input min-w-0 flex-1 bg-slate-50 font-mono text-sm"
			dir="ltr"
			readonly
			value={url}
			onfocus={(e) => e.currentTarget.select()}
		/>
		<div class="flex flex-wrap gap-2">
			<button type="button" class="btn-primary flex-1 sm:flex-none" onclick={copy}>{t('kit.copy')}</button>
			{#if whatsappText}
				<a class="btn-secondary flex-1 sm:flex-none" href={whatsappUrl(whatsappText, whatsappTo)} target="_blank" rel="noopener"
					>{t('kit.sendWhatsapp')}</a
				>
			{/if}
			{#if openable}
				<a class="btn-secondary flex-1 sm:flex-none" href={url} target="_blank" rel="noopener">{t('kit.open')}</a>
			{/if}
		</div>
	</div>
	<p role="status" class="min-h-5 text-sm font-medium text-brand-800">{feedback}</p>
	{#if note}<p class="text-sm text-slate-600">{note}</p>{/if}
</div>
