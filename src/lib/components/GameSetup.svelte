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
        onStartGame(player1, player2, raceTo1, raceTo2);
    };
</script>

<form class="row g-3" {onsubmit}>
    <div>
        <label for="player1" class="fs-2 form-label">Player 1</label>
        <input
            type="text"
            class="form-control fs-3"
            id="player1"
            bind:value={player1}
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
            required
        />
    </div>
    <div>
        <label for="raceTo1" class="fs-2 form-label">{player1 || "Player 1"} races to</label>
        <input
            type="number"
            class="form-control fs-3"
            id="raceTo1"
            bind:value={raceTo1}
            min="1"
            required
        />
    </div>
    <div>
        <label for="raceTo2" class="fs-2 form-label">{player2 || "Player 2"} races to</label>
        <input
            type="number"
            class="form-control fs-3"
            id="raceTo2"
            bind:value={raceTo2}
            min="1"
            required
        />
    </div>
    <div class="col d-flex justify-content-center">
        <button type="submit" class="btn btn-primary btn-lg w-75">
            Start Game
        </button>
    </div>
</form>
