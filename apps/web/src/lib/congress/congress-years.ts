/**
 * Pure helpers for mapping Congress numbers to calendar years.
 */

export interface CongressYears {
	start: number;
	end: number;
}

export function congressYears(congress: number): CongressYears {
	const start = 1789 + 2 * (congress - 1);
	const end = start + 2;
	return { start, end };
}

export function formatCongressYears(congress: number): string {
	const { start, end } = congressYears(congress);
	return `${start}\u2013${end}`;
}
