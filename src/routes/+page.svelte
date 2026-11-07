<script lang="ts">
    import Ball from "$lib/components/Ball.svelte";
    import GameSetup from "$lib/components/GameSetup.svelte";
    import { BALL_COLORS, getNextBallState } from "$lib/types/game";
    import type { BallState, Player } from "$lib/types/game";
    import Icon from "../images/9ball.png";
    import { onMount } from "svelte";
    import { loadMatch, saveMatch, STORAGE_KEY } from "$lib/storage";
    import type { SavedMatch } from "$lib/storage";

    // Game state using runes
    let isStarted = $state(false);
    let player1 = $state("");
    let player2 = $state("");
    let raceTo1 = $state(0);
    let raceTo2 = $state(0);
    let currentPlayer = $state<Player>(0);
    let score1 = $state(0);
    let score2 = $state(0);
    let ballStates = $state<BallState[]>(Array(9).fill("available"));
    // Which player made or killed each ball. Un-making a ball takes the
    // points back from this player even after the turn has changed.
    let ballScorer = $state<(Player | null)[]>(Array(9).fill(null));
    // Ball numbers each player made in the current rack
    let madeInRack = $derived(
        ([0, 1] as const).map((player) =>
            ballScorer.flatMap((scorer, i) =>
                scorer === player && ballStates[i] === "sunk" ? [i + 1] : []
            )
        )
    );

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
        ballStates.filter((state) => state === "dead").length
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

    function startGame(p1: string, p2: string, rt1: number, rt2: number) {
        player1 = p1;
        player2 = p2;
        raceTo1 = rt1;
        raceTo2 = rt2;
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
            .length
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
                i === ballIndex ? nextState : state
            );
            ballScorer = ballScorer.map((scorer, i) =>
                i === ballIndex
                    ? nextState === "available"
                        ? null
                        : currentPlayer
                    : scorer
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

{#snippet madeBalls(numbers: number[])}
    <div
        class="made-balls d-flex justify-content-center flex-wrap gap-1 mt-1"
        aria-label="Made this rack: {numbers.length ? numbers.join(', ') : 'none'}"
    >
        {#each numbers as number}
            <span
                class="made-chip"
                class:striped={number > 8}
                style="--ball-color: {BALL_COLORS[number]};"
            >
                <span>{number}</span>
            </span>
        {/each}
    </div>
{/snippet}

<header class="table-color text-white py-2 mb-3">
    <div class="container-fluid">
        <div class="d-flex align-items-center justify-content-center">
            <img src={Icon} alt="" class="header-icon me-2" />
            <h1 class="mb-0 h2">9-Ball Scorekeeper</h1>
        </div>
    </div>
</header>

<div class="container-fluid">
    {#if !restored}
        <!-- Wait for the saved match to load to avoid flashing the setup form -->
    {:else if !isStarted}
        <GameSetup onStartGame={startGame} />
    {:else}
        <!-- Score Header -->
        <div class="row g-3 mb-3">
            <div class="col-6">
                <h2
                    class="score fs-2 m-0"
                    class:active={currentPlayer === 0}
                    title={player1}
                >
                    <span class="text-truncate">{player1}</span>:&nbsp;{score1}<span
                        class="race-target">/{raceTo1}</span
                    >
                </h2>
                {@render madeBalls(madeInRack[0])}
            </div>
            <div class="col-6">
                <h2
                    class="score fs-2 m-0"
                    class:active={currentPlayer === 1}
                    title={player2}
                >
                    <span class="text-truncate">{player2}</span>:&nbsp;{score2}<span
                        class="race-target">/{raceTo2}</span
                    >
                </h2>
                {@render madeBalls(madeInRack[1])}
            </div>
        </div>

        <div class="text-center text-secondary fs-5 mb-3">
            Dead balls: <span class="fw-bold text-body">{deadTotal}</span>
            <span class="small">({deadInRack} this rack)</span>
        </div>

        <div class="text-center text-secondary fs-5 mb-3">
            Innings: <span class="fw-bold text-body">{inningTotal}</span>
            <span class="small">(inning {rackInning} this rack)</span>
        </div>

        {#if winner !== -1}
            <div class="alert alert-success py-2 text-center mb-3">
                <span class="fs-3 fw-bold">
                    {winner === 0 ? player1 : player2} wins!
                </span>
                <button class="btn btn-primary ms-2" onclick={resetScores}>
                    New Game
                </button>
            </div>
        {/if}

        <div class="row row-cols-3 g-3 mb-4">
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

        {#if undoNine}
            <div class="d-flex justify-content-center mb-3">
                <button
                    class="btn btn-outline-warning btn-lg w-75"
                    onclick={undoLastNine}
                >
                    Undo 9-ball
                </button>
            </div>
        {/if}

        <dialog
            bind:this={nineDialog}
            class="confirm-card rounded shadow border-0 p-0"
            aria-labelledby="confirm-nine-title"
            onclose={() => (confirmingNine = false)}
        >
                    <div class="card-body text-center">
                        <h2 id="confirm-nine-title" class="h4 mb-2">
                            Pocket the 9-ball?
                        </h2>
                        <p class="mb-3">
                            {#if leftoversOnTable > 0}
                                The {leftoversOnTable}
                                {leftoversOnTable === 1 ? "ball" : "balls"} still
                                on the table will count as dead, and the rack
                                will reset.
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
                            <button
                                class="btn btn-success btn-lg"
                                onclick={confirmNine}
                            >
                                Pocket 9
                            </button>
                        </div>
                    </div>
        </dialog>

        <div class="d-flex justify-content-center">
            <button
                class="btn btn-primary btn-lg w-75"
                onclick={endTurn}
                disabled={winner !== -1}
            >
                End Turn
            </button>
        </div>

        <div class="d-flex justify-content-center mt-3 mb-4">
            <button
                class="btn btn-lg w-75"
                class:btn-outline-secondary={!confirmingEnd}
                class:btn-danger={confirmingEnd}
                onclick={endMatch}
            >
                {confirmingEnd ? "Tap again to end match" : "End Match"}
            </button>
        </div>
    {/if}
</div>

<style>
    .header-icon {
        width: 40px;
        height: 40px;
    }
    .active {
        color: #007bff;
        font-weight: bold;
    }
    .race-target {
        font-size: 0.6em;
        font-weight: normal;
        color: #6c757d;
    }
    .made-balls {
        min-height: 28px;
    }
    .made-chip {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        border-radius: 50%;
        background: var(--ball-color);
    }
    .made-chip.striped {
        background: linear-gradient(
            to bottom,
            #f8f6ef 0 24%,
            var(--ball-color) 24% 76%,
            #f8f6ef 76% 100%
        );
    }
    .made-chip span {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 16px;
        height: 16px;
        border-radius: 50%;
        background: #fff;
        color: #111;
        font-size: 0.7rem;
        font-weight: 700;
    }
    .score {
        display: flex;
        justify-content: center;
        align-items: baseline;
        white-space: nowrap;
    }
    .score .text-truncate {
        min-width: 0;
    }
    .confirm-card::backdrop {
        background: rgba(0, 0, 0, 0.5);
    }
    .confirm-card {
        width: calc(100% - 32px);
        max-width: 360px;
    }
    .table-color {
        background-color: #155843;
    }
</style>
