from colorama import init, Fore
import time
import sys

init(autoreset=True)

def animate_text(text):
    colors = [Fore.RED, Fore.GREEN, Fore.YELLOW, Fore.BLUE, Fore.MAGENTA, Fore.CYAN]
    while True:
        for color in colors:
            sys.stdout.write(f"\r{color}{text}")  # Use carriage return to overwrite the line
            sys.stdout.flush()  # Ensure the text is printed immediately
            time.sleep(0.5)  # Pause for half a second

animate_text("Animating Colored Text!")
