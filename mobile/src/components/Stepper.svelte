<!--
  A − / value / + control. Dumb on purpose: it shows what it is given and
  reports taps; the caller decides what a tap means.
-->
<script lang="ts">
  let {
    label,
    onminus,
    onplus,
  }: { label: string; onminus: () => void; onplus: () => void } = $props();
</script>

<div class="stepper">
  <button type="button" onclick={onminus} aria-label="Less">−</button>
  <span class="value">{label}</span>
  <button type="button" onclick={onplus} aria-label="More">+</button>
</div>

<style>
  .stepper {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    background: var(--bg);
    border: 1px solid var(--line);
  }

  button {
    width: 2.7rem;
    height: 2.7rem;
    border: none;
    border-radius: 50%;
    background: none;
    font-size: 1.5rem;
    font-weight: 600;
    line-height: 1;
  }

  button:active {
    background: var(--accent);
  }

  .value {
    min-width: 3.6rem;
    padding: 0 0.2rem;
    text-align: center;
    font-weight: 700;
    font-size: 1.05rem;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
</style>
