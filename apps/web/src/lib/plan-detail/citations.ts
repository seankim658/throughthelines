/**
 * Inline-citation resolution for plan prose.
 *
 * Curators embed references in prose as `[CODE]` tokens (e.g. `[AAR]`), where
 * CODE matches a `source_code` on one of the plan's court_citations or sources.
 * This module turns a prose string into an ordered list of text / citation segments
 * a component can render, and assigns each cited code a display number.
 */

import type { Plan } from '$lib/plan-index/types';

// Must stay in sync with the pipeline's SOURCE_CODE_PATTERN
const CITATION_TOKEN_PATTERN = /\[([A-Z0-9][A-Z0-9-]*)\]/;

export type ProseSegment =
	| { kind: 'text'; text: string }
	| { kind: 'citation'; code: string; number: number };

interface CitationMatch {
	code: string;
	start: number;
	end: number;
}

/**
 * DOM id for a reference's anchor, namespaced by plan.
 */
export function citationAnchorId(planId: string, code: string): string {
	return `ref-${planId}-${code}`;
}

/**
 * All non-null source_codes across a plan's references.
 */
function definedSourceCodes(plan: Plan): Set<string> {
	const codes = new Set<string>();
	for (const ref of [...plan.court_citations, ...plan.sources]) {
		if (ref.source_code !== null) {
			codes.add(ref.source_code);
		}
	}
	return codes;
}

/**
 * Every well-formed [CODE] token in a string, with positions, in order.
 */
function scanCitationTokens(prose: string): CitationMatch[] {
	const matches: CitationMatch[] = [];
	const re = new RegExp(CITATION_TOKEN_PATTERN.source, 'g');
	let match = re.exec(prose);
	while (match !== null) {
		matches.push({
			code: match[1],
			start: match.index,
			end: match.index + match[0].length
		});
		match = re.exec(prose);
	}
	return matches;
}

export function citationCodesInOrder(prose: string): string[] {
	return scanCitationTokens(prose).map((match) => match.code);
}

/**
 * Assign each cited, resolvable code a 1-based display number in the order it first
 * appears across the prose fields (footnote style).
 */
export function buildCitationNumbers(plan: Plan): Map<string, number> {
	const defined = definedSourceCodes(plan);
	const numbers = new Map<string, number>();
	const orderedProse = [plan.origin_details, plan.struck_down_details, plan.notes];
	for (const prose of orderedProse) {
		for (const { code } of scanCitationTokens(prose)) {
			if (defined.has(code) && !numbers.has(code)) {
				numbers.set(code, numbers.size + 1);
			}
		}
	}
	return numbers;
}

/**
 * Split one prose string into ordered text / citation segments.
 */
export function tokenizeProse(prose: string, numbers: Map<string, number>): ProseSegment[] {
	const segments: ProseSegment[] = [];
	let cursor = 0;
	for (const match of scanCitationTokens(prose)) {
		const number = numbers.get(match.code);
		if (number === undefined) {
			continue;
		}
		if (match.start > cursor) {
			segments.push({ kind: 'text', text: prose.slice(cursor, match.start) });
		}
		segments.push({ kind: 'citation', code: match.code, number });
		cursor = match.end;
	}
	if (cursor < prose.length) {
		segments.push({ kind: 'text', text: prose.slice(cursor) });
	}
	return segments;
}
