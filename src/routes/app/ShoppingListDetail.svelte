<!--
	Full-screen shopping list detail overlay, opened by clicking a
	Shopping Lists widget. Built out piece by piece, same as the
	Pantry/Recipe Book tabs and their widgets were.
-->
<script lang="ts">
	import { invoke } from '@tauri-apps/api/core';
	import { onMount } from 'svelte';
	import ConfirmDialog from './ConfirmDialog.svelte';
	import CartAdd from './CartAdd.svelte';
	import { parsePackSize, priceSkuGroups } from './shoppingListPricing';

	interface DbShoppingList {
		id: number;
		name: string;
		created_at: string;
	}

	let { list, onClose, onDeleted }: {
		list: DbShoppingList;
		onClose: () => void;
		onDeleted: () => void;
	} = $props();

	let confirmDeleteList: boolean = $state(false);

	async function deleteList() {
		try {
			await invoke('delete_shopping_list', { listId: list.id });
			onDeleted();
			onClose();
		} catch (e) {
			error = String(e);
		}
	}

	let name: string = $state(list.name);

	async function saveName() {
		const trimmed = name.trim();
		if (!trimmed || trimmed === list.name) {
			name = list.name;
			return;
		}
		try {
			const updated = await invoke<DbShoppingList>('update_shopping_list_name', {
				listId: list.id,
				name: trimmed
			});
			list = updated;
			name = updated.name;
		} catch (e) {
			error = String(e);
		}
	}

	// Which picker the sidebar is showing — for adding a recipe's
	// ingredients or a standalone item onto this list.
	type SidebarTab = 'recipes' | 'items';
	let sidebarTab: SidebarTab = $state('recipes');

	interface DbItem {
		id: number;
		name: string;
		image_url: string | null;
	}

	interface DbRecipe {
		id: number;
		name: string;
		image_url: string | null;
		servings: number | null;
	}

	// Mirrors ItemDetail's SkuData shape — needed here too since the SKUs
	// needed section renders full SKU cards, same as the item page does.
	interface StoredSku {
		id: number;
		item_id: number;
		sku: string;
		name: string;
		brand: string | null;
		variety: string | null;
		price: {
			original_price: number | null;
			sale_price: number | null;
			is_special: boolean;
			promotion_end_date: string | null;
		};
		size: { cup_price: number | null; cup_measure: string | null; volume_size: string | null };
		quantity: {
			unit: string;
			min: number | null;
			increment: number | null;
			supports_both_each_and_kg: boolean;
			average_weight_per_unit: number | null;
		};
		availability_status: string | null;
		images: string[];
		allergens: string[];
	}

	interface PickerItem {
		item: DbItem;
		image: string | null;
		price: number | null;
		skus: StoredSku[];
	}

	interface PickerRecipe {
		recipe: DbRecipe;
	}

	let pickerItems: PickerItem[] = $state([]);
	let pickerRecipes: PickerRecipe[] = $state([]);
	let error: string | null = $state(null);

	// Every linked SKU across every item, keyed by SKU id — the SKUs
	// needed section groups shopping-list lines by SKU, and needs the
	// full SKU record (image, brand, allergens, ...) to render each
	// group the same rich way ItemDetail does, not just what
	// ShoppingListLine's own thin SkuSummary carries.
	let skuById = $derived(new Map(pickerItems.flatMap((p) => p.skus).map((s) => [s.id, s])));

	let pickerSearch: string = $state('');
	let filteredPickerItems = $derived(
		pickerItems.filter((p) => p.item.name.toLowerCase().includes(pickerSearch.trim().toLowerCase()))
	);
	let filteredPickerRecipes = $derived(
		pickerRecipes.filter((p) =>
			p.recipe.name.toLowerCase().includes(pickerSearch.trim().toLowerCase())
		)
	);

	async function loadPickerItems() {
		try {
			const items: DbItem[] = await invoke('list_items');
			pickerItems = await Promise.all(
				items.map(async (item) => {
					const skus = (await invoke('list_skus_for_item', {
						itemId: item.id
					})) as StoredSku[];
					const priced = skus.filter((s) => s.price.sale_price != null);
					const cheapest = priced.length
						? priced.reduce((min, s) => (s.price.sale_price! < min.price.sale_price! ? s : min))
						: null;
					const image = item.image_url ?? skus.find((s) => s.images[0])?.images[0] ?? null;
					return { item, image, price: cheapest?.price.sale_price ?? null, skus };
				})
			);
		} catch (e) {
			error = String(e);
		}
	}

	async function loadPickerRecipes() {
		try {
			const recipes: DbRecipe[] = await invoke('list_recipes');
			pickerRecipes = recipes.map((recipe) => ({ recipe }));
		} catch (e) {
			error = String(e);
		}
	}

	// --- Drag and drop onto the list, and the resolved SKU lines below it ---

	interface ShoppingListLine {
		id: number;
		item_id: number;
		item_name: string;
		amount: number | null;
		unit: string | null;
		sku: { id: number; name: string; sale_price: number | null } | null;
		source_recipe_id: number | null;
	}

	// What's shown as a full-sized widget in the drop zone. Reconstructed
	// from the list's real lines on load — `source_recipe_id` (persisted
	// on the line, see CLAUDE.md) is what lets a recipe's lines regroup
	// under one card even after reopening the list, not just in-session.
	// `quantity` is pure UI state, not stored anywhere: for an item it's
	// seeded from its one line's amount when that's a plain count, for a
	// recipe it always starts at 1 — adjusting the stepper recomputes
	// the underlying line(s) from scratch rather than trying to reverse
	// a stored multiplier back out of summed amounts.
	// An item's `unit` (null/'count' vs 'g'/'mL') drives which control
	// the widget shows — a plain quantity stepper, or a weight amount —
	// for items whose SKU can actually be bought that way (see
	// `isWeightEligible`). It's read straight off the real line, not
	// separate UI state, so switching modes and reloading stay in sync.
	type DroppedEntry =
		| { kind: 'item'; itemId: number; lineIds: number[]; quantity: number; unit: string | null }
		| { kind: 'recipe'; recipeId: number; lineIds: number[]; quantity: number };

	let lines: ShoppingListLine[] = $state([]);

	// Guards against an out-of-order response overwriting a newer one:
	// dropItem/dropRecipe/removeEntry/setItem* etc. all end with
	// loadLines(), and each is its own independent round-trip — if two
	// ever overlap (a fast second click, a drop right after another),
	// nothing stops an earlier call's response from resolving *after* a
	// later call's and clobbering its result with stale data. Only the
	// response matching the most recently *started* call is applied.
	let linesRequestId = 0;
	let droppedEntries: DroppedEntry[] = $state([]);

	interface SkuGroup {
		sku: StoredSku;
		parts: ShoppingListLine[];
		// Whole-pack count — for a weight-sold SKU this is just the plain
		// count portion of the need (a dual-mode SKU can genuinely need
		// both a count and a weight side by side); for an each-only SKU
		// it also absorbs any g/mL need converted into pack-equivalents,
		// since "1500g of bread" isn't purchasable, only whole loaves
		// are. null when there's nothing count-like to show at all.
		count: number | null;
		// A weight/volume amount worth showing on its own pill — only
		// for a SKU that's actually sold that way (onions by the kg), or
		// as a flagged, unconverted leftover when an each-only SKU's own
		// pack size couldn't be parsed (see `parsePackSize`) — genuinely
		// unresolvable, not guessed at.
		weightPill: string | null;
		weightUnresolved: boolean;
		totalPrice: number | null;
	}

	interface UnresolvedGroup {
		itemId: number;
		itemName: string;
		parts: ShoppingListLine[];
	}

	// Grouped by actual SKU, not by item — the same SKU needed via a
	// recipe line and a plain item line (e.g. onions from a recipe and
	// onions dropped directly) merges into one card with a combined
	// total, same as this app already merges same-SKU lines in the real
	// Woolworths cart-add flow. Lines with no SKU chosen can't merge
	// this way (nothing to merge on) — those stay grouped by item
	// instead, still flagged rather than guessed.
	let skuGroups = $derived.by(() => {
		const bySku = new Map<number, ShoppingListLine[]>();
		const byItem = new Map<number, ShoppingListLine[]>();
		for (const line of lines) {
			if (line.sku) {
				const parts = bySku.get(line.sku.id) ?? [];
				parts.push(line);
				bySku.set(line.sku.id, parts);
			} else {
				const parts = byItem.get(line.item_id) ?? [];
				parts.push(line);
				byItem.set(line.item_id, parts);
			}
		}
		// Priced via the same shared logic the outer Shopping Lists card
		// uses (see shoppingListPricing.ts) — computed once over every
		// SKU-linked line here rather than per group below, so the two
		// views can't disagree about what a line actually costs.
		const priced = new Map(
			priceSkuGroups(
				lines.filter((l) => l.sku),
				skuById
			).map((g) => [g.skuId, g.totalPrice])
		);
		const resolved: SkuGroup[] = [...bySku.entries()]
			.map(([skuId, parts]): SkuGroup | null => {
				const sku = skuById.get(skuId);
				if (!sku) return null;

				const countTotal = parts.reduce(
					(sum, p) => sum + (p.unit === 'count' && p.amount != null ? p.amount : 0),
					0
				);
				const gramsTotal = parts.reduce(
					(sum, p) => sum + (p.unit === 'g' && p.amount != null ? p.amount : 0),
					0
				);
				const mlTotal = parts.reduce(
					(sum, p) => sum + (p.unit === 'mL' && p.amount != null ? p.amount : 0),
					0
				);
				const isWeightSku =
					sku.quantity.unit.toLowerCase() === 'kg' || sku.quantity.supports_both_each_and_kg;

				let count: number | null;
				let weightPill: string | null = null;
				let weightUnresolved = false;

				if (isWeightSku) {
					count = countTotal > 0 ? countTotal : null;
					const weightParts: string[] = [];
					if (gramsTotal > 0) weightParts.push(`${gramsTotal}g`);
					if (mlTotal > 0) weightParts.push(`${mlTotal}mL`);
					weightPill = weightParts.length ? weightParts.join(' + ') : null;
				} else {
					const pack = parsePackSize(sku.size.volume_size);
					let convertedPacks = 0;
					const unresolved: string[] = [];
					if (gramsTotal > 0) {
						if (pack?.grams) convertedPacks += Math.ceil(gramsTotal / pack.grams);
						else unresolved.push(`${gramsTotal}g`);
					}
					if (mlTotal > 0) {
						if (pack?.mL) convertedPacks += Math.ceil(mlTotal / pack.mL);
						else unresolved.push(`${mlTotal}mL`);
					}
					const total = countTotal + convertedPacks;
					count = total > 0 ? total : null;
					weightPill = unresolved.length ? unresolved.join(' + ') : null;
					weightUnresolved = unresolved.length > 0;
				}

				if (count == null && weightPill == null) count = parts.length;

				const totalPrice = priced.get(skuId) ?? null;

				return { sku, parts, count, weightPill, weightUnresolved, totalPrice };
			})
			.filter((g): g is SkuGroup => g != null);
		const unresolved: UnresolvedGroup[] = [...byItem.entries()].map(([itemId, parts]) => ({
			itemId,
			itemName: parts[0].item_name,
			parts
		}));
		return { resolved, unresolved };
	});

	// Sum of every resolved SKU group's own total — unresolved (no SKU
	// chosen) lines contribute nothing, same "flag, don't guess" rule as
	// their own row. null (shown as N/A) only when nothing on the list
	// has a price at all, not when some lines just lack one.
	let listTotal = $derived.by(() => {
		const prices = skuGroups.resolved.map((g) => g.totalPrice).filter((p): p is number => p != null);
		return prices.length ? prices.reduce((a, b) => a + b, 0) : null;
	});

	// Keyed by item id, not sku id — the sku id it's showing alternatives
	// *for* is exactly what a successful swap changes, so keying on that
	// would close the dropdown the instant you picked something.
	let openSkuDropdown: number | null = $state(null);

	function toggleSkuDropdown(itemId: number) {
		openSkuDropdown = openSkuDropdown === itemId ? null : itemId;
	}

	function alternativeSkus(sku: StoredSku): StoredSku[] {
		const pick = pickerItems.find((p) => p.item.id === sku.item_id);
		return pick ? pick.skus.filter((s) => s.id !== sku.id) : [];
	}

	// Every line currently resolved to this SKU shares it because they
	// all need the same item — swapping re-points all of them at once,
	// not just one line, so the group stays one coherent SKU choice.
	async function swapSku(group: SkuGroup, newSkuId: number) {
		try {
			for (const line of group.parts) {
				await invoke('set_shopping_list_item_sku', { lineId: line.id, skuId: newSkuId });
			}
			openSkuDropdown = null;
			await loadLines();
		} catch (e) {
			error = String(e);
		}
	}

	function neededDescription(parts: ShoppingListLine[]): string {
		return parts
			.map((p) => (p.amount != null && p.unit ? `${p.amount}${p.unit}` : null))
			.filter((s): s is string => s != null)
			.join(' + ');
	}

	// A recipe's "quantity" (how many batches) isn't stored anywhere as
	// its own number — it's implicit in the summed ingredient amounts,
	// which loadLines() can't reliably reverse back into a multiplier.
	// So the stepper's actual value lives here, keyed by recipe id, and
	// survives across reloads; loadLines() only falls back to 1 for a
	// recipe it's never seen a stepper change for.
	const recipeQuantities = new Map<number, number>();

	async function loadLines() {
		const requestId = ++linesRequestId;
		try {
			const fetched = await invoke<ShoppingListLine[]>('list_shopping_list_items', {
				listId: list.id
			});
			if (requestId !== linesRequestId) return; // a newer call has since started — drop this one
			lines = fetched;

			const byRecipe = new Map<number, number[]>();
			const byItem = new Map<number, { lineIds: number[]; amount: number | null; unit: string | null }>();
			for (const line of lines) {
				if (line.source_recipe_id != null) {
					const ids = byRecipe.get(line.source_recipe_id) ?? [];
					ids.push(line.id);
					byRecipe.set(line.source_recipe_id, ids);
				} else {
					const existing = byItem.get(line.item_id);
					if (existing) {
						// Extra lines beyond the first can exist (a different
						// unit, or leftover from data written before source
						// scoping was fixed) — displayed amount/unit and
						// what +/- and the typed input actually update
						// (lineIds[0], see setItemQuantity/setItemWeight)
						// must be the SAME line, or clicks can silently
						// change a row that isn't the one shown.
						existing.lineIds.push(line.id);
					} else {
						byItem.set(line.item_id, {
							lineIds: [line.id],
							amount: line.amount,
							unit: line.unit
						});
					}
				}
			}
			droppedEntries = [
				...[...byRecipe.entries()].map(
					([recipeId, lineIds]): DroppedEntry => ({
						kind: 'recipe',
						recipeId,
						lineIds,
						quantity: recipeQuantities.get(recipeId) ?? 1
					})
				),
				...[...byItem.entries()].map(
					([itemId, { lineIds, amount, unit }]): DroppedEntry => ({
						kind: 'item',
						itemId,
						lineIds,
						quantity: amount ?? 1,
						unit
					})
				)
			];
		} catch (e) {
			error = String(e);
		}
	}

	onMount(() => {
		loadPickerItems();
		loadPickerRecipes();
		loadLines();
	});

	function handleDragStart(e: DragEvent, kind: 'item' | 'recipe', id: number) {
		e.dataTransfer?.setData('application/json', JSON.stringify({ kind, id }));
	}

	// Dropping the same item/recipe again used to silently add another
	// line the widget's grouping wouldn't visibly reflect (the amount
	// changed underneath, but nothing on-screen told you that happened,
	// and it could also spawn a genuinely separate line if the unit
	// didn't match). Now it's blocked outright with an explanation —
	// the quantity stepper on the existing widget is how you add more.
	let duplicateWarning: string | null = $state(null);

	async function handleDrop(e: DragEvent) {
		e.preventDefault();
		const raw = e.dataTransfer?.getData('application/json');
		if (!raw) return;
		const { kind, id } = JSON.parse(raw) as { kind: 'item' | 'recipe'; id: number };
		if (kind === 'item') {
			const already = droppedEntries.some((d) => d.kind === 'item' && d.itemId === id);
			if (already) {
				const name = pickerItems.find((p) => p.item.id === id)?.item.name ?? 'This item';
				duplicateWarning = `${name} is already on this list — use its + / − to change the quantity`;
				return;
			}
			await dropItem(id);
		} else {
			const already = droppedEntries.some((d) => d.kind === 'recipe' && d.recipeId === id);
			if (already) {
				const name = pickerRecipes.find((p) => p.recipe.id === id)?.recipe.name ?? 'This recipe';
				duplicateWarning = `${name} is already on this list — use its + / − to change the quantity`;
				return;
			}
			await dropRecipe(id);
		}
	}

	async function dropItem(itemId: number) {
		try {
			// amount:1/unit:'count', not null — the widget always displays
			// "1" as its starting quantity, so the underlying line needs
			// to actually say that from the moment it's created. Leaving
			// it unset made the widget's "1" a display-only lie: the SKUs
			// needed total (read from the real line) correctly showed
			// nothing added until the first +/- click wrote a real value,
			// which looked like "dropping does nothing until you click
			// something else."
			await invoke('add_item_to_shopping_list', {
				listId: list.id,
				itemId,
				amount: 1,
				unit: 'count'
			});
			await loadLines();
		} catch (e) {
			error = String(e);
		}
	}

	async function dropRecipe(recipeId: number) {
		try {
			await invoke('add_recipe_to_shopping_list', {
				listId: list.id,
				recipeId,
				targetServings: null
			});
			await loadLines();
		} catch (e) {
			error = String(e);
		}
	}

	async function removeEntry(entry: DroppedEntry) {
		try {
			for (const lineId of entry.lineIds) {
				await invoke('remove_shopping_list_item', { lineId });
			}
			if (entry.kind === 'recipe') recipeQuantities.delete(entry.recipeId);
			await loadLines();
		} catch (e) {
			error = String(e);
		}
	}

	// Item quantity is a direct set — one line, unit fixed to "count".
	async function setItemQuantity(entry: { itemId: number; lineIds: number[] }, quantity: number) {
		if (quantity < 1 || entry.lineIds.length === 0) return;
		try {
			await invoke('set_shopping_list_item_amount', {
				lineId: entry.lineIds[0],
				amount: quantity,
				unit: 'count'
			});
			await loadLines();
		} catch (e) {
			error = String(e);
		}
	}

	// Only items with a SKU that's actually sold by weight (either its
	// default mode, or a dual-mode SKU like loose onions that offers
	// both) get the count/weight toggle — a plain each-only item like
	// bread has no sensible "500g of bread" reading.
	function isWeightEligible(pick: PickerItem): boolean {
		return pick.skus.some(
			(s) => s.quantity.unit.toLowerCase() === 'kg' || s.quantity.supports_both_each_and_kg
		);
	}

	// Same line, different unit — set_shopping_list_item_amount already
	// supports changing amount and unit together, so switching modes
	// doesn't need a delete+recreate.
	async function setItemWeight(entry: { lineIds: number[] }, grams: number) {
		if (grams <= 0 || entry.lineIds.length === 0) return;
		try {
			await invoke('set_shopping_list_item_amount', {
				lineId: entry.lineIds[0],
				amount: grams,
				unit: 'g'
			});
			await loadLines();
		} catch (e) {
			error = String(e);
		}
	}

	// Seeds the switch with the cheapest weight-capable SKU's own
	// minimum order amount (kg → g) rather than an arbitrary number —
	// "0.1kg steps, min 0.1kg" for loose onions becomes 100g, not a
	// guessed round figure that might not even be orderable.
	function defaultWeightGrams(pick: PickerItem): number {
		const weighable = pick.skus.filter(
			(s) => s.quantity.unit.toLowerCase() === 'kg' || s.quantity.supports_both_each_and_kg
		);
		const min = weighable.find((s) => s.quantity.min != null)?.quantity.min;
		return min != null ? Math.round(min * 1000) : 500;
	}

	// Rough cost for a gram amount, from the SKU's own $/kg cup price —
	// not the real pack-rounded price (that rounding lives server-side,
	// in commands.rs's RawCartNeed, used for the real cart-add), just an
	// at-a-glance estimate. null (shown as N/A) rather than a guess when
	// there's no cup price to go on.
	function weightCost(sku: StoredSku | null, grams: number): number | null {
		return sku?.size.cup_price != null ? (sku.size.cup_price * grams) / 1000 : null;
	}

	// The actual SKU currently assigned to a widget's line — not a
	// separately-recomputed "cheapest by sale_price" guess. The real
	// auto-pick (see cheapest_sku_id in Rust) chooses by cup_price, the
	// correct cross-pack comparison, so re-deriving "cheapest" here by
	// sale_price could quietly point at a *different* SKU than the one
	// actually resolved in "SKUs needed" — showing a price that didn't
	// match what was really picked. This also means a manual swap (see
	// the SKU dropdown below) is reflected here too, not just there.
	function lineSku(entry: { lineIds: number[] }): StoredSku | null {
		const line = lines.find((l) => entry.lineIds.includes(l.id));
		return line?.sku ? (skuById.get(line.sku.id) ?? null) : null;
	}

	// A dedicated backend command, not remove+add_recipe with a
	// servings-derived target — that broke for any recipe with no
	// `servings` set, since add_recipe's scale is always 1 unless both
	// a target and the recipe's own servings are present. This one takes
	// quantity as a direct multiplier, no servings involved at all.
	async function setRecipeQuantity(entry: { recipeId: number }, quantity: number) {
		if (quantity < 1) return;
		try {
			await invoke('set_shopping_list_recipe_quantity', {
				listId: list.id,
				recipeId: entry.recipeId,
				quantity
			});
			recipeQuantities.set(entry.recipeId, quantity);
			await loadLines();
		} catch (e) {
			error = String(e);
		}
	}
