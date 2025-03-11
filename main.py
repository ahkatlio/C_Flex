import curses
import os
import sys
import subprocess
from time import sleep
from Flex.AudioPlayer import run_music_player
from Flex.Load import matrix_animation
from Wifi_Scan.wifi_scan import start_wifi_scan
from Game_Of_Life.Conways_Game_of_Life import start_game_of_life
from AI.chat import chat as start_ai_chat
from Flex.markdown_preview_app import main as start_markdown_preview

# Global variables
FIRST_RUN = True

def initialize_colors():
    """Initialize color pairs to match markdown reader style"""
    curses.start_color()
    curses.use_default_colors()
    
    # Match the colors from markdown_preview_app.py
    curses.init_pair(1, curses.COLOR_WHITE, 236)      # Normal text (dark gray background)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Selected item
    curses.init_pair(3, curses.COLOR_WHITE, 236)      # Background
    curses.init_pair(4, curses.COLOR_CYAN, 236)       # Title/header text
    curses.init_pair(5, curses.COLOR_GREEN, 236)      # Success messages
    curses.init_pair(6, curses.COLOR_RED, 236)        # Error messages
    curses.init_pair(7, curses.COLOR_CYAN, 236)       # Info messages

def draw_title(win, title, y=1):
    """Draw centered title with styling matching markdown reader"""
    height, width = win.getmaxyx()
    x = (width - len(title)) // 2
    win.attron(curses.color_pair(4) | curses.A_BOLD)
    win.addstr(y, x, title)
    win.attroff(curses.color_pair(4) | curses.A_BOLD)

def draw_loading_animation(win, text):
    """Show a loading animation with markdown reader styling"""
    height, width = win.getmaxyx()
    x = (width - len(text) - 3) // 2
    y = height // 2
    
    win.clear()
    win.bkgd(' ', curses.color_pair(3))  # Set background
    win.box()
    
    for i in range(3):
        win.attron(curses.color_pair(7))
        win.addstr(y, x, f"{text}{'.' * (i+1)}")
        win.attroff(curses.color_pair(7))
        win.refresh()
        sleep(0.3)
        if i < 2:
            win.addstr(y, x, " " * (len(text) + 3))

def clean_terminal():
    """Clean terminal between program switches"""
    if sys.platform == 'win32':
        os.system('cls')
    else:
        os.system('clear')

def run_program(stdscr, program_name, func):
    """Run a program with proper terminal cleanup"""
    try:
        # Properly end curses before running the program
        curses.endwin()
        clean_terminal()
        
        # Run the selected program
        func()
    finally:
        # Properly reinitialize curses when returning
        stdscr = curses.initscr()
        curses.start_color()
        curses.noecho()
        curses.cbreak()
        stdscr.keypad(True)
        
        # Re-initialize colors
        initialize_colors()
        
        # Show returning animation
        draw_loading_animation(stdscr, "Returning to main menu")
        
        # Return the properly initialized screen
        return stdscr

