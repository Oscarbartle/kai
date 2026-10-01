<!--
  An image that fills whatever box its parent gives it. A letter on a plain
  tile shows when there's no image, when it fails to load (a dead link, or a
  CDN refusing a hotlink — otherwise a broken-image icon in the middle of a
  tidy card) and, importantly, *while it's loading*: on mobile data a row of
  product photos arrives one by one, and without this each shows as a blank
  white disc until its turn. The photo then fades in over the tile.
-->
<script lang="ts">
  let { src, label }: { src: string | null; label: string } = $props();

  let failed = $state(false);
  let loaded = $state(false);
  let img: HTMLImageElement | null = $state(null);

  // A new src (e.g. after a refresh) starts over.
  $effect(() => {
    src;
    failed = false;
    loaded = false;
  });

  // A cached image can finish before this element's load handler is
  // attached, so the event is never seen and the photo would stay
  // invisible forever. Checking `complete` covers that case.
  $effect(() => {
    if (img && img.complete && img.naturalWidth > 0) loaded = true;
  });
</script>

<div class="pic" class:photo={loaded}>
  <span class="initial" aria-hidden="true">{label.trim().charAt(0).toUpperCase()}</span>
  {#if src && !failed}
    <img
      bind:this={img}
      {src}
      alt=""
      class:loaded
      loading="lazy"
      decoding="async"
      referrerpolicy="no-referrer"
      onload={() => (loaded = true)}
      onerror={() => (failed = true)}
    />
  {/if}
</div>

<style>
  .pic {
    position: relative;
    width: 100%;
    height: 100%;
    display: grid;
    place-items: center;
    overflow: hidden;
    background: var(--card-2);
  }

  .initial {
    color: var(--muted);
    font-weight: 700;
    font-size: 1.4em;
    transition: opacity 0.2s ease;
  }

  /* Out of the way once a real photo has arrived, so a transparent image
     can't show it through. */
  .pic.photo .initial {
    opacity: 0;
  }

  img {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    opacity: 0;
    transition: opacity 0.2s ease;
  }

  img.loaded {
    opacity: 1;
  }
</style>
