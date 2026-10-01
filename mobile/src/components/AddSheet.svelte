<!--
  The "+" flow: pick which list, set how much, confirm. The list drop-down
  starts on the list used last time (so the common case is one tap), but
  nothing is added until Add is pressed — never silently into a list.
-->
<script lang="ts">
  import { addItem, addRecipe, createList, getLastListId, shopping, showToast } from '../lib/shopping.svelte';
  import { AuthError } from '../lib/api';
  import { formatAmount } from '../lib/format';
  import type { AddTarget } from '../lib/types';
  import { UNITS, defaultListId, stepAmount } from '../lib/shoppingLogic';
  import Sheet from './Sheet.svelte';
  import Stepper from './Stepper.svelte';

  let {
    target,
    onclose,
    onauthfailed,
  }: { target: AddTarget; onclose: () => void; onauthfailed: () => void } = $props();

  const NEW = 'new';

  const lists = $derived(shopping.entries ?? []);

  // What the drop-down is set to: a list id as a string, or NEW. `target`
  // never changes for the life of one sheet, so reading it once is fine.
  let choice = $state<string>(
    String(
      defaultListId(
        (shopping.entries ?? []).map((e) => e.list.id),
        getLastListId()
      ) ?? NEW
    )
  );
  let newName = $state('');

  let unit = $state<string>('count');
  let amount = $state<number>(1);
  // svelte-ignore state_referenced_locally
  let servings = $state<number>(target.kind === 'recipe' ? (target.servings ?? 1) : 1);

  let busy = $state(false);
  let error: string | null = $state(null);

  const creating = $derived(choice === NEW);
  const canAdd = $derived(!busy && (!creating || newName.trim().length > 0));

  function pickUnit(u: string) {
    unit = u;
    amount = u === 'count' ? 1 : 100;
  }

  function step(dir: 1 | -1) {
    amount = stepAmount(amount, unit, dir).amount;
  }

  async function confirm(close: () => void) {
    busy = true;
    error = null;
    try {
      let listId: number;
      let listName: string;
      if (creating) {
        const list = await createList(newName.trim());
        listId = list.id;
        listName = list.name;
      } else {
        listId = Number(choice);
        listName = lists.find((e) => e.list.id === listId)?.list.name ?? 'list';
      }
      if (target.kind === 'item') await addItem(listId, target.itemId, amount, unit);
      else await addRecipe(listId, target.recipeId, servings);
      showToast(`Added ${target.name} to ${listName}`);
      close();
    } catch (e) {
      if (e instanceof AuthError) onauthfailed();
      else error = e instanceof Error ? e.message : String(e);
    } finally {
      busy = false;
    }
  }
</script>

<Sheet title={`Add ${target.name}`} {onclose}>
  {#snippet children(close)}
    <label class="field">
      <span class="label">Add to</span>
      <select bind:value={choice} aria-label="Shopping list">
        {#each lists as entry (entry.list.id)}
          <option value={String(entry.list.id)}>{entry.list.name}</option>
        {/each}
        <option value={NEW}>＋ New list…</option>
      </select>
    </label>

    {#if creating}
      <input
        class="text"
        type="text"
        placeholder="Name the new list"
        aria-label="New list name"
        autocomplete="off"
        bind:value={newName}
      />
    {/if}

    {#if target.kind === 'item'}
      <div class="field">
        <span class="label">Amount</span>
        <div class="units" role="group" aria-label="Unit">
          {#each UNITS as u (u)}
            <button type="button" class="unit" class:on={unit === u} onclick={() => pickUnit(u)}>
              {u === 'count' ? 'Each' : u}
            </button>
          {/each}
        </div>
        <Stepper
          label={unit === 'count' ? formatAmount(amount) : `${formatAmount(amount)} ${unit}`}
          onminus={() => step(-1)}
          onplus={() => step(1)}
        />
      </div>
    {:else}
      <div class="field">
        <span class="label">Servings</span>
        <Stepper
          label={String(servings)}
          onminus={() => (servings = Math.max(1, servings - 1))}
          onplus={() => (servings = servings + 1)}
        />
        <p class="hint">
          Adds the ingredients scaled to this many servings. Spices and other non-perishables are left
          off, as on the desktop.
        </p>
      </div>
    {/if}

    {#if error}
      <p class="error" role="alert">{error}</p>
    {/if}

    <div class="buttons">
      <button type="button" class="cancel" onclick={close}>Cancel</button>
      <button type="button" class="go" disabled={!canAdd} onclick={() => confirm(close)}>
        {busy ? 'Adding…' : 'Add'}
      </button>
    </div>
  {/snippet}
</Sheet>

<style>
  .field {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
    margin-bottom: 1.1rem;
  }

  .label {
    color: var(--muted);
    font-size: 0.85rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  select,
  .text {
    width: 100%;
    padding: 0.9rem 1rem;
    border-radius: 0.8rem;
    border: 1px solid var(--line);
    background: var(--bg);
    font-size: 1.05rem;
  }

  select {
    color: var(--text);
  }

  .text {
    margin: -0.4rem 0 1.1rem;
  }

  .text:focus,
  select:focus {
    outline: none;
    border-color: var(--accent);
  }

  .units {
    display: flex;
    gap: 0.5rem;
  }

  .unit {
    padding: 0.5rem 1.1rem;
    border-radius: 999px;
    border: 1px solid var(--line);
    background: var(--bg);
    color: var(--muted);
    font-weight: 600;
  }

  .unit.on {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--text);
  }

  .hint {
    margin: 0;
    color: var(--muted);
    font-size: 0.85rem;
    line-height: 1.4;
  }

  .error {
    margin: 0 0 1rem;
    color: var(--error);
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

  .go {
    background: var(--good);
  }

  .go:disabled {
    opacity: 0.5;
    cursor: default;
  }
</style>
