<script lang="ts">
	/**
	 * Admin wizard "Nouveau cabinet" (sections 11.2/12, story A1): 1 Cabinet & contact · 2 Adresse & sous-domaine
	 * (checked live) · 3 Horaires · 4 Praticiens · 5 Actes & tarifs (catalog of the specialty) · 6 Réservation en ligne
	 * · Récapitulatif → invitation link for the owner + booking link.
	 */
	import { onMount, tick } from 'svelte';
	import { api, ApiError, apiErrorMessage } from '#lib/api';
	import { catalogFor } from '#lib/catalog';
	import { defaultWeeklyHours, hoursProblems, sortedWeeklyHours, WEEKDAYS } from '#lib/hours';
	import { t, todayTunis, translate } from '#lib/i18n.svelte';
	import { practiceUrl } from '#lib/links';
	import { DEFAULT_ONLINE_BOOKING, type OnlineBooking } from '#lib/online-booking';
	import {
		bookingProblems,
		emptyProfile,
		practitionerFromContact,
		practitionerProblems,
		profileBody,
		profileProblems,
		serviceDrafts,
		serviceProblems,
		servicesBody,
		type PractitionerDraft,
		type Problems,
		type ServiceDraft
	} from '#lib/practice-form';
	import { suggestSlug, type SlugState } from '#lib/slug';
	import type { Specialty } from '#lib/types';
	import { PLAN_CODES } from '#lib/types/billing';
	import type { AdminPracticeCreated, AdminPracticeInput } from '#lib/types/admin';
	import CopyLink from '../../../../../lib/components/CopyLink.svelte';
	import SlugField from '../../../../../lib/components/admin/SlugField.svelte';
	import HoursEditor from '../../../../../lib/components/HoursEditor.svelte';
	import TextField from '../../../../../lib/components/form/TextField.svelte';
	import OnlineBookingFields from '../../../../../lib/components/practice/OnlineBookingFields.svelte';
	import PracticeFields from '../../../../../lib/components/practice/PracticeFields.svelte';
	import PractitionersEditor from '../../../../../lib/components/practice/PractitionersEditor.svelte';
	import ServicesEditor from '../../../../../lib/components/practice/ServicesEditor.svelte';

	const STEPS = ['identity', 'address', 'hours', 'practitioners', 'services', 'booking', 'summary'] as const;
	type Step = (typeof STEPS)[number];
	const PREFILL_KEY = 'daftar.wizardPrefill';

	let step = $state(0);
	let reached = $state(0);
	const current = $derived<Step>(STEPS[step]);

	let profile = $state(emptyProfile('generaliste'));
	let slug = $state('');
	let slugEdited = false;
	/** sub-domains the server refused on create (taken in the meantime) – not checked again */
	const refused = new Map<string, SlugState>();
	let slugState = $state<SlugState>('idle');
	let hours = $state(defaultWeeklyHours());
	let practitioners = $state<PractitionerDraft[]>([]);
	let services = $state<ServiceDraft[]>([]);
	let servicesFor = $state<string | null>(null);
	let servicesEdited = $state(false);
	let booking = $state<OnlineBooking>({ ...DEFAULT_ONLINE_BOOKING });
	let adminFields = $state({ status: 'pilot', planCode: 'pilot', paidUntil: '', adminNotes: '' });

	let problems = $state<Problems>({});
	let formError = $state('');
	let busy = $state(false);
	let created = $state<AdminPracticeCreated | null>(null);
	let prefilledFrom = $state('');
	let heading = $state<HTMLHeadingElement>();

	onMount(() => {
		try {
			const raw = sessionStorage.getItem(PREFILL_KEY);
			sessionStorage.removeItem(PREFILL_KEY);
			if (!raw) return;
			const pilot = JSON.parse(raw) as { name?: string; practice?: string; city?: string; phone?: string; email?: string | null };
			profile.name = pilot.practice ?? '';
			profile.contactName = pilot.name ?? '';
			profile.phone = pilot.phone ?? '';
			profile.email = pilot.email ?? '';
			profile.city = pilot.city ?? '';
			prefilledFrom = pilot.name ?? '';
		} catch {
			/* no pre-fill */
		}
	});

	// the sub-domain follows the name until the admin types one
	$effect(() => {
		const name = profile.name;
		if (!slugEdited) slug = name.trim() ? suggestSlug(name) : '';
	});

	function prepare(target: Step) {
		if (target === 'practitioners' && practitioners.length === 0) {
			practitioners = [practitionerFromContact(profile.contactName, String(profile.specialty))];
		}
		if (target === 'services' && servicesFor !== profile.specialty && !servicesEdited) {
			services = serviceDrafts(catalogFor(profile.specialty as Specialty));
			servicesFor = String(profile.specialty);
		}
	}

	function problemsOf(target: Step): Problems {
		switch (target) {
			case 'identity':
				return profileProblems(profile, ['identity']);
			case 'address': {
				const found = profileProblems(profile, ['address']);
				if (slugState !== 'available') found.slug = { key: 'admin.wizard.slugRequired' };
				return found;
			}
			case 'hours':
				return Object.keys(hoursProblems(hours)).length ? { hours: { key: 'kit.hours.fixFirst' } } : {};
			case 'practitioners':
				return practitionerProblems(practitioners);
			case 'services':
				return serviceProblems(services);
			case 'booking':
				return bookingProblems(booking);
			default:
				return {};
		}
	}

	async function show(index: number) {
		prepare(STEPS[index]);
		step = index;
		reached = Math.max(reached, index);
		problems = {};
		formError = '';
		await tick();
		heading?.focus();
		document.querySelector('[aria-current="step"]')?.scrollIntoView?.({ block: 'nearest', inline: 'center' });
	}

	async function next() {
		const found = problemsOf(current);
		if (Object.keys(found).length) {
			problems = found;
			formError = t('admin.wizard.fixErrors');
			await tick();
			document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
			return;
		}
		await show(step + 1);
	}

	function body(): AdminPracticeInput {
		const paidUntil = adminFields.paidUntil || null;
		return {
			...profileBody(profile),
			slug,
			status: adminFields.status,
			planCode: adminFields.planCode,
			paidUntil,
			pilotUntil: paidUntil,
			adminNotes: adminFields.adminNotes.trim(),
			weeklyHours: sortedWeeklyHours(hours),
			practitioners: practitioners.map((p) => ({ title: p.title.trim(), name: p.name.trim(), specialty: p.specialty || null })),
			services: servicesBody(services),
			onlineBooking: { ...booking }
		};
	}

	async function create() {
		for (const [index, key] of STEPS.entries()) {
			const found = problemsOf(key);
			if (Object.keys(found).length) {
				await show(index);
				problems = found;
				formError = t('admin.wizard.fixErrors');
				return;
			}
		}
		busy = true;
		formError = '';
		try {
			created = await api<AdminPracticeCreated>('/api/admin/practices', { method: 'POST', json: body() });
			await tick();
			heading?.focus();
		} catch (err) {
			const refusal: Record<string, SlugState> = { slug_taken: 'taken', slug_reserved: 'reserved', slug_invalid: 'invalid' };
			if (err instanceof ApiError && (err.status === 409 || (err.code && err.code in refusal))) {
				refused.set(slug, refusal[err.code ?? ''] ?? 'taken');
				await show(STEPS.indexOf('address'));
			} else {
				formError = apiErrorMessage(err);
			}
		} finally {
			busy = false;
		}
	}

	function restart() {
		location.assign('/app/admin/cabinets/nouveau');
	}

	const openDays = $derived(WEEKDAYS.filter((d) => hours[d].length > 0).length);
	const onlineServices = $derived(services.filter((s) => s.onlineBookable).length);
	const contactPhone = $derived(profile.whatsapp?.trim() || profile.phone);
	const invitationUrl = $derived(created ? practiceUrl(created.practice.slug, `/invitation#${created.invitation.token}`) : '');
	const bookingUrl = $derived(created ? practiceUrl(created.practice.slug, '/') : '');
	const statusOptions = $derived(['pilot', 'trial', 'active'].map((s) => ({ value: s, label: t(`admin.status.${s}` as 'admin.status.pilot') })));
	const planOptions = $derived(PLAN_CODES.map((p) => ({ value: p, label: t(`admin.plans.${p}`) })));
	const minDate = todayTunis();
	const summary = $derived<{ key: Step; text: string }[]>([
		{
			key: 'identity',
			text: [profile.name, translate(`specialty.${profile.specialty}`) ?? '', profile.contactName, profile.phone].filter(Boolean).join(' · ')
		},
		{ key: 'address', text: `${slug ? practiceUrl(slug, '/') : ''} · ${[profile.address, profile.city].filter(Boolean).join(', ')}` },
		{ key: 'hours', text: t('admin.wizard.openDays', { n: openDays }) },
		{ key: 'practitioners', text: t('admin.wizard.practitionersCount', { n: practitioners.length }) },
		{ key: 'services', text: t('admin.wizard.servicesCount', { n: services.length, online: onlineServices }) },
		{
			key: 'booking',
			text: booking.enabled
				? t('admin.wizard.bookingOn', { horizon: booking.horizonDays, notice: booking.minNoticeHours })
				: t('admin.wizard.bookingOff')
		}
	]);
