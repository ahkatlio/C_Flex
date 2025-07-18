#!/usr/bin/env python3
"""
Direct Music Player Launcher
Bypasses the main menu and starts the music player directly.
"""
import os
import sys
import curses

# Add the Flex directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'Flex'))

from Flex.audio_service import AudioService
from Flex.loggers import NullLogger
from Flex.curses_ui_ascii_clean import CursesMusicUI

def run_music_player_direct():
    """Run the music player directly without the main menu."""
    try:
        print("Starting Music Player...")
        print("Controls:")
        print("  Space: Play/Pause")
        print("  S: Stop")  
        print("  Q: Quit")
        print("  R: Toggle Shuffle")
        print("  A: Toggle Auto-advance")
        print("  Left/Right: Previous/Next track")
        print("  Up/Down: Volume")
        print("\nPress any key to continue...")
        input()
        
        # Initialize components
        logger = NullLogger()
        audio_service = AudioService(logger=logger)
        
        # Start the UI
        def ui_wrapper(stdscr):
            ui = CursesMusicUI(audio_service, logger=logger)
            ui.run_ui(stdscr)
        
        curses.wrapper(ui_wrapper)
        
    except KeyboardInterrupt:
        print("\nMusic player interrupted by user.")
    except Exception as e:
        print(f"Error running music player: {e}")
    finally:
        print("Music player stopped.")

if __name__ == "__main__":
    print("Direct Music Player")
    print("=" * 30)
    
    # Check if audio directory exists
    if not os.path.exists("Downloaded Audio"):
        print("Error: 'Downloaded Audio' directory not found!")
        print("Please make sure you have audio files in the 'Downloaded Audio' folder.")
        sys.exit(1)
    
    # Check for audio files
    audio_files = [f for f in os.listdir("Downloaded Audio") 
                  if f.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a'))]
    
    if not audio_files:
        print("Error: No audio files found in 'Downloaded Audio' directory!")
        print("Supported formats: MP3, WAV, FLAC, OGG, M4A")
        sys.exit(1)
    
    print(f"Found {len(audio_files)} audio files ready to play.")
    
    run_music_player_direct()
