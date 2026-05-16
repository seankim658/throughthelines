<script lang="ts">
	import type { Plan } from '$lib/plan-index/types';
	import type { MemberRecord } from '$lib/members/types';
	import type { BlockSource } from '$lib/manifest/types';
	import { formatCongressYears } from '$lib/congress/congress-years';
	import { formatCurationStatus, formatOrigin, formatStruckDown, type BadgeTone } from './format';
	import type { Party } from '$lib/members/types';

	const partyClasses: Record<Party, string> = {
		D: 'bg-party-d text-ink-inverse',
		R: 'bg-party-r text-ink-inverse',
		I: 'bg-party-i text-ink-inverse',
		'?': 'bg-surface-sunken text-ink-secondary'
	};

	function partyClass(party: Party): string {
		return partyClasses[party];
	}
	function formatVintage(vintage: 'v2000' | 'v2010' | 'v2020'): string {
		return vintage.slice(1);
	}

	let {
		plan,
		congress,
		district,
		members,
		blockSource
	}: {
		plan: Plan | null;
		congress: number;
		district: number | null;
		members: MemberRecord[];
		blockSource: BlockSource;
	} = $props();

	const toneClasses: Record<BadgeTone, string> = {
		normal: 'border-line-default text-ink-secondary',
		pending: 'border-line-subtle text-ink-muted italic',
		unknown: 'border-line-subtle text-ink-muted',
		warning: 'border-feedback-warning text-feedback-warning',
		success: 'border-feedback-success text-feedback-success'
	};
</script>

{#if plan === null}
	<section class="text-ink-secondary">
		<h2 class="text-ink-primary text-xl">Plan record not found</h2>
		<p class="mt-2">
			The plan record for the {congress}th Congress isn't in our dataset. This is a data integrity
			issue; please report it.
		</p>
	</section>
{:else}
	{@const origin = formatOrigin(plan.origin)}
	{@const struckDown = formatStruckDown(plan.struck_down)}
	{@const curation = formatCurationStatus(plan.curation_status)}
	<section>
		<header class="flex items-start justify-between gap-4">
			<div>
				<h2 class="text-ink-primary text-2xl">{plan.plan_id}</h2>
				<p class="text-ink-secondary mt-1 text-sm">
					{congress}th Congress · {formatCongressYears(congress)}
				</p>
			</div>
			<span
				class="rounded-full border px-2 py-0.5 text-xs whitespace-nowrap {toneClasses[
					curation.tone
				]}"
			>
				{curation.label}
			</span>
		</header>

		<div class="mt-4 flex flex-wrap gap-2">
			<span class="rounded-full border px-2 py-0.5 text-xs {toneClasses[origin.tone]}">
				{origin.label}
			</span>
			<span class="rounded-full border px-2 py-0.5 text-xs {toneClasses[struckDown.tone]}">
				{struckDown.label}
			</span>
		</div>

		<div class="border-line-subtle mt-6 border-t pt-4">
			<h3 class="text-ink-primary text-sm font-medium">
				Representative{members.length === 1 ? '' : 's'}
			</h3>
			{#if district === null}
				<p class="text-ink-muted mt-2 text-sm">
					Look up an address to see who represented this district.
				</p>
			{:else if members.length === 0}
				<p class="text-ink-muted mt-2 text-sm">
					No member record on file for District {district} in the {congress}th Congress.
				</p>
			{:else}
				<p class="text-ink-secondary mt-2 text-sm">
					District {district}
				</p>
				<ul class="mt-2 flex flex-col gap-2">
					{#each members as member (member.icpsr)}
						<li class="flex items-baseline gap-2">
							<span
								class="inline-block rounded-sm px-1.5 py-0.5 text-xs font-medium {partyClass(
									member.party
								)}"
							>
								{member.party}
							</span>
							<span class="text-ink-primary">{member.name}</span>
							<span class="text-ink-muted text-xs">ICPSR {member.icpsr}</span>
						</li>
					{/each}
				</ul>
				{#if members.length > 1}
					<p class="text-ink-muted mt-2 text-xs italic">
						This Congress had a mid-term transition (death, resignation, or special election).
					</p>
				{/if}
			{/if}
		</div>

		<footer class="border-line-subtle text-ink-muted mt-6 border-t pt-3 text-xs">
			{#if blockSource.type === 'bef'}
				Source:
				<a
					href={blockSource.bef_url}
					target="_blank"
					rel="noopener noreferrer"
					class="text-accent underline"
				>
					Census Block Equivalency File
				</a>
				· {formatVintage(blockSource.block_vintage)} blocks
			{:else if blockSource.type === 'lewis_spatial_join'}
				Source: spatial join against Lewis plan polygons · {formatVintage(
					blockSource.block_vintage
				)} blocks
			{:else}
				Source: not recorded
			{/if}
		</footer>
	</section>
{/if}
