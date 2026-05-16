/**
 * Timeline shapes: the row-per-Congress structure produced by buildTimeline().
 */

import type { BlockSource } from '$lib/manifest/types';
import type { MemberRecord } from '$lib/members/types';
import type { Plan } from '$lib/plan-index/types';

/** One row in an address's congressional-district timeline. */
export interface TimelineRow {
	congress: number;
	/** District number, or null if the block was unassigned for this Congress. */
	district: number | null;
	/** The plan_id from block_lookup. Always present even when `plan` is null. */
	planId: string;
	/** Plan record from plan_index, or null if not found. */
	plan: Plan | null;
	/** Provenance for how this Congress's block-to-district was sourced. */
	blockSource: BlockSource;
	/**
	 * Voteview members for (state, congress, district). May have more than
	 * one entry in special circumstances (death, resignation, special election,
	 * etc.). Empty when district is null or no record exists.
	 */
	members: MemberRecord[];
}

/**
 * Outcome of buildTimeline().
 */
export type TimelineResult =
	| { status: 'ok'; state: string; geoid: string; rows: TimelineRow[] }
	| { status: 'block_not_in_state'; geoid: string; state: string };
