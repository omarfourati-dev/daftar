<script lang="ts">
	/**
	 * Opening hours per weekday with breaks (several windows a day) – the same editor in the admin wizard and in
	 * the owner's settings. Times are `<input type="time">` (native pickers on phones), always left-to-right.
	 */
	import { t } from '../i18n.svelte';
	import { WEEKDAYS, copyDay, hoursProblems, MAX_WINDOWS_PER_DAY, type Weekday, type WeeklyHours } from '../hours';

	let { value = $bindable() }: { value: WeeklyHours } = $props();

	const problems = $derived(hoursProblems(value));
	const dayName = (d: Weekday) => t(`kit.weekdays.${d}`);

	function addMinutes(time: string, minutes: number): string {
		const [h, m] = time.split(':').map(Number);
		const total = Math.min(h * 60 + m + minutes, 23 * 60 + 59);
		return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
	}

	function toggle(day: Weekday) {
		value[day] = value[day].length ? [] : [['08:00', '12:00']];
	}

	function addWindow(day: Weekday) {
		const last = value[day].at(-1);
		const start = last ? addMinutes(last[1], 60) : '08:00';
		value[day] = [...value[day], [start, addMinutes(start, 60)]];
	}

	function removeWindow(day: Weekday, index: number) {
		value[day] = value[day].filter((_, i) => i !== index);
	}

	function copyToOpenDays(day: Weekday) {
		value = copyDay(
			value,
			day,
			WEEKDAYS.filter((d) => d !== day && value[d].length > 0)
		);
	}
</script>

<div class="flex flex-col gap-3">
	<p class="text-sm text-slate-600">{t('kit.hours.hint')}</p>
	<ul class="flex flex-col divide-y divide-slate-200 rounded-xl border border-slate-200 bg-white">
		{#each WEEKDAYS as day (day)}
			{@const open = value[day].length > 0}
			{@const problem = problems[day]}
			<li class="flex flex-col gap-3 p-3 sm:flex-row sm:items-start">
				<label class="flex min-h-11 w-36 shrink-0 cursor-pointer items-center gap-3 font-semibold text-ink">
					<input type="checkbox" class="h-5 w-5 accent-brand-700" checked={open} onchange={() => toggle(day)} />
					{dayName(day)}
				</label>
				{#if open}
					<div class="flex min-w-0 flex-1 flex-col gap-2">
						{#each value[day] as window, i (i)}
							<div class="flex items-center gap-1.5 sm:gap-2">
								<input
									type="time"
									dir="ltr"
									class="input w-28 px-2 sm:w-32 sm:px-3"
									aria-label={t('kit.hours.start', { day: dayName(day), n: i + 1 })}
									aria-invalid={problem ? 'true' : undefined}
									bind:value={window[0]}
								/>
								<span aria-hidden="true" class="text-slate-500">–</span>
								<input
									type="time"
									dir="ltr"
									class="input w-28 px-2 sm:w-32 sm:px-3"
									aria-label={t('kit.hours.end', { day: dayName(day), n: i + 1 })}
									aria-invalid={problem ? 'true' : undefined}
									bind:value={window[1]}
								/>
								<button
									type="button"
									class="inline-flex h-11 w-11 items-center justify-center rounded-lg text-slate-500 hover:bg-rose-50 hover:text-rose-700 focus-visible:outline-2 focus-visible:outline-brand-700"
									aria-label={t('kit.hours.removeWindow', { from: window[0], to: window[1], day: t(`kit.weekdaysOf.${day}`) })}
									onclick={() => removeWindow(day, i)}
								>
									<svg viewBox="0 0 20 20" class="h-5 w-5" aria-hidden="true"
										><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="2" stroke-linecap="round" /></svg
									>
								</button>
							</div>
						{/each}
						{#if problem}
							<p class="text-sm font-medium text-red-700">{t(`kit.hours.problem.${problem}`, { day: dayName(day) })}</p>
						{/if}
						<div class="flex flex-wrap gap-x-4 gap-y-1">
							{#if value[day].length < MAX_WINDOWS_PER_DAY}
								<button
									type="button"
									class="min-h-9 text-sm font-semibold text-brand-700 underline-offset-4 hover:underline"
									aria-label={t('kit.hours.addWindow', { day: t(`kit.weekdaysOn.${day}`) })}
									onclick={() => addWindow(day)}><span aria-hidden="true">+</span> {t('kit.hours.addWindowShort')}</button
								>
							{/if}
							<button
								type="button"
								class="min-h-9 text-sm font-semibold text-slate-600 underline-offset-4 hover:underline"
								aria-label={t('kit.hours.copy', { day: t(`kit.weekdaysOf.${day}`) })}
								onclick={() => copyToOpenDays(day)}>{t('kit.hours.copyShort')}</button
							>
						</div>
					</div>
				{:else}
					<p class="flex min-h-11 items-center text-slate-500">{t('kit.hours.closed')}</p>
				{/if}
			</li>
		{/each}
	</ul>
</div>
