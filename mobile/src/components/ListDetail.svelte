<!--
  One shopping list: its lines (recipe lines grouped under the recipe),
  each with a quantity stepper and a remove button. Removing asks first —
  a stray tap on a phone shouldn't quietly delete a line.
-->
<script lang="ts">
  import type { PantryEntry, RecipeBookEntry, ShoppingEntry, ShoppingLine } from '../lib/types';
  import { formatAmount, itemImage } from '../lib/format';
  import { groupLines, stepAmount } from '../lib/shoppingLogic';
  import { removeLines, setLineAmount } from '../lib/shopping.svelte';
  import Picture from './Picture.svelte';
  import Sheet from './Sheet.svelte';
  import Stepper from './Stepper.svelte';

  let {
    entry,
    book,
    pantry,
    onback,
  }: {
    entry: ShoppingEntry;
    book: RecipeBookEntry[];
    pantry: PantryEntry[];
    onback: () => void;
  } = $props();

  const groups = $derived(groupLines(entry.lines, book));
  const images = $derived(new Map(pantry.map((p) => [p.item.id, itemImage(p)])));

  // What the remove confirmation is asking about.
  let pending = $state<{ lineIds: number[]; what: string } | null>(null);

  function label(line: ShoppingLine): string {
    if (line.amount == null) return '–';
    const n = formatAmount(line.amount);
    return !line.unit || line.unit === 'count' ? n : `${n} ${line.unit}`;
  }

  function step(line: ShoppingLine, dir: 1 | -1) {
    const next = stepAmount(line.amount, line.unit, dir);
    setLineAmount(line.id, next.amount, next.unit);
  }

  async function confirmRemove(close: () => void) {
    if (!pending) return;
    const { lineIds } = pending;
    close();
    await removeLines(entry.list.id, lineIds);
  }
</script>

<header class="bar">
  <button class="back" onclick={onback} aria-label="Back to lists">
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
  <h1>{entry.list.name}</h1>
</header>

<main>
  {#if entry.lines.length === 0}
    <p class="empty">
      Nothing on this list yet. Tap <strong>＋</strong> on a pantry item or a recipe to add it here.
    </p>
  {/if}

  {#each groups as group (group.recipeId ?? 'loose')}
    <section>
      {#if group.recipeId != null}
        <div class="group-head">
          <a class="group-name" href={`#/recipes/${group.recipeId}`}>{group.name}</a>
          <button
            class="link-btn"
            onclick={() =>
              (pending = {
                lineIds: group.lines.map((l) => l.id),
                what: `${group.name} (${group.lines.length} item${group.lines.length === 1 ? '' : 's'})`,
              })}
          >
            Remove all
          </button>
        </div>
      {/if}

      <ul>
        {#each group.lines as line (line.id)}
          <li>
            <div class="thumb"><Picture src={images.get(line.item_id) ?? null} label={line.item_name} /></div>
            <div class="main">
              <span class="name">{line.item_name}</span>
              <Stepper label={label(line)} onminus={() => step(line, -1)} onplus={() => step(line, 1)} />
            </div>
            <button
              class="remove"
              aria-label={`Remove ${line.item_name}`}
              onclick={() => (pending = { lineIds: [line.id], what: line.item_name })}
            >
              <svg viewBox="0 0 24 24" class="icon" aria-hidden="true">
                <path
                  d="M6 6l12 12M18 6L6 18"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2.2"
                  stroke-linecap="round"
                />
              </svg>
            </button>
          </li>
        {/each}
      </ul>
    </section>
  {/each}
</main>

{#if pending}
  <Sheet title={`Remove ${pending.what}?`} onclose={() => (pending = null)}>
    {#snippet children(close)}
      <div class="buttons">
        <button type="button" class="cancel" onclick={close}>Keep</button>
        <button type="button" class="danger" onclick={() => confirmRemove(close)}>Remove</button>
      </div>
    {/snippet}
  </Sheet>
{/if}

<style>
  .bar {
    position: sticky;
    top: 0;
    z-index: 5;
    height: calc(var(--bar-h) + env(safe-area-inset-top));
    padding: env(safe-area-inset-top) 1rem 0 0.5rem;
    display: flex;
    align-items: center;
    gap: 0.25rem;
    background: var(--bar);
    border-bottom: 1px solid var(--line);
  }

  .back {
    flex: 0 0 auto;
    width: 3.1rem;
    height: 3.1rem;
    display: grid;
    place-items: center;
    border: none;
    border-radius: 50%;
    background: none;
    color: #ccc;
  }

  h1 {
    margin: 0;
    font-size: 1.4rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  main {
    padding: 0.5rem 1rem calc(2rem + env(safe-area-inset-bottom));
  }

  section {
    margin-top: 1rem;
  }

  .group-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 0.5rem;
    padding: 0 0.2rem;
  }

  .group-name {
    min-width: 0;
    color: var(--muted);
    font-size: 0.9rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    text-decoration: none;
    overflow-wrap: anywhere;
  }

  .link-btn {
    flex: 0 0 auto;
    padding: 0.4rem 0;
    border: none;
    background: none;
    color: var(--error);
    font-size: 0.9rem;
    font-weight: 700;
  }

  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }

  li {
    display: flex;
    align-items: center;
    gap: 0.85rem;
    padding: 0.75rem 0.5rem 0.75rem 0.9rem;
    border-radius: 1rem;
    background: var(--card);
  }

  .thumb {
    flex: 0 0 auto;
    width: 3.2rem;
    height: 3.2rem;
    border-radius: 50%;
    overflow: hidden;
  }

  .main {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .name {
    font-weight: 700;
    font-size: 1.1rem;
    overflow-wrap: anywhere;
  }

  .remove {
    flex: 0 0 auto;
    width: 2.8rem;
    height: 2.8rem;
    display: grid;
    place-items: center;
    border: none;
    border-radius: 50%;
    background: none;
    color: var(--muted);
  }

  .empty {
    margin: 2.5rem 1rem;
    text-align: center;
    color: var(--muted);
    line-height: 1.5;
  }

  .buttons {
    display: flex;
    gap: 0.75rem;
  }

  .buttons button {
    flex: 1 1 0;
    padding: 1rem;
    border: none;
    border-radius: 0.9rem;
    font-size: 1.05rem;
    font-weight: 700;
  }

  .cancel {
    background: var(--bg);
  }

  .danger {
    background: #8a3a34;
  }
</style>
