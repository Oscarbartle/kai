// Woolworths sends product names lowercase ("woolworths nz beef mince
// grass fed 5% fat"); this makes them read like names. It only raises the
// first letter of each word — it never lowercases the rest, so a name that
// already has deliberate capitals ("KFC") survives.

const SMALL_WORDS = new Set(['and', 'or', 'of', 'the', 'a', 'an', 'in', 'on', 'with', 'for', 'to']);
const ACRONYMS = new Set(['nz', 'uk', 'usa', 'bbq', 'uht']);

export function titleCase(text: string): string {
	let first = true;
	return text
		.trim()
		.split(/(\s+|-)/)
		.map((part) => {
			if (!part || /^(\s+|-)$/.test(part)) return part;
			const isFirst = first;
			first = false;
			const word = part.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
			if (ACRONYMS.has(word)) return part.replace(/\p{L}+/u, (m) => m.toUpperCase());
			if (!isFirst && SMALL_WORDS.has(word)) return part;
			// Raise the first letter, unless the word opens with a digit ("500g").
			return part.replace(/^([^\p{L}\p{N}]*)(\p{L})/u, (_, lead: string, c: string) => lead + c.toUpperCase());
		})
		.join('');
}