</script>

<svelte:head><title>{t('admin.wizard.title')} · Daftar</title></svelte:head>

<a href="/app/admin" class="mb-2 inline-flex min-h-11 items-center text-sm font-medium text-brand-700 hover:underline">
	<span aria-hidden="true" class="me-1 rtl:rotate-180">‹</span>{t('admin.wizard.back')}
</a>
<h1 class="mb-6 text-2xl font-bold text-ink">{t('admin.wizard.title')}</h1>

{#if created}
	<section class="flex max-w-3xl flex-col gap-6">
		<div class="card flex flex-col gap-2 border-brand-200 bg-brand-50">
			<h2 bind:this={heading} tabindex="-1" class="text-xl font-bold text-brand-900 outline-none">
				{t('admin.wizard.createdTitle', { name: created.practice.name })}
			</h2>
			<p class="text-brand-900">{t('admin.wizard.createdIntro')}</p>
		</div>
		<div class="card flex flex-col gap-4">
			<CopyLink
				label={t('admin.wizard.invitationLink')}
				url={invitationUrl}
				whatsappText={t('admin.wizard.invitationMessage', { contact: profile.contactName.trim(), practice: created.practice.name, url: invitationUrl })}
				whatsappTo={contactPhone}
				note={t('kit.linkOnce')}
			/>
			<CopyLink
				label={t('admin.wizard.bookingLink')}
				url={bookingUrl}
				openable
				note={booking.enabled ? undefined : t('admin.wizard.bookingLinkOff')}
			/>
		</div>
		<div class="flex flex-wrap gap-3">
			<a href="/app/admin/cabinets/{created.practice.id}" class="btn-primary">{t('admin.wizard.openPractice')}</a>
			<button type="button" class="btn-secondary" onclick={restart}>{t('admin.wizard.another')}</button>
		</div>
	</section>
{:else}
	<div class="grid gap-6 lg:grid-cols-[15rem_minmax(0,1fr)]">
		<nav aria-label={t('admin.wizard.stepsLabel')} class="-mx-4 overflow-x-auto px-4 lg:mx-0 lg:px-0">
			<p class="mb-2 text-sm font-medium text-slate-600">{t('admin.wizard.progress', { n: step + 1, total: STEPS.length })}</p>
			<ol aria-label={t('admin.wizard.stepsLabel')} class="flex min-w-max gap-2 lg:min-w-0 lg:flex-col lg:gap-1">
				{#each STEPS as key, index (key)}
					<li>
						<button
							type="button"
							disabled={index > reached}
							aria-current={index === step ? 'step' : undefined}
							onclick={() => show(index)}
							class="flex min-h-11 w-full items-center gap-2 rounded-lg px-3 py-2 text-start text-sm font-medium disabled:cursor-default disabled:opacity-60 {index ===
							step
								? 'bg-brand-700 text-white'
								: 'bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-brand-50 lg:bg-transparent lg:ring-0'}"
						>
							<span
								class="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold {index === step
									? 'bg-white text-brand-800'
									: index < reached || (index <= reached && index !== step)
										? 'bg-brand-100 text-brand-800'
										: 'bg-slate-100 text-slate-600'}">{index + 1}</span
							>
							<span>{t(`admin.wizard.steps.${key}`)}</span>
						</button>
					</li>
				{/each}
			</ol>
		</nav>

		<form
			class="flex min-w-0 flex-col gap-5"
			novalidate
			onsubmit={(e) => {
				e.preventDefault();
				if (current === 'summary') void create();
				else void next();
			}}
		>
			<div class="flex flex-col gap-1">
				<h2 bind:this={heading} tabindex="-1" class="text-xl font-bold text-ink outline-none">{t(`admin.wizard.steps.${current}`)}</h2>
				{#if prefilledFrom && current === 'identity'}
					<p class="text-sm text-brand-800">{t('admin.wizard.fromPilot', { name: prefilledFrom })}</p>
				{/if}
			</div>

			{#if current === 'identity'}
				<PracticeFields bind:value={profile} {problems} groups={['identity']} />
			{:else if current === 'address'}
				<SlugField bind:value={slug} bind:state={slugState} {refused} onedit={() => (slugEdited = true)} />
				<PracticeFields bind:value={profile} {problems} groups={['address']} />
			{:else if current === 'hours'}
				<HoursEditor bind:value={hours} />
			{:else if current === 'practitioners'}
				<PractitionersEditor bind:value={practitioners} specialty={String(profile.specialty)} {problems} />
			{:else if current === 'services'}
				<p class="text-sm text-slate-600">
					{t('practice.services.hint', { specialty: translate(`specialty.${profile.specialty}`) ?? String(profile.specialty) })}
				</p>
				{#if servicesEdited && servicesFor !== profile.specialty}
					<button
						type="button"
						class="btn-secondary self-start"
						onclick={() => {
							services = serviceDrafts(catalogFor(profile.specialty as Specialty));
							servicesFor = String(profile.specialty);
							servicesEdited = false;
						}}>{t('practice.services.reload', { specialty: translate(`specialty.${profile.specialty}`) ?? '' })}</button
					>
				{/if}
				<ServicesEditor bind:value={services} {problems} onedit={() => (servicesEdited = true)} />
			{:else if current === 'booking'}
				<OnlineBookingFields bind:value={booking} {problems} />
				<PracticeFields bind:value={profile} {problems} groups={['presentation']} />
			{:else}
				<p class="text-slate-700">{t('admin.wizard.summaryIntro')}</p>
				<dl class="card divide-y divide-slate-100 p-0">
					{#each summary as item, index (item.key)}
						<div class="flex flex-col gap-1 p-4 sm:flex-row sm:items-center sm:gap-4">
							<dt class="w-56 shrink-0 font-semibold text-ink">{t(`admin.wizard.steps.${item.key}`)}</dt>
							<dd class="min-w-0 flex-1 break-words text-slate-700">{item.text}</dd>
							<dd>
								<button type="button" class="text-sm font-semibold text-brand-700 hover:underline" onclick={() => show(index)}
									>{t('admin.wizard.change')}<span class="sr-only"> – {t(`admin.wizard.steps.${item.key}`)}</span></button
								>
							</dd>
						</div>
					{/each}
				</dl>
				<fieldset class="card grid gap-4 sm:grid-cols-3">
					<legend class="px-1 font-semibold text-ink">{t('admin.wizard.adminSection')}</legend>
					<TextField label={t('admin.wizard.statusLabel')} bind:value={adminFields.status} options={statusOptions} />
					<TextField label={t('admin.wizard.planLabel')} bind:value={adminFields.planCode} options={planOptions} />
					<TextField
						label={t('admin.wizard.paidUntil')}
						bind:value={adminFields.paidUntil}
						type="date"
						min={minDate}
						optional
						hint={t('admin.wizard.paidUntilHint')}
					/>
					<TextField
						class="sm:col-span-3"
						label={t('admin.wizard.adminNotes')}
						bind:value={adminFields.adminNotes}
						hint={t('admin.wizard.adminNotesHint')}
						optional
						multiline
						maxlength={2000}
					/>
				</fieldset>
			{/if}

			{#if formError}<p role="alert" class="rounded-lg bg-rose-50 px-4 py-3 text-sm font-medium text-rose-900">{formError}</p>{/if}
			{#if problems.hours}<p class="text-sm font-medium text-red-700">{t('kit.hours.fixFirst')}</p>{/if}

			<div class="sticky bottom-14 z-10 -mx-4 flex gap-3 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur md:bottom-0">
				{#if step > 0}
					<button type="button" class="btn-secondary" onclick={() => show(step - 1)}>{t('admin.wizard.previous')}</button>
				{/if}
				<span class="flex-1"></span>
				{#if current === 'summary'}
					<button type="submit" class="btn-primary" disabled={busy}>{busy ? t('admin.wizard.creating') : t('admin.wizard.create')}</button>
				{:else}
					<button type="submit" class="btn-primary">{t('admin.wizard.next')}</button>
				{/if}
			</div>
		</form>
	</div>
{/if}
