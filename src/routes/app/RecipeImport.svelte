<!--
	"Import a recipe from a website" — slice 1: paste a link, see the recipe
	the page carries. Nothing is saved yet; matching the ingredients to the
	Pantry and creating items/SKUs are the next slices. The supported-sites
	list comes from the importer itself (list_supported_recipe_sites), so
	what is shown here is exactly what it accepts.
-->
<script lang="ts">
	import { invoke } from '@tauri-apps/api/core';
	import { onMount } from 'svelte';

	interface SupportedSite {
		name: string;
		domains: string[];
		example_url: string;
	}

	interface RecipeDraft {
		site: string;
		source_url: string;
		name: string;
		image_url: string | null;
		servings: number | null;
		yield_text: string | null;
		ingredient_lines: string[];
		steps: string[];
	}

	let { onClose }: { onClose: () => void } = $props();

	let sites: SupportedSite[] = $state([]);
	let url = $state('');
	let status: 'idle' | 'loading' | 'done' | 'error' = $state('idle');
	let draft: RecipeDraft | null = $state(null);
	let error: string | null = $state(null);
	let imageBroken = $state(false);

	// A slow fetch must not overwrite the result of a newer one.
	let latestRequest = 0;

	onMount(async () => {
		try {
			sites = await invoke<SupportedSite[]>('list_supported_recipe_sites');
		} catch (e) {
			error = String(e);
		}
	});

	async function fetchPreview() {
		if (!url.trim() || status === 'loading') return;
		const request = ++latestRequest;
		status = 'loading';
		error = null;
		draft = null;
		imageBroken = false;
		try {
			const result = await invoke<RecipeDraft>('preview_recipe_from_url', { url });
			if (request !== latestRequest) return;
			draft = result;
			status = 'done';
		} catch (e) {
			if (request !== latestRequest) return;
			error = String(e);
			status = 'error';
		}
	}
</script>

<div
	class="overlay"
	onclick={onClose}
	onkeydown={(e) => e.key === 'Escape' && onClose()}
	role="presentation"
