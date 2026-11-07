<script lang="ts">
    // The fields are bound to the page's match state, so the last names and
    // race targets are still filled in after a match ends
    interface Props {
        player1: string;
        player2: string;
        raceTo1: number;
        raceTo2: number;
        onStartGame: () => void;
    }

    let {
        player1 = $bindable(),
        player2 = $bindable(),
        raceTo1 = $bindable(),
        raceTo2 = $bindable(),
        onStartGame,
    }: Props = $props();

    let onsubmit = (e: Event) => {
        e.preventDefault();
        onStartGame();
    };

    const MIN_RACE = 14;
    const MAX_RACE = 100;
    // At least one non-space character, so a name can't be blank
    const NAME_PATTERN = ".*\\S.*";
</script>

<form class="setup" {onsubmit}>
    <h1>New match</h1>

    <fieldset>
        <legend class="visually-hidden">First player</legend>
        <div class="field name">
            <label for="player1">First player</label>
            <input
                type="text"
                id="player1"
                autocomplete="off"
                bind:value={player1}
                pattern={NAME_PATTERN}
                title="Enter a name"
                required
            />
        </div>
        <div class="field race">
            <label for="raceTo1">Races to</label>
            <input
                type="number"
                inputmode="numeric"
                id="raceTo1"
                bind:value={raceTo1}
                min={MIN_RACE}
                max={MAX_RACE}
                required
            />
        </div>
    </fieldset>

    <fieldset>
        <legend class="visually-hidden">Second player</legend>
        <div class="field name">
            <label for="player2">Second player</label>
            <input
                type="text"
                id="player2"
                autocomplete="off"
                bind:value={player2}
                pattern={NAME_PATTERN}
                title="Enter a name"
                required
            />
        </div>
        <div class="field race">
            <label for="raceTo2">Races to</label>
            <input
                type="number"
                inputmode="numeric"
                id="raceTo2"
                bind:value={raceTo2}
                min={MIN_RACE}
                max={MAX_RACE}
                required
            />
        </div>
    </fieldset>

    <p class="hint">
        Race targets run from {MIN_RACE} to {MAX_RACE} points. The first player breaks.
    </p>

    <button type="submit" class="btn btn-primary start">Start match</button>
</form>

<style>
    .setup {
        display: flex;
        flex-direction: column;
        gap: 1.25rem;
        width: min(100%, 30rem);
        margin: 0 auto;
        padding: 2.5rem 1.25rem 2rem;
    }

    h1 {
        margin: 0 0 0.5rem;
        font-family: var(--font-display);
        font-weight: 800;
        font-size: 3.5rem;
        line-height: 0.95;
    }

    fieldset {
        display: flex;
        gap: 0.75rem;
        margin: 0;
        padding: 1rem 0 1.25rem;
        border: none;
        border-top: 2px solid var(--brass);
    }

    .field {
        display: flex;
        flex-direction: column;
        gap: 0.375rem;
    }

    .name {
        flex: 1;
        min-width: 0;
    }

    .race {
        width: 6rem;
    }

    label {
        color: var(--ivory-dim);
        font-size: 0.9375rem;
    }

    input {
        width: 100%;
        min-height: 3.25rem;
        padding: 0.375rem 0.75rem;
        border: 2px solid transparent;
        border-radius: 0.5rem;
        background: var(--cloth-shadow);
        font-family: var(--font-display);
        font-weight: 700;
        font-size: 1.75rem;
        line-height: 1;
    }

    input:focus {
        border-color: var(--brass);
        outline: none;
    }

    input:user-invalid {
        border-color: var(--danger);
    }

    .race input {
        text-align: center;
    }

    .hint {
        margin: 0;
        color: var(--ivory-dim);
        font-size: 0.9375rem;
    }

    .start {
        margin-top: 0.5rem;
        min-height: 3.75rem;
        font-size: 1.25rem;
    }

    .visually-hidden {
        position: absolute;
        width: 1px;
        height: 1px;
        overflow: hidden;
        clip-path: inset(50%);
        white-space: nowrap;
    }
</style>
