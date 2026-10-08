import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
	buildSeries,
	formatAxisMoney,
	formatTick,
	nearestDot,
	niceTicks,
	PALETTE,
	isToday,
	MIN_WINDOW,
	timeDomain,
	timeTicks,
	totalDots,
	type PricePoint
} from './priceHistory.ts';

const pt = (sku_id: number, recorded_at: string, sale: number | null, extra: Partial<PricePoint> = {}): PricePoint => ({
	sku_id,
	recorded_at,
	sale_price: sale,
	original_price: sale,
	is_special: false,
	cup_price: null,
	...extra
});

test('one series per SKU, in the order given, with stable colours', () => {
	const points = [pt(2, '2026-10-02T00:00:00Z', 4), pt(1, '2026-10-01T00:00:00Z', 3)];
	const s = buildSeries(points, [
		{ id: 1, label: 'Onions' },
		{ id: 2, label: 'Brown onions' }
	]);
	assert.deepEqual(s.map((x) => x.label), ['Onions', 'Brown onions']);
	assert.deepEqual(s.map((x) => x.color), [PALETTE[0], PALETTE[1]]);
	assert.equal(s[0].dots.length, 1);
	assert.equal(s[0].dots[0].price, 3);
});

test('a series carries its SKU\'s pack size, or null', () => {
	const s = buildSeries([], [{ id: 1, label: 'Beef mince', size: '500g' }, { id: 2, label: 'Beef mince' }]);
	assert.deepEqual(s.map((x) => x.size), ['500g', null]);
});

test('dots are sorted by time whatever order the rows arrive in', () => {
	const s = buildSeries(
		[pt(1, '2026-10-03T00:00:00Z', 5), pt(1, '2026-10-01T00:00:00Z', 3), pt(1, '2026-10-02T00:00:00Z', 4)],
		[{ id: 1, label: 'x' }]
	);
	assert.deepEqual(s[0].dots.map((d) => d.price), [3, 4, 5]);
});

test('rows with no price, bad dates, or an unknown SKU are not plotted', () => {
	const s = buildSeries(
		[pt(1, '2026-10-01T00:00:00Z', null), pt(1, 'garbage', 3), pt(9, '2026-10-01T00:00:00Z', 3), pt(1, '2026-10-02T00:00:00Z', 2)],
		[{ id: 1, label: 'x' }]
	);
	assert.equal(totalDots(s), 1);
	assert.equal(s[0].dots[0].price, 2);
});

test('a special carries its was-price; a plain price does not', () => {
	const s = buildSeries(
		[
			pt(1, '2026-10-01T00:00:00Z', 2.8, { is_special: true, original_price: 3.8 }),
			pt(1, '2026-10-02T00:00:00Z', 3.8, { is_special: false, original_price: 3.8 }),
			pt(1, '2026-10-03T00:00:00Z', 3.0, { is_special: true, original_price: null })
		],
		[{ id: 1, label: 'x' }]
	);
	assert.deepEqual(s[0].dots.map((d) => [d.special, d.was]), [[true, 3.8], [false, null], [true, null]]);
});

test('colours wrap around when there are more SKUs than colours', () => {
	const skus = Array.from({ length: PALETTE.length + 1 }, (_, i) => ({ id: i + 1, label: `s${i}` }));
	const s = buildSeries([], skus);
	assert.equal(s[PALETTE.length].color, PALETTE[0]);
});

test('niceTicks brackets the data with round numbers', () => {
	const { ticks, lo, hi } = niceTicks(2.8, 3.8);
	assert.ok(lo <= 2.8 && hi >= 3.8, `${lo}..${hi}`);
	assert.ok(ticks.length >= 3 && ticks.length <= 8, `${ticks}`);
	const step = ticks[1] - ticks[0];
	assert.ok(ticks.every((t, i) => i === 0 || Math.abs(t - ticks[i - 1] - step) < 1e-9), 'evenly spaced');
});

test('niceTicks on a flat line still has room either side, and never goes below zero', () => {
	const flat = niceTicks(3.5, 3.5);
	assert.ok(flat.lo < 3.5 && flat.hi > 3.5);
	const low = niceTicks(0.1, 0.3);
	assert.ok(low.lo >= 0);
});

test('niceTicks on big and tiny ranges', () => {
	const big = niceTicks(100, 480);
	assert.ok(big.lo <= 100 && big.hi >= 480);
	const tiny = niceTicks(1.99, 2.01);
	assert.ok(tiny.lo <= 1.99 && tiny.hi >= 2.01);
	assert.ok(tiny.ticks.every((t) => Number.isFinite(t)));
});

const NOW = Date.parse('2026-10-08T03:00:00Z');

test('the right edge is the present: the axis runs from the first dot to now', () => {
	const s = buildSeries([pt(1, '2026-09-20T00:00:00Z', 3), pt(1, '2026-09-25T00:00:00Z', 3)], [{ id: 1, label: 'x' }]);
	const [lo, hi] = timeDomain(s, NOW);
	assert.ok(lo < Date.parse('2026-09-20T00:00:00Z') && Date.parse('2026-09-20T00:00:00Z') - lo < 2 * 86_400_000, 'first dot just inside the left edge');
	assert.ok(hi > NOW && hi - NOW < 2 * 86_400_000, 'now is just inside the right edge, not days of empty future');
	const ticks = timeTicks(s, 5, NOW);
	assert.equal(ticks.length, 5);
	assert.equal(ticks[0], Date.parse('2026-09-20T00:00:00Z'));
	assert.equal(ticks[4], NOW);
});

