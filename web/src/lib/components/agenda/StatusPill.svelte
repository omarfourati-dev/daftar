<script lang="ts">
	/** Small coloured label of an appointment status (colours of design section 6). */
	import { statusLabel } from '../../agenda/format';
	import { appointmentStatusClass, type AppointmentStatus } from '../../status';

	let { status, class: extra = '' }: { status: AppointmentStatus; class?: string } = $props();
</script>

<span class="inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-semibold {appointmentStatusClass(status)} {extra}"
	>{statusLabel(status)}</span
>
