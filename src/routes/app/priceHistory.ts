// Turns the raw price-history rows into what the chart draws: one series
// per SKU, "nice" axis ticks, and readable date labels. No Svelte and no
// DOM in here so it can be unit-tested (`npm test`).

export interface PricePoint {
	sku_id: number;
	/** UTC, RFC 3339. */
	recorded_at: string;
	sale_price: number | null;
	original_price: number | null;
	is_special: boolean;
	cup_price: number | null;
}

export interface SkuRef {
	id: number;
	label: string;
}

export interface Dot {
	/** Milliseconds since the epoch. */
	t: number;
	price: number;
	special: boolean;
	/** The shelf price before the special, when it was one. */
	was: number | null;
}

export interface Series {
	skuId: number;
	label: string;
	color: string;
	dots: Dot[];
}

/** Distinguishable on the app's dark background, and in a stable order so
 *  a SKU keeps its colour across refreshes. */
export const PALETTE = ['#e8735f', '#5fb4e0', '#e3b94f', '#7fc784', '#b592e6', '#e885b8', '#4fc9c0', '#c9a27a'];

/** One series per SKU, in the order given. A row with no price (an
 *  unavailable product) has nothing to plot and is skipped; rows for SKUs
 *  not in `skus` (deleted meanwhile) are ignored. */
export function buildSeries(points: PricePoint[], skus: SkuRef[]): Series[] {
	return skus.map((sku, i) => ({
		skuId: sku.id,
		label: sku.label,
		color: PALETTE[i % PALETTE.length],
		dots: points
			.filter((p) => p.sku_id === sku.id && p.sale_price != null)
			.map((p) => ({
				t: Date.parse(p.recorded_at),
				price: p.sale_price as number,
				special: p.is_special,
				was: p.is_special && p.original_price != null && p.original_price !== p.sale_price ? p.original_price : null
			}))
			.filter((d) => !Number.isNaN(d.t))
			.sort((a, b) => a.t - b.t)
	}));
}

export function totalDots(series: Series[]): number {
	return series.reduce((n, s) => n + s.dots.length, 0);
}

/** The y-axis: round numbers that bracket the data with some air around it.
 *  Doesn't force zero — prices wobble by cents, and a chart squashed
 *  against a $0 baseline would show nothing. */
export function niceTicks(min: number, max: number, target = 5): { ticks: number[]; lo: number; hi: number } {
	if (!(max > min)) {
		// A flat line: make some room either side.
		const pad = Math.max(Math.abs(min) * 0.1, 0.5);
		min -= pad;
		max += pad;
	} else {
		const pad = (max - min) * 0.12;
		min -= pad;
		max += pad;
	}
	min = Math.max(0, min);
	const step = niceStep((max - min) / Math.max(1, target - 1));
	const lo = Math.floor(min / step) * step;
	const hi = Math.ceil(max / step) * step;
	const ticks: number[] = [];
	for (let v = lo; v <= hi + step / 2; v += step) ticks.push(round(v, step));
	return { ticks, lo: ticks[0], hi: ticks[ticks.length - 1] };
}

function niceStep(raw: number): number {
	const pow = Math.pow(10, Math.floor(Math.log10(raw)));
	const f = raw / pow;
	const nice = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
	return nice * pow;
}

function round(v: number, step: number): number {
	const decimals = Math.max(0, 2 - Math.floor(Math.log10(step)));
	return Number(v.toFixed(Math.min(6, decimals)));
}

const HOUR = 3_600_000;
const DAY = 24 * HOUR;

/** The x-axis range. A single moment (one dot, or several in the same
 *  second) gets a day of room either side so it sits mid-chart. */
export function timeDomain(series: Series[], now: number = Date.now()): [number, number] {
	const ts = series.flatMap((s) => s.dots.map((d) => d.t));
	if (!ts.length) return [now - DAY, now + DAY];
	let lo = Math.min(...ts);
	let hi = Math.max(...ts);
	if (hi - lo < HOUR) {
		return [lo - DAY, hi + DAY];
	}
	const pad = (hi - lo) * 0.04;
	return [lo - pad, hi + pad];
}

/** x-axis tick times, evenly spaced from the first dot to the last so the
 *  end labels sit under the end dots (not under the padding beyond them).
 *  One moment of data (a lone dot, or refreshes within the same hour) gets
 *  a single label. */
export function timeTicks(series: Series[], count = 5): number[] {
	const ts = series.flatMap((s) => s.dots.map((d) => d.t));
	if (!ts.length) return [];
	const lo = Math.min(...ts);
	const hi = Math.max(...ts);
	if (hi - lo < HOUR) return [Math.round((lo + hi) / 2)];
	return Array.from({ length: count }, (_, i) => lo + ((hi - lo) * i) / (count - 1));
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function clock(d: Date): string {
	const h = d.getHours();
	const m = d.getMinutes().toString().padStart(2, '0');
	return `${((h + 11) % 12) + 1}:${m}${h < 12 ? 'am' : 'pm'}`;
}

/** An axis label that says only as much as the span needs: the time of
 *  day when everything is within a couple of days, the year when it
 *  spans more than one. */
export function formatTick(t: number, spanMs: number): string {
	const d = new Date(t);
	const day = `${d.getDate()} ${MONTHS[d.getMonth()]}`;
	if (spanMs <= 2 * DAY) return `${day} ${clock(d)}`;
	if (spanMs > 300 * DAY) return `${day} ${d.getFullYear()}`;
	return day;
}

/** The tooltip's date: always complete. */
export function formatFull(t: number): string {
	const d = new Date(t);
	return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}, ${clock(d)}`;
}

export function formatMoney(v: number): string {
	return `$${v.toFixed(2)}`;
}

/** Axis money: drops the cents when the tick is a whole dollar. */
export function formatAxisMoney(v: number): string {
	return Number.isInteger(v) ? `$${v}` : `$${v.toFixed(2)}`;
}

/** The dot nearest `(x, y)` within `radius` (all in the same units), or
 *  `null`. Used for the hover tooltip. */
export function nearestDot<T extends { x: number; y: number }>(dots: T[], x: number, y: number, radius: number): T | null {
	let best: T | null = null;
	let bestD = radius * radius;
	for (const d of dots) {
		const dd = (d.x - x) ** 2 + (d.y - y) ** 2;
		if (dd <= bestD) {
			best = d;
			bestD = dd;
		}
	}
	return best;
}
