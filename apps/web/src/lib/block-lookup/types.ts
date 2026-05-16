/**
 * Typescript types mirroring the block_lookup_{STATE}.json emitted by the Python pipeline.
 *
 * Source of truth: pipeline/src/pipeline/blocks/build.py
 */

import type { CongressEntry } from '$lib/manifest/types';

/**
 * One per-Congress slot in a block's history.
 */
export type DistrictAssignment = number | null;

/**
 * One unique history pattern.
 */
export type DistrictHistory = DistrictAssignment[];

/**
 * Top-level shape of a block_lookup_{STATE}.json.
 *
 * Lookup pattern: blocks[geoid] -> integer index -> histories[index]
 */
export interface BlockLookup {
	schema_version: 1;
	state: string;
	chamber: 'congressional';
	congress_start: number;
	congress_end: number;
	congresses: CongressEntry[];
	histories: DistrictHistory[];
	// 2020 Census block GEOID → index into `histories`
	blocks: Record<string, number>;
}
