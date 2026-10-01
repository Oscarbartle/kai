<!--
  The recipe list: a card per recipe. Tapping one goes to its recipe card
  (a hash route, so the phone's own Back button comes back here).
-->
<script lang="ts">
  import type { RecipeBookEntry } from '../lib/types';
  import Picture from './Picture.svelte';

  let { entries }: { entries: RecipeBookEntry[] } = $props();

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
          <div class="photo"><Picture src={entry.recipe.image_url} label={entry.recipe.name} /></div>
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

  .list {
    list-style: none;
    margin: 0;
    padding: 0.25rem 1rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }

  /* Compact rather than a big photo per recipe: a recipe with no picture
     would otherwise be a screen-high empty tile, and a book of a few dozen
     recipes wants to be scannable. The photo gets its moment on the recipe
     card itself. */
  .card {
    display: flex;
    align-items: center;
    gap: 0.9rem;
    padding: 0.7rem;
    border-radius: 14px;
    background: var(--card);
    text-decoration: none;
  }

  .photo {
    flex: 0 0 auto;
    width: 5.25rem;
    height: 5.25rem;
    border-radius: 11px;
    overflow: hidden;
  }

  .body {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .name {
    font-weight: 700;
    font-size: 1.05rem;
    overflow-wrap: anywhere;
  }

  .meta {
    color: var(--muted);
    font-size: 0.82rem;
  }

  .tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-top: 0.15rem;
  }

  .tag {
    padding: 0.12rem 0.55rem;
    border-radius: 999px;
    background: var(--accent);
    font-size: 0.7rem;
    font-weight: 700;
  }

  .empty {
    margin: 2rem 1rem;
    text-align: center;
    color: var(--muted);
  }
</style>
