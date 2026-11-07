<script lang="ts">
    import Ball from "$lib/components/Ball.svelte";
    import GameSetup from "$lib/components/GameSetup.svelte";
    import { getNextBallState } from "$lib/types/game";
    import type { BallState, Player } from "$lib/types/game";
    import Icon from "../images/9ball.png";
    import { onMount } from "svelte";
    import { loadMatch, saveMatch, STORAGE_KEY } from "$lib/storage";
    import type { SavedMatch } from "$lib/storage";

    // Game state using runes
    let isStarted = $state(false);
    // Defaults for the first setup form; later forms show the last match
    let player1 = $state("John");
    let player2 = $state("Doe");
    let raceTo1 = $state(25);
    let raceTo2 = $state(25);
    let currentPlayer = $state<Player>(0);
    let score1 = $state(0);
    let score2 = $state(0);
    let ballStates = $state<BallState[]>(Array(9).fill("available"));
    // Which player made or killed each ball. Un-making a ball takes the
    // points back from this player even after the turn has changed.
    let ballScorer = $state<(Player | null)[]>(Array(9).fill(null));

    // A ball the opponent made or killed this rack cannot be changed on
    // your turn
    function isLocked(ballIndex: number): boolean {
        const scorer = ballScorer[ballIndex];
        return (
            ballStates[ballIndex] !== "available" &&
            scorer !== null &&
            scorer !== currentPlayer
        );
    }
    // Dead balls from completed racks (shared total, not per player)
    let deadCarry = $state(0);
    let deadInRack = $derived(
        ballStates.filter((state) => state === "dead").length,
    );
    let deadTotal = $derived(deadCarry + deadInRack);

    // Innings follow the APA rule: an inning ends when the player who broke
    // the rack and their opponent have each had a turn. The rack's inning in
    // progress counts toward the match total, including when the 9 ends it.
    let rackBreaker = $state<Player>(0);
    let rackInning = $state(1);
    // Innings from completed racks
    let inningCarry = $state(0);
    let inningTotal = $derived(inningCarry + rackInning);

    // Derived values
    let winner = $derived.by(() => {
        if (score1 >= raceTo1) return 0;
        if (score2 >= raceTo2) return 1;
        return -1;
    });

    // Persist the match so a reload or browser restart resumes it.
    // Saving starts only after the saved match has been loaded, so the
    // initial empty state never overwrites it.
    let restored = $state(false);

    function snapshot(): SavedMatch {
        return {
            isStarted,
            player1,
            player2,
            raceTo1,
            raceTo2,
            currentPlayer,
            score1,
            score2,
            ballStates: [...ballStates],
            ballScorer: [...ballScorer],
            deadCarry,
            rackBreaker,
            rackInning,
            inningCarry,
        };
    }

    function applyMatch(saved: SavedMatch) {
        isStarted = saved.isStarted;
        player1 = saved.player1;
        player2 = saved.player2;
        raceTo1 = saved.raceTo1;
        raceTo2 = saved.raceTo2;
        currentPlayer = saved.currentPlayer;
        score1 = saved.score1;
        score2 = saved.score2;
        ballStates = saved.ballStates;
        ballScorer = saved.ballScorer;
        deadCarry = saved.deadCarry;
        rackBreaker = saved.rackBreaker;
        rackInning = saved.rackInning;
        inningCarry = saved.inningCarry;
    }

    onMount(() => {
        const saved = loadMatch();
        if (saved) applyMatch(saved);
        restored = true;

        // Another tab changed the match: follow it, so this tab's next
        // save doesn't overwrite that change with stale state
        function onStorage(event: StorageEvent) {
            if (event.key !== STORAGE_KEY) return;
            const changed = loadMatch();
            if (!changed) return;
            applyMatch(changed);
            undoNine = null;
            confirmingNine = false;
        }
        window.addEventListener("storage", onStorage);
        return () => window.removeEventListener("storage", onStorage);
    });

    $effect(() => {
        if (!restored) return;
        saveMatch(snapshot());
    });

    // "End Match" needs a second tap within a few seconds, so a stray tap
    // can't wipe a saved match.
    let confirmingEnd = $state(false);
    let confirmEndTimer: ReturnType<typeof setTimeout> | undefined;

    function endMatch() {
        if (!confirmingEnd) {
            confirmingEnd = true;
            clearTimeout(confirmEndTimer);
            confirmEndTimer = setTimeout(() => (confirmingEnd = false), 3000);
            return;
        }
        clearTimeout(confirmEndTimer);
        confirmingEnd = false;
        resetScores();
        isStarted = false;
    }

    function startGame() {
        player1 = player1.trim();
        player2 = player2.trim();
        isStarted = true;
        resetScores();
    }

    function resetScores() {
        undoNine = null;
        score1 = 0;
        score2 = 0;
        ballStates = Array(9).fill("available");
        ballScorer = Array(9).fill(null);
        deadCarry = 0;
        currentPlayer = 0;
        rackBreaker = 0;
        rackInning = 1;
        inningCarry = 0;
    }

    // In-page confirmation for making the 9. Browser confirm() dialogs are
    // blocked in sandboxed frames (e.g. the published page), where they
    // return false immediately and the 9 could never be made.
    // A modal <dialog> makes the rest of the page inert, so the turn can't
    // change while the 9 is waiting for confirmation.
    let confirmingNine = $state(false);
    let nineDialog = $state<HTMLDialogElement>();
    let leftoversOnTable = $derived(
        ballStates.filter((state, i) => i !== 8 && state === "available")
            .length,
    );

    $effect(() => {
        if (!nineDialog) return;
        if (confirmingNine && !nineDialog.open) nineDialog.showModal();
        if (!confirmingNine && nineDialog.open) nineDialog.close();
    });

    function confirmNine() {
        confirmingNine = false;
        handleBallClick(8, true);
    }

    // The match as it was before the last 9 was made, so a mistaken 9 can
    // be taken back. Cleared by the next change to the match.
    let undoNine = $state<SavedMatch | null>(null);

    function undoLastNine() {
        if (!undoNine) return;
        applyMatch(undoNine);
        undoNine = null;
    }

    // Ignore a second tap on the same ball this soon after the first, so a
    // double tap on a phone doesn't skip past "made" to "dead"
    const DOUBLE_TAP_MS = 400;
    let lastTap = { ball: -1, time: 0 };

    function handleBallClick(ballIndex: number, confirmed = false) {
        if (!isStarted || isLocked(ballIndex)) return;

        if (!confirmed) {
            const now = Date.now();
            const isDoubleTap =
                lastTap.ball === ballIndex &&
                now - lastTap.time < DOUBLE_TAP_MS;
            lastTap = { ball: ballIndex, time: now };
            if (isDoubleTap) return;
        }

        const isBall9 = ballIndex === 8;
        const currentState = ballStates[ballIndex];
        if (currentState === undefined) return;
        const nextState = getNextBallState(currentState, isBall9);
        const leftovers = leftoversOnTable;

        // Once the match is won, balls can only be un-made, to correct a
        // mistaken final ball
        if (winner !== -1 && nextState === "sunk") return;

        if (isBall9 && nextState === "sunk" && !confirmed) {
            confirmingNine = true;
            return;
        }

        undoNine = isBall9 && nextState === "sunk" ? snapshot() : null;

        const points = isBall9 ? 2 : 1;

        // Un-making a ball takes the points back from whoever made it
        if (currentState === "sunk" && nextState !== "sunk") {
            addPoints(ballScorer[ballIndex] ?? currentPlayer, -points);
        }
        // Making a ball scores for the current player
        else if (currentState !== "sunk" && nextState === "sunk") {
            addPoints(currentPlayer, points);
        }

        if (isBall9 && nextState === "sunk") {
            // Rack over: this rack's dead balls, plus any balls left on
            // the table, go into the running dead-ball total
            deadCarry += deadInRack + leftovers;
            ballStates = Array(9).fill("available");
            ballScorer = Array(9).fill(null);
            // The player who made the 9 breaks the next rack
            inningCarry += rackInning;
            rackInning = 1;
            rackBreaker = currentPlayer;
        } else {
            ballStates = ballStates.map((state, i) =>
                i === ballIndex ? nextState : state,
            );
            ballScorer = ballScorer.map((scorer, i) =>
                i === ballIndex
                    ? nextState === "available"
                        ? null
                        : currentPlayer
                    : scorer,
            );
        }
    }

    function addPoints(player: Player, points: number) {
        if (player === 0) {
            score1 += points;
        } else {
            score2 += points;
        }
    }

    function endTurn() {
        if (winner !== -1) return;
        undoNine = null;
        if (currentPlayer !== rackBreaker) {
            rackInning += 1;
        }
        currentPlayer = currentPlayer === 0 ? 1 : 0;
    }
