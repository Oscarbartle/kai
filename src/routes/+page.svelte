<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";

  interface Sku {
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
    };
    size: {
      cup_price: number | null;
      cup_measure: string | null;
      package_type: string | null;
      volume_size: string | null;
    };
    availability_status: string | null;
    stock_level: number | null;
    images: string[];
    allergens: string[];
    ingredients: string[];
  }

  interface SkuSlot {
    id: string;
    status: "input" | "loading" | "loaded" | "error";
    inputValue: string;
    data: Sku | null;
    error: string | null;
  }

  interface ItemShell {
    id: string;
    name: string;
    skus: SkuSlot[];
  }

  let items = $state<ItemShell[]>([]);

  function createItem() {
    items.push({
      id: crypto.randomUUID(),
      name: "",
      skus: [],
    });
  }

  function addSku(item: ItemShell) {
    item.skus.push({
      id: crypto.randomUUID(),
      status: "input",
      inputValue: "",
      data: null,
      error: null,
    });
  }

  async function submitSku(slot: SkuSlot) {
    if (!slot.inputValue.trim()) return;
    slot.status = "loading";
    slot.error = null;
    try {
      slot.data = await invoke<Sku>("fetch_woolworths_sku", {
        input: slot.inputValue,
      });
      slot.status = "loaded";
    } catch (e) {
      slot.error = String(e);
      slot.status = "error";
    }
  }
</script>

<header>
  <h1>Create Item</h1>
  <button onclick={createItem}>+</button>
</header>

