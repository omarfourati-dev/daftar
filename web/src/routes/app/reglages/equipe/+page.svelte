<script lang="ts">
	/**
	 * Team: accounts with their role, password reset links (story A3), pending invitations and new invitation
	 * links to send by WhatsApp (story A2). Only the owner.
	 */
	import { onMount } from 'svelte';
	import { api, apiErrorMessage } from '#lib/api';
	import { auth } from '#lib/auth.svelte';
	import { formatDate, formatDateTime, t, translate } from '#lib/i18n.svelte';
	import { practiceUrl } from '#lib/links';
	import type { OneTimeLink, StaffInvitation, StaffMember } from '#lib/types/practice';
	import ConfirmDialog from '../../../../lib/components/ConfirmDialog.svelte';
	import CopyLink from '../../../../lib/components/CopyLink.svelte';
	import LoadState from '../../../../lib/components/LoadState.svelte';
	import OwnerOnly from '../../../../lib/components/reglages/OwnerOnly.svelte';

	const ROLES = ['dentist', 'assistant'] as const;
	let staff = $state<StaffMember[]>([]);
	let invitations = $state<StaffInvitation[]>([]);
	let loading = $state(true);
	let error = $state('');
	let notice = $state('');
	let actionError = $state('');
	let resets = $state<Record<number, { url: string; expiresAt: string }>>({});
	let inviteRole = $state<'dentist' | 'assistant'>('assistant');
	let invited = $state<{ url: string; role: string; expiresAt: string } | null>(null);
	let removing = $state<StaffMember | null>(null);
	let busy = $state(false);

	const slug = $derived(auth.user?.practice?.slug ?? '');
	const practiceName = $derived(auth.user?.practice?.name ?? '');
	const roleName = (role: string) => translate(`roles.${role}`) ?? role;

	async function load() {
		loading = true;
		error = '';
		try {
			[staff, invitations] = await Promise.all([api<StaffMember[]>('/api/staff'), api<StaffInvitation[]>('/api/staff/invitations')]);
		} catch (err) {
			error = apiErrorMessage(err);
		} finally {
			loading = false;
		}
	}
	onMount(() => {
		if (auth.user?.role === 'owner') void load();
	});

	async function run(action: () => Promise<void>) {
		notice = '';
		actionError = '';
		busy = true;
		try {
			await action();
		} catch (err) {
			actionError = apiErrorMessage(err);
		} finally {
			busy = false;
		}
	}

	const changeRole = (member: StaffMember, role: string) =>
		run(async () => {
			const updated = await api<StaffMember>(`/api/staff/${member.id}`, { method: 'PATCH', json: { role } });
			staff = staff.map((s) => (s.id === member.id ? { ...s, role: updated?.role ?? role } : s));
			notice = t('reglages.equipe.roleSaved');
		});

	const resetLink = (member: StaffMember) =>
		run(async () => {
			const link = await api<OneTimeLink>(`/api/staff/${member.id}/reset-link`, { method: 'POST' });
			resets = { ...resets, [member.id]: { url: practiceUrl(slug, `/reinitialiser#${link.token}`), expiresAt: link.expiresAt } };
		});

	const invite = () =>
		run(async () => {
			const link = await api<OneTimeLink>('/api/staff/invitations', { method: 'POST', json: { role: inviteRole } });
			invited = { url: practiceUrl(slug, `/invitation#${link.token}`), role: inviteRole, expiresAt: link.expiresAt };
			invitations = [...invitations, { id: link.id ?? Date.now(), role: inviteRole, createdAt: new Date().toISOString(), expiresAt: link.expiresAt }];
		});

	const revoke = (inv: StaffInvitation) =>
		run(async () => {
			await api(`/api/staff/invitations/${inv.id}`, { method: 'DELETE' });
			invitations = invitations.filter((i) => i.id !== inv.id);
		});

	async function remove() {
		if (!removing) return;
		const id = removing.id;
		await run(async () => {
			await api(`/api/staff/${id}`, { method: 'DELETE' });
			staff = staff.filter((s) => s.id !== id);
			removing = null;
		});
	}

	const isProtected = (m: StaffMember) => m.role === 'owner' || m.id === auth.user?.id;
</script>

