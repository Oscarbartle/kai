<!--
	The "Edit tag" dialog, opened from the ✎ on a Tags-sidebar pill.
	A tag is one shared row used by both Pantry items and recipes, so this
	works on the tag everywhere at once:
	  - name: renamed on blur/Enter (shows up on every item/recipe at once;
	    a name another tag already has is refused),
	  - emoji: same override/reset as before,
	  - "Used by": checklists of every item and recipe, ticked where the tag
	    already applies. Ticks are only staged — nothing is tagged or untagged
	    until Apply, so a batch can be reviewed or abandoned.
-->
<script lang="ts">
	interface Row {
		id: number;
		name: string;
	}

	let {
		tag,
		autoEmoji,
		items,
		recipes,
		itemHas,
		recipeHas,
		onrename,
		onemoji,
		onapply,
		onclose
	}: {
		tag: { id: number; name: string; emoji: string | null };
		autoEmoji: string;
		items: Row[];
		recipes: Row[];
		itemHas: Set<number>;
		recipeHas: Set<number>;
		onrename: (name: string) => Promise<void>;
		onemoji: (emoji: string | null) => Promise<void>;
		onapply: (changes: {
			add_item_ids: number[];
			remove_item_ids: number[];
			add_recipe_ids: number[];
			remove_recipe_ids: number[];
		}) => Promise<void>;
		onclose: () => void;
	} = $props();

	// Drafts start from the tag as it was when the dialog opened; the tag
	// prop changes underneath as renames/emoji land, which is why these
	// are state of their own rather than derived.
	// svelte-ignore state_referenced_locally
	let nameDraft = $state(tag.name);
	// svelte-ignore state_referenced_locally
	let emojiDraft = $state(tag.emoji ?? autoEmoji);
	// svelte-ignore state_referenced_locally
	let tickedItems = $state(new Set(itemHas));
	// svelte-ignore state_referenced_locally
	let tickedRecipes = $state(new Set(recipeHas));

	let search = $state('');
	let nameError: string | null = $state(null);
	let applyError: string | null = $state(null);
	let applying = $state(false);

	const needle = $derived(search.trim().toLowerCase());
	const shownItems = $derived(items.filter((r) => r.name.toLowerCase().includes(needle)));
	const shownRecipes = $derived(recipes.filter((r) => r.name.toLowerCase().includes(needle)));

	const changes = $derived({
		add_item_ids: [...tickedItems].filter((id) => !itemHas.has(id)),
		remove_item_ids: [...itemHas].filter((id) => !tickedItems.has(id)),
		add_recipe_ids: [...tickedRecipes].filter((id) => !recipeHas.has(id)),
		remove_recipe_ids: [...recipeHas].filter((id) => !tickedRecipes.has(id))
	});
	const changeCount = $derived(
		changes.add_item_ids.length +
			changes.remove_item_ids.length +
			changes.add_recipe_ids.length +
			changes.remove_recipe_ids.length
	);

	function toggle(set: Set<number>, id: number): Set<number> {
		const next = new Set(set);
		if (next.has(id)) next.delete(id);
		else next.add(id);
		return next;
	}

	// "Select/clear all shown" act on what the search currently shows, so
	// searching "chicken" then "select all" ticks just the chicken rows.
	function setShown(kind: 'items' | 'recipes', on: boolean) {
		const rows = kind === 'items' ? shownItems : shownRecipes;
		const next = new Set(kind === 'items' ? tickedItems : tickedRecipes);
		for (const r of rows) {
			if (on) next.add(r.id);
			else next.delete(r.id);
		}
		if (kind === 'items') tickedItems = next;
		else tickedRecipes = next;
	}

	async function saveName() {
		const trimmed = nameDraft.trim();
		if (trimmed === tag.name) {
			nameDraft = tag.name;
			nameError = null;
			return;
		}
		nameError = null;
		try {
			await onrename(trimmed);
			nameDraft = trimmed;
		} catch (e) {
			nameError = String(e);
			nameDraft = tag.name;
		}
	}

	async function saveEmoji() {
		const trimmed = emojiDraft.trim();
		const emoji = trimmed === '' ? null : trimmed;
		if (emoji === tag.emoji) return;
		try {
			await onemoji(emoji);
		} catch (e) {
			nameError = String(e);
		}
		emojiDraft = tag.emoji ?? autoEmoji;
	}

	async function resetEmoji() {
		try {
			await onemoji(null);
		} catch (e) {
			nameError = String(e);
		}
		emojiDraft = tag.emoji ?? autoEmoji;
	}

	async function apply() {
		applying = true;
		applyError = null;
		try {
			await onapply(changes);
			onclose();
		} catch (e) {
			applyError = String(e);
		} finally {
			applying = false;
		}
	}
</script>

<div
	class="overlay"
	onclick={onclose}
	onkeydown={(e) => e.key === 'Escape' && onclose()}
	role="presentation"
