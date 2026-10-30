<script lang="ts">
	/** `/rdv/<token>` – the patient's own link: the appointment, its status, the practice's contact, cancel (11.3). */
	import { onMount } from 'svelte';
	import { api, ApiError } from '#lib/api';
	import { bookingErrorMessage, useBookingManifest } from '#lib/booking';
	import { currentPracticeSlug } from '#lib/host';
	import { applyLocaleFromQuery, formatDateTime, i18n, t, translate } from '#lib/i18n.svelte';
	import { telUrl, whatsappUrl } from '#lib/links';
	import { appointmentStatusClass, type AppointmentStatus } from '#lib/status';
	import type { ManagedBooking } from '#lib/types/booking';
	import ConfirmDialog from '../../../lib/components/ConfirmDialog.svelte';
	import LanguageSwitch from '../../../lib/components/LanguageSwitch.svelte';
	import AppointmentEntry from '../../../lib/components/booking/AppointmentEntry.svelte';

	let { data }: { data: { token: string } } = $props();
	applyLocaleFromQuery();

	let booking = $state<ManagedBooking | null>(null);
	let loading = $state(true);
	let error = $state('');
	let confirming = $state(false);
	let cancelError = $state('');
	let busy = $state(false);
	let notice = $state('');
	const host = currentPracticeSlug();

	onMount(async () => {
		if (host) useBookingManifest();
		try {
			booking = await api<ManagedBooking>(`/api/public/bookings/${encodeURIComponent(data.token)}`);
		} catch (err) {
			error = err instanceof ApiError && err.status === 404 ? t('booking.manage.notFound') : bookingErrorMessage(err);
		} finally {
			loading = false;
		}
	});

	const ACTIVE = ['requested', 'confirmed', 'scheduled'];
	const now = () => Date.now();
	const starts = $derived(booking ? new Date(booking.startsAt).getTime() : 0);
	const past = $derived(!!booking && starts < now() && booking.status !== 'cancelled');
	const deadline = $derived(booking?.cancelUntil ? new Date(booking.cancelUntil).getTime() : starts);
	const tooLate = $derived(!!booking && !past && now() > deadline);
	const canCancel = $derived(!!booking && (booking.canCancel ?? (ACTIVE.includes(booking.status) && !past && !tooLate)));
	const practiceName = $derived(booking ? (i18n.locale === 'ar' && booking.practice.nameAr ? booking.practice.nameAr : booking.practice.name) : '');
	const bookAgain = $derived(booking ? (host === booking.practice.slug ? '/' : `/r/${booking.practice.slug}`) : '/');

	async function cancel() {
		busy = true;
		cancelError = '';
		try {
			const answer = await api<ManagedBooking | undefined>(`/api/public/bookings/${encodeURIComponent(data.token)}/cancel`, { method: 'POST' });
			booking = { ...booking!, ...(answer ?? {}), status: 'cancelled' };
			confirming = false;
			notice = t('booking.manage.cancelled');
		} catch (err) {
			cancelError = bookingErrorMessage(err);
		} finally {
			busy = false;
		}
	}
</script>

<svelte:head><title>{t('booking.manage.title')} · {booking ? practiceName : 'Daftar'}</title></svelte:head>

<div class="min-h-screen bg-surface">
	<main class="mx-auto flex max-w-xl flex-col gap-5 px-4 py-4">
		<div class="flex justify-end"><LanguageSwitch /></div>
		<h1 class="text-2xl font-bold text-ink">{t('booking.manage.title')}</h1>

		{#if loading}
			<p role="status" class="text-slate-600">{t('common.loading')}</p>
		{:else if error}
			<p role="alert" class="card text-slate-800">{error}</p>
		{:else if booking}
			{#if notice}<p role="status" class="rounded-xl bg-brand-50 px-4 py-3 font-medium text-brand-900">{notice}</p>{/if}
			<AppointmentEntry
				startsAt={booking.startsAt}
				service={booking.serviceName}
				practitioner={booking.practitionerName}
				practice={practiceName}
				address={[booking.practice.address, booking.practice.city].filter(Boolean).join(', ')}
			>
				{#snippet badge()}
					<span class="inline-flex rounded-full px-2.5 py-0.5 text-sm font-semibold {appointmentStatusClass(booking!.status as AppointmentStatus)}"
						>{translate(`booking.manage.status.${booking!.status}`) ?? booking!.status}</span
					>
				{/snippet}
			</AppointmentEntry>

			{#if past}
				<p class="text-slate-700">{t('booking.manage.past')}</p>
			{:else if canCancel}
				{#if booking.cancelUntil}<p class="text-sm text-slate-600">{t('booking.manage.cancelUntil', { when: formatDateTime(booking.cancelUntil) })}</p>{/if}
				<button
					type="button"
					class="btn self-start border border-rose-300 bg-white text-rose-800 hover:bg-rose-50"
					onclick={() => {
						cancelError = '';
						confirming = true;
					}}>{t('booking.manage.cancel')}</button
				>
			{:else if tooLate && ACTIVE.includes(booking.status)}
				<p class="text-slate-700">{t('booking.errors.too_late')}</p>
			{/if}

			<div class="flex flex-wrap gap-2">
				<a class="btn-secondary" href={telUrl(booking.practice.phone)}>{t('booking.call')}</a>
				{#if booking.practice.whatsapp}<a class="btn-secondary" href={whatsappUrl('', booking.practice.whatsapp)} target="_blank" rel="noopener"
						>{t('booking.whatsapp')}</a
					>{/if}
				{#if booking.practice.mapsUrl}<a class="btn-secondary" href={booking.practice.mapsUrl} target="_blank" rel="noopener">{t('booking.directions')}</a>{/if}
			</div>
			{#if !ACTIVE.includes(booking.status) || past}
				<a class="btn-primary self-start" href={bookAgain} data-sveltekit-reload>{t('booking.manage.bookAgain')}</a>
			{/if}
		{/if}
	</main>
</div>

<ConfirmDialog
	open={confirming}
	title={t('booking.manage.cancelTitle')}
	message={t('booking.manage.cancelMessage')}
	confirmLabel={t('booking.manage.cancelConfirm')}
	danger
	{busy}
	error={cancelError}
	onconfirm={cancel}
	oncancel={() => (confirming = false)}
/>
