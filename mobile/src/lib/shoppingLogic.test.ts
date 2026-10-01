import { test } from 'node:test';
import assert from 'node:assert/strict';
import { defaultListId, groupLines, stepAmount, stepFor } from './shoppingLogic.ts';
import type { RecipeBookEntry, ShoppingLine } from './types.ts';

const line = (id: number, source: number | null): ShoppingLine => ({
  id,
  item_id: id,
  item_name: `item ${id}`,
  amount: 1,
  unit: 'count',
  source_recipe_id: source,
});

test('step sizes follow the unit', () => {
  assert.equal(stepFor('count', 7), 1);
  assert.equal(stepFor(null, 7), 1);
  assert.equal(stepFor('g', 200), 50);
  assert.equal(stepFor('mL', 500), 100);
});

test('stepping a count', () => {
  assert.deepEqual(stepAmount(3, 'count', 1), { amount: 4, unit: 'count' });
  assert.deepEqual(stepAmount(3, 'count', -1), { amount: 2, unit: 'count' });
});

test('stepping never reaches zero', () => {
  assert.equal(stepAmount(1, 'count', -1).amount, 1);
  assert.equal(stepAmount(50, 'g', -1).amount, 50);
  assert.equal(stepAmount(20, 'g', -1).amount, 50);
});

test('weights use the finer step below 500 and the coarser from 500 up, both ways', () => {
  assert.equal(stepAmount(450, 'g', 1).amount, 500);
  assert.equal(stepAmount(500, 'g', 1).amount, 600);
  assert.equal(stepAmount(600, 'g', -1).amount, 500);
  assert.equal(stepAmount(500, 'g', -1).amount, 450);
});

test('an amount that was never set starts at one item', () => {
  assert.deepEqual(stepAmount(null, null, 1), { amount: 1, unit: 'count' });
  assert.deepEqual(stepAmount(null, 'g', -1), { amount: 1, unit: 'g' });
});

test('fractional amounts from a scaled recipe stay tidy', () => {
  assert.equal(stepAmount(112.5, 'g', 1).amount, 162.5);
});

test('loose items come first, then each recipe in order of appearance', () => {
  const book = [{ recipe: { id: 2, name: 'Curry' } }, { recipe: { id: 5, name: 'Pasta' } }] as RecipeBookEntry[];
  const groups = groupLines([line(1, 5), line(2, null), line(3, 2), line(4, 5)], book);
  assert.deepEqual(
    groups.map((g) => [g.recipeId, g.name, g.lines.map((l) => l.id)]),
    [
      [null, null, [2]],
      [5, 'Pasta', [1, 4]],
      [2, 'Curry', [3]],
    ]
  );
});

test('lines from a deleted recipe are kept', () => {
  const groups = groupLines([line(1, 99)], []);
  assert.equal(groups[0].name, 'A removed recipe');
  assert.equal(groups[0].lines.length, 1);
});

test('default list: last used if it still exists, else the first, else none', () => {
  assert.equal(defaultListId([4, 7, 9], 7), 7);
  assert.equal(defaultListId([4, 7, 9], 3), 4);
  assert.equal(defaultListId([4, 7, 9], null), 4);
  assert.equal(defaultListId([], 7), null);
});
