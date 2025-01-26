<script lang="ts">
    import type { BallState } from "$lib/types/game";
    import { BALL_COLORS } from "$lib/types/game";

    interface Props {
        number: number;
        state: BallState;
        onClick: () => void;
    }

    let { number, state, onClick }: Props = $props();

    let backgroundColor = $derived(BALL_COLORS[number]);
    let ballOpacity = $derived(
        state === "available" ? 1 : state === "dead" ? 0.3 : 0.7
    );
    let statusIcon = $derived(
        state === "sunk"
            ? "fa-solid fa-check text-success"
            : state === "dead"
              ? "fa-solid fa-x text-danger"
              : ""
    );
</script>

<button
    onclick={onClick}
    class="ball rounded-circle d-flex align-items-center justify-content-center position-relative"
    style="width: 100px; height: 100px; background-color: {backgroundColor}; opacity: {ballOpacity};"
>
    <div
        class="rounded-circle bg-white position-absolute"
        style="width: 40px; height: 40px; display: flex; align-items: center; justify-content: center;"
    >
        {number}
    </div>

    {#if statusIcon}
        <div class="status-indicator">
            <i class={statusIcon}></i>
        </div>
    {/if}
</button>

<style>
    .status-indicator {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: clamp(1.5rem, 5vw, 3rem);
        z-index: 2;
        filter: drop-shadow(0 2px 2px rgba(0, 0, 0, 0.3));
    }
</style>
