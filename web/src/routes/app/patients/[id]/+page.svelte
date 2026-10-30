<script lang="ts">
	/**
	 * /app/patients/[id] – the patient file (stories E1–E4, F1): identity and contact, medical alert in red at the top,
	 * same phone number (families), reliability (came / no-show / cancelled), appointments, treatments and payments
	 * with receipts, balance; add treatment or payment; edit; delete (owner, by typing the name).
	 */
	import { errorText } from '#lib/agenda/errors';
	import { api, ApiError, deps } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { clock } from '#lib/clock';
	import { FREEING, initials, money, personName, shortDay } from '#lib/agenda/format';
	import { displayPhone, telUrl, whatsappUrl } from '#lib/agenda/links';
	import { formatDate, formatDay, formatTime, t, translate, type MessageKey } from '#lib/i18n.svelte';
	import type { Appointment } from '#lib/types/agenda';
	import type { Ledger, Patient, Payment } from '#lib/types/patients';
	import Icon from '../../../../lib/components/daily/Icon.svelte';
	import Modal from '../../../../lib/components/daily/Modal.svelte';
	import StatusPill from '../../../../lib/components/agenda/StatusPill.svelte';
	import PatientForm from '../../../../lib/components/patients/PatientForm.svelte';
	import PaymentForm from '../../../../lib/components/patients/PaymentForm.svelte';
	import TreatmentForm from '../../../../lib/components/patients/TreatmentForm.svelte';

	let { data }: { data?: { id: number } } = $props();
	const id = $derived(data?.id ?? Number(location.pathname.split('/').filter(Boolean)[2]));

	let patient = $state<Patient | null>(null);
	let appointments = $state<Appointment[]>([]);
	let ledger = $state<Ledger | null>(null);
	let error = $state('');
	let missing = $state(false);
	let notice = $state('');
	let receiptId = $state<number | null>(null);
	let tab = $state<'appointments' | 'money' | 'notes'>('money');
	let dialog = $state<'edit' | 'treatment' | 'payment' | 'delete' | null>(null);
	let typed = $state('');
	let confirming = $state<string | null>(null);
	let busy = $state(false);

	const isOwner = $derived(auth.user?.role === 'owner');
	const showTooth = $derived(auth.user?.practice?.specialty === 'dentiste');

	async function load(target = id) {
		try {
			const [p, list, money] = await Promise.all([
				api<Patient>(`/api/patients/${target}`),
				api<Appointment[]>(`/api/patients/${target}/appointments`),
				api<Ledger>(`/api/patients/${target}/ledger`)
			]);
			if (target !== id) return;
			patient = p;
			appointments = list;
			ledger = money;
			error = '';
		} catch (err) {
			if (err instanceof ApiError && err.status === 404) missing = true;
			else error = t('patients.file.loadError');
		}
	}

	$effect(() => {
		const target = id;
		patient = null;
		missing = false;
		notice = '';
		void load(target);
	});

	const now = $derived(clock.now().toISOString());
	const upcoming = $derived(
		appointments.filter((a) => !FREEING.includes(a.status) && a.status !== 'done' && new Date(a.startsAt).toISOString() >= now).sort((a, b) => a.startsAt.localeCompare(b.startsAt))
	);
	const fullName = $derived(patient ? personName(patient) : '');
	const nameMatches = $derived(typed.trim().toLowerCase().replace(/\s+/g, ' ') === fullName.toLowerCase());

	function say(text: string, receipt: number | null = null) {
		notice = text;
		receiptId = receipt;
	}

	async function afterTreatment() {
		dialog = null;
		await load();
		say(t('patients.treatmentForm.saved'));
	}

	async function afterPayment(p: Payment) {
		dialog = null;
		await load();
		say(t('patients.paymentForm.saved'), p.id);
	}

	function afterEdit(p: Patient) {
		dialog = null;
		patient = { ...patient, ...p } as Patient;
		say(t('patients.form.saved'));
	}

	async function remove(kind: 'payment' | 'treatment', itemId: number) {
		busy = true;
		try {
			await api(`/api/${kind === 'payment' ? 'payments' : 'treatments'}/${itemId}`, { method: 'DELETE' });
			confirming = null;
			await load();
		} catch (err) {
			error = errorText(err);
		} finally {
			busy = false;
		}
	}

	async function deletePatient() {
		if (!patient || !nameMatches) return;
		busy = true;
		try {
			await api(`/api/patients/${patient.id}`, { method: 'DELETE' });
			void deps.goto('/app/patients');
		} catch (err) {
			error = errorText(err);
			dialog = null;
		} finally {
			busy = false;
		}
	}

	const TABS: { key: 'appointments' | 'money' | 'notes'; label: MessageKey }[] = [
		{ key: 'appointments', label: 'patients.file.tabAppointments' },
		{ key: 'money', label: 'patients.file.tabMoney' },
		{ key: 'notes', label: 'patients.file.tabNotes' }
	];
	function tabKeys(e: KeyboardEvent) {
		const i = TABS.findIndex((x) => x.key === tab);
		const forward = document.documentElement.dir === 'rtl' ? 'ArrowLeft' : 'ArrowRight';
		const back = forward === 'ArrowRight' ? 'ArrowLeft' : 'ArrowRight';
		if (e.key !== forward && e.key !== back) return;
		e.preventDefault();
		tab = TABS[(i + (e.key === forward ? 1 : TABS.length - 1)) % TABS.length].key;
		document.getElementById(`tab-${tab}`)?.focus();
	}
	const dateShort = (iso: string | null) => (iso ? (iso.length === 10 ? formatDay(iso) : formatDate(iso)) : '');
