<script lang="ts">
    interface Props {
        onStartGame: (player1: string, player2: string, raceTo: number) => void;
    }

    let { onStartGame }: Props = $props();

    let player1 = $state("John");
    let player2 = $state("Doe");
    let raceTo = $state(25);

    let onsubmit = (e: Event) => {
        e.preventDefault();
        onStartGame(player1, player2, raceTo);
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
        <label for="raceTo" class="fs-2 form-label">Race to</label>
        <input
            type="number"
            class="form-control fs-3"
            id="raceTo"
            bind:value={raceTo}
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
