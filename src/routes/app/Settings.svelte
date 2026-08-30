<!--
	Settings — a separate full-window area reached from the header's
	gear button, with a back button to return. Deliberately a container
	that grows: Woolworths account is the only section for now.
-->
<script lang="ts">
	import { invoke } from '@tauri-apps/api/core';
	import { getVersion } from '@tauri-apps/api/app';
	import { check, type Update } from '@tauri-apps/plugin-updater';
	import { relaunch } from '@tauri-apps/plugin-process';
	import { onMount } from 'svelte';
	import ConfirmDialog from './ConfirmDialog.svelte';

	let { onClose }: { onClose: () => void } = $props();

	type Status = 'checking' | 'logged-in' | 'logged-out' | 'error';

	let status: Status = $state('checking');
	let error: string | null = $state(null);

	// A real request to Woolworths (see woolworths_cart::check_logged_in),
	// not a guess from cookie names — so what this shows is exactly what
	// the cart-add will find when it runs.
	async function checkStatus() {
		status = 'checking';
		error = null;
		try {
			status = (await invoke<boolean>('woolworths_login_status')) ? 'logged-in' : 'logged-out';
		} catch (e) {
			error = String(e);
			status = 'error';
		}
	}

	onMount(checkStatus);

	async function logIn() {
		try {
			await invoke('open_woolworths_login');
		} catch (e) {
			error = String(e);
		}
	}

	// The flat fee Woolworths adds at checkout — not fetched from
	// anywhere, just a user-entered constant (see db::settings on the
	// Rust side) so the Shopping Lists tab can show a combined total's
	// cost with delivery included. Same implicit-save-on-blur pattern as
	// everywhere else in the app.
	let deliveryFee: number = $state(14);
	let deliveryFeeError: string | null = $state(null);

	async function loadDeliveryFee() {
		try {
			deliveryFee = await invoke<number>('get_delivery_fee');
		} catch (e) {
			deliveryFeeError = String(e);
		}
	}

	onMount(loadDeliveryFee);

	async function saveDeliveryFee() {
		deliveryFeeError = null;
		if (!Number.isFinite(deliveryFee) || deliveryFee < 0) {
			deliveryFeeError = 'Delivery fee must be a positive number';
			await loadDeliveryFee();
			return;
		}
		try {
			deliveryFee = await invoke<number>('set_delivery_fee', { fee: deliveryFee });
		} catch (e) {
			deliveryFeeError = String(e);
		}
	}

	// Auto-updater — checked silently on open (no interruption if there's
	// nothing new), with a manual "Check again" for peace of mind. The
	// point of building this at all: Oscar's partner isn't expected to
	// know what a GitHub release is, so "there's an update" has to show
	// up *inside the app* rather than needing anyone to go looking for a
	// new installer themselves.
	type UpdateStatus = 'checking' | 'up-to-date' | 'available' | 'downloading' | 'restarting' | 'error';

	let currentVersion: string = $state('');
	let updateStatus: UpdateStatus = $state('checking');
	let pendingUpdate: Update | null = null;
	let updateVersion: string | null = $state(null);
	let updateNotes: string | null = $state(null);
	let updateError: string | null = $state(null);

	async function checkForUpdate() {
		updateStatus = 'checking';
		updateError = null;
		try {
			const update = await check();
			if (update) {
				pendingUpdate = update;
				updateVersion = update.version;
				updateNotes = update.body ?? null;
				updateStatus = 'available';
			} else {
				pendingUpdate = null;
				updateStatus = 'up-to-date';
			}
		} catch (e) {
			updateError = String(e);
			updateStatus = 'error';
		}
	}

	async function installUpdate() {
		if (!pendingUpdate) return;
		updateStatus = 'downloading';
		updateError = null;
		try {
			await pendingUpdate.downloadAndInstall();
			updateStatus = 'restarting';
			await relaunch();
		} catch (e) {
			updateError = String(e);
			updateStatus = 'error';
		}
	}

	onMount(async () => {
		try {
			currentVersion = await getVersion();
		} catch {
			// Non-critical — the update-check flow itself still works
			// without a version number to display.
		}
		checkForUpdate();
	});

	// Local/remote switch — see CLAUDE.md's Phase B notes. `backend_mode`/
	// `remote_url`/`remote_token` live in the *local* settings table
	// regardless of which one is active (get_backend_config/
	// set_backend_mode/set_remote_config on the Rust side), which is what
	// lets switching back to local show exactly what was there before.
	type BackendConfig = {
		mode: 'local' | 'remote';
		remote_url: string | null;
		remote_token: string | null;
	};

	let backendMode: 'local' | 'remote' = $state('local');
	let remoteUrl: string = $state('');
	let remoteToken: string = $state('');
	let remoteConfigError: string | null = $state(null);

	// Gates the confirm dialog — an unexplained empty pantry right after
	// switching could otherwise read as data loss to a non-technical user
	// (Oscar's partner), so the switch itself always asks first.
	let pendingModeSwitch: 'local' | 'remote' | null = $state(null);

	async function loadBackendConfig() {
		try {
			const config = await invoke<BackendConfig>('get_backend_config');
			backendMode = config.mode;
			remoteUrl = config.remote_url ?? '';
			remoteToken = config.remote_token ?? '';
		} catch (e) {
			remoteConfigError = String(e);
		}
	}

	onMount(loadBackendConfig);

	function requestModeSwitch(mode: 'local' | 'remote') {
		if (mode === backendMode) return;
		pendingModeSwitch = mode;
	}

	async function confirmModeSwitch() {
		const mode = pendingModeSwitch;
		pendingModeSwitch = null;
		if (!mode) return;
		remoteConfigError = null;
		try {
			const config = await invoke<BackendConfig>('set_backend_mode', { mode });
			backendMode = config.mode;
		} catch (e) {
			remoteConfigError = String(e);
		}
	}

	// Same implicit-save-on-blur pattern as Delivery Fee — no separate
	// "Save" button. Saving also immediately rebuilds the active backend
	// if remote mode is already on, so a token typo shows up on the next
	// real request rather than silently lingering unsaved.
	async function saveRemoteConfig() {
		remoteConfigError = null;
		try {
			const config = await invoke<BackendConfig>('set_remote_config', {
				url: remoteUrl,
				token: remoteToken
			});
			remoteUrl = config.remote_url ?? '';
			remoteToken = config.remote_token ?? '';
		} catch (e) {
			remoteConfigError = String(e);
		}
	}

	type TestStatus = 'idle' | 'testing' | 'ok' | 'error';
	let testStatus: TestStatus = $state('idle');
	let testError: string | null = $state(null);

	// Tests whatever's currently typed, not necessarily what's saved yet —
	// same reasoning as save-on-blur: a user should be able to check a URL
	// works before committing it.
	async function testConnection() {
		testStatus = 'testing';
		testError = null;
		try {
			await invoke('test_remote_connection', { url: remoteUrl, token: remoteToken });
			testStatus = 'ok';
		} catch (e) {
			testError = String(e);
			testStatus = 'error';
		}
	}
