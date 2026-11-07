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
    onclick={onClick}
    disabled={locked}
    aria-label="{number} ball, {label}{locked ? ', locked' : ''}"
>
    <span
        class="ball-body"
        class:striped
        class:made={state === "sunk"}
        class:dead={state === "dead"}
        style="--ball-color: {color};"
    >
        <span class="ball-number">{number}</span>
    </span>

    {#if state === "sunk"}
        <span class="status-badge made-badge" aria-hidden="true">✓</span>
    {:else if state === "dead"}
        <span class="status-badge dead-badge" aria-hidden="true">✗</span>
    {/if}
</button>

<style>
    .ball {
        position: relative;
        width: min(100px, 26vw);
        aspect-ratio: 1;
        padding: 0;
        border: none;
        border-radius: 50%;
        background: none;
        cursor: pointer;
        -webkit-tap-highlight-color: transparent;
        transition: transform 0.1s ease;
    }

    .ball:disabled {
        cursor: not-allowed;
    }

    .ball:disabled .ball-body {
        opacity: 0.2;
    }

    .ball:not(:disabled):active {
        transform: scale(0.94);
    }

    .ball:focus-visible {
        outline: 3px solid #0d6efd;
        outline-offset: 4px;
    }

    .ball-body {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        background: radial-gradient(
            circle at 45% 40%,
            var(--ball-color) 45%,
            color-mix(in srgb, var(--ball-color) 55%, black) 100%
        );
        box-shadow:
            0 6px 10px rgba(0, 0, 0, 0.35),
            inset -6px -8px 14px rgba(0, 0, 0, 0.3);
        transition:
            opacity 0.2s ease,
            filter 0.2s ease;
    }

    .ball-body.striped {
        background: linear-gradient(
            to bottom,
            #f8f6ef 0 24%,
            var(--ball-color) 24% 76%,
            #f8f6ef 76% 100%
        );
        box-shadow:
            0 6px 10px rgba(0, 0, 0, 0.35),
            inset -6px -8px 16px rgba(0, 0, 0, 0.35);
    }

    .ball-body.made {
        opacity: 0.4;
    }

    .ball-body.dead {
        opacity: 0.35;
        filter: grayscale(1);
    }

    .ball-number {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 46%;
        aspect-ratio: 1;
        border-radius: 50%;
        background: #fff;
        color: #111;
        font-weight: 700;
        font-size: clamp(1rem, 4.5vw, 1.5rem);
        line-height: 1;
        box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.25);
    }

    .status-badge {
        position: absolute;
        top: -2%;
        right: -2%;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 36%;
        aspect-ratio: 1;
        border: 3px solid #fff;
        border-radius: 50%;
        color: #fff;
        font-weight: 700;
        font-size: clamp(0.9rem, 4vw, 1.3rem);
        line-height: 1;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
    }

    .made-badge {
        background: #198754;
    }

    .dead-badge {
        background: #dc3545;
    }
</style>
