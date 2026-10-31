<script lang="ts">
	/**
	 * /app/reglages – the owner edits the practice (all fields except the admin ones: section 11.2), the agenda grid
	 * and the reminder messages. Other roles land on their account here.
	 */
	import { onMount, tick } from 'svelte';
	import { api, apiErrorMessage, deps } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { t } from '#lib/i18n.svelte';
	import { practiceUrl } from '#lib/links';
	import { profileBody, profileProblems, type Problems } from '#lib/practice-form';
	import type { Me } from '#lib/types';
	import type { Practice, PracticeProfileFields } from '#lib/types/practice';
	import LoadState from '../../../lib/components/LoadState.svelte';
	import TextField from '../../../lib/components/form/TextField.svelte';
	import PracticeFields from '../../../lib/components/practice/PracticeFields.svelte';
	import AccountSettings from '../../../lib/components/reglages/AccountSettings.svelte';

	const isOwner = auth.user?.role === 'owner';
	const SLOTS = [5, 10, 15, 20, 30];
	const COLORS = ['#0f766e', '#0369a1', '#4338ca', '#7c3aed', '#be185d', '#b45309', '#15803d', '#334155'];

	type Extra = { brandColor: string; slotMinutes: number; defaultDurationMin: number; reminderTemplateFr: string; reminderTemplateAr: string };
	let loaded = $state<Practice | null>(null);
	let profile = $state<PracticeProfileFields | null>(null);
	let extra = $state<Extra>({ brandColor: '#0f766e', slotMinutes: 15, defaultDurationMin: 30, reminderTemplateFr: '', reminderTemplateAr: '' });
	let loading = $state(isOwner);
	let error = $state('');
	let problems = $state<Problems>({});
	let notice = $state('');
	let saveError = $state('');
	let busy = $state(false);

	function fill(p: Practice) {
		loaded = p;
		profile = pick(p);
		extra = {
			brandColor: p.brandColor ?? '#0f766e',
			slotMinutes: p.slotMinutes ?? 15,
			defaultDurationMin: p.defaultDurationMin ?? 30,
			reminderTemplateFr: p.reminderTemplateFr ?? '',
			reminderTemplateAr: p.reminderTemplateAr ?? ''
		};
	}

	async function load() {
		loading = true;
		error = '';
		try {
			fill(await api<Practice>('/api/practice'));
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			loading = false;
		}
	}
	/** Old links of the first steps (`/app/reglages#horaires` …) open the section itself, without a history entry. */
	const SECTIONS = ['horaires', 'actes', 'praticiens', 'equipe', 'reservation', 'ecran', 'donnees', 'compte'];
	onMount(() => {
		const section = location.hash.slice(1);
		if (SECTIONS.includes(section)) {
			void deps.goto(`/app/reglages/${section}`, { replaceState: true });
			return;
		}
		if (isOwner) void load();
	});

	async function save(e: SubmitEvent) {
		e.preventDefault();
		if (!profile || !loaded) return;
		notice = '';
		saveError = '';
		problems = profileProblems(profile, ['identity', 'address']);
		if (!Number.isInteger(extra.defaultDurationMin) || extra.defaultDurationMin < 5 || extra.defaultDurationMin > 480) {
			problems.defaultDurationMin = { key: 'practice.services.durationInvalid' };
		}
		if (Object.keys(problems).length) {
			saveError = t('admin.wizard.fixErrors');
			await tick();
			document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
			return;
		}
		const before = profileBody(pick(loaded)) as unknown as Record<string, unknown>;
		const now = profileBody(profile) as unknown as Record<string, unknown>;
		const patch: Record<string, unknown> = {};
		for (const [key, value] of Object.entries(now)) if (JSON.stringify(value) !== JSON.stringify(before[key])) patch[key] = value;
		for (const [key, value] of Object.entries(extra)) {
			const was = (loaded as Record<string, unknown>)[key];
			const clean = typeof value === 'string' ? value.trim() : value;
			if (clean !== (typeof was === 'string' ? was.trim() : was)) patch[key] = clean;
		}
		if (!Object.keys(patch).length) {
			notice = t('admin.edit.nothingToSave');
			return;
		}
		busy = true;
		try {
			fill({ ...loaded, ...patch, ...(await api<Practice>('/api/practice', { method: 'PATCH', json: patch })) });
			notice = t('kit.saved');
			void api<Me>('/api/auth/me')
				.then((me) => auth.setUser(me))
				.catch(() => undefined);
		} catch (err) {
			saveError = apiErrorMessage(err);
		} finally {
			busy = false;
		}
	}

	/** The profile fields of the loaded practice (for the comparison). */
	function pick(p: Practice): PracticeProfileFields {
		return {
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
	}

	const card = 'card flex flex-col gap-4';
	const heading = 'font-semibold text-ink';
</script>

{#if !isOwner}
	<AccountSettings />
{:else}
	<h2 class="mb-4 text-xl font-bold text-ink">{t('reglages.cabinet.title')}</h2>
	<LoadState {loading} {error} onretry={load} />
	{#if profile && loaded}
		<form class="flex flex-col gap-6" novalidate onsubmit={save}>
			<section class={card} aria-labelledby="c-contact">
				<h3 id="c-contact" class={heading}>{t('reglages.cabinet.contact')}</h3>
				<div class="flex flex-col gap-1 text-sm">
					<span class="text-slate-600">{t('reglages.cabinet.slug')}</span>
					<span dir="ltr" class="self-start font-mono font-semibold text-ink">{practiceUrl(loaded.slug, '/')}</span>
					<span class="text-slate-500">{t('reglages.cabinet.slugHint')}</span>
				</div>
				<PracticeFields bind:value={profile} {problems} groups={['identity']} />
			</section>

			<section class={card} aria-labelledby="c-address">
				<h3 id="c-address" class={heading}>{t('reglages.cabinet.address')}</h3>
				<PracticeFields bind:value={profile} {problems} groups={['address']} />
			</section>

			<section class={card} aria-labelledby="c-presentation">
				<h3 id="c-presentation" class={heading}>{t('reglages.cabinet.presentation')}</h3>
				<PracticeFields bind:value={profile} {problems} groups={['presentation']} />
				<fieldset class="flex flex-col gap-2">
					<legend class="text-sm font-medium text-slate-700">{t('practice.fields.brandColor')}</legend>
					<div class="flex flex-wrap items-center gap-2">
						{#each COLORS as color (color)}
							<label class="relative cursor-pointer">
								<input type="radio" name="brand" value={color} bind:group={extra.brandColor} class="peer sr-only" aria-label={color} />
								<span
									class="block h-10 w-10 rounded-xl ring-offset-2 peer-checked:ring-2 peer-checked:ring-ink peer-focus-visible:outline-2 peer-focus-visible:outline-offset-4 peer-focus-visible:outline-brand-700"
									style="background:{color}"
								></span>
							</label>
						{/each}
						<span class="ms-2 inline-flex h-10 w-10 items-center justify-center rounded-xl text-sm font-bold text-white" style="background:{extra.brandColor}" aria-hidden="true"
							>{(profile.name.match(/[A-Za-z]/g) ?? ['D']).slice(0, 1).join('').toUpperCase()}</span
						>
					</div>
					<p class="text-sm text-slate-600">{t('practice.fields.brandColorHint')}</p>
				</fieldset>
			</section>

			<section class={card} aria-labelledby="c-agenda">
				<h3 id="c-agenda" class={heading}>{t('reglages.cabinet.agenda')}</h3>
				<div class="grid gap-4 sm:grid-cols-2">
					<label class="label">
						{t('practice.fields.slotMinutes')}
						<select class="input" bind:value={extra.slotMinutes}>
							{#each SLOTS as n (n)}<option value={n}>{t('reglages.cabinet.minutes', { n })}</option>{/each}
						</select>
					</label>
					<div class="flex flex-col gap-1">
						<label for="c-duration" class="text-sm font-medium text-slate-700">{t('practice.fields.defaultDuration')}</label>
						<input
							id="c-duration"
							class="input w-32"
							type="number"
							min="5"
							max="480"
							step="5"
							dir="ltr"
							bind:value={extra.defaultDurationMin}
							aria-invalid={problems.defaultDurationMin ? 'true' : undefined}
							aria-describedby={problems.defaultDurationMin ? 'c-duration-error' : undefined}
						/>
						{#if problems.defaultDurationMin}<p id="c-duration-error" class="text-sm font-medium text-red-700">
								{t('practice.services.durationInvalid')}
							</p>{/if}
					</div>
				</div>
			</section>

			<section class={card} aria-labelledby="c-reminders">
				<h3 id="c-reminders" class={heading}>{t('reglages.cabinet.reminders')}</h3>
				<p class="text-sm text-slate-600" dir="ltr">{t('practice.fields.reminderHint')}</p>
				<div class="grid gap-4 lg:grid-cols-2">
					<TextField label={t('practice.fields.reminderFr')} bind:value={extra.reminderTemplateFr} multiline rows={4} dir="ltr" maxlength={1000} />
					<TextField label={t('practice.fields.reminderAr')} bind:value={extra.reminderTemplateAr} multiline rows={4} dir="rtl" maxlength={1000} />
				</div>
			</section>

			<div class="sticky bottom-14 z-10 -mx-4 flex flex-wrap items-center gap-3 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur md:bottom-0">
				<button type="submit" class="btn-primary" disabled={busy}>{busy ? t('kit.saving') : t('reglages.cabinet.save')}</button>
				<p role="status" class="text-sm font-medium text-brand-800">{notice}</p>
				{#if saveError}<p role="alert" class="text-sm font-medium text-red-700">{saveError}</p>{/if}
			</div>
		</form>
	{/if}
{/if}
