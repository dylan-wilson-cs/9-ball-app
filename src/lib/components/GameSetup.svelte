<script lang="ts">
    interface Props {
        onStartGame: (
            player1: string,
            player2: string,
            raceTo1: number,
            raceTo2: number
        ) => void;
    }

    let { onStartGame }: Props = $props();

    let player1 = $state("John");
    let player2 = $state("Doe");
    let raceTo1 = $state(25);
    let raceTo2 = $state(25);

    let onsubmit = (e: Event) => {
        e.preventDefault();
        onStartGame(player1.trim(), player2.trim(), raceTo1, raceTo2);
    };

    const MIN_RACE = 14;
    const MAX_RACE = 100;
    // At least one non-space character, so a name can't be blank
    const NAME_PATTERN = ".*\\S.*";
</script>

<form class="row g-3" {onsubmit}>
    <div>
        <label for="player1" class="fs-2 form-label">Player 1</label>
        <input
            type="text"
            class="form-control fs-3"
            id="player1"
            bind:value={player1}
            pattern={NAME_PATTERN}
            title="Enter a name"
            required
        />
    </div>
    <div>
        <label for="player2" class="fs-2 form-label">Player 2</label>
        <input
            type="text"
            class="form-control fs-3"
            id="player2"
            bind:value={player2}
            pattern={NAME_PATTERN}
            title="Enter a name"
            required
        />
    </div>
    <div>
        <label for="raceTo1" class="fs-2 form-label">{player1.trim() || "Player 1"} races to</label>
        <input
            type="number"
            class="form-control fs-3"
            id="raceTo1"
            bind:value={raceTo1}
            min={MIN_RACE}
            max={MAX_RACE}
            required
        />
    </div>
    <div>
        <label for="raceTo2" class="fs-2 form-label">{player2.trim() || "Player 2"} races to</label>
        <input
            type="number"
            class="form-control fs-3"
            id="raceTo2"
            bind:value={raceTo2}
            min={MIN_RACE}
            max={MAX_RACE}
            required
        />
    </div>
    <div class="col d-flex justify-content-center">
        <button type="submit" class="btn btn-primary btn-lg w-75">
            Start Game
        </button>
    </div>
</form>
