<!--
  First-run screen: the shared token is checked against the server before
  it's saved, so a typo says so here rather than showing up later as an
  empty app that "just doesn't load anything".
-->
<script lang="ts">
  import { AuthError, setToken, verifyToken } from '../lib/api';

  let { message = null, onready }: { message?: string | null; onready: () => void } = $props();

  let token = $state('');
  let busy = $state(false);
  let error: string | null = $state(null);

  async function connect(e: SubmitEvent) {
    e.preventDefault();
    const value = token.trim();
    if (!value) return;
    busy = true;
    error = null;
    try {
      await verifyToken(value);
      setToken(value);
      onready();
    } catch (err) {
      error =
        err instanceof AuthError
          ? "That token wasn't accepted. Check it and try again."
          : err instanceof Error
            ? err.message
            : String(err);
    } finally {
      busy = false;
    }
  }
</script>

<main class="gate">
  <img class="logo" src="/icons/icon-192.png" alt="" />
  <h1>Kai</h1>
  <p class="lead">Enter your shared token to connect.</p>

  {#if message}
    <p class="notice">{message}</p>
  {/if}

  <form onsubmit={connect}>
    <input
      type="password"
      autocomplete="current-password"
      autocapitalize="off"
      spellcheck="false"
      placeholder="Shared token"
      aria-label="Shared token"
      bind:value={token}
    />
    <button type="submit" disabled={busy || !token.trim()}>
      {busy ? 'Connecting…' : 'Connect'}
    </button>
  </form>

  {#if error}
    <p class="error" role="alert">{error}</p>
  {/if}
</main>

<style>
  .gate {
    min-height: 100dvh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    padding: 2rem 1.5rem calc(2rem + env(safe-area-inset-bottom));
    text-align: center;
  }

  .logo {
    width: 4.5rem;
    height: 4.5rem;
    border-radius: 1rem;
  }

  h1 {
    margin: 0;
    font-size: 1.75rem;
  }

  .lead {
    margin: 0 0 0.5rem;
    color: var(--muted);
  }

  form {
    width: 100%;
    max-width: 22rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  input {
    width: 100%;
    padding: 0.95rem 1.1rem;
    border-radius: 0.7rem;
    border: 1px solid var(--line);
    background: var(--card);
    font-size: 1rem;
  }

  input:focus {
    outline: none;
    border-color: var(--accent);
  }

  button {
    padding: 0.95rem 1.1rem;
    border: none;
    border-radius: 0.7rem;
    background: var(--accent);
    font-weight: 700;
    font-size: 1rem;
  }

  button:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .notice {
    margin: 0;
    color: var(--muted);
    font-size: 0.9rem;
  }

  .error {
    margin: 0;
    color: var(--error);
    font-size: 0.9rem;
  }
</style>
