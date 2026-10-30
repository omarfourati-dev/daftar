<script lang="ts">
	/**
	 * Admin: one practice – status & subscription, all practice data, hours, online booking, new invitation link,
	 * owner reset link, delete (stories A1, A3, I1). Saves only the fields that changed (PATCH).
	 */
	import { onMount, tick } from 'svelte';
	import { api, ApiError, apiErrorMessage, deps } from '#lib/api';
	import { hoursProblems, normalizeWeeklyHours, sortedWeeklyHours } from '#lib/hours';
	import { formatDate, formatDateTime, t } from '#lib/i18n.svelte';
	import { practiceUrl } from '#lib/links';
	import { readOnlineBooking, type OnlineBooking } from '#lib/online-booking';
	import { bookingProblems, profileBody, profileProblems, type Problems } from '#lib/practice-form';
	import type { SlugState } from '#lib/slug';
	import type { AdminPractice } from '#lib/types/admin';
	import { PLAN_CODES } from '#lib/types/billing';
	import type { PracticeProfileFields } from '#lib/types/practice';
	import ConfirmDialog from '../../../../../lib/components/ConfirmDialog.svelte';
	import CopyLink from '../../../../../lib/components/CopyLink.svelte';
	import HoursEditor from '../../../../../lib/components/HoursEditor.svelte';
	import LoadState from '../../../../../lib/components/LoadState.svelte';
	import SlugField from '../../../../../lib/components/admin/SlugField.svelte';
	import TextField from '../../../../../lib/components/form/TextField.svelte';
	import OnlineBookingFields from '../../../../../lib/components/practice/OnlineBookingFields.svelte';
	import PracticeFields from '../../../../../lib/components/practice/PracticeFields.svelte';
	import StatusBadge from '../../../../../lib/components/practice/StatusBadge.svelte';

	let { data }: { data: { id: number } } = $props();

	type Form = {
		profile: PracticeProfileFields;
		slug: string;
		status: string;
		planCode: string;
		paidUntil: string;
		adminNotes: string;
		weeklyHours: ReturnType<typeof normalizeWeeklyHours>;
		onlineBooking: OnlineBooking;
	};

	let original = $state<AdminPractice | null>(null);
	let form = $state<Form | null>(null);
	let loading = $state(true);
	let loadError = $state('');
	let problems = $state<Problems>({});
	let slugState = $state<SlugState>('unchanged');
	const refused = new Map<string, SlugState>();
	let saving = $state(false);
	let saveMessage = $state('');
	let saveError = $state('');

	let invitation = $state<{ url: string; expiresAt: string } | null>(null);
	let reset = $state<{ url: string; expiresAt: string } | null>(null);
	let linkError = $state('');
	let confirmDelete = $state(false);
	let deleteError = $state('');
	let deleting = $state(false);

	function toForm(p: AdminPractice): Form {
		const profile: PracticeProfileFields = {
			name: p.name ?? '',
			nameAr: p.nameAr ?? '',
			specialty: p.specialty ?? 'generaliste',
			contactName: p.contactName ?? '',
			phone: p.phone ?? '',
			whatsapp: p.whatsapp ?? '',
			email: p.email ?? '',
			address: p.address ?? '',
			postalCode: p.postalCode ?? '',
			city: p.city ?? '',
			governorate: p.governorate ?? '',
			mapsUrl: p.mapsUrl ?? '',
			descriptionFr: p.descriptionFr ?? '',
			descriptionAr: p.descriptionAr ?? '',
			taxId: p.taxId ?? ''
		};
		return {
			profile,
			slug: p.slug,
			status: p.status ?? 'pilot',
			planCode: p.planCode ?? 'pilot',
			paidUntil: p.paidUntil ?? '',
			adminNotes: p.adminNotes ?? '',
			weeklyHours: normalizeWeeklyHours(p.weeklyHours),
			onlineBooking: readOnlineBooking(p)
		};
	}

	async function load() {
		loading = true;
		loadError = '';
		try {
			original = await api<AdminPractice>(`/api/admin/practices/${data.id}`);
			form = toForm(original);
		} catch (err) {
			loadError = err instanceof ApiError && err.status === 404 ? t('admin.edit.notFound') : apiErrorMessage(err);
		} finally {
			loading = false;
		}
	}
	onMount(load);

	const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

	/** Only what differs from the loaded practice. */
	function changes(f: Form, p: AdminPractice): Record<string, unknown> {
		const before = toForm(p);
		const patch: Record<string, unknown> = {};
		const now = profileBody(f.profile);
		const was = profileBody(before.profile);
		for (const key of Object.keys(now) as (keyof PracticeProfileFields)[]) if (!same(now[key], was[key])) patch[key] = now[key];
		if (f.slug !== before.slug) patch.slug = f.slug;
		if (f.status !== before.status) patch.status = f.status;
		if (f.planCode !== before.planCode) patch.planCode = f.planCode;
		if (f.paidUntil !== before.paidUntil) patch.paidUntil = f.paidUntil || null;
		if (f.adminNotes.trim() !== before.adminNotes.trim()) patch.adminNotes = f.adminNotes.trim();
		if (!same(sortedWeeklyHours(f.weeklyHours), sortedWeeklyHours(before.weeklyHours))) patch.weeklyHours = sortedWeeklyHours(f.weeklyHours);
		if (!same(f.onlineBooking, before.onlineBooking)) patch.onlineBooking = { ...f.onlineBooking };
		return patch;
	}

	async function save(e: SubmitEvent) {
		e.preventDefault();
		if (!form || !original) return;
		saveMessage = '';
		saveError = '';
		const found: Problems = { ...profileProblems(form.profile, ['identity', 'address']), ...bookingProblems(form.onlineBooking) };
		if (Object.keys(hoursProblems(form.weeklyHours)).length) found.hours = { key: 'kit.hours.fixFirst' };
		if (form.slug !== original.slug && slugState !== 'available') found.slug = { key: 'admin.wizard.slugRequired' };
		problems = found;
		if (Object.keys(found).length) {
			saveError = t('admin.wizard.fixErrors');
			await tick();
			document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
			return;
		}
		const patch = changes(form, original);
		if (!Object.keys(patch).length) {
			saveMessage = t('admin.edit.nothingToSave');
			return;
		}
		saving = true;
		try {
			const updated = await api<AdminPractice>(`/api/admin/practices/${data.id}`, { method: 'PATCH', json: patch });
			original = { ...original, ...patch, ...updated } as AdminPractice;
			form = toForm(original);
			saveMessage = t('kit.saved');
		} catch (err) {
			const refusal: Record<string, SlugState> = { slug_taken: 'taken', slug_reserved: 'reserved', slug_invalid: 'invalid' };
			if (err instanceof ApiError && err.code && err.code in refusal) {
				refused.set(form.slug, refusal[err.code]);
				slugState = refusal[err.code];
			}
			saveError = apiErrorMessage(err);
		} finally {
			saving = false;
		}
	}

	async function newInvitation() {
		linkError = '';
		try {
			const link = await api<{ token: string; expiresAt: string }>(`/api/admin/practices/${data.id}/invitation`, { method: 'POST' });
			invitation = { url: practiceUrl(original!.slug, `/invitation#${link.token}`), expiresAt: link.expiresAt };
		} catch (err) {
			linkError = apiErrorMessage(err);
		}
	}

	async function newReset() {
		linkError = '';
		try {
			const link = await api<{ token: string; expiresAt: string }>(`/api/admin/practices/${data.id}/owner-reset-link`, { method: 'POST' });
			reset = { url: practiceUrl(original!.slug, `/reinitialiser#${link.token}`), expiresAt: link.expiresAt };
		} catch (err) {
			linkError = err instanceof ApiError && err.status === 404 ? t('admin.edit.noOwner') : apiErrorMessage(err);
		}
	}

	async function remove() {
		deleting = true;
		deleteError = '';
		try {
			await api(`/api/admin/practices/${data.id}`, { method: 'DELETE' });
			confirmDelete = false;
			void deps.goto('/app/admin');
		} catch (err) {
			deleteError = apiErrorMessage(err);
		} finally {
			deleting = false;
		}
	}

	const statusOptions = $derived(
		['pilot', 'trial', 'active', 'past_due', 'suspended', 'canceled'].map((s) => ({ value: s, label: t(`admin.status.${s}` as 'admin.status.pilot') }))
	);
	const planOptions = $derived(PLAN_CODES.map((p) => ({ value: p, label: t(`admin.plans.${p}`) })));
	const contactPhone = $derived(form ? form.profile.whatsapp?.trim() || form.profile.phone : '');
	const section = 'card flex flex-col gap-4';
	const sectionTitle = 'text-lg font-bold text-ink';
