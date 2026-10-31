<script lang="ts">
	/**
	 * The booking page of a practice (sections 11.3, 13; story C1), mostly opened on a phone from WhatsApp:
	 * practice profile → act → practitioner ("peu importe") → day strip → free times → name, phone, consent, note
	 * → confirmation with the personal link. 409 (time taken) goes back to the times; 422 `booking_refused` (one
	 * answer for every reason of the person – no-shows, bookings, an appointment at that time) and 429 limits are
	 * explained with a call button.
	 */
	import { onMount, tick } from 'svelte';
	import { api, ApiError } from '../../api';
	import { bookingDays, bookingErrorMessage, dayParts, serviceName } from '../../booking';
	import { hoursSummary, isOpenOn, normalizeWeeklyHours, type WeeklyHours } from '../../hours';
	import { formatDate, formatMillimes, formatTime, i18n, t, todayTunis, translate, tunisInstant } from '../../i18n.svelte';
	import { initials } from '../../initials';
	import { mainUrl, telUrl, whatsappUrl } from '../../links';
	import { formatPhone, looksLikePhone } from '../../phone-check';
	import type { BookingCreated, PublicPracticeProfile, SlotsAnswer } from '../../types/booking';
	import CopyLink from '../CopyLink.svelte';
	import LanguageSwitch from '../LanguageSwitch.svelte';
	import TextField from '../form/TextField.svelte';
	import AppointmentEntry from './AppointmentEntry.svelte';

	let { slug }: { slug: string } = $props();

	let profile = $state<PublicPracticeProfile | null>(null);
	let hours = $state<WeeklyHours | null>(null);
	let loading = $state(true);
	let loadError = $state('');

	let view = $state<'select' | 'details' | 'done'>('select');
	let serviceId = $state<number | null>(null);
	let practitionerId = $state<string>('');
	let day = $state('');
	let time = $state('');
	let slots = $state<string[]>([]);
	let slotsLoading = $state(false);
	let slotsError = $state('');
	let selectError = $state('');
	let request = 0;

	let firstName = $state('');
	let lastName = $state('');
	let phone = $state('');
	let note = $state('');
	let consent = $state(false);
	let website = $state('');
	let fieldErrors = $state<{ firstName?: string; lastName?: string; phone?: string }>({});
	let submitError = $state('');
	let offerCall = $state(false);
	let sending = $state(false);
	let created = $state<BookingCreated | null>(null);
	let detailsHeading = $state<HTMLHeadingElement>();
	let doneHeading = $state<HTMLHeadingElement>();
	let timesSection = $state<HTMLElement>();

	onMount(async () => {
		try {
			profile = await api<PublicPracticeProfile>(`/api/public/practices/${encodeURIComponent(slug)}`);
			hours = normalizeWeeklyHours(profile.weeklyHours);
		} catch (err) {
			loadError = err instanceof ApiError && err.status === 404 ? t('booking.notFound') : bookingErrorMessage(err);
		} finally {
			loading = false;
		}
	});

	const ar = $derived(i18n.locale === 'ar');
	const title = $derived(profile ? (ar && profile.nameAr ? profile.nameAr : profile.name) : '');
	const otherName = $derived(profile ? (ar ? (profile.nameAr ? profile.name : '') : profile.nameAr) : '');
	const description = $derived(profile ? (ar ? profile.descriptionAr || profile.descriptionFr : profile.descriptionFr || profile.descriptionAr) : '');
	const color = $derived(profile?.brandColor && /^#[0-9a-f]{6}$/i.test(profile.brandColor) ? profile.brandColor : '#0f766e');
	const specialtyLine = $derived(
		profile ? [translate(`specialty.${profile.specialty}`) ?? '', profile.city].filter(Boolean).join(' · ') : ''
	);
	const today = $derived(todayTunis());
	const days = $derived(profile ? bookingDays(today, profile.horizonDays || 30) : []);
	const service = $derived(profile?.services.find((s) => s.id === serviceId) ?? null);
	const practitioner = $derived(profile?.practitioners.find((p) => String(p.id) === practitionerId) ?? null);
	const fullName = (p: { title?: string; name: string }) => `${p.title ?? ''} ${p.name}`.trim();
	const open = (d: string) => !!hours && isOpenOn(hours, d);
	const monthOfDay = $derived(day ? dayParts(day).monthYear : days.length ? dayParts(days[0]).monthYear : '');
	const summary = $derived(day && time && service ? `${dayParts(day).weekday} ${dayParts(day).day} ${dayParts(day).month} · ${time} · ${serviceName(service)}` : '');

	function nextOpenDay(from: string): string | null {
		const index = days.indexOf(from);
		return days.slice(index + 1).find(open) ?? null;
	}

	/** Free times of `date`; when the day was chosen for the patient (`auto`) and is full, the next open day is tried. */
	async function loadSlots(date: string, auto: boolean) {
		if (!serviceId) return;
		const mine = ++request;
		day = date;
		time = '';
		slots = [];
		slotsError = '';
		slotsLoading = true;
		try {
			let current: string | null = date;
			for (let tries = 0; current && tries < 7; tries++) {
				const params = new URLSearchParams({ date: current, serviceId: String(serviceId) });
				if (practitionerId) params.set('practitionerId', practitionerId);
				const answer = await api<SlotsAnswer>(`/api/public/practices/${encodeURIComponent(slug)}/slots?${params}`);
				if (mine !== request) return;
				day = current;
				slots = answer.slots;
				if (answer.slots.length || !auto) break;
				current = nextOpenDay(current);
			}
		} catch (err) {
			if (mine === request) slotsError = bookingErrorMessage(err);
		} finally {
			if (mine === request) slotsLoading = false;
		}
	}

	function chooseService(id: number) {
		serviceId = id;
		selectError = '';
		const first = days.find(open);
		if (first) void loadSlots(first, true);
	}

	function choosePractitioner(id: string) {
		practitionerId = id;
		if (day) void loadSlots(day, false);
	}

	async function toDetails() {
		view = 'details';
		await tick();
		detailsHeading?.focus();
		detailsHeading?.scrollIntoView?.({ block: 'start' });
	}

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		submitError = '';
		offerCall = false;
		const errors: typeof fieldErrors = {};
		if (!firstName.trim()) errors.firstName = t('kit.fieldRequired');
		if (!lastName.trim()) errors.lastName = t('kit.fieldRequired');
		if (!phone.trim()) errors.phone = t('kit.fieldRequired');
		else if (!looksLikePhone(phone)) errors.phone = t('kit.invalidPhone');
		fieldErrors = errors;
		if (Object.keys(errors).length) {
			await tick();
			document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
			return;
		}
		if (!serviceId || !day || !time) return;
		const body: Record<string, unknown> = { serviceId };
		if (practitionerId) body.practitionerId = Number(practitionerId);
		Object.assign(body, {
			startsAt: tunisInstant(day, time),
			firstName: firstName.trim(),
			lastName: lastName.trim(),
			phone: phone.trim(),
			lang: i18n.locale,
			reminderConsent: consent
		});
		if (note.trim()) body.note = note.trim();
		body.website = website;
		sending = true;
		try {
			created = await api<BookingCreated>(`/api/public/practices/${encodeURIComponent(slug)}/bookings`, { method: 'POST', json: body });
			view = 'done';
			await tick();
			doneHeading?.focus();
			doneHeading?.scrollIntoView?.({ block: 'start' });
		} catch (err) {
			const backToTimes = ['too_soon', 'outside_horizon', 'invalid_service', 'invalid_practitioner'];
			if (err instanceof ApiError && (err.status === 409 || backToTimes.includes(err.code ?? ''))) {
				selectError = bookingErrorMessage(err);
				view = 'select';
				await loadSlots(day, false);
				await tick();
				timesSection?.scrollIntoView?.({ block: 'start' });
			} else if (err instanceof ApiError && err.code === 'invalid_phone') {
				fieldErrors = { phone: t('kit.invalidPhone') };
			} else {
				submitError = bookingErrorMessage(err);
				offerCall = err instanceof ApiError && (err.status === 422 || err.status === 429 || err.status === 403);
			}
		} finally {
			sending = false;
		}
	}

	function restart() {
		created = null;
		serviceId = null;
		practitionerId = '';
		day = '';
		time = '';
		slots = [];
		note = '';
		view = 'select';
	}

	/** The patient's own link: the token in the fragment (`/rdv#…`) never reaches a server log. */
	const manageUrl = $derived(created ? `${location.origin}/rdv#${created.manageToken}` : '');
	const privacyUrl = $derived(mainUrl(ar ? '/ar/confidentialite/' : '/confidentialite/'));
	const hoursLines = $derived(hours ? hoursSummary(hours) : []);
	const dayRange = (from: string, to: string) =>
		from === to ? t(`kit.weekdaysShort.${from as '1'}`) : `${t(`kit.weekdaysShort.${from as '1'}`)} – ${t(`kit.weekdaysShort.${to as '1'}`)}`;
