<script lang="ts">
	/**
	 * /salle/[displayToken] – the public waiting-room screen for the TV (story D1). Ticket numbers only, never names
	 * (design section 1, anti-goal). Labels in French and Arabic at once, refreshed every 10 s, keeps the screen awake,
	 * one gentle highlight when a new number is called.
	 */
	import { onMount } from 'svelte';
	import { ApiError, api } from '#lib/api';
	import { clock } from '#lib/clock';
	import { ar } from '#lib/i18n/ar';
	import { fr } from '#lib/i18n/fr';
	import { applyLocaleFromQuery, formatTime, i18n, t } from '#lib/i18n.svelte';
	import type { PublicDisplay } from '#lib/types/queue';

	const REFRESH_MS = 10_000;
	const token = decodeURIComponent(location.pathname.split('/').filter(Boolean)[1] ?? '');
	applyLocaleFromQuery();

	let data = $state<PublicDisplay | null>(null);
	let invalid = $state(false);
	let offline = $state(false);
	let updatedAt = $state<Date | null>(null);
	let flash = $state(false);
	let fullscreen = $state(false);

	type Label = keyof typeof fr.display;
	/** The label in the screen's language first, then in the other one (a waiting room reads both). */
	const both = (key: Label) => (i18n.locale === 'ar' ? [ar.display[key], fr.display[key]] : [fr.display[key], ar.display[key]]);

	async function load() {
		try {
			const next = await api<PublicDisplay>(`/api/public/display/${encodeURIComponent(token)}`);
			if (data && next.called[0] !== undefined && next.called[0] !== data.called[0]) {
				flash = true;
				setTimeout(() => (flash = false), 1600);
			}
			data = next;
			offline = false;
			updatedAt = clock.now();
		} catch (err) {
			if (err instanceof ApiError && err.status === 404) invalid = true;
			else offline = true;
		}
	}

	onMount(() => {
		void load();
		const timer = setInterval(() => {
			if (!invalid) void load();
		}, REFRESH_MS);
		let lock: { release: () => Promise<void> } | null = null;
		const nav = navigator as Navigator & { wakeLock?: { request: (type: 'screen') => Promise<{ release: () => Promise<void> }> } };
		void nav.wakeLock
			?.request('screen')
			.then((l) => (lock = l))
			.catch(() => undefined);
		const onFullscreen = () => (fullscreen = !!document.fullscreenElement);
		document.addEventListener('fullscreenchange', onFullscreen);
		return () => {
			clearInterval(timer);
			void lock?.release().catch(() => undefined);
			document.removeEventListener('fullscreenchange', onFullscreen);
		};
	});

	const current = $derived(data?.called[0]);
	const before = $derived(data?.called.slice(1, 3) ?? []);
</script>

<svelte:head><title>{data?.practiceName ?? t('display.title')} · Daftar</title></svelte:head>

<main class="screen flex min-h-screen flex-col bg-brand-900 px-[4vw] py-[3vh] text-white">
	{#if invalid}
		<p role="alert" class="m-auto max-w-2xl text-center text-3xl font-semibold">{t('display.invalid')}</p>
	{:else}
		<header class="flex items-center gap-6 border-b border-white/15 pb-[2vh]">
			<h1 class="min-w-0 flex-1 truncate text-[clamp(1.5rem,3vw,3rem)] font-bold">{data?.practiceName ?? ''}</h1>
			<span class="text-[clamp(1.5rem,3vw,3rem)] font-semibold text-brand-100 tabular-nums">{formatTime(updatedAt ?? clock.now())}</span>
		</header>

		<div class="grid flex-1 items-center gap-[4vw] py-[3vh] lg:grid-cols-[3fr_2fr]">
			<section aria-labelledby="called-title" class="flex flex-col items-center text-center lg:items-start lg:text-start">
				<h2 id="called-title" class="flex flex-col text-[clamp(1.25rem,2.4vw,2.5rem)] font-semibold text-brand-100">
					{#each both('called') as label, i (i)}<span lang={i === 0 ? i18n.locale : i18n.locale === 'ar' ? 'fr' : 'ar'} class={i ? 'text-[0.7em] text-brand-200' : ''}
							>{label}</span
						>{/each}
				</h2>
				{#if current !== undefined}
					<p class="called font-bold leading-none text-accent-400 tabular-nums" class:flash>{current}</p>
				{:else}
					<p class="py-[6vh] text-[clamp(2rem,6vw,6rem)] font-bold text-brand-100">{both('welcome').join(' · ')}</p>
				{/if}
				{#if before.length}
					<div class="flex gap-[2vw]">
						{#each before as n (n)}<span class="text-[clamp(2rem,5vw,5rem)] font-bold text-white/60 tabular-nums">{n}</span>{/each}
					</div>
				{/if}
			</section>

			<div class="flex flex-col gap-[3vh]">
				<section aria-labelledby="next-title" class="rounded-3xl bg-white/8 p-[2vw] ring-1 ring-white/10">
					<h2 id="next-title" class="flex flex-col text-[clamp(1.1rem,2vw,2rem)] font-semibold text-brand-100">
						{#each both('next') as label, i (i)}<span class={i ? 'text-[0.7em] text-brand-200' : ''}>{label}</span>{/each}
					</h2>
					<ul class="mt-[2vh] grid grid-cols-3 gap-[1.2vw]">
						{#each data?.next ?? [] as n (n)}
							<li class="grid place-items-center rounded-2xl bg-white/12 py-[2vh] text-[clamp(2rem,4.5vw,4.5rem)] font-bold tabular-nums">{n}</li>
						{/each}
					</ul>
				</section>
				<section aria-labelledby="waiting-title" class="flex items-center justify-between gap-4 rounded-3xl bg-white/8 p-[2vw] ring-1 ring-white/10">
					<h2 id="waiting-title" class="flex flex-col text-[clamp(1.1rem,2vw,2rem)] font-semibold text-brand-100">
						{#each both('waiting') as label, i (i)}<span class={i ? 'text-[0.7em] text-brand-200' : ''}>{label}</span>{/each}
					</h2>
					<p class="text-[clamp(2.5rem,5vw,5rem)] font-bold tabular-nums">{data?.waiting ?? 0}</p>
				</section>
			</div>
		</div>

		<footer class="flex flex-wrap items-center gap-4 text-sm text-brand-200">
			{#if offline}<p role="status" class="rounded-lg bg-amber-400 px-3 py-1 font-semibold text-ink">{t('display.reconnecting')}</p>{/if}
			{#if updatedAt}<p>{t('display.updated', { time: formatTime(updatedAt) })}</p>{/if}
			{#if !fullscreen}
				<button
					type="button"
					class="ms-auto rounded-lg px-3 py-2 font-semibold text-white ring-1 ring-white/30 hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-accent-400"
					onclick={() => void document.documentElement.requestFullscreen?.().catch(() => undefined)}>{t('display.fullscreen')}</button
				>
			{/if}
		</footer>
	{/if}
</main>

<style>
	.called {
		font-size: clamp(8rem, 26vw, 26rem);
		transform-origin: center;
	}
	@media (prefers-reduced-motion: no-preference) {
		.called.flash {
			animation: called 1.6s ease-out;
		}
	}
	@keyframes called {
		0% {
			transform: scale(0.85);
			text-shadow: 0 0 0 rgb(251 191 36 / 0);
		}
		35% {
			transform: scale(1.06);
			text-shadow: 0 0 60px rgb(251 191 36 / 0.65);
		}
		100% {
			transform: scale(1);
			text-shadow: 0 0 0 rgb(251 191 36 / 0);
		}
	}
</style>
