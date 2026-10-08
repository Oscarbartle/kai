<!--
	Line chart of an item's price history: one coloured line per SKU on a
	shared axis, a dot for every time that SKU was fetched (hollow when the
	price was a special). Hover a dot for the details; click a legend chip
	to hide or show that SKU. Drawn by hand as SVG — no chart library — so
	it matches the app's dark theme and adds nothing to the bundle. The
	maths (series, ticks, date labels) lives in priceHistory.ts, where it's
	unit-tested.
-->
<script lang="ts">
	import SizeBadge from './SizeBadge.svelte';
	import {
		formatAxisMoney,
		formatFull,
		formatMoney,
		formatTick,
		nearestDot,
		niceTicks,
		timeDomain,
		timeTicks,
		totalDots,
		type Dot,
		type Series
	} from './priceHistory';

	let { series }: { series: Series[] } = $props();

	// Drawn at the container's real pixel width (1 unit = 1px), so text and
	// dots stay a normal size however wide the window is.
	let boxWidth = $state(720);
	const W = $derived(Math.max(320, boxWidth));
	const H = 250;
	const M = { l: 52, r: 18, t: 14, b: 30 };

	let hiddenIds: number[] = $state([]);
	let focusId: number | null = $state(null);
	let tip: { x: number; y: number; series: Series; dot: Dot } | null = $state(null);

	const visible = $derived(series.filter((s) => !hiddenIds.includes(s.skuId)));
	const domain = $derived(timeDomain(visible.length ? visible : series));
	const prices = $derived(visible.flatMap((s) => s.dots.map((d) => d.price)));
	const yAxis = $derived(prices.length ? niceTicks(Math.min(...prices), Math.max(...prices)) : niceTicks(0, 1));

	const x = (t: number) => M.l + ((t - domain[0]) / (domain[1] - domain[0])) * (W - M.l - M.r);
	const y = (p: number) => M.t + (1 - (p - yAxis.lo) / (yAxis.hi - yAxis.lo)) * (H - M.t - M.b);

	const plotted = $derived(
		visible.map((s) => ({
			series: s,
			pts: s.dots.map((d) => ({ dot: d, x: x(d.t), y: y(d.price) }))
		}))
	);
	const allPts = $derived(plotted.flatMap((p) => p.pts.map((pt) => ({ ...pt, series: p.series }))));
	const xTicks = $derived(timeTicks(visible));
	// Labels describe the dots' own span, not the padded drawing range.
	const dataSpan = $derived(xTicks.length > 1 ? xTicks[xTicks.length - 1] - xTicks[0] : 0);
	const dotCount = $derived(totalDots(series));

	function path(pts: { x: number; y: number }[]): string {
		return pts.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
	}

	function toggle(id: number) {
		hiddenIds = hiddenIds.includes(id) ? hiddenIds.filter((h) => h !== id) : [...hiddenIds, id];
		tip = null;
	}

	function onMove(e: MouseEvent) {
		const svg = e.currentTarget as SVGSVGElement;
		const r = svg.getBoundingClientRect();
		const px = e.clientX - r.left;
		const py = e.clientY - r.top;
		const hit = nearestDot(allPts, px, py, 18);
		tip = hit ? { x: hit.x, y: hit.y, series: hit.series, dot: hit.dot } : null;
	}

	/** Latest price and how it compares with the first one recorded. */
	function summary(s: Series): { latest: number; delta: number } | null {
		if (!s.dots.length) return null;
		const latest = s.dots[s.dots.length - 1].price;
		return { latest, delta: latest - s.dots[0].price };
	}

	function deltaText(delta: number): string {
		const c = Math.round(Math.abs(delta) * 100);
		if (c === 0) return 'no change';
		return `${delta > 0 ? '▲' : '▼'} ${c >= 100 ? formatMoney(c / 100) : `${c}c`}`;
	}

	const label = $derived(
		`Price history for ${series.length} SKU${series.length === 1 ? '' : 's'}, ${dotCount} recorded price${dotCount === 1 ? '' : 's'}`
	);
</script>

