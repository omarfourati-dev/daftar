<script lang="ts">
	/**
	 * The practice sub-domain with a live check: format and reserved names locally, uniqueness with
	 * `GET /api/admin/slug-available` (300 ms after typing). `state` tells the page whether it may continue.
	 */
	import { api } from '../../api';
	import { t } from '../../i18n.svelte';
	import { practiceUrl } from '../../links';
	import { slugProblem, type SlugState } from '../../slug';
	import type { SlugCheck } from '../../types/admin';

	let {
		value = $bindable(),
		state = $bindable('idle'),
		original = '',
		refused = new Set<string>(),
		onedit,
		hint = t('admin.wizard.slugHint'),
		warning = ''
	}: {
		value: string;
		state?: SlugState;
		/** the current sub-domain of an existing practice: not checked again */
		original?: string;
		/** refused by the server on save (taken in the meantime) */
		refused?: Set<string>;
		onedit?: () => void;
		hint?: string;
		warning?: string;
	} = $props();

	const id = `slug-${Math.random().toString(36).slice(2, 9)}`;
	const suffix = practiceUrl('x', '/')
		.replace(/^https?:\/\/x\./, '')
		.replace(/\/.*$/, '');

	$effect(() => {
		const slug = value;
		if (!slug) {
			state = 'idle';
			return;
		}
		if (original && slug === original) {
			state = 'unchanged';
			return;
		}
		const local = slugProblem(slug);
		if (local) {
			state = local;
			return;
		}
		if (refused.has(slug)) {
			state = 'taken';
			return;
		}
		state = 'checking';
		let alive = true;
		const timer = setTimeout(async () => {
			try {
				const check = await api<SlugCheck>(`/api/admin/slug-available?slug=${encodeURIComponent(slug)}`);
				if (!alive) return;
				state = check.available ? 'available' : check.reason === 'reserved' ? 'reserved' : check.reason === 'invalid' ? 'invalid' : 'taken';
			} catch {
				if (alive) state = 'error';
			}
		}, 300);
		return () => {
			alive = false;
			clearTimeout(timer);
		};
	});

	const message = $derived(
		{
			idle: '',
			unchanged: '',
			checking: t('admin.wizard.slugChecking'),
			available: t('admin.wizard.slugAvailable', { url: value ? practiceUrl(value, '/') : '' }),
			taken: t('admin.wizard.slugTaken'),
			reserved: t('admin.wizard.slugReserved'),
			invalid: t('admin.wizard.slugInvalid'),
			error: t('admin.wizard.slugUnchecked')
		}[state]
	);
	const bad = $derived(['taken', 'reserved', 'invalid', 'error'].includes(state));
	const changed = $derived(!!original && value !== original);
</script>

<div class="flex flex-col gap-1">
	<label for={id} class="text-sm font-medium text-slate-700">{t('admin.wizard.slug')}</label>
	<div class="flex items-stretch" dir="ltr">
		<input
			{id}
			class="input min-w-0 font-mono sm:rounded-e-none"
			autocomplete="off"
			autocapitalize="none"
			spellcheck="false"
			maxlength="40"
			{value}
			oninput={(e) => {
				value = e.currentTarget.value.trim().toLowerCase();
				onedit?.();
			}}
			aria-invalid={bad ? 'true' : undefined}
			aria-describedby="{id}-hint {id}-state"
		/>
		<span
			class="hidden shrink-0 items-center rounded-e-lg border border-s-0 border-slate-300 bg-slate-50 px-3 font-mono text-sm text-slate-600 sm:inline-flex"
			>.{suffix}</span
		>
	</div>
	<p id="{id}-hint" class="text-sm text-slate-600">{hint}</p>
	{#if changed && warning}<p class="text-sm font-medium text-amber-800">{warning}</p>{/if}
	<p id="{id}-state" aria-live="polite" class="text-sm font-medium {state === 'available' ? 'text-emerald-800' : bad ? 'text-red-700' : 'text-slate-600'}">
		{message}
	</p>
</div>
