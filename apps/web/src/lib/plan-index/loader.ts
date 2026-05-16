import { resolveArtifactUrl } from '$lib/manifest/loader';
import type { Manifest } from '$lib/manifest/types';
import type { PlanIndex } from './types';

const _PLAN_INDEX_SCHEMA_VERSION = 1;

export async function loadPlanIndex(
	manifest: Manifest,
	fetch: typeof globalThis.fetch = globalThis.fetch
): Promise<PlanIndex> {
	const url = resolveArtifactUrl(manifest, manifest.artifacts.plan_index);
	const response = await fetch(url);
	if (!response.ok) {
		throw new Error(
			`failed to fetch plan_index at ${url}: ${response.status} ${response.statusText}`
		);
	}
	const planIndex = (await response.json()) as PlanIndex;
	if (planIndex.schema_version !== _PLAN_INDEX_SCHEMA_VERSION) {
		throw new Error(
			`plan_index schema_version ${planIndex.schema_version} is not supported by this build`
		);
	}
	return planIndex;
}
