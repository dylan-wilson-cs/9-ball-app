export type Player = 0 | 1;
export type BallState = "available" | "sunk" | "dead";

export interface GameState {
    isStarted: boolean;
    players: [string, string];
    raceTo: number;
    currentPlayer: Player;
    scores: [number, number];
    ballStates: BallState[];
}

export interface BallColors {
    [key: number]: string;
}

export const BALL_COLORS: BallColors = {
    1: "#FFFF00", // Yellow
    2: "#0000FF", // Blue
    3: "#FF0000", // Red
    4: "#800080", // Purple
    5: "#FFA500", // Orange
    6: "#008000", // Green
    7: "#FF0000", // Red
    8: "#000000", // Black
    9: "#FFFF00", // Yellow
};

export const NINE_BALL_INDEX = 8;
export const NINE_BALL_POINTS = 2;
export const REGULAR_BALL_POINTS = 1;

export function getNextBallState(
    currentState: BallState,
    isBall9: boolean
): BallState {
    if (isBall9) {
        return currentState === "available" ? "sunk" : "available";
    }

    switch (currentState) {
        case "available":
            return "sunk";
        case "sunk":
            return "dead";
        case "dead":
            return "available";
    }
}
