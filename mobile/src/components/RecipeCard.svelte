<!--
  The recipe card: hero image, title and quick facts, ingredients with their
  amounts lined up, and the method as numbered steps. Read-only.
-->
<script lang="ts">
  import type { RecipeBookEntry } from '../lib/types';
  import { formatQuantity, methodSteps } from '../lib/format';
  import Picture from './Picture.svelte';

  let { entry, onback, onadd }: { entry: RecipeBookEntry; onback: () => void; onadd: () => void } = $props();

  const recipe = $derived(entry.recipe);
  const steps = $derived(methodSteps(recipe.method));
  // The source link comes from freeform text — only ever make it clickable
  // if it's really a web address.
  const sourceUrl = $derived(
    recipe.source_url && /^https?:\/\//i.test(recipe.source_url.trim())
      ? recipe.source_url.trim()
      : null
  );
</script>

<article class="card">
  <div class="hero" class:no-image={!recipe.image_url}>
    <Picture src={recipe.image_url} label={recipe.name} />
    <button class="back" onclick={onback} aria-label="Back to recipes">
      <svg viewBox="0 0 24 24" class="icon" aria-hidden="true">
        <path
          d="M15 5l-7 7 7 7"
          fill="none"
          stroke="currentColor"
          stroke-width="2.4"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </button>
    <button class="back add" onclick={onadd} aria-label="Add to a shopping list">
      <svg viewBox="0 0 24 24" class="icon" aria-hidden="true">
      <path d="M12 5v14M5 12h14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" />
    </svg>
    </button>
  </div>

  <div class="sheet">
    <h1>{recipe.name}</h1>

    <div class="facts">
      {#if recipe.servings != null}
        <span class="fact">Serves {recipe.servings}</span>
      {/if}
      <span class="fact">
        {entry.ingredients.length} ingredient{entry.ingredients.length === 1 ? '' : 's'}
      </span>
      {#if sourceUrl}
        <a class="fact link" href={sourceUrl} target="_blank" rel="noopener noreferrer">Source ↗</a>
      {/if}
    </div>

    {#if entry.tags.length}
      <div class="tags">
        {#each entry.tags as tag (tag.id)}
          <span class="tag">{tag.name}</span>
        {/each}
      </div>
    {/if}

    <section>
      <h2>Ingredients</h2>
      {#if entry.ingredients.length === 0}
        <p class="none">No ingredients yet.</p>
      {:else}
        <ul class="ingredients">
          {#each entry.ingredients as ing (ing.item_id)}
            <li>
              <span class="qty">{formatQuantity(ing)}</span>
              <span class="ing-name">{ing.name}</span>
            </li>
          {/each}
        </ul>
      {/if}
    </section>

    <section>
      <h2>Method</h2>
      {#if steps.length === 0}
        <p class="none">No method written yet.</p>
      {:else if steps.length === 1}
        <p class="single">{steps[0]}</p>
      {:else}
        <ol class="steps">
          {#each steps as step, i (i)}
            <li>{step}</li>
          {/each}
        </ol>
      {/if}
    </section>
  </div>
</article>

<style>
  .card {
    padding-bottom: calc(2rem + env(safe-area-inset-bottom));
  }

  .hero {
    position: relative;
    aspect-ratio: 4 / 3;
    max-height: 45vh;
    width: 100%;
  }

  .hero.no-image {
    aspect-ratio: 16 / 7;
  }

  /* Floats over the photo so the picture can run to the very top. A
     translucent circle stays readable on both light and dark images. */
  .back {
    position: absolute;
    top: calc(0.75rem + env(safe-area-inset-top));
    left: 0.75rem;
    width: 2.9rem;
    height: 2.9rem;
    display: grid;
    place-items: center;
    border: none;
    border-radius: 50%;
    background: rgba(23, 23, 22, 0.72);
    color: #fff;
    backdrop-filter: blur(6px);
  }

  .add {
    left: auto;
    right: 0.75rem;
  }

  /* The sheet overlaps the bottom of the photo with rounded top corners,
     which reads as a card laid over the picture rather than a page that
     happens to start with one. */
  .sheet {
    position: relative;
    margin-top: -1.25rem;
    padding: 1.4rem 1.1rem 0;
    border-radius: 1.25rem 1.25rem 0 0;
    background: var(--bg);
  }

  h1 {
    margin: 0 0 0.75rem;
    font-size: 1.85rem;
    line-height: 1.2;
    overflow-wrap: anywhere;
  }

  .facts {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .fact {
    padding: 0.3rem 0.8rem;
    border-radius: 999px;
    background: var(--card-2);
    color: #ccc;
    font-size: 0.92rem;
    font-weight: 600;
    text-decoration: none;
  }

  .fact.link {
    background: var(--accent);
    color: var(--text);
  }

  .tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-top: 0.75rem;
  }

  .tag {
    padding: 0.15rem 0.6rem;
    border-radius: 999px;
    border: 1px solid var(--accent);
    color: #b9c6cf;
    font-size: 0.85rem;
    font-weight: 700;
  }

  section {
    margin-top: 1.75rem;
  }

  h2 {
    margin: 0 0 0.6rem;
    font-size: 0.9rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
  }

  .none {
    margin: 0;
    color: var(--muted);
  }

  .ingredients {
    list-style: none;
    margin: 0;
    padding: 0.25rem 1rem;
    border-radius: 14px;
    background: var(--card);
  }

  /* Quantities in their own right-aligned column so the names line up in
     one tidy edge however long "3½ tbsp" or "125 mL" gets. */
  .ingredients li {
    display: grid;
    font-size: 1.05rem;
    grid-template-columns: 5.5rem 1fr;
    align-items: baseline;
    gap: 0.9rem;
    padding: 0.7rem 0;
  }

  .ingredients li + li {
    border-top: 1px solid var(--line);
  }

  .qty {
    text-align: right;
    font-weight: 700;
    color: var(--price);
    font-variant-numeric: tabular-nums;
  }

  .ing-name {
    overflow-wrap: anywhere;
  }

  .single {
    margin: 0;
    line-height: 1.65;
    white-space: pre-wrap;
  }

  .steps {
    list-style: none;
    margin: 0;
    padding: 0;
    counter-reset: step;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .steps li {
    counter-increment: step;
    position: relative;
    padding-left: 2.8rem;
    font-size: 1.05rem;
    line-height: 1.65;
    overflow-wrap: anywhere;
  }

  .steps li::before {
    content: counter(step);
    position: absolute;
    left: 0;
    top: 0.1rem;
    width: 1.9rem;
    height: 1.9rem;
    display: grid;
    place-items: center;
    border-radius: 50%;
    background: var(--accent);
    font-size: 0.85rem;
    font-weight: 700;
  }
</style>
