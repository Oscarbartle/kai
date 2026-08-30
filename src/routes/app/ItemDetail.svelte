<!--
	Full-screen item detail overlay, opened by clicking a Pantry widget.
	Owns all the Item/SKU/tag CRUD itself (mirrors what the old /items
	page did) — the parent just hands it an item id and gets told when
	to close/refresh.
-->
<script lang="ts">
	import { invoke } from '@tauri-apps/api/core';
	import { tick } from 'svelte';
	import ConfirmDialog from './ConfirmDialog.svelte';

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
	}

	interface SkuData {
		provider: string;
		sku: string;
		name: string;
		brand: string | null;
		variety: string | null;
		price: {
			original_price: number | null;
			sale_price: number | null;
			is_special: boolean;
			save_percentage: number | null;
			promotion_start_date: string | null;
			promotion_end_date: string | null;
		};
		size: {
			cup_price: number | null;
			cup_measure: string | null;
			package_type: string | null;
			volume_size: string | null;
		};
		quantity: {
			unit: string;
			min: number | null;
			max: number | null;
			increment: number | null;
			supports_both_each_and_kg: boolean;
			average_weight_per_unit: number | null;
		};
		availability_status: string | null;
		stock_level: number | null;
		images: string[];
		allergens: string[];
		ingredients: string[];
	}

	interface StoredSku extends SkuData {
		id: number;
		item_id: number;
		is_preferred: boolean;
	}

	interface SkuSlot {
		id: string;
		status: 'input' | 'loading' | 'loaded' | 'error';
		inputValue: string;
		data: SkuData | null;
		error: string | null;
		dbId: number | null;
		saveError: string | null;
		refreshing: boolean;
		refreshError: string | null;
		// Trumps the item's cheapest_by setting entirely for the
		// shopping-list auto-pick — at most one true per item.
		isPreferred: boolean;
	}

	let { item, onClose, onDeleted }: {
		item: DbItem;
		onClose: () => void;
		onDeleted: () => void;
	} = $props();

	let name: string = $state(item.name);
	let isPerishable: boolean = $state(item.is_perishable);
	let imageUrlDraft: string = $state(item.image_url ?? '');
	let tags: Tag[] = $state([]);
	let tagInput: string = $state('');
	let tagError: string | null = $state(null);
	let skuSlots: SkuSlot[] = $state([]);
	let error: string | null = $state(null);

	function skuSlotFromStored(stored: StoredSku): SkuSlot {
		const { id, item_id, is_preferred, ...sku } = stored;
		return {
			id: crypto.randomUUID(),
			status: 'loaded',
			inputValue: '',
			data: sku,
			error: null,
			dbId: id,
			saveError: null,
			refreshing: false,
			refreshError: null,
			isPreferred: is_preferred
		};
	}

	async function load() {
		try {
			const [storedSkus, itemTags] = await Promise.all([
				invoke<StoredSku[]>('list_skus_for_item', { itemId: item.id }),
				invoke<Tag[]>('list_tags_for_item', { itemId: item.id })
			]);
			skuSlots = storedSkus.map(skuSlotFromStored);
			tags = itemTags;
		} catch (e) {
			error = String(e);
		}
	}

	load();

	async function saveName() {
		const trimmed = name.trim();
		if (!trimmed || trimmed === item.name) {
			name = item.name;
			return;
		}
		try {
			const updated = await invoke<DbItem>('update_item_name', { itemId: item.id, name: trimmed });
			item = updated;
			name = updated.name;
		} catch (e) {
			error = String(e);
		}
	}

	async function saveImageUrl() {
		editingImageUrl = false;
		const trimmed = imageUrlDraft.trim();
		if (trimmed === (item.image_url ?? '')) return;
		try {
			const updated = await invoke<DbItem>('set_item_image_url', {
				itemId: item.id,
				imageUrl: trimmed || null
			});
			item = updated;
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

	async function togglePerishable() {
		isPerishable = !isPerishable;
		try {
			await invoke('set_item_perishable', { itemId: item.id, isPerishable });
		} catch (e) {
			error = String(e);
			isPerishable = !isPerishable;
		}
	}

	// Which metric the shopping-list auto-pick compares this item's SKUs
	// by — plain total cost (default) or $/kg-$/L cup price, per item
	// rather than a single global rule (see CLAUDE.md).
	let cheapestBy: string = $state(item.cheapest_by);

	async function setCheapestBy(value: string) {
		const previous = cheapestBy;
		cheapestBy = value;
		try {
			item = await invoke<DbItem>('set_item_cheapest_by', { itemId: item.id, cheapestBy: value });
		} catch (e) {
			error = String(e);
			cheapestBy = previous;
		}
	}

	async function addTag() {
		const name = tagInput.trim();
		if (!name) return;
		tagError = null;
		try {
			const tag = await invoke<Tag>('add_tag_to_item', { itemId: item.id, name });
			if (!tags.some((t) => t.id === tag.id)) tags.push(tag);
			tagInput = '';
		} catch (e) {
			tagError = String(e);
		}
	}

	async function removeTag(tag: Tag) {
		try {
			await invoke('remove_tag_from_item', { itemId: item.id, tagId: tag.id });
			tags = tags.filter((t) => t.id !== tag.id);
		} catch (e) {
			tagError = String(e);
		}
	}

	function addSkuSlot() {
		// Unshift, not push — with a long SKU list already loaded, adding
		// at the bottom meant scrolling down to find the new input.
		skuSlots.unshift({
			id: crypto.randomUUID(),
			status: 'input',
			inputValue: '',
			data: null,
			error: null,
			dbId: null,
			saveError: null,
			refreshing: false,
			refreshError: null,
			isPreferred: false
		});
	}

	// Reloads every SKU slot from the backend rather than patching
	// isPreferred locally — setting one preferred clears any other
	// preferred SKU for the same item server-side (see
	// db::skus::set_preferred), and re-fetching is the simplest way to
	// stay in sync with that without duplicating the exclusivity rule
	// here too.
	async function togglePreferred(slot: SkuSlot) {
		if (slot.dbId == null) return;
		try {
			await invoke('set_sku_preferred', { skuId: slot.dbId, isPreferred: !slot.isPreferred });
			const stored = await invoke<StoredSku[]>('list_skus_for_item', { itemId: item.id });
			skuSlots = stored.map(skuSlotFromStored);
		} catch (e) {
			error = String(e);
		}
	}

	async function submitSku(slot: SkuSlot) {
		if (!slot.inputValue.trim()) return;
		slot.status = 'loading';
		slot.error = null;
		try {
			slot.data = await invoke<SkuData>('fetch_woolworths_sku', { input: slot.inputValue });
			slot.status = 'loaded';
		} catch (e) {
			slot.error = String(e);
			slot.status = 'error';
			return;
		}
		try {
			const stored = await invoke<StoredSku>('save_sku_to_item', { itemId: item.id, sku: slot.data });
			slot.dbId = stored.id;
		} catch (e) {
			slot.saveError = String(e);
		}
	}

	let confirmDeleteSku: SkuSlot | null = $state(null);
	let confirmDeleteItem: boolean = $state(false);

	async function deleteSku(slot: SkuSlot) {
		if (slot.dbId != null) {
			try {
				await invoke('delete_sku', { skuId: slot.dbId });
			} catch (e) {
				slot.error = String(e);
				slot.status = 'error';
				return;
			}
		}
		skuSlots = skuSlots.filter((s) => s.id !== slot.id);
	}

	async function refreshOneSku(slot: SkuSlot) {
		if (slot.dbId == null || slot.refreshing) return;
		slot.refreshing = true;
		slot.refreshError = null;
		try {
			const updated = await invoke<StoredSku>('refresh_sku', { skuId: slot.dbId });
			const { id, item_id, ...sku } = updated;
			slot.data = sku;
		} catch (e) {
			slot.refreshError = String(e);
		} finally {
			slot.refreshing = false;
		}
	}

	let refreshingAll: boolean = $state(false);

	async function refreshAllSkus() {
		if (refreshingAll) return;
		refreshingAll = true;
		try {
			const stored = await invoke<StoredSku[]>('refresh_skus_for_item', { itemId: item.id });
			skuSlots = stored.map(skuSlotFromStored);
		} catch (e) {
			error = String(e);
		} finally {
			refreshingAll = false;
		}
	}

	async function deleteItem() {
		try {
			await invoke('delete_item', { itemId: item.id });
			onDeleted();
			onClose();
		} catch (e) {
			error = String(e);
		}
	}

	function formatPromoDate(iso: string): string {
		const d = new Date(iso);
		return isNaN(d.getTime()) ? iso : d.toLocaleDateString();
	}

	function soldByWeight(quantity: SkuData['quantity']): boolean {
		return quantity.unit.toLowerCase() === 'kg';
	}

	function quantityDescription(quantity: SkuData['quantity']): string {
		if (quantity.supports_both_each_and_kg) {
			const each =
				quantity.average_weight_per_unit != null
					? ` (~${quantity.average_weight_per_unit}kg each)`
					: '';
			return `sold by weight or individually${each}`;
		}
		if (!soldByWeight(quantity)) return 'sold individually';
		const steps = quantity.increment != null ? `${quantity.increment}kg steps` : '';
		const min = quantity.min != null ? `min ${quantity.min}kg` : '';
		return ['sold by weight', steps, min].filter(Boolean).join(', ');
	}

	const heroImage = $derived(
		item.image_url ?? skuSlots.find((s) => s.data?.images[0])?.data?.images[0] ?? null
	);
</script>

<div class="overlay">
	<div class="topbar">
		<button class="back" onclick={onClose}>← Back</button>
		<button class="delete-item" onclick={() => (confirmDeleteItem = true)}>Delete Item</button>
	</div>

	{#if error}
		<p class="error">{error}</p>
	{/if}

	<div class="hero">
		<div class="hero-image-block">
			<div class="hero-image">
				{#if heroImage}
					<img src={heroImage} alt={name} />
				{:else}
					Image
				{/if}
			</div>
			{#if editingImageUrl}
				<input
					class="image-url-input"
					type="text"
					placeholder="Image URL (overrides SKU image)"
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
			<input class="name" type="text" bind:value={name} onblur={saveName} placeholder="Item name" />
			<button
				class="perishable-pill"
				class:yes={isPerishable}
				class:no={!isPerishable}
				onclick={togglePerishable}
			>
				{isPerishable ? 'Perishable' : 'Not perishable'}
			</button>
			<div class="cheapest-by">
				<span class="cheapest-by-label">Cheapest by:</span>
				<button
					class="cheapest-by-option"
					class:active={cheapestBy === 'total'}
					onclick={() => setCheapestBy('total')}
				>
					Total cost
				</button>
				<button
					class="cheapest-by-option"
					class:active={cheapestBy === 'unit'}
					onclick={() => setCheapestBy('unit')}
				>
					Unit price
				</button>
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

	<section class="skus">
		<div class="skus-header">
			<h2>SKUs</h2>
			<div class="skus-header-actions">
				<button class="refresh-all" disabled={refreshingAll} onclick={refreshAllSkus}>
					{refreshingAll ? 'Refreshing…' : '⟳ Refresh all'}
				</button>
				<button class="add-sku" onclick={addSkuSlot}>+ SKU</button>
			</div>
		</div>

		{#each skuSlots as slot (slot.id)}
			<div class="sku-shell">
				{#if slot.status === 'input' || slot.status === 'error'}
					<div class="sku-input-row">
						<input
							type="text"
							placeholder="Paste product URL or stock code"
							bind:value={slot.inputValue}
							onkeydown={(e) => e.key === 'Enter' && submitSku(slot)}
						/>
						<button onclick={() => submitSku(slot)}>Add</button>
					</div>
					{#if slot.status === 'error'}
						<p class="inline-error">{slot.error}</p>
					{/if}
				{:else if slot.status === 'loading'}
					<p class="muted">Loading…</p>
				{:else if slot.status === 'loaded' && slot.data}
					<div class="sku-actions">
						<button
							class="star-sku"
							class:active={slot.isPreferred}
							aria-label={slot.isPreferred ? 'Unset as preferred SKU' : 'Set as preferred SKU'}
							onclick={() => togglePreferred(slot)}
						>
							{slot.isPreferred ? '★' : '☆'}
						</button>
						<button
							class="refresh-sku"
							aria-label="Refresh SKU"
							disabled={slot.refreshing}
							onclick={() => refreshOneSku(slot)}
						>
							{slot.refreshing ? '…' : '⟳'}
						</button>
						<button class="delete-sku" onclick={() => (confirmDeleteSku = slot)}>×</button>
					</div>
					<div class="sku-loaded">
						{#if slot.data.images[0]}
							<img class="sku-thumb" src={slot.data.images[0]} alt={slot.data.name} />
						{/if}
						<div class="sku-info">
							<p class="sku-name">{slot.data.name}</p>
							{#if slot.saveError}
								<p class="inline-error">{slot.saveError}</p>
							{:else if slot.dbId == null}
								<p class="muted">saving…</p>
							{/if}
							{#if slot.refreshError}
								<p class="inline-error">Refresh failed: {slot.refreshError}</p>
							{/if}
							<p class="sku-meta">
								{slot.data.brand ?? ''}
								{slot.data.variety ?? ''}
								· sku {slot.data.sku}
							</p>
							<p class="sku-price">
								${slot.data.price.sale_price ?? '?'}
								{#if slot.data.price.is_special}
									<span class="special">was ${slot.data.price.original_price}</span>
								{/if}
								{#if slot.data.size.cup_price && slot.data.size.cup_measure}
									<span class="unit-price">
										(${slot.data.size.cup_price}/{slot.data.size.cup_measure})
									</span>
								{/if}
							</p>
							{#if slot.data.price.is_special && slot.data.price.promotion_end_date}
								<p class="sku-promo">
									Special until {formatPromoDate(slot.data.price.promotion_end_date)}
								</p>
							{/if}
							<p class="sku-availability">
								{slot.data.availability_status ?? 'unknown availability'}
								· {quantityDescription(slot.data.quantity)}
							</p>
							{#if slot.data.allergens.length}
								<p class="sku-allergens">⚠ {slot.data.allergens.join(', ')}</p>
							{/if}
						</div>
					</div>
				{/if}
			</div>
		{:else}
			<p class="muted">No SKUs linked yet.</p>
		{/each}
	</section>
</div>

{#if confirmDeleteItem}
	<ConfirmDialog
		message={`Delete "${item.name || 'this item'}"? This also removes its linked SKUs. This can't be undone.`}
		onConfirm={() => {
			confirmDeleteItem = false;
			deleteItem();
		}}
		onCancel={() => (confirmDeleteItem = false)}
	/>
{/if}

{#if confirmDeleteSku}
	<ConfirmDialog
		message={`Delete SKU "${confirmDeleteSku.data?.name ?? confirmDeleteSku.data?.sku ?? ''}"?`}
		onConfirm={() => {
			const slot = confirmDeleteSku!;
			confirmDeleteSku = null;
			deleteSku(slot);
		}}
		onCancel={() => (confirmDeleteSku = null)}
	/>
{/if}

<style>
	.overlay {
		position: absolute;
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
		border: 1px solid #b3261e;
		border-radius: 6px;
		color: #b3261e;
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

	.image-url-input:focus {
		outline: none;
		border-color: #3a4a55;
	}

	.image-url-row {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.4rem;
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

	.perishable-pill {
		border: none;
		border-radius: 999px;
		padding: 0.25rem 0.8rem;
		font-size: 0.75rem;
		font-weight: bold;
		color: #fff;
		cursor: pointer;
	}

	.perishable-pill.yes {
		background: var(--color-warning);
	}

	.perishable-pill.no {
		background: var(--color-error);
	}

	.cheapest-by {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin-top: 0.75rem;
	}

	.cheapest-by-label {
		font-size: 0.75rem;
		color: #999;
	}

	.cheapest-by-option {
		background: #232322;
		border: 1px solid #333;
		border-radius: 999px;
		color: #999;
		font-size: 0.7rem;
		font-weight: bold;
		padding: 0.2rem 0.6rem;
		cursor: pointer;
	}

	.cheapest-by-option.active {
		background: #3a4a55;
		border-color: #3a4a55;
		color: #fff;
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

	.skus-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 0.75rem;
	}

	.skus-header h2 {
		margin: 0;
		font-size: 1rem;
	}

	.skus-header-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.add-sku,
	.refresh-all {
		background: none;
		border: 1px solid #555;
		border-radius: 6px;
		color: #fff;
		font-weight: bold;
		font-size: 0.8rem;
		padding: 0.35rem 0.7rem;
		cursor: pointer;
	}

	.refresh-all:disabled {
		opacity: 0.5;
		cursor: default;
	}

	.skus {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}

	.muted {
		color: #999;
		font-size: 0.85rem;
	}

	.sku-shell {
		position: relative;
		background: #232322;
		border-radius: 10px;
		padding: 0.75rem 1rem;
	}

	.sku-input-row {
		display: flex;
		gap: 0.5rem;
	}

	.sku-input-row input {
		flex: 1;
		box-sizing: border-box;
		padding: 0.4rem 0.6rem;
		border-radius: 6px;
		border: 1px solid #555;
		background: #1e1e1d;
		color: #fff;
		font-size: 0.85rem;
	}

	.sku-input-row button {
		border: 1px solid #555;
		border-radius: 6px;
		background: none;
		color: #fff;
		font-size: 0.8rem;
		padding: 0.3rem 0.8rem;
		cursor: pointer;
	}

	.sku-actions {
		position: absolute;
		top: 0.6rem;
		right: 0.7rem;
		display: flex;
		gap: 0.4rem;
	}

	.star-sku,
	.refresh-sku,
	.delete-sku {
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

	.star-sku.active {
		background: var(--color-warning, #c99a3d);
		color: #1e1e1d;
	}

	.refresh-sku:disabled {
		opacity: 0.5;
		cursor: default;
	}

	.sku-loaded {
		display: flex;
		gap: 0.75rem;
		align-items: flex-start;
		padding-right: 5.2rem;
	}

	.sku-thumb {
		width: 56px;
		height: 56px;
		object-fit: contain;
		background: #fff;
		border-radius: 6px;
		flex-shrink: 0;
	}

	.sku-info p {
		margin: 0 0 0.2rem;
		font-size: 0.85rem;
	}

	.sku-name {
		font-weight: bold;
		text-transform: capitalize;
	}

	.sku-meta {
		color: #999;
		text-transform: capitalize;
	}

	.sku-price .special {
		color: #ff8a80;
		text-decoration: line-through;
		margin-left: 0.3rem;
		font-size: 0.8rem;
	}

	.sku-price .unit-price {
		color: #999;
		font-size: 0.8rem;
		margin-left: 0.3rem;
	}

	.sku-availability {
		color: #999;
		font-size: 0.75rem;
	}

	.sku-promo {
		color: #ff8a80;
		font-size: 0.75rem;
	}

	.sku-allergens {
		color: #d9a441;
		font-size: 0.75rem;
	}
</style>
