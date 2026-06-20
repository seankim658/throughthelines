<script lang="ts">
	import type { LookupState } from './types';

	let {
		lookup,
		stateName
	}: {
		lookup: LookupState;
		stateName: string;
	} = $props();
</script>

<div class="min-h-6 text-sm" aria-live="polite">
	{#if lookup.status === 'geocoding'}
		<p class="text-ink-secondary">Looking up…</p>
	{:else if lookup.status === 'geocode_error'}
		<p class="text-feedback-error">{lookup.message}</p>
	{:else if lookup.status === 'no_match'}
		<p class="text-feedback-error">
			The Census Geocoder couldn't find that address. Try including a city, state, and ZIP.
		</p>
	{:else if lookup.status === 'out_of_state'}
		<p class="text-feedback-warning">
			That address is in {lookup.state}, but this page covers {stateName}. Matched:
			{lookup.matchedAddress}
		</p>
	{:else if lookup.status === 'not_in_block_lookup'}
		<p class="text-feedback-error">
			We matched the address but its Census block isn't in our dataset. This is unexpected — please
			report it. Matched: {lookup.matchedAddress} (GEOID {lookup.geoid})
		</p>
	{:else if lookup.status === 'ready'}
		<p class="text-ink-secondary">Matched: {lookup.matchedAddress}</p>
	{/if}
</div>
