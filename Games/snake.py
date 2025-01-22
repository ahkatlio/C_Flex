import curses
import random
import time
from enum import Enum
import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich import box
from rich.align import Align

BANNER = """
[bold cyan]
███████╗███╗   ██╗ █████╗ ██╗  ██╗███████╗     ██████╗  █████╗ ███╗   ███╗███████╗
██╔════╝████╗  ██║██╔══██╗██║ ██╔╝██╔════╝    ██╔════╝ ██╔══██╗████╗ ████║██╔════╝
███████╗██╔██╗ ██║███████║█████╔╝ █████╗      ██║  ███╗███████║██╔████╔██║█████╗  
╚════██║██║╚██╗██║██╔══██║██╔═██╗ ██╔══╝      ██║   ██║██╔══██║██║╚██╔╝██║██╔══╝  
███████║██║ ╚████║██║  ██║██║  ██╗███████╗    ╚██████╔╝██║  ██║██║ ╚═╝ ██║███████╗
╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝     ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝
[/bold cyan]"""

def show_welcome_screen():
    """Show welcome screen with banner"""
    if sys.platform == 'win32':
        os.system('cls')
    else:
        os.system('clear')
        
    console = Console()
    console.print(Panel(
        Align.center(BANNER),
        title="[bold yellow]Welcome to Snake Game[/bold yellow]",
        subtitle="[dim]Press Enter to start...[/dim]",
        border_style="cyan",
        padding=(1, 2),
        box=box.DOUBLE
    ))
    
    console.print("\n[bold green]Press Enter to start the game...[/bold green]")
    input()
    
    if sys.platform == 'win32':
        os.system('cls')
    else:
        os.system('clear')

class Direction(Enum):
    UP = 1
    DOWN = 2
    LEFT = 3
    RIGHT = 4

class FoodType(Enum):
    NORMAL = 1
    SPEED = 2
    BONUS = 3
    SLOW = 4

