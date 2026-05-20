/**
 * Centralized accessors for covering messaging.
 *
 * The canonical surface for "what's covered" is the /data page, which
 * renders live lists from the manifest. This module provides the set
 * of derived-data accessors that the page (and the site footer) uses.
 */

import type { Manifest } from '$lib/manifest/types';
import { STATE_NAMES } from '$lib/states/states';

export function getVersionLabel(manifest: Manifest): string {
	return `v${manifest.build.version}`;
}

export function getCoveredStateCodes(manifest: Manifest): string[] {
	return Object.keys(manifest.states).sort((a, b) => STATE_NAMES[a].localeCompare(STATE_NAMES[b]));
}

export function getCoveredStateNames(manifest: Manifest): string[] {
	return getCoveredStateCodes(manifest).map((code) => STATE_NAMES[code]);
}

export function getPlannedStateCodes(manifest: Manifest): string[] {
	return manifest.scope.planned
		.filter((code) => manifest.states[code] === undefined)
		.sort((a, b) => STATE_NAMES[a].localeCompare(STATE_NAMES[b]));
}

export function getPlannedStateNames(manifest: Manifest): string[] {
	return getPlannedStateCodes(manifest).map((code) => STATE_NAMES[code]);
}

export function joinWithAnd(items: readonly string[]): string {
	if (items.length === 0) return '';
	if (items.length === 1) return items[0];
	if (items.length === 2) return `${items[0]} and ${items[1]}`;
	const init = items.slice(0, -1).join(', ');
	const last = items[items.length - 1];
	return `${init}, and ${last}`;
}
