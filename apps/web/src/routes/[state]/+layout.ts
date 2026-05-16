/**
 * State-route layout loader.
 *
 * Validates the [state] URL param and classifies coverage. For
 * covered states, parallel-loads block lookup, plan index, and
 * members so the page can render the lookup tool.
 */

import { error } from '@sveltejs/kit';
import { loadBlockLookup } from '$lib/block-lookup/loader';
import { loadMembers } from '$lib/members/loader';
import { loadPlanIndex } from '$lib/plan-index/loader';
import { classifyCoverage, isRealStateCode, STATE_NAMES } from '$lib/states/states';
import type { LayoutLoad } from './$types';

export const load: LayoutLoad = async ({ params, parent, fetch }) => {
	const stateCode = params.state.toUpperCase();

	if (!isRealStateCode(stateCode)) {
		error(404, `Unknown state code: ${params.state}`);
	}

	const { manifest } = await parent();
	const coverage = classifyCoverage(stateCode, manifest);
	const stateName = STATE_NAMES[stateCode];

	if (coverage !== 'covered') {
		return { coverage, stateCode, stateName };
	}

	const [blockLookup, planIndex, members] = await Promise.all([
		loadBlockLookup(manifest, stateCode, fetch),
		loadPlanIndex(manifest, fetch),
		loadMembers(manifest, fetch)
	]);

	return {
		coverage,
		stateCode,
		stateName,
		blockLookup,
		planIndex,
		members
	};
};
