<script lang="ts">
	import type { Plan } from '$lib/plan-index/types';
	import type { MemberRecord } from '$lib/members/types';
	import type { BlockSource, SourcesSection } from '$lib/manifest/types';
	import { formatCongressYears } from '$lib/congress/congress-years';
	import {
		formatCurationStatus,
		formatOrigin,
		formatPlanDate,
		formatStruckDown,
		isRealDate,
		isRealPlanRef,
		isRealProse,
		type BadgeTone
	} from './format';
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
	// TODO : Probably extract this to the pipeline
	function formatDelimitedProvider(provider: string): string {
		switch (provider) {
			case 'census':
				return 'Census Block Equivalency File';
			case 'ncga':
				return 'NC General Assembly block assignment file';
			default:
				return 'block assignment file';
		}
	}

	let {
		plan,
		congress,
		district,
		members,
		blockSource,
		sources
	}: {
		plan: Plan | null;
		congress: number;
		district: number | null;
		members: MemberRecord[];
		blockSource: BlockSource;
		sources: SourcesSection;
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
	{@const dateParts = [
		isRealDate(plan.effective_date) ? `Effective ${formatPlanDate(plan.effective_date)}` : null,
		isRealDate(plan.enacted_date) ? `Enacted ${formatPlanDate(plan.enacted_date)}` : null
	].filter((p): p is string => p !== null)}
	{@const refParts = [
		isRealPlanRef(plan.predecessor) ? `Predecessor: ${plan.predecessor}` : null,
		isRealPlanRef(plan.superseded_by) ? `Superseded by: ${plan.superseded_by}` : null
	].filter((p): p is string => p !== null)}
	<section>
		<header class="flex items-start justify-between gap-4">
			<div>
				<h2 class="text-ink-primary text-2xl">{plan.plan_id}</h2>
				<p class="text-ink-secondary mt-1 text-sm">
					{congress}th Congress · {formatCongressYears(congress)}
				</p>
				{#if dateParts.length > 0}
					<p class="text-ink-secondary mt-1 text-sm">{dateParts.join(' · ')}</p>
				{/if}
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

		{#if refParts.length > 0}
			<p class="text-ink-secondary mt-3 text-sm">{refParts.join(' · ')}</p>
		{/if}

		{#if isRealProse(plan.origin_details)}
			<div class="mt-6">
				<h3 class="text-ink-primary text-sm font-medium">About this plan</h3>
				<p class="text-ink-secondary mt-2 text-sm whitespace-pre-line">{plan.origin_details}</p>
			</div>
		{/if}

		{#if isRealProse(plan.struck_down_details) || plan.struck_down_districts.length > 0}
			<div class="mt-6">
				<h3 class="text-ink-primary text-sm font-medium">Strikedown</h3>
				{#if isRealProse(plan.struck_down_details)}
					<p class="text-ink-secondary mt-2 text-sm whitespace-pre-line">
						{plan.struck_down_details}
					</p>
				{/if}
				{#if plan.struck_down_districts.length > 0}
					<p class="text-ink-secondary mt-2 text-sm">
						Affected district{plan.struck_down_districts.length === 1 ? '' : 's'}:
						{plan.struck_down_districts.join(', ')}
					</p>
				{/if}
			</div>
		{/if}

		<div class="mt-6">
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

		{#if plan.court_citations.length > 0}
			<div class="mt-6">
				<h3 class="text-ink-primary text-sm font-medium">
					Court citation{plan.court_citations.length === 1 ? '' : 's'}
				</h3>
				<ul class="mt-2 flex flex-col gap-2">
					{#each plan.court_citations as cite (cite.citation)}
						<li class="text-ink-secondary text-sm">
							<a
								href={cite.url}
								target="_blank"
								rel="noopener noreferrer"
								class="text-accent underline"
							>
								{cite.case}
							</a>
							: {cite.citation}
							<span class="text-ink-muted">· {cite.role}</span>
							{#if cite.archived_url}
								·
								<a
									href={cite.archived_url}
									target="_blank"
									rel="noopener noreferrer"
									class="text-ink-muted underline"
								>
									archived
								</a>
							{/if}
						</li>
					{/each}
				</ul>
			</div>
		{/if}

		{#if isRealProse(plan.notes)}
			<div class="mt-6">
				<h3 class="text-ink-primary text-sm font-medium">Notes</h3>
				<p class="text-ink-secondary mt-2 text-sm whitespace-pre-line">{plan.notes}</p>
			</div>
		{/if}

		{#if plan.sources.length > 0}
			<div class="mt-6">
				<h3 class="text-ink-primary text-sm font-medium">
					Source{plan.sources.length === 1 ? '' : 's'}
				</h3>
				<ul class="mt-2 flex flex-col gap-1">
					{#each plan.sources as source (source.url)}
						<li class="text-ink-secondary text-sm">
							<a
								href={source.url}
								target="_blank"
								rel="noopener noreferrer"
								class="text-accent break-all underline"
							>
								{source.url}
							</a>
							<span class="text-ink-muted ml-1">
								· accessed {formatPlanDate(source.accessed)}
							</span>
							{#if source.archived}
								·
								<a
									href={source.archived}
									target="_blank"
									rel="noopener noreferrer"
									class="text-ink-muted underline"
								>
									archived
								</a>
							{/if}
						</li>
					{/each}
				</ul>
			</div>
		{/if}

		<footer class="text-ink-muted mt-6 space-y-1 text-xs">
			<h2>Data</h2>
			<p>
				District boundaries:
				<a
					href={sources.lewis.homepage_url}
					target="_blank"
					rel="noopener noreferrer"
					class="text-accent underline"
				>
					Jeffrey B. Lewis
				</a>
			</p>
			<p>
				Member data:
				<a
					href={sources.voteview.landing_url}
					target="_blank"
					rel="noopener noreferrer"
					class="text-accent underline"
				>
					Voteview
				</a>
			</p>
			<p>
				{#if blockSource.type === 'delimited_assignment'}
					Address lookup source data:
					<a
						href={blockSource.upstream_landing_url}
						target="_blank"
						rel="noopener noreferrer"
						class="text-accent underline"
					>
						{formatDelimitedProvider(blockSource.provider)}
					</a>
					· {formatVintage(blockSource.block_vintage)} blocks
				{:else if blockSource.type === 'polygon_join'}
					Address lookup source data: spatial join against
					<a
						href={blockSource.upstream_landing_url}
						target="_blank"
						rel="noopener noreferrer"
						class="text-accent underline"
					>
						<!-- NOTE : Will have to remove this hardcode later -->
						Lewis plan polygons
					</a>
					· {formatVintage(blockSource.block_vintage)} blocks
				{:else}
					Address lookup not available for this Congress.
				{/if}
			</p>
			{#if plan.curation_last_reviewed !== null}
				<p>Last reviewed {formatPlanDate(plan.curation_last_reviewed)}</p>
			{/if}
		</footer>
	</section>
{/if}
