#!/usr/bin/env python3
"""
Test script for the shuffle functionality in the audio player.
Run this to verify that shuffle features are working correctly.
"""

import os
import sys

# Add the parent directory to the path so we can import Flex modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from Flex.audio_service import AudioService
    from Flex.loggers import NullLogger
    
    def test_shuffle_functionality():
        print("Testing shuffle functionality...")
        
        # Create audio service
        logger = NullLogger()
        audio_service = AudioService(logger=logger)
        
        # Test shuffle toggle
        print(f"Shuffle initially: {audio_service.is_shuffle_enabled()}")
        audio_service.toggle_shuffle()
        print(f"After toggle: {audio_service.is_shuffle_enabled()}")
        audio_service.toggle_shuffle()
        print(f"After second toggle: {audio_service.is_shuffle_enabled()}")
        
        # Test playlist functionality
        test_folder = "e:/C_Flex/Downloaded Audio"
        if os.path.exists(test_folder):
            audio_files = [f for f in os.listdir(test_folder) if f.lower().endswith('.mp3')]
            if audio_files:
                test_file = os.path.join(test_folder, audio_files[0])
                print(f"Testing with file: {test_file}")
                
                audio_service.set_playlist_from_folder(test_file)
                print(f"Playlist created with {len(audio_service.playlist)} files")
                
                # Test getting next tracks
                audio_service.toggle_shuffle()  # Enable shuffle
                print("Shuffle enabled, testing random track selection:")
                for i in range(3):
                    next_track = audio_service.get_next_track()
                    if next_track:
                        print(f"  Next track {i+1}: {os.path.basename(next_track)}")
                
                audio_service.toggle_shuffle()  # Disable shuffle
                print("Shuffle disabled, testing sequential track selection:")
                for i in range(3):
                    next_track = audio_service.get_next_track()
                    if next_track:
                        print(f"  Next track {i+1}: {os.path.basename(next_track)}")
            else:
                print("No MP3 files found in test folder")
        else:
            print(f"Test folder not found: {test_folder}")
        
        audio_service.cleanup()
        print("Test completed successfully!")
    
    if __name__ == "__main__":
        test_shuffle_functionality()
        
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this from the correct directory and all dependencies are installed.")
except Exception as e:
    print(f"Error: {e}")
