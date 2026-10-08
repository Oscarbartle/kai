<!--
	The pack size of a SKU ("500g") as a pill, shown beside its name
	everywhere a SKU appears — the size is what tells similar products
	apart. Renders nothing when there is no size.
-->
<script lang="ts">
	import { sizeLabel } from './skuSize';

	let { size, small = false }: { size: { volume_size?: string | null } | string | null | undefined; small?: boolean } = $props();

	const text = $derived(typeof size === 'string' ? sizeLabel({ volume_size: size }) : sizeLabel(size));
</script>

{#if text}
	<span class="size-badge" class:small title="Pack size">{text}</span>
{/if}

<style>
	.size-badge {
		display: inline-block;
		flex: none;
		padding: 0.12rem 0.55rem;
		font-size: 0.85rem;
		font-weight: 700;
		line-height: 1.35;
		color: #fff;
		background: #3a4a55;
		border: 1px solid #52677a;
		border-radius: 999px;
		white-space: nowrap;
		vertical-align: baseline;
	}

	.size-badge.small {
		padding: 0.05rem 0.45rem;
		font-size: 0.72rem;
	}
</style>