>
	<div
		class="box"
		onclick={(e) => e.stopPropagation()}
		onkeydown={(e) => e.stopPropagation()}
		role="dialog"
		aria-modal="true"
		aria-label="Edit tag {tag.name}"
		tabindex="-1"
	>
		<h3>Edit tag</h3>

		<div class="row">
			<input
				class="emoji-input"
				bind:value={emojiDraft}
				onblur={saveEmoji}
				onkeydown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
				placeholder="Emoji"
				maxlength="8"
				aria-label="Emoji"
			/>
			<input
				class="name-input"
				bind:value={nameDraft}
				onblur={saveName}
				onkeydown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
				placeholder="Tag name"
				aria-label="Tag name"
			/>
		</div>
		<div class="sub">
			<button class="link" onclick={resetEmoji} disabled={tag.emoji === null}>Reset emoji to auto</button>
		</div>
		{#if nameError}
			<p class="error" role="alert">{nameError}</p>
		{/if}

		<h4>Used by</h4>
		<input
			class="search"
			type="text"
			placeholder="Search items and recipes…"
			bind:value={search}
			aria-label="Search items and recipes"
		/>

		<div class="lists">
			<section>
				<div class="section-head">
					<span>Pantry ({tickedItems.size})</span>
					<span>
						<button class="link" onclick={() => setShown('items', true)}>Select shown</button>
						<button class="link" onclick={() => setShown('items', false)}>Clear shown</button>
					</span>
				</div>
				<ul>
					{#each shownItems as row (row.id)}
						<li>
							<label>
								<input
									type="checkbox"
									checked={tickedItems.has(row.id)}
									onchange={() => (tickedItems = toggle(tickedItems, row.id))}
								/>
								<span>{row.name}</span>
							</label>
						</li>
					{:else}
						<li class="none">{items.length === 0 ? 'No items yet.' : 'Nothing matches.'}</li>
					{/each}
				</ul>
			</section>

			<section>
				<div class="section-head">
					<span>Recipes ({tickedRecipes.size})</span>
					<span>
						<button class="link" onclick={() => setShown('recipes', true)}>Select shown</button>
						<button class="link" onclick={() => setShown('recipes', false)}>Clear shown</button>
					</span>
				</div>
				<ul>
					{#each shownRecipes as row (row.id)}
						<li>
							<label>
								<input
									type="checkbox"
									checked={tickedRecipes.has(row.id)}
									onchange={() => (tickedRecipes = toggle(tickedRecipes, row.id))}
								/>
								<span>{row.name}</span>
							</label>
						</li>
					{:else}
						<li class="none">{recipes.length === 0 ? 'No recipes yet.' : 'Nothing matches.'}</li>
					{/each}
				</ul>
			</section>
		</div>

		{#if applyError}
			<p class="error" role="alert">{applyError}</p>
		{/if}

		<div class="actions">
			<button class="cancel" onclick={onclose}>Cancel</button>
			<button class="apply" onclick={apply} disabled={changeCount === 0 || applying}>
				{applying
					? 'Applying…'
					: changeCount === 0
						? 'No changes'
						: `Apply ${changeCount} change${changeCount === 1 ? '' : 's'}`}
			</button>
		</div>
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
		padding: 1.25rem 1.5rem;
		width: 560px;
		max-width: calc(100% - 2rem);
		max-height: calc(100% - 3rem);
		display: flex;
		flex-direction: column;
		box-sizing: border-box;
		color: #fff;
	}

	h3 {
		margin: 0 0 0.9rem;
		font-size: 1.05rem;
	}

	h4 {
		margin: 1.1rem 0 0.5rem;
		font-size: 0.8rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: #999;
	}

	.row {
		display: flex;
		gap: 0.5rem;
	}

	.emoji-input,
	.name-input,
	.search {
		background: #1e1e1d;
		border: 1px solid #333;
		border-radius: 6px;
		color: #fff;
		font-size: 0.95rem;
		padding: 0.45rem 0.6rem;
		box-sizing: border-box;
	}

	.emoji-input {
		width: 3.6rem;
		text-align: center;
		font-size: 1.1rem;
	}

	.name-input {
		flex: 1 1 auto;
		min-width: 0;
	}

	.search {
		width: 100%;
	}

	.emoji-input:focus,
	.name-input:focus,
	.search:focus {
		outline: none;
		border-color: #3a4a55;
	}

	.sub {
		margin-top: 0.35rem;
	}

	.link {
		background: none;
		border: none;
		color: #999;
		font-size: 0.75rem;
		text-decoration: underline;
		padding: 0;
		margin-left: 0.6rem;
		cursor: pointer;
	}

	.sub .link {
		margin-left: 0;
	}

	.link:disabled {
		opacity: 0.4;
		cursor: default;
	}

	.error {
		margin: 0.5rem 0 0;
		color: #ff8a80;
		font-size: 0.85rem;
	}

	.lists {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1rem;
		margin-top: 0.75rem;
		min-height: 0;
		flex: 1 1 auto;
	}

	section {
		display: flex;
		flex-direction: column;
		min-height: 0;
	}

	.section-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		font-size: 0.85rem;
		font-weight: bold;
		margin-bottom: 0.35rem;
	}

	ul {
		list-style: none;
		margin: 0;
		padding: 0.25rem;
		height: 14rem;
		overflow-y: auto;
		background: #1e1e1d;
		border: 1px solid #333;
		border-radius: 6px;
	}

	li label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.25rem 0.35rem;
		border-radius: 4px;
		font-size: 0.9rem;
		cursor: pointer;
	}

	li label:hover {
		background: #2c2c2b;
	}

	.none {
		color: #999;
		font-size: 0.85rem;
		padding: 0.5rem;
	}

	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.75rem;
		margin-top: 1rem;
	}

	.cancel,
	.apply {
		border-radius: 6px;
		font-weight: bold;
		font-size: 0.85rem;
		padding: 0.5rem 1.1rem;
		cursor: pointer;
	}

	.cancel {
		background: none;
		border: 1px solid #555;
		color: #fff;
	}

	.apply {
		background: var(--color-good);
		border: none;
		color: #fff;
	}

	.apply:disabled {
		opacity: 0.5;
		cursor: default;
	}
</style>
