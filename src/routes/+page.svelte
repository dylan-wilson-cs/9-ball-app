<script lang="ts">
    import Ball from "$lib/components/Ball.svelte";
    import GameSetup from "$lib/components/GameSetup.svelte";
    import Icon from "../images/9ball.png";
    import {
        loadMatch,
        newMatch,
        newRack,
        saveMatch,
        STORAGE_KEY,
        type BallState,
        type Match,
        type RackBall,
    } from "$lib/match";

    // The page only renders in the browser (ssr is off), so the saved match
    // can be read during setup and a reload resumes it
    let match = $state<Match>(loadMatch() ?? newMatch());
    $effect(() => saveMatch(match));

    let winner = $derived(match.players.find((p) => p.score >= p.raceTo));
    let deadInRack = $derived(
        match.rack.balls.filter((b) => b.state === "dead").length,
    );
    // Balls 1 to 8 still on the table, which go dead when the 9 is made
    let leftovers = $derived(
        match.rack.balls.slice(0, 8).filter((b) => b.state === "available")
            .length,
    );

    // The match as it was before the last 9 was made, so a mistaken 9 can
    // be taken back. Cleared by the next change to the match.
    let undoNine = $state<Match | null>(null);

    // In-page confirmation for making the 9. Browser confirm() dialogs are
    // blocked in sandboxed frames (e.g. the published page). A modal dialog
    // also makes the rest of the page inert, so the turn can't change while
    // the 9 waits for confirmation.
    let nineDialog = $state<HTMLDialogElement>();

    // Another tab changed the match: follow it, so this tab's next save
    // doesn't overwrite that change with stale state
    function onStorage(event: StorageEvent) {
        if (event.key !== STORAGE_KEY) return;
        const changed = loadMatch();
        if (!changed) return;
        match = changed;
        undoNine = null;
        nineDialog?.close();
    }

    function startGame() {
        for (const p of match.players) p.name = p.name.trim();
        match.isStarted = true;
        resetMatch();
    }

    function resetMatch() {
        undoNine = null;
        for (const p of match.players) p.score = 0;
        match.currentPlayer = 0;
        match.rack = newRack(0);
        match.deadCarry = 0;
        match.inningCarry = 0;
    }

    // "End match" needs a second tap within a few seconds, so a stray tap
    // can't wipe a saved match
    let confirmingEnd = $state(false);
    let confirmEndTimer: ReturnType<typeof setTimeout> | undefined;

    function endMatch() {
        clearTimeout(confirmEndTimer);
        if (!confirmingEnd) {
            confirmingEnd = true;
            confirmEndTimer = setTimeout(() => (confirmingEnd = false), 3000);
            return;
        }
        confirmingEnd = false;
        resetMatch();
        match.isStarted = false;
    }

    // A ball the opponent made or killed this rack cannot be changed on
    // your turn
    function isLocked(ball: RackBall): boolean {
        return ball.state !== "available" && ball.by !== match.currentPlayer;
    }

    const NEXT_STATE: Record<BallState, BallState> = {
        available: "sunk",
        sunk: "dead",
        dead: "available",
    };

    // Ignore a second tap on the same ball this soon after the first, so a
    // double tap on a phone doesn't skip past "made" to "dead"
    const DOUBLE_TAP_MS = 400;
    let lastTap = { ball: -1, time: 0 };

    function tapBall(i: number, ball: RackBall) {
        const now = Date.now();
        const isDoubleTap =
            lastTap.ball === i && now - lastTap.time < DOUBLE_TAP_MS;
        lastTap = { ball: i, time: now };
        if (isDoubleTap) return;

        const next = NEXT_STATE[ball.state];
        // Once the match is won, balls can only be un-made, to correct a
        // mistaken final ball
        if (winner && next === "sunk") return;

        // Making the 9 ends the rack, so the 9 is always on the table here
        if (i === 8) {
            nineDialog?.showModal();
            return;
        }

        undoNine = null;
        // Un-making a ball takes the point back from whoever made it
        if (ball.state === "sunk") match.players[ball.by].score -= 1;
        if (next === "sunk") match.players[match.currentPlayer].score += 1;
        match.rack.balls[i] =
            next === "available"
                ? { state: next }
                : { state: next, by: match.currentPlayer };
    }

    function pocketNine() {
        nineDialog?.close();
        // The snapshot is a plain copy of the match, but its type widens the
        // players tuple to an array
        undoNine = $state.snapshot(match) as Match;
        match.players[match.currentPlayer].score += 2;
        // This rack's dead balls and the balls left on the table go into the
        // shared dead total, and the player who made the 9 breaks next
        match.deadCarry += deadInRack + leftovers;
        match.inningCarry += match.rack.inning;
        match.rack = newRack(match.currentPlayer);
    }

    function undoLastNine() {
        if (!undoNine) return;
        match = undoNine;
        undoNine = null;
    }

    function endTurn() {
        undoNine = null;
        if (match.currentPlayer !== match.rack.breaker) match.rack.inning += 1;
        match.currentPlayer = match.currentPlayer === 0 ? 1 : 0;
    }
</script>

<svelte:window onstorage={onStorage} />

