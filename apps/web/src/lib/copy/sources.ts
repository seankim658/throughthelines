/**
 * Editorial copy for the upstream data sources shown on the /data page.
 *
 * This module owns the descriptions of each source. Lewis and Voteview
 * link via the manifest. The Census and basemap sources carry static
 * landing URLs here.
 */

import type { Manifest } from '$lib/manifest/types';

/** Where a source's external link is resolved from. */
export type SourceLink =
	| { kind: 'static'; url: string }
	| { kind: 'manifest'; key: 'lewis' | 'voteview' };

export type CitationSegment =
	| { type: 'text'; value: string }
	| { type: 'italic'; value: string }
	| { type: 'access_date' };

/** One upstream data source. */
export interface DataSource {
	name: string;
	description: string;
	link: SourceLink;
	license: string;
	note?: string;
	citation?: readonly CitationSegment[];
}

/**
 * The upstream data sources in display order.
 *
 * The Census and Protomaps landing URLs are not in the manifest and
 * are hardcoded here.
 */
export const DATA_SOURCES: readonly DataSource[] = [
	{
		name: 'Lewis Congressional District Boundaries',
		description:
			'Historical district polygons for most Congresses, used to draw the district maps on the state pages. The newest maps, which the archive does not yet carry, come from the publishing authority instead.',
		link: { kind: 'manifest', key: 'lewis' },
		license: 'MIT license',
		citation: [
			{
				type: 'text',
				value: 'Jeffrey B. Lewis, Brandon DeVine, Lincoln Pitcher, and Kenneth C. Martis. (2013) '
			},
			{
				type: 'italic',
				value: 'Digital Boundary Definitions of United States Congressional Districts, 1789-2012.'
			},
			{
				type: 'text',
				value: ' [Data file and code book]. Retrieved from https://cdmaps.polisci.ucla.edu on '
			},
			{ type: 'access_date' },
			{ type: 'text', value: '.' }
		]
	},
	{
		name: 'U.S. Census Geocoder',
		description: 'Resolves an address to its 2020 Census block.',
		link: { kind: 'static', url: 'https://geocoding.geo.census.gov/geocoder/' },
		license: 'Public domain'
	},
	{
		name: 'All About Redistricting',
		description:
			'The narrative reference behind our plan-origin curation. Most of the curation metadata is summarized from here.',
		link: { kind: 'static', url: 'https://redistricting.lls.edu/' },
		license: '© Justin Levitt (copyrighted reference, summarized with attribution)',
		citation: [
			{ type: 'text', value: 'Justin Levitt. ' },
			{
				type: 'italic',
				value:
					'All About Redistricting: Prof. Justin Levitt’s Guide to Drawing the Electoral Lines.'
			},
			{
				type: 'text',
				value: ' Loyola Law School. Retrieved from https://redistricting.lls.edu/.'
			}
		]
	},
	{
		name: 'Census Block Equivalency Files',
		description:
			'Official block-to-district assignments, used for most Congresses from the 113th on.',
		link: {
			kind: 'static',
			url: 'https://www.census.gov/geographies/mapping-files.html'
		},
		license: 'Public domain'
	},
	{
		name: 'Census Tabulation Blocks (TIGER/Line)',
		description: 'Per-decade block geometry used to link blocks across Census vintages.',
		link: {
			kind: 'static',
			url: 'https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html'
		},
		license: 'Public domain'
	},
	{
		name: 'Voteview',
		description: 'House member records: name, party, and dates served.',
		link: { kind: 'manifest', key: 'voteview' },
		license: 'Open / academic',
		citation: [
			{
				type: 'text',
				value:
					'Lewis, Jeffrey B., Keith Poole, Howard Rosenthal, Adam Boche, Aaron Rudkin, and Luke Sonnet (2026). '
			},
			{ type: 'italic', value: 'Voteview: Congressional Roll-Call Votes Database.' },
			{ type: 'text', value: ' https://voteview.com/' }
		]
	},
	{
		name: 'Protomaps Basemap',
		description: 'The base map the districts are drawn over.',
		link: { kind: 'static', url: 'https://maps.protomaps.com/builds' },
		license: 'Open (OpenStreetMap)'
	}
];

/**
 * State-specific data sources.
 */
export const STATE_SOURCES: readonly DataSource[] = [
	{
		name: 'North Carolina General Assembly',
		description:
			'Congressional maps enacted by the North Carolina legislature and published directly. Supplies the address-lookup files for the 117th and 120th Congresses and the boundary shapefile for the 120th.',
		link: { kind: 'static', url: 'https://www.ncleg.gov/Redistricting' },
		license: 'Public domain'
	}
];

export function resolveSourceUrl(manifest: Manifest, link: SourceLink): string {
	if (link.kind === 'static') {
		return link.url;
	}
	if (link.key === 'lewis') {
		return manifest.sources.lewis.homepage_url;
	}
	return manifest.sources.voteview.landing_url;
}

export function formatAccessDate(manifest: Manifest): string {
	const isoDate = manifest.build.built_at.slice(0, 10);
	const [year, month, day] = isoDate.split('-').map(Number);
	const date = new Date(Date.UTC(year, month - 1, day));
	return date.toLocaleDateString('en-US', {
		year: 'numeric',
		month: 'long',
		day: 'numeric',
		timeZone: 'UTC'
	});
}