class SnakeGame:
    MIN_HEIGHT = 20
    MIN_WIDTH = 60

    def __init__(self):
        self.score = 0
        self.speed = 0.1
        self.snake_body = [(10, 10)]
        self.direction = Direction.RIGHT
        self.food = None
        self.food_type = FoodType.NORMAL
        self.game_over = False
        self.effects = []
        self.powerups = []
        self.level = 1
        
    def safe_addstr(self, stdscr, y, x, string, attr=0):
        """Safe string drawing that handles boundary errors"""
        if not hasattr(stdscr, 'getmaxyx'):
            return
        
        height, width = stdscr.getmaxyx()
        if 0 <= y < height and 0 <= x < width and x + len(string) <= width:
            try:
                stdscr.addstr(y, x, string, attr)
            except curses.error:
                pass

    def check_terminal_size(self, stdscr):
        height, width = stdscr.getmaxyx()
        if height < self.MIN_HEIGHT or width < self.MIN_WIDTH:
            raise ValueError(f"Terminal too small. Min size: {self.MIN_WIDTH}x{self.MIN_HEIGHT}")

    def create_food(self):
        attempts = 0
        max_attempts = 100
        
        while attempts < max_attempts:
            food = (
                random.randint(2, self.height-3),
                random.randint(2, self.width-3)
            )
            if food not in self.snake_body:
                self.food = food
                self.food_type = random.choices(
                    list(FoodType),
                    weights=[0.7, 0.1, 0.1, 0.1]
                )[0]
                return True
            attempts += 1
        
        # If no position found, place food in safe location
        self.food = (self.height//2, self.width//2)
        self.food_type = FoodType.NORMAL
        return False

    def draw_fancy_border(self, stdscr):
        # Top and bottom borders
        for x in range(self.width):
            self.safe_addstr(stdscr, 0, x, "═", curses.color_pair(1))
            self.safe_addstr(stdscr, self.height-1, x, "═", curses.color_pair(1))
        
        # Side borders
        for y in range(self.height):
            self.safe_addstr(stdscr, y, 0, "║", curses.color_pair(1))
            self.safe_addstr(stdscr, y, self.width-1, "║", curses.color_pair(1))
        
        # Corners
        self.safe_addstr(stdscr, 0, 0, "╔", curses.color_pair(1))
        self.safe_addstr(stdscr, 0, self.width-1, "╗", curses.color_pair(1))
        self.safe_addstr(stdscr, self.height-1, 0, "╚", curses.color_pair(1))
        self.safe_addstr(stdscr, self.height-1, self.width-1, "╝", curses.color_pair(1))

    def draw(self, stdscr):
        stdscr.clear()
        self.draw_fancy_border(stdscr)
        
        # Draw snake
        for i, segment in enumerate(self.snake_body):
            char = "◉" if i == 0 else "●"
            try:
                y, x = segment[0], segment[1]
                self.safe_addstr(stdscr, y, x, char, curses.color_pair(2) | curses.A_BOLD)
            except:
                continue
        
        # Draw food
        if self.food:
            food_colors = {
                FoodType.NORMAL: 3,
                FoodType.SPEED: 4,
                FoodType.BONUS: 5,
                FoodType.SLOW: 6
            }
            food_chars = {
                FoodType.NORMAL: "★",
                FoodType.SPEED: "👾",
                FoodType.BONUS: "💎",
                FoodType.SLOW: "💤"
            }
            try:
                self.safe_addstr(
                    stdscr,
                    self.food[0],
                    self.food[1],
                    food_chars[self.food_type],
                    curses.color_pair(food_colors[self.food_type]) | curses.A_BOLD
                )
            except:
                pass
        
        # Draw score and level
        score_text = f" Score: {self.score} | Level: {self.level} "
        self.safe_addstr(stdscr, 0, (self.width - len(score_text))//2, score_text, 
                        curses.color_pair(7) | curses.A_BOLD)
        
        # Draw effects
        for effect in self.effects:
            self.safe_addstr(stdscr, effect['y'], effect['x'], effect['char'], 
                        curses.color_pair(effect['color']))
            
        stdscr.refresh()
        

    def move_snake(self):
        head = self.snake_body[0]
        new_head = None
        
        if self.direction == Direction.UP:
            new_head = (head[0] - 1, head[1])
        elif self.direction == Direction.DOWN:
            new_head = (head[0] + 1, head[1])
        elif self.direction == Direction.LEFT:
            new_head = (head[0], head[1] - 1)
        elif self.direction == Direction.RIGHT:
            new_head = (head[0], head[1] + 1)
            
        # Check collision with walls
        if (new_head[0] in [0, self.height-1] or 
            new_head[1] in [0, self.width-1] or 
            new_head in self.snake_body):
            self.game_over = True
            return
            
        self.snake_body.insert(0, new_head)
        
        # Check food collision
        if new_head == self.food:
            self.handle_food_collision()
        else:
            self.snake_body.pop()

    def handle_food_collision(self):
        self.score += 10 * (2 if self.food_type == FoodType.BONUS else 1)

        # Store current food location for effect
        food_x, food_y = self.food[1], self.food[0]
        food_type = self.food_type
        
        # Create new food before applying effects
        self.create_food()
        
        if self.food_type == FoodType.SPEED:
            self.speed = max(0.05, self.speed * 0.9)
        elif self.food_type == FoodType.SLOW:
            self.speed = min(0.15, self.speed * 1.1)
        
            
        # Add visual effect
        self.effects.append({
            'x': self.food[1],
            'y': self.food[0],
            'char': '✨',
            'color': 5,
            'timer': 3
        })
        
        # Level up every 100 points
        if self.score % 100 == 0:
            self.level += 1
            self.speed *= 0.9
            
        

    def cleanup(self):
        # Reset terminal state
        curses.nocbreak()
        curses.echo()
        curses.curs_set(1)

    def run(self, stdscr):
        # Setup
        curses.start_color()
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        curses.init_pair(6, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)
        
        curses.curs_set(0)
        stdscr.nodelay(1)
        self.height, self.width = stdscr.getmaxyx()
        try:
            self.check_terminal_size(stdscr)
        except ValueError as e:
            stdscr.clear()
            error_msg = str(e)
            self.safe_addstr(stdscr, self.height//2, (self.width-len(error_msg))//2, 
                            error_msg, curses.color_pair(1) | curses.A_BOLD)
            self.safe_addstr(stdscr, self.height//2+1, 
                            (self.width-len("Press 'q' to quit or resize the terminal and press any other key..."))//2,
                            "Press 'q' to quit or resize the terminal and press any other key...", 
                            curses.color_pair(7) | curses.A_BOLD)
            stdscr.refresh()
            if stdscr.getch() == ord('q'):
                return
            
        self.create_food()
        last_update = time.time()
        
        while not self.game_over:
            current_height, current_width = stdscr.getmaxyx()
            if current_height != self.height or current_width != self.width:
                self.height, self.width = current_height, current_width
                try:
                    self.check_terminal_size(stdscr)
                except ValueError:
                    continue
            
            if time.time() - last_update > self.speed:
                self.move_snake()
                last_update = time.time()
            
            # Handle input
            key = stdscr.getch()
            if key == curses.KEY_UP and self.direction != Direction.DOWN:
                self.direction = Direction.UP
            elif key == curses.KEY_DOWN and self.direction != Direction.UP:
                self.direction = Direction.DOWN
            elif key == curses.KEY_LEFT and self.direction != Direction.RIGHT:
                self.direction = Direction.LEFT
            elif key == curses.KEY_RIGHT and self.direction != Direction.LEFT:
                self.direction = Direction.RIGHT
            elif key == ord('q'):
                break
                
            # Update effects
            self.effects = [e for e in self.effects if e['timer'] > 0]
            for effect in self.effects:
                effect['timer'] -= 1
                
            self.draw(stdscr)
            
        # Game over screen
        stdscr.clear()
        game_over_text = "GAME OVER!"
        score_text = f"Final Score: {self.score}"
        self.safe_addstr(stdscr, self.height//2, (self.width-len(game_over_text))//2,
                    game_over_text, curses.color_pair(1) | curses.A_BOLD)
        self.safe_addstr(stdscr, self.height//2+1, (self.width-len(score_text))//2,
                    score_text, curses.color_pair(7) | curses.A_BOLD)
        stdscr.refresh()
        time.sleep(2)

def start_snake_game():
    """Main function to handle game flow"""
    try:
        show_welcome_screen()
        curses.wrapper(SnakeGame().run)
    finally:
        curses.endwin()
        if sys.platform == 'win32':
            os.system('cls')
        else:
            os.system('clear')

if __name__ == "__main__":
    start_snake_game()