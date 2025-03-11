import curses
import os
import signal
import sys
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.theme import Theme
from rich.align import Align
from rich import box

# Create banner for markdown previewer
BANNER = """
[bold blue]
███╗   ███╗ █████╗ ██████╗ ██╗  ██╗██████╗  ██████╗ ██╗    ██╗███╗   ██╗
████╗ ████║██╔══██╗██╔══██╗██║ ██╔╝██╔══██╗██╔═══██╗██║    ██║████╗  ██║
██╔████╔██║███████║██████╔╝█████╔╝ ██║  ██║██║   ██║██║ █╗ ██║██╔██╗ ██║
██║╚██╔╝██║██╔══██║██╔══██╗██╔═██╗ ██║  ██║██║   ██║██║███╗██║██║╚██╗██║
██║ ╚═╝ ██║██║  ██║██║  ██║██║  ██╗██████╔╝╚██████╔╝╚███╔███╔╝██║ ╚████║
╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝  ╚═════╝  ╚══╝╚══╝ ╚═╝  ╚═══╝
                                                                         
██████╗ ██████╗ ███████╗██╗   ██╗██╗███████╗██╗    ██╗███████╗██████╗    
██╔══██╗██╔══██╗██╔════╝██║   ██║██║██╔════╝██║    ██║██╔════╝██╔══██╗   
██████╔╝██████╔╝█████╗  ██║   ██║██║█████╗  ██║ █╗ ██║█████╗  ██████╔╝   
██╔═══╝ ██╔══██╗██╔══╝  ╚██╗ ██╔╝██║██╔══╝  ██║███╗██║██╔══╝  ██╔══██╗   
██║     ██║  ██║███████╗ ╚████╔╝ ██║███████╗╚███╔███╔╝███████╗██║  ██║   
╚═╝     ╚═╝  ╚═╝╚══════╝  ╚═══╝  ╚═╝╚══════╝ ╚══╝╚══╝ ╚══════╝╚═╝  ╚═╝   
[/bold blue]"""

def show_welcome_screen():
    """Show welcome screen with banner"""
    # Clear screen based on OS
    if sys.platform == 'win32':
        os.system('cls')
    else:
        os.system('clear')
        
    # Show banner
    console = Console()
    console.print(Panel(
        Align.center(BANNER),
        title="[bold yellow]Markdown Previewer[/bold yellow]",
        subtitle="[dim]A simple tool to preview markdown files[/dim]",
        border_style="blue",
        padding=(1, 2),
        box=box.DOUBLE
    ))
    
    # Wait for input and clear
    console.print("\n[bold green]Press Enter to start...[/bold green]")
    input()
    
    # Final clear before application starts
    if sys.platform == 'win32':
        os.system('cls')
    else:
        os.system('clear')

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    cleanup_terminal()
    sys.exit(0)

def cleanup_terminal():
    """Ensure terminal is properly restored"""
    try:
        curses.endwin()
    except:
        pass
    
    # Show cursor
    print('\033[?25h', end='')
    
    # Clear screen
    if sys.platform == 'win32':
        os.system('cls')
    else:
        os.system('clear')


