import type { BallState, Player } from "$lib/types/game";

// Bump the key if the saved shape changes incompatibly, so old saves are
// ignored instead of loading as a broken match.
export const STORAGE_KEY = "nine-ball-match-v1";

export interface SavedMatch {
    isStarted: boolean;
    player1: string;
    player2: string;
    raceTo1: number;
    raceTo2: number;
    currentPlayer: Player;
    score1: number;
    score2: number;
    ballStates: BallState[];
    ballScorer: (Player | null)[];
    deadCarry: number;
    rackBreaker: Player;
    rackInning: number;
    inningCarry: number;
}

// Saves made before inning tracking existed lack these fields. They load
// with the inning count starting fresh instead of being discarded.
const INNING_DEFAULTS = { rackInning: 1, inningCarry: 0 } as const;

const BALL_STATES: readonly string[] = ["available", "sunk", "dead"];

function isNumber(value: unknown): value is number {
    return typeof value === "number" && Number.isFinite(value);
}

function isPlayer(value: unknown): value is Player {
    return value === 0 || value === 1;
}

type StoredMatch = Omit<SavedMatch, keyof typeof INNING_DEFAULTS | "rackBreaker"> &
    Partial<Pick<SavedMatch, keyof typeof INNING_DEFAULTS | "rackBreaker">>;

function isStoredMatch(value: unknown): value is StoredMatch {
    if (typeof value !== "object" || value === null) return false;
    const m = value as Record<string, unknown>;
    return (
        typeof m.isStarted === "boolean" &&
        typeof m.player1 === "string" &&
        typeof m.player2 === "string" &&
        isNumber(m.raceTo1) &&
        isNumber(m.raceTo2) &&
        isPlayer(m.currentPlayer) &&
        isNumber(m.score1) &&
        isNumber(m.score2) &&
        isNumber(m.deadCarry) &&
        Array.isArray(m.ballStates) &&
        m.ballStates.length === 9 &&
        m.ballStates.every((s) => BALL_STATES.includes(s as string)) &&
        Array.isArray(m.ballScorer) &&
        m.ballScorer.length === 9 &&
        m.ballScorer.every((p) => p === null || isPlayer(p)) &&
        (m.rackBreaker === undefined || isPlayer(m.rackBreaker)) &&
        (m.rackInning === undefined || isNumber(m.rackInning)) &&
        (m.inningCarry === undefined || isNumber(m.inningCarry))
    );
}

// Storage can be unavailable or throw (private browsing, blocked site data,
// full quota). In those cases the app keeps working without persistence.
export function loadMatch(): SavedMatch | null {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return null;
        const parsed: unknown = JSON.parse(raw);
        if (!isStoredMatch(parsed)) return null;
        return {
            ...INNING_DEFAULTS,
            rackBreaker: parsed.currentPlayer,
            ...parsed,
        };
    } catch {
        return null;
    }
}

export function saveMatch(match: SavedMatch): void {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(match));
    } catch {
        // Ignore: persistence is best-effort.
    }
}
