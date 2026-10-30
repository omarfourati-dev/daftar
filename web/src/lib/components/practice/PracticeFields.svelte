<script lang="ts">
	/** Contact, address and presentation fields of a practice (admin wizard, admin edit page, owner settings). */
	import TextField from '../form/TextField.svelte';
	import { SPECIALTIES } from '../../catalog';
	import { i18n, t } from '../../i18n.svelte';
	import type { ProfileGroup, Problems } from '../../practice-form';
	import type { PracticeProfileFields } from '../../types/practice';

	const GOVERNORATES = [
		'ariana',
		'beja',
		'ben_arous',
		'bizerte',
		'gabes',
		'gafsa',
		'jendouba',
		'kairouan',
		'kasserine',
		'kebili',
		'kef',
		'mahdia',
		'manouba',
		'medenine',
		'monastir',
		'nabeul',
		'sfax',
		'sidi_bouzid',
		'siliana',
		'sousse',
		'tataouine',
		'tozeur',
		'tunis',
		'zaghouan'
	] as const;

	let {
		value = $bindable(),
		problems = {},
		groups
	}: { value: PracticeProfileFields; problems?: Problems; groups: readonly ProfileGroup[] } = $props();

	const err = (field: string) => (problems[field] ? t(problems[field].key, problems[field].params) : '');
	const specialties = $derived(
		[...SPECIALTIES]
			.map((s) => ({ value: s, label: t(`specialty.${s}`) }))
			.sort((a, b) => (a.value === 'autre' ? 1 : b.value === 'autre' ? -1 : a.label.localeCompare(b.label, i18n.locale)))
	);
	const governorates = $derived([
		{ value: '', label: t('practice.fields.choose') },
		...[...GOVERNORATES].map((g) => ({ value: g, label: t(`governorate.${g}`) })).sort((a, b) => a.label.localeCompare(b.label, i18n.locale))
	]);
</script>

{#if groups.includes('identity')}
	<div class="grid gap-4 sm:grid-cols-2">
		<TextField class="sm:col-span-2" label={t('practice.fields.specialty')} bind:value={value.specialty} options={specialties} />
		<TextField label={t('practice.fields.name')} bind:value={value.name} error={err('name')} hint={t('practice.fields.nameHint')} maxlength={120} />
		<TextField label={t('practice.fields.nameAr')} bind:value={value.nameAr} optional dir="rtl" maxlength={120} />
		<TextField
			label={t('practice.fields.contactName')}
			bind:value={value.contactName}
			error={err('contactName')}
			hint={t('practice.fields.contactHint')}
			autocomplete="name"
			maxlength={120}
		/>
		<TextField
			label={t('practice.fields.phone')}
			bind:value={value.phone}
			error={err('phone')}
			type="tel"
			inputmode="tel"
			dir="ltr"
			autocomplete="tel"
			placeholder="71 123 456"
		/>
		<TextField
			label={t('practice.fields.whatsapp')}
			bind:value={value.whatsapp}
			error={err('whatsapp')}
			hint={t('practice.fields.whatsappHint')}
			optional
			type="tel"
			inputmode="tel"
			dir="ltr"
			placeholder="20 123 456"
		/>
		<TextField
			label={t('practice.fields.email')}
			bind:value={value.email}
			error={err('email')}
			optional
			type="email"
			inputmode="email"
			dir="ltr"
			autocomplete="email"
		/>
		<TextField label={t('practice.fields.taxId')} bind:value={value.taxId} optional dir="ltr" maxlength={40} />
	</div>
{/if}

{#if groups.includes('address')}
	<div class="grid gap-4 sm:grid-cols-2">
		<TextField class="sm:col-span-2" label={t('practice.fields.address')} bind:value={value.address} error={err('address')} maxlength={200} />
		<TextField label={t('practice.fields.city')} bind:value={value.city} error={err('city')} maxlength={120} />
		<TextField label={t('practice.fields.postalCode')} bind:value={value.postalCode} optional inputmode="numeric" dir="ltr" maxlength={10} />
		<TextField label={t('practice.fields.governorate')} bind:value={value.governorate} error={err('governorate')} options={governorates} />
		<TextField
			label={t('practice.fields.mapsUrl')}
			bind:value={value.mapsUrl}
			error={err('mapsUrl')}
			hint={t('practice.fields.mapsHint')}
			optional
			type="url"
			inputmode="url"
			dir="ltr"
			placeholder="https://maps.app.goo.gl/…"
		/>
	</div>
{/if}

{#if groups.includes('presentation')}
	<div class="grid gap-4 sm:grid-cols-2">
		<TextField
			label={t('practice.fields.descriptionFr')}
			bind:value={value.descriptionFr}
			hint={t('practice.fields.descriptionHint')}
			optional
			multiline
			dir="ltr"
			maxlength={2000}
		/>
		<TextField label={t('practice.fields.descriptionAr')} bind:value={value.descriptionAr} optional multiline dir="rtl" maxlength={2000} />
	</div>
{/if}
