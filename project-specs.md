# Nine Ball Score Keeper App Specification

## Core Features
- Track 9-ball pool game between 2 players
- Track score based on ball pocketing
- Race to X points format
- Responsive design for mobile/desktop

## Ball Display Requirements
- Balls displayed as colored circles with numbers 1-9
- Standard 9-ball colors:
  - 1: Yellow
  - 2: Blue
  - 3: Red
  - 4: Purple
  - 5: Orange
  - 6: Green
  - 7: Red
  - 8: Black
  - 9: Yellow
- Each ball shows its number centered in white text
- Balls show check mark (✓) above when pocketed
- Balls show X mark above when fouled
- Balls maintain consistent spacing and sizing
- Circular shape with solid fill colors
- Numbers centered in white text
- Status indicators (✓/✗) positioned above balls

## Technical Stack
- SvelteKit with TypeScript
- Svelte 5 runes for state management
- Bootstrap 5 for styling
- Vite for build/dev

## Component Structure

### 1. Main Game Container (`routes/+page.svelte`)
- Game state management
- Player switching logic
- Setup and game components

### 2. Game Setup Component (`lib/components/GameSetup.svelte`)
- Player name inputs (2 players)
- Race to points input
- Start game button
- Form validation

### 3. Game Board Component (`lib/components/GameBoard.svelte`)
- Score display
- Current player indicator
- 3x3 ball grid
- Turn end button

### 4. Ball Component (`lib/components/Ball.svelte`)
- Ball number display (1-9)
- Click handling
- Visual states (available/pocketed)

## Core State Types
```typescript
interface GameState {
  isStarted: boolean;
  players: [string, string];
  raceTo: number;
  currentPlayer: 0 | 1;
  scores: [number, number];
  ballStates: Array<'available' | 'pocketed' | 'fouled'>;
}
```

## Key Functions

### Game Setup
```typescript
function startGame(p1: string, p2: string, raceTo: number): void
function validateSetup(p1: string, p2: string, raceTo: number): boolean
```

### Game Logic
```typescript
function handleBallClick(ballNumber: number): void
function switchPlayer(): void
function updateScore(ballValue: number): void
function checkWinCondition(): boolean
function resetGame(): void
```

## Ball Component Styling
```css
.ball {
  border-radius: 50%;
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  margin: 10px;
}

.ball-number {
  color: white;
  font-size: 1.5rem;
  font-weight: bold;
}

.status-indicator {
  position: absolute;
  top: -20px;
  width: 100%;
  text-align: center;
}
```

## Ball State Visual Indicators
- Available: Full opacity
- Pocketed: Check mark above
- Fouled: X mark above
- Optional: Reduced opacity for pocketed/fouled balls

## Styling Requirements
- Bootstrap 5 responsive grid
- Mobile-first design
- Touch-friendly ball targets (minimum 44px)
- Clear visual hierarchy
- Distinct player turn indicators

## Development Phases
1. Player setup screen
2. Ball grid implementation
3. Score tracking system
4. Turn management
5. Win condition logic
6. Polish and responsive design

## User Interface Flow
1. Enter player names and race to points
2. Click balls to mark as pocketed
3. End turn button switches players
4. Auto-switch on 9-ball pocket
5. First to target score wins
6. Option to reset/start new game

## Error Handling
- Invalid player names
- Invalid race to points value
- Invalid ball selection order
- Prevent double-scoring

## Mobile Considerations
- Full-width inputs on small screens
- Large touch targets for balls
- Clear score visibility
- Compact layout for small devices