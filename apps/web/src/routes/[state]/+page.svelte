<script lang="ts">
	import type { PageData } from './$types';
	import { geocode } from '$lib/geocoder/client';
	import { buildTimeline } from '$lib/timeline/build';
	import CongressStrip from '$lib/congress-strip/CongressStrip.svelte';
	import PlanDetail from '$lib/plan-detail/PlanDetail.svelte';
	import LookupStatus from '$lib/lookup/LookupStatus.svelte';
	import AddressForm from '$lib/lookup/AddressForm.svelte';
	import type { BlockSource } from '$lib/manifest/types';
	import type { LookupState } from '$lib/lookup/types';

	let { data }: { data: PageData } = $props();

	let lookup = $state<LookupState>({ status: 'idle' });
	// Component is remounted on stateCode change by {#key} in [state]/+layout.svelte.
	// svelte-ignore state_referenced_locally
	let activeCongress = $state(data.coverage === 'covered' ? data.blockLookup.congress_end : 0);

	const congresses = $derived(data.coverage === 'covered' ? data.blockLookup.congresses : []);

	const districts = $derived.by(() => {
		if (lookup.status !== 'ready') return null;
		const result: Record<number, number | null> = {};
		for (const row of lookup.rows) {
			result[row.congress] = row.district;
		}
		return result;
	});

	const activeCongressEntry = $derived(
		data.coverage === 'covered'
			? (data.blockLookup.congresses.find((c) => c.congress === activeCongress) ?? null)
			: null
	);

	const activePlan = $derived.by(() => {
		if (data.coverage !== 'covered') return null;
		if (activeCongressEntry === null) return null;
		return data.planIndex.plans[data.stateCode]?.[activeCongressEntry.plan_id] ?? null;
	});

	const activeDistrict = $derived(districts === null ? null : (districts[activeCongress] ?? null));

	const activeMembers = $derived.by(() => {
		if (data.coverage !== 'covered') return [];
		if (activeDistrict === null) return [];
		return data.members[data.stateCode]?.[String(activeCongress)]?.[String(activeDistrict)] ?? [];
	});

	const activeBlockSource: BlockSource = $derived(
		activeCongressEntry?.block_source ?? { type: 'unsourced' }
	);

	async function handleSubmit(trimmed: string) {
		if (data.coverage !== 'covered') return;

		lookup = { status: 'geocoding' };
		const geo = await geocode(trimmed);

		if (geo.status === 'error') {
			lookup = { status: 'geocode_error', message: geo.message };
			return;
		}
		if (geo.status === 'no_match') {
			lookup = { status: 'no_match' };
			return;
		}

		if (geo.state !== data.stateCode) {
			lookup = {
				status: 'out_of_state',
				state: geo.state,
				matchedAddress: geo.matchedAddress
			};
			return;
		}

		const timeline = buildTimeline(geo.geoid, data.blockLookup, data.planIndex, data.members);

		if (timeline.status === 'block_not_in_state') {
			lookup = {
				status: 'not_in_block_lookup',
				geoid: geo.geoid,
				matchedAddress: geo.matchedAddress
			};
			return;
		}

		lookup = {
			status: 'ready',
			matchedAddress: geo.matchedAddress,
			geoid: geo.geoid,
			rows: timeline.rows
		};
	}
</script>

<svelte:head>
	<title>{data.stateName} — Through the Lines</title>
</svelte:head>

{#if data.coverage === 'planned'}
	<div class="mx-auto max-w-3xl space-y-4 p-8">
		<h1 class="text-4xl">{data.stateName}</h1>
		<p>
			{data.stateName} is planned for V1 of Through the Lines. The current release covers North Carolina;
			Pennsylvania and Texas are next on the roadmap.
		</p>
		<p><a href="/" class="text-accent underline">Back to the home page</a></p>
	</div>
{:else if data.coverage === 'not_yet'}
	<div class="mx-auto max-w-3xl space-y-4 p-8">
		<h1 class="text-4xl">{data.stateName}</h1>
		<p>
			{data.stateName} isn't yet covered by Through the Lines. The current release covers North Carolina;
			Pennsylvania and Texas are planned for V1.
		</p>
		<p><a href="/" class="text-accent underline">Back to the home page</a></p>
	</div>
{:else}
	<div class="mx-auto max-w-5xl space-y-1 p-8 pt-4">
		<h1 class="text-4xl pb-4">{data.stateName}</h1>

		<AddressForm
			disabled={lookup.status === 'geocoding'}
			placeholder="123 Main St, {data.stateName}"
			onSubmit={handleSubmit}
			onClear={() => (lookup = { status: 'idle' })}
		/>

		<LookupStatus {lookup} stateName={data.stateName} />

		<div class="grid grid-cols-[1fr_240px] gap-4">
			<div
				class="bg-surface-sunken text-ink-muted flex h-[520px] items-center justify-center rounded"
			>
				Map placeholder
			</div>
			<div
				class="h-[520px] overflow-y-auto pr-1 [scrollbar-color:var(--color-ink-muted)_transparent] [scrollbar-width:thin]"
			>
				<CongressStrip {congresses} bind:activeCongress {districts} />
			</div>
			<div class="col-span-2">
				<PlanDetail
					plan={activePlan}
					congress={activeCongress}
					district={activeDistrict}
					members={activeMembers}
					blockSource={activeBlockSource}
				/>
			</div>
		</div>
	</div>
{/if}