</script>

<div class="settings">
	<div class="topbar">
		<button class="back" onclick={onClose}>← Back</button>
	</div>

	<h1>Settings</h1>

	<section class="setting-block">
		<h2>Woolworths account</h2>
		<p class="blurb">
			Signing in lets Kai add a shopping list straight to your real Woolworths cart. Your password
			goes into Woolworths' own page — Kai never sees or stores it.
		</p>

		<div class="status-row">
			<span class="status-pill" class:on={status === 'logged-in'} class:off={status === 'logged-out'}
				class:unknown={status === 'checking' || status === 'error'}
			>
				{#if status === 'checking'}
					Checking…
				{:else if status === 'logged-in'}
					Signed in
				{:else if status === 'logged-out'}
					Not signed in
				{:else}
					Couldn't check
				{/if}
			</span>

			{#if status !== 'logged-in'}
				<button class="primary" onclick={logIn}>Log in to Woolworths</button>
			{/if}
			<button class="secondary" onclick={checkStatus} disabled={status === 'checking'}>
				Check again
			</button>
		</div>

		{#if status === 'logged-in'}
			<p class="hint">
				A Woolworths session doesn't last forever — if a cart add starts failing, come back here and
				sign in again.
			</p>
		{:else if status === 'logged-out'}
			<p class="hint">
				After signing in, the window stays open — close it and hit <em>Check again</em>.
			</p>
		{/if}

		{#if error}
			<p class="error">{error}</p>
		{/if}
	</section>

	<section class="setting-block">
		<h2>Delivery fee</h2>
		<p class="blurb">
			The flat fee Woolworths adds at checkout — shown alongside a shopping list total so it
			reflects what you'd actually pay.
		</p>

		<div class="status-row">
			<span class="fee-input-wrap">
				<span class="fee-dollar">$</span>
				<input
					class="fee-input"
					type="number"
					min="0"
					step="0.01"
					bind:value={deliveryFee}
					onblur={saveDeliveryFee}
				/>
			</span>
		</div>

		{#if deliveryFeeError}
			<p class="error">{deliveryFeeError}</p>
		{/if}
	</section>

	<section class="setting-block">
		<h2>Updates</h2>
		<p class="blurb">
			Kai can update itself — no need to download anything by hand.
			{#if currentVersion}Currently running version {currentVersion}.{/if}
		</p>

		<div class="status-row">
			<span
				class="status-pill"
				class:on={updateStatus === 'up-to-date'}
				class:off={updateStatus === 'error'}
				class:unknown={updateStatus === 'checking' ||
					updateStatus === 'available' ||
					updateStatus === 'downloading' ||
					updateStatus === 'restarting'}
			>
				{#if updateStatus === 'checking'}
					Checking…
				{:else if updateStatus === 'up-to-date'}
					Up to date
				{:else if updateStatus === 'available'}
					Update available
				{:else if updateStatus === 'downloading'}
					Downloading…
				{:else if updateStatus === 'restarting'}
					Restarting…
				{:else}
					Couldn't check
				{/if}
			</span>

			{#if updateStatus === 'available'}
				<button class="primary" onclick={installUpdate}>
					Install v{updateVersion} &amp; restart
				</button>
			{/if}
			<button
				class="secondary"
				onclick={checkForUpdate}
				disabled={updateStatus === 'checking' ||
					updateStatus === 'downloading' ||
					updateStatus === 'restarting'}
			>
				Check again
			</button>
		</div>

		{#if updateStatus === 'available' && updateNotes}
			<p class="hint">{updateNotes}</p>
		{/if}

		{#if updateError}
			<p class="error">{updateError}</p>
		{/if}
	</section>

	<section class="setting-block">
		<h2>Remote server</h2>
		<p class="blurb">
			Local keeps everything on this device. Remote points Kai at a shared server instead — the two
			are separate datasets, switching doesn't move anything between them.
		</p>

		<div class="status-row">
			<div class="mode-toggle">
				<button
					class:active={backendMode === 'local'}
					onclick={() => requestModeSwitch('local')}
				>
					Local
				</button>
				<button
					class:active={backendMode === 'remote'}
					onclick={() => requestModeSwitch('remote')}
				>
					Remote
				</button>
			</div>
		</div>

		<div class="remote-fields">
			<label class="field">
				<span>Server URL</span>
				<input
					type="text"
					placeholder="https://kai.yourdomain.com"
					bind:value={remoteUrl}
					disabled={backendMode !== 'remote'}
					onblur={saveRemoteConfig}
				/>
			</label>
			<label class="field">
				<span>Shared token</span>
				<input
					type="password"
					placeholder="the server's KAI_SHARED_TOKEN"
					bind:value={remoteToken}
					disabled={backendMode !== 'remote'}
					onblur={saveRemoteConfig}
				/>
			</label>
		</div>

		<div class="status-row">
			<span
				class="status-pill"
				class:on={testStatus === 'ok'}
				class:off={testStatus === 'error'}
				class:unknown={testStatus === 'idle' || testStatus === 'testing'}
			>
				{#if testStatus === 'idle'}
					Not tested
				{:else if testStatus === 'testing'}
					Testing…
				{:else if testStatus === 'ok'}
					Connected
				{:else}
					Couldn't connect
				{/if}
			</span>
			<button
				class="secondary"
				onclick={testConnection}
				disabled={testStatus === 'testing' || !remoteUrl}
			>
				Test connection
			</button>
		</div>

		{#if testStatus === 'error' && testError}
			<p class="error">{testError}</p>
		{/if}

		{#if remoteConfigError}
			<p class="error">{remoteConfigError}</p>
		{/if}
	</section>
</div>

{#if pendingModeSwitch}
	<ConfirmDialog
		message={pendingModeSwitch === 'remote'
			? "Switch to the remote server? Kai will show what's stored there instead of what's on this device."
			: "Switch back to local? Kai will show what's on this device instead of the remote server."}
		confirmLabel="Switch"
		onConfirm={confirmModeSwitch}
		onCancel={() => (pendingModeSwitch = null)}
	/>
{/if}

<style>
	.settings {
		position: absolute;
		inset: 0;
		background: #1e1e1d;
		color: #fff;
		overflow-y: auto;
		padding: 1.5rem;
		box-sizing: border-box;
		z-index: 20;
	}

	.topbar {
		display: flex;
		align-items: center;
		margin-bottom: 1.5rem;
	}

	.back {
		background: none;
		border: none;
		color: #ccc;
		font-weight: bold;
		font-size: 1rem;
		cursor: pointer;
		padding: 0;
	}

	h1 {
		margin: 0 0 1.5rem;
		font-size: 1.75rem;
	}

	.setting-block {
		max-width: 640px;
		background: #232322;
		border-radius: 10px;
		padding: 1.25rem;
	}

	.setting-block + .setting-block {
		margin-top: 1rem;
	}

	.fee-input-wrap {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		background: #1e1e1d;
		border: 1px solid #444;
		border-radius: 6px;
		padding: 0.4rem 0.7rem;
	}

	.fee-dollar {
		color: #999;
		font-weight: bold;
	}

	.fee-input {
		width: 5rem;
		background: none;
		border: none;
		color: #fff;
		font-weight: bold;
		font-size: 0.95rem;
		padding: 0;
	}

	.fee-input:focus {
		outline: none;
	}

	.fee-input::-webkit-inner-spin-button,
	.fee-input::-webkit-outer-spin-button {
		-webkit-appearance: none;
		margin: 0;
	}

	h2 {
		margin: 0 0 0.5rem;
		font-size: 1rem;
	}

	.blurb {
		margin: 0 0 1rem;
		color: #999;
		font-size: 0.85rem;
		line-height: 1.5;
	}

	.status-row {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.6rem;
	}

	.status-pill {
		padding: 0.25rem 0.8rem;
		border-radius: 999px;
		font-size: 0.75rem;
		font-weight: bold;
		color: #fff;
	}

	.status-pill.on {
		background: var(--color-good, #5f9b46);
	}

	.status-pill.off {
		background: var(--color-error, #b3261e);
	}

	.status-pill.unknown {
		background: #333;
		color: #999;
	}

	.mode-toggle {
		display: flex;
		background: #1e1e1d;
		border: 1px solid #444;
		border-radius: 6px;
		padding: 0.2rem;
		gap: 0.2rem;
	}

	.mode-toggle button {
		background: none;
		border: none;
		color: #999;
		font-weight: bold;
		font-size: 0.85rem;
		padding: 0.4rem 1rem;
		border-radius: 4px;
		cursor: pointer;
	}

	.mode-toggle button.active {
		background: #3a4a55;
		color: #fff;
	}

	.remote-fields {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		margin-top: 1rem;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		font-size: 0.8rem;
		color: #999;
	}

	.field input {
		background: #1e1e1d;
		border: 1px solid #444;
		border-radius: 6px;
		color: #fff;
		font-size: 0.9rem;
		padding: 0.5rem 0.7rem;
	}

	.field input:focus {
		outline: none;
		border-color: #3a4a55;
	}

	.field input:disabled {
		opacity: 0.5;
	}

	.primary,
	.secondary {
		border-radius: 6px;
		font-weight: bold;
		font-size: 0.85rem;
		padding: 0.45rem 0.9rem;
		cursor: pointer;
	}

	.primary {
		background: #3a4a55;
		border: none;
		color: #fff;
	}

	.secondary {
		background: none;
		border: 1px solid #555;
		color: #fff;
	}

	.secondary:disabled {
		opacity: 0.5;
		cursor: default;
	}

	.hint {
		margin: 0.9rem 0 0;
		color: #999;
		font-size: 0.78rem;
		line-height: 1.5;
	}

	.error {
		margin: 0.9rem 0 0;
		color: #ff8a80;
		font-size: 0.8rem;
	}
</style>
