import random
import curses
import time
import winsound
from rich.console import Console
from rich.panel import Panel
from rich import box
from rich.align import Align
from rich.text import Text
import os
import sys

console = Console()

BANNER = """
[bold cyan]
███████╗ ██████╗ ███╗   ██╗██╗    ██╗ █████╗ ██╗   ██╗███████╗
██╔════╝██╔═══██╗████╗  ██║██║    ██║██╔══██╗╚██╗ ██╔╝██╔════╝
██║     ██║   ██║██╔██╗ ██║██║ █╗ ██║███████║ ╚████╔╝ ███████╗
██║     ██║   ██║██║╚██╗██║██║███╗██║██╔══██║  ╚██╔╝  ╚════██║
╚██████╗╚██████╔╝██║ ╚████║╚███╔███╔╝██║  ██║   ██║   ███████║
 ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝ ╚══╝╚══╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝

 ██████╗  █████╗ ███╗   ███╗███████╗     ██████╗ ███████╗    
██╔════╝ ██╔══██╗████╗ ████║██╔════╝    ██╔═══██╗██╔════╝    
██║  ███╗███████║██╔████╔██║█████╗      ██║   ██║█████╗      
██║   ██║██╔══██║██║╚██╔╝██║██╔══╝      ██║   ██║██╔══╝      
╚██████╔╝██║  ██║██║ ╚═╝ ██║███████╗    ╚██████╔╝██║         
 ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝     ╚═════╝ ╚═╝         

██╗     ██╗███████╗███████╗
██║     ██║██╔════╝██╔════╝
██║     ██║█████╗  █████╗  
██║     ██║██╔══╝  ██╔══╝  
███████╗██║██║     ███████╗
╚══════╝╚═╝╚═╝     ╚══════╝
[/bold cyan]"""

# Unicode box drawing characters
BOX_CHARS = {
    'top_left': '╔', 'top_right': '╗', 'bottom_left': '╚', 'bottom_right': '╝',
    'horizontal': '═', 'vertical': '║', 'cell': '█'
}

def show_welcome_screen():
    """Show welcome screen once with proper clearing"""
    # Clear screen based on OS
    if sys.platform == 'win32':
        os.system('cls')
    else:
        os.system('clear')
        
    # Show banner once
    console = Console()
    console.print(Panel(
        Align.center(BANNER),
        title="[bold yellow]Conway's Game of Life[/bold yellow]",
        subtitle="[dim]Press Enter to start...[/dim]",
        border_style="cyan",
        padding=(1, 2),
        box=box.DOUBLE
    ))
    
    # Wait for input and clear
    console.print("\n[bold green]Press Enter to start the game...[/bold green]")
    input()
    
    # Final clear before game starts
    if sys.platform == 'win32':
        os.system('cls')
    else:
        os.system('clear')

