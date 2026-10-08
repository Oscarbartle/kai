import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
	buildSeries,
	formatAxisMoney,
	formatTick,
	nearestDot,
	niceTicks,
	PALETTE,
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

test('a young chart is left-weighted: first dot at the left, a week of room', () => {
	const t0 = Date.parse('2026-10-06T12:00:00Z');
	const one = buildSeries([pt(1, '2026-10-06T12:00:00Z', 3)], [{ id: 1, label: 'x' }]);
	const [lo, hi] = timeDomain(one);
	assert.ok(lo < t0 && t0 - lo < 86_400_000, 'first dot is just inside the left edge');
	assert.ok(hi - t0 >= MIN_WINDOW, 'a week of room to the right');
	// A few refreshes the same afternoon stay on the left too.
	const same = buildSeries([pt(1, '2026-10-06T12:00:00Z', 3), pt(1, '2026-10-06T15:00:00Z', 3.2)], [{ id: 1, label: 'x' }]);
	const [, hi2] = timeDomain(same);
	assert.ok(hi2 - Date.parse('2026-10-06T15:00:00Z') > 5 * 86_400_000);
});

test('an older chart fits its data: window grows past a week, small padding only', () => {
	const two = buildSeries([pt(1, '2026-09-01T00:00:00Z', 3), pt(1, '2026-10-11T00:00:00Z', 4)], [{ id: 1, label: 'x' }]);
	const [a, b] = timeDomain(two);
	const first = Date.parse('2026-09-01T00:00:00Z');
	const last = Date.parse('2026-10-11T00:00:00Z');
	assert.ok(a < first && b > last);
	assert.ok(b - last < 3 * 86_400_000, 'only a hair of room after the last dot');
	// With no data at all there is still a sane domain.
	const [x, y] = timeDomain([], 1_000_000_000_000);
	assert.ok(y > x);
});

test('x ticks start at the first dot and cover the whole window', () => {
	const young = buildSeries([pt(1, '2026-10-06T12:00:00Z', 3)], [{ id: 1, label: 'x' }]);
	const yt = timeTicks(young);
	assert.equal(yt.length, 5);
	assert.equal(yt[0], Date.parse('2026-10-06T12:00:00Z'));
	assert.equal(yt[4] - yt[0], MIN_WINDOW);
	const old = buildSeries([pt(1, '2026-10-01T00:00:00Z', 3), pt(1, '2026-10-21T00:00:00Z', 4)], [{ id: 1, label: 'x' }]);
	const ot = timeTicks(old);
	assert.equal(ot[0], Date.parse('2026-10-01T00:00:00Z'));
	assert.equal(ot[4], Date.parse('2026-10-21T00:00:00Z'), 'ends under the last dot');
	assert.deepEqual(timeTicks([]), []);
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