</script>

<svelte:head><title>{original?.name ?? t('admin.title')} · Daftar</title></svelte:head>

<a href="/app/admin" class="mb-2 inline-flex min-h-11 items-center text-sm font-medium text-brand-700 hover:underline">
	<span aria-hidden="true" class="me-1 rtl:rotate-180">‹</span>{t('admin.edit.back')}
</a>

<LoadState {loading} error={loadError} onretry={loadError === t('admin.edit.notFound') ? undefined : load} />

{#if form && original}
	<header class="mb-6 flex flex-col gap-1">
		<div class="flex flex-wrap items-center gap-3">
			<h1 class="text-2xl font-bold text-ink">{original.name}</h1>
			<StatusBadge status={original.status} />
		</div>
		<p class="text-sm text-slate-600">
			<span dir="ltr" class="font-mono">{practiceUrl(original.slug, '/')}</span>
			{#if original.createdAt}<span> · {t('admin.edit.createdOn', { date: formatDate(original.createdAt) })}</span>{/if}
		</p>
	</header>

	<form class="flex flex-col gap-6" novalidate onsubmit={save}>
		<section class={section} aria-labelledby="s-admin">
			<h2 id="s-admin" class={sectionTitle}>{t('admin.edit.sections.admin')}</h2>
			<div class="grid gap-4 sm:grid-cols-3">
				<TextField label={t('admin.wizard.statusLabel')} bind:value={form.status} options={statusOptions} />
				<TextField label={t('admin.wizard.planLabel')} bind:value={form.planCode} options={planOptions} />
				<TextField label={t('admin.wizard.paidUntil')} bind:value={form.paidUntil} type="date" optional hint={t('admin.wizard.paidUntilHint')} />
				<TextField
					class="sm:col-span-3"
					label={t('admin.wizard.adminNotes')}
					bind:value={form.adminNotes}
					hint={t('admin.wizard.adminNotesHint')}
					optional
					multiline
					maxlength={2000}
				/>
			</div>
		</section>

		<section class={section} aria-labelledby="s-identity">
			<h2 id="s-identity" class={sectionTitle}>{t('admin.edit.sections.identity')}</h2>
			<PracticeFields bind:value={form.profile} {problems} groups={['identity']} />
		</section>

		<section class={section} aria-labelledby="s-address">
			<h2 id="s-address" class={sectionTitle}>{t('admin.edit.sections.address')}</h2>
			<SlugField
				bind:value={form.slug}
				bind:state={slugState}
				original={original.slug}
				practiceId={data.id}
				{refused}
				warning={t('admin.edit.slugWarning')}
			/>
			<PracticeFields bind:value={form.profile} {problems} groups={['address', 'presentation']} />
		</section>

		<section class={section} aria-labelledby="s-hours">
			<h2 id="s-hours" class={sectionTitle}>{t('admin.edit.sections.hours')}</h2>
			<HoursEditor bind:value={form.weeklyHours} />
		</section>

		<section class={section} aria-labelledby="s-booking">
			<h2 id="s-booking" class={sectionTitle}>{t('admin.edit.sections.booking')}</h2>
			<OnlineBookingFields bind:value={form.onlineBooking} {problems} />
		</section>

		<div class="sticky bottom-14 z-10 -mx-4 flex flex-wrap items-center gap-3 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur md:bottom-0">
			<button type="submit" class="btn-primary" disabled={saving}>{saving ? t('kit.saving') : t('admin.edit.save')}</button>
			<p role="status" class="text-sm font-medium text-brand-800">{saveMessage}</p>
			{#if saveError}<p role="alert" class="text-sm font-medium text-red-700">{saveError}</p>{/if}
		</div>
	</form>

	<section class="{section} mt-6" aria-labelledby="s-links">
		<h2 id="s-links" class={sectionTitle}>{t('admin.edit.sections.links')}</h2>
		<CopyLink label={t('admin.wizard.bookingLink')} url={practiceUrl(original.slug, '/')} openable />
		<div class="grid gap-4 lg:grid-cols-2">
			<div class="flex flex-col gap-3 rounded-xl bg-slate-50 p-4">
				<h3 class="font-semibold text-ink">{t('admin.edit.invitationTitle')}</h3>
				<p class="text-sm text-slate-600">{t('admin.edit.invitationText')}</p>
				{#if invitation}
					<CopyLink
						label={t('admin.wizard.invitationLink')}
						url={invitation.url}
						whatsappText={t('admin.wizard.invitationMessage', { contact: original.contactName, practice: original.name, url: invitation.url })}
						whatsappTo={contactPhone}
						note={t('kit.validUntil', { date: formatDateTime(invitation.expiresAt) })}
					/>
				{:else}
					<button type="button" class="btn-secondary self-start" onclick={newInvitation}>{t('admin.edit.invitationCreate')}</button>
				{/if}
			</div>
			<div class="flex flex-col gap-3 rounded-xl bg-slate-50 p-4">
				<h3 class="font-semibold text-ink">{t('admin.edit.resetTitle')}</h3>
				<p class="text-sm text-slate-600">{t('admin.edit.resetText')}</p>
				{#if original.owner}
					<p class="text-sm font-medium text-ink">{t('admin.edit.owner', { name: original.owner.name, email: original.owner.email })}</p>
				{/if}
				{#if original.owner === null}
					<p class="text-sm font-medium text-amber-800">{t('admin.edit.noOwner')}</p>
				{:else if reset}
					<CopyLink
						label={t('admin.edit.resetLink')}
						url={reset.url}
						whatsappText={t('admin.edit.resetMessage', { url: reset.url })}
						whatsappTo={contactPhone}
						note={t('kit.validUntil', { date: formatDateTime(reset.expiresAt) })}
					/>
				{:else}
					<button type="button" class="btn-secondary self-start" onclick={newReset}>{t('admin.edit.resetCreate')}</button>
				{/if}
			</div>
		</div>
		{#if linkError}<p role="alert" class="text-sm font-medium text-red-700">{linkError}</p>{/if}
	</section>

	<section class="{section} mt-6 border-rose-200" aria-labelledby="s-danger">
		<h2 id="s-danger" class="{sectionTitle} text-rose-800">{t('admin.edit.sections.danger')}</h2>
		<p class="text-slate-700">{t('admin.edit.deleteText')}</p>
		<button type="button" class="btn self-start border border-rose-300 bg-white text-rose-800 hover:bg-rose-50" onclick={() => (confirmDelete = true)}
			>{t('admin.edit.deleteButton')}</button
		>
	</section>

	<ConfirmDialog
		open={confirmDelete}
		title={t('admin.edit.deleteTitle', { name: original.name })}
		message={t('admin.edit.deleteMessage')}
		confirmLabel={t('admin.edit.deleteConfirm')}
		typeToConfirm={original.name}
		danger
		busy={deleting}
		error={deleteError}
		onconfirm={remove}
		oncancel={() => (confirmDelete = false)}
	/>
{/if}
