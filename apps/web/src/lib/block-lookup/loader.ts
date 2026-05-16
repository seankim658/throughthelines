import { resolveArtifactUrl } from '$lib/manifest/loader';
import type { Manifest } from '$lib/manifest/types';
import type { BlockLookup } from './types';

const _BLOCK_LOOKUP_SCHEMA_VERSION = 1;
const _CHAMBER = 'congressional';

/**
 * Fetch and parse block_lookup_{STATE}.json for the given state code.
 */
export async function loadBlockLookup(
	manifest: Manifest,
	state: string,
	fetch: typeof globalThis.fetch = globalThis.fetch
): Promise<BlockLookup> {
	const stateSection = manifest.states[state];
	if (stateSection === undefined) {
		throw new Error(`block_lookup: state ${state} is not in this build's manifest`);
	}

	const chamberSection = stateSection.chambers[_CHAMBER];
	if (chamberSection === undefined) {
		throw new Error(
			`block_lookup: state ${state} has no ${_CHAMBER} chamber section in the manifest`
		);
	}

	const url = resolveArtifactUrl(manifest, chamberSection.artifacts.block_lookup);
	const response = await fetch(url);
	if (!response.ok) {
		throw new Error(
			`failed to fetch block_lookup at ${url}: ${response.status} ${response.statusText}`
		);
	}

	const blockLookup = (await response.json()) as BlockLookup;
	if (blockLookup.schema_version !== _BLOCK_LOOKUP_SCHEMA_VERSION) {
		throw new Error(
			`block_lookup schema_version ${blockLookup.schema_version} is not supported by this build`
		);
	}

	return blockLookup;
}
