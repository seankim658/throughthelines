/**
 * Typescript types mirroring the member.json emitted by the data pipeline.
 *
 * Source of truth: pipeline/src/pipeline/members/build.py
 */

/**
 * Voteview party code translated to a single-letter string.
 *
 * Mapping:
 *   "100" -> "D"   Democratic
 *   "200" -> "R"   Republican
 *   "328" -> "I"   Independent
 */
export type Party = 'D' | 'R' | 'I' | '?';

/**
 * One House member's appearance in a single Congress.
 *
 * A district may have more than one MemberRecord in a single
 * Congress (death, resignation, expulsion, special election).
 */
export interface MemberRecord {
	name: string;
	party: Party;
	icpsr: number;
	bioguide_id: string;
	born: number | null;
	died: number | null;
	nominate_dim1: number | null;
	nominate_dim2: number | null;
	nokken_poole_dim1: number | null;
	nokken_poole_dim2: number | null;
}

/**
 * Members for a single (state, congress, district).
 */
export type MembersByDistrict = Record<string, MemberRecord[]>;

/**
 * Keyed by congress number as a string.
 */
export type MembersByCongress = Record<string, MembersByDistrict>;

/**
 * Keyed by state code.
 */
export type MembersByState = Record<string, MembersByCongress>;

/**
 * Top-level shape of members.json.
 */
export type MembersIndex = MembersByState;
