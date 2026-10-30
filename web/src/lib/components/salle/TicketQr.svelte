<script lang="ts">
	/** QR code + WhatsApp link of one ticket: the patient photographs it and follows their turn (numbers only). */
	import { ticketMessage, ticketPath, ticketUrl } from '../../agenda/queue';
	import { whatsappUrl } from '../../agenda/links';
	import { t } from '../../i18n.svelte';
	import type { QueueEntry } from '../../types/queue';
	import Icon from '../daily/Icon.svelte';
	import QrCode from '../daily/QrCode.svelte';

	let { entry, practice }: { entry: QueueEntry; practice: string } = $props();
</script>

<div class="flex flex-col items-center gap-3 text-center">
	<QrCode value={ticketUrl(entry.ticketToken)} label={t('salle.qr.image', { number: entry.ticketNo })} class="h-56 w-56" />
	<p class="max-w-xs text-sm text-slate-600">{t('salle.qr.hint')}</p>
	<div class="flex flex-wrap justify-center gap-2">
		{#if entry.phone}
			<a class="btn min-h-11 bg-[#25d366] text-ink hover:bg-[#1ebe5b]" href={whatsappUrl(entry.phone, ticketMessage(entry, practice))} target="_blank" rel="noopener noreferrer"
				><Icon name="chat" />{t('salle.actions.whatsapp')}</a
			>
		{/if}
		<a class="btn-secondary min-h-11" href={ticketPath(entry.ticketToken)} target="_blank" rel="noopener noreferrer"><Icon name="external" />{t('salle.qr.open')}</a>
	</div>
</div>
