<!--
  A bottom sheet. It pushes a history entry while it is open, so the
  phone's Back button closes the sheet instead of leaving the screen
  underneath — the first thing anyone presses on Android.

  Closing always goes through `history.back()`; the popstate that follows
  is what actually calls `onclose`, so there is exactly one path whether
  the user taps outside, taps Cancel, or presses Back.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import type { Snippet } from 'svelte';

  let {
    title,
    onclose,
    children,
  }: { title: string; onclose: () => void; children: Snippet<[() => void]> } = $props();

  function close() {
    history.back();
  }

  onMount(() => {
    history.pushState({ sheet: true }, '');
    const onPop = () => onclose();
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  });
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="scrim" onclick={close}></div>
<div class="sheet" role="dialog" aria-modal="true" aria-label={title}>
  <div class="grab"></div>
  <h2>{title}</h2>
  {@render children(close)}
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 20;
    background: rgba(0, 0, 0, 0.55);
  }

  .sheet {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 21;
    max-height: 85dvh;
    overflow-y: auto;
    padding: 0.6rem 1.2rem calc(1.4rem + env(safe-area-inset-bottom));
    border-radius: 1.4rem 1.4rem 0 0;
    background: var(--card-2);
    animation: rise 0.18s ease-out;
  }

  @keyframes rise {
    from {
      transform: translateY(2rem);
      opacity: 0;
    }
  }

  .grab {
    width: 2.6rem;
    height: 0.28rem;
    margin: 0 auto 0.9rem;
    border-radius: 999px;
    background: #555;
  }

  h2 {
    margin: 0 0 1rem;
    font-size: 1.25rem;
    overflow-wrap: anywhere;
  }
</style>
