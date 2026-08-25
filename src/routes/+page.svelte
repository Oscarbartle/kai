<script lang="ts">
  interface SkuShell {
    id: string;
  }

  interface ItemShell {
    id: string;
    name: string;
    skus: SkuShell[];
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
    item.skus.push({ id: crypto.randomUUID() });
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
            <p class="id">sku: {sku.id}</p>
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
  }
</style>
