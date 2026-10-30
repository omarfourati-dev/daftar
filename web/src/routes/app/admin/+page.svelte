<script lang="ts">
	/** Administration – all practices with status, plan, paid-until, last activity and usage (story A1/I2). */
	import { onMount } from 'svelte';
	import { api, apiErrorMessage } from '#lib/api';
	import { formatDateTime, formatDay, t, todayTunis, translate } from '#lib/i18n.svelte';
	import type { AdminPracticeRow } from '#lib/types/admin';
	import AdminTabs from '../../../lib/components/admin/AdminTabs.svelte';
	import LoadState from '../../../lib/components/LoadState.svelte';
	import StatusBadge from '../../../lib/components/practice/StatusBadge.svelte';

	const STATUSES = ['pilot', 'trial', 'active', 'past_due', 'suspended', 'canceled'] as const;

	let rows = $state<AdminPracticeRow[]>([]);
	let loading = $state(true);
	let error = $state('');
	let query = $state('');
	let status = $state('');
	let showDemos = $state(false);

	async function load() {
		loading = true;
		error = '';
		try {
			rows = await api<AdminPracticeRow[]>(showDemos ? '/api/admin/practices?demo=true' : '/api/admin/practices');
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			loading = false;
		}
	}
	onMount(load);

	const fold = (s: string) =>
		s
			.normalize('NFKD')
			.replace(/[̀-ͯ]/g, '')
			.toLowerCase();
	const visible = $derived(
		rows.filter((r) => {
			if (status && r.status !== status) return false;
			const q = fold(query.trim());
			return !q || fold(`${r.name} ${r.city} ${r.slug ?? ''}`).includes(q);
		})
	);
	const today = todayTunis();
	const overdue = (r: AdminPracticeRow) => !!r.paidUntil && r.paidUntil < today && r.status !== 'pilot';
</script>

<svelte:head><title>{t('admin.title')} · Daftar</title></svelte:head>

<AdminTabs current="practices" />

<div class="mb-4 flex flex-col gap-3 lg:flex-row lg:items-end">
	<label class="label flex-1">
		{t('admin.list.search')}
		<input class="input" type="search" placeholder={t('admin.list.searchPlaceholder')} bind:value={query} />
	</label>
	<label class="label lg:w-56">
		{t('admin.list.statusFilter')}
		<select class="input" bind:value={status}>
			<option value="">{t('admin.list.allStatuses')}</option>
			{#each STATUSES as s (s)}<option value={s}>{t(`admin.status.${s}`)}</option>{/each}
		</select>
	</label>
	<label class="flex min-h-11 cursor-pointer items-center gap-2 text-sm font-medium text-slate-700">
		<input type="checkbox" class="h-5 w-5 accent-brand-700" bind:checked={showDemos} onchange={load} />
		{t('admin.list.showDemos')}
	</label>
	<a href="/app/admin/cabinets/nouveau" class="btn-primary"><span aria-hidden="true">+</span> {t('admin.list.newPractice')}</a>
</div>

<LoadState {loading} {error} onretry={load} />

{#if !loading && !error}
	{#if rows.length === 0}
		<div class="card flex flex-col items-start gap-3 py-8">
			<p class="text-slate-700">{t('admin.list.empty')}</p>
		</div>
	{:else}
		<p class="mb-2 text-sm text-slate-600" aria-live="polite">{t('admin.list.count', { n: visible.length })}</p>
		{#if visible.length === 0}
			<p class="card text-slate-700">{t('admin.list.noMatch')}</p>
		{:else}
			<ul class="flex flex-col gap-2">
				{#each visible as row (row.id)}
					<li
						class="card grid gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_auto_minmax(0,1fr)] lg:items-center"
					>
						<div class="min-w-0">
							<a href="/app/admin/cabinets/{row.id}" class="text-lg font-semibold text-brand-800 hover:underline">{row.name}</a>
							<p class="truncate text-sm text-slate-600">
								{#if row.isDemo}<span class="me-1 rounded bg-accent-400 px-1.5 py-0.5 text-xs font-semibold text-ink">{t('admin.list.demo')}</span>{/if}
								{#if row.slug}<span dir="ltr" class="font-mono">{row.slug}</span>{/if}
								{#if row.specialty}<span> · {translate(`specialty.${row.specialty}`) ?? row.specialty}</span>{/if}
								{#if row.city}<span> · {row.city}</span>{/if}
							</p>
						</div>
						<div class="flex flex-wrap items-center gap-2">
							<StatusBadge status={row.status} />
							{#if row.planCode}<span class="text-sm text-slate-700">{translate(`admin.plans.${row.planCode}`) ?? row.planCode}</span>{/if}
						</div>
						<dl class="grid grid-cols-[auto_1fr] gap-x-3 text-sm whitespace-nowrap">
							<dt class="text-slate-500">{t('admin.list.paidUntil')}</dt>
							<dd class={overdue(row) ? 'font-semibold text-rose-700' : ''}>
								<span>{row.paidUntil ? formatDay(row.paidUntil) : t('kit.none')}</span>
								{#if overdue(row)}<span class="sr-only">({t('admin.list.overdue')})</span>{/if}
							</dd>
							<dt class="text-slate-500">{t('admin.list.activity')}</dt>
							<dd>{row.lastActivityAt ? formatDateTime(row.lastActivityAt) : t('admin.list.never')}</dd>
						</dl>
						<p class="text-sm text-slate-600">
							<span class="sr-only">{t('admin.list.usage')} :</span>
							<span>{t('admin.list.usageLine', { users: row.users, patients: row.patients, appointments: row.appointments })}</span>
						</p>
					</li>
				{/each}
			</ul>
		{/if}
	{/if}
{/if}
