<!--
  The recipe list: a card per recipe. Tapping one goes to its recipe card
  (a hash route, so the phone's own Back button comes back here).
-->
<script lang="ts">
  import type { RecipeBookEntry } from '../lib/types';
  import Picture from './Picture.svelte';

  let { entries, onadd }: { entries: RecipeBookEntry[]; onadd: (entry: RecipeBookEntry) => void } = $props();

  let search = $state('');

  const visible = $derived(
    entries.filter((e) => e.recipe.name.toLowerCase().includes(search.trim().toLowerCase()))
  );

  function meta(e: RecipeBookEntry): string {
    const parts: string[] = [];
    if (e.recipe.servings != null) parts.push(`Serves ${e.recipe.servings}`);
    const n = e.ingredients.length;
    parts.push(`${n} ingredient${n === 1 ? '' : 's'}`);
    return parts.join(' · ');
  }
</script>

<div class="filters">
  <input
    type="search"
    placeholder="Search recipes…"
    aria-label="Search recipes"
    autocomplete="off"
    bind:value={search}
  />
</div>

{#if entries.length === 0}
  <p class="empty">No recipes yet. Add them from the desktop app.</p>
{:else if visible.length === 0}
  <p class="empty">Nothing matches.</p>
{:else}
  <ul class="list">
    {#each visible as entry (entry.recipe.id)}
      <li>
        <a class="card" href={`#/recipes/${entry.recipe.id}`}>
          <div class="photo" class:no-image={!entry.recipe.image_url}>
            <Picture src={entry.recipe.image_url} label={entry.recipe.name} />
          </div>
          <div class="body">
            <span class="name">{entry.recipe.name}</span>
            <span class="meta">{meta(entry)}</span>
            {#if entry.tags.length}
              <span class="tags">
                {#each entry.tags as tag (tag.id)}
                  <span class="tag">{tag.name}</span>
                {/each}
              </span>
            {/if}
          </div>
        </a>
        <button class="add" aria-label={`Add ${entry.recipe.name} to a shopping list`} onclick={() => onadd(entry)}>
          <svg viewBox="0 0 24 24" class="icon" aria-hidden="true">
      <path d="M12 5v14M5 12h14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" />
    </svg>
        </button>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .filters {
    position: sticky;
    top: calc(var(--bar-h) + env(safe-area-inset-top));
    z-index: 4;
    padding: 0.9rem 1rem 0.6rem;
    background: var(--bg);
  }

  input[type='search'] {
    width: 100%;
    padding: 0.9rem 1rem;
    border-radius: 0.8rem;
    border: 1px solid var(--line);
    background: var(--card);
    font-size: 1.05rem;
  }

  input[type='search']:focus {
    outline: none;
    border-color: var(--accent);
  }

  .list {
    list-style: none;
    margin: 0;
    padding: 0.35rem 1rem 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  li {
    position: relative;
  }

  /* Outside the link (a button inside an <a> is invalid and taps would
     also open the recipe), floated over the photo's corner. */
  .add {
    position: absolute;
    top: 0.7rem;
    right: 0.7rem;
    width: 3rem;
    height: 3rem;
    display: grid;
    place-items: center;
    border: none;
    border-radius: 50%;
    background: rgba(23, 23, 22, 0.78);
    color: #fff;
    backdrop-filter: blur(6px);
  }

  .add:active {
    background: var(--good);
  }

  .card {
    display: block;
    overflow: hidden;
    border-radius: 1.1rem;
    background: var(--card);
    text-decoration: none;
  }

  /* A real photo card — most recipes have one. A recipe with no picture
     gets a short band instead of the full 16:9 block, which would be a
     screen-high empty tile for no information. */
  .photo {
    aspect-ratio: 16 / 9;
  }

  .photo.no-image {
    aspect-ratio: 16 / 5;
  }

  .body {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    padding: 1rem 1.1rem 1.15rem;
  }

  .name {
    font-weight: 700;
    font-size: 1.3rem;
    line-height: 1.25;
    overflow-wrap: anywhere;
  }

  .meta {
    color: var(--muted);
    font-size: 0.95rem;
  }

  .tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-top: 0.2rem;
  }

  .tag {
    padding: 0.2rem 0.7rem;
    border-radius: 999px;
    background: var(--accent);
    font-size: 0.8rem;
    font-weight: 700;
  }

  .empty {
    margin: 2rem 1rem;
    text-align: center;
    color: var(--muted);
    font-size: 1rem;
  }
</style>
