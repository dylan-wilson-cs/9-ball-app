export type Player = 0 | 1;
export type BallState = "available" | "sunk" | "dead";

export interface BallColors {
    [key: number]: string;
}

export const BALL_COLORS: BallColors = {
    1: "#F5C211", // Yellow
    2: "#1E4FB5", // Blue
    3: "#D7262C", // Red
    4: "#5B2A86", // Purple
    5: "#F07A1A", // Orange
    6: "#13804A", // Green
    7: "#7A1E22", // Maroon
    8: "#151515", // Black
    9: "#F5C211", // Yellow stripe
};

export function getNextBallState(
    currentState: BallState,
    isBall9: boolean,
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