{#if !match.isStarted}
    <header class="table-color text-white py-2 mb-3">
        <div class="d-flex align-items-center justify-content-center">
            <img src={Icon} alt="" class="header-icon me-2" />
            <h1 class="mb-0 h2">9-Ball Scorekeeper</h1>
        </div>
    </header>
    <div class="container-fluid pb-4">
        <GameSetup bind:players={match.players} onStart={startGame} />
    </div>
{:else}
    <div class="match container-fluid d-flex flex-column">
        <div class="d-flex justify-content-end py-2">
            <button
                class="btn btn-sm"
                class:btn-outline-secondary={!confirmingEnd}
                class:btn-danger={confirmingEnd}
                onclick={endMatch}
            >
                {confirmingEnd ? "Tap again to end match" : "End match"}
            </button>
        </div>

        <div class="row g-2 mb-3">
            {#each match.players as player, i}
                {@const active = winner
                    ? winner === player
                    : match.currentPlayer === i}
                <div class="col-6">
                    <div
                        class="player-card card h-100 text-center"
                        class:active
                    >
                        <div class="card-body px-2 py-1">
                            <h2
                                class="player-name h6 fw-bold text-truncate m-0"
                                title={player.name}
                            >
                                {player.name}
                            </h2>
                            <div class="player-score">
                                <span class="fw-bold">{player.score}</span><span
                                    class="race-target">/{player.raceTo}</span
                                >
                            </div>
                            <div class="needs small">
                                {winner === player
                                    ? "Winner"
                                    : `needs ${Math.max(0, player.raceTo - player.score)}`}
                                {#if active && !winner}
                                    <span class="visually-hidden"
                                        >, at the table</span
                                    >
                                {/if}
                            </div>
                        </div>
                    </div>
                </div>
            {/each}
        </div>

        <div class="ball-grid row row-cols-3 g-3 mb-3 flex-grow-1">
            {#each match.rack.balls as ball, i}
                <div class="col d-flex justify-content-center">
                    <Ball
                        number={i + 1}
                        state={ball.state}
                        madeBy={ball.state === "available"
                            ? undefined
                            : match.players[ball.by].name}
                        locked={isLocked(ball)}
                        onClick={() => tapBall(i, ball)}
                    />
                </div>
            {/each}
        </div>

        <div class="action-bar mt-auto d-flex flex-column gap-2">
            <div class="stats d-flex justify-content-center gap-3 small">
                <span>
                    <span class="stat-label">Dead</span>
                    <span class="fw-bold">{match.deadCarry + deadInRack}</span>
                    <span class="text-body-secondary"
                        >({deadInRack} this rack)</span
                    >
                </span>
                <span class="vr"></span>
                <span>
                    <span class="stat-label">Innings</span>
                    <span class="fw-bold"
                        >{match.inningCarry + match.rack.inning}</span
                    >
                    <span class="text-body-secondary"
                        >({match.rack.inning} this rack)</span
                    >
                </span>
            </div>
            {#if winner}
                <div class="fs-4 fw-bold text-center text-truncate">
                    {winner.name} wins!
                </div>
            {/if}
            <div class="d-flex gap-2">
                {#if undoNine}
                    <button
                        class="btn btn-outline-warning btn-lg text-nowrap"
                        onclick={undoLastNine}
                    >
                        Undo 9-ball
                    </button>
                {/if}
                {#if winner}
                    <button
                        class="btn btn-felt btn-lg flex-grow-1 text-nowrap"
                        onclick={resetMatch}
                    >
                        New Game
                    </button>
                {:else}
                    <button
                        class="btn btn-felt btn-lg flex-grow-1"
                        onclick={endTurn}
                    >
                        End Turn
                    </button>
                {/if}
            </div>
        </div>
    </div>

    <dialog
        bind:this={nineDialog}
        class="confirm-card rounded shadow border-0 p-0"
        aria-labelledby="confirm-nine-title"
    >
        <div class="p-3 text-center">
            <h2 id="confirm-nine-title" class="h4 mb-2">Pocket the 9-ball?</h2>
            <p class="mb-3">
                {#if leftovers > 0}
                    The {leftovers}
                    {leftovers === 1 ? "ball" : "balls"} still on the table will count
                    as dead, and the rack will reset.
                {:else}
                    The rack will reset.
                {/if}
            </p>
            <div class="d-flex gap-2 justify-content-center">
                <button
                    class="btn btn-outline-secondary btn-lg"
                    onclick={() => nineDialog?.close()}
                >
                    Cancel
                </button>
                <button class="btn btn-success btn-lg" onclick={pocketNine}>
                    Pocket 9
                </button>
            </div>
        </div>
    </dialog>
{/if}

<style>
    .header-icon {
        width: 40px;
        height: 40px;
    }
    .table-color {
        background-color: var(--felt);
    }
    .match {
        min-height: 100dvh;
    }
    /* The grid takes the height the cards and bottom bar leave over and
       spreads the three rows evenly across it */
    .ball-grid {
        align-content: space-evenly;
    }
    .player-card {
        transition:
            background-color 0.2s ease,
            color 0.2s ease;
    }
    .player-card.active {
        background-color: var(--felt);
        border-color: var(--felt);
        color: #fff;
    }
    .player-score {
        font-size: 2rem;
        line-height: 1.1;
    }
    .race-target {
        font-size: 0.45em;
    }
    .race-target,
    .needs,
    .stat-label {
        color: var(--bs-secondary-color);
    }
    .player-card.active .race-target,
    .player-card.active .needs {
        color: rgba(255, 255, 255, 0.75);
    }
    .stat-label {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    /* Pinned to the bottom edge, spanning the container's side padding */
    .action-bar {
        position: sticky;
        bottom: 0;
        margin-inline: calc(var(--bs-gutter-x) * -0.5);
        padding: 0.75rem calc(var(--bs-gutter-x) * 0.5);
        background-color: var(--bs-body-bg);
        border-top: 1px solid var(--bs-border-color);
    }
    .confirm-card {
        width: calc(100% - 32px);
        max-width: 360px;
        background-color: var(--bs-body-bg);
        color: var(--bs-body-color);
    }
    .confirm-card::backdrop {
        background: rgba(0, 0, 0, 0.5);
    }
</style>
