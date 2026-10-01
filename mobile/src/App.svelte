<!--
  The shell: token gate, then two tabs (Pantry, Recipe Book) and a recipe
  card on top of the Recipe Book. Routing is just the URL hash, so the
  phone's own Back button does the obvious thing (closes a recipe card)
  without any router library.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { AuthError, apiGet, clearToken, getToken } from './lib/api';
  import type { PantryEntry, RecipeBookEntry } from './lib/types';
  import TokenGate from './components/TokenGate.svelte';
  import Pantry from './components/Pantry.svelte';
  import Recipes from './components/Recipes.svelte';
  import RecipeCard from './components/RecipeCard.svelte';

  let authed = $state(!!getToken());
  let authMessage: string | null = $state(null);

  let pantry: PantryEntry[] | null = $state(null);
  let book: RecipeBookEntry[] | null = $state(null);
  let loading = $state(false);
  let loadError: string | null = $state(null);

  let hash = $state(location.hash);

  const tab = $derived(hash.startsWith('#/recipes') ? 'recipes' : 'pantry');
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

  onMount(() => {
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
    <RecipeCard entry={openRecipe} onback={closeRecipe} />
  {:else if loading || book === null}
    <p class="status">{loadError ?? 'Loading…'}</p>
  {:else}
    <div class="status">
      <p>That recipe isn't in your book.</p>
      <button class="retry" onclick={closeRecipe}>Back to recipes</button>
    </div>
  {/if}
{:else}
  <header class="topbar">
    <h1>{tab === 'pantry' ? 'Pantry' : 'Recipe Book'}</h1>
    <div class="actions">
      <button class="icon" onclick={load} disabled={loading} aria-label="Refresh">
        <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" class:spin={loading}>
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
      <button class="icon" onclick={() => signOut()} aria-label="Sign out">
        <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
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
      <Pantry entries={pantry} />
    {:else}
      <Recipes entries={book} />
    {/if}
  </main>

  <nav class="tabs" aria-label="Sections">
    <a href="#/pantry" class:active={tab === 'pantry'} aria-current={tab === 'pantry' ? 'page' : undefined}>
      <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
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
      <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
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
  </nav>
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
    font-size: 1.2rem;
  }

  .actions {
    display: flex;
  }

  .icon {
    width: 2.75rem;
    height: 2.75rem;
    display: grid;
    place-items: center;
    border: none;
    border-radius: 50%;
    background: none;
    color: #ccc;
  }

  .icon:disabled {
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
    gap: 0.15rem;
    color: var(--muted);
    font-size: 0.72rem;
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

  .retry {
    padding: 0.7rem 1.4rem;
    border: none;
    border-radius: 10px;
    background: var(--accent);
    color: var(--text);
    font-weight: 700;
  }
</style>
