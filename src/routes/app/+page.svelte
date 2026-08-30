<!--
	The app's real UI — the Tauri window loads this directly (see
	src-tauri/tauri.conf.json's window `url`). The old flat /items,
	/recipes, /shopping-list pages this replaced piece by piece are gone;
	this is the only shopping-list/pantry/recipe UI now.
-->
<script lang="ts">
	import { invoke } from '@tauri-apps/api/core';
	import { onMount, tick } from 'svelte';
	import ItemDetail from './ItemDetail.svelte';
	import RecipeDetail from './RecipeDetail.svelte';
	import ShoppingListDetail from './ShoppingListDetail.svelte';
	import Settings from './Settings.svelte';
	import CartAdd from './CartAdd.svelte';
	import { priceSkuGroups, sumSkuGroupTotals, type PricingSku } from './shoppingListPricing';

	type Tab = 'pantry' | 'recipes' | 'shopping-list';

	const tabs: { id: Tab; label: string }[] = [
		{ id: 'pantry', label: 'Pantry' },
		{ id: 'recipes', label: 'Recipe Book' },
		{ id: 'shopping-list', label: 'Shopping Lists' }
	];

	let activeTab: Tab = $state('pantry');
	let settingsOpen: boolean = $state(false);

	// Which shopping lists are ticked for a combined cart add. Cleared
	// whenever the set of lists changes underneath it (see loadShoppingLists)
	// so a deleted list can't linger as a selected-but-missing id.
	let selectedListIds: Set<number> = $state(new Set());

	function toggleListSelected(listId: number) {
		const next = new Set(selectedListIds);
		if (next.has(listId)) next.delete(listId);
		else next.add(listId);
		selectedListIds = next;
	}

	// Sum of the selected lists' own (already correctly weight-scaled,
	// see shoppingListPricing.ts) card totals — not a re-derivation from
	// raw lines, so it always agrees with what each card already shows.
	// A list with no priced lines (totalPrice null) contributes nothing,
	// same "skip, don't guess" rule as everywhere else.
	let selectedTotalPrice = $derived.by(() => {
		const prices = shoppingListCards
			.filter((c) => selectedListIds.has(c.list.id))
			.map((c) => c.totalPrice)
			.filter((p): p is number => p != null);
		return prices.length ? prices.reduce((a, b) => a + b, 0) : null;
	});

	// The flat fee Woolworths adds at checkout — a user-entered constant,
	// editable in Settings (default $14). Loaded once here, alongside
	// the other tab data, and added to the selected-lists total below so
	// the toolbar shows what a real combined order would actually cost.
	let deliveryFee: number = $state(14);

	async function loadDeliveryFee() {
		error = null;
		try {
			deliveryFee = await invoke('get_delivery_fee');
		} catch (e) {
			error = String(e);
		}
	}

	let selectedTotalWithDelivery = $derived(
		selectedTotalPrice != null ? selectedTotalPrice + deliveryFee : null
	);

	interface DbItem {
		id: number;
		name: string;
		is_perishable: boolean;
		image_url: string | null;
		cheapest_by: string;
		created_at: string;
	}

	interface Tag {
		id: number;
		name: string;
		// User override for the sidebar toggle's emoji — null means "use
		// the auto-picked one" (autoEmojiForTag below). Never shown on
		// the plain-text tag pills on item/recipe cards, only here.
		emoji: string | null;
	}

	// Best-effort keyword → emoji mapping for a tag's default look on the
	// sidebar toggle — purely cosmetic, no accuracy guarantee. Checked as
	// substrings against the lowercased tag name, first match wins.
	// Always overridable per-tag (see startEditingTagEmoji/saveTagEmoji),
	// so a wrong or missing guess is a one-click fix, not a dead end.
	const TAG_EMOJI_KEYWORDS: [string, string][] = [
		['vegetarian', '🥗'],
		['vegan', '🌱'],
		['vegetable', '🥦'],
		['fruit', '🍎'],
		['dairy', '🥛'],
		['cheese', '🧀'],
		['egg', '🥚'],
		['chicken', '🍗'],
		['beef', '🥩'],
		['pork', '🥓'],
		['bacon', '🥓'],
		['meat', '🥩'],
		['fish', '🐟'],
		['seafood', '🦐'],
		['bread', '🍞'],
		['bakery', '🥖'],
		['baking', '🍰'],
		['pasta', '🍝'],
		['rice', '🍚'],
		['spicy', '🌶️'],
		['spice', '🌶️'],
		['herb', '🌿'],
		['sauce', '🍯'],
		['sweet', '🍬'],
		['dessert', '🍰'],
		['snack', '🍿'],
		['drink', '🥤'],
		['beverage', '🥤'],
		['coffee', '☕'],
		['tea', '🍵'],
		['frozen', '🧊'],
		['fridge', '🧊'],
		['pantry', '🥫'],
		['canned', '🥫'],
		['cereal', '🥣'],
		['breakfast', '🍳'],
		['lunch', '🥪'],
		['dinner', '🍽️'],
		['quick', '⚡'],
		['easy', '✅'],
		['healthy', '💪'],
		['gluten', '🌾'],
		['nut', '🥜'],
		['oil', '🫒']
	];

	function autoEmojiForTag(name: string): string {
		const lower = name.toLowerCase();
		for (const [keyword, emoji] of TAG_EMOJI_KEYWORDS) {
			if (lower.includes(keyword)) return emoji;
		}
		return '🏷️';
	}

	interface StoredSku {
		id: number;
		item_id: number;
		price: {
			original_price: number | null;
			sale_price: number | null;
			is_special: boolean;
		};
		images: string[];
	}

	interface ItemCard {
		item: DbItem;
		skus: StoredSku[];
		tags: Tag[];
		nameDraft: string;
	}

	interface DbRecipe {
		id: number;
		name: string;
		method: string | null;
		servings: number | null;
		source_url: string | null;
		image_url: string | null;
		created_at: string;
	}

	interface RecipeCard {
		recipe: DbRecipe;
		tags: Tag[];
		ingredientCount: number;
		nameDraft: string;
		imageDraft: string;
		// Sum of each linked ingredient's cheapest-SKU price — ingredients
		// with no linked SKU are silently skipped, not treated as $0, and
		// tsp/tbsp ingredients are excluded entirely (nominal, never real
		// shopping amounts). null when *no* priceable ingredient has
		// pricing at all (nothing to sum).
		totalPrice: number | null;
	}

	interface DbShoppingList {
		id: number;
		name: string;
		created_at: string;
	}

	interface ShoppingListLine {
		id: number;
		item_id: number;
		item_name: string;
		amount: number | null;
		unit: string | null;
		sku: { id: number; name: string; sale_price: number | null } | null;
	}

	interface ShoppingListCard {
		list: DbShoppingList;
		itemCount: number;
		// Same weight/pack-aware pricing as the detail page's "SKUs
		// needed" section (see shoppingListPricing.ts) — this used to be
		// a flat sum of raw sale_price, which was wrong for any
		// weight-based line (450g of $2.49/kg onions showed as $2.49,
		// not $1.12). Lines with no SKU chosen are silently skipped, not
		// treated as $0. Not pack-rounded (a raw weight/count total, not
		// what you'd actually be charged after Woolworths rounds to a
		// purchasable pack — that rounding lives server-side in
		// commands.rs's RawCartNeed, used for the real cart-add) — just a
		// quick at-a-glance total, but one that now agrees with the
		// detail page.
		totalPrice: number | null;
		nameDraft: string;
	}

	let cards: ItemCard[] = $state([]);
	let recipeCards: RecipeCard[] = $state([]);
	let shoppingListCards: ShoppingListCard[] = $state([]);
	let error: string | null = $state(null);
	let refreshingItemIds: Set<number> = $state(new Set());

	async function refreshCardSkus(card: ItemCard, e: MouseEvent) {
		e.stopPropagation();
		if (refreshingItemIds.has(card.item.id)) return;
		error = null;
		refreshingItemIds = new Set(refreshingItemIds).add(card.item.id);
		try {
			card.skus = await invoke('refresh_skus_for_item', { itemId: card.item.id });
		} catch (e) {
			error = String(e);
		} finally {
			const next = new Set(refreshingItemIds);
			next.delete(card.item.id);
			refreshingItemIds = next;
		}
	}

	let refreshingAllPantry: boolean = $state(false);

	// Sequential, not Promise.all — a burst of simultaneous requests to
	// Woolworths for every item at once is worth avoiding, and it mirrors
	// how the backend's own refresh_skus_for_item already refreshes a
	// single item's SKUs one at a time.
	async function refreshAllPantry() {
		if (refreshingAllPantry) return;
		error = null;
		refreshingAllPantry = true;
		try {
			for (const card of cards) {
				if (card.skus.length === 0) continue;
				refreshingItemIds = new Set(refreshingItemIds).add(card.item.id);
				try {
					card.skus = await invoke('refresh_skus_for_item', { itemId: card.item.id });
				} catch (e) {
					error = String(e);
				} finally {
					const next = new Set(refreshingItemIds);
					next.delete(card.item.id);
					refreshingItemIds = next;
				}
			}
		} finally {
			refreshingAllPantry = false;
		}
	}

	async function loadItems() {
		error = null;
		try {
			const items: DbItem[] = await invoke('list_items');
			cards = await Promise.all(
				items.map(async (item) => {
					const [skus, tags] = await Promise.all([
						invoke('list_skus_for_item', { itemId: item.id }) as Promise<StoredSku[]>,
						invoke('list_tags_for_item', { itemId: item.id }) as Promise<Tag[]>
					]);
					return { item, skus, tags, nameDraft: item.name };
				})
			);
		} catch (e) {
			error = String(e);
		}
	}

	async function loadRecipes() {
		error = null;
		try {
			const recipes: DbRecipe[] = await invoke('list_recipes');
			recipeCards = await Promise.all(
				recipes.map(async (recipe) => {
					const [tags, ingredients] = await Promise.all([
						invoke('list_tags_for_recipe', { recipeId: recipe.id }) as Promise<Tag[]>,
						invoke('list_recipe_ingredients', { recipeId: recipe.id }) as Promise<
							{ item_id: number; unit: string | null }[]
						>
					]);
					// tsp/tbsp are nominal — cooking reference only, never fed
					// into shopping-list/purchase math (see CLAUDE.md) — so they
					// don't contribute to the recipe's total price either.
					const priceable = ingredients.filter(
						(ing) => ing.unit !== 'tsp' && ing.unit !== 'tbsp'
					);
					const skuLists = await Promise.all(
						priceable.map(
							(ing) =>
								invoke('list_skus_for_item', { itemId: ing.item_id }) as Promise<StoredSku[]>
						)
					);
					const prices = skuLists
						.map((skus) => cheapestSku(skus)?.price.sale_price ?? null)
						.filter((p): p is number => p != null);
					const totalPrice = prices.length ? prices.reduce((a, b) => a + b, 0) : null;
					return {
						recipe,
						tags,
						ingredientCount: ingredients.length,
						nameDraft: recipe.name,
						imageDraft: recipe.image_url ?? '',
						totalPrice
					};
				})
			);
		} catch (e) {
			error = String(e);
		}
	}

	async function loadShoppingLists() {
		error = null;
		try {
			const lists: DbShoppingList[] = await invoke('list_shopping_lists');
			shoppingListCards = await Promise.all(
				lists.map(async (list) => {
					const lines = (await invoke('list_shopping_list_items', {
						listId: list.id
					})) as ShoppingListLine[];

					// Need the full SKU record (cup_price, quantity.unit) to
					// price a line correctly — the line's own thin `sku`
					// only carries sale_price, enough to display but not to
					// scale by amount. Fetched per item actually on the
					// list, same as the detail page's own picker does.
					const itemIds = [...new Set(lines.filter((l) => l.sku).map((l) => l.item_id))];
					const skuLists = await Promise.all(
						itemIds.map(
							(itemId) => invoke('list_skus_for_item', { itemId }) as Promise<PricingSku[]>
						)
					);
					const skuById = new Map(skuLists.flat().map((s) => [s.id, s]));
					const totalPrice = sumSkuGroupTotals(priceSkuGroups(lines, skuById));

					return { list, itemCount: lines.length, totalPrice, nameDraft: list.name };
				})
			);
			// Drop any selection whose list no longer exists, so a deleted
			// list can't stay ticked and get sent to the cart as a
			// dangling id.
			const alive = new Set(shoppingListCards.map((c) => c.list.id));
			selectedListIds = new Set([...selectedListIds].filter((id) => alive.has(id)));
		} catch (e) {
			error = String(e);
		}
	}

	onMount(() => {
		loadItems();
		loadRecipes();
		loadShoppingLists();
		loadDeliveryFee();
	});

	async function addItem() {
		error = null;
		try {
			const item: DbItem = await invoke('create_item', { name: '' });
			cards = [...cards, { item, skus: [], tags: [], nameDraft: '' }];
			await startEditingName(item.id);
		} catch (e) {
			error = String(e);
		}
	}

	let editingNameId: number | null = $state(null);

	async function startEditingName(itemId: number) {
		editingNameId = itemId;
		await tick();
		const el = document.querySelector<HTMLInputElement>(`[data-item-id="${itemId}"] .name-input`);
		el?.focus();
	}

	async function saveName(card: ItemCard) {
		editingNameId = null;
		const name = card.nameDraft.trim();
		if (name === card.item.name) return;
		error = null;
		try {
			card.item = await invoke('update_item_name', { itemId: card.item.id, name });
			card.nameDraft = card.item.name;
		} catch (e) {
			error = String(e);
		}
	}

	async function addRecipe() {
		error = null;
		try {
			const recipe: DbRecipe = await invoke('create_recipe', { name: '' });
			recipeCards = [
				...recipeCards,
				{ recipe, tags: [], ingredientCount: 0, nameDraft: '', imageDraft: '', totalPrice: null }
			];
			await startEditingRecipeName(recipe.id);
		} catch (e) {
			error = String(e);
		}
	}

	let editingRecipeNameId: number | null = $state(null);

	async function startEditingRecipeName(recipeId: number) {
		editingRecipeNameId = recipeId;
		await tick();
		const el = document.querySelector<HTMLInputElement>(
			`[data-recipe-id="${recipeId}"] .name-input`
		);
		el?.focus();
	}

	async function saveRecipeName(card: RecipeCard) {
		editingRecipeNameId = null;
		const name = card.nameDraft.trim();
		if (name === card.recipe.name) return;
		error = null;
		try {
			card.recipe = await invoke('update_recipe_name', { recipeId: card.recipe.id, name });
			card.nameDraft = card.recipe.name;
		} catch (e) {
			error = String(e);
		}
	}

	async function addShoppingList() {
		error = null;
		try {
			const list: DbShoppingList = await invoke('create_shopping_list', { name: '' });
			shoppingListCards = [
				...shoppingListCards,
				{ list, itemCount: 0, totalPrice: null, nameDraft: '' }
			];
			await startEditingShoppingListName(list.id);
		} catch (e) {
			error = String(e);
		}
	}

	let editingShoppingListNameId: number | null = $state(null);

	async function startEditingShoppingListName(listId: number) {
		editingShoppingListNameId = listId;
		await tick();
		const el = document.querySelector<HTMLInputElement>(
			`[data-shopping-list-id="${listId}"] .name-input`
		);
		el?.focus();
	}

	async function saveShoppingListName(card: ShoppingListCard) {
		editingShoppingListNameId = null;
		const name = card.nameDraft.trim();
		if (name === card.list.name) return;
		error = null;
		try {
			card.list = await invoke('update_shopping_list_name', { listId: card.list.id, name });
			card.nameDraft = card.list.name;
		} catch (e) {
			error = String(e);
		}
	}

	let editingRecipeImageId: number | null = $state(null);

	async function startEditingRecipeImage(recipeId: number) {
		editingRecipeImageId = recipeId;
		await tick();
		const el = document.querySelector<HTMLInputElement>(
			`[data-recipe-id="${recipeId}"] .image-url-input-inline`
		);
		el?.focus();
	}

	async function saveRecipeImage(card: RecipeCard) {
		editingRecipeImageId = null;
		const trimmed = card.imageDraft.trim();
		if (trimmed === (card.recipe.image_url ?? '')) return;
		error = null;
		try {
			card.recipe = await invoke('set_recipe_image_url', {
				recipeId: card.recipe.id,
				imageUrl: trimmed || null
			});
			card.imageDraft = card.recipe.image_url ?? '';
		} catch (e) {
			error = String(e);
		}
	}

	function cheapestSku(skus: StoredSku[]): StoredSku | null {
		const priced = skus.filter((s) => s.price.sale_price != null);
		if (!priced.length) return null;
		return priced.reduce((min, s) =>
			s.price.sale_price! < min.price.sale_price! ? s : min
		);
	}

	// User-set image wins; otherwise fall back to the first linked SKU
	// that actually has one. No auto-picking beyond that — an item with
	// SKUs but no images just shows the placeholder.
	function cardImage(card: ItemCard): string | null {
		if (card.item.image_url) return card.item.image_url;
		return card.skus.find((s) => s.images[0])?.images[0] ?? null;
	}

	// Only tags actually in use by whichever tab is active — not every
	// tag that's ever existed. Shared `tags` table/vocabulary underneath
	// (an item and a recipe can both use "quick"), but an item-only tag
	// doesn't clutter the Recipe Book list until a recipe uses it too,
	// and vice versa. Derived from the cards already loaded, not a
	// separate fetch — updates whenever cards/recipeCards do.
	let contextTags = $derived.by(() => {
		const source = activeTab === 'pantry' ? cards : recipeCards;
		const byId = new Map<number, Tag>();
		for (const card of source) {
			for (const tag of card.tags) byId.set(tag.id, tag);
		}
		return [...byId.values()].sort((a, b) => a.name.localeCompare(b.name));
	});

	let tagSearch: string = $state('');
	let filteredTags = $derived(
		contextTags.filter((t) => t.name.toLowerCase().includes(tagSearch.trim().toLowerCase()))
	);

	let activeTagIds: Set<number> = $state(new Set());

	function toggleTagFilter(tagId: number) {
		const next = new Set(activeTagIds);
		if (next.has(tagId)) {
			next.delete(tagId);
		} else {
			next.add(tagId);
		}
		activeTagIds = next;
	}

	// A tag's emoji, updated in every card's own tags array (not just the
	// one that triggered the edit) — each card fetched its own separate
	// copy of the same tag via list_tags_for_item/list_tags_for_recipe,
	// so a single object mutation wouldn't reach the others, and
	// contextTags (derived from all of them) could show a stale value
	// depending on which copy it happened to dedupe on last.
	function applyTagEmojiEverywhere(tagId: number, emoji: string | null) {
		for (const card of cards) {
			const t = card.tags.find((t) => t.id === tagId);
			if (t) t.emoji = emoji;
		}
		for (const card of recipeCards) {
			const t = card.tags.find((t) => t.id === tagId);
			if (t) t.emoji = emoji;
		}
	}

	let editingTagEmojiId: number | null = $state(null);
	let tagEmojiDraft: string = $state('');

	function startEditingTagEmoji(tag: Tag) {
		editingTagEmojiId = tag.id;
		tagEmojiDraft = tag.emoji ?? autoEmojiForTag(tag.name);
	}

	async function saveTagEmoji(tag: Tag) {
		editingTagEmojiId = null;
		const trimmed = tagEmojiDraft.trim();
		const emoji = trimmed === '' ? null : trimmed;
		if (emoji === tag.emoji) return;
		error = null;
		try {
			const updated: Tag = await invoke('set_tag_emoji', { tagId: tag.id, emoji });
			applyTagEmojiEverywhere(tag.id, updated.emoji);
		} catch (e) {
			error = String(e);
		}
	}

	async function resetTagEmoji(tag: Tag) {
		editingTagEmojiId = null;
		if (tag.emoji === null) return;
		error = null;
		try {
			await invoke('set_tag_emoji', { tagId: tag.id, emoji: null });
			applyTagEmojiEverywhere(tag.id, null);
		} catch (e) {
			error = String(e);
		}
	}

	let itemSearch: string = $state('');

	let visibleCards = $derived(
		cards
			.filter(
				(card) =>
					activeTagIds.size === 0 ||
					[...activeTagIds].every((tagId) => card.tags.some((t) => t.id === tagId))
			)
			.filter((card) => card.item.name.toLowerCase().includes(itemSearch.trim().toLowerCase()))
	);

	let recipeSearch: string = $state('');

	// Same tag-filter set as Pantry, applied against recipe_tags instead
	// of item_tags — whichever tab is active is what the sidebar filters.
	let visibleRecipeCards = $derived(
		recipeCards
			.filter(
				(card) =>
					activeTagIds.size === 0 ||
					[...activeTagIds].every((tagId) => card.tags.some((t) => t.id === tagId))
			)
			.filter((card) => card.recipe.name.toLowerCase().includes(recipeSearch.trim().toLowerCase()))
	);

	let selectedItemId: number | null = $state(null);
	let selectedItem = $derived(cards.find((c) => c.item.id === selectedItemId)?.item ?? null);

	function closeDetail() {
		selectedItemId = null;
		loadItems();
	}

	let selectedRecipeId: number | null = $state(null);
	let selectedRecipe = $derived(
		recipeCards.find((c) => c.recipe.id === selectedRecipeId)?.recipe ?? null
	);

	function closeRecipeDetail() {
		selectedRecipeId = null;
		loadRecipes();
	}

	let selectedShoppingListId: number | null = $state(null);
	let selectedShoppingList = $derived(
		shoppingListCards.find((c) => c.list.id === selectedShoppingListId)?.list ?? null
	);

	function closeShoppingListDetail() {
		selectedShoppingListId = null;
		loadShoppingLists();
	}