<main>
  {#each items as item (item.id)}
    <div class="item-shell">
      <input
        class="name"
        type="text"
        placeholder="Item name"
        bind:value={item.name}
      />
      <p class="id">{item.id}</p>

      <div class="skus">
        {#each item.skus as sku (sku.id)}
          <div class="sku-shell">
            {#if sku.status === "input" || sku.status === "error"}
              <div class="sku-input-row">
                <input
                  type="text"
                  placeholder="Paste product URL or stock code"
                  bind:value={sku.inputValue}
                  onkeydown={(e) => e.key === "Enter" && submitSku(sku)}
                />
                <button onclick={() => submitSku(sku)}>Add</button>
              </div>
              {#if sku.status === "error"}
                <p class="sku-error">{sku.error}</p>
              {/if}
            {:else if sku.status === "loading"}
              <p class="sku-loading">Loading…</p>
            {:else if sku.status === "loaded" && sku.data}
              <div class="sku-loaded">
                {#if sku.data.images[0]}
                  <img src={sku.data.images[0]} alt={sku.data.name} />
                {/if}
                <div class="sku-info">
                  <p class="sku-name">{sku.data.name}</p>
                  <p class="sku-meta">
                    {sku.data.brand ?? ""}
                    {sku.data.variety ?? ""}
                    · sku {sku.data.sku}
                  </p>
                  <p class="sku-price">
                    ${sku.data.price.sale_price ?? "?"}
                    {#if sku.data.price.is_special}
                      <span class="special">
                        was ${sku.data.price.original_price}
                      </span>
                    {/if}
                    {#if sku.data.size.cup_price && sku.data.size.cup_measure}
                      <span class="unit-price">
                        (${sku.data.size.cup_price}/{sku.data.size.cup_measure})
                      </span>
                    {/if}
                  </p>
                  <p class="sku-availability">
                    {sku.data.availability_status ?? "unknown availability"}
                  </p>
                  {#if sku.data.allergens.length}
                    <p class="sku-allergens">
                      ⚠ {sku.data.allergens.join(", ")}
                    </p>
                  {/if}
                </div>
              </div>
            {/if}
          </div>
        {/each}
        <button class="add-sku" onclick={() => addSku(item)}>+ SKU</button>
      </div>
    </div>
  {:else}
    <p class="empty">No items yet.</p>
  {/each}
</main>

<style>
  :global(:root) {
    font-family: Inter, Avenir, Helvetica, Arial, sans-serif;
    color: #0f0f0f;
    background-color: #f6f6f6;
  }

  :global(body) {
    margin: 0;
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.5rem;
    border-bottom: 1px solid #ddd;
  }

  h1 {
    font-size: 1.1rem;
    margin: 0;
  }

  button {
    width: 2rem;
    height: 2rem;
    border-radius: 6px;
    border: 1px solid #ccc;
    background: #fff;
    font-size: 1.2rem;
    line-height: 1;
    cursor: pointer;
  }

  button:hover {
    background: #eee;
  }

  main {
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .item-shell {
    border: 1px solid #ddd;
    border-radius: 6px;
    padding: 0.75rem 1rem;
    background: #fff;
  }

  .item-shell .name {
    display: block;
    width: 100%;
    box-sizing: border-box;
    margin: 0 0 0.25rem;
    font-weight: 600;
    font-size: 1rem;
    font-family: inherit;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 0.25rem 0.35rem;
    background: transparent;
    color: inherit;
  }

  .item-shell .name:hover,
  .item-shell .name:focus {
    border-color: #ccc;
    outline: none;
  }

  .item-shell .id {
    margin: 0;
    font-size: 0.75rem;
    color: #888;
    font-family: monospace;
  }

  .skus {
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px dashed #ddd;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .sku-shell {
    border: 1px dashed #ccc;
    border-radius: 6px;
    padding: 0.5rem 0.75rem;
  }

  .sku-input-row {
    display: flex;
    gap: 0.4rem;
  }

  .sku-input-row input {
    flex: 1;
    box-sizing: border-box;
    padding: 0.4rem 0.5rem;
    border-radius: 4px;
    border: 1px solid #ccc;
    font-family: inherit;
    font-size: 0.85rem;
    background: #fff;
    color: inherit;
  }

  .sku-input-row button {
    width: auto;
    height: auto;
    padding: 0.3rem 0.7rem;
    font-size: 0.8rem;
  }

  .sku-error {
    margin: 0.4rem 0 0;
    font-size: 0.8rem;
    color: #c0392b;
  }

  .sku-loading {
    margin: 0;
    font-size: 0.85rem;
    color: #888;
  }

  .sku-loaded {
    display: flex;
    gap: 0.6rem;
    align-items: flex-start;
  }

  .sku-loaded img {
    width: 48px;
    height: 48px;
    object-fit: contain;
    background: #fff;
    border-radius: 4px;
    flex-shrink: 0;
  }

  .sku-info p {
    margin: 0 0 0.15rem;
    font-size: 0.85rem;
  }

  .sku-name {
    font-weight: 600;
  }

  .sku-meta {
    color: #888;
    text-transform: capitalize;
  }

  .sku-price .special {
    color: #c0392b;
    text-decoration: line-through;
    margin-left: 0.3rem;
    font-size: 0.8rem;
  }

  .sku-price .unit-price {
    color: #888;
    font-size: 0.8rem;
    margin-left: 0.3rem;
  }

  .sku-availability {
    color: #888;
    font-size: 0.75rem;
  }

  .sku-allergens {
    color: #b8860b;
    font-size: 0.75rem;
  }

  .add-sku {
    align-self: flex-start;
    width: auto;
    height: auto;
    padding: 0.3rem 0.6rem;
    font-size: 0.8rem;
  }

  .empty {
    color: #888;
  }

  @media (prefers-color-scheme: dark) {
    :global(:root) {
      color: #f6f6f6;
      background-color: #2f2f2f;
    }

    header {
      border-bottom-color: #444;
    }

    button {
      background: #3a3a3a;
      border-color: #555;
      color: #f6f6f6;
    }

    button:hover {
      background: #454545;
    }

    .item-shell {
      background: #3a3a3a;
      border-color: #4d4d4d;
    }

    .item-shell .name:hover,
    .item-shell .name:focus {
      border-color: #666;
    }

    .skus {
      border-top-color: #4d4d4d;
    }

    .sku-shell {
      border-color: #666;
    }

    .sku-input-row input {
      background: #2f2f2f;
      border-color: #555;
      color: #f6f6f6;
    }
  }
</style>