>
	<div
		class="box"
		onclick={(e) => e.stopPropagation()}
		onkeydown={(e) => e.stopPropagation()}
		role="dialog"
		aria-modal="true"
		aria-label="Import a recipe from a website"
		tabindex="-1"
	>
		<div class="head">
			<h3>Import a recipe from a website</h3>
			<button class="close" onclick={onClose} aria-label="Close">✕</button>
		</div>

		<form
			class="url-row"
			onsubmit={(e) => {
				e.preventDefault();
				fetchPreview();
			}}
		>
			<input
				class="url-input"
				type="text"
				placeholder="Paste a recipe link, e.g. https://www.bbcgoodfood.com/recipes/easy-pancakes"
				aria-label="Recipe link"
				bind:value={url}
			/>
			<button class="go" type="submit" disabled={!url.trim() || status === 'loading'}>
				{status === 'loading' ? 'Fetching…' : 'Fetch recipe'}
			</button>
		</form>

		<div class="sites">
			<span class="sites-label">Supported sites</span>
			{#each sites as site (site.name)}
				<button
					class="site"
					title="Fill in an example link from {site.domains[0]}"
					onclick={() => (url = site.example_url)}
				>
					{site.name}
					<span class="domain">{site.domains[0]}</span>
				</button>
			{/each}
			<span class="sites-note">More can be added once they've been checked.</span>
		</div>

		{#if error}
			<p class="error" role="alert">{error}</p>
		{/if}

		{#if draft}
			<div class="preview">
				<div class="top">
					{#if draft.image_url && !imageBroken}
						<img
							class="photo"
							src={draft.image_url}
							alt=""
							onerror={() => (imageBroken = true)}
						/>
					{/if}
					<div class="titles">
						<h4>{draft.name}</h4>
						<p class="meta">
							{#if draft.servings != null}Serves {draft.servings} ·{/if}
							{#if draft.yield_text}“{draft.yield_text}” ·{/if}
							{draft.ingredient_lines.length} ingredients ·
							{draft.steps.length} step{draft.steps.length === 1 ? '' : 's'} · from {draft.site}
						</p>
					</div>
				</div>

				<div class="cols">
					<section>
						<h5>Ingredients</h5>
						<ul>
							{#each draft.ingredient_lines as line}
								<li>{line}</li>
							{/each}
						</ul>
					</section>
					<section>
						<h5>Method</h5>
						{#if draft.steps.length === 0}
							<p class="none">This page doesn't include a method.</p>
						{:else}
							<ol>
								{#each draft.steps as step}
									<li>{step}</li>
								{/each}
							</ol>
						{/if}
					</section>
				</div>

				<p class="note">Preview only — nothing has been saved yet.</p>
			</div>
		{/if}
	</div>
</div>

<style>
	.overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
	}

	.box {
		background: #232322;
		border-radius: 12px;
		padding: 1.25rem 1.5rem 1.5rem;
		width: 860px;
		max-width: calc(100% - 2rem);
		max-height: calc(100% - 3rem);
		overflow-y: auto;
		box-sizing: border-box;
		color: #fff;
	}

	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 1rem;
	}

	h3 {
		margin: 0;
		font-size: 1.1rem;
	}

	.close {
		background: none;
		border: none;
		color: #999;
		font-size: 1rem;
		cursor: pointer;
	}

	.url-row {
		display: flex;
		gap: 0.6rem;
	}

	.url-input {
		flex: 1 1 auto;
		min-width: 0;
		background: #1e1e1d;
		border: 1px solid #444;
		border-radius: 6px;
		color: #fff;
		font-size: 0.9rem;
		padding: 0.6rem 0.75rem;
	}

	.url-input:focus {
		outline: none;
		border-color: #3a4a55;
	}

	.go {
		flex: 0 0 auto;
		background: #3a4a55;
		border: none;
		border-radius: 6px;
		color: #fff;
		font-weight: bold;
		font-size: 0.85rem;
		padding: 0.6rem 1.1rem;
		cursor: pointer;
	}

	.go:disabled {
		opacity: 0.5;
		cursor: default;
	}

	.sites {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.9rem;
	}

	.sites-label {
		color: #999;
		font-size: 0.75rem;
		font-weight: bold;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		margin-right: 0.2rem;
	}

	.site {
		background: #1e1e1d;
		border: 1px solid #444;
		border-radius: 999px;
		color: #fff;
		font-size: 0.8rem;
		font-weight: bold;
		padding: 0.3rem 0.8rem;
		cursor: pointer;
	}

	.site:hover {
		border-color: #3a4a55;
	}

	.domain {
		color: #999;
		font-weight: normal;
		margin-left: 0.3rem;
	}

	.sites-note {
		color: #777;
		font-size: 0.75rem;
	}

	.error {
		margin: 1rem 0 0;
		color: #ff8a80;
		font-size: 0.85rem;
	}

	.preview {
		margin-top: 1.25rem;
		padding-top: 1.1rem;
		border-top: 1px solid #333;
	}

	.top {
		display: flex;
		gap: 1rem;
		align-items: flex-start;
	}

	.photo {
		flex: 0 0 auto;
		width: 11rem;
		aspect-ratio: 4 / 3;
		object-fit: cover;
		border-radius: 8px;
		background: #1e1e1d;
	}

	.titles {
		min-width: 0;
	}

	h4 {
		margin: 0 0 0.4rem;
		font-size: 1.25rem;
		overflow-wrap: anywhere;
	}

	.meta {
		margin: 0;
		color: #999;
		font-size: 0.8rem;
		line-height: 1.5;
	}

	.cols {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr);
		gap: 1.5rem;
		margin-top: 1.25rem;
	}

	@media (max-width: 760px) {
		.cols {
			grid-template-columns: minmax(0, 1fr);
		}
	}

	h5 {
		margin: 0 0 0.5rem;
		color: #999;
		font-size: 0.75rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}

	ul,
	ol {
		margin: 0;
		padding-left: 1.2rem;
		font-size: 0.88rem;
		line-height: 1.55;
	}

	li {
		margin-bottom: 0.35rem;
		overflow-wrap: anywhere;
	}

	.none {
		margin: 0;
		color: #999;
		font-size: 0.85rem;
	}

	.note {
		margin: 1.25rem 0 0;
		color: #999;
		font-size: 0.8rem;
		font-style: italic;
	}
</style>
