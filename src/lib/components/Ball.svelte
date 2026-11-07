<script lang="ts">
    import type { BallState } from "$lib/types/game";
    import { BALL_COLORS } from "$lib/types/game";

    interface Props {
        number: number;
        state: BallState;
        // Name of the player who made the ball, when it is made
        madeBy?: string | undefined;
        // A locked ball is one the opponent made or killed this rack
        locked?: boolean;
        onClick: () => void;
    }

    let { number, state, madeBy, locked = false, onClick }: Props = $props();

    let color = $derived(BALL_COLORS[number]);
    let striped = $derived(number > 8);
    let label = $derived(
        state === "sunk"
            ? madeBy
                ? `made by ${madeBy}`
                : "made"
            : state === "dead"
              ? "dead"
              : "on table",
    );
</script>

<button
    type="button"
    class="ball"
    class:made={state === "sunk"}
    class:dead={state === "dead"}
    onclick={onClick}
    disabled={locked}
    aria-label="{number} ball, {label}{locked ? ', locked' : ''}"
>
    <span class="ball-body" class:striped style="--ball-color: {color};">
        <span class="ball-number">{number}</span>
    </span>

    {#if state === "sunk"}
        <span class="status-badge made-badge" aria-hidden="true">✓</span>
    {:else if state === "dead"}
        <span class="status-badge dead-badge" aria-hidden="true">✕</span>
    {/if}
</button>

<style>
    .ball {
        position: relative;
        width: var(--ball-size, 96px);
        aspect-ratio: 1;
        padding: 0;
        border: none;
        border-radius: 50%;
        background: none;
    }

    .ball:disabled {
        cursor: not-allowed;
        opacity: 0.25;
    }

    .ball:focus-visible {
        outline-offset: 5px;
    }

    .ball-body {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        background:
            radial-gradient(
                circle at 34% 28%,
                rgba(255, 255, 255, 0.55) 0 6%,
                transparent 18%
            ),
            radial-gradient(
                circle at 42% 38%,
                var(--ball-color) 40%,
                color-mix(in srgb, var(--ball-color) 50%, black) 100%
            );
        box-shadow: 0 8px 12px -4px rgba(0, 0, 0, 0.55);
        transition:
            transform 0.18s ease,
            opacity 0.18s ease,
            filter 0.18s ease;
    }

    /* The stripe ball keeps the ivory caps above and below the color band */
    .ball-body.striped {
        background:
            radial-gradient(
                circle at 34% 28%,
                rgba(255, 255, 255, 0.6) 0 6%,
                transparent 18%
            ),
            radial-gradient(
                circle at 42% 38%,
                transparent 55%,
                rgba(0, 0, 0, 0.35) 100%
            ),
            linear-gradient(
                to bottom,
                var(--ivory) 0 22%,
                var(--ball-color) 22% 78%,
                var(--ivory) 78% 100%
            );
    }

    .ball:not(:disabled):active .ball-body {
        transform: scale(0.93);
    }

    /* A made ball drops into the cloth: smaller, flatter, faded */
    .made .ball-body {
        transform: scale(0.72);
        opacity: 0.45;
        box-shadow: inset 0 3px 8px rgba(0, 0, 0, 0.5);
    }

    .dead .ball-body {
        transform: scale(0.72);
        opacity: 0.4;
        filter: grayscale(1);
        box-shadow: none;
    }

    .ball-number {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 48%;
        aspect-ratio: 1;
        border-radius: 50%;
        background: var(--ivory);
        color: #1a1a1a;
        font-family: var(--font-display);
        font-weight: 800;
        font-size: calc(var(--ball-size, 96px) * 0.3);
        line-height: 1;
    }

    .status-badge {
        position: absolute;
        right: 4%;
        bottom: 4%;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 36%;
        aspect-ratio: 1;
        border: 3px solid var(--cloth-deep);
        border-radius: 50%;
        font-weight: 700;
        font-size: calc(var(--ball-size, 96px) * 0.19);
        line-height: 1;
    }

    .made-badge {
        background: var(--brass);
        color: var(--rail);
    }

    .dead-badge {
        background: var(--ivory-dim);
        color: var(--cloth-shadow);
    }
</style>
