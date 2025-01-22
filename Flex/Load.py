from rich.live import Live
from rich.console import Console
from rich.text import Text
import random
import string
import time

JAPANESE_CHARS = "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
CHINESE_CHARS = "的一是不了人我在有他这为之大来以个中上们"
BANGLA_CHARS = "অআইঈউঊঋএঐওঔকখগঘঙচছজঝঞটঠডঢণতথদধনপফবভমযরলশষসহড়ঢ়য়"
ENGLISH_CHARS = string.ascii_letters
NUMBERS = string.digits
TARGET_TEXT = "Chilli Flex"

ALL_CHARS = JAPANESE_CHARS + CHINESE_CHARS + BANGLA_CHARS + ENGLISH_CHARS + NUMBERS

class TargetChar:
    def __init__(self, char, final_x, final_y, start_time):
        self.char = char
        self.current_char = random.choice(ALL_CHARS)
        self.x = final_x
        self.y = 0
        self.final_y = final_y
        self.locked = False
        self.change_countdown = random.randint(1, 5)
        self.start_time = start_time
        self.active = False

    def update(self, current_time):
        if current_time >= self.start_time:
            self.active = True
            
        if self.active and not self.locked:
            if self.y < self.final_y:
                self.y += 1
            else:
                self.change_countdown -= 1
                if self.change_countdown <= 0:
                    self.locked = True
                    self.current_char = self.char
                else:
                    self.current_char = random.choice(ALL_CHARS)

def matrix_animation():
    console = Console()
    width = console.width
    height = console.height - 1
    
    # Initialize background rain
    rain = [[' ' for _ in range(width)] for _ in range(height)]
    
    # Pure rain animation duration
    RAIN_DURATION = 2  # seconds
    CHAR_DELAY = 0.5   # delay between each character start
    FINAL_PAUSE = 5    # seconds
    
    # Create target characters with staggered start times
    start_x = (width - len(TARGET_TEXT)) // 2
    target_y = height // 2
    target_chars = [
        TargetChar(
            char=TARGET_TEXT[i],
            final_x=start_x + i,
            final_y=target_y,
            start_time=RAIN_DURATION + (i * CHAR_DELAY)
        )
        for i in range(len(TARGET_TEXT))
    ]
    
    start_time = time.time()
    
    with Live(refresh_per_second=15) as live:
        while True:
            current_time = time.time() - start_time
            output = Text()
            
            # Update background rain
            new_row = [' ' if random.random() > 0.1 else random.choice(ALL_CHARS) 
                      for _ in range(width)]
            rain.pop()
            rain.insert(0, new_row)
            
            # Update target characters
            all_locked = True
            for char in target_chars:
                if not char.locked:
                    all_locked = False
                    char.update(current_time)
            
            # Render frame
            for y in range(height):
                for x in range(width):
                    # Check if position has a target character
                    target_char = next(
                        (tc for tc in target_chars if tc.active and tc.x == x and tc.y == y),
                        None
                    )
                    
                    if target_char:
                        if target_char.locked:
                            output.append(target_char.char, style="bold white")
                        else:
                            output.append(target_char.current_char, style="bold green")
                    else:
                        char = rain[y][x]
                        if char != ' ':
                            brightness = random.randint(0, 100)
                            output.append(char, style=f"rgb(0,{brightness + 155},0)")
                        else:
                            output.append(char)
                output.append("\n")
                
            live.update(output)
            # time.sleep(0.05)
            
            # Exit condition: all target characters have reached their final position
            if all_locked and current_time > (RAIN_DURATION + len(TARGET_TEXT) * CHAR_DELAY + FINAL_PAUSE):
                break

    console.clear()

if __name__ == "__main__":
    matrix_animation()