<!--
	The whole "send these lists to the real Woolworths cart" flow in one
	place: login check (prompt if signed out) → omission check (review
	pop-up if something didn't make the list) → send → show what actually
	happened → open the cart. Login is checked first, ahead of the
	omission review, so there's no point reviewing anything if the next
	step is just "go sign in and try again". Used by both the Shopping
	Lists tab's multi-select and a single list's own detail page, so the
	two can't drift apart.
-->
<script lang="ts">
	import { invoke } from '@tauri-apps/api/core';
	import { priceSkuGroups, sumSkuGroupTotals, type PricingLine, type PricingSku } from './shoppingListPricing';

	interface CartLineResult {
		name: string;
		sku: string;
		quantity: number;
		pricing_unit: string;
		ok: boolean;
		error: string | null;
	}

	interface CartAddSummary {
		results: CartLineResult[];
	}

	interface OmittedIngredient {
		recipe_id: number;
		recipe_name: string;
		item_id: number;
		item_name: string;
		amount: number | null;
		unit: string | null;
	}

	interface OmittedPerishable {
		item_id: number;
		item_name: string;
	}

	interface OmissionReport {
		recipe_ingredients: OmittedIngredient[];
		perishables: OmittedPerishable[];
	}

	// A "+ Add" pick from the omission pop-up, staged locally for *this*
	// send only — never written to shopping_list_items. Writing it to
	// the list was the previous version's approach, and it broke the
	// whole point of the check: once "rice" was a real line, it stayed
	// on the list forever (nothing ever clears it), so it silently
	// looked "already handled" on every future checkout instead of
	// being asked about again. The list stays the list; a one-off
	// "actually I need this today" only affects the cart going out now.
	interface ExtraItem {
		item_id: number;
		amount: number;
		unit: string;
		name: string;
	}

	let {
		listIds,
		label = 'Add to Woolworths cart',
		disabled = false
	}: {
		listIds: number[];
		label?: string;
		disabled?: boolean;
	} = $props();

	type Phase = 'idle' | 'checking' | 'sending';

	let phase: Phase = $state('idle');
	let needsLogin: boolean = $state(false);
	let summary = $state<CartAddSummary | null>(null);
	let omissions = $state<OmissionReport | null>(null);
	let extraItems: ExtraItem[] = $state([]);
	let error: string | null = $state(null);

	// The omission pop-up's own running total — the real list(s)' total
	// plus whatever's been staged via "+ Add" so far. Recomputed (not
	// just incremented) on every add, via the same shared pricing logic
	// the Shopping Lists tab and list detail page use, so it can't
	// disagree with either of them.
	let omissionTotal: number | null = $state(null);
	let omissionTotalWithDelivery: number | null = $state(null);
	let deliveryFee: number = $state(14);

	function cheapestSkuId(skus: PricingSku[]): number | null {
		const priced = skus.filter((s) => s.price.sale_price != null);
		if (!priced.length) return null;
		return priced.reduce((min, s) => (s.price.sale_price! < min.price.sale_price! ? s : min)).id;
	}

	async function refreshOmissionTotal() {
		try {
			const [lineLists, fee] = await Promise.all([
				Promise.all(
					listIds.map((listId) =>
						invoke<{ item_id: number; amount: number | null; unit: string | null; sku: { id: number } | null }[]>(
							'list_shopping_list_items',
							{ listId }
						)
					)
				),
				invoke<number>('get_delivery_fee')
			]);
			deliveryFee = fee;
			const lines = lineLists.flat();

			const itemIds = new Set<number>([
				...lines.map((l) => l.item_id),
				...extraItems.map((e) => e.item_id)
			]);
			const skusByItem = new Map<number, PricingSku[]>();
			await Promise.all(
				[...itemIds].map(async (itemId) => {
					skusByItem.set(itemId, await invoke<PricingSku[]>('list_skus_for_item', { itemId }));
				})
			);

			const pricingLines: PricingLine[] = [
				...lines.map((l) => ({ amount: l.amount, unit: l.unit, sku: l.sku })),
				// Same cheapest-by-sale-price pick a fresh item-drop starts
				// with — an estimate for this preview, not necessarily the
				// exact SKU the real send resolves to (which also weighs a
				// preferred SKU / cheapest_by="unit"), but close enough for
				// "roughly what will this cost".
				...extraItems.flatMap((e) => {
					const skuId = cheapestSkuId(skusByItem.get(e.item_id) ?? []);
					return skuId != null ? [{ amount: e.amount, unit: e.unit, sku: { id: skuId } }] : [];
				})
			];
			const skuById = new Map([...skusByItem.values()].flat().map((s) => [s.id, s]));

			omissionTotal = sumSkuGroupTotals(priceSkuGroups(pricingLines, skuById));
			omissionTotalWithDelivery = omissionTotal != null ? omissionTotal + deliveryFee : null;
		} catch {
			// Non-critical for the pop-up itself — just don't show a total
			// rather than surfacing an error over what's otherwise a
			// working review flow.
			omissionTotal = null;
			omissionTotalWithDelivery = null;
		}
	}

	let succeeded: CartLineResult[] = $derived(
		summary ? summary.results.filter((r: CartLineResult) => r.ok) : []
	);
	let failed: CartLineResult[] = $derived(
		summary ? summary.results.filter((r: CartLineResult) => !r.ok) : []
	);

	async function send() {
		if (!listIds.length) return;
		error = null;
		summary = null;
		// Fresh every time — nothing from a previous, possibly-cancelled
		// checkout attempt should carry over into this one.
		extraItems = [];
		omissionTotal = null;
		omissionTotalWithDelivery = null;

		// Login is checked first, before anything else — no point
		// reviewing omissions (or doing anything else) if the very next
		// step is going to be "go sign in and try again".
		phase = 'checking';
		try {
			const loggedIn = await invoke<boolean>('woolworths_login_status');
			if (!loggedIn) {
				needsLogin = true;
				phase = 'idle';
				return;
			}
		} catch (e) {
			error = String(e);
			phase = 'idle';
			return;
		}

		try {
			const report = await invoke<OmissionReport>('list_omitted_shopping_list_items', {
				listIds
			});
			if (report.recipe_ingredients.length || report.perishables.length) {
				omissions = report;
				phase = 'idle';
				refreshOmissionTotal();
				return;
			}
		} catch (e) {
			error = String(e);
			phase = 'idle';
			return;
		}

		await sendToCart();
	}

	async function continueToCart() {
		omissions = null;
		await sendToCart();
	}

	async function sendToCart() {
		phase = 'sending';
		try {
			summary = await invoke<CartAddSummary>('add_shopping_lists_to_cart', {
				listIds,
				extraItems: extraItems.map((e) => ({ itemId: e.item_id, amount: e.amount, unit: e.unit }))
			});
			// Only jump to the cart if something actually landed in it —
			// opening it after a total failure would just be confusing.
			if (summary.results.some((r) => r.ok)) {
				await invoke('open_woolworths_cart');
			}
		} catch (e) {
			error = String(e);
		} finally {
			phase = 'idle';
		}
	}

	async function logIn() {
		try {
			await invoke('open_woolworths_login');
		} catch (e) {
			error = String(e);
		}
	}

	// Moves the pick from the pop-up into extraItems — purely local
	// state, no backend call, nothing written anywhere. See ExtraItem
	// above for why: this must NOT touch shopping_list_items.
	function addOmittedIngredient(ing: OmittedIngredient) {
		if (!omissions) return;
		extraItems = [
			...extraItems,
			{
				item_id: ing.item_id,
				amount: ing.amount ?? 1,
				unit: ing.unit ?? 'count',
				name: ing.item_name
			}
		];
		omissions = {
			...omissions,
			recipe_ingredients: omissions.recipe_ingredients.filter(
				(i) => !(i.recipe_id === ing.recipe_id && i.item_id === ing.item_id)
			)
		};
		refreshOmissionTotal();
	}

	// No natural amount for a bare perishable (it's not tied to a
	// specific recipe's quantity) — same default a plain item-drop on
	// the list detail page starts at.
	function addOmittedPerishable(p: OmittedPerishable) {
		if (!omissions) return;
		extraItems = [...extraItems, { item_id: p.item_id, amount: 1, unit: 'count', name: p.item_name }];
		omissions = {
			...omissions,
			perishables: omissions.perishables.filter((i) => i.item_id !== p.item_id)
		};
		refreshOmissionTotal();
	}
</script>

<button class="cart-button" {disabled} onclick={send}>
	{#if phase === 'checking'}
		Checking…
	{:else if phase === 'sending'}
		Adding to cart…
	{:else}
		{label}
	{/if}
</button>

{#if error}
	<p class="cart-error">{error}</p>
{/if}

{#if needsLogin}
	<div
		class="modal-overlay"
		onclick={() => (needsLogin = false)}
		onkeydown={(e) => e.key === 'Escape' && (needsLogin = false)}
		role="presentation"
	>
		<div
			class="modal-box"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
			role="dialog"
			aria-modal="true"
			tabindex="-1"
		>
			<h3>Sign in to Woolworths first</h3>
			<p>
				Kai needs a signed-in Woolworths session to put things in your cart. A window will open —
				sign in there, then try again.
			</p>
			<div class="modal-actions">
				<button class="secondary" onclick={() => (needsLogin = false)}>Cancel</button>
				<button
					class="primary"
					onclick={() => {
						needsLogin = false;
						logIn();
					}}
				>
					Log in
				</button>
			</div>
		</div>
	</div>
{/if}

{#if omissions}
	<div
		class="modal-overlay"
		onclick={() => (omissions = null)}
		onkeydown={(e) => e.key === 'Escape' && (omissions = null)}
		role="presentation"
	>
		<div
			class="modal-box wide"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
			role="dialog"
			aria-modal="true"
			tabindex="-1"
		>
			<h3>Anything missing?</h3>
			<p>
				These didn't make it onto the list — nominal amounts, non-perishables, and recipe
				regulars aren't added automatically, but this is your chance to catch one that's actually
				run out.
			</p>

			<div class="omission-list">
				{#if omissions.recipe_ingredients.length}
					<p class="omission-section-label">From recipes on this list</p>
					{#each omissions.recipe_ingredients as ing (ing.recipe_id + '-' + ing.item_id)}
						<div class="omission-row">
							<div class="omission-info">
								<span class="omission-name">{ing.item_name}</span>
								<span class="omission-meta">
									{ing.amount != null && ing.unit ? `${ing.amount}${ing.unit} · ` : ''}for {ing.recipe_name}
								</span>
							</div>
							<button class="omission-add" onclick={() => addOmittedIngredient(ing)}>
								+ Add
							</button>
						</div>
					{/each}
				{/if}
				{#if omissions.perishables.length}
					<p class="omission-section-label">Regulars you might've forgotten</p>
					{#each omissions.perishables as p (p.item_id)}
						<div class="omission-row">
							<div class="omission-info">
								<span class="omission-name">{p.item_name}</span>
							</div>
							<button class="omission-add" onclick={() => addOmittedPerishable(p)}>
								+ Add
							</button>
						</div>
					{/each}
				{/if}
			</div>

			{#if omissionTotal != null}
				<div class="omission-total">
					<div class="omission-total-row">
						<span class="omission-total-label">Total</span>
						<span class="omission-total-value">${omissionTotal.toFixed(2)}</span>
					</div>
					{#if omissionTotalWithDelivery != null}
						<div class="omission-total-row sub">
							<span class="omission-total-label">+ ${deliveryFee.toFixed(2)} delivery</span>
							<span class="omission-total-value">${omissionTotalWithDelivery.toFixed(2)}</span>
						</div>
					{/if}
				</div>
			{/if}

			<div class="modal-actions">
				<button class="secondary" onclick={() => (omissions = null)}>Cancel</button>
				<button class="primary" onclick={continueToCart}>Continue to cart</button>
			</div>
		</div>
	</div>
{/if}

{#if summary}
	<div
		class="modal-overlay"
		onclick={() => (summary = null)}
		onkeydown={(e) => e.key === 'Escape' && (summary = null)}
		role="presentation"
	>
		<div
			class="modal-box wide"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
			role="dialog"
			aria-modal="true"
			tabindex="-1"
		>
			<h3>
				{succeeded.length} added{failed.length ? `, ${failed.length} couldn't be` : ''}
			</h3>

			<div class="result-list">
				{#each succeeded as r (r.sku + r.name)}
					<div class="result-row ok">
						<span class="result-name">{r.name}</span>
						<span class="result-qty">
							{r.quantity}{r.pricing_unit === 'Kg' ? 'kg' : ''}
						</span>
					</div>
				{/each}
				{#each failed as r (r.sku + r.name)}
					<div class="result-row bad">
						<span class="result-name">{r.name}</span>
						<span class="result-why">{r.error ?? 'Failed'}</span>
					</div>
				{/each}
			</div>

			<div class="modal-actions">
				<button class="secondary" onclick={() => (summary = null)}>Close</button>
				<button class="primary" onclick={() => invoke('open_woolworths_cart')}>Open cart</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.cart-button {
		background: var(--color-good, #5f9b46);
		border: none;
		border-radius: 6px;
		color: #fff;
		font-weight: bold;
		font-size: 0.85rem;
		padding: 0.5rem 0.9rem;
		cursor: pointer;
	}

	.cart-button:disabled {
		opacity: 0.5;
		cursor: default;
	}

	.cart-error {
		margin: 0.4rem 0 0;
		color: #ff8a80;
		font-size: 0.8rem;
	}

	.modal-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
	}

	.modal-box {
		background: #232322;
		border-radius: 12px;
		padding: 1.5rem;
		width: 360px;
		max-width: calc(100% - 2rem);
		box-sizing: border-box;
		color: #fff;
	}

	.modal-box.wide {
		width: 520px;
	}

	.modal-box h3 {
		margin: 0 0 0.75rem;
		font-size: 1rem;
	}

	.modal-box p {
		margin: 0 0 1.25rem;
		font-size: 0.85rem;
		color: #ccc;
		line-height: 1.5;
	}

	.result-list {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		max-height: 320px;
		overflow-y: auto;
		margin-bottom: 1.25rem;
	}

	.result-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		background: #1e1e1d;
		border-radius: 6px;
		padding: 0.45rem 0.7rem;
		font-size: 0.8rem;
	}

	.result-row.ok {
		border-left: 3px solid var(--color-good, #5f9b46);
	}

	.result-row.bad {
		border-left: 3px solid var(--color-warning, #c99a3d);
	}

	.result-name {
		flex: 1 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-weight: bold;
		text-transform: capitalize;
	}

	.result-qty {
		flex: 0 0 auto;
		color: #95977e;
		font-weight: bold;
	}

	.result-why {
		flex: 0 0 auto;
		color: var(--color-warning, #c99a3d);
		font-size: 0.72rem;
		max-width: 60%;
		text-align: right;
	}

	.omission-list {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		max-height: 360px;
		overflow-y: auto;
		margin-bottom: 1.25rem;
	}

	.omission-section-label {
		margin: 0.6rem 0 0.15rem;
		font-size: 0.7rem;
		font-weight: bold;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: #999;
	}

	.omission-section-label:first-child {
		margin-top: 0;
	}

	.omission-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		background: #1e1e1d;
		border-radius: 6px;
		padding: 0.45rem 0.7rem;
	}

	.omission-info {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.omission-name {
		font-weight: bold;
		font-size: 0.85rem;
		text-transform: capitalize;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.omission-meta {
		font-size: 0.7rem;
		color: #999;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.omission-add {
		flex: 0 0 auto;
		background: none;
		border: 1px solid var(--color-good, #5f9b46);
		border-radius: 6px;
		color: var(--color-good, #5f9b46);
		font-weight: bold;
		font-size: 0.75rem;
		padding: 0.3rem 0.6rem;
		cursor: pointer;
	}

	.omission-total {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		background: #1e1e1d;
		border: 1px solid #3a4a55;
		border-radius: 8px;
		padding: 0.6rem 0.9rem;
		margin-bottom: 1.25rem;
	}

	.omission-total-row {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1.5rem;
	}

	.omission-total-row.sub {
		padding-top: 0.4rem;
		border-top: 1px dashed #333;
	}

	.omission-total-label {
		font-size: 0.7rem;
		font-weight: bold;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: #999;
		white-space: nowrap;
	}

	.omission-total-row.sub .omission-total-label {
		text-transform: none;
		letter-spacing: normal;
	}

	.omission-total-value {
		font-size: 1.2rem;
		font-weight: bold;
		color: #95977e;
		white-space: nowrap;
	}

	.omission-total-row.sub .omission-total-value {
		font-size: 0.85rem;
	}

	.modal-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.6rem;
	}

	.primary,
	.secondary {
		border-radius: 6px;
		font-weight: bold;
		font-size: 0.85rem;
		padding: 0.45rem 1rem;
		cursor: pointer;
	}

	.primary {
		background: #3a4a55;
		border: none;
		color: #fff;
	}

	.secondary {
		background: none;
		border: 1px solid #555;
		color: #fff;
	}
</style>
