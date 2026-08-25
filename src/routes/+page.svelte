<script lang="ts">
  interface ItemShell {
    id: string;
    name: string;
  }

  let items = $state<ItemShell[]>([]);

  function createItem() {
    items.push({
      id: crypto.randomUUID(),
      name: "New Item",
    });
  }
</script>

<header>
  <h1>Create Item</h1>
  <button onclick={createItem}>+</button>
</header>

<main>
  {#each items as item (item.id)}
    <div class="item-shell">
      <p class="name">{item.name}</p>
      <p class="id">{item.id}</p>
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
    margin: 0 0 0.25rem;
    font-weight: 600;
  }

  .item-shell .id {
    margin: 0;
    font-size: 0.75rem;
    color: #888;
    font-family: monospace;
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
  }
</style>