def draw_menu(win, menu_items, selected_idx):
    """Draw the menu with styling matching markdown reader"""
    height, width = win.getmaxyx()
    
    # Set background color for whole window
    win.bkgd(' ', curses.color_pair(3))
    
    # Draw border
    win.attron(curses.color_pair(1))
    win.box()
    win.attroff(curses.color_pair(1))
    
    # Calculate visible items
    max_items = height - 4  # Leave space for title and instructions
    start_y = 2  # Start after title
    
    # Draw each menu item - similar to markdown reader
    for i, item in enumerate(menu_items):
        if i >= max_items:
            break
            
        y = start_y + i
        
        if i == selected_idx:
            win.attron(curses.color_pair(2))
            win.addstr(y, 1, item[:width-2].ljust(width-2))
            win.attroff(curses.color_pair(2))
        else:
            win.attron(curses.color_pair(1))
            win.addstr(y, 1, item)
            win.attroff(curses.color_pair(1))
    
    # Draw instructions at bottom
    instructions = "↑/↓: Navigate | Enter: Select | Q: Quit"
    win.attron(curses.color_pair(1))
    win.addstr(height-1, (width - len(instructions)) // 2, instructions)
    win.attroff(curses.color_pair(1))

def main(stdscr):
    global FIRST_RUN
    
    # Setup
    curses.curs_set(0)  # Hide cursor
    initialize_colors()
    stdscr.clear()
    
    # Define menu items with emoji indicators like in markdown reader
    menu_items = [
        "🎵 Music Player",  
        "📄 PDF Downloader",
        "📺 YouTube Downloader",
        "🤖 AI Chat",
        "🔍 AI Math Solver",
        "🪟 Windows Utilizer", 
        "📶 Wi-Fi Scanner",  
        "🎮 Game of Life", 
        "🐍 Snake Game",
        "📝 Markdown Previewer",
        "🚪 Exit"
    ]
    
    selected_idx = 0
    offset = 0
    
    # Run the matrix animation only once
    if FIRST_RUN:
        curses.endwin()
        matrix_animation()
        FIRST_RUN = False
        # Restore curses after matrix animation
        stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        stdscr.keypad(True)
        initialize_colors()
    
    # Main menu loop
    while True:
        # Get window dimensions
        height, width = stdscr.getmaxyx()
        
        # Draw the frame
        stdscr.clear()
        stdscr.bkgd(' ', curses.color_pair(3))  # Set background to match markdown reader
        
        # Draw border and title
        draw_title(stdscr, "🔥 Welcome to Chilli Flex! 🔥")
        draw_menu(stdscr, menu_items, selected_idx)
        
        # Update the screen
        stdscr.refresh()
        
        # Get user input
        key = stdscr.getch()
        
        if key == curses.KEY_UP and selected_idx > 0:
            selected_idx -= 1
        elif key == curses.KEY_DOWN and selected_idx < len(menu_items) - 1:
            selected_idx += 1
        elif key == ord('\n') or key == ord(' '):  # Enter or Space
            option = menu_items[selected_idx]
            
            if "Exit" in option:
                break
                
            # Show loading animation
            draw_loading_animation(stdscr, f"Loading {option.split(' ')[0].strip()}")
            
            # Launch the selected program
            try:
                if "Music Player" in option:
                    stdscr = run_program(stdscr, "Music Player", run_music_player)
                elif "PDF Downloader" in option:
                    stdscr = run_program(stdscr, "PDF Downloader", lambda: os.system('python Downloader/pdf.py'))
                elif "YouTube Downloader" in option:
                    stdscr = run_program(stdscr, "YouTube Downloader", lambda: os.system('python Downloader/youtube.py'))
                elif "AI Chat" in option:
                    stdscr = run_program(stdscr, "AI Chat", start_ai_chat)
                elif "AI Math Solver" in option:
                    stdscr = run_program(stdscr, "AI Math Solver", lambda: os.system('python AI/AI_Math_Solver.py'))
                elif "Windows Utilizer" in option:
                    stdscr = run_program(stdscr, "Windows Utilizer", lambda: subprocess.run(['elevate.bat'], shell=True))
                elif "Wi-Fi Scanner" in option:
                    stdscr = run_program(stdscr, "Wi-Fi Scanner", start_wifi_scan)
                elif "Game of Life" in option:
                    stdscr = run_program(stdscr, "Game of Life", start_game_of_life)
                elif "Snake Game" in option:
                    stdscr = run_program(stdscr, "Snake Game", lambda: os.system('python Games/snake.py'))
                elif "Markdown Previewer" in option:
                    stdscr = run_program(stdscr, "Markdown Previewer", start_markdown_preview)
            except KeyboardInterrupt:
                # Reinitialize if interrupted
                stdscr = curses.initscr()
                curses.curs_set(0)
                initialize_colors()
        elif key == ord('q') or key == ord('Q'):
            break
        
        # Adjust offset for scrolling if needed
        if selected_idx < offset:
            offset = selected_idx
        elif selected_idx >= offset + (height - 6):
            offset = selected_idx - (height - 6) + 1
    
    # Show exit message
    stdscr.clear()
    stdscr.bkgd(' ', curses.color_pair(3))
    stdscr.box()
    goodbye_msg = "👋 Thanks for using Chilli Flex! 👋"
    stdscr.attron(curses.color_pair(5) | curses.A_BOLD)
    stdscr.addstr(height//2, (width - len(goodbye_msg))//2, goodbye_msg)
    stdscr.attroff(curses.color_pair(5) | curses.A_BOLD)
    stdscr.refresh()
    sleep(2)

if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        clean_terminal()
        sys.exit(0)