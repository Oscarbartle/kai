<!--
  The shell: token gate, then three tabs (Pantry, Recipe Book, Lists), a
  recipe card on top of the Recipe Book and a list on top of Lists. Routing is just the URL hash, so the
  phone's own Back button does the obvious thing (closes a recipe card)
  without any router library.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { AuthError, apiGet, clearToken, getToken } from './lib/api';
  import type { AddTarget, PantryEntry, RecipeBookEntry } from './lib/types';
  import {
    createList,
    loadShopping,
    setAuthFailedHandler,
    shopping,
    showToast,
  } from './lib/shopping.svelte';
  import TokenGate from './components/TokenGate.svelte';
  import Pantry from './components/Pantry.svelte';
  import Recipes from './components/Recipes.svelte';
  import RecipeCard from './components/RecipeCard.svelte';
  import Lists from './components/Lists.svelte';
  import ListDetail from './components/ListDetail.svelte';
  import AddSheet from './components/AddSheet.svelte';
  import Sheet from './components/Sheet.svelte';

  let authed = $state(!!getToken());
  let authMessage: string | null = $state(null);

  let pantry: PantryEntry[] | null = $state(null);
  let book: RecipeBookEntry[] | null = $state(null);
  let loading = $state(false);
  let loadError: string | null = $state(null);

  let hash = $state(location.hash);

  // What the "+" sheet is open for, and the little "new list" sheet.
  let adding: AddTarget | null = $state(null);
  let newListOpen = $state(false);
  let newListName = $state('');
  let newListBusy = $state(false);

  const tab = $derived(
    hash.startsWith('#/recipes') ? 'recipes' : hash.startsWith('#/lists') ? 'lists' : 'pantry'
  );
  const listId = $derived.by(() => {
    const m = hash.match(/^#\/lists\/(\d+)/);
    return m ? Number(m[1]) : null;
  });
  const openList = $derived.by(() =>
    listId == null ? null : (shopping.entries?.find((e) => e.list.id === listId) ?? null)
  );
  const title = $derived(
    tab === 'pantry' ? 'Pantry' : tab === 'recipes' ? 'Recipe Book' : 'Shopping Lists'
  );
  const recipeId = $derived.by(() => {
    const m = hash.match(/^#\/recipes\/(\d+)/);
    return m ? Number(m[1]) : null;
  });
  // `.by` (a closure), not an inline expression: TypeScript narrows `book`
  // to `null` from its initial assignment and only resets that inside a
  // function body.
  const openRecipe = $derived.by(() =>
    recipeId == null ? null : (book?.find((b) => b.recipe.id === recipeId) ?? null)
  );

  async function load() {
    loading = true;
    loadError = null;
    try {
      // One request per screen — see kai-server's routes/overview.rs.
      const [p, b] = await Promise.all([
        apiGet<PantryEntry[]>('/pantry'),
        apiGet<RecipeBookEntry[]>('/recipe-book'),
        loadShopping(),
      ]);
      pantry = p;
      book = b;
    } catch (e) {
      if (e instanceof AuthError) signOut('That token was rejected — enter it again.');
      else loadError = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  function signOut(message: string | null = null) {
    clearToken();
    authed = false;
    authMessage = message;
    pantry = null;
    book = null;
    shopping.entries = null;
    adding = null;
    location.hash = '';
  }

  function onReady() {
    authed = true;
    authMessage = null;
    load();
  }

  // Opening a recipe pushes a history entry, so Back normally just pops it.
  // Landing straight on a recipe (a bookmark) has nothing to go back to
  // inside the app, so fall back to the list rather than leaving it.
  function closeRecipe() {
    if (history.length > 1) history.back();
    else location.hash = '#/recipes';
  }

  function closeList() {
    if (history.length > 1) history.back();
    else location.hash = '#/lists';
  }

  async function makeList(close: () => void) {
    const name = newListName.trim();
    if (!name) return;
    newListBusy = true;
    try {
      const list = await createList(name);
      showToast(`Created ${list.name}`);
      close();
    } catch (e) {
      if (e instanceof AuthError) signOut('That token was rejected — enter it again.');
      else showToast(e instanceof Error ? e.message : String(e));
    } finally {
      newListBusy = false;
    }
  }

  onMount(() => {
    setAuthFailedHandler(() => signOut('That token was rejected — enter it again.'));
    const onHash = () => (hash = location.hash);
    window.addEventListener('hashchange', onHash);
    if (authed) load();
    return () => window.removeEventListener('hashchange', onHash);
  });
</script>

{#if !authed}
  <TokenGate message={authMessage} onready={onReady} />
{:else if recipeId != null}
  <!-- A recipe card: its own full screen, no tab bar. -->
  {#if openRecipe}
    <RecipeCard
      entry={openRecipe}
      onback={closeRecipe}
      onadd={() =>
        (adding = {
          kind: 'recipe',
          recipeId: openRecipe.recipe.id,
          name: openRecipe.recipe.name,
          servings: openRecipe.recipe.servings,
        })}
    />
  {:else if loading || book === null}
    <p class="status">{loadError ?? 'Loading…'}</p>
  {:else}
    <div class="status">
      <p>That recipe isn't in your book.</p>
      <button class="retry" onclick={closeRecipe}>Back to recipes</button>
    </div>
  {/if}
{:else if listId != null}
  <!-- A shopping list: its own full screen, no tab bar. -->
  {#if openList && pantry && book}
    <ListDetail entry={openList} {book} {pantry} onback={closeList} />
  {:else if loading || shopping.entries === null}
    <p class="status">{loadError ?? 'Loading…'}</p>
  {:else}
    <div class="status">
      <p>That list does not exist any more.</p>
      <button class="retry" onclick={closeList}>Back to lists</button>
    </div>
  {/if}
{:else}
  <header class="topbar">
    <h1>{title}</h1>
    <div class="actions">
      <button class="icon-btn" onclick={load} disabled={loading} aria-label="Refresh">
        <svg viewBox="0 0 24 24" class="icon" aria-hidden="true" class:spin={loading}>
          <path
            d="M20 12a8 8 0 1 1-2.5-5.8M20 4v5h-5"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </button>
      <button class="icon-btn" onclick={() => signOut()} aria-label="Sign out">
        <svg viewBox="0 0 24 24" class="icon" aria-hidden="true">
          <path
            d="M9 4H5v16h4M16 8l4 4-4 4M20 12H9"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </button>
    </div>
  </header>

  <main>
    {#if loadError && pantry === null}
      <div class="status">
        <p class="error">{loadError}</p>
        <button class="retry" onclick={load}>Try again</button>
      </div>
    {:else if pantry === null || book === null}
      <p class="status">Loading…</p>
    {:else if tab === 'pantry'}
      <Pantry
        entries={pantry}
        onadd={(e) => (adding = { kind: 'item', itemId: e.item.id, name: e.item.name })}
      />
    {:else if tab === 'recipes'}
      <Recipes
        entries={book}
        onadd={(e) =>
          (adding = {
            kind: 'recipe',
            recipeId: e.recipe.id,
            name: e.recipe.name,
            servings: e.recipe.servings,
          })}
      />
    {:else if shopping.entries}
      <Lists
        entries={shopping.entries}
        onnew={() => {
          newListName = '';
          newListOpen = true;
        }}
      />
    {/if}
  </main>

  <nav class="tabs" aria-label="Sections">
    <a href="#/pantry" class:active={tab === 'pantry'} aria-current={tab === 'pantry' ? 'page' : undefined}>
      <svg viewBox="0 0 24 24" class="icon" aria-hidden="true">
        <path
          d="M4 9h16l-1.5 11h-13zM8 9V6a4 4 0 0 1 8 0v3"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
      Pantry
    </a>
    <a href="#/recipes" class:active={tab === 'recipes'} aria-current={tab === 'recipes' ? 'page' : undefined}>
      <svg viewBox="0 0 24 24" class="icon" aria-hidden="true">
        <path
          d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zM4 19V5M9 8h6"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
      Recipes
    </a>
    <a href="#/lists" class:active={tab === 'lists'} aria-current={tab === 'lists' ? 'page' : undefined}>
      <svg viewBox="0 0 24 24" class="icon" aria-hidden="true">
        <path
          d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01"
          fill="none"
          stroke="currentColor"
          stroke-width="2.4"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
      Lists
    </a>
  </nav>
{/if}

{#if adding}
  <AddSheet
    target={adding}
    onclose={() => (adding = null)}
    onauthfailed={() => signOut('That token was rejected — enter it again.')}
  />
{/if}

{#if newListOpen}
  <Sheet title="New list" onclose={() => (newListOpen = false)}>
    {#snippet children(close)}
      <form
        class="newlist"
        onsubmit={(e) => {
          e.preventDefault();
          makeList(close);
        }}
      >
        <input
          type="text"
          placeholder="List name"
          aria-label="List name"
          autocomplete="off"
          bind:value={newListName}
        />
        <button type="submit" disabled={newListBusy || !newListName.trim()}>Create</button>
      </form>
    {/snippet}
  </Sheet>
{/if}

{#if shopping.toast}
  <div class="toast" role="status">{shopping.toast}</div>
{/if}

<style>
  .topbar {
    position: sticky;
    top: 0;
    z-index: 5;
    height: calc(var(--bar-h) + env(safe-area-inset-top));
    padding: env(safe-area-inset-top) 0.5rem 0 1rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--bar);
    border-bottom: 1px solid var(--line);
  }

  h1 {
    margin: 0;
    font-size: 1.4rem;
  }

  .actions {
    display: flex;
  }

  .icon-btn {
    width: 3.1rem;
    height: 3.1rem;
    display: grid;
    place-items: center;
    border: none;
    border-radius: 50%;
    background: none;
    color: #ccc;
  }

  .icon-btn:disabled {
    opacity: 0.6;
    cursor: default;
  }

  .spin {
    animation: spin 0.9s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  main {
    /* Room for the fixed tab bar, so the last row isn't hidden under it. */
    padding-bottom: calc(var(--nav-h) + env(safe-area-inset-bottom));
  }

  .tabs {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 5;
    display: flex;
    padding-bottom: env(safe-area-inset-bottom);
    background: var(--bar);
    border-top: 1px solid var(--line);
  }

  .tabs a {
    flex: 1 1 0;
    height: var(--nav-h);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.2rem;
    color: var(--muted);
    font-size: 0.8rem;
    font-weight: 700;
    text-decoration: none;
  }

  .tabs a.active {
    color: var(--text);
  }

  .status {
    margin: 3rem 1.5rem;
    text-align: center;
    color: var(--muted);
  }

  .error {
    color: var(--error);
  }

  .newlist {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .newlist input {
    padding: 0.9rem 1rem;
    border-radius: 0.8rem;
    border: 1px solid var(--line);
    background: var(--bg);
    font-size: 1.05rem;
  }

  .newlist button {
    padding: 1rem;
    border: none;
    border-radius: 0.9rem;
    background: var(--good);
    font-size: 1.05rem;
    font-weight: 700;
  }

  .newlist button:disabled {
    opacity: 0.5;
  }

  /* Sits above the tab bar and any sheet. */
  .toast {
    position: fixed;
    left: 1rem;
    right: 1rem;
    bottom: calc(var(--nav-h) + 1rem + env(safe-area-inset-bottom));
    z-index: 30;
    padding: 0.9rem 1.1rem;
    border-radius: 0.9rem;
    background: #3b3b3a;
    text-align: center;
    font-weight: 600;
    box-shadow: 0 0.4rem 1.2rem rgba(0, 0, 0, 0.45);
  }

  .retry {
    padding: 0.85rem 1.6rem;
    border: none;
    border-radius: 0.7rem;
    font-size: 1rem;
    background: var(--accent);
    color: var(--text);
    font-weight: 700;
  }
</style>
