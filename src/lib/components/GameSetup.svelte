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

{#snippet playerFields(
    n: 1 | 2,
    name: string,
    setName: (value: string) => void,
    race: number,
    setRace: (value: number) => void,
)}
    <fieldset class="card">
        <div class="card-body">
            <legend class="h5 fw-bold mb-2">Player {n}</legend>
            <div class="row g-2">
                <div class="col-8">
                    <label for="player{n}" class="form-label small mb-1"
                        >Name</label
                    >
                    <input
                        type="text"
                        class="form-control form-control-lg"
                        id="player{n}"
                        bind:value={() => name, setName}
                        pattern={NAME_PATTERN}
                        title="Enter a name"
                        autocomplete="off"
                        required
                    />
                </div>
                <div class="col-4">
                    <label for="raceTo{n}" class="form-label small mb-1"
                        >Races to</label
                    >
                    <input
                        type="number"
                        inputmode="numeric"
                        class="form-control form-control-lg"
                        id="raceTo{n}"
                        bind:value={() => race, setRace}
                        min={MIN_RACE}
                        max={MAX_RACE}
                        required
                    />
                </div>
            </div>
        </div>
    </fieldset>
{/snippet}

<form class="d-flex flex-column gap-3" {onsubmit}>
    {@render playerFields(
        1,
        player1,
        (v) => (player1 = v),
        raceTo1,
        (v) => (raceTo1 = v),
    )}
    {@render playerFields(
        2,
        player2,
        (v) => (player2 = v),
        raceTo2,
        (v) => (raceTo2 = v),
    )}
    <button type="submit" class="btn btn-felt btn-lg w-100">Start Game</button>
</form>
