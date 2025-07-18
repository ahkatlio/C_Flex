#!/usr/bin/env python3
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'Flex'))

from Flex.audio_service import AudioService
from Flex.loggers import NullLogger
import time

def test_audio_playback():
    """Test actual audio playback"""
    print("Testing Audio Playback")
    print("=" * 30)
    
    # Initialize audio service
    logger = NullLogger()
    audio_service = AudioService(logger=logger)
    
    # Find first audio file
    audio_dir = "Downloaded Audio"
    if os.path.exists(audio_dir):
        audio_files = [f for f in os.listdir(audio_dir) 
                      if f.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a'))]
        
        if audio_files:
            test_file = os.path.join(audio_dir, audio_files[0])
            print(f"Testing with: {test_file}")
            
            # Set up playlist
            audio_service.set_playlist_from_folder(test_file)
            print(f"Playlist setup: {len(audio_service.playlist)} files")
            
            # Try to load and play
            print("Attempting to load and play...")
            success = audio_service.load_and_play(test_file)
            print(f"Load and play result: {success}")
            
            if success:
                print(f"Is playing: {audio_service.is_playing}")
                print(f"Is paused: {audio_service.is_paused}")
                print(f"Duration: {audio_service.duration_s} seconds")
                
                # Let it play for 3 seconds
                print("Playing for 3 seconds...")
                for i in range(3):
                    time.sleep(1)
                    position = audio_service.get_playback_position()
                    print(f"  Position: {position:.1f}s")
                
                # Stop
                print("Stopping...")
                audio_service.stop()
                print(f"Is playing after stop: {audio_service.is_playing}")
                
                return True
            else:
                print("Failed to load and play file")
                return False
        else:
            print("No audio files found")
            return False
    else:
        print("Audio directory not found")
        return False

if __name__ == "__main__":
    test_audio_playback()