</script>

<div class="app">
	<header>
		<img src="/logo.png" alt="Kai" class="logo" />
		<nav>
			{#each tabs as tab}
				<button class="tab" class:active={activeTab === tab.id} onclick={() => (activeTab = tab.id)}>
					{tab.label}
				</button>
			{/each}
		</nav>
		<button class="settings-button" aria-label="Settings" onclick={() => (settingsOpen = true)}>
			⚙
		</button>
	</header>
	<main>
		{#if activeTab !== 'shopping-list'}
			<aside class="sidebar">
				<h2>Tags</h2>
				<hr />
				<input class="tag-search" type="text" placeholder="Search tags…" bind:value={tagSearch} />
				<ul class="tag-list">
					{#each filteredTags as tag (tag.id)}
						<li>
							<div
								class="tag-filter"
								class:active={activeTagIds.has(tag.id)}
								role="button"
								tabindex="0"
								onclick={() => toggleTagFilter(tag.id)}
								onkeydown={(e) => e.key === 'Enter' && toggleTagFilter(tag.id)}
							>
								<span class="tag-emoji">{tag.emoji ?? autoEmojiForTag(tag.name)}</span>
								<span class="tag-name">{tag.name}</span>
								<button
									class="tag-emoji-edit-btn"
									aria-label="Change emoji for {tag.name}"
									onclick={(e) => {
										e.stopPropagation();
										startEditingTagEmoji(tag);
									}}
								>
									✎
								</button>
							</div>
							{#if editingTagEmojiId === tag.id}
								<div class="tag-emoji-editor">
									<input
										class="tag-emoji-input"
										bind:value={tagEmojiDraft}
										onblur={() => saveTagEmoji(tag)}
										onkeydown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
										placeholder="Emoji"
										maxlength="8"
									/>
									<button class="tag-emoji-reset" onclick={() => resetTagEmoji(tag)}>
										Reset to auto
									</button>
								</div>
							{/if}
						</li>
					{/each}
				</ul>
			</aside>
		{/if}
		<section class="content">
			{#if activeTab === 'recipes'}
				<div class="toolbar">
					<input
						class="item-search"
						type="text"
						placeholder="Search recipes…"
						bind:value={recipeSearch}
					/>
				</div>
				<div class="cards">
					{#each visibleRecipeCards as card (card.recipe.id)}
						<div
							class="item-card recipe-card"
							data-recipe-id={card.recipe.id}
							role="button"
							tabindex="0"
							onclick={() => (selectedRecipeId = card.recipe.id)}
							onkeydown={(e) => e.key === 'Enter' && (selectedRecipeId = card.recipe.id)}
						>
							<div class="item-card-header">
								{#if editingRecipeImageId === card.recipe.id}
									<input
										class="image-url-input-inline"
										bind:value={card.imageDraft}
										onblur={() => saveRecipeImage(card)}
										onclick={(e) => e.stopPropagation()}
										placeholder="Image URL"
									/>
								{:else}
									<div
										class="image-placeholder"
										role="button"
										tabindex="0"
										onclick={(e) => {
											e.stopPropagation();
											startEditingRecipeImage(card.recipe.id);
										}}
										onkeydown={(e) =>
											e.key === 'Enter' && startEditingRecipeImage(card.recipe.id)}
									>
										{#if card.recipe.image_url}
											<img src={card.recipe.image_url} alt="" />
										{:else}
											Image
										{/if}
									</div>
								{/if}
								{#if editingRecipeNameId === card.recipe.id}
									<input
										class="name-input"
										bind:value={card.nameDraft}
										onblur={() => saveRecipeName(card)}
										onclick={(e) => e.stopPropagation()}
										placeholder="Name"
									/>
								{:else}
									<div class="name-display">
										<span class="name-text">{card.recipe.name || 'Name'}</span>
										<button
											class="edit-name-btn"
											aria-label="Edit name"
											onclick={(e) => {
												e.stopPropagation();
												startEditingRecipeName(card.recipe.id);
											}}
										>
											✎
										</button>
									</div>
								{/if}
							</div>
							<div class="sku-count">
								Ingredients: {card.ingredientCount}
								{#if card.recipe.servings != null}
									· Serves {card.recipe.servings}
								{/if}
							</div>
							<div class="item-card-footer">
								<div class="tags">
									{#each card.tags as tag (tag.id)}
										<span class="tag-chip">{tag.name}</span>
									{/each}
								</div>
								{#if card.totalPrice === null}
									<span class="price na">N/A</span>
								{:else}
									<span class="price">
										<span class="dollar">$</span><span class="amount"
											>{card.totalPrice.toFixed(2)}</span
										>
									</span>
								{/if}
							</div>
						</div>
					{/each}
				</div>
				<button class="add-item" aria-label="Add recipe" onclick={addRecipe}>+</button>
				{#if selectedRecipe}
					<RecipeDetail
						recipe={selectedRecipe}
						onClose={closeRecipeDetail}
						onDeleted={() =>
							(recipeCards = recipeCards.filter((c) => c.recipe.id !== selectedRecipe?.id))}
					/>
				{/if}
			{:else if activeTab === 'shopping-list'}
				<div class="toolbar">
					{#if selectedListIds.size > 0}
						<span class="selection-count">
							{selectedListIds.size} list{selectedListIds.size === 1 ? '' : 's'} selected
						</span>
						<button class="clear-selection" onclick={() => (selectedListIds = new Set())}>
							Clear
						</button>
						<div class="cart-panel">
							{#if selectedTotalPrice != null}
								<div class="selection-total">
									<div class="selection-total-row">
										<span class="selection-total-label">Total</span>
										<span class="selection-total-value">${selectedTotalPrice.toFixed(2)}</span>
									</div>
									{#if selectedTotalWithDelivery != null}
										<div class="selection-total-row sub">
											<span class="selection-total-label">+ ${deliveryFee.toFixed(2)} delivery</span>
											<span class="selection-total-value"
												>${selectedTotalWithDelivery.toFixed(2)}</span
											>
										</div>
									{/if}
								</div>
							{/if}
							<CartAdd
								listIds={[...selectedListIds]}
								label={selectedListIds.size === 1
									? 'Add to Woolworths cart'
									: `Combine ${selectedListIds.size} lists → Woolworths cart`}
							/>
						</div>
					{:else}
						<span class="selection-hint">
							Tick lists to combine them into one Woolworths cart order.
						</span>
					{/if}
				</div>
				<div class="cards">
					{#each shoppingListCards as card (card.list.id)}
						<div
							class="item-card"
							data-shopping-list-id={card.list.id}
							role="button"
							tabindex="0"
							onclick={() => (selectedShoppingListId = card.list.id)}
							onkeydown={(e) => e.key === 'Enter' && (selectedShoppingListId = card.list.id)}
						>
							<div class="item-card-header">
								<input
									class="list-select"
									type="checkbox"
									aria-label="Select for combined cart add"
									checked={selectedListIds.has(card.list.id)}
									onclick={(e) => {
										e.stopPropagation();
										toggleListSelected(card.list.id);
									}}
								/>
								{#if editingShoppingListNameId === card.list.id}
									<input
										class="name-input"
										bind:value={card.nameDraft}
										onblur={() => saveShoppingListName(card)}
										onclick={(e) => e.stopPropagation()}
										placeholder="Name"
									/>
								{:else}
									<div class="name-display">
										<span class="name-text">{card.list.name || 'Name'}</span>
										<button
											class="edit-name-btn"
											aria-label="Edit name"
											onclick={(e) => {
												e.stopPropagation();
												startEditingShoppingListName(card.list.id);
											}}
										>
											✎
										</button>
									</div>
								{/if}
							</div>
							<div class="sku-count">Items: {card.itemCount}</div>
							<div class="item-card-footer end">
								{#if card.totalPrice === null}
									<span class="price na">N/A</span>
								{:else}
									<span class="price">
										<span class="dollar">$</span><span class="amount"
											>{card.totalPrice.toFixed(2)}</span
										>
									</span>
								{/if}
							</div>
						</div>
					{/each}
				</div>
				<button class="add-item" aria-label="Add shopping list" onclick={addShoppingList}>+</button>
				{#if selectedShoppingList}
					<ShoppingListDetail
					list={selectedShoppingList}
					onClose={closeShoppingListDetail}
					onDeleted={() =>
						(shoppingListCards = shoppingListCards.filter(
							(c) => c.list.id !== selectedShoppingList?.id
						))}
				/>
				{/if}
			{:else}
			<div class="toolbar">
				<input
					class="item-search"
					type="text"
					placeholder="Search items…"
					bind:value={itemSearch}
				/>
				<button
					class="refresh-pantry"
					disabled={refreshingAllPantry}
					onclick={refreshAllPantry}
				>
					{refreshingAllPantry ? 'Refreshing…' : '⟳ Refresh pantry'}
				</button>
			</div>
			{#if error}
				<p class="error">{error}</p>
			{/if}
			<div class="cards">
				{#each visibleCards as card (card.item.id)}
					{@const best = cheapestSku(card.skus)}
					{@const image = cardImage(card)}
					<div
						class="item-card"
						data-item-id={card.item.id}
						role="button"
						tabindex="0"
						onclick={() => (selectedItemId = card.item.id)}
						onkeydown={(e) => e.key === 'Enter' && (selectedItemId = card.item.id)}
					>
						<div class="item-card-header">
							<div class="image-placeholder">
								{#if image}
									<img src={image} alt="" />
								{:else}
									Image
								{/if}
							</div>
							{#if editingNameId === card.item.id}
								<input
									class="name-input"
									bind:value={card.nameDraft}
									onblur={() => saveName(card)}
									onclick={(e) => e.stopPropagation()}
									placeholder="Name"
								/>
							{:else}
								<div class="name-display">
									<span class="name-text">{card.item.name || 'Name'}</span>
									<button
										class="edit-name-btn"
										aria-label="Edit name"
										onclick={(e) => {
											e.stopPropagation();
											startEditingName(card.item.id);
										}}
									>
										✎
									</button>
								</div>
							{/if}
							<div
								class="perishable-badge"
								class:yes={card.item.is_perishable}
								class:no={!card.item.is_perishable}
								title={card.item.is_perishable ? 'Perishable' : 'Not perishable'}
							>
								P
							</div>
						</div>
						<div class="sku-count">
						SKUS: {card.skus.length}
						{#if card.skus.length > 0}
							<button
								class="refresh-btn"
								aria-label="Refresh SKUs"
								disabled={refreshingItemIds.has(card.item.id)}
								onclick={(e) => refreshCardSkus(card, e)}
							>
								{refreshingItemIds.has(card.item.id) ? '…' : '⟳'}
							</button>
						{/if}
					</div>
						<div class="item-card-footer">
							<div class="tags">
								{#each card.tags as tag (tag.id)}
									<span class="tag-chip">{tag.name}</span>
								{/each}
							</div>
							{#if best === null || best.price.sale_price == null}
								<span class="price na">N/A</span>
							{:else}
								<span class="price" class:special={best.price.is_special}>
									{#if best.price.is_special && best.price.original_price != null}
										<span class="was">${best.price.original_price.toFixed(2)}</span>
									{/if}
									<span class="dollar">$</span><span class="amount"
										>{best.price.sale_price.toFixed(2)}</span
									>
								</span>
							{/if}
						</div>
					</div>
				{/each}
			</div>
			<button class="add-item" aria-label="Add item" onclick={addItem}>+</button>
			{#if selectedItem}
				<ItemDetail item={selectedItem} onClose={closeDetail} onDeleted={() => (cards = cards.filter((c) => c.item.id !== selectedItem?.id))} />
			{/if}
			{/if}
		</section>
	</main>

	{#if settingsOpen}
		<Settings
			onClose={() => {
				settingsOpen = false;
				// The delivery fee could have just changed in there — reload
				// it so the Shopping Lists toolbar's combined total reflects
				// it immediately, not whatever was loaded at app start.
				loadDeliveryFee();
			}}
		/>
	{/if}
</div>

<style>
	:global(html, body) {
		height: 100%;
		margin: 0;
	}

	.app {
		--color-good: #5f9b46;
		--color-warning: #c99a3d;
		--color-error: #b3261e;
		display: flex;
		flex-direction: column;
		height: 100vh;
		font-family:
			-apple-system,
			'Segoe UI Variable',
			'Segoe UI',
			system-ui,
			Roboto,
			sans-serif;
	}

	header {
		height: 7vh;
		flex: 0 0 auto;
		background: #171716;
		display: flex;
		align-items: center;
		gap: 1.5rem;
		padding: 0 1rem;
	}

	.logo {
		height: 60%;
		width: auto;
	}

	nav {
		display: flex;
		align-items: center;
		gap: 1.5rem;
		height: 100%;
	}

	.tab {
		background: none;
		border: none;
		color: #999;
		font-weight: bold;
		font-size: 1rem;
		padding: 0;
		cursor: pointer;
	}

	.tab.active {
		color: #fff;
	}

	.settings-button {
		margin-left: auto;
		background: none;
		border: none;
		color: #999;
		font-size: 1.2rem;
		line-height: 1;
		padding: 0;
		cursor: pointer;
	}

	.settings-button:hover {
		color: #fff;
	}

	.selection-count {
		font-size: 0.85rem;
		font-weight: bold;
		color: #fff;
	}

	.selection-hint {
		font-size: 0.85rem;
		color: #999;
	}

	.selection-total {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		background: #232322;
		border: 1px solid #3a4a55;
		border-radius: 10px;
		padding: 0.6rem 1rem;
		min-width: 220px;
	}

	.selection-total-row {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1.5rem;
	}

	.selection-total-row.sub {
		padding-top: 0.4rem;
		border-top: 1px dashed #333;
	}

	.selection-total-label {
		font-size: 0.7rem;
		font-weight: bold;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: #999;
		white-space: nowrap;
	}

	.selection-total-row.sub .selection-total-label {
		text-transform: none;
		letter-spacing: normal;
	}

	.selection-total-value {
		font-size: 1.35rem;
		font-weight: bold;
		color: #95977e;
		white-space: nowrap;
	}

	.selection-total-row.sub .selection-total-value {
		font-size: 0.9rem;
	}

	.clear-selection {
		background: none;
		border: 1px solid #333;
		border-radius: 6px;
		color: #999;
		font-size: 0.8rem;
		font-weight: bold;
		padding: 0.35rem 0.7rem;
		cursor: pointer;
	}

	.list-select {
		appearance: none;
		-webkit-appearance: none;
		flex: 0 0 auto;
		width: 1rem;
		height: 1rem;
		margin: 0;
		border-radius: 4px;
		border: 1px solid #555;
		background: #1e1e1d;
		cursor: pointer;
	}

	.list-select:checked {
		background: #3a4a55;
		border-color: #3a4a55;
	}

	main {
		flex: 1 1 auto;
		display: flex;
		min-height: 0;
	}

	.sidebar {
		flex: 0 0 250px;
		background: #191918;
		padding: 1rem;
	}

	.sidebar h2 {
		margin: 0 0 1rem 0.25rem;
		color: #fff;
		font-size: 1rem;
	}

	.sidebar hr {
		border: none;
		border-top: 3px dashed #333;
		margin: 0;
	}

	.tag-search {
		width: 100%;
		box-sizing: border-box;
		margin-top: 1rem;
		background: #232322;
		border: 1px solid #333;
		border-radius: 6px;
		color: #fff;
		font-size: 0.9rem;
		padding: 0.4rem 0.6rem;
	}

	.tag-search:focus {
		outline: none;
		border-color: #3a4a55;
	}

	.tag-list {
		list-style: none;
		margin: 0.75rem 0 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.tag-emoji {
		flex: 0 0 auto;
		font-size: 1rem;
		line-height: 1;
	}

	.tag-name {
		flex: 1 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.tag-emoji-edit-btn {
		flex: 0 0 auto;
		background: none;
		border: none;
		color: #999;
		font-size: 0.8rem;
		line-height: 1;
		padding: 0;
		cursor: pointer;
		opacity: 0;
		transition: opacity 0.1s;
	}

	.tag-filter:hover .tag-emoji-edit-btn {
		opacity: 1;
	}

	.tag-emoji-editor {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin: 0.35rem 0 0;
	}

	.tag-emoji-input {
		width: 3.2rem;
		box-sizing: border-box;
		background: #1e1e1d;
		border: 1px solid #3a4a55;
		border-radius: 6px;
		color: #fff;
		font-size: 1rem;
		text-align: center;
		padding: 0.3rem 0.2rem;
	}

	.tag-emoji-input:focus {
		outline: none;
	}

	.tag-emoji-reset {
		background: none;
		border: none;
		color: #999;
		font-size: 0.7rem;
		text-decoration: underline;
		padding: 0;
		cursor: pointer;
	}

	.tag-filter {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		width: 100%;
		box-sizing: border-box;
		text-align: left;
		background: #232322;
		border: 1px solid #333;
		border-radius: 6px;
		color: #ccc;
		font-size: 0.9rem;
		padding: 0.4rem 0.6rem;
		cursor: pointer;
	}

	.tag-filter.active {
		background: #3a4a55;
		border-color: #3a4a55;
		color: #fff;
	}

	.content {
		position: relative;
		flex: 1 1 auto;
		color: #fff;
		padding: 1rem;
		overflow-y: auto;
	}

	.toolbar {
		position: relative;
		margin-bottom: 1rem;
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	/* Absolutely positioned against .toolbar rather than laid out in
	   flow — it's taller than the "N lists selected" row next to it, and
	   as a normal-flow sibling that extra height was pushing the card
	   grid down by however tall the total widget happened to be. This
	   pins it to the toolbar's own top-right corner instead, so it
	   floats over the (otherwise empty) space there without affecting
	   where anything below the toolbar starts. */
	.cart-panel {
		position: absolute;
		top: 0;
		right: 0;
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 0.6rem;
	}

	.refresh-pantry {
		flex: 0 0 auto;
		margin-left: auto;
		background: none;
		border: 1px solid #333;
		border-radius: 6px;
		color: #fff;
		font-weight: bold;
		font-size: 0.85rem;
		padding: 0.5rem 0.8rem;
		cursor: pointer;
	}

	.refresh-pantry:disabled {
		opacity: 0.5;
		cursor: default;
	}

	.item-search {
		width: 100%;
		max-width: 320px;
		box-sizing: border-box;
		background: #232322;
		border: 1px solid #333;
		border-radius: 6px;
		color: #fff;
		font-size: 0.9rem;
		padding: 0.5rem 0.7rem;
	}

	.item-search:focus {
		outline: none;
		border-color: #3a4a55;
	}

	.error {
		color: #ff8a80;
	}

	.cards {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
	}

	.item-card {
		width: 238px;
		background: #232322;
		border-radius: 10px;
		padding: 0.85rem;
		display: flex;
		flex-direction: column;
		gap: 0.65rem;
		cursor: pointer;
	}

	.item-card-header {
		display: flex;
		align-items: center;
		gap: 0.65rem;
	}

	.image-placeholder {
		flex: 0 0 auto;
		width: 48px;
		height: 48px;
		border-radius: 50%;
		background: #fff;
		color: #000;
		font-size: 0.5rem;
		display: flex;
		align-items: center;
		justify-content: center;
		overflow: hidden;
		cursor: pointer;
	}

	.image-url-input-inline {
		flex: 0 0 auto;
		width: 48px;
		height: 48px;
		box-sizing: border-box;
		border-radius: 50%;
		border: 1px solid #555;
		background: #1e1e1d;
		color: #fff;
		font-size: 0.5rem;
		text-align: center;
		padding: 0 0.2rem;
	}

	.image-url-input-inline:focus {
		outline: none;
		border-color: #3a4a55;
	}

	.image-placeholder img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.name-input {
		flex: 1 1 auto;
		min-width: 0;
		background: none;
		border: none;
		color: #fff;
		font-weight: bold;
		font-size: 1rem;
		padding: 0;
	}

	.name-display {
		flex: 1 1 auto;
		min-width: 0;
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}

	.name-text {
		flex: 1 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: #fff;
		font-weight: bold;
		font-size: 1rem;
	}

	.edit-name-btn {
		flex: 0 0 auto;
		background: none;
		border: none;
		color: #999;
		font-size: 0.85rem;
		line-height: 1;
		padding: 0;
		cursor: pointer;
		opacity: 0;
		transition: opacity 0.1s;
	}

	.item-card:hover .edit-name-btn {
		opacity: 1;
	}

	.perishable-badge {
		flex: 0 0 auto;
		width: 1.1rem;
		height: 1.1rem;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		color: #fff;
		font-size: 0.6rem;
		font-weight: bold;
	}

	.perishable-badge.yes {
		background: var(--color-warning);
	}

	.perishable-badge.no {
		background: var(--color-error);
	}

	.name-input:focus {
		outline: none;
	}

	.sku-count {
		font-size: 0.65rem;
		font-weight: bold;
		color: #999;
		display: flex;
		align-items: center;
		gap: 0.35rem;
	}

	.refresh-btn {
		width: 1.1rem;
		height: 1.1rem;
		border: none;
		border-radius: 50%;
		background: #333;
		color: #fff;
		font-size: 0.6rem;
		line-height: 1;
		padding: 0;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
	}

	.refresh-btn:disabled {
		opacity: 0.5;
		cursor: default;
	}

	.item-card-footer {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.item-card-footer.end {
		justify-content: flex-end;
	}

	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}

	.tag-chip {
		background: #3a4a55;
		border-radius: 999px;
		padding: 0.13rem 0.5rem;
		font-size: 0.6rem;
		font-weight: bold;
		white-space: nowrap;
	}

	.price {
		font-size: 1.2rem;
		font-weight: bold;
		white-space: nowrap;
		color: #95977e;
	}

	.price.na {
		font-size: 0.85rem;
		color: var(--color-warning);
	}

	.price.special .amount,
	.price.special .dollar {
		color: var(--color-good);
	}

	.price .was {
		margin-right: 0.3rem;
		font-size: 0.75rem;
		font-weight: normal;
		color: var(--color-error);
		text-decoration: line-through;
	}

	.add-item {
		position: absolute;
		right: 1.5rem;
		bottom: 1.5rem;
		width: 3rem;
		height: 3rem;
		border-radius: 50%;
		border: none;
		background: #b3261e;
		color: #fff;
		font-size: 1.75rem;
		line-height: 1;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
	}
</style>
