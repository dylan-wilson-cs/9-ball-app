<script lang="ts">
    import Ball from "$lib/components/Ball.svelte";
    import GameSetup from "$lib/components/GameSetup.svelte";
    import { getNextBallState } from "$lib/types/game";
    import type { BallState, Player } from "$lib/types/game";
    import Icon from "../images/9ball.png";

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
    // Which player made each ball, so un-making it takes the points back
    // from the right player even after the turn has changed.
    let ballScorer = $state<(Player | null)[]>(Array(9).fill(null));
    // Dead balls from completed racks (shared total, not per player)
    let deadCarry = $state(0);
    let deadInRack = $derived(
        ballStates.filter((state) => state === "dead").length
    );
    let deadTotal = $derived(deadCarry + deadInRack);

    // Derived values
    let winner = $derived.by(() => {
        if (score1 >= raceTo1) return 0;
        if (score2 >= raceTo2) return 1;
        return -1;
    });

    function startGame(p1: string, p2: string, rt1: number, rt2: number) {
        player1 = p1;
        player2 = p2;
        raceTo1 = rt1;
        raceTo2 = rt2;
        isStarted = true;
        resetScores();
    }

    function resetScores() {
        score1 = 0;
        score2 = 0;
        ballStates = Array(9).fill("available");
        ballScorer = Array(9).fill(null);
        deadCarry = 0;
        currentPlayer = 0;
    }

    // In-page confirmation for making the 9. Browser confirm() dialogs are
    // blocked in sandboxed frames (e.g. the published page), where they
    // return false immediately and the 9 could never be made.
    let confirmingNine = $state(false);
    let leftoversOnTable = $derived(
        ballStates.filter((state, i) => i !== 8 && state === "available")
            .length
    );

    function confirmNine() {
        confirmingNine = false;
        handleBallClick(8, true);
    }

    function handleBallClick(ballIndex: number, confirmed = false) {
        if (!isStarted) return;

        const isBall9 = ballIndex === 8;
        const currentState = ballStates[ballIndex];
        const nextState = getNextBallState(currentState, isBall9);
        const leftovers = leftoversOnTable;

        if (isBall9 && nextState === "sunk" && !confirmed) {
            confirmingNine = true;
            return;
        }

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
        } else {
            ballStates = ballStates.map((state, i) =>
                i === ballIndex ? nextState : state
            );
            ballScorer = ballScorer.map((scorer, i) =>
                i === ballIndex
                    ? nextState === "sunk"
                        ? currentPlayer
                        : null
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
        currentPlayer = currentPlayer === 0 ? 1 : 0;
    }
</script>

<header class="table-color text-white py-2 mb-3">
    <div class="container-fluid">
        <div class="d-flex align-items-center justify-content-center">
            <img src={Icon} alt="" class="header-icon me-2" />
            <h1 class="mb-0 h2">9-Ball Scorekeeper</h1>
        </div>
    </div>
</header>

<div class="container-fluid">
    {#if !isStarted}
        <GameSetup onStartGame={startGame} />
    {:else}
        <!-- Score Header -->
        <div class="row g-3 mb-3">
            <div class="col-6">
                <h2
                    class="fs-2 text-center m-0"
                    class:active={currentPlayer === 0}
                >
                    {player1}: {score1}<span class="race-target">/{raceTo1}</span>
                </h2>
            </div>
            <div class="col-6">
                <h2
                    class="fs-2 text-center m-0"
                    class:active={currentPlayer === 1}
                >
                    {player2}: {score2}<span class="race-target">/{raceTo2}</span>
                </h2>
            </div>
        </div>

        <div class="text-center text-secondary fs-5 mb-3">
            Dead balls: <span class="fw-bold text-body">{deadTotal}</span>
            <span class="small">({deadInRack} this rack)</span>
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
                        onClick={() => handleBallClick(i)}
                    />
                </div>
            {/each}
        </div>

        {#if confirmingNine}
            <div class="confirm-backdrop">
                <div
                    class="card shadow confirm-card"
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="confirm-nine-title"
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
                </div>
            </div>
        {/if}

        <div class="d-flex justify-content-center">
            <button class="btn btn-primary btn-lg w-75" onclick={endTurn}>
                End Turn
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
    .confirm-backdrop {
        position: fixed;
        inset: 0;
        z-index: 1050;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 16px;
        background: rgba(0, 0, 0, 0.5);
    }
    .confirm-card {
        width: 100%;
        max-width: 360px;
    }
    .table-color {
        background-color: #155843;
    }
</style>
