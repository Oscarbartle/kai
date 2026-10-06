<!--
	The new-item wizard for the recipe import: one step per ingredient that has
	no Pantry item yet. For each: confirm the name, say whether it's perishable,
	and pick the Woolworths product(s) to link — by searching, or by pasting a
	product link / stock code. Picking a product fetches its *full* record
	straight away (the search result doesn't carry allergens, which matter here),
	so what is saved later is exactly what was shown.

	Nothing is written from here. The wizard only fills in `items`; the import
	dialog saves everything — recipe, items, products — in one go afterwards.
-->
<script lang="ts" module>
	export interface Hit {
		sku: string;
		name: string;
		brand: string | null;
		variety: string | null;
		volume_size: string | null;
		package_type: string | null;
		sale_price: number | null;
		original_price: number | null;
		is_special: boolean;
		cup_price: number | null;
		cup_measure: string | null;
		unit: string | null;
		availability: string | null;
		image_url: string | null;
	}

	/** The full product record from Woolworths — passed through to be saved as-is. */
	export interface FullSku {
		provider: string;
		sku: string;
		name: string;
		brand: string | null;
		variety: string | null;
		price: { sale_price: number | null; original_price: number | null; is_special: boolean };
		size: { volume_size: string | null; cup_price: number | null; cup_measure: string | null };
		images: string[];
		allergens: string[];
		[more: string]: unknown;
	}

	export interface Chosen {
		code: string;
		hit: Hit | null;
		status: 'loading' | 'ready' | 'error';
		error: string | null;
		sku: FullSku | null;
	}

	export interface WizItem {
		/** The lowercase name this item had when the wizard started — how rows find it again. */
		key: string;
		name: string;
		lines: string[];
		perishable: boolean;
		chosen: Chosen[];
		query: string;
		hits: Hit[] | null;
		searching: boolean;
		searchError: string | null;
		manual: string;
		manualError: string | null;
		manualBusy: boolean;
	}
</script>

<script lang="ts">
	import { invoke } from '@tauri-apps/api/core';
	import { untrack } from 'svelte';

	let {
		items = $bindable(),
		existingNames,
		saving,
		error,
		onback,
		ondone
	}: {
		items: WizItem[];
		existingNames: Set<string>;
		saving: boolean;
		error: string | null;
		onback: () => void;
		ondone: () => void;
	} = $props();

	let index = $state(0);
	let item = $derived(items[index]);
	let isLast = $derived(index === items.length - 1);

	const money = (n: number | null) => (n == null ? '—' : `$${n.toFixed(2)}`);
	const titleCase = (s: string) => s.replace(/\b\w/g, (c) => c.toUpperCase());

	// A name that is already in the pantry means this line will simply use that
	// item — there is nothing to set up, so the product search is switched off.
	let alreadyExists = $derived(!!item && existingNames.has(item.name.trim().toLowerCase()));

	async function search(it: WizItem) {
		const q = it.query.trim();
		if (!q || it.searching) return;
		it.searching = true;
		it.searchError = null;
		try {
			it.hits = await invoke<Hit[]>('search_woolworths', { query: q });
		} catch (e) {
			it.searchError = String(e);
		} finally {
			it.searching = false;
		}
	}

	// Search once when a step is first opened. Typing alone never searches
	// (Enter or the button does), so Woolworths isn't hit on every keystroke.
	$effect(() => {
		const i = index;
		untrack(() => {
			const it = items[i];
			if (it && it.hits === null && !it.searching && !it.searchError && !existingNames.has(it.name.trim().toLowerCase())) {
				search(it);
			}
		});
	});

	async function loadFull(entry: Chosen) {
		entry.status = 'loading';
		entry.error = null;
		try {
			entry.sku = await invoke<FullSku>('fetch_woolworths_sku', { input: entry.code });
			entry.status = 'ready';
		} catch (e) {
			entry.error = String(e);
			entry.status = 'error';
		}
	}

	async function toggle(it: WizItem, hit: Hit) {
		const already = it.chosen.find((c) => c.code === hit.sku);
		if (already) {
			it.chosen = it.chosen.filter((c) => c.code !== hit.sku);
			return;
		}
		it.chosen = [...it.chosen, { code: hit.sku, hit, status: 'loading', error: null, sku: null }];
		// The array now holds a reactive copy; load into *that*, not the original.
		await loadFull(it.chosen[it.chosen.length - 1]);
	}

	function remove(it: WizItem, code: string) {
		it.chosen = it.chosen.filter((c) => c.code !== code);
	}

	async function addManual(it: WizItem) {
		const input = it.manual.trim();
		if (!input || it.manualBusy) return;
		it.manualBusy = true;
		it.manualError = null;
		try {
			const sku = await invoke<FullSku>('fetch_woolworths_sku', { input });
			if (it.chosen.some((c) => c.code === sku.sku)) {
				it.manualError = 'That product is already added.';
			} else {
				it.chosen = [...it.chosen, { code: sku.sku, hit: null, status: 'ready', error: null, sku }];
				it.manual = '';
			}
		} catch (e) {
			it.manualError = String(e);
		} finally {
			it.manualBusy = false;
		}
	}

	let blocker = $derived.by(() => {
		if (!item) return null;
		if (!item.name.trim()) return 'Give the item a name.';
		if (item.chosen.some((c) => c.status === 'loading')) return 'Waiting for product details…';
		if (item.chosen.some((c) => c.status === 'error')) return 'Remove or retry the product that failed to load.';
		return null;
	});

	function next() {
		if (blocker) return;
		if (isLast) ondone();
		else index += 1;
	}

	function back() {
		if (index === 0) onback();
		else index -= 1;
	}
</script>

{#if item}
	<div class="wizard">
		<div class="progress">
			<span class="count">Item {index + 1} of {items.length}</span>
			<span class="dots" aria-hidden="true">
				{#each items as _, i}<span class="dot" class:done={i < index} class:here={i === index}></span>{/each}
			</span>
		</div>

		<p class="from">
			For {item.lines.length === 1 ? 'this line' : 'these lines'} of the recipe:
			<span class="lines">{item.lines.join(' · ')}</span>
		</p>

		<div class="basics">
			<label class="field grow">
				<span>Item name</span>
				<input type="text" bind:value={item.name} />
			</label>
			<label class="check">
				<input type="checkbox" bind:checked={item.perishable} />
				<span>
					<strong>Perishable</strong>
					<small>Tick for fresh things. Untick for salt, spices, tins: they're left off the shopping list when this recipe is added to one.</small>
				</span>
			</label>
		</div>

		{#if alreadyExists}
			<p class="notice">
				You already have “{item.name.trim()}” in your pantry, so this line will use that item. Nothing new is
				created and no product is added.
			</p>
		{:else}
			<h5>Woolworths products</h5>

			{#if item.chosen.length}
				<ul class="chosen" aria-label="Chosen products">
					{#each item.chosen as c (c.code)}
						{@const shown = c.sku ?? c.hit}
						<li>
							{#if (c.hit?.image_url ?? c.sku?.images?.[0]) != null}
								<img src={c.hit?.image_url ?? c.sku?.images?.[0]} alt="" />
							{:else}
								<span class="noimg"></span>
							{/if}
							<div class="info">
								<span class="pname">{titleCase(shown?.name ?? c.code)}</span>
								<span class="sub">
									{c.hit?.volume_size ?? c.sku?.size?.volume_size ?? ''}
									· {money(c.hit?.sale_price ?? c.sku?.price?.sale_price ?? null)}
									· sku {c.code}
								</span>
								{#if c.status === 'loading'}
									<span class="muted">Loading details…</span>
								{:else if c.status === 'error'}
									<span class="bad">{c.error} <button class="link" onclick={() => loadFull(c)}>Retry</button></span>
								{:else if c.sku && c.sku.allergens.length}
									<span class="allergens">⚠ {c.sku.allergens.join(', ')}</span>
								{:else}
									<span class="muted">No allergens listed</span>
								{/if}
							</div>
							<button class="x" aria-label="Remove this product" onclick={() => remove(item, c.code)}>✕</button>
						</li>
					{/each}
				</ul>
			{/if}

			<form
				class="search-row"
				onsubmit={(e) => {
					e.preventDefault();
					search(item);
				}}
			>
				<input type="text" placeholder="Search Woolworths…" aria-label="Search Woolworths" bind:value={item.query} />
				<button class="secondary" type="submit" disabled={!item.query.trim() || item.searching}>
					{item.searching ? 'Searching…' : 'Search'}
				</button>
			</form>

			{#if item.searchError}
				<p class="bad">{item.searchError}</p>
			{:else if item.hits && item.hits.length === 0}
				<p class="muted">Nothing found for “{item.query.trim()}”. Try a simpler word, or paste a link below.</p>
			{/if}

			{#if item.hits && item.hits.length}
				<ul class="hits" aria-label="Search results">
					{#each item.hits as hit (hit.sku)}
						{@const picked = item.chosen.some((c) => c.code === hit.sku)}
						<li>
							<button class="hit" class:picked onclick={() => toggle(item, hit)} aria-pressed={picked}>
								{#if hit.image_url}<img src={hit.image_url} alt="" />{:else}<span class="noimg"></span>{/if}
								<span class="info">
									<span class="pname">{titleCase(hit.name)}</span>
									<span class="sub">
										{[hit.brand ? titleCase(hit.brand) : null, hit.volume_size].filter(Boolean).join(' · ')}
										{#if hit.availability && !/in stock/i.test(hit.availability)}
											<span class="bad">· {hit.availability}</span>
										{/if}
									</span>
								</span>
								<span class="price">
									<span class:special={hit.is_special}>{money(hit.sale_price)}</span>
									{#if hit.is_special && hit.original_price != null}
										<s>{money(hit.original_price)}</s>
									{/if}
									{#if hit.cup_price != null && hit.cup_measure}
										<small>${hit.cup_price.toFixed(2)}/{hit.cup_measure}</small>
									{/if}
								</span>
								<span class="tick" aria-hidden="true">{picked ? '✓' : ''}</span>
							</button>
						</li>
					{/each}
				</ul>
			{/if}

			<form
				class="manual"
				onsubmit={(e) => {
					e.preventDefault();
					addManual(item);
				}}
			>
				<input
					type="text"
					placeholder="Or paste a Woolworths product link or stock code"
					aria-label="Product link or stock code"
					bind:value={item.manual}
				/>
				<button class="secondary" type="submit" disabled={!item.manual.trim() || item.manualBusy}>
					{item.manualBusy ? 'Adding…' : 'Add'}
				</button>
			</form>
			{#if item.manualError}<p class="bad">{item.manualError}</p>{/if}
		{/if}

		{#if error}
			<p class="bad" role="alert">{error}</p>
		{/if}

		<div class="footer">
			<button class="secondary" onclick={back} disabled={saving}>← Back</button>
			<span class="hint">
				{#if blocker}{blocker}{:else if !alreadyExists && item.chosen.length === 0}No product chosen: the item is created without a SKU, and you can add one later.{/if}
			</span>
			<button class="go" onclick={next} disabled={!!blocker || saving}>
				{#if isLast}
					{saving ? 'Creating…' : 'Create recipe'}
				{:else if !alreadyExists && item.chosen.length === 0}
					Next without a product →
				{:else}
					Next →
				{/if}
			</button>
		</div>
	</div>
{/if}

<style>
	.wizard {
		display: flex;
		flex-direction: column;
	}

	.progress {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 0.75rem;
	}

	.count {
		color: #999;
		font-size: 0.8rem;
		font-weight: bold;
	}

	.dots {
		display: flex;
		gap: 0.35rem;
	}

	.dot {
		width: 0.55rem;
		height: 0.55rem;
		border-radius: 50%;
		background: #3a3a39;
	}

	.dot.done {
		background: #5f9b46;
	}

	.dot.here {
		background: #fff;
	}

	.from {
		margin: 0 0 1rem;
		color: #999;
		font-size: 0.82rem;
		line-height: 1.5;
	}

	.lines {
		color: #ddd;
		overflow-wrap: anywhere;
	}

	.basics {
		display: flex;
		gap: 1.25rem;
		align-items: flex-start;
		flex-wrap: wrap;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		font-size: 0.75rem;
		color: #999;
	}

	.field.grow {
		flex: 1 1 14rem;
	}

	input[type='text'] {
		box-sizing: border-box;
		width: 100%;
		background: #1e1e1d;
		border: 1px solid #444;
		border-radius: 6px;
		color: #fff;
		font-size: 0.9rem;
		padding: 0.55rem 0.7rem;
	}

	input[type='text']:focus {
		outline: none;
		border-color: #3a4a55;
	}

	.check {
		display: flex;
		gap: 0.6rem;
		align-items: flex-start;
		flex: 1 1 18rem;
		font-size: 0.85rem;
		cursor: pointer;
	}

	.check input {
		margin-top: 0.2rem;
	}

	.check small {
		display: block;
		margin-top: 0.15rem;
		color: #888;
		font-size: 0.75rem;
		line-height: 1.4;
	}

	h5 {
		margin: 1.4rem 0 0.6rem;
		color: #999;
		font-size: 0.75rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}

	.notice {
		margin: 1.2rem 0 0;
		padding: 0.75rem 0.9rem;
		background: #2b3d4a;
		border-radius: 8px;
		color: #cfe3f1;
		font-size: 0.85rem;
		line-height: 1.5;
	}

	.search-row,
	.manual {
		display: flex;
		gap: 0.6rem;
		margin-top: 0.6rem;
	}

	.manual {
		margin-top: 1rem;
		padding-top: 1rem;
		border-top: 1px solid #333;
	}

	.hits,
	.chosen {
		list-style: none;
		margin: 0.6rem 0 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.hits {
		max-height: 19rem;
		overflow-y: auto;
		padding-right: 0.2rem;
	}

	.chosen li {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.5rem 0.7rem;
		background: #2a3a26;
		border: 1px solid #3f5a36;
		border-radius: 8px;
	}

	.hit {
		width: 100%;
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.45rem 0.7rem;
		background: #1e1e1d;
		border: 1px solid #333;
		border-radius: 8px;
		color: #fff;
		text-align: left;
		cursor: pointer;
	}

	.hit:hover {
		border-color: #3a4a55;
	}

	.hit.picked {
		border-color: #5f9b46;
		background: #232d20;
	}

	img,
	.noimg {
		flex: 0 0 auto;
		width: 2.75rem;
		height: 2.75rem;
		border-radius: 6px;
		object-fit: contain;
		background: #fff;
	}

	.noimg {
		background: #2c2c2b;
	}

	.info {
		flex: 1 1 auto;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.pname {
		font-size: 0.88rem;
		font-weight: bold;
		overflow-wrap: anywhere;
	}

	.sub {
		color: #999;
		font-size: 0.75rem;
	}

	.price {
		flex: 0 0 auto;
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		font-size: 0.88rem;
		font-weight: bold;
	}

	.price small {
		color: #888;
		font-weight: normal;
		font-size: 0.7rem;
	}

	.price s {
		color: #ff8a80;
		font-weight: normal;
		font-size: 0.72rem;
	}

	.price .special {
		color: #7fc46a;
	}

	.tick {
		flex: 0 0 1.2rem;
		color: #7fc46a;
		font-weight: bold;
		text-align: center;
	}

	.x {
		flex: 0 0 auto;
		background: none;
		border: none;
		color: #999;
		cursor: pointer;
		font-size: 0.95rem;
	}

	.allergens {
		color: var(--color-warning, #c99a3d);
		font-size: 0.75rem;
		font-weight: bold;
	}

	.muted {
		color: #888;
		font-size: 0.78rem;
	}

	.bad {
		margin: 0.6rem 0 0;
		color: #ff8a80;
		font-size: 0.8rem;
	}

	.sub .bad,
	.info .bad {
		margin: 0;
	}

	.link {
		background: none;
		border: none;
		color: #cdd8df;
		font-size: 0.78rem;
		text-decoration: underline;
		cursor: pointer;
		padding: 0;
	}

	.secondary {
		flex: 0 0 auto;
		background: none;
		border: 1px solid #555;
		border-radius: 6px;
		color: #fff;
		font-weight: bold;
		font-size: 0.85rem;
		padding: 0.5rem 1rem;
		cursor: pointer;
	}

	.go {
		flex: 0 0 auto;
		background: var(--color-good, #5f9b46);
		border: none;
		border-radius: 6px;
		color: #fff;
		font-weight: bold;
		font-size: 0.85rem;
		padding: 0.6rem 1.1rem;
		cursor: pointer;
	}

	.go:disabled,
	.secondary:disabled {
		opacity: 0.5;
		cursor: default;
	}

	.footer {
		position: sticky;
		bottom: -1.5rem;
		display: flex;
		align-items: center;
		gap: 0.9rem;
		margin: 1.25rem -1.5rem -1.5rem;
		padding: 0.9rem 1.5rem;
		background: #232322;
		border-top: 1px solid #333;
	}

	.hint {
		flex: 1 1 auto;
		color: #888;
		font-size: 0.75rem;
	}
</style>
