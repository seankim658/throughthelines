/**
 * Docs navigation registry.
 */

export type DocGroup = 'Start here' | 'Reference' | 'Contributing' | 'About';

export interface DocPage {
	readonly slug: string;
	readonly title: string;
	readonly description: string;
	readonly group: DocGroup;
	readonly lastUpdated?: string;
}

export const DOC_GROUP_ORDER: readonly DocGroup[] = [
	'Start here',
	'Reference',
	'Contributing',
	'About'
] as const;

export const DOC_PAGES: readonly DocPage[] = [
	{
		slug: 'overview',
		title: 'Overview',
		description: 'What Through the Lines is, the question it answers, and who it is for.',
		group: 'Start here',
		lastUpdated: '2026-05-25'
	},
	{
		slug: 'how-it-works',
		title: 'How it works',
		description: 'The address-to-district lookup flow, how it works, and the privacy model.',
		group: 'Start here',
		lastUpdated: '2026-05-25'
	},
	{
		slug: 'methodology',
		title: 'Methodology',
		description: 'Per-Congress data sourcing, cross-decade block linkage, and known caveats.',
		group: 'Reference',
		lastUpdated: '2026-05-25'
	},
	{
		slug: 'data-model',
		title: 'Data model & schema',
		description: 'The plan-metadata schema, the missingness model, and the build artifacts.',
		group: 'Reference',
		lastUpdated: '2026-05-25'
	},
	{
		slug: 'architecture',
		title: 'Architecture',
		description: 'The build pipeline, the manifest contract, and the frontend runtime flow.',
		group: 'Reference',
		lastUpdated: '2026-05-25'
	},
	{
		slug: 'curation',
		title: 'Curation guide',
		description: 'How to take a plan from pending to curated, and how to contribute one.',
		group: 'Contributing',
		lastUpdated: '2026-05-25'
	},
	{
		slug: 'roadmap',
		title: 'Roadmap & limitations',
		description: 'What is in scope today, what is planned, and the known limitations.',
		group: 'About',
		lastUpdated: '2026-05-25'
	},
	{
		slug: 'glossary',
		title: 'Glossary',
		description: 'Redistricting and technical terms used throughout the documentation.',
		group: 'About',
		lastUpdated: '2026-05-25'
	}
] as const;

export function findDocPage(slug: string): DocPage | undefined {
	return DOC_PAGES.find((page) => page.slug === slug);
}

export function pagesInGroup(group: DocGroup): readonly DocPage[] {
	return DOC_PAGES.filter((page) => page.group === group);
}

export interface DocNeighbors {
	readonly previous: DocPage | null;
	readonly next: DocPage | null;
}

export function neighborsOf(slug: string): DocNeighbors {
	const index = DOC_PAGES.findIndex((page) => page.slug === slug);
	if (index === -1) {
		return { previous: null, next: null };
	}
	return {
		previous: index > 0 ? DOC_PAGES[index - 1] : null,
		next: index < DOC_PAGES.length - 1 ? DOC_PAGES[index + 1] : null
	};
}

export function formatLastUpdated(isoDate: string): string {
	const [year, month, day] = isoDate.split('-').map(Number);
	const date = new Date(Date.UTC(year, month - 1, day));
	return date.toLocaleDateString('en-US', {
		year: 'numeric',
		month: '2-digit',
		day: '2-digit',
		timeZone: 'UTC'
	});
}
