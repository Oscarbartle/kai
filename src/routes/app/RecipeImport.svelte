<!--
	"Import a recipe from a website".
	  1. Paste a link, see the recipe the page carries (nothing saved).
	  2. Review: every ingredient line is split into amount/unit/name and given a
	     best-guess Pantry item. Nothing is final — each line can point at a
	     different item, become a new item, or be skipped, and amounts are
	     editable. Only "Create recipe" saves, and it saves everything or nothing.
	The supported-sites list comes from the importer itself
	(list_supported_recipe_sites), so what is shown is exactly what it accepts.
-->
<script lang="ts">
	import { invoke } from '@tauri-apps/api/core';
	import { onMount } from 'svelte';
	import { openUrl } from '@tauri-apps/plugin-opener';
	import ItemPicker from './ItemPicker.svelte';
	import NewItemWizard, { type WizItem } from './NewItemWizard.svelte';

	interface SupportedSite {
		name: string;
		domains: string[];
		example_url: string;
		note: string | null;
	}

	interface RecipeDraft {
		site: string;
		source_url: string;
		name: string;
		image_url: string | null;
		servings: number | null;
		yield_text: string | null;
		ingredient_lines: string[];
		steps: string[];
	}

	interface Suggestion {
		item_id: number;
		name: string;
		score: number;
	}

	interface AnalyzedLine {
		raw: string;
		amount: number | null;
		unit: string | null;
		unresolved_quantity: string | null;
		note: string | null;
		name: string;
		confidence: 'strong' | 'check' | 'none';
		suggestions: Suggestion[];
		/** The top suggestion is what the user chose for this wording before. */
		learned: boolean;
		/** The name looks like a pantry staple — the default for "perishable". */
		likely_non_perishable: boolean;
	}

	interface Analysis {
		rows: AnalyzedLine[];
		items: { id: number; name: string }[];
	}

	// What the review table edits: the analysis plus the user's choices.
	interface Row extends AnalyzedLine {
		choice: string; // 'item:<id>' | 'new' | 'skip'
		newName: string;
		amountText: string;
		unitChoice: string; // '' | g | mL | count | tsp | tbsp
	}

	const UNITS = ['g', 'mL', 'count', 'tsp', 'tbsp'];

	let { onClose, onCreated }: { onClose: () => void; onCreated: (recipeId: number) => void } =
		$props();

	let sites: SupportedSite[] = $state([]);
	let url = $state('');
	let status: 'idle' | 'loading' | 'done' | 'error' = $state('idle');
	let draft: RecipeDraft | null = $state(null);
	let error: string | null = $state(null);
	let imageBroken = $state(false);
	// With a recipe showing the site list is out of the way; this brings it back.
	let sitesOpen = $state(false);

	let step: 'preview' | 'review' | 'wizard' = $state('preview');
	let wizItems: WizItem[] = $state([]);
	let allTags: string[] = $state([]);
	let analyzing = $state(false);
	let saving = $state(false);
	let items: { id: number; name: string }[] = $state([]);
	let rows: Row[] = $state([]);
	let recipeName = $state('');
	let servingsText = $state('');
	let reviewError: string | null = $state(null);

	// A slow fetch must not overwrite the result of a newer one.
	let latestRequest = 0;

	onMount(async () => {
		try {
			sites = await invoke<SupportedSite[]>('list_supported_recipe_sites');
		} catch (e) {
			error = String(e);
		}
	});

	// A site chip takes you to that site, in your own browser, to find a recipe;
	// you then paste its link here. (The site's front page, taken from its
	// example link so it is always an address known to work.)
	async function openSite(site: SupportedSite) {
		try {
			await openUrl(`${new URL(site.example_url).origin}/`);
		} catch (e) {
			error = `Couldn't open ${site.name}: ${String(e)}`;
		}
	}

	async function fetchPreview() {
		if (!url.trim() || status === 'loading') return;
		const request = ++latestRequest;
		status = 'loading';
		error = null;
		draft = null;
		imageBroken = false;
		sitesOpen = false;
		step = 'preview';
		try {
			const result = await invoke<RecipeDraft>('preview_recipe_from_url', { url });
			if (request !== latestRequest) return;
			draft = result;
			status = 'done';
		} catch (e) {
			if (request !== latestRequest) return;
			error = String(e);
			status = 'error';
		}
	}

	const tidy = (n: number) => String(Math.round(n * 1000) / 1000);

	async function startReview() {
		if (!draft || analyzing) return;
		analyzing = true;
		reviewError = null;
		try {
			const analysis = await invoke<Analysis>('analyze_import_ingredients', {
				lines: draft.ingredient_lines
			});
			items = analysis.items;
			recipeName = draft.name;
			servingsText = draft.servings != null ? String(draft.servings) : '';
			rows = analysis.rows.map((r) => ({
				...r,
				// The best guess is preselected when it is good enough; a line with
				// nothing convincing starts as "skip" so nothing is created or
				// linked unless the user chooses it.
				choice:
					r.confidence !== 'none' && r.suggestions.length > 0
						? `item:${r.suggestions[0].item_id}`
						: 'skip',
				newName: r.name,
				amountText: r.amount != null ? tidy(r.amount) : '',
				unitChoice: r.unit ?? ''
			}));
			step = 'review';
		} catch (e) {
			error = String(e);
		} finally {
			analyzing = false;
		}
	}

	function chosenItemId(row: Row): number | null {
		return row.choice.startsWith('item:') ? Number(row.choice.slice(5)) : null;
	}

	function chip(row: Row): { text: string; kind: string } {
		if (row.choice === 'skip') return { text: 'Skipped', kind: 'skip' };
		if (row.choice === 'new') return { text: 'New item', kind: 'new' };
		const best = row.suggestions[0];
		if (best && chosenItemId(row) === best.item_id) {
			if (row.learned) return { text: '✓ Remembered', kind: 'good' };
			if (row.confidence === 'strong') return { text: '✓ Match', kind: 'good' };
			if (row.confidence === 'check') return { text: '? Check', kind: 'check' };
		}
		return { text: 'Your pick', kind: 'good' };
	}

	// Lines that end up on the same item are merged on save.
	function targetKey(row: Row): string | null {
		const id = chosenItemId(row);
		if (id != null) return `item:${id}`;
		if (row.choice === 'new' && row.newName.trim()) return `new:${row.newName.trim().toLowerCase()}`;
		return null;
	}

	let sharedTargets = $derived.by(() => {
		const counts = new Map<string, number>();
		for (const r of rows) {
			const k = targetKey(r);
			if (k) counts.set(k, (counts.get(k) ?? 0) + 1);
		}
		return counts;
	});

	let summary = $derived({
		matched: rows.filter((r) => r.choice.startsWith('item:')).length,
		created: rows.filter((r) => r.choice === 'new').length,
		skipped: rows.filter((r) => r.choice === 'skip').length,
		toCheck: rows.filter((r) => chip(r).kind === 'check').length,
		blankAmounts: rows.filter((r) => r.choice !== 'skip' && r.unresolved_quantity && !r.amountText.trim()).length
	});

	// Names already in the pantry: a "new item" with one of these just uses that item.
	let existingNames = $derived(new Set(items.map((i) => i.name.trim().toLowerCase())));

	const keyOf = (row: Row) => row.newName.trim().toLowerCase();

	// The ingredients that need setting up as brand-new items, one entry per name
	// (two lines for "tamari" are one item).
	let newGroups = $derived.by(() => {
		const groups = new Map<string, { key: string; name: string; lines: string[]; staple: boolean }>();
		for (const r of rows) {
			if (r.choice !== 'new' || !r.newName.trim()) continue;
			const key = keyOf(r);
			if (existingNames.has(key)) continue; // will reuse the existing item
			const g = groups.get(key);
			if (g) {
				g.lines.push(r.raw);
				g.staple = g.staple || r.likely_non_perishable;
			} else {
				groups.set(key, { key, name: r.newName.trim(), lines: [r.raw], staple: r.likely_non_perishable });
			}
		}
		return [...groups.values()];
	});

	/** The problem with the review table as it stands, or null if it can be saved. */
	function validateReview(): string | null {
		for (const r of rows.filter((r) => r.choice !== 'skip')) {
			const amount = r.amountText.trim();
			if (amount !== '' && (!Number.isFinite(Number(amount)) || Number(amount) <= 0)) {
				return `“${r.raw}”: the amount must be a number above zero, or left blank.`;
			}
			if (amount !== '' && !r.unitChoice) {
				return `“${r.raw}”: pick a unit for the amount, or clear the amount.`;
			}
			if (r.choice === 'new' && !r.newName.trim()) {
				return `“${r.raw}”: give the new item a name, or choose another option.`;
			}
		}
		const servings = servingsText.trim();
		if (servings !== '' && !(Number.isInteger(Number(servings)) && Number(servings) > 0)) {
			return 'Servings must be a whole number, or left blank.';
		}
		return null;
	}

	// Review → wizard. Work already done on an item (products picked, name
	// changed) is kept if the user goes back and forward again.
	async function goToWizard() {
		reviewError = validateReview();
		if (reviewError) return;
		// Existing tags, offered as suggestions. Not essential: a failure just
		// means no suggestions.
		try {
			allTags = (await invoke<{ name: string }[]>('list_tags')).map((t) => t.name);
		} catch {
			allTags = [];
		}
		wizItems = newGroups.map(
			(g) =>
				wizItems.find((w) => w.key === g.key) ?? {
					key: g.key,
					name: g.name,
					lines: g.lines,
					// A pantry staple (salt, a spice, a sauce, a tin) starts unticked;
					// it is only a guess and the wizard says so.
					perishable: !g.staple,
					guessedStaple: g.staple,
					tags: [],
					tagInput: '',
					preferred: null,
					chosen: [],
					query: g.name,
					hits: null,
					searching: false,
					searchError: null,
					manual: '',
					manualError: null,
					manualBusy: false
				}
		);
		step = 'wizard';
	}

	// Remember this wording → this item, but only when a person made the call:
	// not a sure match that was simply accepted, and not one already remembered.
	function learnName(row: Row): string | null {
		const id = chosenItemId(row);
		const best = row.suggestions[0];
		if (id == null || !row.name.trim()) return null;
		if (best && id === best.item_id && (row.learned || row.confidence === 'strong')) return null;
		return row.name.trim();
	}

	async function createRecipe() {
		if (saving) return;
		reviewError = validateReview();
		if (reviewError) {
			step = 'review';
			return;
		}
		const chosen = rows.filter((r) => r.choice !== 'skip');
		const servings = servingsText.trim();

		saving = true;
		try {
			const outcome = await invoke<{ recipe_id: number; created_items: string[] }>(
				'create_recipe_from_import',
				{
					request: {
						name: recipeName,
						source_url: draft?.source_url ?? '',
						image_url: draft?.image_url ?? null,
						servings: servings === '' ? null : Number(servings),
						steps: draft?.steps ?? [],
						ingredients: chosen.map((r) => {
							const wiz = r.choice === 'new' ? wizItems.find((w) => w.key === keyOf(r)) : undefined;
							return {
								item_id: chosenItemId(r),
								// The wizard may have renamed it.
								new_item_name: r.choice === 'new' ? (wiz?.name.trim() || r.newName.trim()) : null,
								new_item_perishable: wiz ? wiz.perishable : null,
								new_item_tags: wiz ? wiz.tags : [],
								new_item_preferred_sku:
									wiz?.preferred && wiz.chosen.some((c) => c.code === wiz.preferred && c.status === 'ready')
										? wiz.preferred
										: null,
								learn_name: r.choice === 'new' ? null : learnName(r),
								new_item_skus: wiz
									? wiz.chosen.filter((c) => c.status === 'ready' && c.sku).map((c) => c.sku)
									: [],
								amount: r.amountText.trim() === '' ? null : Number(r.amountText),
								unit: r.amountText.trim() === '' ? null : r.unitChoice
							};
						})
					}
				}
			);
			onCreated(outcome.recipe_id);
		} catch (e) {
			reviewError = String(e);
		} finally {
			saving = false;
		}
	}
