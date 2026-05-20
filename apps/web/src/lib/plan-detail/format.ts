/**
 * Pure formatters for plan metadata fields that support
 * the three-valued missingness model.
 *
 * Each formatter returns a label and a styling tone.
 */

import { PENDING, UNKNOWN } from '$lib/plan-index/types';
import type {
	CurationStatus,
	OriginField,
	OriginLiteral,
	StruckDownField,
	DateField,
	IsoDate,
	PlanRefField,
	ProseField
} from '$lib/plan-index/types';

export type BadgeTone = 'normal' | 'pending' | 'unknown' | 'warning' | 'success';

export interface Badge {
	label: string;
	tone: BadgeTone;
}

const ORIGIN_LABELS: Record<OriginLiteral, string> = {
	legislature: 'Legislature-drawn',
	court: 'Court-drawn',
	commission: 'Commission-drawn',
	remedial: 'Remedial plan',
	unchanged: 'Carried over'
};

export function formatOrigin(origin: OriginField): Badge {
	if (origin === PENDING) {
		return { label: 'Origin pending', tone: 'pending' };
	}
	if (origin === UNKNOWN) {
		return { label: 'Origin not determined', tone: 'pending' };
	}
	return { label: ORIGIN_LABELS[origin], tone: 'normal' };
}

export function formatStruckDown(struck_down: StruckDownField): Badge {
	if (struck_down === PENDING) {
		return { label: 'Strikedown pending', tone: 'pending' };
	}
	if (struck_down === UNKNOWN) {
		return { label: 'Invalidation status not determined', tone: 'unknown' };
	}
	if (struck_down === true) {
		return { label: 'Struck down', tone: 'warning' };
	}
	return { label: 'Not invalidated', tone: 'normal' };
}

const CURATION_STATUS_LABELS: Record<CurationStatus, string> = {
	curated: 'Curated',
	partial: 'Partially curated',
	pending: 'Curation pending'
};

const CURATION_STATUS_TONES: Record<CurationStatus, BadgeTone> = {
	curated: 'success',
	partial: 'warning',
	pending: 'pending'
};

export function formatCurationStatus(status: CurationStatus): Badge {
	return {
		label: CURATION_STATUS_LABELS[status],
		tone: CURATION_STATUS_TONES[status]
	};
}

export function isRealProse(value: ProseField): boolean {
	return value !== PENDING && value !== UNKNOWN && value.length > 0;
}

export function isRealDate(value: DateField): value is IsoDate {
	return value !== null && value !== PENDING && value !== UNKNOWN;
}

export function isRealPlanRef(value: PlanRefField): value is string {
	return value !== null && value !== PENDING;
}

export function formatPlanDate(value: IsoDate): string {
	const [year, month, day] = value.split('-').map(Number);
	const date = new Date(Date.UTC(year, month - 1, day));
	return date.toLocaleDateString('en-US', {
		year: 'numeric',
		month: 'long',
		day: 'numeric',
		timeZone: 'UTC'
	});
}
