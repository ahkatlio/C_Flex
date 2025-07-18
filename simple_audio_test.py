#!/usr/bin/env python3
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'Flex'))

from Flex.audio_service import AudioService
from Flex.loggers import NullLogger
import time

def simple_audio_test():
    """Simple audio test with user interaction"""
    print("Simple Audio Player Test")
    print("=" * 40)
    
    # Initialize audio service
    logger = NullLogger()
    audio_service = AudioService(logger=logger)
    
    # Find audio files
    audio_dir = "Downloaded Audio"
    if not os.path.exists(audio_dir):
        print(f"Audio directory '{audio_dir}' not found!")
        return
    
    audio_files = [f for f in os.listdir(audio_dir) 
                  if f.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a'))]
    
    if not audio_files:
        print("No audio files found!")
        return
    
    print(f"Found {len(audio_files)} audio files:")
    for i, file in enumerate(audio_files[:5]):  # Show first 5
        print(f"  {i+1}. {file}")
    if len(audio_files) > 5:
        print(f"  ... and {len(audio_files) - 5} more")
    
    # Use first file
    test_file = os.path.join(audio_dir, audio_files[0])
    print(f"\nTesting with: {os.path.basename(test_file)}")
    
    # Set up playlist and test shuffle
    audio_service.set_playlist_from_folder(test_file)
    print(f"Playlist created with {len(audio_service.playlist)} files")
    
    print("\nTesting shuffle functionality:")
    print(f"  Shuffle initially: {audio_service.shuffle_enabled}")
    audio_service.toggle_shuffle()
    print(f"  Shuffle after toggle: {audio_service.shuffle_enabled}")
    
    # Test track navigation
    print("\nTesting track navigation:")
    next_track = audio_service.get_next_track()
    if next_track:
        print(f"  Next track: {os.path.basename(next_track)}")
    
    prev_track = audio_service.get_previous_track()
    if prev_track:
        print(f"  Previous track: {os.path.basename(prev_track)}")
    
    # Load and play
    print(f"\nLoading and playing: {os.path.basename(test_file)}")
    success = audio_service.load_and_play(test_file)
    
    if success:
        print("SUCCESS: Audio is playing!")
        print(f"  Duration: {audio_service.duration_s:.1f} seconds")
        print(f"  Playing: {audio_service.is_playing}")
        print(f"  Paused: {audio_service.is_paused}")
        
        # Let it play briefly
        print("\nPlaying for 2 seconds...")
        for i in range(2):
            time.sleep(1)
            pos = audio_service.get_playback_position()
            print(f"  Position: {pos:.1f}s")
        
        # Test pause
        print("\nTesting pause...")
        audio_service.pause()
        print(f"  Paused: {audio_service.is_paused}")
        time.sleep(1)
        
        # Resume
        print("Resuming...")
        audio_service.pause()  # Toggle back
        print(f"  Paused: {audio_service.is_paused}")
        time.sleep(1)
        
        # Stop
        print("Stopping...")
        audio_service.stop()
        print(f"  Playing: {audio_service.is_playing}")
        
        print("\n✅ All audio tests passed!")
        return True
    else:
        print("❌ Failed to load and play audio")
        return False

if __name__ == "__main__":
    simple_audio_test()
