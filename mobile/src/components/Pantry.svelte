<!--
  Read-only pantry: search, tag filter, and an alphabetical list (the
  server already sorts it). Card contents match the desktop Pantry's —
  image, name, cheapest price with the was-price on a special.
-->
<script lang="ts">
  import type { PantryEntry, Tag } from '../lib/types';
  import { cheapestSku, itemImage, money } from '../lib/format';
  import Picture from './Picture.svelte';

  let { entries }: { entries: PantryEntry[] } = $props();

  let search = $state('');
  let activeTags = $state<Set<number>>(new Set());

  // Only tags some item actually uses — not every tag that has ever
  // existed (the tag table is shared with recipes).
  const allTags = $derived.by(() => {
    const byId = new Map<number, Tag>();
    for (const e of entries) for (const t of e.tags) byId.set(t.id, t);
    return [...byId.values()].sort((a, b) =>
      a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
    );
  });

  // Several tags narrow the list down (an item must have all of them),
  // same as the desktop sidebar.
  const visible = $derived(
    entries.filter(
      (e) =>
        (activeTags.size === 0 || [...activeTags].every((id) => e.tags.some((t) => t.id === id))) &&
        e.item.name.toLowerCase().includes(search.trim().toLowerCase())
    )
  );

  function toggleTag(id: number) {
    const next = new Set(activeTags);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    activeTags = next;
  }
</script>

<div class="filters">
  <input
    type="search"
    placeholder="Search pantry…"
    aria-label="Search pantry"
    autocomplete="off"
    bind:value={search}
  />
  {#if allTags.length}
    <div class="chips" role="group" aria-label="Filter by tag">
      {#each allTags as tag (tag.id)}
        <button
          class="chip"
          class:active={activeTags.has(tag.id)}
          aria-pressed={activeTags.has(tag.id)}
          onclick={() => toggleTag(tag.id)}
        >
          {tag.name}
        </button>
      {/each}
    </div>
  {/if}
</div>

{#if entries.length === 0}
  <p class="empty">Your pantry is empty. Add items from the desktop app.</p>
{:else if visible.length === 0}
  <p class="empty">Nothing matches.</p>
{:else}
  <ul class="list">
    {#each visible as entry (entry.item.id)}
      {@const best = cheapestSku(entry.skus)}
      <li class="row">
        <div class="thumb"><Picture src={itemImage(entry)} label={entry.item.name} /></div>
        <div class="main">
          <span class="name">{entry.item.name}</span>
          {#if entry.tags.length}
            <span class="tags">{entry.tags.map((t) => t.name).join(' · ')}</span>
          {/if}
        </div>
        <div class="price">
          {#if best === null || best.price.sale_price == null}
            <span class="na">N/A</span>
          {:else}
            {#if best.price.is_special && best.price.original_price != null}
              <span class="was">{money(best.price.original_price)}</span>
            {/if}
            <span class="now" class:special={best.price.is_special}>
              {money(best.price.sale_price)}
            </span>
          {/if}
        </div>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .filters {
    position: sticky;
    top: calc(var(--bar-h) + env(safe-area-inset-top));
    z-index: 4;
    padding: 0.75rem 1rem 0.5rem;
    background: var(--bg);
  }

  input[type='search'] {
    width: 100%;
    padding: 0.7rem 0.9rem;
    border-radius: 10px;
    border: 1px solid var(--line);
    background: var(--card);
    font-size: 1rem;
  }

  input[type='search']:focus {
    outline: none;
    border-color: var(--accent);
  }

  /* One scrolling row rather than wrapping onto several lines — a pantry
     can have a dozen tags and wrapped chips would eat the screen. */
  .chips {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.6rem;
    overflow-x: auto;
    padding-bottom: 0.25rem;
    scrollbar-width: none;
  }

  .chips::-webkit-scrollbar {
    display: none;
  }

  .chip {
    flex: 0 0 auto;
    padding: 0.4rem 0.85rem;
    border-radius: 999px;
    border: 1px solid var(--line);
    background: var(--card);
    color: var(--muted);
    font-size: 0.85rem;
    font-weight: 600;
  }

  .chip.active {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--text);
  }

  .list {
    list-style: none;
    margin: 0;
    padding: 0.25rem 1rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .row {
    display: flex;
    align-items: center;
    gap: 0.85rem;
    padding: 0.65rem 0.85rem;
    background: var(--card);
    border-radius: 12px;
  }

  .thumb {
    flex: 0 0 auto;
    width: 3rem;
    height: 3rem;
    border-radius: 50%;
    overflow: hidden;
  }

  .main {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  .name {
    font-weight: 700;
    overflow-wrap: anywhere;
  }

  .tags {
    color: var(--muted);
    font-size: 0.78rem;
  }

  .price {
    flex: 0 0 auto;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    font-variant-numeric: tabular-nums;
  }

  .now {
    color: var(--price);
    font-weight: 700;
    font-size: 1.05rem;
  }

  .now.special {
    color: var(--good);
  }

  .was {
    color: var(--error);
    font-size: 0.75rem;
    text-decoration: line-through;
  }

  .na {
    color: var(--muted);
    font-size: 0.85rem;
  }

  .empty {
    margin: 2rem 1rem;
    text-align: center;
    color: var(--muted);
  }
</style>
