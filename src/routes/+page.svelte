<script lang="ts">
    import Ball from "$lib/components/Ball.svelte";
    import GameSetup from "$lib/components/GameSetup.svelte";
    import { BALL_COLORS, getNextBallState } from "$lib/types/game";
    import type { BallState, Player } from "$lib/types/game";
    import { onMount } from "svelte";
    import { loadMatch, saveMatch, STORAGE_KEY } from "$lib/storage";
    import type { SavedMatch } from "$lib/storage";

    // Ball numbers by row of the racked diamond, apex first
    const RACK_ROWS = [[1], [2, 3], [4, 9, 5], [6, 7], [8]] as const;

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
    // Ball numbers each player made in the current rack
    function madeInRack(player: Player): number[] {
        return ballScorer.flatMap((scorer, i) =>
            scorer === player && ballStates[i] === "sunk" ? [i + 1] : [],
        );
    }

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

{#snippet player(index: Player, name: string, score: number, raceTo: number)}
    <section
        class="player"
        class:active={currentPlayer === index}
        aria-current={currentPlayer === index ? "true" : undefined}
        aria-label="{name}, {score} of {raceTo}{currentPlayer === index
            ? ', shooting'
            : ''}"
    >
        <h2 class="name" title={name}>
            <span class="sight" aria-hidden="true"></span>
            <span class="name-text">{name}</span>
        </h2>
        <p class="score">
            {score}<span class="race-target">of {raceTo}</span>
        </p>
        <div class="progress" aria-hidden="true">
            <span style="width: {Math.min(100, (score / raceTo) * 100)}%"
            ></span>
        </div>
        {@render madeBalls(madeInRack(index))}
    </section>
{/snippet}

{#snippet madeBalls(numbers: number[])}
    <div
        class="made-balls"
        aria-label="Made this rack: {numbers.length
            ? numbers.join(', ')
            : 'none'}"
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

