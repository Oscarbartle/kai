import { test } from 'node:test';
import assert from 'node:assert/strict';
import { sizeLabel } from './skuSize.ts';

test('a normal size is shown as Woolworths gave it', () => {
	assert.equal(sizeLabel({ volume_size: '500g' }), '500g');
	assert.equal(sizeLabel({ volume_size: '1.5kg' }), '1.5kg');
	assert.equal(sizeLabel({ volume_size: '750mL' }), '750mL');
});

test('multi-packs get a space', () => {
	assert.equal(sizeLabel({ volume_size: '6pack' }), '6 pack');
	assert.equal(sizeLabel({ volume_size: '12 PACK' }), '12 pack');
});

test('wording that is not a size passes through untouched', () => {
	assert.equal(sizeLabel({ volume_size: 'per kg' }), 'per kg');
	assert.equal(sizeLabel({ volume_size: 'min order 1kg' }), 'min order 1kg');
});

test('no size means no badge', () => {
	assert.equal(sizeLabel({ volume_size: null }), null);
	assert.equal(sizeLabel({ volume_size: '   ' }), null);
	assert.equal(sizeLabel({}), null);
	assert.equal(sizeLabel(undefined), null);
	assert.equal(sizeLabel(null), null);
});