<div class="chart-card">
	{#if dotCount === 0}
		<p class="empty">No prices recorded yet. Every refresh adds a dot.</p>
	{:else}
		<div class="plot" bind:clientWidth={boxWidth}>
			<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
			<svg
				width={W}
				height={H}
				viewBox={`0 0 ${W} ${H}`}
				role="img"
				aria-label={label}
				onmousemove={onMove}
				onmouseleave={() => (tip = null)}
			>
				{#each yAxis.ticks as tick}
					<line class="grid" x1={M.l} x2={W - M.r} y1={y(tick)} y2={y(tick)} />
					<text class="axis" x={M.l - 10} y={y(tick)} text-anchor="end" dominant-baseline="middle">
						{formatAxisMoney(tick)}
					</text>
				{/each}
				{#each xTicks as t, i}
					<text
						class="axis"
						x={x(t)}
						y={H - M.b + 18}
						text-anchor={i === 0 ? 'start' : i === xTicks.length - 1 ? 'end' : 'middle'}
					>
						{formatTick(t, dataSpan)}
					</text>
				{/each}

				{#each plotted as p (p.series.skuId)}
					<g class="series" class:dim={focusId != null && focusId !== p.series.skuId}>
						{#if p.pts.length > 1}
							<path class="line" d={path(p.pts)} pathLength="1" stroke={p.series.color} />
						{/if}
						{#each p.pts as pt}
							<circle
								class="dot"
								class:special={pt.dot.special}
								cx={pt.x}
								cy={pt.y}
								r="4"
								stroke={p.series.color}
								fill={pt.dot.special ? 'var(--chart-bg)' : p.series.color}
							>
								<title>{p.series.label}{p.series.size ? ` ${p.series.size}` : ''}: {formatMoney(pt.dot.price)}, {formatFull(pt.dot.t)}</title>
							</circle>
						{/each}
					</g>
				{/each}

				{#if tip}
					<circle class="ring" cx={tip.x} cy={tip.y} r="8" stroke={tip.series.color} />
				{/if}
			</svg>

			{#if tip}
				<div
					class="tip"
					class:flip={tip.x > W * 0.62}
					style={`left:${tip.x}px; top:${tip.y}px`}
				>
					<span class="tip-name">
						<span class="tip-label" style={`color:${tip.series.color}`}>{tip.series.label}</span>
						<SizeBadge size={tip.series.size} small />
					</span>
					<span class="tip-price">
						{formatMoney(tip.dot.price)}
						{#if tip.dot.special}<span class="tip-special">special</span>{/if}
					</span>
					{#if tip.dot.was != null}<span class="tip-was">was {formatMoney(tip.dot.was)}</span>{/if}
					<span class="tip-date">{formatFull(tip.dot.t)}</span>
				</div>
			{/if}
		</div>

		{#if dotCount === 1}
			<p class="hint">Just the one dot so far. Every refresh adds another.</p>
		{/if}

		<div class="legend">
			{#each series as s (s.skuId)}
				{@const sum = summary(s)}
				<button
					class="chip"
					class:off={hiddenIds.includes(s.skuId)}
					aria-pressed={!hiddenIds.includes(s.skuId)}
					title={hiddenIds.includes(s.skuId) ? 'Show on chart' : 'Hide from chart'}
					onclick={() => toggle(s.skuId)}
					onmouseenter={() => (focusId = hiddenIds.includes(s.skuId) ? null : s.skuId)}
					onmouseleave={() => (focusId = null)}
				>
					<span class="swatch" style={`--c:${s.color}`}></span>
					<span class="chip-name">{s.label}</span>
					<SizeBadge size={s.size} small />
					{#if sum}
						<span class="chip-price">{formatMoney(sum.latest)}</span>
						{#if s.dots.length > 1}
							<span
								class="chip-delta"
								class:up={sum.delta > 0.004}
								class:down={sum.delta < -0.004}
								title="Compared with the first price recorded"
							>
								{deltaText(sum.delta)}
							</span>
						{/if}
					{:else}
						<span class="chip-price none">no price yet</span>
					{/if}
				</button>
			{/each}
		</div>
	{/if}
</div>

<style>
	.chart-card {
		--chart-bg: #232322;
		background: var(--chart-bg);
		border: 1px solid #2f2f2d;
		border-radius: 12px;
		padding: 0.8rem 0.9rem 0.8rem;
	}

	.plot {
		position: relative;
	}

	svg {
		display: block;
		overflow: visible;
	}

	.grid {
		stroke: #3a3a38;
		stroke-width: 1;
		stroke-dasharray: 3 5;
	}

	.axis {
		fill: #9a9a96;
		font-size: 11.5px;
		font-variant-numeric: tabular-nums;
	}

	.series {
		transition: opacity 0.15s;
	}

	.series.dim {
		opacity: 0.18;
	}

	.line {
		fill: none;
		stroke-width: 2.5;
		stroke-linejoin: round;
		stroke-linecap: round;
		stroke-dasharray: 1;
		stroke-dashoffset: 0;
		animation: draw 0.8s ease-out;
	}

	@keyframes draw {
		from {
			stroke-dashoffset: 1;
		}
		to {
			stroke-dashoffset: 0;
		}
	}

	.dot {
		stroke-width: 2;
		animation: pop 0.4s ease-out backwards;
		animation-delay: 0.5s;
		transform-box: fill-box;
		transform-origin: center;
	}

	@keyframes pop {
		from {
			opacity: 0;
			transform: scale(0.2);
		}
	}

	.ring {
		fill: none;
		stroke-width: 1.5;
		opacity: 0.55;
		pointer-events: none;
	}

	@media (prefers-reduced-motion: reduce) {
		.line,
		.dot {
			animation: none;
		}
	}

	.tip {
		position: absolute;
		transform: translate(14px, -50%);
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
		padding: 0.5rem 0.7rem;
		background: #111110;
		border: 1px solid #44443f;
		border-radius: 8px;
		box-shadow: 0 6px 18px rgba(0, 0, 0, 0.45);
		font-size: 0.8rem;
		white-space: nowrap;
		max-width: min(30rem, 80%);
		pointer-events: none;
		z-index: 2;
	}

	.tip.flip {
		transform: translate(calc(-100% - 14px), -50%);
	}

	.tip-name {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		min-width: 0;
		font-weight: 600;
	}

	/* A very long name is cut with an ellipsis rather than pushing the
	   badge out of the box. */
	.tip-label {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.tip-price {
		font-size: 1.05rem;
		font-weight: 700;
		color: #fff;
	}

	.tip-special {
		margin-left: 0.4rem;
		padding: 0.05rem 0.4rem;
		font-size: 0.65rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: #111;
		background: var(--color-warning, #c99a3d);
		border-radius: 999px;
		vertical-align: middle;
	}

	.tip-was {
		color: #b0b0aa;
		text-decoration: line-through;
	}

	.tip-date {
		color: #8d8d88;
		font-size: 0.72rem;
	}

	.hint,
	.empty {
		margin: 0.5rem 0 0;
		color: #9a9a96;
		font-size: 0.85rem;
		text-align: center;
	}

	.empty {
		padding: 1.5rem 0;
	}

	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-top: 0.9rem;
	}

	.chip {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		max-width: 100%;
		padding: 0.35rem 0.7rem;
		font: inherit;
		font-size: 0.82rem;
		color: #e8e8e4;
		background: #2b2b29;
		border: 1px solid #3a3a37;
		border-radius: 999px;
		cursor: pointer;
		transition:
			background 0.15s,
			opacity 0.15s;
	}

	.chip:hover {
		background: #343431;
	}

	.chip.off {
		opacity: 0.45;
	}

	.chip.off .chip-name {
		text-decoration: line-through;
	}

	/* A little line with a dot on it — the same mark the chart uses. */
	.swatch {
		position: relative;
		flex: none;
		width: 1.4rem;
		height: 3px;
		border-radius: 2px;
		background: var(--c);
	}

	.swatch::after {
		content: '';
		position: absolute;
		left: 50%;
		top: 50%;
		width: 9px;
		height: 9px;
		border-radius: 50%;
		background: var(--c);
		transform: translate(-50%, -50%);
	}

	.chip-name {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.chip-price {
		font-weight: 700;
		color: #fff;
	}

	.chip-price.none {
		font-weight: 400;
		color: #8d8d88;
	}

	.chip-delta {
		font-size: 0.74rem;
		color: #9a9a96;
	}

	/* Dearer is bad, cheaper is good. */
	.chip-delta.up {
		color: #ff8a80;
	}

	.chip-delta.down {
		color: #7fc784;
	}
</style>
