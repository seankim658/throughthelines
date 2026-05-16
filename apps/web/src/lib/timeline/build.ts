import type { BlockLookup } from '$lib/block-lookup/types';
import type { MembersIndex } from '$lib/members/types';
import type { PlanIndex } from '$lib/plan-index/types';
import type { TimelineResult, TimelineRow } from './types';

/**
 * Given a 2020 block GEOID and three lookup artifacts, produce
 * a row-per-Congress timeline.
 *
 * The artifacts should already be in memory by the time this
 * function runs.
 *
 * Defensive behaviour:
 *   GEOID not in blockLookup.blocks            -> `block_not_in_state`
 *   history length != congresses length        -> warn + truncate to shorter
 *   plan_id not in plan_index for this state   -> row's plan is null + warn
 *   district is null                           -> row exists, members is []
 *   no member records for (state, cong, dist)  -> row's members is []
 */
export function buildTimeline(
	geoid: string,
	blockLookup: BlockLookup,
	planIndex: PlanIndex,
	members: MembersIndex
): TimelineResult {
	const state = blockLookup.state;
	const historyIndex = blockLookup.blocks[geoid];

	if (historyIndex === undefined) {
		return { status: 'block_not_in_state', geoid, state };
	}

	const history = blockLookup.histories[historyIndex];
	const congresses = blockLookup.congresses;

	if (history.length !== congresses.length) {
		console.warn(
			`buildTimeline: history length ${history.length} does not match ` +
				`congresses length ${congresses.length} for state ${state}; truncating`
		);
	}

	const rowCount = Math.min(history.length, congresses.length);
	const plansForState = planIndex.plans[state] ?? {};
	const membersForState = members[state] ?? {};
	const rows: TimelineRow[] = [];

	for (let i = 0; i < rowCount; i++) {
		const congressEntry = congresses[i];
		const district = history[i];
		const congress = congressEntry.congress;
		const planId = congressEntry.plan_id;

		const plan = plansForState[planId] ?? null;
		if (plan === null) {
			console.warn(
				`buildTimeline: plan_id ${planId} (state ${state}, Congress ${congress}) ` +
					`not found in plan_index`
			);
		}

		const memberRecords =
			district === null ? [] : (membersForState[String(congress)]?.[String(district)] ?? []);

		rows.push({
			congress,
			district,
			planId,
			plan,
			blockSource: congressEntry.block_source,
			members: memberRecords
		});
	}

	return { status: 'ok', state, geoid, rows };
}
