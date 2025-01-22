import os
import sys

from rich.console import Console
from rich.panel import Panel
from rich import box
from rich.align import Align

###############################################################################
#                            GLOBAL CONFIG & CONSTANTS
###############################################################################

BASE_DIR = os.path.dirname(__file__)
FFMPEG_FOLDER = os.path.join(BASE_DIR, "ffmpeg", "bin")

# Make local ffmpeg visible to the system:
os.environ["PATH"] = FFMPEG_FOLDER + os.pathsep + os.environ.get("PATH", "")

WELCOME_BANNER = r"""
[bold cyan]
███╗   ███╗██╗   ██╗███████╗██╗ ██████╗    ██████╗ ██╗      █████╗ ██╗   ██╗███████╗██████╗ 
████╗ ████║██║   ██║██╔════╝██║██╔════╝    ██╔══██╗██║     ██╔══██╗╚██╗ ██╔╝██╔════╝██╔══██╗
██╔████╔██║██║   ██║███████╗██║██║         ██████╔╝██║     ███████║ ╚████╔╝ █████╗  ██████╔╝
██║╚██╔╝██║██║   ██║╚════██║██║██║         ██╔═══╝ ██║     ██╔══██║  ╚██╔╝  ██╔══╝  ██╔══██╗
██║ ╚═╝ ██║╚██████╔╝███████║██║╚██████╗    ██║     ███████╗██║  ██║   ██║   ███████╗██║  ██║
╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝ ╚═════╝    ╚═╝     ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝
[/bold cyan]
"""

def show_welcome_screen():
    """
    Displays the welcome banner using rich, then waits for user to press Enter.
    Clears the screen afterward.
    """
    # Clear screen
    if sys.platform == 'win32':
        os.system('cls')
    else:
        os.system('clear')

    console = Console()
    console.print(Panel(
        Align.center(WELCOME_BANNER),
        title="[bold yellow]Music Player[/bold yellow]",
        subtitle="[dim]Press Enter to start...[/dim]",
        border_style="cyan",
        padding=(1, 2),
        box=box.DOUBLE
    ))

    console.print("\n[bold green]Press Enter to continue...[/bold green]")
    input()

    # Clear again
    if sys.platform == 'win32':
        os.system('cls')
    else:
        os.system('clear')
