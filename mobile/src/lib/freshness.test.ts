import { test } from 'node:test';
import assert from 'node:assert/strict';
import { skuAgeDays, staleAgeDays } from './freshness.ts';

const NOW = Date.parse('2026-10-20T12:00:00Z');
const daysAgo = (n: number) => new Date(NOW - n * 86_400_000).toISOString();

test('age is whole days, never negative', () => {
  assert.equal(skuAgeDays(daysAgo(0), NOW), 0);
  assert.equal(skuAgeDays(daysAgo(3), NOW), 3);
  assert.equal(skuAgeDays(new Date(NOW - 3.9 * 86_400_000).toISOString(), NOW), 3);
  assert.equal(skuAgeDays(new Date(NOW + 5 * 86_400_000).toISOString(), NOW), 0); // clock skew
});

test('unknown or junk timestamps have no age', () => {
  assert.equal(skuAgeDays(undefined, NOW), null);
  assert.equal(skuAgeDays('', NOW), null);
  assert.equal(skuAgeDays('not a date', NOW), null);
});

test('stale means 14 days or more, judged by the oldest SKU', () => {
  assert.equal(staleAgeDays([{ updated_at: daysAgo(13) }], NOW), null);
  assert.equal(staleAgeDays([{ updated_at: daysAgo(14) }], NOW), 14);
  assert.equal(staleAgeDays([{ updated_at: daysAgo(2) }, { updated_at: daysAgo(30) }], NOW), 30);
});

test('no SKUs, or none with a known age, is never flagged', () => {
  assert.equal(staleAgeDays([], NOW), null);
  assert.equal(staleAgeDays([{}, { updated_at: '' }], NOW), null);
  // An unknown one doesn't hide a known stale one.
  assert.equal(staleAgeDays([{}, { updated_at: daysAgo(20) }], NOW), 20);
});
