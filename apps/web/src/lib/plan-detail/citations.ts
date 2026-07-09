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

export type RefKind = 'court' | 'source';

export type ProseSegment =
	| { kind: 'text'; text: string }
	| { kind: 'citation'; refKind: 'source'; code: string; number: number }
	| { kind: 'citation'; refKind: 'court'; code: string };

type CitationSegment = Extract<ProseSegment, { kind: 'citation' }>;

interface CitationMatch {
	code: string;
	start: number;
	end: number;
}

export interface PlanCitations {
	sourceNumbers: Map<string, number>;
	kinds: Map<string, RefKind>;
	cited: Set<string>;
}

/**
 * DOM id for a reference's anchor, namespaced by plan.
 */
export function citationAnchorId(planId: string, code: string): string {
	return `ref-${planId}-${code}`;
}

/**
 * Every defined source_code in the plan, mapped to the list it belongs to.
 */
function sourceCodeKinds(plan: Plan): Map<string, RefKind> {
	const kinds = new Map<string, RefKind>();
	for (const citation of plan.court_citations) {
		if (citation.source_code !== null) {
			kinds.set(citation.source_code, 'court');
		}
	}
	for (const source of plan.sources) {
		if (source.source_code !== null) {
			kinds.set(source.source_code, 'source');
		}
	}
	return kinds;
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

export function emptyPlanCitations(): PlanCitations {
	return { sourceNumbers: new Map(), kinds: new Map(), cited: new Set() };
}

/**
 * Build the per-plan citation model: source footnote numbers (first-appearance order,
 * cited sources only), each code's kind, and the resolvable codes that appear in prose.
 */
export function buildPlanCitations(plan: Plan): PlanCitations {
	const kinds = sourceCodeKinds(plan);
	const sourceNumbers = new Map<string, number>();
	const cited = new Set<string>();
	const orderedProse = [plan.origin_details, plan.struck_down_details, plan.notes];
	for (const prose of orderedProse) {
		for (const { code } of scanCitationTokens(prose)) {
			const kind = kinds.get(code);
			if (kind === undefined) {
				continue;
			}
			cited.add(code);
			if (kind === 'source' && !sourceNumbers.has(code)) {
				sourceNumbers.set(code, sourceNumbers.size + 1);
			}
		}
	}
	return { sourceNumbers, kinds, cited };
}

/**
 * The display segment for one [CODE], or null if the code does not resolve.
 */
function citationSegment(code: string, citations: PlanCitations): CitationSegment | null {
	const kind = citations.kinds.get(code);
	if (kind === 'source') {
		const number = citations.sourceNumbers.get(code);
		return number === undefined ? null : { kind: 'citation', refKind: 'source', code, number };
	}
	if (kind === 'court') {
		return { kind: 'citation', refKind: 'court', code };
	}
	return null;
}

/**
 * Split one prose string into ordered text / citation segments.
 */
export function tokenizeProse(prose: string, citations: PlanCitations): ProseSegment[] {
	const segments: ProseSegment[] = [];
	let cursor = 0;
	for (const match of scanCitationTokens(prose)) {
		const segment = citationSegment(match.code, citations);
		if (segment === null) {
			continue;
		}
		if (match.start > cursor) {
			segments.push({ kind: 'text', text: prose.slice(cursor, match.start) });
		}
		segments.push(segment);
		cursor = match.end;
	}
	if (cursor < prose.length) {
		segments.push({ kind: 'text', text: prose.slice(cursor) });
	}
	return segments;
}