{#if !restored}
    <!-- Wait for the saved match to load to avoid flashing the setup form -->
{:else if !isStarted}
    <GameSetup
        bind:player1
        bind:player2
        bind:raceTo1
        bind:raceTo2
        onStartGame={startGame}
    />
{:else}
    <main class="match">
        <div class="players">
            {@render player(0, player1, score1, raceTo1)}
            {@render player(1, player2, score2, raceTo2)}
        </div>

        <dl class="tallies">
            <div>
                <dt>Dead balls</dt>
                <dd>
                    {deadTotal}
                    <span class="this-rack">{deadInRack} this rack</span>
                </dd>
            </div>
            <div>
                <dt>Innings</dt>
                <dd>
                    {inningTotal}
                    <span class="this-rack">inning {rackInning} this rack</span>
                </dd>
            </div>
        </dl>

        {#if winner !== -1}
            <div class="winner" role="status">
                <p>{winner === 0 ? player1 : player2} wins the match</p>
                <button class="btn btn-primary" onclick={resetScores}>
                    Rematch
                </button>
            </div>
        {/if}

        <!-- The balls sit in the 9-ball diamond: the 1 at the apex and the
             9 in the middle -->
        <div class="rack">
            {#each RACK_ROWS as row}
                <div class="rack-row">
                    {#each row as number}
                        {@const i = number - 1}
                        <Ball
                            {number}
                            state={ballStates[i] ?? "available"}
                            madeBy={ballScorer[i] === 0
                                ? player1
                                : ballScorer[i] === 1
                                  ? player2
                                  : undefined}
                            locked={isLocked(i)}
                            onClick={() => handleBallClick(i)}
                        />
                    {/each}
                </div>
            {/each}
        </div>

        <div class="rail">
            <button
                class="btn btn-primary end-turn"
                onclick={endTurn}
                disabled={winner !== -1}
            >
                End turn
            </button>
            <div class="rail-secondary">
                {#if undoNine}
                    <button class="btn btn-quiet" onclick={undoLastNine}>
                        Undo 9-ball
                    </button>
                {/if}
                <button
                    class="btn"
                    class:btn-quiet={!confirmingEnd}
                    class:btn-danger={confirmingEnd}
                    onclick={endMatch}
                >
                    {confirmingEnd ? "Tap again to end match" : "End match"}
                </button>
            </div>
        </div>
    </main>

    <dialog
        bind:this={nineDialog}
        class="confirm"
        aria-labelledby="confirm-nine-title"
        onclose={() => (confirmingNine = false)}
    >
        <h2 id="confirm-nine-title">Pocket the 9-ball?</h2>
        <p>
            {#if leftoversOnTable > 0}
                The {leftoversOnTable}
                {leftoversOnTable === 1 ? "ball" : "balls"} still on the table will
                count as dead, and the rack will reset.
            {:else}
                The rack will reset.
            {/if}
        </p>
        <div class="confirm-actions">
            <button
                class="btn btn-quiet"
                onclick={() => (confirmingNine = false)}
            >
                Cancel
            </button>
            <button class="btn btn-primary" onclick={confirmNine}>
                Pocket 9
            </button>
        </div>
    </dialog>
{/if}

<style>
    .match {
        --ball-size: min(88px, 24vw, 10.5svh);
        --ball-gap: calc(var(--ball-size) * 0.12);

        display: flex;
        flex-direction: column;
        min-height: 100svh;
        width: min(100%, 30rem);
        margin: 0 auto;
    }

    .players {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1rem;
        padding: max(1rem, env(safe-area-inset-top)) 1.25rem 0;
    }

    .player {
        min-width: 0;
        color: var(--ivory-dim);
        transition: color 0.15s ease;
    }

    .player.active {
        color: var(--ivory);
    }

    .name {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin: 0;
        font-size: 1.125rem;
        font-weight: 700;
    }

    .name-text {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    /* The diamond rail sight marks the player at the table */
    .sight {
        flex: none;
        width: 0.7rem;
        height: 0.7rem;
        background: var(--brass);
        transform: rotate(45deg) scale(0);
        transition: transform 0.2s ease;
    }

    .active .sight {
        transform: rotate(45deg) scale(1);
    }

    .score {
        display: flex;
        align-items: baseline;
        gap: 0.4rem;
        margin: 0;
        font-family: var(--font-display);
        font-weight: 800;
        font-size: 4.5rem;
        line-height: 1;
        font-variant-numeric: tabular-nums;
    }

    .race-target {
        font-family: var(--font-body);
        font-weight: 400;
        font-size: 0.9375rem;
        color: var(--ivory-dim);
    }

    .progress {
        height: 4px;
        border-radius: 2px;
        background: var(--cloth-shadow);
        overflow: hidden;
    }

    .progress span {
        display: block;
        height: 100%;
        background: var(--ivory-dim);
        transition: width 0.25s ease;
    }

    .active .progress span {
        background: var(--brass);
    }

    .made-balls {
        display: flex;
        flex-wrap: wrap;
        gap: 0.25rem;
        min-height: 1.5rem;
        margin-top: 0.5rem;
    }

    .made-chip {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 1.5rem;
        height: 1.5rem;
        border-radius: 50%;
        background: var(--ball-color);
    }

    .made-chip.striped {
        background: linear-gradient(
            to bottom,
            var(--ivory) 0 24%,
            var(--ball-color) 24% 76%,
            var(--ivory) 76% 100%
        );
    }

    .made-chip span {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 0.875rem;
        height: 0.875rem;
        border-radius: 50%;
        background: var(--ivory);
        color: #1a1a1a;
        font-size: 0.625rem;
        font-weight: 700;
    }

    .tallies {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        margin: 0.75rem 1.25rem 0;
        padding-top: 0.625rem;
        border-top: 1px solid color-mix(in srgb, var(--ivory) 15%, transparent);
    }

    .tallies div {
        display: flex;
        align-items: baseline;
        gap: 0.5rem;
    }

    dt {
        color: var(--ivory-dim);
        font-size: 0.9375rem;
    }

    dd {
        margin: 0;
        font-family: var(--font-display);
        font-weight: 800;
        font-size: 1.5rem;
        line-height: 1;
    }

    .this-rack {
        display: block;
        margin-top: 0.125rem;
        font-family: var(--font-body);
        font-weight: 400;
        font-size: 0.75rem;
        color: var(--ivory-dim);
    }

    .winner {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        margin: 1rem 1.25rem 0;
        padding: 0.75rem 0.75rem 0.75rem 1rem;
        border-radius: 0.5rem;
        background: var(--cloth-shadow);
    }

    .winner p {
        margin: 0;
        font-family: var(--font-display);
        font-weight: 800;
        font-size: 1.75rem;
        line-height: 1.05;
    }

    .rack {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 1.25rem 0;
    }

    .rack-row {
        display: flex;
        gap: var(--ball-gap);
    }

    /* Rows of touching balls stack at sin(60deg) of their spacing */
    .rack-row + .rack-row {
        margin-top: calc(
            (var(--ball-size) + var(--ball-gap)) * 0.866 - var(--ball-size)
        );
    }

    .rail {
        position: sticky;
        bottom: 0;
        display: flex;
        flex-direction: column;
        gap: 0.625rem;
        padding: 0.875rem 1.25rem max(0.875rem, env(safe-area-inset-bottom));
        background: linear-gradient(
            to bottom,
            var(--rail-light),
            var(--rail) 0.5rem
        );
        box-shadow: 0 -6px 16px rgba(0, 0, 0, 0.35);
    }

    .end-turn {
        min-height: 3.75rem;
        font-size: 1.25rem;
    }

    .rail-secondary {
        display: flex;
        gap: 0.625rem;
    }

    .rail-secondary .btn {
        flex: 1;
        min-height: 2.75rem;
        font-size: 1rem;
    }

    .confirm {
        width: calc(100% - 2rem);
        max-width: 22rem;
        padding: 1.5rem 1.25rem 1.25rem;
        border: none;
        border-top: 4px solid var(--brass);
        border-radius: 0.5rem;
        background: var(--rail);
        color: var(--ivory);
    }

    .confirm::backdrop {
        background: rgba(8, 24, 34, 0.7);
    }

    .confirm h2 {
        margin: 0 0 0.5rem;
        font-family: var(--font-display);
        font-weight: 800;
        font-size: 2rem;
        line-height: 1;
    }

    .confirm p {
        margin: 0 0 1.25rem;
    }

    .confirm-actions {
        display: flex;
        gap: 0.625rem;
    }

    .confirm-actions .btn {
        flex: 1;
    }
</style>
