<script lang="ts">
	/** Test harness: the hours editor with a bound value that tests can read. */
	import HoursEditor from './HoursEditor.svelte';
	import { defaultWeeklyHours } from '../hours';

	let value = $state(defaultWeeklyHours());
</script>

<HoursEditor bind:value />
<output data-testid="value">{JSON.stringify(value)}</output>
