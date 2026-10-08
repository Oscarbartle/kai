import { test } from 'node:test';
import assert from 'node:assert/strict';
import { titleCase } from './titleCase.ts';

test('a Woolworths name reads like a name, with NZ as an acronym', () => {
	assert.equal(titleCase('woolworths nz beef mince grass fed 5% fat'), 'Woolworths NZ Beef Mince Grass Fed 5% Fat');
	assert.equal(titleCase('woolworths nz beef mince prime grass fed 13% fat'), 'Woolworths NZ Beef Mince Prime Grass Fed 13% Fat');
});

test('sizes and numbers are left alone', () => {
	assert.equal(titleCase('pams butter 500g block'), 'Pams Butter 500g Block');
	assert.equal(titleCase('2 pack'), '2 Pack');
});

test('apostrophes do not start a new word', () => {
	assert.equal(titleCase("pam's cheese"), "Pam's Cheese");
	assert.equal(titleCase("farmer's choice"), "Farmer's Choice");
});

test('hyphenated words and brackets', () => {
	assert.equal(titleCase('gluten-free bread (sliced)'), 'Gluten-Free Bread (Sliced)');
});

test('small words stay lowercase, except as the first word', () => {
	assert.equal(titleCase('cheese and onion chips'), 'Cheese and Onion Chips');
	assert.equal(titleCase('the big cheese'), 'The Big Cheese');
});

test('existing capitals are kept, and odd input is safe', () => {
	assert.equal(titleCase('KFC gravy'), 'KFC Gravy');
	assert.equal(titleCase('  extra   spaces '), 'Extra   Spaces');
	assert.equal(titleCase(''), '');
	assert.equal(titleCase('   '), '');
});

test('idempotent: already-titled text is unchanged', () => {
	const s = 'Woolworths NZ Beef Mince Grass Fed 5% Fat';
	assert.equal(titleCase(s), s);
});