class LifeBoard:
    def __init__(self, scr, char=ord('█')):
        self.state = {}
        self.generation = 0
        self.cell_age = {}
        self.scr = scr
        self.setup_screen()
        
    def setup_screen(self):
        Y, X = self.scr.getmaxyx()
        self.X, self.Y = X - 15, Y - 4  # Leave space for menu and borders
        self.char = ord('█')
        self.scr.clear()
        self.draw_borders()
        
    def draw_borders(self):
        try:
            border_top = BOX_CHARS['top_left'] + (self.X * BOX_CHARS['horizontal']) + BOX_CHARS['top_right']
            border_bottom = BOX_CHARS['bottom_left'] + (self.X * BOX_CHARS['horizontal']) + BOX_CHARS['bottom_right']
            self.scr.attron(curses.color_pair(3))  # Use yellow color pair
            self.scr.addstr(0, 0, border_top)
            self.scr.addstr(self.Y + 1, 0, border_bottom)
            for y in range(self.Y):
                self.scr.addstr(1 + y, 0, BOX_CHARS['vertical'])
                self.scr.addstr(1 + y, self.X + 1, BOX_CHARS['vertical'])
            self.scr.attroff(curses.color_pair(3))  # Turn off yellow color pair
            self.scr.refresh()
        except curses.error:
            pass

    def set(self, y, x):
        if x < 0 or self.X <= x or y < 0 or self.Y <= y:
            return  # Silently ignore out-of-bounds
        self.state[x, y] = 1
        self.cell_age[x, y] = 0

    def toggle(self, y, x):
        try:
            if x < 0 or self.X <= x or y < 0 or self.Y <= y:
                return
            if (x, y) in self.state:
                del self.state[x, y]
                del self.cell_age[x, y]
                self.scr.addch(y + 1, x + 1, ' ')
            else:
                self.state[x, y] = 1
                self.cell_age[x, y] = 0
                if curses.has_colors():
                    color = self._get_color_pair(0)
                    self.scr.attrset(color)
                self.scr.addch(y + 1, x + 1, self.char)
                self.scr.attrset(0)
                winsound.Beep(440, 50)
            self.scr.refresh()
        except curses.error:
            pass

    def _get_color_pair(self, age):
        colors = [
            curses.COLOR_CYAN,
            curses.COLOR_BLUE,
            curses.COLOR_GREEN,
            curses.COLOR_YELLOW,
            curses.COLOR_MAGENTA,
            curses.COLOR_RED
        ]
        index = min(age // 2, len(colors) - 1)
        return curses.color_pair(index + 1)

    def erase(self):
        self.state = {}
        self.cell_age = {}
        self.generation = 0
        self.display(update_board=False)

    def display(self, update_board=True):
        try:
            if not update_board:
                for i in range(self.X):
                    for j in range(self.Y):
                        ch = self.char if (i, j) in self.state else ' '
                        self.scr.addch(j + 1, i + 1, ch)
                self.scr.refresh()
                return

            new_state = {}
            new_age = {}
            for i in range(self.X):
                for j in range(self.Y):
                    neighbors = self._count_neighbors(i, j)
                    was_alive = (i, j) in self.state
                    
                    if neighbors == 3 or (was_alive and neighbors == 2):
                        new_state[i, j] = 1
                        new_age[i, j] = self.cell_age.get((i, j), 0) + 1
                        if curses.has_colors():
                            color = self._get_color_pair(new_age[i, j])
                            self.scr.attrset(color)
                        self.scr.addch(j + 1, i + 1, self.char)
                        self.scr.attrset(0)
                    elif was_alive:
                        self.scr.addch(j + 1, i + 1, ' ')

            self.state = new_state
            self.cell_age = new_age
            self.generation += 1
            self.scr.refresh()
        except curses.error:
            pass

    def _count_neighbors(self, x, y):
        count = 0
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                if (x + dx, y + dy) in self.state:
                    count += 1
        return count

    def makeRandom(self):
        self.state = {}
        self.cell_age = {}
        for i in range(self.X):
            for j in range(self.Y):
                if random.random() > 0.5:
                    self.set(j, i)
        self.generation = 0

def display_menu(stdscr, menu_y):
    try:
        height, width = stdscr.getmaxyx()
        menu_x = width - 14
        
        menu_items = [
            ("🎮 Controls", curses.color_pair(1)),
            ("↑↓←→ Move", curses.color_pair(2)),
            ("Space:Set", curses.color_pair(3)),
            ("──────", curses.color_pair(7)),
            ("E:Clear", curses.color_pair(4)),
            ("R:Random", curses.color_pair(5)),
            ("S:Step", curses.color_pair(6)),
            ("C:Run", curses.color_pair(2)),
            ("Q:Quit", curses.color_pair(1))
        ]
        
        for i, (text, color) in enumerate(menu_items):
            if menu_y + i < height - 1:
                stdscr.attron(color)
                stdscr.addstr(menu_y + i, menu_x, text[:10])
                stdscr.attroff(color)
    except curses.error:
        pass

def keyloop(stdscr):
    curses.start_color()
    curses.use_default_colors()
    
    # Initialize color pairs
    for i in range(1, 8):
        curses.init_pair(i, i, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Initialize yellow color pair
    
    curses.curs_set(1)  # Show cursor initially
    stdscr.timeout(100) # Set getch() non-blocking
    
    while True:
        try:
            height, width = stdscr.getmaxyx()
            menu_y = 2
            
            # Adjust board dimensions to account for borders
            board_height = height - 4
            board_width = width - 15
            subwin = stdscr.subwin(board_height, board_width, 2, 2)
            board = LifeBoard(subwin)
            
            display_menu(stdscr, menu_y)
            board.display(update_board=False)
            
            # Initialize cursor position
            xpos, ypos = board.X // 2, board.Y // 2
            
            while True:
                try:
                    # Correct cursor position to account for board borders
                    stdscr.move(ypos + 2, xpos + 2)  # +2 for border offset
                    c = stdscr.getch()
                    
                    if c == curses.KEY_RESIZE:
                        break
                        
                    if 0 < c < 256:
                        c = chr(c)
                        if c in ' \n':
                            board.toggle(ypos, xpos)  # Use actual grid coordinates
                        elif c in 'Cc':
                            curses.curs_set(0)
                            stdscr.nodelay(1)
                            while True:
                                if stdscr.getch() != -1:
                                    break
                                board.display()
                            stdscr.nodelay(0)
                            curses.curs_set(1)
                            display_menu(stdscr, menu_y)
                        elif c in 'Ee':
                            board.erase()
                        elif c in 'Qq':
                            return
                        elif c in 'Rr':
                            board.makeRandom()
                            board.display(update_board=False)
                        elif c in 'Ss':
                            board.display()
                    elif c == curses.KEY_UP and ypos > 0:
                        ypos -= 1
                    elif c == curses.KEY_DOWN and ypos < board.Y - 1:
                        ypos += 1
                    elif c == curses.KEY_LEFT and xpos > 0:
                        xpos -= 1
                    elif c == curses.KEY_RIGHT and xpos < board.X - 1:
                        xpos += 1
                    
                    
                except curses.error:
                    continue
                    
        except (curses.error, ValueError):
            continue

def start_game_of_life():
    """Main function to handle game flow"""
    try:
        # Show welcome screen before initializing curses
        show_welcome_screen()
        
        # Initialize curses after welcome screen
        curses.wrapper(game_loop)
    except KeyboardInterrupt:
        console.print("[bold red]Game terminated by user[/bold red]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
    finally:
        # Ensure terminal is reset
        if sys.platform == 'win32':
            os.system('cls')
        else:
            os.system('clear')

def game_loop(stdscr):
    """Main game loop with curses"""
    # Initialize colors
    curses.start_color()
    curses.use_default_colors()
    for i in range(1, 8):
        curses.init_pair(i, i, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Initialize yellow color pair
    
    # Show cursor and set timeout
    curses.curs_set(1)
    stdscr.timeout(100)
    
    try:
        keyloop(stdscr)
    finally:
        curses.endwin()


if __name__ == '__main__':
    start_game_of_life()