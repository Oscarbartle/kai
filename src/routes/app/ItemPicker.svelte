<!--
	A searchable item picker, used by the recipe-import review table in place of
	a plain <select> (with a few hundred Pantry items a drop-down is no good).

	Shows the current choice on a button; opens a panel with a search box.
	  - empty search: the suggestions first, then "New item…" and "Skip", then
	    every item A–Z;
	  - typing: items whose name contains every typed word (suggestions first,
	    then names starting with what you typed), then "＋ New item “…”" using the
	    typed text as the new item's name, then "Skip".
	Keyboard: ↑/↓ move, Enter chooses, Esc closes. The panel is positioned
	against the window (position: fixed) because the table around it clips its
	own overflow, and it opens upwards when there is no room below.

	`value` is 'skip', 'new' or 'item:<id>' — the same strings the review table
	already uses, so the table's logic did not have to change.
-->
<script lang="ts">
	import { tick } from 'svelte';

	interface Suggestion {
		item_id: number;
		name: string;
	}

	let {
		value,
		suggestions,
		items,
		label,
		onpick
	}: {
		value: string;
		suggestions: Suggestion[];
		items: { id: number; name: string }[];
		label: string;
		/** `newName` is set only when the user picked "New item" from a typed search. */
		onpick: (choice: string, newName?: string) => void;
	} = $props();

	type Option =
		| { kind: 'heading'; text: string }
		| { kind: 'item' | 'new' | 'skip'; text: string; choice: string; newName?: string };

	const MAX_SHOWN = 60;

	let open = $state(false);
	let query = $state('');
	let highlighted = $state(0);
	let button: HTMLButtonElement | undefined = $state();
	let popover: HTMLDivElement | undefined = $state();
	let input: HTMLInputElement | undefined = $state();
	let pos = $state({ left: 0, width: 0, top: 0, bottom: 0, up: false });

	let display = $derived.by(() => {
		if (value === 'skip') return 'Skip this line';
		if (value === 'new') return '＋ New item…';
		const id = Number(value.slice(5));
		return items.find((i) => i.id === id)?.name ?? suggestions.find((s) => s.item_id === id)?.name ?? 'Unknown item';
	});

	let options: Option[] = $derived.by(() => {
		const q = query.trim().toLowerCase();
		const suggestedOrder = new Map(suggestions.map((s, i) => [s.item_id, i]));
		const asItem = (id: number, name: string): Option => ({ kind: 'item', text: name, choice: `item:${id}` });

		if (!q) {
			const rest = items.filter((i) => !suggestedOrder.has(i.id));
			return [
				...(suggestions.length
					? [{ kind: 'heading', text: 'Suggested' } as Option, ...suggestions.map((s) => asItem(s.item_id, s.name))]
					: []),
				{ kind: 'new', text: '＋ New item…', choice: 'new' },
				{ kind: 'skip', text: 'Skip this line', choice: 'skip' },
				{ kind: 'heading', text: 'All items' },
				...rest.slice(0, MAX_SHOWN * 2).map((i) => asItem(i.id, i.name))
			];
		}

		const words = q.split(/\s+/).filter(Boolean);
		const matches = items
			.filter((i) => {
				const n = i.name.toLowerCase();
				return words.every((w) => n.includes(w));
			})
			.sort((a, b) => {
				const rank = (x: { id: number; name: string }) =>
					suggestedOrder.has(x.id) ? suggestedOrder.get(x.id)! : x.name.toLowerCase().startsWith(q) ? 100 : 1000;
				return rank(a) - rank(b) || a.name.toLowerCase().localeCompare(b.name.toLowerCase());
			});
		const typed = query.trim();
		const out: Option[] = matches.slice(0, MAX_SHOWN).map((i) => asItem(i.id, i.name));
		if (matches.length > MAX_SHOWN) {
			out.push({ kind: 'heading', text: `${matches.length - MAX_SHOWN} more — keep typing to narrow it down` });
		}
		out.push({
			kind: 'new',
			text: `＋ New item “${typed}”`,
			choice: 'new',
			newName: typed.charAt(0).toUpperCase() + typed.slice(1)
		});
		out.push({ kind: 'skip', text: 'Skip this line', choice: 'skip' });
		return out;
	});

	const selectable = (o: Option) => o.kind !== 'heading';

	async function openPicker() {
		if (!button) return;
		const r = button.getBoundingClientRect();
		const below = window.innerHeight - r.bottom;
		const up = below < 300 && r.top > below;
		pos = {
			left: r.left,
			width: Math.max(r.width, 260),
			top: r.bottom + 4,
			bottom: window.innerHeight - r.top + 4,
			up
		};
		query = '';
		highlighted = Math.max(0, options.findIndex(selectable));
		open = true;
		await tick();
		input?.focus();
	}

	function close(refocus = false) {
		open = false;
		if (refocus) button?.focus();
	}

	function pick(option: Option) {
		if (option.kind === 'heading') return;
		onpick(option.choice, option.newName);
		close(true);
	}

	function move(step: 1 | -1) {
		let i = highlighted;
		for (let n = 0; n < options.length; n++) {
			i = (i + step + options.length) % options.length;
			if (selectable(options[i])) {
				highlighted = i;
				return;
			}
		}
	}

	function onKey(e: KeyboardEvent) {
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			move(1);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			move(-1);
		} else if (e.key === 'Enter') {
			e.preventDefault();
			const o = options[highlighted];
			if (o) pick(o);
		} else if (e.key === 'Escape') {
			// Only the picker closes — not the dialog around it.
			e.preventDefault();
			e.stopPropagation();
			close(true);
		} else if (e.key === 'Tab') {
			close();
		}
	}

	// Typing changes the list, so start again from its first real option.
	$effect(() => {
		query;
		highlighted = Math.max(0, options.findIndex(selectable));
	});

	// Keep the highlighted row in view as the arrow keys move it.
	$effect(() => {
		highlighted;
		if (open) popover?.querySelector('[data-active="true"]')?.scrollIntoView({ block: 'nearest' });
	});

	// Click elsewhere, scroll, or resize closes it (the panel is fixed to the
	// window, so it would otherwise float away from its row).
	$effect(() => {
		if (!open) return;
		const onDown = (e: MouseEvent) => {
			const t = e.target as Node;
			if (!popover?.contains(t) && !button?.contains(t)) close();
		};
		const onScroll = (e: Event) => {
			if (!popover?.contains(e.target as Node)) close();
		};
		const onResize = () => close();
		window.addEventListener('mousedown', onDown, true);
		window.addEventListener('scroll', onScroll, true);
		window.addEventListener('resize', onResize);
		return () => {
			window.removeEventListener('mousedown', onDown, true);
			window.removeEventListener('scroll', onScroll, true);
			window.removeEventListener('resize', onResize);
		};
	});