</script>

{#snippet playerCard(
    player: Player,
    name: string,
    score: number,
    raceTo: number,
)}
    {@const active =
        winner === -1 ? currentPlayer === player : winner === player}
    <div class="col-6">
        <div class="player-card card h-100 text-center" class:active>
            <div class="card-body px-2 py-1">
                <h2
                    class="player-name h6 fw-bold text-truncate m-0"
                    title={name}
                >
                    {name}
                </h2>
                <div class="player-score">
                    <span class="fw-bold">{score}</span><span
                        class="race-target">/{raceTo}</span
                    >
                </div>
                <div class="needs small">
                    {winner === player
                        ? "Winner"
                        : `needs ${Math.max(0, raceTo - score)}`}
                    {#if active && winner === -1}
                        <span class="visually-hidden">, at the table</span>
                    {/if}
                </div>
            </div>
        </div>
    </div>
{/snippet}

{#if !restored}
    <!-- Wait for the saved match to load to avoid flashing the setup form -->
{:else if !isStarted}
    <header class="table-color text-white py-2 mb-3">
        <div class="container-fluid">
            <div class="d-flex align-items-center justify-content-center">
                <img src={Icon} alt="" class="header-icon me-2" />
                <h1 class="mb-0 h2">9-Ball Scorekeeper</h1>
            </div>
        </div>
    </header>
    <div class="container-fluid pb-4">
        <GameSetup
            bind:player1
            bind:player2
            bind:raceTo1
            bind:raceTo2
            onStartGame={startGame}
        />
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
            {@render playerCard(0, player1, score1, raceTo1)}
            {@render playerCard(1, player2, score2, raceTo2)}
        </div>

        <div class="ball-grid row row-cols-3 g-3 mb-3 flex-grow-1">
            {#each ballStates as state, i}
                <div class="col d-flex justify-content-center">
                    <Ball
                        number={i + 1}
                        {state}
                        madeBy={ballScorer[i] === 0
                            ? player1
                            : ballScorer[i] === 1
                              ? player2
                              : undefined}
                        locked={isLocked(i)}
                        onClick={() => handleBallClick(i)}
                    />
                </div>
            {/each}
        </div>

        <div class="action-bar mt-auto d-flex flex-column gap-2">
            <div class="stats d-flex justify-content-center gap-3 small">
                <span>
                    <span class="stat-label">Dead</span>
                    <span class="fw-bold">{deadTotal}</span>
                    <span class="text-body-secondary"
                        >({deadInRack} this rack)</span
                    >
                </span>
                <span class="vr"></span>
                <span>
                    <span class="stat-label">Innings</span>
                    <span class="fw-bold">{inningTotal}</span>
                    <span class="text-body-secondary"
                        >({rackInning} this rack)</span
                    >
                </span>
            </div>
            {#if winner !== -1}
                <div class="fs-4 fw-bold text-center text-truncate">
                    {winner === 0 ? player1 : player2} wins!
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
                {#if winner !== -1}
                    <button
                        class="btn btn-felt btn-lg flex-grow-1 text-nowrap"
                        onclick={resetScores}
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
        onclose={() => (confirmingNine = false)}
    >
        <div class="p-3 text-center">
            <h2 id="confirm-nine-title" class="h4 mb-2">Pocket the 9-ball?</h2>
            <p class="mb-3">
                {#if leftoversOnTable > 0}
                    The {leftoversOnTable}
                    {leftoversOnTable === 1 ? "ball" : "balls"} still on the table
                    will count as dead, and the rack will reset.
                {:else}
                    The rack will reset.
                {/if}
            </p>
            <div class="d-flex gap-2 justify-content-center">
                <button
                    class="btn btn-outline-secondary btn-lg"
                    onclick={() => (confirmingNine = false)}
                >
                    Cancel
                </button>
                <button class="btn btn-success btn-lg" onclick={confirmNine}>
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
        color: var(--bs-secondary-color);
    }
    .needs {
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
        color: var(--bs-secondary-color);
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
    .confirm-card::backdrop {
        background: rgba(0, 0, 0, 0.5);
    }
    .confirm-card {
        width: calc(100% - 32px);
        max-width: 360px;
        background-color: var(--bs-body-bg);
        color: var(--bs-body-color);
    }
</style>
