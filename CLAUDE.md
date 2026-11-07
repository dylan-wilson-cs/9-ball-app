# 9-ball-app

A single-page SvelteKit app (Svelte 5 runes, TypeScript, Bootstrap 5) that keeps score for an APA-style 9-ball match between two players on one phone.

## Commands

- `npm run dev` starts the dev server.
- `npm run check` runs svelte-check. It must report 0 errors and 0 warnings.
- `npm run build` builds the app.

## Files

- `src/routes/+page.svelte` holds all match state and scoring logic.
- `src/lib/components/GameSetup.svelte` is the setup form: two names and a race target per player, 14 to 100.
- `src/lib/components/Ball.svelte` draws one tappable ball.
- `src/lib/storage.ts` saves the match to localStorage. Bump `STORAGE_KEY` if the saved shape changes incompatibly.

## Scoring rules

- Balls 1 to 8 score 1 point and the 9 scores 2. The first player to reach their own race target wins.
- Tapping a ball cycles on table, made, dead. The 9 only toggles between on table and made, and needs a confirmation.
- Making the 9 ends the rack. Balls left on the table count as dead, and the player who made the 9 breaks the next rack.
- Dead balls are one shared match total.
- Each made or dead ball records whose turn it was. The opponent cannot change it during the same rack. Un-making a ball takes the points back from the player who made it.
- An inning ends when both the rack's breaker and the opponent have had a turn.
- After a win, balls can only be un-made and End Turn is disabled.
- "Undo 9-ball" restores the match from before the last 9 until the next ball tap or End Turn.
- Open tabs follow each other's saves through the `storage` event.

## Testing

Test in a browser at phone width (about 400px). There are no automated tests.
