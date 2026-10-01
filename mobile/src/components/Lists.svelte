<!--
  The Lists tab: one card per shopping list. Tapping opens it (a hash
  route, so Back comes back here).
-->
<script lang="ts">
  import type { ShoppingEntry } from '../lib/types';

  let { entries, onnew }: { entries: ShoppingEntry[]; onnew: () => void } = $props();

  function count(e: ShoppingEntry): string {
    const n = e.lines.length;
    return n === 0 ? 'Empty' : `${n} item${n === 1 ? '' : 's'}`;
  }
</script>

{#if entries.length === 0}
  <p class="empty">No shopping lists yet.</p>
{:else}
  <ul class="list">
    {#each entries as entry (entry.list.id)}
      <li>
        <a class="card" href={`#/lists/${entry.list.id}`}>
          <span class="name">{entry.list.name}</span>
          <span class="meta">{count(entry)}</span>
        </a>
      </li>
    {/each}
  </ul>
{/if}

<div class="new">
  <button type="button" onclick={onnew}>＋ New list</button>
</div>

<style>
  .list {
    list-style: none;
    margin: 0;
    padding: 1rem 1rem 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .card {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    padding: 1.1rem 1.2rem;
    border-radius: 1rem;
    background: var(--card);
    text-decoration: none;
  }

  .name {
    font-weight: 700;
    font-size: 1.25rem;
    overflow-wrap: anywhere;
  }

  .meta {
    color: var(--muted);
    font-size: 0.95rem;
  }

  .empty {
    margin: 2rem 1rem 1rem;
    text-align: center;
    color: var(--muted);
  }

  .new {
    padding: 0.5rem 1rem 1rem;
  }

  .new button {
    width: 100%;
    padding: 1rem;
    border: 1px dashed #555;
    border-radius: 1rem;
    background: none;
    color: var(--muted);
    font-size: 1.05rem;
    font-weight: 700;
  }
</style>
