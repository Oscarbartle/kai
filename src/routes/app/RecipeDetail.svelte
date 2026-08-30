<!--
	Full-screen recipe detail overlay, opened by clicking a Recipe Book
	widget. Mirrors ItemDetail.svelte's shape (owns its own CRUD, parent
	just hands it a recipe id and gets told when to close/refresh) but
	covers the recipe-specific fields: method, servings, source URL,
	ingredient links (recipe_items), plus the same tags/image pattern.
-->
<script lang="ts">
	import { invoke } from '@tauri-apps/api/core';
	import { tick } from 'svelte';
	import ConfirmDialog from './ConfirmDialog.svelte';

	interface DbRecipe {
		id: number;
		name: string;
		method: string | null;
		servings: number | null;
		source_url: string | null;
		image_url: string | null;
		created_at: string;
	}

	interface Tag {
		id: number;
		name: string;
	}

	interface Item {
		id: number;
		name: string;
	}

	// `g`/`mL`/`count` are real, shopping-relevant amounts (count for
	// "3 onions"-style discrete amounts). `tsp`/`tbsp` are nominal —
	// cooking reference only, never counted for shopping. No cup, no
	// arbitrary units — deliberately narrow, see CLAUDE.md.
	const UNITS = ['g', 'mL', 'count', 'tsp', 'tbsp'] as const;

	interface Ingredient {
		item_id: number;
		name: string;
		amount: number | null;
		unit: string | null;
	}

	let { recipe, onClose, onDeleted }: {
		recipe: DbRecipe;
		onClose: () => void;
		onDeleted: () => void;
	} = $props();

	let name: string = $state(recipe.name);
	let imageUrlDraft: string = $state(recipe.image_url ?? '');
	let servings: number | null = $state(recipe.servings);
	let sourceUrl: string = $state(recipe.source_url ?? '');
	let method: string = $state(recipe.method ?? '');
	let methodEl: HTMLTextAreaElement | null = $state(null);

	function resizeMethod() {
		if (methodEl) {
			methodEl.style.height = 'auto';
			methodEl.style.height = `${methodEl.scrollHeight}px`;
		}
	}

	// Auto-grow to fit content instead of a fixed-rows box with a
	// manual resize handle — reruns whenever `method` changes, so it
	// covers both typing and the initial value loading in.
	$effect(() => {
		method;
		resizeMethod();
	});

	// The above only reruns when the *text* changes — resizing the
	// window (or the sidebar/content pane otherwise changing width)
	// rewraps the same text into more/fewer lines without touching
	// `method`, so the fixed pixel height set above goes stale and
	// stops matching the content. A ResizeObserver on the textarea
	// itself catches that: any actual box-size change re-measures.
	$effect(() => {
		if (!methodEl) return;
		const observer = new ResizeObserver(() => resizeMethod());
		observer.observe(methodEl);
		return () => observer.disconnect();
	});
	let tags: Tag[] = $state([]);
	let tagInput: string = $state('');
	let tagError: string | null = $state(null);
	let ingredients: Ingredient[] = $state([]);
	let itemInput: string = $state('');
	let itemError: string | null = $state(null);
	let allItems: Item[] = $state([]);
	let error: string | null = $state(null);

	async function load() {
		try {
			const [recipeTags, recipeIngredients, items] = await Promise.all([
				invoke<Tag[]>('list_tags_for_recipe', { recipeId: recipe.id }),
				invoke<Ingredient[]>('list_recipe_ingredients', { recipeId: recipe.id }),
				invoke<Item[]>('list_items')
			]);
			tags = recipeTags;
			ingredients = recipeIngredients;
			allItems = items;
		} catch (e) {
			error = String(e);
		}
	}

	load();

	async function saveName() {
		const trimmed = name.trim();
		if (!trimmed || trimmed === recipe.name) {
			name = recipe.name;
			return;
		}
		try {
			const updated = await invoke<DbRecipe>('update_recipe_name', {
				recipeId: recipe.id,
				name: trimmed
			});
			recipe = updated;
			name = updated.name;
		} catch (e) {
			error = String(e);
		}
	}

	async function saveImageUrl() {
		editingImageUrl = false;
		const trimmed = imageUrlDraft.trim();
		if (trimmed === (recipe.image_url ?? '')) return;
		try {
			const updated = await invoke<DbRecipe>('set_recipe_image_url', {
				recipeId: recipe.id,
				imageUrl: trimmed || null
			});
			recipe = updated;
			imageUrlDraft = updated.image_url ?? '';
		} catch (e) {
			error = String(e);
		}
	}

	let editingImageUrl: boolean = $state(false);
	let imageUrlEl: HTMLInputElement | null = $state(null);

	async function startEditingImageUrl() {
		editingImageUrl = true;
		await tick();
		imageUrlEl?.focus();
	}

	async function saveServings() {
		try {
			recipe = await invoke<DbRecipe>('update_recipe_servings', {
				recipeId: recipe.id,
				servings
			});
		} catch (e) {
			error = String(e);
		}
	}

	async function saveSourceUrl() {
		editingSourceUrl = false;
		const trimmed = sourceUrl.trim();
		if (trimmed === (recipe.source_url ?? '')) return;
		try {
			recipe = await invoke<DbRecipe>('update_recipe_source_url', {
				recipeId: recipe.id,
				sourceUrl: trimmed
			});
			sourceUrl = recipe.source_url ?? '';
		} catch (e) {
			error = String(e);
		}
	}

	let editingSourceUrl: boolean = $state(false);
	let sourceUrlEl: HTMLInputElement | null = $state(null);

	async function startEditingSourceUrl() {
		editingSourceUrl = true;
		await tick();
		sourceUrlEl?.focus();
	}

	async function saveMethod() {
		if (method === (recipe.method ?? '')) return;
		try {
			recipe = await invoke<DbRecipe>('update_recipe_method', { recipeId: recipe.id, method });
		} catch (e) {
			error = String(e);
		}
	}

	async function addTag() {
		const tagName = tagInput.trim();
		if (!tagName) return;
		tagError = null;
		try {
			const tag = await invoke<Tag>('add_tag_to_recipe', { recipeId: recipe.id, name: tagName });
			if (!tags.some((t) => t.id === tag.id)) tags.push(tag);
			tagInput = '';
		} catch (e) {
			tagError = String(e);
		}
	}

	async function removeTag(tag: Tag) {
		try {
			await invoke('remove_tag_from_recipe', { recipeId: recipe.id, tagId: tag.id });
			tags = tags.filter((t) => t.id !== tag.id);
		} catch (e) {
			tagError = String(e);
		}
	}

	// Reuses an existing item by name (case-insensitive) if there's a
	// match, otherwise creates a new one — mirrors how Items/Pantry never
	// makes you pick from a rigid list.
	async function addIngredient() {
		const itemName = itemInput.trim();
		if (!itemName) return;
		itemError = null;
		try {
			let item = allItems.find((i) => i.name.toLowerCase() === itemName.toLowerCase());
			if (!item) {
				item = await invoke<Item>('create_item', { name: itemName });
				allItems.push(item);
			}
			await invoke('add_item_to_recipe', { recipeId: recipe.id, itemId: item.id });
			if (!ingredients.some((i) => i.item_id === item!.id)) {
				ingredients.push({ item_id: item.id, name: item.name, amount: null, unit: 'count' });
				await updateIngredientQuantity(ingredients[ingredients.length - 1]);
			}
			itemInput = '';
		} catch (e) {
			itemError = String(e);
		}
	}

	let confirmRemoveIngredient: Ingredient | null = $state(null);
	let confirmDeleteRecipe: boolean = $state(false);

	async function removeIngredient(ingredient: Ingredient) {
		try {
			await invoke('remove_item_from_recipe', { recipeId: recipe.id, itemId: ingredient.item_id });
			ingredients = ingredients.filter((i) => i.item_id !== ingredient.item_id);
		} catch (e) {
			itemError = String(e);
		}
	}

	async function updateIngredientQuantity(ingredient: Ingredient) {
		itemError = null;
		try {
			await invoke('set_recipe_item_quantity', {
				recipeId: recipe.id,
				itemId: ingredient.item_id,
				amount: ingredient.amount,
				unit: ingredient.unit
			});
		} catch (e) {
			itemError = String(e);
		}
	}

	async function deleteRecipe() {
		try {
			await invoke('delete_recipe', { recipeId: recipe.id });
			onDeleted();
			onClose();
		} catch (e) {
			error = String(e);
		}
	}
