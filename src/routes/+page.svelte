<script lang="ts">
    import Ball from "$lib/components/Ball.svelte";
    import GameSetup from "$lib/components/GameSetup.svelte";
    import { getNextBallState } from "$lib/types/game";
    import Icon from "../images/9ball.png";

    // Game state using runes
    let isStarted = $state(false);
    let player1 = $state("");
    let player2 = $state("");
    let raceTo = $state(0);
    let currentPlayer = $state(0);
    let score1 = $state(0);
    let score2 = $state(0);
    let ballStates = $state(Array(9).fill("available"));

    // Derived values
    let winner = $derived.by(() => {
        if (score1 >= raceTo) return 0;
        if (score2 >= raceTo) return 1;
        return -1;
    });

    function startGame(p1: string, p2: string, rt: number) {
        player1 = p1;
        player2 = p2;
        raceTo = rt;
        isStarted = true;
        resetScores();
    }

    function resetScores() {
        score1 = 0;
        score2 = 0;
        ballStates = Array(9).fill("available");
        currentPlayer = 0;
    }

    function handleBallClick(ballIndex: number) {
        if (!isStarted) return;

        const isBall9 = ballIndex === 8;
        const currentState = ballStates[ballIndex];
        const nextState = getNextBallState(currentState, isBall9);

        if (
            isBall9 &&
            nextState === "sunk" &&
            !confirm(
                "Are you sure you want to pocket the 9-ball? This will reset all other balls."
            )
        ) {
            return;
        }

        // Update score
        if (currentState === "sunk" && nextState !== "sunk") {
            // Decrement score when unsinking a ball
            if (currentPlayer === 0) {
                score1 -= isBall9 ? 2 : 1;
            } else {
                score2 -= isBall9 ? 2 : 1;
            }
        }
        // Add point if pocketing a ball
        else if (currentState !== "sunk" && nextState === "sunk") {
            if (currentPlayer === 0) {
                score1 += isBall9 ? 2 : 1;
            } else {
                score2 += isBall9 ? 2 : 1;
            }
        }

        // Update ball states
        if (isBall9 && nextState === "sunk") {
            ballStates = Array(9).fill("available");
        } else {
            ballStates = ballStates.map((state, i) =>
                i === ballIndex ? nextState : state
            );
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
                    {player1}: {score1}
                </h2>
            </div>
            <div class="col-6">
                <h2
                    class="fs-2 text-center m-0"
                    class:active={currentPlayer === 1}
                >
                    {player2}: {score2}
                </h2>
            </div>
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
    .table-color {
        background-color: #155843;
    }
</style>
