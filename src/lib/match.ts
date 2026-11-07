export type PlayerIndex = 0 | 1;
export type BallState = "available" | "sunk" | "dead";

// A made or dead ball records whose turn it was
export type RackBall =
    { state: "available" } | { state: "sunk" | "dead"; by: PlayerIndex };

export interface Player {
    name: string;
    raceTo: number;
    score: number;
}

export interface Rack {
    balls: RackBall[];
    breaker: PlayerIndex;
    // Innings follow the APA rule: an inning ends when the breaker and
    // their opponent have each had a turn
    inning: number;
}

export interface Match {
    isStarted: boolean;
    players: [Player, Player];
    currentPlayer: PlayerIndex;
    rack: Rack;
    // Dead balls and innings from completed racks
    deadCarry: number;
    inningCarry: number;
}

export function newRack(breaker: PlayerIndex): Rack {
    return {
        balls: Array.from({ length: 9 }, () => ({ state: "available" })),
        breaker,
        inning: 1,
    };
}

export function newMatch(): Match {
    return {
        isStarted: false,
        players: [
            { name: "John", raceTo: 25, score: 0 },
            { name: "Doe", raceTo: 25, score: 0 },
        ],
        currentPlayer: 0,
        rack: newRack(0),
        deadCarry: 0,
        inningCarry: 0,
    };
}

// Bump the key if the saved shape changes incompatibly. Only this app
// writes the key, so a save under it is trusted to have this shape.
export const STORAGE_KEY = "nine-ball-match-v2";

// Storage can be unavailable or throw (private browsing, blocked site data,
// full quota). In those cases the app keeps working without persistence.
export function loadMatch(): Match | null {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        return raw ? (JSON.parse(raw) as Match) : null;
    } catch {
        return null;
    }
}

export function saveMatch(match: Match): void {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(match));
    } catch {
        // Persistence is best-effort
    }
}
