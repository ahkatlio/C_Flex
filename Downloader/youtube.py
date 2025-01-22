from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich import box
from rich.align import Align
import inquirer
import os
from pytubefix import YouTube 
import re

console = Console()

def create_download_folders():
    folders = ['Downloaded Videos', 'Downloaded Audio']
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)

def validate_url(url):
    youtube_regex = r'^(https?\:\/\/)?(www\.youtube\.com|youtu\.?be)\/.+$'
    return bool(re.match(youtube_regex, url))

def get_video_quality(yt):
    streams = yt.streams.filter(progressive=True)
    qualities = [f"{stream.resolution} - {stream.filesize_mb:.1f}MB" for stream in streams]
    questions = [
        inquirer.List('quality',
                     message="Select video quality:",
                     choices=qualities)
    ]
    answer = inquirer.prompt(questions)
    return answer['quality'].split()[0]

def download_video(url, quality):
    try:
        yt = YouTube(url)
        stream = yt.streams.filter(res=quality, progressive=True).first()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        ) as progress:
            task = progress.add_task("[cyan]Downloading...", total=100)
            
            def progress_callback(stream, chunk, bytes_remaining):
                total_size = stream.filesize
                bytes_downloaded = total_size - bytes_remaining
                percentage = (bytes_downloaded / total_size) * 100
                progress.update(task, completed=percentage)
                
            yt.register_on_progress_callback(progress_callback)
            filepath = stream.download('Downloaded Videos')
            
        return filepath
    except Exception as e:
        raise Exception(f"Download failed: {str(e)}")

def download_audio(url):
    try:
        yt = YouTube(url)
        stream = yt.streams.filter(only_audio=True).first()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        ) as progress:
            task = progress.add_task("[cyan]Downloading audio...", total=100)
            
            def progress_callback(stream, chunk, bytes_remaining):
                total_size = stream.filesize
                bytes_downloaded = total_size - bytes_remaining
                percentage = (bytes_downloaded / total_size) * 100
                progress.update(task, completed=percentage)
                
            yt.register_on_progress_callback(progress_callback)
            filepath = stream.download('Downloaded Audio')
            
        # Convert to MP3
        base, ext = os.path.splitext(filepath)
        new_filepath = base + '.mp3'
        os.rename(filepath, new_filepath)
        return new_filepath
    except Exception as e:
        raise Exception(f"Download failed: {str(e)}")

def main():
    console.clear()
    create_download_folders()
    
    while True:
        console.print(Align.center(Panel(
            "[bold magenta]             YouTube Downloader[/bold magenta]\n"
            "✨ Download videos and audio with style ✨",
            box=box.DOUBLE,
            padding=(1, 2),
            expand=False
        )))

        questions = [
            inquirer.List('option',
                         message="Choose download type",
                         choices=['📺 Video', '🎵 Audio', '🚪 Exit'])
        ]
        answer = inquirer.prompt(questions)
        
        if answer['option'] == '🚪 Exit':
            console.print("\n[bold yellow]Returning to main menu...[/bold yellow]")
            break
            
        url = Prompt.ask("\n[bold cyan]Enter YouTube URL[/bold cyan]")
        
        if not validate_url(url):
            console.print(Panel(
                "[bold red]❌ Invalid YouTube URL![/bold red]",
                style="red",
                box=box.ROUNDED
            ))
            continue

        try:
            if '📺 Video' in answer['option']:
                quality = get_video_quality(YouTube(url))
                filepath = download_video(url, quality)
            else:
                filepath = download_audio(url)
                
            console.print(Panel(
                f"[bold green]✅ Download complete![/bold green]\n"
                f"📁 Saved as: [bold cyan]{filepath}[/bold cyan]",
                box=box.ROUNDED
            ))
            
        except Exception as e:
            console.print(Panel(
                f"[bold red]Error:[/bold red] {str(e)}",
                style="red",
                box=box.ROUNDED
            ))

        questions = [
            inquirer.List('continue',
                         message="Download another?",
                         choices=['Yes ✅', 'No ❌'])
        ]
        if inquirer.prompt(questions)['continue'] == 'No ❌':
            console.print("\n[bold yellow]Returning to main menu...[/bold yellow]")
            break

if __name__ == "__main__":
    main()