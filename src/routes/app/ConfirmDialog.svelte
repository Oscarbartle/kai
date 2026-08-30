<!--
	Universal delete-confirmation modal — one component, reused by every
	place in the new /app UI that permanently removes a row (items,
	recipes, SKUs, ingredient links, and anything added later). Deliberately
	NOT used for tag removal — tagging is a lightweight, frequent, easily
	redone action, not a "delete" in the same sense as the rest.
-->
<script lang="ts">
	let {
		message,
		confirmLabel = 'Delete',
		onConfirm,
		onCancel
	}: {
		message: string;
		confirmLabel?: string;
		onConfirm: () => void;
		onCancel: () => void;
	} = $props();
</script>

<div
	class="confirm-overlay"
	onclick={onCancel}
	onkeydown={(e) => e.key === 'Escape' && onCancel()}
	role="presentation"
>
	<div
		class="confirm-box"
		onclick={(e) => e.stopPropagation()}
		onkeydown={(e) => e.stopPropagation()}
		role="dialog"
		aria-modal="true"
		tabindex="-1"
	>
		<p>{message}</p>
		<div class="confirm-actions">
			<button class="cancel" onclick={onCancel}>Cancel</button>
			<button class="confirm-delete" onclick={onConfirm}>{confirmLabel}</button>
		</div>
	</div>
</div>

<style>
	.confirm-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
	}

	.confirm-box {
		background: #232322;
		border-radius: 12px;
		padding: 1.5rem;
		width: 320px;
		max-width: calc(100% - 2rem);
		box-sizing: border-box;
		color: #fff;
		text-align: center;
	}

	.confirm-box p {
		margin: 0 0 1.5rem;
		font-size: 0.95rem;
	}

	.confirm-actions {
		display: flex;
		justify-content: center;
		gap: 0.75rem;
	}

	.cancel,
	.confirm-delete {
		border-radius: 6px;
		font-weight: bold;
		font-size: 0.85rem;
		padding: 0.5rem 1.1rem;
		cursor: pointer;
	}

	.cancel {
		background: none;
		border: 1px solid #555;
		color: #fff;
	}

	.confirm-delete {
		background: var(--color-error);
		border: none;
		color: #fff;
	}
</style>