</script>

<div class="overlay">
	<div class="topbar">
		<button class="back" onclick={onClose}>← Back</button>
		<button class="delete-item" onclick={() => (confirmDeleteRecipe = true)}>Delete Recipe</button>
	</div>

	{#if error}
		<p class="error">{error}</p>
	{/if}

	<div class="hero">
		<div class="hero-image-block">
			<div class="hero-image">
				{#if imageUrlDraft}
					<img src={imageUrlDraft} alt={name} />
				{:else}
					Image
				{/if}
			</div>
			{#if editingImageUrl}
				<input
					class="image-url-input"
					type="text"
					placeholder="Image URL"
					bind:value={imageUrlDraft}
					bind:this={imageUrlEl}
					onblur={saveImageUrl}
					onkeydown={(e) => e.key === 'Enter' && imageUrlEl?.blur()}
				/>
			{:else}
				<div class="image-url-row">
					<a
						class="link-pill"
						class:active={!!imageUrlDraft}
						href={imageUrlDraft || undefined}
						target="_blank"
						rel="noreferrer"
					>
						{imageUrlDraft ? 'Image' : 'No image'}
					</a>
					<button class="edit-name-btn" aria-label="Edit image link" onclick={startEditingImageUrl}>
						✎
					</button>
				</div>
			{/if}
		</div>
		<div class="hero-info">
			<input class="name" type="text" bind:value={name} onblur={saveName} placeholder="Recipe name" />
			<div class="meta-row">
				<label class="servings">
					Servings
					<input
						type="number"
						min="1"
						step="1"
						bind:value={servings}
						onblur={saveServings}
					/>
				</label>
				{#if editingSourceUrl}
					<input
						class="source-url"
						type="text"
						placeholder="Source URL"
						bind:value={sourceUrl}
						bind:this={sourceUrlEl}
						onblur={saveSourceUrl}
						onkeydown={(e) => e.key === 'Enter' && sourceUrlEl?.blur()}
					/>
				{:else}
					<a
						class="link-pill"
						class:active={!!sourceUrl}
						href={sourceUrl || undefined}
						target="_blank"
						rel="noreferrer"
					>
						{sourceUrl ? 'Link' : 'No link'}
					</a>
					<button class="edit-name-btn" aria-label="Edit source link" onclick={startEditingSourceUrl}>
						✎
					</button>
				{/if}
			</div>
			<div class="tags">
				{#each tags as tag (tag.id)}
					<span class="tag-chip">
						{tag.name}
						<button onclick={() => removeTag(tag)}>×</button>
					</span>
				{/each}
				<input
					class="tag-input"
					type="text"
					placeholder="+ tag"
					bind:value={tagInput}
					onkeydown={(e) => e.key === 'Enter' && addTag()}
				/>
			</div>
			{#if tagError}
				<p class="inline-error">{tagError}</p>
			{/if}
		</div>
	</div>

	<hr />

	<section class="ingredients-section">
		<h2>Ingredients</h2>
		<datalist id="existing-items">
			{#each allItems as item (item.id)}
				<option value={item.name}></option>
			{/each}
		</datalist>
		<div class="ingredients">
			{#each ingredients as ingredient (ingredient.item_id)}
				<div class="ingredient-row">
					<input
						class="ingredient-amount"
						type="number"
						min="0"
						step="any"
						placeholder="amount"
						bind:value={ingredient.amount}
						onblur={() => updateIngredientQuantity(ingredient)}
					/>
					<select
						class="ingredient-unit"
						bind:value={ingredient.unit}
						onchange={() => updateIngredientQuantity(ingredient)}
					>
						{#each UNITS as unit (unit)}
							<option value={unit}>{unit}</option>
						{/each}
					</select>
					<span class="ingredient-name">{ingredient.name}</span>
					<button class="delete-ingredient" onclick={() => (confirmRemoveIngredient = ingredient)}>×</button>
				</div>
			{:else}
				<p class="muted">No ingredients yet.</p>
			{/each}
			<input
				class="item-input"
				type="text"
				list="existing-items"
				placeholder="+ item"
				bind:value={itemInput}
				onkeydown={(e) => e.key === 'Enter' && addIngredient()}
			/>
		</div>
		{#if itemError}
			<p class="inline-error">{itemError}</p>
		{/if}
	</section>

	<hr />

	<section class="method-section">
		<h2>Method</h2>
		<textarea
			class="method"
			placeholder="Method"
			rows="1"
			bind:this={methodEl}
			bind:value={method}
			oninput={resizeMethod}
			onblur={saveMethod}
		></textarea>
	</section>
</div>

{#if confirmDeleteRecipe}
	<ConfirmDialog
		message={`Delete "${recipe.name || 'this recipe'}"? This can't be undone.`}
		onConfirm={() => {
			confirmDeleteRecipe = false;
			deleteRecipe();
		}}
		onCancel={() => (confirmDeleteRecipe = false)}
	/>
{/if}

{#if confirmRemoveIngredient}
	<ConfirmDialog
		message={`Remove "${confirmRemoveIngredient.name}" from this recipe?`}
		onConfirm={() => {
			const ingredient = confirmRemoveIngredient!;
			confirmRemoveIngredient = null;
			removeIngredient(ingredient);
		}}
		onCancel={() => (confirmRemoveIngredient = null)}
	/>
{/if}

<style>
	.overlay {
		/* fixed, not absolute — see ItemDetail.svelte's identical comment.
		   Same bug here: this is a sibling of the Recipe Book grid inside
		   .content's own scroll region, not a wrapper around it, so
		   `absolute` positioned/sized it against that scrollable
		   container instead of the real viewport. */
		position: fixed;
		inset: 0;
		background: #1e1e1d;
		color: #fff;
		overflow-y: auto;
		padding: 1.5rem;
		box-sizing: border-box;
		z-index: 10;
	}

	.topbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 1.5rem;
	}

	.back {
		background: none;
		border: none;
		color: #ccc;
		font-weight: bold;
		font-size: 1rem;
		cursor: pointer;
		padding: 0;
	}

	.delete-item {
		background: none;
		border: 1px solid var(--color-error);
		border-radius: 6px;
		color: var(--color-error);
		font-weight: bold;
		font-size: 0.85rem;
		padding: 0.4rem 0.8rem;
		cursor: pointer;
	}

	.error {
		color: #ff8a80;
	}

	.hero {
		display: flex;
		gap: 1.5rem;
		align-items: flex-start;
	}

	.hero-image-block {
		flex: 0 0 auto;
		width: 140px;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.hero-image {
		width: 140px;
		height: 140px;
		border-radius: 12px;
		background: #fff;
		color: #000;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 0.8rem;
		overflow: hidden;
	}

	.hero-image img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.image-url-input {
		width: 100%;
		box-sizing: border-box;
		background: #232322;
		border: 1px solid #333;
		border-radius: 6px;
		color: #fff;
		font-size: 0.7rem;
		padding: 0.3rem 0.5rem;
	}

	.image-url-row {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.4rem;
	}

	.image-url-input:focus {
		outline: none;
		border-color: #3a4a55;
	}

	.hero-info {
		flex: 1 1 auto;
		min-width: 0;
	}

	.name {
		display: block;
		width: 100%;
		box-sizing: border-box;
		background: none;
		border: none;
		color: #fff;
		font-weight: bold;
		font-size: 1.75rem;
		padding: 0;
		margin-bottom: 0.5rem;
	}

	.name:focus {
		outline: none;
	}

	.meta-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.servings {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.8rem;
		color: #999;
	}

	.servings input {
		width: 3.5rem;
		box-sizing: border-box;
		padding: 0.25rem 0.4rem;
		border-radius: 6px;
		border: 1px solid #555;
		background: #232322;
		color: #fff;
		font-size: 0.85rem;
	}

	.source-url {
		flex: 1;
		box-sizing: border-box;
		padding: 0.25rem 0.5rem;
		border-radius: 6px;
		border: 1px solid #555;
		background: #232322;
		color: #fff;
		font-size: 0.85rem;
	}

	.servings input:focus,
	.source-url:focus {
		outline: none;
		border-color: #3a4a55;
	}

	.link-pill {
		display: inline-flex;
		align-items: center;
		padding: 0.25rem 0.8rem;
		border-radius: 999px;
		font-size: 0.75rem;
		font-weight: bold;
		text-decoration: none;
		background: #333;
		color: #999;
		cursor: default;
	}

	.link-pill.active {
		background: #3a4a55;
		color: #fff;
		cursor: pointer;
	}

	.edit-name-btn {
		background: none;
		border: none;
		color: #999;
		font-size: 0.85rem;
		line-height: 1;
		padding: 0;
		cursor: pointer;
	}

	.tags {
		margin-top: 0.75rem;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem;
	}

	.tag-chip {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		padding: 0.15rem 0.6rem;
		border-radius: 999px;
		background: #3a4a55;
		font-size: 0.75rem;
		font-weight: bold;
	}

	.tag-chip button {
		border: none;
		background: none;
		color: #ccc;
		font-size: 0.85rem;
		line-height: 1;
		cursor: pointer;
		padding: 0;
	}

	.tag-input {
		border: 1px dashed #555;
		border-radius: 999px;
		padding: 0.15rem 0.6rem;
		font-size: 0.75rem;
		background: transparent;
		color: #fff;
		width: 6rem;
	}

	.tag-input:focus {
		outline: none;
		border-color: #3a4a55;
	}

	.inline-error {
		margin: 0.3rem 0 0;
		font-size: 0.8rem;
		color: #ff8a80;
	}

	hr {
		border: none;
		border-top: 3px dashed #333;
		margin: 1.5rem 0;
	}

	h2 {
		margin: 0 0 0.75rem;
		font-size: 1rem;
	}

	.muted {
		color: #999;
		font-size: 0.85rem;
	}

	.ingredients {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.ingredient-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		background: #232322;
		border-radius: 8px;
		padding: 0.5rem 0.75rem;
	}

	.ingredient-amount {
		width: 4.5rem;
		box-sizing: border-box;
		padding: 0.3rem 0.5rem;
		border-radius: 6px;
		border: 1px solid #555;
		background: #1e1e1d;
		color: #fff;
		font-size: 0.8rem;
	}

	.ingredient-unit {
		box-sizing: border-box;
		padding: 0.3rem 0.5rem;
		border-radius: 6px;
		border: 1px solid #555;
		background: #1e1e1d;
		color: #fff;
		font-size: 0.8rem;
	}

	.ingredient-name {
		flex: 1;
		font-size: 0.9rem;
	}

	.delete-ingredient {
		flex: 0 0 auto;
		width: 1.5rem;
		height: 1.5rem;
		border: none;
		border-radius: 50%;
		background: #333;
		color: #fff;
		font-size: 0.9rem;
		line-height: 1;
		cursor: pointer;
	}

	.item-input {
		align-self: flex-start;
		border: 1px dashed #555;
		border-radius: 999px;
		padding: 0.3rem 0.7rem;
		font-size: 0.8rem;
		background: transparent;
		color: #fff;
		width: 8rem;
	}

	.item-input:focus {
		outline: none;
		border-color: #3a4a55;
	}

	.method {
		display: block;
		width: 100%;
		box-sizing: border-box;
		resize: none;
		overflow: hidden;
		padding: 0.6rem 0.75rem;
		border-radius: 8px;
		border: 1px solid #555;
		background: #232322;
		color: #fff;
		font-size: 0.9rem;
		font-family: inherit;
	}

	.method:focus {
		outline: none;
		border-color: #3a4a55;
	}
</style>