</script>

<div class="overlay">
	<aside class="sidebar">
		<nav class="sidebar-tabs">
			<button
				class="sidebar-tab"
				class:active={sidebarTab === 'recipes'}
				onclick={() => (sidebarTab = 'recipes')}
			>
				Recipes
			</button>
			<button
				class="sidebar-tab"
				class:active={sidebarTab === 'items'}
				onclick={() => (sidebarTab = 'items')}
			>
				Items
			</button>
		</nav>

		<input class="picker-search" type="text" placeholder="Search…" bind:value={pickerSearch} />

		<div class="picker-list">
			{#if sidebarTab === 'items'}
				{#each filteredPickerItems as pick (pick.item.id)}
					<div
						class="picker-widget"
						draggable="true"
						role="button"
						tabindex="0"
						ondragstart={(e) => handleDragStart(e, 'item', pick.item.id)}
					>
						<div class="picker-image">
							{#if pick.image}
								<img src={pick.image} alt="" />
							{:else}
								Image
							{/if}
						</div>
						<span class="picker-name">{pick.item.name || 'Name'}</span>
						{#if pick.price != null}
							<span class="picker-price">${pick.price.toFixed(2)}</span>
						{/if}
					</div>
				{:else}
					<p class="picker-empty">No items yet.</p>
				{/each}
			{:else}
				{#each filteredPickerRecipes as pick (pick.recipe.id)}
					<div
						class="picker-widget"
						draggable="true"
						role="button"
						tabindex="0"
						ondragstart={(e) => handleDragStart(e, 'recipe', pick.recipe.id)}
					>
						<div class="picker-image">
							{#if pick.recipe.image_url}
								<img src={pick.recipe.image_url} alt="" />
							{:else}
								Image
							{/if}
						</div>
						<span class="picker-name">{pick.recipe.name || 'Name'}</span>
						{#if pick.recipe.servings != null}
							<span class="picker-servings">Serves {pick.recipe.servings}</span>
						{/if}
					</div>
				{:else}
					<p class="picker-empty">No recipes yet.</p>
				{/each}
			{/if}
		</div>
	</aside>
	<section class="content">
		<div class="topbar">
			<button class="back" onclick={onClose}>← Back</button>
			<div class="topbar-actions">
				<CartAdd listIds={[list.id]} disabled={lines.length === 0} />
				<button class="delete-list" onclick={() => (confirmDeleteList = true)}>Delete List</button>
			</div>
		</div>
		{#if error}
			<p class="error">{error}</p>
		{/if}
		<input class="name" type="text" bind:value={name} onblur={saveName} placeholder="List name" />

		<h2 class="section-title">On this list</h2>
		<div
			class="drop-zone"
			class:empty={droppedEntries.length === 0}
			role="region"
			aria-label="Drop items or recipes here to add them to the list"
			ondragover={(e) => e.preventDefault()}
			ondrop={handleDrop}
		>
			{#each droppedEntries as entry (entry.kind + '-' + (entry.kind === 'item' ? entry.itemId : entry.recipeId))}
				{#if entry.kind === 'item'}
					{@const pick = pickerItems.find((p) => p.item.id === entry.itemId)}
					{#if pick}
						<div class="dropped-card">
							<span class="type-badge item">Item</span>
							<button class="remove-btn" aria-label="Remove" onclick={() => removeEntry(entry)}
								>×</button
							>
							<div class="dropped-header">
								<div class="dropped-image">
									{#if pick.image}
										<img src={pick.image} alt="" />
									{:else}
										Image
									{/if}
								</div>
								<span class="dropped-name">{pick.item.name}</span>
							</div>
							<div class="dropped-footer">
								{#if entry.unit === 'g' || entry.unit === 'mL'}
									<div class="quantity-stepper">
										<button
											aria-label="Decrease amount"
											onclick={() => setItemWeight(entry, entry.quantity - 50)}>−</button
										>
										<input
											class="weight-input"
											type="number"
											min="0"
											step="any"
											value={entry.quantity}
											onblur={(e) => setItemWeight(entry, Number(e.currentTarget.value))}
											onkeydown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
										/>
										<span class="weight-unit">{entry.unit}</span>
										<button
											aria-label="Increase amount"
											onclick={() => setItemWeight(entry, entry.quantity + 50)}>+</button
										>
									</div>
									<button
										class="mode-toggle"
										aria-label="Switch to quantity"
										onclick={() => setItemQuantity(entry, 1)}
									>
										⇄ ×
									</button>
									{#if weightCost(lineSku(entry), entry.quantity) != null}
										<span class="dropped-price"
											>${weightCost(lineSku(entry), entry.quantity)?.toFixed(2)}</span
										>
									{:else}
										<span class="dropped-price na">N/A</span>
									{/if}
								{:else}
									<div class="quantity-stepper">
										<button
											aria-label="Decrease quantity"
											onclick={() => setItemQuantity(entry, entry.quantity - 1)}>−</button
										>
										<input
											class="weight-input"
											type="number"
											min="1"
											step="1"
											value={entry.quantity}
											onblur={(e) => setItemQuantity(entry, Number(e.currentTarget.value))}
											onkeydown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
										/>
										<button
											aria-label="Increase quantity"
											onclick={() => setItemQuantity(entry, entry.quantity + 1)}>+</button
										>
									</div>
									{#if isWeightEligible(pick)}
										<button
											class="mode-toggle"
											aria-label="Switch to weight"
											onclick={() => setItemWeight(entry, defaultWeightGrams(pick))}
										>
											⇄ g
										</button>
									{/if}
									{#if lineSku(entry)?.price.sale_price != null}
										<span class="dropped-price"
											>${(lineSku(entry)!.price.sale_price! * entry.quantity).toFixed(2)}</span
										>
									{/if}
								{/if}
							</div>
						</div>
					{/if}
				{:else}
					{@const pick = pickerRecipes.find((p) => p.recipe.id === entry.recipeId)}
					{#if pick}
						<div class="dropped-card">
							<span class="type-badge recipe">Recipe</span>
							<button class="remove-btn" aria-label="Remove" onclick={() => removeEntry(entry)}
								>×</button
							>
							<div class="dropped-header">
								<div class="dropped-image">
									{#if pick.recipe.image_url}
										<img src={pick.recipe.image_url} alt="" />
									{:else}
										Image
									{/if}
								</div>
								<span class="dropped-name">{pick.recipe.name}</span>
							</div>
							<div class="dropped-footer">
								<div class="quantity-stepper">
									<button
										aria-label="Decrease quantity"
										onclick={() => setRecipeQuantity(entry, entry.quantity - 1)}>−</button
									>
									<input
										class="weight-input"
										type="number"
										min="1"
										step="1"
										value={entry.quantity}
										onblur={(e) => setRecipeQuantity(entry, Number(e.currentTarget.value))}
										onkeydown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
									/>
									<button
										aria-label="Increase quantity"
										onclick={() => setRecipeQuantity(entry, entry.quantity + 1)}>+</button
									>
								</div>
								{#if pick.recipe.servings != null}
									<span class="dropped-servings">Serves {pick.recipe.servings * entry.quantity}</span>
								{/if}
							</div>
						</div>
					{/if}
				{/if}
			{:else}
				<p class="drop-zone-message">Drag items or recipes here from the sidebar</p>
			{/each}
		</div>

		<h2 class="section-title">SKUs needed</h2>
		<div class="lines">
			{#each skuGroups.resolved as group (group.sku.id)}
				<div class="sku-group">
					<div class="sku-shell">
						{#if group.sku.images[0]}
							<img class="sku-thumb" src={group.sku.images[0]} alt={group.sku.name} />
						{/if}
						<div class="sku-info">
							<p class="sku-name">
								<span class="sku-name-text">{group.sku.name}</span>
								<button
									class="sku-swap-toggle"
									aria-label="Choose a different SKU"
									onclick={() => toggleSkuDropdown(group.sku.item_id)}
								>
									▾
								</button>
							</p>
							<p class="sku-meta">
								{group.sku.brand ?? ''}
								{group.sku.variety ?? ''}
								· sku {group.sku.sku}
								· ${group.sku.price.sale_price ?? '?'}
								{#if group.sku.price.is_special}
									<span class="special">was ${group.sku.price.original_price}</span>
								{/if}
								{#if group.sku.allergens.length}
									<span class="sku-allergens">⚠ {group.sku.allergens.join(', ')}</span>
								{/if}
							</p>
						</div>
						<div class="sku-totals">
							{#if group.count != null}
								<span class="sku-count-badge">×{group.count}</span>
							{/if}
							{#if group.weightPill}
								<span class="sku-weight-pill" class:unresolved={group.weightUnresolved}>
									{group.weightPill}
								</span>
							{/if}
							{#if group.totalPrice != null}
								<span class="sku-total-price">${group.totalPrice.toFixed(2)}</span>
							{/if}
						</div>
					</div>
					{#if openSkuDropdown === group.sku.item_id}
						<div class="sku-swap-dropdown">
							{#each alternativeSkus(group.sku) as alt (alt.id)}
								<button class="sku-swap-option" onclick={() => swapSku(group, alt.id)}>
									<div class="sku-swap-image">
										{#if alt.images[0]}
											<img src={alt.images[0]} alt="" />
										{:else}
											Image
										{/if}
									</div>
									<span class="sku-swap-name">{alt.name}</span>
									{#if alt.price.sale_price != null}
										<span class="sku-swap-price">${alt.price.sale_price.toFixed(2)}</span>
									{/if}
								</button>
							{:else}
								<p class="picker-empty">No other SKUs linked to this item.</p>
							{/each}
						</div>
					{/if}
				</div>
			{/each}
			{#each skuGroups.unresolved as group (group.itemId)}
				<div class="line-row">
					<span class="line-name">{group.itemName}</span>
					{#if neededDescription(group.parts)}
						<span class="line-amount">{neededDescription(group.parts)}</span>
					{/if}
					<span class="line-sku na">no SKU chosen</span>
				</div>
			{/each}
			{#if skuGroups.resolved.length === 0 && skuGroups.unresolved.length === 0}
				<p class="drop-zone-empty">Nothing on this list yet.</p>
			{/if}
		</div>

		<hr />
		<div class="list-total-row">
			<span class="list-total-label">Total</span>
			{#if listTotal != null}
				<span class="list-total-price">${listTotal.toFixed(2)}</span>
			{:else}
				<span class="list-total-price na">N/A</span>
			{/if}
		</div>
	</section>
</div>

{#if confirmDeleteList}
	<ConfirmDialog
		message={`Delete "${list.name || 'this list'}"? This can't be undone.`}
		onConfirm={() => {
			confirmDeleteList = false;
			deleteList();
		}}
		onCancel={() => (confirmDeleteList = false)}
	/>
{/if}

{#if duplicateWarning}
	<div
		class="warning-overlay"
		onclick={() => (duplicateWarning = null)}
		onkeydown={(e) => e.key === 'Escape' && (duplicateWarning = null)}
		role="presentation"
	>
		<div
			class="warning-box"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
			role="dialog"
			aria-modal="true"
			tabindex="-1"
		>
			<p>{duplicateWarning}</p>
			<button onclick={() => (duplicateWarning = null)}>OK</button>
		</div>
	</div>
{/if}

<style>
	.overlay {
		position: absolute;
		inset: 0;
		background: #1e1e1d;
		color: #fff;
		display: flex;
		z-index: 10;
	}

	.sidebar {
		flex: 0 0 288px;
		min-height: 0;
		background: #191918;
		padding: 1rem;
		overflow-y: auto;
	}

	.sidebar-tabs {
		display: flex;
		gap: 0.5rem;
	}

	.sidebar-tab {
		flex: 1 1 0;
		background: #232322;
		border: 1px solid #333;
		border-radius: 6px;
		color: #999;
		font-weight: bold;
		font-size: 0.8rem;
		padding: 0.5rem 0;
		cursor: pointer;
	}

	.sidebar-tab.active {
		background: #3a4a55;
		border-color: #3a4a55;
		color: #fff;
	}

	.picker-search {
		width: 100%;
		box-sizing: border-box;
		margin-top: 0.75rem;
		background: #232322;
		border: 1px solid #333;
		border-radius: 6px;
		color: #fff;
		font-size: 0.85rem;
		padding: 0.4rem 0.6rem;
	}

	.picker-search:focus {
		outline: none;
		border-color: #3a4a55;
	}

	.picker-list {
		margin-top: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.picker-empty {
		color: #999;
		font-size: 0.85rem;
	}

	.picker-widget {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		background: #232322;
		border-radius: 8px;
		padding: 0.5rem 0.6rem;
		cursor: grab;
	}

	.picker-widget:active {
		cursor: grabbing;
	}

	.picker-image {
		flex: 0 0 auto;
		width: 36px;
		height: 36px;
		border-radius: 50%;
		background: #fff;
		color: #000;
		font-size: 0.45rem;
		display: flex;
		align-items: center;
		justify-content: center;
		overflow: hidden;
	}

	.picker-image img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.picker-name {
		flex: 1 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-weight: bold;
		font-size: 0.8rem;
	}

	.picker-price {
		flex: 0 0 auto;
		font-size: 0.75rem;
		font-weight: bold;
		color: #95977e;
	}

	.picker-servings {
		flex: 0 0 auto;
		font-size: 0.7rem;
		color: #999;
		white-space: nowrap;
	}

	.content {
		flex: 1 1 auto;
		min-height: 0;
		overflow-y: auto;
		padding: 1.5rem;
	}

	.error {
		color: #ff8a80;
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

	.topbar-actions {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}

	.delete-list {
		background: none;
		border: 1px solid var(--color-error, #b3261e);
		border-radius: 6px;
		color: var(--color-error, #b3261e);
		font-weight: bold;
		font-size: 0.85rem;
		padding: 0.4rem 0.8rem;
		cursor: pointer;
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
	}

	.name:focus {
		outline: none;
	}

	.section-title {
		margin: 2rem 0 0.75rem;
		font-size: 1rem;
	}

	.drop-zone {
		min-height: 140px;
		background: #232322;
		border: 2px dashed #333;
		border-radius: 10px;
		padding: 1rem;
		display: flex;
		flex-wrap: wrap;
		align-content: flex-start;
		gap: 0.85rem;
	}

	.drop-zone.empty {
		justify-content: center;
		align-content: center;
	}

	.drop-zone-message {
		width: 100%;
		color: #999;
		font-size: 0.85rem;
		font-weight: bold;
		text-align: center;
		margin: 0;
	}

	.drop-zone-empty {
		color: #999;
		font-size: 0.85rem;
		margin: 0;
	}

	.dropped-card {
		position: relative;
		width: 238px;
		background: #2c2c2b;
		border-radius: 10px;
		padding: 0.85rem;
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: 0.5rem;
	}

	.type-badge {
		align-self: flex-start;
		padding: 0.15rem 0.55rem;
		border-radius: 999px;
		font-size: 0.65rem;
		font-weight: bold;
		text-transform: uppercase;
		letter-spacing: 0.02em;
	}

	.type-badge.item {
		background: #333;
		color: #ccc;
	}

	.type-badge.recipe {
		background: #3a4a55;
		color: #fff;
	}

	.remove-btn {
		position: absolute;
		top: 0.5rem;
		right: 0.5rem;
		width: 1.4rem;
		height: 1.4rem;
		border: none;
		border-radius: 50%;
		background: #333;
		color: #fff;
		font-size: 0.85rem;
		line-height: 1;
		cursor: pointer;
	}

	.dropped-header {
		display: flex;
		align-items: center;
		gap: 0.65rem;
		padding-right: 1.5rem;
	}

	.dropped-image {
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
	}

	.dropped-image img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.dropped-name {
		flex: 1 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-weight: bold;
		font-size: 1rem;
	}

	.dropped-footer {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 0.4rem;
	}

	.mode-toggle {
		flex: 0 0 auto;
		background: #333;
		border: none;
		border-radius: 999px;
		color: #ccc;
		font-size: 0.7rem;
		font-weight: bold;
		padding: 0.2rem 0.5rem;
		cursor: pointer;
	}

	.quantity-stepper {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.85rem;
		font-weight: bold;
	}

	.quantity-stepper button {
		width: 1.4rem;
		height: 1.4rem;
		border: none;
		border-radius: 50%;
		background: #333;
		color: #fff;
		font-size: 0.9rem;
		line-height: 1;
		cursor: pointer;
	}

	.weight-input {
		width: 3.2rem;
		box-sizing: border-box;
		background: #1e1e1d;
		border: 1px solid #444;
		border-radius: 4px;
		color: #fff;
		font-size: 0.8rem;
		font-weight: bold;
		text-align: center;
		padding: 0.15rem 0;
	}

	.weight-input:focus {
		outline: none;
		border-color: #3a4a55;
	}

	.weight-input::-webkit-inner-spin-button,
	.weight-input::-webkit-outer-spin-button {
		-webkit-appearance: none;
		margin: 0;
	}

	.weight-unit {
		color: #999;
		font-size: 0.75rem;
	}

	.dropped-price {
		font-size: 1.1rem;
		font-weight: bold;
		color: #95977e;
	}

	.dropped-price.na {
		font-size: 0.85rem;
		color: var(--color-warning, #c99a3d);
	}

	.dropped-servings {
		font-size: 0.75rem;
		color: #999;
	}

	.lines {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.line-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		background: #232322;
		border-radius: 8px;
		padding: 0.6rem 0.9rem;
	}

	.line-name {
		flex: 1 1 auto;
		font-weight: bold;
		font-size: 0.9rem;
	}

	.line-amount {
		flex: 0 0 auto;
		color: #999;
		font-size: 0.8rem;
	}

	.line-sku {
		flex: 0 0 auto;
		color: #ccc;
		font-size: 0.8rem;
	}

	.line-sku.na {
		color: var(--color-warning, #c99a3d);
	}

	.sku-shell {
		display: flex;
		gap: 0.75rem;
		align-items: center;
		background: #232322;
		border-radius: 8px;
		padding: 0.4rem 0.75rem;
	}

	.sku-thumb {
		width: 36px;
		height: 36px;
		object-fit: contain;
		background: #fff;
		border-radius: 5px;
		flex-shrink: 0;
	}

	.sku-info {
		flex: 1 1 auto;
		min-width: 0;
	}

	.sku-info p {
		margin: 0;
		font-size: 0.85rem;
	}

	.sku-name {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		font-weight: bold;
	}

	.sku-name-text {
		text-transform: capitalize;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}

	.sku-meta {
		color: #999;
		text-transform: capitalize;
		font-size: 0.75rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.sku-meta .special {
		color: #ff8a80;
		text-decoration: line-through;
		margin-left: 0.3rem;
	}

	.sku-meta .sku-allergens {
		color: #d9a441;
		margin-left: 0.3rem;
	}

	.sku-totals {
		flex: 0 0 auto;
		display: flex;
		flex-direction: row;
		align-items: center;
		gap: 0.6rem;
	}

	.sku-count-badge {
		flex: 0 0 auto;
		width: 1.7rem;
		height: 1.7rem;
		border-radius: 50%;
		background: #333;
		color: #fff;
		font-size: 0.75rem;
		font-weight: bold;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.sku-weight-pill {
		flex: 0 0 auto;
		background: #333;
		color: #ccc;
		border-radius: 999px;
		padding: 0.2rem 0.6rem;
		font-size: 0.7rem;
		font-weight: bold;
		white-space: nowrap;
	}

	.sku-weight-pill.unresolved {
		background: none;
		border: 1px solid var(--color-warning, #c99a3d);
		color: var(--color-warning, #c99a3d);
	}

	.sku-total-price {
		color: #95977e;
		font-weight: bold;
		font-size: 1.2rem;
	}

	.sku-group {
		display: flex;
		flex-direction: column;
	}

	.sku-swap-toggle {
		flex: 0 0 auto;
		background: none;
		border: none;
		color: #999;
		font-size: 0.9rem;
		line-height: 1;
		padding: 0 0.2rem;
		cursor: pointer;
	}

	.sku-swap-toggle:hover {
		color: #fff;
	}

	.sku-swap-dropdown {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		background: #1e1e1d;
		border: 1px dashed #333;
		border-radius: 8px;
		padding: 0.6rem;
		margin: 0.4rem 0 0.2rem 1.5rem;
	}

	.sku-swap-option {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		background: #232322;
		border: none;
		border-radius: 6px;
		padding: 0.4rem 0.6rem;
		cursor: pointer;
		text-align: left;
	}

	.sku-swap-option:hover {
		background: #2c2c2b;
	}

	.sku-swap-image {
		flex: 0 0 auto;
		width: 32px;
		height: 32px;
		border-radius: 50%;
		background: #fff;
		color: #000;
		font-size: 0.4rem;
		display: flex;
		align-items: center;
		justify-content: center;
		overflow: hidden;
	}

	.sku-swap-image img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.sku-swap-name {
		flex: 1 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: #fff;
		font-size: 0.8rem;
		font-weight: bold;
		text-transform: capitalize;
	}

	.sku-swap-price {
		flex: 0 0 auto;
		color: #95977e;
		font-weight: bold;
		font-size: 0.8rem;
	}

	.warning-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
	}

	.warning-box {
		background: #232322;
		border: 1px solid var(--color-warning, #c99a3d);
		border-radius: 12px;
		padding: 1.5rem;
		width: 320px;
		max-width: calc(100% - 2rem);
		box-sizing: border-box;
		color: #fff;
		text-align: center;
	}

	.warning-box p {
		margin: 0 0 1.5rem;
		font-size: 0.95rem;
	}

	.warning-box button {
		border: none;
		border-radius: 6px;
		background: var(--color-warning, #c99a3d);
		color: #1e1e1d;
		font-weight: bold;
		font-size: 0.85rem;
		padding: 0.5rem 1.5rem;
		cursor: pointer;
	}

	hr {
		border: none;
		border-top: 3px dashed #333;
		margin: 1.5rem 0;
	}

	.list-total-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.list-total-label {
		font-size: 1.1rem;
		font-weight: bold;
	}

	.list-total-price {
		font-size: 1.6rem;
		font-weight: bold;
		color: #95977e;
	}

	.list-total-price.na {
		font-size: 1rem;
		color: var(--color-warning, #c99a3d);
	}
</style>