class MarkdownPreviewCLI:
    def __init__(self):
        self.current_path = os.getcwd()
        self.files = []
        self.selected_idx = 0
        self.offset = 0
       
        self.console = Console(theme=Theme({
            "markdown": "bold white",
            "panel": "dim white"
        }))
        signal.signal(signal.SIGINT, signal_handler)


    def init_colors(self):
        """Initialize color pairs"""
        # Start curses colors
        curses.start_color()
        curses.use_default_colors()
        
        # Define Discord dark theme colors
        # Background: #36393F (dark gray)
        # Text: #FFFFFF (white)
        # Selected: #7289DA (Discord blue)
        curses.init_pair(1, curses.COLOR_WHITE, 236)  # Normal text
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Selected item
        
        # Set background color
        curses.init_pair(3, curses.COLOR_WHITE, 236)  # Background

    def get_files(self):
        """Get list of files and directories in current path with emoji indicators"""
        items = ['📁 ..']  # Add parent directory option with emoji
        try:
            for item in os.listdir(self.current_path):
                full_path = os.path.join(self.current_path, item)
                if os.path.isdir(full_path):
                    items.append(f"📁 {item}/")
                elif item.endswith('.md'):
                    items.append(f"📄 {item}")
        except OSError as e:
            self.console.print(f"❌ Error accessing directory: {e}", style="bold red")
            return ['📁 ..']  # Return only parent directory on error
        return items

    def draw_menu(self, stdscr):
        """Draw the file browser menu"""
        self.files = self.get_files()
        height, width = stdscr.getmaxyx()
        
        # Set background color
        stdscr.bkgd(' ', curses.color_pair(3))
        
        # Calculate visible items
        max_items = height - 2
        visible_files = self.files[self.offset:self.offset + max_items]

        # Draw border
        stdscr.attron(curses.color_pair(1))
        stdscr.box()
        stdscr.attroff(curses.color_pair(1))
        
        # Draw files
        for idx, item in enumerate(visible_files):
            y = idx + 1
            if idx + self.offset == self.selected_idx:
                stdscr.attron(curses.color_pair(2))
                stdscr.addstr(y, 1, item[:width-2].ljust(width-2))
                stdscr.attroff(curses.color_pair(2))
            else:
                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(y, 1, item[:width-2])
                stdscr.attroff(curses.color_pair(1))


    def preview_markdown(self, filepath):
        """Preview markdown file using rich with emoji support"""
        try:
            # Hide cursor and clear screen
            print('\033[?25l', end='')  # Hide cursor
            os.system('cls' if os.name == 'nt' else 'clear')
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                console = Console(
                    emoji=True,
                    theme=Theme({
                        "markdown.h1": "bold cyan",
                        "markdown.h2": "bold blue",
                        "markdown.item": "green",
                        "markdown.link": "bold magenta",
                        "markdown.code": "bold yellow",
                    }),
                    force_terminal=True
                )
                
                title = f"📄 {filepath}" if filepath.endswith('.md') else f"📁 {filepath}"
                console.print("\n" + "="*50 + "\n")
                markdown = Markdown(content, justify="left")
                console.print(Panel(
                    markdown,
                    title=title,
                    border_style="blue",
                    padding=(1, 2),
                    title_align="left"
                ))
                console.print("\n" + "="*50)
                console.print("\nPress Enter to return to file browser (Ctrl+C to exit)", style="bold yellow")
                
        except Exception as e:
            self.console.print(f"❌ Error: {str(e)}", style="bold red")
        finally:
            # Always show cursor before returning
            print('\033[?25h', end='')


    def run(self, stdscr):
        """Main run loop"""
        curses.curs_set(0)
        self.init_colors()  
        stdscr.clear()

        try:
            while True:
                stdscr.clear()
                self.draw_menu(stdscr)
                key = stdscr.getch()

                if key == curses.KEY_UP and self.selected_idx > 0:
                    self.selected_idx -= 1
                elif key == curses.KEY_DOWN and self.selected_idx < len(self.files) - 1:
                    self.selected_idx += 1
                elif key == ord('\n'):  # Enter key
                    # Remove emoji prefix from selected item
                    selected = self.files[self.selected_idx].split(' ', 1)[1]
                    
                    if selected == '..':
                        self.current_path = os.path.dirname(self.current_path)
                        self.selected_idx = 0
                    elif selected.endswith('/'):
                        # Remove trailing slash for directory navigation
                        clean_path = selected.rstrip('/')
                        self.current_path = os.path.join(self.current_path, clean_path)
                        self.selected_idx = 0
                    elif selected.endswith('.md'):
                        # Construct proper path for markdown files
                        curses.endwin()  # Properly end curses
                        self.preview_markdown(os.path.join(self.current_path, selected))
                        input("\nPress Enter to continue...")
                        # Restore curses environment
                        stdscr = curses.initscr()
                        curses.start_color()
                        self.init_colors()
                        curses.curs_set(0)  
                        stdscr.clear()
                elif key == ord('q'):
                    break

                # Adjust offset for scrolling
                if self.selected_idx < self.offset:
                    self.offset = self.selected_idx
                elif self.selected_idx >= self.offset + (stdscr.getmaxyx()[0] - 2):
                    self.offset = self.selected_idx - (stdscr.getmaxyx()[0] - 3)
        finally:
            # Always clean up when exiting
            cleanup_terminal()

def main():
    """Main function with proper setup and cleanup"""
    try:
        # Show welcome banner first
        show_welcome_screen()
        
        # Start the app with curses wrapper for safe terminal handling
        app = MarkdownPreviewCLI()
        curses.wrapper(app.run)
    except KeyboardInterrupt:
        pass
    finally:
        # Ensure terminal is cleaned up properly
        cleanup_terminal()

if __name__ == "__main__":
    main()