</script>

<button
	type="button"
	class="trigger"
	bind:this={button}
	aria-haspopup="listbox"
	aria-expanded={open}
	aria-label={label}
	onclick={() => (open ? close() : openPicker())}
>
	<span class="text">{display}</span>
	<span class="caret" aria-hidden="true">▾</span>
</button>

{#if open}
	<div
		class="popover"
		bind:this={popover}
		style="left: {pos.left}px; width: {pos.width}px; {pos.up ? `bottom: ${pos.bottom}px` : `top: ${pos.top}px`}"
		role="presentation"
	>
		<input
			class="search"
			type="text"
			placeholder="Search items…"
			aria-label="Search items"
			autocomplete="off"
			bind:this={input}
			bind:value={query}
			onkeydown={onKey}
		/>
		<ul class="list" role="listbox" aria-label={label}>
			{#each options as option, i (i)}
				{#if option.kind === 'heading'}
					<li class="heading" role="presentation">{option.text}</li>
				{:else}
					<!-- svelte-ignore a11y_click_events_have_key_events -->
					<li
						class="option"
						class:active={i === highlighted}
						class:current={option.choice === value}
						class:action={option.kind !== 'item'}
						role="option"
						aria-selected={option.choice === value}
						data-active={i === highlighted}
						onmousemove={() => (highlighted = i)}
						onclick={() => pick(option)}
					>
						<span>{option.text}</span>
						{#if option.choice === value && option.kind === 'item'}<span class="tick">✓</span>{/if}
					</li>
				{/if}
			{/each}
			{#if query.trim() && !options.some((o) => o.kind === 'item')}
				<li class="heading" role="presentation">No items match “{query.trim()}”</li>
			{/if}
		</ul>
	</div>
{/if}

<style>
	.trigger {
		box-sizing: border-box;
		width: 100%;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		background: #1e1e1d;
		border: 1px solid #444;
		border-radius: 6px;
		color: #fff;
		font-size: 0.85rem;
		padding: 0.4rem 0.5rem;
		text-align: left;
		cursor: pointer;
	}

	.trigger:focus,
	.trigger[aria-expanded='true'] {
		outline: none;
		border-color: #3a4a55;
	}

	.text {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.caret {
		flex: 0 0 auto;
		color: #999;
		font-size: 0.7rem;
	}

	.popover {
		position: fixed;
		z-index: 200;
		box-sizing: border-box;
		background: #232322;
		border: 1px solid #3a4a55;
		border-radius: 8px;
		box-shadow: 0 0.5rem 1.5rem rgba(0, 0, 0, 0.55);
		padding: 0.5rem;
	}

	.search {
		box-sizing: border-box;
		width: 100%;
		background: #1e1e1d;
		border: 1px solid #444;
		border-radius: 6px;
		color: #fff;
		font-size: 0.85rem;
		padding: 0.45rem 0.6rem;
	}

	.search:focus {
		outline: none;
		border-color: #3a4a55;
	}

	.list {
		list-style: none;
		margin: 0.4rem 0 0;
		padding: 0;
		max-height: 18rem;
		overflow-y: auto;
	}

	.heading {
		padding: 0.5rem 0.5rem 0.25rem;
		color: #888;
		font-size: 0.7rem;
		font-weight: bold;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}

	.option {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		padding: 0.4rem 0.5rem;
		border-radius: 5px;
		font-size: 0.85rem;
		cursor: pointer;
	}

	.option.active {
		background: #3a4a55;
	}

	.option.action {
		color: #cdd8df;
	}

	.option.current {
		font-weight: bold;
	}

	.tick {
		color: #9bd18a;
	}
</style>
