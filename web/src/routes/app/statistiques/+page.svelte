<script lang="ts">
	/**
	 * /app/statistiques – the month for the owner (story H1): appointments, patients who came, no-show rate, cancelled,
	 * online share, cash received, new patients – each compared with the previous month – plus a small bar chart and the
	 * most frequent services, and the material of the month (spending, cost per act – spec stock-hygiène 4.3). Plain
	 * SVG/CSS, no chart library.
	 */
	import { api } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { clock } from '#lib/clock';
	import { money } from '#lib/agenda/format';
	import { i18n, t, todayTunis } from '#lib/i18n.svelte';
	import Icon from '../../../lib/components/daily/Icon.svelte';
	import StockStats from '../../../lib/components/stock/StockStats.svelte';

	type Month = {
		month: string;
		appointments: { total: number; done: number; noShow: number; cancelled: number; online: number };
		noShowRate: number;
		revenueMillimes: number;
		newPatients: number;
		topServices: { name: string; count: number }[];
	};
	type Stats = Month & { previous: Month };

	const current = todayTunis(clock.now()).slice(0, 7);
	const isOwner = $derived(auth.user?.role === 'owner');
	let month = $state(current);
	let stats = $state<Stats | null>(null);
	let error = $state('');
	let seq = 0;

	async function load() {
		const mine = ++seq;
		error = '';
		try {
			const result = await api<Stats>(`/api/stats?month=${month}`);
			if (mine === seq) stats = result;
		} catch {
			if (mine === seq) error = t('statistiques.loadError');
		}
	}

	$effect(() => {
		if (isOwner) void load();
	});

	function shift(by: number) {
		const [y, m] = month.split('-').map(Number);
		const d = new Date(Date.UTC(y, m - 1 + by, 1));
		month = d.toISOString().slice(0, 7);
		stats = null;
		void load();
	}

	const locale = () => (i18n.locale === 'ar' ? 'ar-TN-u-nu-latn' : 'fr-TN');
	const monthName = (m: string, withYear = true) =>
		new Intl.DateTimeFormat(locale(), { month: 'long', ...(withYear ? { year: 'numeric' } : {}), timeZone: 'UTC' }).format(new Date(`${m}-15T00:00:00Z`));
	const number = (n: number, digits = 0) => new Intl.NumberFormat(locale(), { maximumFractionDigits: digits, minimumFractionDigits: 0 }).format(n);
	const percent = (rate: number) => new Intl.NumberFormat(locale(), { style: 'percent', maximumFractionDigits: 1 }).format(rate);
	const round1 = (n: number) => Math.round(n * 10) / 10;

	type Tile = { label: string; value: string; sub?: string; delta: number; deltaText: string; goodWhenUp: boolean };
	const tiles = $derived.by((): Tile[] => {
		if (!stats) return [];
		const s = stats;
		const p = s.previous;
		const prevName = monthName(p.month, false);
		const diff = (d: number, text: (v: number) => string) =>
			d === 0 ? t('statistiques.same') : t(d > 0 ? 'statistiques.up' : 'statistiques.down', { value: text(Math.abs(d)), month: prevName });
		const count = (cur: number, prev: number) => ({ delta: cur - prev, deltaText: diff(cur - prev, (v) => number(v)) });
		// points between the rates as shown (one decimal), so the difference matches what is on screen
		const ratePoints = round1(round1(s.noShowRate * 100) - round1(p.noShowRate * 100));
		return [
			{ label: t('statistiques.kpis.appointments'), value: number(s.appointments.total), goodWhenUp: true, ...count(s.appointments.total, p.appointments.total) },
			{ label: t('statistiques.kpis.done'), value: number(s.appointments.done), goodWhenUp: true, ...count(s.appointments.done, p.appointments.done) },
			{
				label: t('statistiques.kpis.noShowRate'),
				value: percent(s.noShowRate),
				sub: t('statistiques.kpis.noShowCount', { count: s.appointments.noShow }),
				goodWhenUp: false,
				delta: ratePoints,
				deltaText: diff(ratePoints, (v) => t('statistiques.points', { value: number(v, 1) }))
			},
			{ label: t('statistiques.kpis.cancelled'), value: number(s.appointments.cancelled), goodWhenUp: false, ...count(s.appointments.cancelled, p.appointments.cancelled) },
			{
				label: t('statistiques.kpis.online'),
				value: number(s.appointments.online),
				sub: t('statistiques.kpis.onlineShare', { share: percent(s.appointments.total ? s.appointments.online / s.appointments.total : 0) }),
				goodWhenUp: true,
				...count(s.appointments.online, p.appointments.online)
			},
			{
				label: t('statistiques.kpis.revenue'),
				value: money(s.revenueMillimes),
				goodWhenUp: true,
				delta: s.revenueMillimes - p.revenueMillimes,
				deltaText: diff(s.revenueMillimes - p.revenueMillimes, (v) => money(v))
			},
			{ label: t('statistiques.kpis.newPatients'), value: number(s.newPatients), goodWhenUp: true, ...count(s.newPatients, p.newPatients) }
		];
	});

	const bars = $derived.by(() => {
		if (!stats) return [];
		const a = stats.appointments;
		const b = stats.previous.appointments;
		return [
			{ label: t('statistiques.kpis.appointments'), now: a.total, before: b.total },
			{ label: t('statistiques.kpis.done'), now: a.done, before: b.done },
			{ label: t('statistiques.kpis.online'), now: a.online, before: b.online },
			{ label: t('statistiques.kpis.cancelled'), now: a.cancelled, before: b.cancelled },
			{ label: t('agenda.actions.no_show'), now: a.noShow, before: b.noShow }
		];
	});
	const maxBar = $derived(Math.max(1, ...bars.flatMap((b) => [b.now, b.before])));
	const maxTop = $derived(Math.max(1, ...(stats?.topServices ?? []).map((s) => s.count)));
