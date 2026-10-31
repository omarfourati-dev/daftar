<script lang="ts">
	/** Online booking settings, the booking link with its QR code (generated locally) and the A4 poster (C1, C3). */
	import { onMount } from 'svelte';
	import { api, apiErrorMessage } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { t } from '#lib/i18n.svelte';
	import { practiceUrl } from '#lib/links';
	import { readOnlineBooking, type OnlineBooking } from '#lib/online-booking';
	import { bookingProblems, type Problems } from '#lib/practice-form';
	import type { Practice } from '#lib/types/practice';
	import CopyLink from '../../../../lib/components/CopyLink.svelte';
	import LoadState from '../../../../lib/components/LoadState.svelte';
	import QrCode from '../../../../lib/components/QrCode.svelte';
	import OnlineBookingFields from '../../../../lib/components/practice/OnlineBookingFields.svelte';
	import OwnerOnly from '../../../../lib/components/reglages/OwnerOnly.svelte';

	let practice = $state<Practice | null>(null);
	let settings = $state<OnlineBooking | null>(null);
	let saved = '';
	let loading = $state(true);
	let error = $state('');
	let problems = $state<Problems>({});
	let notice = $state('');
	let saveError = $state('');
	let busy = $state(false);

	async function load() {
		loading = true;
		error = '';
		try {
			practice = await api<Practice>('/api/practice');
			settings = readOnlineBooking(practice);
			saved = JSON.stringify(settings);
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			loading = false;
		}
	}
	onMount(() => {
		if (auth.user?.role === 'owner') void load();
	});

	async function save(e: SubmitEvent) {
		e.preventDefault();
		if (!settings) return;
		notice = '';
		saveError = '';
		problems = bookingProblems(settings);
		if (Object.keys(problems).length) return;
		if (JSON.stringify(settings) === saved) {
			notice = t('admin.edit.nothingToSave');
			return;
		}
		busy = true;
		try {
			await api<Practice>('/api/practice', { method: 'PATCH', json: { onlineBooking: { ...settings } } });
			saved = JSON.stringify(settings);
			notice = t('kit.saved');
		} catch (err) {
			saveError = apiErrorMessage(err);
		} finally {
			busy = false;
		}
	}

	const url = $derived(practice ? practiceUrl(practice.slug, '/') : '');
</script>

<OwnerOnly>
	<div class="flex flex-col gap-6">
		<h2 class="text-xl font-bold text-ink">{t('reglages.reservation.title')}</h2>
		<LoadState {loading} {error} onretry={load} />
		{#if practice && settings}
			<section class="card flex flex-col gap-4" aria-labelledby="r-page">
				<h3 id="r-page" class="font-semibold text-ink">{t('reglages.reservation.pageTitle')}</h3>
				<p class="max-w-2xl text-sm text-slate-600">{t('reglages.reservation.pageText')}</p>
				{#if !settings.enabled}
					<p class="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">{t('reglages.reservation.disabled')}</p>
				{/if}
				<CopyLink
					label={t('reglages.reservation.link')}
					{url}
					openable
					whatsappText={t('reglages.reservation.shareMessage', { practice: practice.name, url })}
				/>
				<div class="flex flex-col items-start gap-4 sm:flex-row sm:items-center">
					<div class="rounded-2xl border border-slate-200 bg-white p-3">
						<QrCode text={url} label={t('reglages.reservation.qr')} class="h-40 w-40" />
					</div>
					<div class="flex flex-col gap-3">
						<p class="max-w-sm text-sm text-slate-600">{t('reglages.reservation.qrHint')}</p>
						<a class="btn-secondary self-start" href="/app/reglages/affiche">{t('reglages.reservation.poster')}</a>
					</div>
				</div>
			</section>

			<form class="flex flex-col gap-4" novalidate onsubmit={save}>
				<OnlineBookingFields bind:value={settings} {problems} />
				<div class="flex flex-wrap items-center gap-3">
					<button type="submit" class="btn-primary" disabled={busy}>{t('reglages.reservation.save')}</button>
					<p role="status" class="text-sm font-medium text-brand-800">{notice}</p>
					{#if saveError}<p role="alert" class="text-sm font-medium text-red-700">{saveError}</p>{/if}
				</div>
			</form>
		{/if}
	</div>
</OwnerOnly>
