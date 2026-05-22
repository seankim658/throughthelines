/**
 * Typescript types mirroring the manifest.json emitted by the Python pipeline.
 *
 * Source of truth: pipeline/src/pipeline/manifest/build.py
 *
 * These types have to updated if the pipeline schema_version changes.
 */

/** A reference to one artifact on disk. */
export interface ArtifactRef {
	// Path relative to the manifest's url_prefix
	path: string;
	size_bytes: number;
	sha256: string;
}

/** Build identity. Populated by the pipeline at manifest-build time. */
export interface BuildInfo {
	version: string;
	git_sha: string | null;
	built_at: string;
	url_prefix: string | null;
}

/** The Congress range covered by this build. */
export interface ScopeInfo {
	congress_start: number;
	congress_end: number;
	planned: string[];
}

/** How the block-to-district assignment was sourced for a Congress. */
export type BlockSource =
	| {
			type: 'bef';
			bef_url: string;
			bef_landing_url: string;
			block_vintage: 'v2000' | 'v2010' | 'v2020';
	  }
	| {
			type: 'lewis_spatial_join';
			lewis_path: string;
			lewis_landing_url: string;
			block_vintage: 'v2000' | 'v2010' | 'v2020';
	  }
	| { type: 'unsourced' };

/** One Congress's provenance entry, lifted from the block-lookup file into the manifest. */
export interface CongressEntry {
	congress: number;
	plan_id: string;
	block_source: BlockSource;
}

/** Per-chamber artifacts and provenance for one state. */
export interface ChamberSection {
	artifacts: {
		block_lookup: ArtifactRef;
		tiles: ArtifactRef;
	};
	congresses: CongressEntry[];
}

/** Per-state section. Keyed by chamber code. */
export interface StateSection {
	code: string;
	name: string;
	fips: string;
	chambers: Record<string, ChamberSection>;
}

/** Display-only provenance for the Lewis polygon source. */
export interface LewisSource {
	commit_sha: string;
	commit_url: string;
	homepage_url: string;
}

/** Display-only provenance for the Voteview member source. */
export interface VoteviewSource {
	landing_url: string;
}

export interface SourcesSection {
	lewis: LewisSource;
	voteview: VoteviewSource;
}

/** Top-level manifest. */
export interface Manifest {
	schema_version: 1;
	build: BuildInfo;
	scope: ScopeInfo;
	artifacts: {
		plan_index: ArtifactRef;
		members: ArtifactRef;
		basemap: ArtifactRef;
	};
	sources: SourcesSection;
	states: Record<string, StateSection>;
}
