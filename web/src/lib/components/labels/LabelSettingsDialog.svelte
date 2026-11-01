<script lang="ts">
	/**
	 * Label settings of the practice (assistant and owner): the printer format of each kind of label and how long a
	 * pack stays usable per packaging. Daftar proposes 90 days; the practice enters its own protocol.
	 */
	import { untrack } from 'svelte';
	import { api } from '../../api';
	import { t } from '../../i18n.svelte';
	import { FORMATS, PACKAGINGS, labelsError } from '../../labels';
	import type { LabelSettings } from '../../types/labels';
	import Modal from '../daily/Modal.svelte';

	type Props = { settings: LabelSettings; onsaved: (s: LabelSettings) => void; onclose: () => void };
	let { settings, onsaved, onclose }: Props = $props();

	const start = untrack(() => settings);
	let formats = $state({ ...start.formats });
	let days = $state({ ...start.shelfLifeDays });
	let error = $state('');
	let busy = $state(false);

	async function save(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		if (PACKAGINGS.some((p) => !Number.isInteger(days[p]) || days[p] < 1 || days[p] > 1825)) {
			error = t('labels.settings.daysInvalid');
			return;
		}
		busy = true;
		try {
			onsaved(await api<LabelSettings>('/api/labels/settings', { method: 'PATCH', json: { formats, shelfLifeDays: days } }));
		} catch (err) {
			error = labelsError(err);
		} finally {
			busy = false;
		}
	}
</script>

<Modal title={t('labels.settings.title')} {onclose} guard>
	<form id="label-settings" class="flex flex-col gap-5" onsubmit={save} novalidate>
		<div class="grid gap-3 sm:grid-cols-2">
			<label class="label"
				>{t('labels.settings.formatSterile')}
				<select class="input" bind:value={formats.sterile} data-autofocus>
					{#each FORMATS as f (f)}<option value={f}>{t(`labels.formats.${f}`)}</option>{/each}
				</select>
			</label>
			<label class="label"
				>{t('labels.settings.formatSpecimen')}
				<select class="input" bind:value={formats.specimen}>
					{#each FORMATS as f (f)}<option value={f}>{t(`labels.formats.${f}`)}</option>{/each}
				</select>
			</label>
		</div>
		<fieldset class="flex flex-col gap-2">
			<legend class="mb-1 font-semibold">{t('labels.settings.shelfLife')}</legend>
			<p class="text-sm text-slate-600">{t('labels.settings.shelfLifeHint')}</p>
			<div class="grid gap-3 sm:grid-cols-2">
				{#each PACKAGINGS as p (p)}
					<label class="label"
						>{t(`labels.packagings.${p}`)}
						<span class="flex items-center gap-2">
							<input class="input w-28 text-center tabular-nums" type="number" inputmode="numeric" min="1" max="1825" step="1" bind:value={days[p]} />
							<span class="text-sm text-slate-600">{t('labels.settings.days')}</span>
						</span>
					</label>
				{/each}
			</div>
		</fieldset>
		<a class="self-start text-sm font-semibold text-brand-800 underline-offset-2 hover:underline" href="/app/etiquettes?test=1">{t('labels.settings.test')}</a>
		{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}
	</form>
	{#snippet footer()}
		<button type="button" class="btn-secondary" onclick={onclose}>{t('common.cancel')}</button>
		<button type="submit" form="label-settings" class="btn-primary" disabled={busy}>{t('labels.settings.save')}</button>
	{/snippet}
</Modal>