<OwnerOnly>
	<div class="flex flex-col gap-6">
		<div class="flex max-w-2xl flex-col gap-1">
			<h2 class="text-xl font-bold text-ink">{t('reglages.equipe.title')}</h2>
			<p class="text-slate-600">{t('reglages.equipe.intro')}</p>
		</div>
		<p role="status" class="-my-3 min-h-5 text-sm font-medium text-brand-800">{notice}</p>
		{#if actionError && !removing}<p role="alert" class="text-sm font-medium text-red-700">{actionError}</p>{/if}
		<LoadState {loading} {error} onretry={load} />

		{#if !loading && !error}
			<section class="card flex flex-col gap-2" aria-labelledby="t-members">
				<h3 id="t-members" class="font-semibold text-ink">{t('reglages.equipe.members')}</h3>
				<ul class="flex flex-col divide-y divide-slate-100">
					{#each staff as member (member.id)}
						<li class="flex flex-col gap-3 py-3">
							<div class="flex flex-wrap items-center gap-3">
								<div class="flex min-w-0 flex-1 basis-full flex-col sm:basis-auto">
									<span class="font-semibold text-ink"
										>{member.name}{#if member.id === auth.user?.id}<span class="ms-2 rounded-full bg-brand-50 px-2 py-0.5 text-xs font-semibold text-brand-800"
												>{t('reglages.equipe.you')}</span
											>{/if}</span
									>
									<span dir="ltr" class="truncate text-start text-sm text-slate-600">{member.email}</span>
								</div>
								{#if isProtected(member)}
									<span class="text-sm text-slate-700">{roleName(member.role)}</span>
								{:else}
									<select
										class="input w-auto"
										aria-label={t('reglages.equipe.roleOf', { name: member.name })}
										value={member.role}
										onchange={(e) => changeRole(member, e.currentTarget.value)}
									>
										{#each ROLES as role (role)}<option value={role}>{roleName(role)}</option>{/each}
									</select>
									<button
										type="button"
										class="btn-secondary min-h-10 px-3 py-1 text-sm"
										aria-label={t('reglages.equipe.resetOf', { name: member.name })}
										disabled={busy}
										onclick={() => resetLink(member)}>{t('reglages.equipe.reset')}</button
									>
									<button
										type="button"
										class="btn-secondary min-h-10 px-3 py-1 text-sm text-rose-700"
										aria-label={t('reglages.equipe.remove', { name: member.name })}
										onclick={() => {
											actionError = '';
											removing = member;
										}}>{t('reglages.equipe.removeShort')}</button
									>
								{/if}
							</div>
							{#if resets[member.id]}
								<div class="rounded-xl bg-slate-50 p-3">
									<CopyLink
										label={t('reglages.equipe.resetLink', { name: member.name })}
										url={resets[member.id].url}
										whatsappText={t('reglages.equipe.resetMessage', { name: member.name, url: resets[member.id].url })}
										note={`${t('kit.linkOnce')} ${t('kit.validUntil', { date: formatDateTime(resets[member.id].expiresAt) })}`}
									/>
								</div>
							{/if}
						</li>
					{/each}
				</ul>
			</section>

			<section class="card flex flex-col gap-3" aria-labelledby="t-invitations">
				<h3 id="t-invitations" class="font-semibold text-ink">{t('reglages.equipe.invitations')}</h3>
				{#if invitations.length === 0}
					<p class="text-sm text-slate-600">{t('reglages.equipe.invitationsNone')}</p>
				{:else}
					<ul class="flex flex-col divide-y divide-slate-100">
						{#each invitations as inv (inv.id)}
							<li class="flex items-center gap-3 py-2">
								<span class="flex-1 text-slate-700"
									>{t('reglages.equipe.invitationLine', { role: roleName(inv.role), date: formatDate(inv.expiresAt) })}</span
								>
								<button
									type="button"
									class="min-h-10 px-2 text-sm font-semibold text-rose-700 hover:underline"
									aria-label={t('reglages.equipe.revoke', { role: roleName(inv.role), date: formatDate(inv.createdAt) })}
									onclick={() => revoke(inv)}>{t('reglages.equipe.revokeShort')}</button
								>
							</li>
						{/each}
					</ul>
				{/if}
			</section>

			<section class="card flex flex-col gap-3" aria-labelledby="t-invite">
				<h3 id="t-invite" class="font-semibold text-ink">{t('reglages.equipe.invite')}</h3>
				<p class="text-sm text-slate-600">{t('reglages.equipe.inviteText')}</p>
				<div class="flex flex-wrap items-end gap-3">
					<label class="label">
						{t('reglages.equipe.inviteRole')}
						<select class="input w-auto" bind:value={inviteRole}>
							{#each ROLES as role (role)}<option value={role}>{roleName(role)}</option>{/each}
						</select>
					</label>
					<button type="button" class="btn-primary" disabled={busy} onclick={invite}>{t('reglages.equipe.inviteCreate')}</button>
				</div>
				{#if invited}
					<div class="rounded-xl bg-brand-50 p-3">
						<CopyLink
							label={t('reglages.equipe.inviteLink', { role: roleName(invited.role) })}
							url={invited.url}
							whatsappText={t('reglages.equipe.inviteMessage', { practice: practiceName, url: invited.url })}
							note={`${t('kit.linkOnce')} ${t('kit.validUntil', { date: formatDateTime(invited.expiresAt) })}`}
						/>
					</div>
				{/if}
			</section>
		{/if}
	</div>

	<ConfirmDialog
		open={!!removing}
		title={removing ? t('reglages.equipe.removeTitle', { name: removing.name }) : ''}
		message={t('reglages.equipe.removeMessage')}
		confirmLabel={t('reglages.equipe.removeConfirm')}
		danger
		{busy}
		error={actionError}
		onconfirm={remove}
		oncancel={() => (removing = null)}
	/>
</OwnerOnly>
