<script lang="ts">
    import type { Player } from "$lib/match";

    // The fields are bound to the match's players, so the last names and
    // race targets are still filled in after a match ends
    interface Props {
        players: [Player, Player];
        onStart: () => void;
    }

    let { players = $bindable(), onStart }: Props = $props();

    function onsubmit(event: SubmitEvent) {
        event.preventDefault();
        onStart();
    }
</script>

<form class="d-flex flex-column gap-3" {onsubmit}>
    {#each players as player, i}
        <fieldset class="card">
            <div class="card-body">
                <legend class="h5 fw-bold mb-2">Player {i + 1}</legend>
                <div class="row g-2">
                    <div class="col-8">
                        <label for="name{i}" class="form-label small mb-1"
                            >Name</label
                        >
                        <!-- At least one non-space character -->
                        <input
                            type="text"
                            class="form-control form-control-lg"
                            id="name{i}"
                            bind:value={player.name}
                            pattern=".*\S.*"
                            title="Enter a name"
                            autocomplete="off"
                            required
                        />
                    </div>
                    <div class="col-4">
                        <label for="raceTo{i}" class="form-label small mb-1"
                            >Races to</label
                        >
                        <input
                            type="number"
                            inputmode="numeric"
                            class="form-control form-control-lg"
                            id="raceTo{i}"
                            bind:value={player.raceTo}
                            min="14"
                            max="100"
                            required
                        />
                    </div>
                </div>
            </div>
        </fieldset>
    {/each}
    <button type="submit" class="btn btn-felt btn-lg w-100">Start Game</button>
</form>