test('no empty space before the data once there is more than a day of history', () => {
	// First dot ~2 days ago: the axis starts at it, not a day earlier.
	const s = buildSeries([pt(1, '2026-10-06T03:00:00Z', 3), pt(1, '2026-10-08T01:00:00Z', 3)], [{ id: 1, label: 'x' }]);
	const ticks = timeTicks(s, 5, NOW);
	assert.equal(ticks[0], Date.parse('2026-10-06T03:00:00Z'));
	const [lo] = timeDomain(s, NOW);
	assert.ok(Date.parse('2026-10-06T03:00:00Z') - lo < 0.05 * (NOW - Date.parse('2026-10-06T03:00:00Z')) + 1, 'only the hairline margin');
});

test('a brand-new item gets a minimum window ending now, its dot at the right', () => {
	const s = buildSeries([pt(1, '2026-10-08T01:00:00Z', 3)], [{ id: 1, label: 'x' }]);
	const ticks = timeTicks(s, 5, NOW);
	assert.equal(ticks[ticks.length - 1], NOW);
	assert.equal(ticks[ticks.length - 1] - ticks[0], MIN_WINDOW);
	const [lo, hi] = timeDomain(s, NOW);
	assert.ok(hi - lo >= MIN_WINDOW);
	assert.ok(hi - Date.parse('2026-10-08T01:00:00Z') < 0.2 * (hi - lo), 'the dot is at the right-hand end');
});

test('a short window gets fewer labels so no two neighbours share a date', () => {
	const s = buildSeries([pt(1, '2026-10-05T03:00:00Z', 3), pt(1, '2026-10-08T01:00:00Z', 3)], [{ id: 1, label: 'x' }]);
	const ticks = timeTicks(s, 5, NOW);
	assert.equal(ticks.length, 4, 'a 3-day window: one label per day');
	for (let i = 1; i < ticks.length; i++) assert.ok(ticks[i] - ticks[i - 1] >= 86_400_000);
	const day = (t: number) => new Date(t).toDateString();
	assert.equal(new Set(ticks.map(day)).size, ticks.length, 'every label is a different date');
});

test('a dot dated after "now" (clock skew) is not cut off', () => {
	const s = buildSeries([pt(1, '2026-10-01T00:00:00Z', 3), pt(1, '2026-10-09T00:00:00Z', 4)], [{ id: 1, label: 'x' }]);
	const ticks = timeTicks(s, 5, NOW);
	assert.equal(ticks[ticks.length - 1], Date.parse('2026-10-09T00:00:00Z'));
});

test('an item whose price stopped changing still runs to today', () => {
	// Last dot 20 days ago: the line stops there and the axis carries on to now.
	const s = buildSeries([pt(1, '2026-09-01T00:00:00Z', 3), pt(1, '2026-09-18T00:00:00Z', 3)], [{ id: 1, label: 'x' }]);
	const ticks = timeTicks(s, 5, NOW);
	assert.equal(ticks[ticks.length - 1], NOW);
});

test('with no data there is still a sane domain and no ticks', () => {
	const [x, y] = timeDomain([], 1_000_000_000_000);
	assert.ok(y > x);
	assert.deepEqual(timeTicks([], 5, NOW), []);
});

test('isToday compares local calendar days', () => {
	const noon = new Date(2026, 9, 8, 12, 0).getTime();
	assert.equal(isToday(new Date(2026, 9, 8, 0, 5).getTime(), noon), true);
	assert.equal(isToday(new Date(2026, 9, 8, 23, 55).getTime(), noon), true);
	assert.equal(isToday(new Date(2026, 9, 7, 23, 55).getTime(), noon), false);
	assert.equal(isToday(new Date(2025, 9, 8, 12, 0).getTime(), noon), false);
});

test('axis labels say only what the span needs', () => {
	const t = new Date(2026, 9, 6, 14, 5).getTime();
	assert.equal(formatTick(t, 3_600_000), '6 Oct 2:05pm');
	assert.equal(formatTick(t, 30 * 86_400_000), '6 Oct');
	assert.equal(formatTick(t, 400 * 86_400_000), '6 Oct 2026');
	assert.equal(formatTick(new Date(2026, 9, 6, 0, 0).getTime(), 3_600_000), '6 Oct 12:00am');
	assert.equal(formatTick(new Date(2026, 9, 6, 12, 0).getTime(), 3_600_000), '6 Oct 12:00pm');
});

test('axis money drops whole-dollar cents', () => {
	assert.equal(formatAxisMoney(3), '$3');
	assert.equal(formatAxisMoney(3.5), '$3.50');
});

test('nearestDot picks the closest within the radius, else nothing', () => {
	const dots = [{ x: 10, y: 10, id: 'a' }, { x: 14, y: 10, id: 'b' }, { x: 100, y: 100, id: 'c' }];
	assert.equal(nearestDot(dots, 13, 10, 20)?.id, 'b');
	assert.equal(nearestDot(dots, 50, 50, 20), null);
	assert.equal(nearestDot([], 0, 0, 20), null);
});