</script>

<svelte:head><title>{t('statistiques.title')} · Daftar</title></svelte:head>

<div class="flex flex-col gap-5">
	<div class="flex flex-wrap items-end justify-between gap-3">
		<div>
			<h1 class="text-2xl font-bold">{t('statistiques.title')}</h1>
			{#if isOwner}<p class="text-slate-600 first-letter:uppercase">{monthName(month)}</p>{/if}
		</div>
		{#if isOwner}
			<div class="flex items-center gap-1">
				<button type="button" class="btn-secondary min-w-11 px-2" aria-label={t('statistiques.previousMonth')} onclick={() => shift(-1)}><Icon name="start" /></button>
				<button type="button" class="btn-secondary min-w-11 px-2" aria-label={t('statistiques.nextMonth')} disabled={month >= current} onclick={() => shift(1)}
					><Icon name="end" /></button
				>
			</div>
		{/if}
	</div>

	{#if !isOwner}
		<p class="card text-slate-700">{t('statistiques.ownerOnly')}</p>
	{:else if error}
		<div role="alert" class="card flex flex-wrap items-center justify-between gap-3 border-rose-200 bg-rose-50 text-rose-900">
			<p>{error}</p>
			<button type="button" class="btn-secondary" onclick={load}>{t('common.retry')}</button>
		</div>
	{:else if !stats}
		<p class="card text-slate-600" aria-busy="true">{t('common.loading')}</p>
	{:else}
		<ul aria-label={t('statistiques.title')} class="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
			{#each tiles as tile (tile.label)}
				{@const good = tile.delta === 0 ? null : tile.delta > 0 === tile.goodWhenUp}
				<li class="flex flex-col gap-1 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
					<span class="text-sm font-semibold text-slate-600">{tile.label}</span>
					<span class="text-2xl font-bold whitespace-nowrap text-ink tabular-nums">{tile.value}</span>
					{#if tile.sub}<span class="text-sm text-slate-600">{tile.sub}</span>{/if}
					<span class="text-xs font-semibold {good === null ? 'text-slate-500' : good ? 'text-emerald-700' : 'text-rose-700'}">{tile.deltaText}</span>
				</li>
			{/each}
		</ul>

		<div class="grid items-start gap-5 lg:grid-cols-2">
			<section class="card flex flex-col gap-3 p-5">
				<h2 class="text-lg font-bold">{t('statistiques.chart.title')}</h2>
				<div class="flex gap-4 text-sm" aria-hidden="true">
					<span class="inline-flex items-center gap-2"><span class="h-3 w-3 rounded-sm bg-brand-700"></span>{t('statistiques.chart.thisMonth')}</span>
					<span class="inline-flex items-center gap-2"><span class="h-3 w-3 rounded-sm bg-slate-300"></span>{t('statistiques.chart.lastMonth')}</span>
				</div>
				<svg
					role="img"
					aria-label={t('statistiques.chart.title')}
					viewBox="0 0 {bars.length * 80} 180"
					class="h-56 w-full rtl:-scale-x-100"
					preserveAspectRatio="none"
				>
					<title>{t('statistiques.chart.title')}</title>
					{#each bars as b, i (b.label)}
						{@const x = i * 80 + 14}
						{@const hNow = (b.now / maxBar) * 150}
						{@const hBefore = (b.before / maxBar) * 150}
						<rect x={x + 26} y={155 - hBefore} width="22" height={hBefore} rx="3" fill="#cbd5e1"><title>{b.label}: {b.before}</title></rect>
						<rect {x} y={155 - hNow} width="22" height={hNow} rx="3" fill="#0f766e"><title>{b.label}: {b.now}</title></rect>
						<line x1={i * 80} x2={i * 80 + 80} y1="155.5" y2="155.5" stroke="#e2e8f0" />
					{/each}
				</svg>
				<ul class="grid gap-x-3 text-xs text-slate-600" style="grid-template-columns:repeat({bars.length},minmax(0,1fr))" aria-hidden="true">
					{#each bars as b (b.label)}<li class="text-center">{b.label}<br /><span class="font-semibold text-ink tabular-nums">{b.now}</span> / {b.before}</li>{/each}
				</ul>
			</section>

			<section aria-labelledby="top-title" class="card flex flex-col gap-3 p-5">
				<h2 id="top-title" class="text-lg font-bold">{t('statistiques.top.title')}</h2>
				{#if stats.topServices.length}
					<ul class="flex flex-col gap-2">
						{#each stats.topServices as s (s.name)}
							<li class="grid grid-cols-[minmax(0,10rem)_1fr_auto] items-center gap-3 text-sm">
								<span class="truncate font-medium">{s.name}</span>
								<span class="h-3 overflow-hidden rounded-full bg-slate-100" aria-hidden="true"
									><span class="block h-full rounded-full bg-accent-500" style="width:{(s.count / maxTop) * 100}%"></span></span
								>
								<span class="font-semibold tabular-nums">{t('statistiques.top.count', { count: s.count })}</span>
							</li>
						{/each}
					</ul>
				{:else}
					<p class="text-slate-600">{t('statistiques.top.empty')}</p>
				{/if}
			</section>
		</div>

		<StockStats {month} previousName={monthName(stats.previous.month, false)} />
	{/if}
</div>
