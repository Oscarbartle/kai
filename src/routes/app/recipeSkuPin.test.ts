import { test } from 'node:test';
import assert from 'node:assert/strict';
import { autoPickLabel, pinOptionLabel, type PinSku } from './recipeSkuPin.ts';
import { sizeLabel } from './skuSize.ts';
import { titleCase } from './titleCase.ts';

const sku = (id: number, size: string | null, price: number | null, starred = false): PinSku => ({
	id,
	name: 'woolworths nz beef mince grass fed 5% fat',
	is_preferred: starred,
	size: { volume_size: size },
	price: { sale_price: price }
});

test('an option leads with size, then price, then the title-cased name', () => {
	assert.equal(
		pinOptionLabel(sku(1, '500g', 15.25), (s) => sizeLabel(s), titleCase),
		'500g · $15.25 · Woolworths NZ Beef Mince Grass Fed 5% Fat'
	);
});

test('the starred SKU is marked', () => {
	assert.ok(pinOptionLabel(sku(2, '750g', 20.25, true), (s) => sizeLabel(s), titleCase).startsWith('★ 750g'));
});

test('a SKU with no size or no price just leaves those parts out', () => {
	assert.equal(pinOptionLabel(sku(3, null, 9), (s) => sizeLabel(s)), '$9.00 · woolworths nz beef mince grass fed 5% fat');
	assert.equal(pinOptionLabel(sku(4, '1kg', null), (s) => sizeLabel(s)), '1kg · woolworths nz beef mince grass fed 5% fat');
});

test('Auto says what it currently means', () => {
	assert.equal(autoPickLabel([sku(1, '500g', 15.25), sku(2, '750g', 20.25, true)]), 'Auto — ★ 750g');
	assert.equal(autoPickLabel([sku(1, '500g', 15.25), sku(2, '750g', 20.25)]), 'Auto — cheapest');
	assert.equal(autoPickLabel([sku(1, null, 1, true)]), 'Auto — ★ starred SKU');
	assert.equal(autoPickLabel([]), 'Auto — cheapest');
});