</script>

<svelte:head><title>{profile ? `${title} · ${t('booking.title')}` : t('booking.title')}</title></svelte:head>

<div class="min-h-screen bg-surface pb-32">
	<div class="mx-auto flex max-w-5xl justify-end px-4 pt-3"><LanguageSwitch /></div>

	{#if loading}
		<p role="status" class="mx-auto max-w-xl px-4 py-16 text-center text-slate-600">{t('booking.loading')}</p>
	{:else if loadError}
		<div class="mx-auto max-w-xl px-4 py-16">
			<p role="alert" class="card text-center text-slate-800">{loadError}</p>
		</div>
	{:else if profile}
		<header class="ruled mx-auto mt-2 max-w-5xl px-4 pt-4 pb-5 sm:rounded-2xl">
			<div class="flex items-center gap-4">
				<span
					class="inline-flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl text-2xl font-bold text-white shadow-sm"
					style="background:{color}"
					aria-hidden="true">{initials(profile.name)}</span
				>
				<div class="min-w-0">
					<h1 class="text-2xl leading-tight font-bold text-ink sm:text-3xl">{title}</h1>
					{#if otherName}<p class="text-lg font-semibold text-slate-700" lang={ar ? 'fr' : 'ar'} dir={ar ? 'ltr' : 'rtl'}>{otherName}</p>{/if}
					<p class="text-slate-600"><bdi>{specialtyLine}</bdi></p>
				</div>
			</div>
			<div class="mt-4 flex flex-wrap gap-2">
				<a class="pill" href={telUrl(profile.phone)}>
					<svg viewBox="0 0 20 20" class="h-4 w-4" aria-hidden="true" fill="currentColor"
						><path d="M5.6 2.5l2.2 2.6c.4.5.4 1.2 0 1.6L6.6 8a10 10 0 0 0 5.4 5.4l1.3-1.2c.4-.4 1.1-.4 1.6 0l2.6 2.2c.5.4.5 1.2.1 1.7l-1 1.1c-.8.8-2 1.1-3 .7A16 16 0 0 1 2.4 6.7c-.4-1.1-.1-2.3.7-3l1.1-1c.4-.5 1.1-.5 1.4-.2z" /></svg
					>{t('booking.call')}</a
				>
				{#if profile.whatsapp}
					<a class="pill" href={whatsappUrl('', profile.whatsapp)} target="_blank" rel="noopener">{t('booking.whatsapp')}</a>
				{/if}
				{#if profile.mapsUrl}
					<a class="pill" href={profile.mapsUrl} target="_blank" rel="noopener">{t('booking.directions')}</a>
				{/if}
			</div>
		</header>

		<div class="mx-auto grid max-w-5xl gap-6 px-4 pt-6 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
			<main class="min-w-0">
				{#if !profile.onlineBookingEnabled || profile.services.length === 0}
					<div class="card flex flex-col items-start gap-3">
						<p class="text-slate-800">{profile.onlineBookingEnabled ? t('booking.noServices') : t('booking.disabled')}</p>
						<a class="btn-primary" href={telUrl(profile.phone)}>{t('booking.call')} · <span dir="ltr">{formatPhone(profile.phone)}</span></a>
					</div>
				{:else if view === 'select'}
					<h2 class="mb-5 text-2xl font-bold text-ink">{t('booking.headline')}</h2>
					{#if selectError}<p role="alert" class="mb-4 rounded-xl bg-amber-50 px-4 py-3 font-medium text-amber-900 ring-1 ring-amber-200">{selectError}</p>{/if}

					<fieldset class="mb-7 min-w-0">
						<legend class="step"><bdi>1.</bdi> {t('booking.stepService')}</legend>
						<div class="grid grid-cols-2 gap-2.5 sm:gap-3">
							{#each profile.services as s (s.id)}
								<label class="choice">
									<input
										type="radio"
										name="service"
										class="peer sr-only"
										value={s.id}
										checked={serviceId === s.id}
										onchange={() => chooseService(s.id)}
										aria-label={[serviceName(s), t('booking.minutes', { n: s.durationMin }), s.priceMillimes !== null ? formatMillimes(s.priceMillimes) : '']
											.filter(Boolean)
											.join(', ')}
									/>
									<span class="choice-box">
										<span class="block font-semibold text-ink">{serviceName(s)}</span>
										<span class="mt-0.5 flex flex-wrap gap-x-3 text-slate-600">
											<span class="tabular-nums">{t('booking.minutes', { n: s.durationMin })}</span>
											{#if s.priceMillimes !== null}<span class="tabular-nums">{formatMillimes(s.priceMillimes)}</span>{/if}
										</span>
									</span>
								</label>
							{/each}
						</div>
					</fieldset>

					{#if profile.practitioners.length > 1}
						<fieldset class="mb-7 min-w-0">
							<legend class="step"><bdi>2.</bdi> {t('booking.stepPractitioner')}</legend>
							<div class="flex flex-wrap gap-2">
								{#each [{ id: '', label: t('booking.anyPractitioner') }, ...profile.practitioners.map((p) => ({ id: String(p.id), label: fullName(p) }))] as option (option.id)}
									<label class="choice">
										<input
											type="radio"
											name="practitioner"
											class="peer sr-only"
											value={option.id}
											checked={practitionerId === option.id}
											onchange={() => choosePractitioner(option.id)}
										/>
										<span class="choice-box px-4 py-2.5 font-semibold">{option.label}</span>
									</label>
								{/each}
							</div>
						</fieldset>
					{/if}

					{#if serviceId}
						{@const n = profile.practitioners.length > 1 ? 3 : 2}
						<fieldset class="mb-7 min-w-0">
							<div class="mb-3 flex items-baseline justify-between gap-3">
								<legend class="step mb-0"><bdi>{n}.</bdi> {t('booking.stepDay')}</legend>
								<span class="text-sm text-slate-600 first-letter:uppercase" aria-live="polite">{monthOfDay}</span>
							</div>
							<div class="-mx-4 overflow-x-auto px-4 pb-2" role="radiogroup" aria-label={t('booking.daysLabel')}>
								<div class="flex w-max gap-2">
									{#each days as d (d)}
										{@const parts = dayParts(d)}
										{@const isOpen = open(d)}
										<label class="choice w-16 shrink-0">
											<input
												type="radio"
												name="day"
												class="peer sr-only"
												value={d}
												checked={day === d}
												disabled={!isOpen}
												onchange={() => {
													selectError = '';
													void loadSlots(d, false);
												}}
												aria-label="{parts.weekday} {parts.day} {parts.month}{isOpen ? '' : ` – ${t('booking.closed')}`}"
											/>
											<span class="choice-box flex flex-col items-center px-1 py-2 text-center peer-disabled:cursor-not-allowed peer-disabled:opacity-45">
												<span class="text-sm text-slate-600 peer-checked:text-white">{parts.weekday}</span>
												<span class="text-2xl leading-tight font-bold tabular-nums">{parts.day}</span>
												{#if !isOpen}<span class="text-[0.7rem] text-slate-500">{t('booking.closed')}</span>{/if}
											</span>
										</label>
									{/each}
								</div>
							</div>
						</fieldset>

						<section class="mb-6" bind:this={timesSection} aria-labelledby="times-title">
							<h3 id="times-title" class="step"><bdi>{n + 1}.</bdi> {t('booking.stepTime')}</h3>
							{#if slotsLoading}
								<div role="status" class="grid grid-cols-4 gap-2" aria-label={t('booking.slotsLoading')}>
									{#each Array(8) as _, i (i)}<span class="h-12 animate-pulse rounded-xl bg-slate-200/70 motion-reduce:animate-none"></span>{/each}
								</div>
							{:else if slotsError}
								<div class="card flex flex-col items-start gap-3">
									<p role="alert" class="text-slate-800">{slotsError || t('booking.slotsFailed')}</p>
									<button type="button" class="btn-secondary" onclick={() => loadSlots(day, false)}>{t('common.retry')}</button>
								</div>
							{:else if slots.length === 0}
								<div class="card flex flex-col items-start gap-3">
									<p class="text-slate-800">{t('booking.noSlots')}</p>
									{#if nextOpenDay(day)}
										<button type="button" class="btn-secondary" onclick={() => loadSlots(nextOpenDay(day)!, false)}>{t('booking.nextDay')}</button>
									{/if}
								</div>
							{:else}
								<div role="radiogroup" aria-label={t('booking.slotsLabel')} class="grid grid-cols-4 gap-2 sm:grid-cols-5">
									{#each slots as slot (slot)}
										<label class="choice">
											<input type="radio" name="time" class="peer sr-only" value={slot} bind:group={time} />
											<span class="choice-box py-3 text-center text-lg font-semibold tabular-nums" dir="ltr">{slot}</span>
										</label>
									{/each}
								</div>
								<p class="mt-3 text-sm text-slate-600">{t('booking.slotsHint')}</p>
							{/if}
						</section>
					{/if}

					<p class="rounded-xl bg-brand-50 px-4 py-3 text-brand-900">{t('booking.pendingInfo')}</p>
				{:else if view === 'details' && service}
					<h2 bind:this={detailsHeading} tabindex="-1" class="mb-4 text-2xl font-bold text-ink outline-none">{t('booking.detailsTitle')}</h2>
					<div class="card mb-5 flex items-center justify-between gap-3 bg-brand-50/60">
						<p class="font-semibold text-brand-900">{summary}{#if practitioner}<span class="font-normal"> · {fullName(practitioner)}</span>{/if}</p>
						<button type="button" class="shrink-0 text-sm font-semibold text-brand-700 underline-offset-4 hover:underline" onclick={() => (view = 'select')}
							>{t('booking.change')}</button
						>
					</div>
					<form class="flex flex-col gap-4" novalidate onsubmit={submit}>
						<div class="grid gap-4 sm:grid-cols-2">
							<TextField label={t('booking.firstName')} bind:value={firstName} error={fieldErrors.firstName} autocomplete="given-name" maxlength={120} />
							<TextField label={t('booking.lastName')} bind:value={lastName} error={fieldErrors.lastName} autocomplete="family-name" maxlength={120} />
						</div>
						<TextField
							label={t('booking.phone')}
							bind:value={phone}
							error={fieldErrors.phone}
							hint={t('booking.phoneHint')}
							type="tel"
							inputmode="tel"
							autocomplete="tel"
							dir="ltr"
							placeholder="20 123 456"
						/>
						<TextField
							label={t('booking.note')}
							bind:value={note}
							optional
							multiline
							rows={2}
							maxlength={500}
							placeholder={t('booking.notePlaceholder')}
						/>
						<label class="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 bg-white p-4">
							<input type="checkbox" class="mt-0.5 h-5 w-5 shrink-0 accent-brand-700" bind:checked={consent} />
							<span class="text-slate-800">{t('booking.consent')}</span>
						</label>
						<div class="honeypot" aria-hidden="true">
							<label>Website <input tabindex="-1" autocomplete="off" bind:value={website} /></label>
						</div>
						<p class="text-sm text-slate-600">
							{t('booking.privacy')}
							<a class="font-medium text-brand-700 underline" href={privacyUrl} target="_blank" rel="noopener">{t('booking.privacyLink')}</a>
						</p>
						{#if submitError}
							<div role="alert" class="flex flex-col items-start gap-3 rounded-xl bg-rose-50 px-4 py-3 text-rose-900 ring-1 ring-rose-200">
								<p class="font-medium">{submitError}</p>
								{#if offerCall}<a class="btn-secondary" href={telUrl(profile.phone)}>{t('booking.call')}</a>{/if}
							</div>
						{/if}
						<button type="submit" class="btn-primary min-h-13 text-lg" disabled={sending}>{sending ? t('booking.sending') : t('booking.submit')}</button>
					</form>
				{:else if view === 'done' && created}
					<h2 bind:this={doneHeading} tabindex="-1" class="mb-2 text-2xl font-bold text-ink outline-none">
						{created.status === 'confirmed' ? t('booking.confirmedTitle') : t('booking.requestedTitle')}
					</h2>
					<p class="mb-5 text-slate-700">{created.status === 'confirmed' ? t('booking.confirmedText') : t('booking.requestedText')}</p>
					<AppointmentEntry
						startsAt={created.startsAt}
						service={service ? serviceName(service) : created.serviceName}
						practitioner={created.practitionerName}
						practice={title}
						address={[profile.address, profile.city].filter(Boolean).join(', ')}
					/>
					<div class="card mt-5 flex flex-col gap-4">
						<CopyLink
							label={t('booking.manageLink')}
							url={manageUrl}
							whatsappText={t('booking.shareMessage', {
								practice: title,
								day: formatDate(created.startsAt),
								time: formatTime(created.startsAt),
								url: manageUrl
							})}
						/>
						<a class="btn-primary self-start" href="/rdv#{created.manageToken}">{t('booking.openManage')}</a>
					</div>
					<button type="button" class="mt-4 min-h-11 font-semibold text-brand-700 underline-offset-4 hover:underline" onclick={restart}
						>{t('booking.another')}</button
					>
				{/if}
			</main>

			<aside class="flex flex-col gap-4 lg:sticky lg:top-4">
				{#if description}<p class="card whitespace-pre-line text-slate-700">{description}</p>{/if}
				<section class="card flex flex-col gap-3" aria-labelledby="info-hours">
					<h2 id="info-hours" class="font-semibold text-ink">{t('booking.hours')}</h2>
					<ul aria-label={t('booking.hours')} class="flex flex-col gap-1.5 text-sm">
						{#each hoursLines as line (line.from)}
							<li class="flex justify-between gap-3">
								<span class="text-slate-600">{dayRange(line.from, line.to)}</span>
								<span class="text-end tabular-nums {line.windows.length ? 'text-ink' : 'text-slate-500'}" dir="ltr"
									>{line.windows.length ? line.windows.map(([a, b]) => `${a}–${b}`).join(' · ') : t('booking.closed')}</span
								>
							</li>
						{/each}
					</ul>
				</section>
				<section class="card flex flex-col gap-1 text-sm text-slate-700">
					<p><bdi>{profile.address}</bdi></p>
					<p><bdi>{[profile.postalCode, profile.city].filter(Boolean).join(' ')}</bdi></p>
					<p class="mt-1 font-semibold text-ink tabular-nums" dir="ltr">{formatPhone(profile.phone)}</p>
				</section>
			</aside>
		</div>

		{#if view === 'select' && summary}
			<div class="fixed inset-x-0 bottom-0 z-20 border-t border-slate-200 bg-white/95 backdrop-blur">
				<div class="mx-auto flex max-w-5xl items-center gap-3 px-4 py-3">
					<p class="line-clamp-2 min-w-0 flex-1 text-sm leading-snug font-semibold text-slate-800 sm:text-base" aria-live="polite">{summary}</p>
					<button type="button" class="btn-primary min-h-12 px-6 text-lg" onclick={toDetails}>{t('booking.continue')}</button>
				</div>
			</div>
		{/if}
	{/if}
</div>

<style>
	.ruled {
		background-color: #fff;
		background-image:
			linear-gradient(to right, transparent 1.75rem, rgb(225 29 72 / 0.28) 1.75rem, rgb(225 29 72 / 0.28) calc(1.75rem + 1px), transparent calc(1.75rem + 1px)),
			repeating-linear-gradient(to bottom, transparent 0 31px, rgb(15 118 110 / 0.12) 31px 32px),
			repeating-linear-gradient(to bottom, transparent 0 7px, rgb(15 118 110 / 0.05) 7px 8px);
		border-bottom: 1px solid #e2e8f0;
	}
	:global([dir='rtl']) .ruled {
		background-image:
			linear-gradient(to left, transparent 1.75rem, rgb(225 29 72 / 0.28) 1.75rem, rgb(225 29 72 / 0.28) calc(1.75rem + 1px), transparent calc(1.75rem + 1px)),
			repeating-linear-gradient(to bottom, transparent 0 31px, rgb(15 118 110 / 0.12) 31px 32px),
			repeating-linear-gradient(to bottom, transparent 0 7px, rgb(15 118 110 / 0.05) 7px 8px);
	}
	@media (min-width: 640px) {
		.ruled {
			border: 1px solid #e2e8f0;
		}
	}
	.pill {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		min-height: 2.75rem;
		padding: 0.4rem 1rem;
		border-radius: 999px;
		background: #fff;
		border: 1px solid #cbd5e1;
		font-weight: 600;
		color: #134e4a;
	}
	.pill:hover {
		background: #f0fdfa;
		border-color: #0f766e;
	}
	.pill:focus-visible {
		outline: 2px solid #0f766e;
		outline-offset: 2px;
	}
	.step {
		display: block;
		margin-bottom: 0.75rem;
		font-size: 1.125rem;
		font-weight: 700;
		color: #334155;
	}
	.choice {
		position: relative;
		display: block;
		cursor: pointer;
	}
	.choice-box {
		display: block;
		height: 100%;
		border-radius: 0.875rem;
		border: 1.5px solid #e2e8f0;
		background: #fff;
		padding: 0.75rem 1rem;
		transition:
			border-color 0.12s,
			background-color 0.12s;
	}
	.choice:hover .choice-box {
		border-color: #99f6e4;
	}
	:global(.peer:checked) + .choice-box {
		border-color: #0f766e;
		background: #f0fdfa;
		box-shadow: inset 0 0 0 1px #0f766e;
	}
	:global(.peer:focus-visible) + .choice-box {
		outline: 3px solid #134e4a;
		outline-offset: 2px;
	}
	:global(input[name='day']:checked) + .choice-box,
	:global(input[name='time']:checked) + .choice-box {
		background: #0f766e;
		border-color: #0f766e;
		color: #fff;
		box-shadow: none;
	}
	:global(input[name='day']:checked) + .choice-box span {
		color: #fff;
	}
	/* invisible to people (and screen readers via aria-hidden), still filled in by naive bots */
	.honeypot {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}
	@media (prefers-reduced-motion: reduce) {
		.choice-box {
			transition: none;
		}
	}
</style>
