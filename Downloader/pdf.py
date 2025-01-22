from rich.console import Console
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from rich import box
import requests
import os
import inquirer
from urllib.parse import urlparse
import mimetypes

console = Console()

def create_fancy_progress():
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(complete_style="green", finished_style="bold green"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        expand=True
    )

def validate_pdf_url(url):
    try:
        response = requests.head(url, allow_redirects=True)
        content_type = response.headers.get('content-type', '').lower()
        return 'application/pdf' in content_type
    except:
        return False

def create_download_folder():
    folder_name = "Downloaded PDFs"
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
    return folder_name

def sanitize_filename(filename):
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename

def download_pdf():
    console.clear()
    console.print(Align.center(Panel(
        "[bold blue]     Welcome to PDF Downloader![/bold blue]\n"
        "✨ Download your PDFs with style ✨",
        box=box.DOUBLE,
        padding=(1, 2),
        expand=False
    )))

    while True:
        url = Prompt.ask("\n[bold cyan]Enter the URL[/bold cyan] of the PDF file to download (or 'exit' to quit)")
        
        if url.lower() == 'exit':
            console.print("\n[bold yellow]Returning to main menu...[/bold yellow]")
            return

        with console.status("[bold yellow]Validating URL...[/bold yellow]") as status:
            if not validate_pdf_url(url):
                console.print("\n[bold red]❌ Invalid PDF URL. Please enter a valid PDF file URL.[/bold red]")
                continue

        default_filename = os.path.basename(urlparse(url).path) or "download.pdf"
        filename = Prompt.ask(
            "\n[bold cyan]Enter filename[/bold cyan] to save as",
            default=default_filename
        )
        
        if not filename.endswith('.pdf'):
            filename += '.pdf'
        
        filename = sanitize_filename(filename)
        download_folder = create_download_folder()
        filepath = os.path.join(download_folder, filename)

        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            total_length = int(response.headers.get('content-length', 0))

            with open(filepath, 'wb') as f, create_fancy_progress() as progress:
                task = progress.add_task("[bold blue]Downloading PDF...", total=total_length)
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        progress.update(task, advance=len(chunk))

            console.print(Panel(
                f"[bold green]✅ Success![/bold green]\n"
                f"📁 File saved as: [bold cyan]{filepath}[/bold cyan]",
                box=box.ROUNDED,
                expand=False
            ))

        except Exception as e:
            console.print(Panel(
                f"[bold red]❌ Error:[/bold red] {str(e)}",
                style="red",
                box=box.ROUNDED,
                expand=False
            ))

        questions = [
            inquirer.List('continue',
                         message="Would you like to download another PDF?",
                         choices=['Yes ✅', 'No ❌'])
        ]
        answer = inquirer.prompt(questions)
        if answer['continue'] == 'No ❌':
            console.print("\n[bold yellow]Returning to main menu...[/bold yellow]")
            break

if __name__ == "__main__":
    download_pdf()