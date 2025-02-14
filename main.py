from rich.console import Console
from rich.panel import Panel
from rich import box
from rich.align import Align
from time import sleep
import os
import inquirer
import sys
import subprocess  
from Flex.AudioPlayer import run_music_player
from Flex.Load import matrix_animation   
from Wifi_Scan.wifi_scan import start_wifi_scan 
from Game_Of_Life.Conways_Game_of_Life import start_game_of_life
from AI.chat import chat as start_ai_chat  

console = Console()
FIRST_RUN = True

def create_menu_panel(title):
    return Panel(
        title,
        style="bold red",
        border_style="red",
        box=box.DOUBLE,
        padding=(1, 2),
        expand=False
    )

def loading_animation(text):
    with console.status(f"[bold blue]{text}[/bold blue]", spinner="dots"):
        sleep(1)

def clean_terminal():
    """Clean terminal between program switches"""
    if sys.platform == 'win32':
        os.system('cls')
    else:
        os.system('clear')

def run_program(program_name, func):
    """Run a program with proper terminal cleanup"""
    try:
        clean_terminal()
        loading_animation(f"Loading {program_name}")
        clean_terminal()
        func()
    finally:
        clean_terminal()
        console.print(f"\n[bold green]Returning to main menu...[/bold green]")
        sleep(1)
        clean_terminal()

def main():
    global FIRST_RUN

    # Run the matrix animation only once
    if FIRST_RUN:
        matrix_animation()
        FIRST_RUN = False

    while True:
        console.clear()
        console.print("\n")
        console.print(Align.center(
            create_menu_panel(
                "🔥 [bold red]          Welcome to Chilli Flex![/bold red]        🔥\n"
                "[dim]Use arrow keys to navigate and Enter to select[/dim]"
            )
        ))
        console.print("\n")

        # Create fancy menu
        questions = [
            inquirer.List(
                'option',
                message="Choose your destiny",
                choices=[
                    "🎵 Music Player 🎵",  
                    "📄 PDF Downloader 📄",
                    "📺 YouTube Downloader 📺",
                    "🤖 AI Chat 🤖",
                    "🔍 AI Math Solver 🔍",
                    "🪟 Windows Utilizer 🪟", 
                    "📶 Wi-Fi Scanner 📶",  
                    "🎮 Game of Life 🎮", 
                    "🐍 Snake Game 🐍",
                    "🚪 Exit 🚪"
                ],
            )
        ]
        answer = inquirer.prompt(questions)
        option = answer['option']

        console.clear()
        loading_animation("Processing your choice")

        try:
            if "Music Player" in option:
                run_program("Music Player", run_music_player)
            elif "PDF Downloader" in option:
                run_program("PDF Downloader", lambda: os.system('python Downloader/pdf.py'))
            elif "YouTube Downloader" in option:
                run_program("YouTube Downloader", lambda: os.system('python Downloader/youtube.py'))
            elif "AI Chat" in option:
                run_program("AI Chat", start_ai_chat)
            elif "AI Math Solver" in option:
                run_program("AI Math Solver", lambda: os.system('python AI/AI_Math_Solver.py'))
            elif "Windows Utilizer" in option:
                run_program("Windows Utilizer", lambda: subprocess.run(['elevate.bat'], shell=True))
            elif "Wi-Fi Scanner" in option:
                run_program("Wi-Fi Scanner", start_wifi_scan)
            elif "Game of Life" in option:
                run_program("Game of Life", start_game_of_life)
            elif "Snake Game" in option:
                run_program("Snake Game", lambda: os.system('python Games/snake.py'))
            elif "Exit" in option:
                clean_terminal()
                console.print(Panel(
                    "👋 [bold red]Thanks for using Chilli Flex![/bold red]",
                    style="red",
                    box=box.ROUNDED
                ))
                break

            if "Exit" not in option:
                sleep(1)
        except KeyboardInterrupt:
            clean_terminal()
            console.print("\n[bold yellow]Returning to main menu...[/bold yellow]\n")
            sleep(1)

if __name__ == "__main__":
    main()