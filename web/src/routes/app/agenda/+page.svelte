<script lang="ts">
	/**
	 * /app/agenda – the practice's day (one column per practitioner) or week (one column per day), ruled like the
	 * paper agenda it replaces. Opening hours, pauses and closures are hatched, a red line marks "now"; a free slot
	 * opens the appointment dialog. Phones get a list per day instead of the grid.
	 * Address: `?date=YYYY-MM-DD`, `?vue=semaine`.
	 */
	import { onMount } from 'svelte';
	import { clock } from '#lib/clock';
	import { loadAgendaBase, loadAppointments, type AgendaBase } from '#lib/agenda/data';
	import { practitionerLabel } from '#lib/agenda/format';
	import { agendaRange, closureOn, hhmm, minutesOfDay, tunisDayOf, weekDays, windowsOn } from '#lib/agenda/time';
	import { addDays, formatDay, i18n, t, todayTunis } from '#lib/i18n.svelte';
	import type { Appointment, Practitioner } from '#lib/types/agenda';
	import { viewport } from '#lib/viewport.svelte';
	import AgendaList from '../../../lib/components/agenda/AgendaList.svelte';
	import DayColumn from '../../../lib/components/agenda/DayColumn.svelte';
	import Icon from '../../../lib/components/daily/Icon.svelte';

	const DAY = /^\d{4}-\d{2}-\d{2}$/;
	const params = new URLSearchParams(location.search);
	const today = () => todayTunis(clock.now());

	let day = $state(DAY.test(params.get('date') ?? '') ? (params.get('date') as string) : today());
	let view = $state<'day' | 'week'>(params.get('vue') === 'semaine' ? 'week' : 'day');
	/** Practitioner filter: null = everybody, 0 = appointments without practitioner. */
	let filter = $state<number | null>(null);
	let base = $state<AgendaBase | null>(null);
	let appointments = $state<Appointment[]>([]);
	let loading = $state(true);
	let error = $state('');
	let tick = $state(0);
	let seq = 0;

	const days = $derived(view === 'day' ? [day] : weekDays(day));
	const ppm = $derived(view === 'day' ? 1.6 : 1.2);

	async function load() {
		const mine = ++seq;
		loading = true;
		error = '';
		try {
			const [b, list] = await Promise.all([base ? Promise.resolve(base) : loadAgendaBase(), loadAppointments(days[0], days[days.length - 1])]);
			if (mine !== seq) return;
			base = b;
			appointments = list;
		} catch {
			if (mine === seq) error = t('agenda.loadError');
		} finally {
			if (mine === seq) loading = false;
		}
	}

	function go(nextDay: string, nextView: 'day' | 'week' = view) {
		if (!DAY.test(nextDay)) return;
		day = nextDay;
		view = nextView;
		void load();
	}

	onMount(() => {
		void load();
		const timer = setInterval(() => tick++, 60_000);
		return () => clearInterval(timer);
	});

	const matches = (a: Appointment) => filter === null || (filter === 0 ? a.practitionerId == null : a.practitionerId === filter);
	const visible = $derived(appointments.filter(matches).sort((a, b) => a.startsAt.localeCompare(b.startsAt)));
	const byDay = $derived.by(() => {
		const map = new Map<string, Appointment[]>();
		for (const a of visible) {
			const d = tunisDayOf(a.startsAt);
			map.set(d, [...(map.get(d) ?? []), a]);
		}
		return map;
	});

	const practitioners = $derived(base?.practitioners ?? []);
	const nameOf = (a: Appointment) => {
		const p = practitioners.find((x) => x.id === a.practitionerId);
		return p ? practitionerLabel(p) : a.practitionerName;
	};

	type Column = { key: string; id: number | null; label: string; practitioner: Pick<Practitioner, 'name' | 'title'> | null; items: Appointment[] };
	/** Day view: one column per practitioner (+ "without practitioner" when needed). */
	const columns = $derived.by(() => {
		const cols: Column[] = practitioners.map((p) => ({ key: `p${p.id}`, id: p.id, label: practitionerLabel(p), practitioner: p, items: [] }));
		const noneLabel = practitioners.length ? t('agenda.noPractitioner') : formatDay(day, 'long');
		for (const a of appointments.filter((x) => tunisDayOf(x.startsAt) === day)) {
			let col = cols.find((c) => c.id === (a.practitionerId ?? null));
			if (!col) {
				col =
					a.practitionerId == null
						? { key: 'none', id: null, label: noneLabel, practitioner: null, items: [] }
						: { key: `p${a.practitionerId}`, id: a.practitionerId, label: a.practitionerName ?? '', practitioner: { name: a.practitionerName ?? '' }, items: [] };
				cols.push(col);
			}
			col.items.push(a);
		}
		if (!cols.length) cols.push({ key: 'none', id: null, label: noneLabel, practitioner: null, items: [] });
		return filter === null ? cols : cols.filter((c) => (filter === 0 ? c.id === null : c.id === filter));
	});

	const range = $derived.by(() => {
		let { start, end } = agendaRange(base?.practice.weeklyHours);
		for (const a of visible) {
			const s = minutesOfDay(a.startsAt);
			start = Math.min(start, Math.floor(s / 60) * 60);
			end = Math.max(end, Math.min(1440, Math.ceil((s + a.durationMin) / 60) * 60));
		}
		return { start, end };
	});

	const hours = $derived.by(() => {
		const list: number[] = [];
		for (let m = Math.ceil(range.start / 60) * 60; m <= range.end; m += 60) list.push(m);
		return list;
	});

	const now = $derived.by(() => {
		void tick;
		const at = clock.now();
		const index = days.indexOf(tunisDayOf(at));
		const minutes = minutesOfDay(at);
		if (index < 0 || minutes < range.start || minutes > range.end) return null;
		return { index, minutes };
	});

	const closure = $derived(base ? closureOn(base.closures, day) : null);
	const closureText = (d: string) => {
		const c = base ? closureOn(base.closures, d) : null;
		if (c) return c.label ? t('agenda.closure', { label: c.label }) : t('agenda.closedDay');
		return windowsOn(base?.practice.weeklyHours, d).length ? null : t('agenda.closedDay');
	};

	function intl(options: Intl.DateTimeFormatOptions) {
		return new Intl.DateTimeFormat(i18n.locale === 'ar' ? 'ar-TN-u-nu-latn' : 'fr-TN', { timeZone: 'Africa/Tunis', ...options });
	}
	const dayMonth = (d: string) => intl({ day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(`${d}T12:00:00+01:00`));
	const weekdayShort = (d: string) => intl({ weekday: 'short' }).format(new Date(`${d}T12:00:00+01:00`));

	const title = $derived(view === 'day' ? formatDay(day, 'long') : `${dayMonth(days[0])} – ${dayMonth(days[6])}`);
	const isEmpty = $derived(!loading && !error && visible.length === 0);


	function step(direction: 1 | -1) {
		go(addDays(day, direction * (view === 'day' ? 1 : 7)));
	}

	// The appointment dialogs come with the next stories; the grid already offers the targets.
	function openSlot(_day: string, _time: string, _practitionerId: number | null) {}
	function openAppointment(_a: Appointment) {}
</script>

<svelte:head><title>{t('agenda.title')} · Daftar</title></svelte:head>

<div class="flex flex-col gap-4">
	<div class="flex flex-wrap items-end justify-between gap-3">
		<div class="min-w-0">
			<h1 class="text-2xl font-bold">{t('agenda.title')}</h1>
			<p class="text-slate-600 first-letter:uppercase" aria-live="polite">{title}</p>
		</div>
		<div class="flex flex-wrap items-center gap-2">
			<div class="flex items-center gap-1">
				<button type="button" class="btn-secondary min-w-11 px-2" aria-label={view === 'day' ? t('agenda.previousDay') : t('agenda.previousWeek')} onclick={() => step(-1)}>
					<Icon name="start" />
				</button>
				<button type="button" class="btn-secondary" onclick={() => go(today())}>{t('agenda.today')}</button>
				<button type="button" class="btn-secondary min-w-11 px-2" aria-label={view === 'day' ? t('agenda.nextDay') : t('agenda.nextWeek')} onclick={() => step(1)}>
					<Icon name="end" />
				</button>
			</div>
			<div class="inline-flex rounded-lg border border-slate-300 bg-white p-0.5" role="group" aria-label={t('agenda.view')}>
				{#each [['day', t('agenda.day')], ['week', t('agenda.week')]] as [value, text] (value)}
					<button
						type="button"
						class="min-h-10 rounded-md px-4 font-semibold {view === value ? 'bg-brand-700 text-white' : 'text-slate-700 hover:bg-slate-100'}"
						aria-pressed={view === value}
						onclick={() => go(day, value as 'day' | 'week')}>{text}</button
					>
				{/each}
			</div>
			<label class="sr-only" for="agenda-date">{t('agenda.pickDate')}</label>
			<input id="agenda-date" type="date" class="input w-auto" value={day} onchange={(e) => go(e.currentTarget.value)} />
			<a href="/app/agenda/imprimer?date={day}" class="btn-secondary"><Icon name="print" />{t('agenda.printDay')}</a>
		</div>
	</div>

	{#if practitioners.length > 1}
		<div class="flex flex-wrap gap-2" role="group" aria-label={t('agenda.practitioners')}>
			<button
				type="button"
				class="min-h-10 rounded-full border px-4 text-sm font-semibold {filter === null ? 'border-brand-700 bg-brand-700 text-white' : 'border-slate-300 bg-white text-slate-700'}"
				aria-pressed={filter === null}
				onclick={() => (filter = null)}>{t('agenda.allPractitioners')}</button
			>
			{#each practitioners as p (p.id)}
				<button
					type="button"
					class="inline-flex min-h-10 items-center gap-2 rounded-full border px-4 text-sm font-semibold {filter === p.id
						? 'border-brand-700 bg-brand-700 text-white'
						: 'border-slate-300 bg-white text-slate-700'}"
					aria-pressed={filter === p.id}
					onclick={() => (filter = filter === p.id ? null : p.id)}
					><span class="h-2.5 w-2.5 rounded-full ring-1 ring-white" style="background:{p.color ?? '#0f766e'}" aria-hidden="true"></span>{practitionerLabel(
						p
					)}</button
				>
			{/each}
		</div>
	{/if}

	{#if error}
		<div role="alert" class="card flex flex-wrap items-center justify-between gap-3 border-rose-200 bg-rose-50 text-rose-900">
			<p>{error}</p>
			<button type="button" class="btn-secondary" onclick={load}>{t('common.retry')}</button>
		</div>
	{:else if !base}
		<p class="card text-slate-600" aria-busy="true">{t('common.loading')}</p>
	{:else}
		{#if view === 'day' && closure}
			<p class="rounded-lg border border-slate-300 bg-slate-100 px-4 py-3 font-semibold text-slate-700">
				{closure.label ? t('agenda.closure', { label: closure.label }) : t('agenda.closedDay')}
			</p>
		{/if}
		{#if isEmpty}
			<p class="text-slate-600">
				<span>{view === 'day' ? t('agenda.emptyDay') : t('agenda.emptyWeek')}</span>
				<span class="text-slate-500">{t('agenda.emptyHint')}</span>
			</p>
		{/if}

		{#if viewport.narrow}
			<AgendaList {days} {byDay} closedText={closureText} practitionerOf={(a) => (practitioners.length > 1 ? nameOf(a) : null)} onopen={openAppointment} />
		{:else}
			<div class="rounded-xl border border-slate-200 bg-white shadow-sm" aria-busy={loading}>
				<div class="sticky top-0 z-30 flex rounded-t-xl border-b border-slate-200 bg-white/95 backdrop-blur">
					<div class="w-14 shrink-0"></div>
					{#if view === 'day'}
						{#each columns as col (col.key)}
							<div class="flex min-w-0 flex-1 items-center gap-2 border-s border-slate-200 px-3 py-2.5">
								{#if col.practitioner}
									<span
										class="grid h-8 w-8 shrink-0 place-items-center rounded-full text-xs font-bold text-white"
										style="background:{practitioners.find((p) => p.id === col.id)?.color ?? '#0f766e'}"
										aria-hidden="true"
										>{col.practitioner.name
											.split(/\s+/)
											.slice(0, 2)
											.map((w) => w.charAt(0))
											.join('')}</span
									>
								{/if}
								<span class="min-w-0 truncate font-semibold">{col.label}</span>
								<span class="ms-auto shrink-0 text-xs text-slate-500">{t('agenda.count', { count: col.items.length })}</span>
							</div>
						{/each}
					{:else}
						{#each days as d (d)}
							{@const isToday = d === today()}
							<button type="button" class="flex min-w-0 flex-1 flex-col items-center border-s border-slate-200 px-1 py-2 hover:bg-brand-50" onclick={() => go(d, 'day')}>
								<span class="text-xs font-medium text-slate-500 first-letter:uppercase">{weekdayShort(d)}</span>
								<span class="grid h-8 w-8 place-items-center rounded-full text-base font-bold tabular-nums {isToday ? 'bg-brand-700 text-white' : 'text-ink'}"
									>{Number(d.slice(8))}</span
								>
							</button>
						{/each}
					{/if}
				</div>
				<div class="flex">
					<div class="relative w-14 shrink-0" style="height:{(range.end - range.start) * ppm}px" aria-hidden="true">
						{#each hours as m (m)}
							<span class="absolute end-2 -translate-y-1/2 text-xs text-slate-500 tabular-nums" style="top:{Math.max((m - range.start) * ppm, 8)}px">{hhmm(m)}</span>
						{/each}
					</div>
					<div class="relative flex min-w-0 flex-1">
						{#if view === 'day'}
							{#each columns as col (col.key)}
								<DayColumn
									label={col.label}
									appointments={col.items}
									windows={windowsOn(base.practice.weeklyHours, day)}
									closed={!!closure}
									closedLabel={t('agenda.closedDay')}
									{range}
									{ppm}
									slotMinutes={base.practice.slotMinutes || 15}
									practitioner={col.practitioner}
									onslot={(time) => openSlot(day, time, col.id)}
									onopen={openAppointment}
								/>
							{/each}
						{:else}
							{#each days as d (d)}
								<DayColumn
									label={formatDay(d, 'long')}
									appointments={byDay.get(d) ?? []}
									windows={windowsOn(base.practice.weeklyHours, d)}
									closed={!!closureOn(base.closures, d)}
									closedLabel={closureText(d) ?? ''}
									{range}
									{ppm}
									slotMinutes={base.practice.slotMinutes || 15}
									practitioner={filter ? (practitioners.find((p) => p.id === filter) ?? null) : null}
									minimal
									onslot={(time) => openSlot(d, time, filter || null)}
									onopen={openAppointment}
								/>
							{/each}
						{/if}
						{#if now}
							{@const width = view === 'day' ? 100 : 100 / 7}
							<div
								role="img"
								aria-label={t('agenda.now', { time: hhmm(now.minutes) })}
								class="pointer-events-none absolute z-20 h-0.5 bg-rose-600"
								style="top:{(now.minutes - range.start) * ppm}px;inset-inline-start:{view === 'day' ? 0 : now.index * width}%;width:{width}%"
							>
								<span class="absolute -start-1.5 -top-1 h-2.5 w-2.5 rounded-full bg-rose-600"></span>
							</div>
						{/if}
					</div>
				</div>
			</div>
		{/if}
	{/if}
</div>