</script>

<div
	class="overlay"
	onclick={onClose}
	onkeydown={(e) => e.key === 'Escape' && onClose()}
	role="presentation"
>
	<div
		class="box"
		class:wide={step !== 'preview'}
		onclick={(e) => e.stopPropagation()}
		onkeydown={(e) => e.stopPropagation()}
		role="dialog"
		aria-modal="true"
		aria-label="Import a recipe from a website"
		tabindex="-1"
	>
		<div class="head">
			<h3>
				{step === 'review' ? 'Review the ingredients' : step === 'wizard' ? 'Set up the new items' : 'Import a recipe from a website'}
			</h3>
			<button class="close" onclick={onClose} aria-label="Close">✕</button>
		</div>

		{#if step === 'preview'}
			<form
				class="url-row"
				onsubmit={(e) => {
					e.preventDefault();
					fetchPreview();
				}}
			>
				<input
					class="url-input"
					type="text"
					placeholder="Paste a recipe link, e.g. https://www.bbcgoodfood.com/recipes/easy-pancakes"
					aria-label="Recipe link"
					bind:value={url}
				/>
				<button class="go" type="submit" disabled={!url.trim() || status === 'loading'}>
					{status === 'loading' ? 'Fetching…' : 'Fetch recipe'}
				</button>
			</form>

			{#if draft}
				<button class="sites-toggle" onclick={() => (sitesOpen = !sitesOpen)}>
					{sitesOpen ? 'Hide' : 'Show'} supported sites
				</button>
			{/if}

			{#if !draft || sitesOpen}
			<div class="sites">
				<span class="sites-label">Supported sites</span>
				{#each sites as site (site.name)}
					<button
						class="site"
						title="Open {site.name} in your browser to find a recipe"
						onclick={() => openSite(site)}
					>
						{site.name}
						<span class="domain">{site.domains[0]}</span>
						{#if site.note}<span class="site-note">· {site.note}</span>{/if}
						<span class="out" aria-hidden="true">↗</span>
					</button>
				{/each}
				<span class="sites-note">
					Click a site to browse it in your browser, then paste a recipe's link above. More can be added once
					they've been checked.
				</span>
			</div>
			{/if}

			{#if error}
				<p class="error" role="alert">{error}</p>
			{/if}

			{#if draft}
				<div class="preview">
					<div class="top">
						{#if draft.image_url && !imageBroken}
							<img
								class="photo"
								src={draft.image_url}
								alt=""
								onerror={() => (imageBroken = true)}
							/>
						{/if}
						<div class="titles">
							<h4>{draft.name}</h4>
							<p class="meta">
								{#if draft.servings != null}Serves {draft.servings} ·{/if}
								{#if draft.yield_text}“{draft.yield_text}” ·{/if}
								{draft.ingredient_lines.length} ingredients ·
								{draft.steps.length} step{draft.steps.length === 1 ? '' : 's'} · from {draft.site}
							</p>
							<button class="go next" onclick={startReview} disabled={analyzing}>
								{analyzing ? 'Matching…' : 'Match ingredients to my pantry →'}
							</button>
						</div>
					</div>

					<div class="cols">
						<section>
							<h5>Ingredients</h5>
							<ul>
								{#each draft.ingredient_lines as line}
									<li>{line}</li>
								{/each}
							</ul>
						</section>
						<section>
							<h5>Method</h5>
							{#if draft.steps.length === 0}
								<p class="none">This page doesn't include a method.</p>
							{:else}
								<ol>
									{#each draft.steps as step}
										<li>{step}</li>
									{/each}
								</ol>
							{/if}
						</section>
					</div>

					<p class="note">Nothing is saved until you create the recipe on the next screen.</p>
				</div>
			{/if}
		{:else if step === 'wizard'}
			<NewItemWizard
				bind:items={wizItems}
				{existingNames}
				{allTags}
				{saving}
				error={reviewError}
				onback={() => {
					reviewError = null;
					step = 'review';
				}}
				ondone={createRecipe}
			/>
		{:else}
			<div class="recipe-fields">
				<label class="field grow">
					<span>Recipe name</span>
					<input type="text" bind:value={recipeName} />
				</label>
				<label class="field servings">
					<span>Servings</span>
					<input type="text" inputmode="numeric" placeholder="—" bind:value={servingsText} />
				</label>
			</div>

			<p class="summary">
				{summary.matched} matched to pantry items
				{#if summary.toCheck > 0}({summary.toCheck} worth checking){/if}
				· {summary.created} new · {summary.skipped} skipped
				{#if summary.blankAmounts > 0}
					· <span class="amber">{summary.blankAmounts} without an amount</span>
				{/if}
			</p>

			<div class="table" role="table" aria-label="Ingredients">
				<div class="table-head" role="row">
					<span>From the recipe</span>
					<span>Amount</span>
					<span>Unit</span>
					<span>Pantry item</span>
				</div>
				{#each rows as row, i (i)}
					{@const c = chip(row)}
					{@const key = targetKey(row)}
					<div class="line" class:skipped={row.choice === 'skip'} role="row">
						<div class="orig">
							<span class="raw">{row.raw}</span>
							{#if row.unresolved_quantity}
								<span class="amber small">
									The recipe says “{row.unresolved_quantity}” — enter grams/mL (or tsp/tbsp/count) below, or
									leave it blank.
								</span>
							{:else if row.note}
								<span class="muted small">{row.note}</span>
							{/if}
						</div>
						<input
							class="amount"
							type="text"
							inputmode="decimal"
							placeholder="—"
							aria-label="Amount for {row.raw}"
							bind:value={row.amountText}
							disabled={row.choice === 'skip'}
						/>
						<select
							class="unit"
							aria-label="Unit for {row.raw}"
							bind:value={row.unitChoice}
							disabled={row.choice === 'skip'}
						>
							<option value="">—</option>
							{#each UNITS as u}
								<option value={u}>{u}</option>
							{/each}
						</select>
						<div class="pick">
							<ItemPicker
								value={row.choice}
								suggestions={row.suggestions}
								{items}
								label="Pantry item for {row.raw}"
								onpick={(choice, newName) => {
									row.choice = choice;
									if (newName) row.newName = newName;
								}}
							/>
							<span class="chip {c.kind}">{c.text}</span>
							{#if row.choice === 'new'}
								<input
									class="newname"
									type="text"
									placeholder="Name of the new item"
									aria-label="Name of the new item for {row.raw}"
									bind:value={row.newName}
								/>
							{/if}
							{#if key && (sharedTargets.get(key) ?? 0) > 1}
								<span class="muted small">
									Same item as another line — amounts are added together when their units match.
								</span>
							{/if}
						</div>
					</div>
				{/each}
			</div>

			{#if reviewError}
				<p class="error" role="alert">{reviewError}</p>
			{/if}

			<div class="footer">
				<button class="secondary" onclick={() => (step = 'preview')} disabled={saving}>← Back</button>
				<span class="footer-note">
					{#if newGroups.length > 0}
						{newGroups.length} new item{newGroups.length === 1 ? '' : 's'} to set up next: name, perishable, and a
						Woolworths product.
					{/if}
				</span>
				{#if newGroups.length > 0}
					<button class="go" onclick={goToWizard} disabled={saving || !recipeName.trim()}>
						Next: set up {newGroups.length} new item{newGroups.length === 1 ? '' : 's'} →
					</button>
				{:else}
					<button class="go" onclick={createRecipe} disabled={saving || !recipeName.trim()}>
						{saving ? 'Creating…' : `Create recipe (${rows.length - summary.skipped} ingredients)`}
					</button>
				{/if}
			</div>
		{/if}
	</div>
</div>

<style>
	.overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
	}

	.box {
		background: #232322;
		border-radius: 12px;
		padding: 1.25rem 1.5rem 1.5rem;
		width: 860px;
		max-width: calc(100% - 2rem);
		max-height: calc(100% - 3rem);
		overflow-y: auto;
		box-sizing: border-box;
		color: #fff;
	}

	.box.wide {
		width: 1100px;
	}

	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 1rem;
	}

	h3 {
		margin: 0;
		font-size: 1.1rem;
	}

	.close {
		background: none;
		border: none;
		color: #999;
		font-size: 1rem;
		cursor: pointer;
	}

	.url-row {
		display: flex;
		gap: 0.6rem;
	}

	.url-input {
		flex: 1 1 auto;
		min-width: 0;
		background: #1e1e1d;
		border: 1px solid #444;
		border-radius: 6px;
		color: #fff;
		font-size: 0.9rem;
		padding: 0.6rem 0.75rem;
	}

	input:focus,
	select:focus {
		outline: none;
		border-color: #3a4a55;
	}

	.go {
		flex: 0 0 auto;
		background: #3a4a55;
		border: none;
		border-radius: 6px;
		color: #fff;
		font-weight: bold;
		font-size: 0.85rem;
		padding: 0.6rem 1.1rem;
		cursor: pointer;
	}

	.go.next {
		margin-top: 0.9rem;
		background: var(--color-good, #5f9b46);
	}

	.go:disabled,
	.secondary:disabled {
		opacity: 0.5;
		cursor: default;
	}

	.secondary {
		background: none;
		border: 1px solid #555;
		border-radius: 6px;
		color: #fff;
		font-weight: bold;
		font-size: 0.85rem;
		padding: 0.55rem 1rem;
		cursor: pointer;
	}

	.sites {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.9rem;
	}

	.sites-toggle {
		margin-top: 0.7rem;
		padding: 0;
		background: none;
		border: none;
		color: #999;
		font-size: 0.78rem;
		text-decoration: underline;
		cursor: pointer;
	}

	.sites-label {
		color: #999;
		font-size: 0.75rem;
		font-weight: bold;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		margin-right: 0.2rem;
	}

	.site {
		background: #1e1e1d;
		border: 1px solid #444;
		border-radius: 999px;
		color: #fff;
		font-size: 0.8rem;
		font-weight: bold;
		padding: 0.3rem 0.8rem;
		cursor: pointer;
	}

	.site:hover {
		border-color: #3a4a55;
	}

	.domain {
		color: #999;
		font-weight: normal;
		margin-left: 0.3rem;
	}

	.out {
		color: #999;
		margin-left: 0.3rem;
		font-weight: normal;
	}

	.site-note {
		color: var(--color-warning, #c99a3d);
		font-weight: normal;
		margin-left: 0.2rem;
	}

	.sites-note {
		color: #777;
		font-size: 0.75rem;
	}

	.error {
		margin: 1rem 0 0;
		color: #ff8a80;
		font-size: 0.85rem;
	}

	.preview {
		margin-top: 1.25rem;
		padding-top: 1.1rem;
		border-top: 1px solid #333;
	}

	.top {
		display: flex;
		gap: 1rem;
		align-items: flex-start;
	}

	.photo {
		flex: 0 0 auto;
		width: 11rem;
		aspect-ratio: 4 / 3;
		object-fit: cover;
		border-radius: 8px;
		background: #1e1e1d;
	}

	.titles {
		min-width: 0;
	}

	h4 {
		margin: 0 0 0.4rem;
		font-size: 1.25rem;
		overflow-wrap: anywhere;
	}

	.meta {
		margin: 0;
		color: #999;
		font-size: 0.8rem;
		line-height: 1.5;
	}

	.cols {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr);
		gap: 1.5rem;
		margin-top: 1.25rem;
	}

	@media (max-width: 760px) {
		.cols {
			grid-template-columns: minmax(0, 1fr);
		}
	}

	h5 {
		margin: 0 0 0.5rem;
		color: #999;
		font-size: 0.75rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}

	ul,
	ol {
		margin: 0;
		padding-left: 1.2rem;
		font-size: 0.88rem;
		line-height: 1.55;
	}

	li {
		margin-bottom: 0.35rem;
		overflow-wrap: anywhere;
	}

	.none {
		margin: 0;
		color: #999;
		font-size: 0.85rem;
	}

	.note {
		margin: 1.25rem 0 0;
		color: #999;
		font-size: 0.8rem;
		font-style: italic;
	}

	/* ---- review step ---- */

	.recipe-fields {
		display: flex;
		gap: 0.75rem;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		font-size: 0.75rem;
		color: #999;
	}

	.field.grow {
		flex: 1 1 auto;
	}

	.field.servings {
		width: 6rem;
	}

	.field input {
		background: #1e1e1d;
		border: 1px solid #444;
		border-radius: 6px;
		color: #fff;
		font-size: 0.9rem;
		padding: 0.5rem 0.65rem;
	}

	.summary {
		margin: 0.9rem 0 0.7rem;
		color: #999;
		font-size: 0.82rem;
	}

	.amber {
		color: var(--color-warning, #c99a3d);
	}

	.muted {
		color: #888;
	}

	.small {
		font-size: 0.75rem;
		line-height: 1.4;
	}

	.table {
		border: 1px solid #333;
		border-radius: 8px;
		overflow: hidden;
	}

	.table-head,
	.line {
		display: grid;
		grid-template-columns: minmax(0, 1.5fr) 6rem 6rem minmax(0, 1.7fr);
		gap: 0.75rem;
		padding: 0.6rem 0.8rem;
		align-items: start;
	}

	.table-head {
		background: #1e1e1d;
		color: #999;
		font-size: 0.72rem;
		font-weight: bold;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}

	.line {
		border-top: 1px solid #333;
	}

	.line.skipped .orig {
		opacity: 0.55;
	}

	.orig {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		min-width: 0;
	}

	.raw {
		font-size: 0.85rem;
		overflow-wrap: anywhere;
	}

	.amount,
	.unit,
	.newname {
		box-sizing: border-box;
		width: 100%;
		background: #1e1e1d;
		border: 1px solid #444;
		border-radius: 6px;
		color: #fff;
		font-size: 0.85rem;
		padding: 0.4rem 0.5rem;
	}

	.amount:disabled,
	.unit:disabled {
		opacity: 0.4;
	}

	.pick {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		min-width: 0;
	}

	.chip {
		align-self: flex-start;
		border-radius: 999px;
		font-size: 0.7rem;
		font-weight: bold;
		padding: 0.1rem 0.6rem;
		background: #333;
		color: #bbb;
	}

	.chip.good {
		background: #2f4a27;
		color: #b5e0a3;
	}

	.chip.check {
		background: #4a3d1c;
		color: #e8c978;
	}

	.chip.new {
		background: #2b3d4a;
		color: #a9cde6;
	}

	.footer {
		position: sticky;
		bottom: -1.5rem;
		display: flex;
		align-items: center;
		gap: 0.9rem;
		margin: 1.1rem -1.5rem -1.5rem;
		padding: 0.9rem 1.5rem;
		background: #232322;
		border-top: 1px solid #333;
	}

	.footer-note {
		flex: 1 1 auto;
		color: #888;
		font-size: 0.75rem;
	}
</style>
