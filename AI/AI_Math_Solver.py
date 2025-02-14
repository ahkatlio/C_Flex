from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich import box
from rich.text import Text
from rich.align import Align
from rich.markdown import Markdown
import ollama

console = Console()
chat_history = []
MODEL = 'wizard-math'

def create_header():
    return Panel(
        Align.center("[bold green]                 🤖 Chilli Flex AI Math Solver 🤖[/bold green]\n" +
                     "[dim]Commands: 'exit' - return to menu, 'clear' - clear history[/dim]"),
        box=box.DOUBLE,
        style="bright_green",
        border_style="green"
    )

def display_message(role, content, style_color):
    icon = "🧑" if role == "User" else "🤖"
    if role == "Assistant":
        content = Markdown(content) 
    else:
        content = Text(content, style=style_color, justify="left")
    
    console.print(Panel(
        content,
        title=f"[{style_color}]{icon} {role}[/{style_color}]",
        title_align="left",
        box=box.ROUNDED,
        border_style=style_color,
        padding=(0, 1)
    ))

def chat():
    console.clear()
    console.print(create_header())
    system_message = {
        'role': 'system',
        'content': 'You are a chatbot that solves math problems.'
    }
    chat_history.append(system_message)
    
    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")
            
            if user_input.lower() == 'exit':
                console.print("\n[bold yellow]Returning to main menu...[/bold yellow]")
                break
                
            if user_input.lower() == 'clear':
                chat_history.clear()
                chat_history.append(system_message)
                console.clear()
                console.print(create_header())
                continue

            chat_history.append({'role': 'user', 'content': user_input})
            display_message("User", user_input, "cyan")

            try:
                with console.status("[bold green]AI is thinking...[/bold green]", spinner="dots"):
                    response = ollama.chat(
                        model=MODEL,
                        messages=chat_history
                    )
                
                ai_response = response['message']['content']
                chat_history.append({'role': 'assistant', 'content': ai_response})
                display_message("Assistant", ai_response, "green")

            except ConnectionRefusedError:
                console.print(Panel(
                    "[bold red]Error:[/bold red] Unable to connect to Ollama. Make sure the Ollama service is running.",
                    style="red",
                    box=box.ROUNDED,
                    expand=False
                ))
                continue 
                
            except Exception as e:
                console.print(Panel(
                    f"[bold red]Error:[/bold red] {str(e)}",
                    style="red",
                    box=box.ROUNDED,
                    expand=False
                ))
                continue  
                
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Returning to main menu...[/bold yellow]")
            break

if __name__ == "__main__":
    chat()