</script>

<svelte:head><title>{fullName || t('patients.title')} · Daftar</title></svelte:head>

<div class="flex flex-col gap-5">
	<a class="inline-flex items-center gap-1 self-start text-sm font-semibold text-brand-800 hover:underline" href="/app/patients"
		><Icon name="start" class="h-4 w-4" />{t('patients.file.back')}</a
	>

	{#if missing}
		<p role="alert" class="card text-lg font-semibold">{t('patients.file.notFound')}</p>
	{:else if error && !patient}
		<div role="alert" class="card flex flex-wrap items-center justify-between gap-3 border-rose-200 bg-rose-50 text-rose-900">
			<p>{error}</p>
			<button type="button" class="btn-secondary" onclick={() => load()}>{t('common.retry')}</button>
		</div>
	{:else if !patient || !ledger}
		<p class="card text-slate-600" aria-busy="true">{t('common.loading')}</p>
	{:else}
		{#if patient.alerts}
			<p role="note" class="flex items-start gap-3 rounded-xl border-2 border-rose-300 bg-rose-50 px-4 py-3 text-lg font-bold text-rose-800">
				<Icon name="alert" class="mt-1 h-6 w-6" /><span><span class="sr-only">{t('agenda.alert')} – </span>{patient.alerts}</span>
			</p>
		{/if}
		{#if notice}
			<p role="status" class="flex flex-wrap items-center gap-3 rounded-lg bg-emerald-50 px-4 py-2 font-medium text-emerald-900 ring-1 ring-emerald-200">
				{notice}
				{#if receiptId}<a class="btn-secondary min-h-10 px-3 text-sm" href="/app/recu/{receiptId}"><Icon name="receipt" class="h-4 w-4" />{t('patients.paymentForm.print')}</a>{/if}
			</p>
		{/if}
		{#if error}<p role="alert" class="rounded-lg bg-rose-50 px-3 py-2 text-rose-900 ring-1 ring-rose-200">{error}</p>{/if}

		<div class="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
			<div class="flex min-w-0 flex-col gap-5">
				<section class="card flex flex-col gap-4 p-5">
					<div class="flex flex-wrap items-start gap-4">
						<span class="grid h-14 w-14 shrink-0 place-items-center rounded-full bg-brand-50 text-lg font-bold text-brand-800 ring-1 ring-brand-200" aria-hidden="true"
							>{initials(patient)}</span
						>
						<div class="min-w-[12rem] flex-1">
							<h1 class="text-2xl font-bold">{fullName}</h1>
							<p class="flex flex-wrap gap-x-3 gap-y-1 text-sm text-slate-600">
								<span class="tabular-nums" dir="ltr">{displayPhone(patient.phone)}</span>
								{#if patient.birthYear}<span>{t('patients.file.born', { year: patient.birthYear })}</span>{/if}
								<span>{patient.lang === 'ar' ? t('patients.file.langAr') : t('patients.file.langFr')}</span>
								<span class={patient.reminderConsent ? 'text-emerald-800' : 'text-slate-500'}
									>{patient.reminderConsent ? t('patients.file.consentYes') : t('patients.file.consentNo')}</span
								>
							</p>
							{#if patient.samePhone?.length}
								<p class="mt-1 flex flex-wrap gap-x-2 text-sm">
									<span class="text-slate-600">{t('patients.file.samePhone')}</span>
									{#each patient.samePhone as other (other.id)}<a class="font-semibold text-brand-800 underline-offset-2 hover:underline" href="/app/patients/{other.id}"
											>{personName(other)}</a
										>{/each}
								</p>
							{/if}
						</div>
						<ul aria-label={t('patients.file.reliability')} class="flex w-full gap-2 sm:w-auto [&>li]:flex-1 sm:[&>li]:flex-none">
							<li class="flex min-w-16 flex-col items-center rounded-xl px-3 py-2 ring-1 ring-slate-200">
								<span class="text-xl font-bold text-emerald-700 tabular-nums">{patient.attended}</span><span class="text-xs text-slate-600">{t('patients.file.attended')}</span>
							</li>
							<li class="flex min-w-16 flex-col items-center rounded-xl px-3 py-2 ring-1 ring-slate-200">
								<span class="text-xl font-bold tabular-nums {patient.noShows ? 'text-rose-700' : 'text-slate-500'}">{patient.noShows}</span><span class="text-xs text-slate-600"
									>{t('patients.file.noShows')}</span
								>
							</li>
							<li class="flex min-w-16 flex-col items-center rounded-xl px-3 py-2 ring-1 ring-slate-200">
								<span class="text-xl font-bold text-slate-500 tabular-nums">{patient.cancelled}</span><span class="text-xs text-slate-600">{t('patients.file.cancelled')}</span>
							</li>
						</ul>
					</div>
					<div class="flex flex-wrap gap-2">
						<a class="btn-primary" href="/app/agenda?nouveau=1&patient={patient.id}"><Icon name="calendar" />{t('patients.file.newAppointment')}</a>
						<a class="btn-secondary" href={telUrl(patient.phone)}><Icon name="phone" />{t('patients.file.call')}</a>
						<a class="btn-secondary" href={whatsappUrl(patient.phone)} target="_blank" rel="noopener noreferrer"><Icon name="chat" />{t('patients.file.whatsapp')}</a>
						<button type="button" class="btn-secondary" onclick={() => (dialog = 'edit')}><Icon name="edit" />{t('patients.file.edit')}</button>
						{#if isOwner}
							<button type="button" class="btn-secondary ms-auto text-rose-800" onclick={() => ((typed = ''), (dialog = 'delete'))}
								><Icon name="trash" />{t('patients.file.delete')}</button
							>
						{/if}
					</div>
				</section>

				<section class="card p-0">
					<div role="tablist" aria-label={t('patients.file.tabs')} tabindex="-1" class="flex gap-1 overflow-x-auto border-b border-slate-200 px-3" onkeydown={tabKeys}>
						{#each TABS as item (item.key)}
							<button
								type="button"
								role="tab"
								id="tab-{item.key}"
								aria-selected={tab === item.key}
								aria-controls="panel-{item.key}"
								tabindex={tab === item.key ? 0 : -1}
								class="min-h-12 shrink-0 border-b-2 px-4 font-semibold {tab === item.key ? 'border-brand-700 text-brand-800' : 'border-transparent text-slate-600 hover:text-ink'}"
								onclick={() => (tab = item.key)}>{t(item.label)}</button
							>
						{/each}
					</div>

					{#if tab === 'money'}
						<div role="tabpanel" id="panel-money" aria-labelledby="tab-money" class="flex flex-col gap-6 p-4">
							<div class="flex flex-col gap-2">
								<div class="flex items-center justify-between gap-2">
									<h2 id="treatments-title" class="font-bold">{t('patients.money.treatments')}</h2>
									<button type="button" class="btn-secondary min-h-10 px-3 text-sm" onclick={() => (dialog = 'treatment')}><Icon name="plus" class="h-4 w-4" />{t('patients.money.addTreatment')}</button>
								</div>
								{#if ledger.treatments.length}
									<div class="overflow-x-auto">
										<table aria-labelledby="treatments-title" class="w-full text-sm">
											<thead class="text-xs text-slate-500">
												<tr class="border-b border-slate-200">
													<th scope="col" class="py-2 pe-3 text-start font-semibold">{t('patients.money.date')}</th>
													<th scope="col" class="py-2 pe-3 text-start font-semibold">{t('patients.money.label')}</th>
													{#if showTooth}<th scope="col" class="py-2 pe-3 text-start font-semibold">{t('patients.money.tooth')}</th>{/if}
													<th scope="col" class="py-2 text-end font-semibold">{t('patients.money.price')}</th>
													<td></td>
												</tr>
											</thead>
											<tbody>
												{#each ledger.treatments as tr (tr.id)}
													<tr class="border-b border-slate-100">
														<td class="py-2.5 pe-3 tabular-nums">{dateShort(tr.performedOn ?? tr.createdAt)}</td>
														<td class="py-2.5 pe-3">{tr.label}</td>
														{#if showTooth}<td class="py-2.5 pe-3 tabular-nums">{tr.tooth ?? ''}</td>{/if}
														<td class="py-2.5 text-end font-semibold tabular-nums">{money(tr.priceMillimes)}</td>
															<td class="py-1 ps-2 text-end">
																{#if confirming === `t${tr.id}`}
																	<button type="button" class="btn min-h-9 bg-rose-700 px-2 text-xs text-white" disabled={busy} onclick={() => remove('treatment', tr.id)}
																		>{t('patients.money.confirm')}</button
																	>
																	<button type="button" class="btn min-h-9 px-2 text-xs" onclick={() => (confirming = null)}>{t('patients.money.keep')}</button>
																{:else}
																	<button
																		type="button"
																		class="btn min-h-9 min-w-9 px-2 text-slate-500 hover:text-rose-700"
																		aria-label={t('patients.money.deleteTreatment', { label: tr.label })}
																		onclick={() => (confirming = `t${tr.id}`)}><Icon name="trash" class="h-4 w-4" /></button
																	>
																{/if}
															</td>
													</tr>
												{/each}
											</tbody>
										</table>
									</div>
								{:else}
									<p class="text-sm text-slate-600">{t('patients.money.noTreatments')}</p>
								{/if}
							</div>

							<div class="flex flex-col gap-2">
								<div class="flex items-center justify-between gap-2">
									<h2 id="payments-title" class="font-bold">{t('patients.money.payments')}</h2>
									<button type="button" class="btn-primary min-h-10 px-3 text-sm" onclick={() => (dialog = 'payment')}><Icon name="plus" class="h-4 w-4" />{t('patients.money.addPayment')}</button>
								</div>
								{#if ledger.payments.length}
									<div class="overflow-x-auto">
										<table aria-labelledby="payments-title" class="w-full text-sm">
											<thead class="text-xs text-slate-500">
												<tr class="border-b border-slate-200">
													<th scope="col" class="py-2 pe-3 text-start font-semibold">{t('patients.money.date')}</th>
													<th scope="col" class="py-2 pe-3 text-start font-semibold">{t('patients.money.method')}</th>
													<th scope="col" class="py-2 pe-3 text-start font-semibold"><span class="sr-only">{t('patients.money.receipt')}</span></th>
													<th scope="col" class="py-2 text-end font-semibold">{t('patients.money.amount')}</th>
													{#if isOwner}<td></td>{/if}
												</tr>
											</thead>
											<tbody>
												{#each ledger.payments as p (p.id)}
													<tr class="border-b border-slate-100">
														<td class="py-2.5 pe-3 tabular-nums">{formatDate(p.paidAt)}</td>
														<td class="py-2.5 pe-3">
															{translate(`paymentMethod.${p.method}`) ?? p.method}
															{#if p.isDeposit}<span class="ms-1 rounded-full bg-amber-100 px-2 text-xs font-semibold text-amber-900">{t('patients.money.deposit')}</span>{/if}
															{#if p.note}<span class="block text-xs text-slate-500">{p.note}</span>{/if}
														</td>
														<td class="py-2.5 pe-3"><a class="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700 hover:bg-slate-200" href="/app/recu/{p.id}">{t('patients.money.receipt')}</a></td>
														<td class="py-2.5 text-end font-semibold tabular-nums">{money(p.amountMillimes)}</td>
														{#if isOwner}
															<td class="py-1 ps-2 text-end whitespace-nowrap">
																{#if confirming === `p${p.id}`}
																	<button type="button" class="btn min-h-9 bg-rose-700 px-2 text-xs text-white" disabled={busy} onclick={() => remove('payment', p.id)}
																		>{t('patients.money.confirm')}</button
																	>
																	<button type="button" class="btn min-h-9 px-2 text-xs" onclick={() => (confirming = null)}>{t('patients.money.keep')}</button>
																{:else}
																	<button
																		type="button"
																		class="btn min-h-9 min-w-9 px-2 text-slate-500 hover:text-rose-700"
																		aria-label={t('patients.money.deletePayment', { date: formatDate(p.paidAt) })}
																		onclick={() => (confirming = `p${p.id}`)}><Icon name="trash" class="h-4 w-4" /></button
																	>
																{/if}
															</td>
														{/if}
													</tr>
												{/each}
											</tbody>
										</table>
									</div>
								{:else}
									<p class="text-sm text-slate-600">{t('patients.money.noPayments')}</p>
								{/if}
							</div>
						</div>
					{:else if tab === 'appointments'}
						<div role="tabpanel" id="panel-appointments" aria-labelledby="tab-appointments" class="p-4">
							{#if appointments.length}
								<ul class="divide-y divide-slate-100">
									{#each appointments as a (a.id)}
										<li class="flex flex-wrap items-center gap-x-3 gap-y-1 py-2.5">
											<a class="min-w-0 flex-1 hover:underline" href="/app/agenda?date={a.startsAt.slice(0, 10)}">
												<span class="font-semibold tabular-nums first-letter:uppercase">{shortDay(a.startsAt)} {formatTime(a.startsAt)}</span>
												<span class="text-slate-700">– {a.reason}</span>
												{#if a.practitionerName}<span class="block text-sm text-slate-500">{a.practitionerName}</span>{/if}
											</a>
											<StatusPill status={a.status} />
										</li>
									{/each}
								</ul>
							{:else}
								<p class="text-slate-600">{t('patients.file.noAppointments')}</p>
							{/if}
						</div>
					{:else}
						<div role="tabpanel" id="panel-notes" aria-labelledby="tab-notes" class="p-4 whitespace-pre-line">
							{patient.notes || t('patients.file.noNotes')}
						</div>
					{/if}
				</section>
			</div>

			<aside class="flex flex-col gap-4">
				<section aria-labelledby="balance-title" class="card flex flex-col gap-3 p-5">
					<h2 id="balance-title" class="font-bold">{t('patients.file.balance')}</h2>
					<dl class="flex flex-col gap-2 text-sm">
						<div class="flex justify-between gap-3"><dt class="text-slate-600">{t('patients.file.total')}</dt><dd class="font-semibold tabular-nums">{money(ledger.totalMillimes)}</dd></div>
						<div class="flex justify-between gap-3"><dt class="text-slate-600">{t('patients.file.paid')}</dt><dd class="font-semibold tabular-nums">{money(ledger.paidMillimes)}</dd></div>
						{#if ledger.dueMillimes > 0}
							<div class="flex flex-col gap-1 rounded-xl bg-amber-50 p-4 ring-1 ring-amber-200">
								<dt class="font-semibold text-amber-900">{t('patients.file.due')}</dt>
								<dd class="text-3xl font-bold text-amber-900 tabular-nums">{money(ledger.dueMillimes)}</dd>
							</div>
						{:else if ledger.dueMillimes < 0}
							<div class="flex justify-between gap-3 rounded-xl bg-emerald-50 p-3 text-emerald-900">
								<dt class="font-semibold">{t('patients.file.credit')}</dt>
								<dd class="font-bold tabular-nums">{money(-ledger.dueMillimes)}</dd>
							</div>
						{:else}
							<div class="rounded-xl bg-emerald-50 p-3 font-semibold text-emerald-900"><dt class="sr-only">{t('patients.file.due')}</dt><dd>{t('patients.file.settled')}</dd></div>
						{/if}
					</dl>
				</section>

				{#if patient.noShows >= 2}
					<div class="flex gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-rose-900">
						<Icon name="alert" class="mt-0.5 h-5 w-5" />
						<div>
							<p class="font-bold">{t('patients.file.noShowWarning', { count: patient.noShows })}</p>
							<p class="text-sm">{t('patients.file.noShowHint')}</p>
						</div>
					</div>
				{/if}

				<section aria-labelledby="upcoming-title" class="card flex flex-col gap-3 p-5">
					<h2 id="upcoming-title" class="font-bold">{t('patients.file.upcoming')}</h2>
					{#if upcoming.length}
						<ul class="flex flex-col divide-y divide-slate-100">
							{#each upcoming as a (a.id)}
								<li class="flex items-center gap-3 py-2">
									<span class="grid w-12 shrink-0 place-items-center rounded-lg bg-slate-50 py-1 text-center ring-1 ring-slate-200">
										<span class="text-lg leading-tight font-bold tabular-nums">{Number(a.startsAt.slice(8, 10))}</span>
										<span class="text-xs text-slate-500">{shortDay(a.startsAt).split(' ').slice(-1)[0]}</span>
									</span>
									<span class="min-w-0 flex-1">
										<span class="block font-semibold"><span class="tabular-nums">{formatTime(a.startsAt)}</span> – {a.reason}</span>
										{#if a.practitionerName}<span class="block text-xs text-slate-500">{a.practitionerName}</span>{/if}
									</span>
									<StatusPill status={a.status} />
								</li>
							{/each}
						</ul>
					{:else}
						<p class="text-sm text-slate-600">{t('patients.file.noUpcoming')}</p>
					{/if}
				</section>
			</aside>
		</div>
	{/if}
</div>

{#if patient}
	{#if dialog === 'edit'}
		<PatientForm {patient} onsaved={afterEdit} onclose={() => (dialog = null)} />
	{:else if dialog === 'treatment'}
		<TreatmentForm patientId={patient.id} {showTooth} onsaved={afterTreatment} onclose={() => (dialog = null)} />
	{:else if dialog === 'payment' && ledger}
		<PaymentForm patientId={patient.id} due={ledger.dueMillimes} appointments={upcoming} onsaved={afterPayment} onclose={() => (dialog = null)} />
	{:else if dialog === 'delete'}
		<Modal title={t('patients.remove.title', { name: fullName })} onclose={() => (dialog = null)}>
			<div class="flex flex-col gap-3">
				<p class="rounded-lg bg-rose-50 px-3 py-2 font-medium text-rose-900">{t('patients.remove.warning')}</p>
				<label class="label">{t('patients.remove.typeName', { name: fullName })}<input class="input" bind:value={typed} autocomplete="off" data-autofocus /></label>
			</div>
			{#snippet footer()}
				<button type="button" class="btn-secondary" onclick={() => (dialog = null)}>{t('common.cancel')}</button>
				<button type="button" class="btn bg-rose-700 text-white hover:bg-rose-800" disabled={!nameMatches || busy} onclick={deletePatient}>{t('patients.remove.confirm')}</button>
			{/snippet}
		</Modal>
	{/if}
{/if}
