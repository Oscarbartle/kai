<!--
	`/` itself is never actually visited by the app — the Tauri window
	loads `/app` directly (see src-tauri/tauri.conf.json's window `url`).
	This only matters if something loads the raw dev server root in a
	plain browser tab; redirect straight to the real app rather than
	leaving a dead end (the old nav-tile version of this page pointed at
	/items, /recipes, /shopping-list, all removed now that /app fully
	replaces them).
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	onMount(() => {
		goto('/app', { replaceState: true });
	});
</script>
