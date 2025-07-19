#!/usr/bin/env python3
import os
import sys
import time
sys.path.append(os.path.join(os.path.dirname(__file__), 'Flex'))

from Flex.audio_service import AudioService
from Flex.loggers import NullLogger

def test_track_switching():
    """Test track switching and auto-advance functionality"""
    print("Testing Track Switching and Auto-Advance")
    print("=" * 50)
    
    # Initialize audio service
    logger = NullLogger()
    audio_service = AudioService(logger=logger)
    
    # Find audio files
    audio_dir = "Downloaded Audio"
    if not os.path.exists(audio_dir):
        print("❌ Downloaded Audio directory not found")
        return False
        
    audio_files = [f for f in os.listdir(audio_dir) 
                  if f.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a'))]
    
    if len(audio_files) < 2:
        print("❌ Need at least 2 audio files for testing")
        return False
    
    test_file = os.path.join(audio_dir, audio_files[0])
    print(f"Loading first file: {os.path.basename(test_file)}")
    
    # Test auto-advance callback
    advance_called = []
    def mock_callback():
        advance_called.append(True)
        print("🎵 Auto-advance callback triggered!")
    
    audio_service.set_track_finished_callback(mock_callback)
    
    # Test 1: Playlist creation and navigation
    print("\n1. Testing Playlist and Navigation:")
    audio_service.set_playlist_from_folder(test_file)
    print(f"   Playlist size: {len(audio_service.playlist)}")
    print(f"   Current track: {os.path.basename(audio_service.playlist[audio_service.current_track_index])}")
    
    # Test next track
    next_track = audio_service.get_next_track()
    print(f"   Next track: {os.path.basename(next_track) if next_track else 'None'}")
    
    # Test previous track
    prev_track = audio_service.get_previous_track()
    print(f"   Previous track: {os.path.basename(prev_track) if prev_track else 'None'}")
    
    # Test 2: Shuffle functionality
    print("\n2. Testing Shuffle:")
    print(f"   Shuffle enabled: {audio_service.is_shuffle_enabled()}")
    audio_service.toggle_shuffle()
    print(f"   After toggle: {audio_service.is_shuffle_enabled()}")
    
    # Test 3: Auto-advance setting
    print("\n3. Testing Auto-advance:")
    print(f"   Auto-advance: {audio_service.get_auto_advance()}")
    audio_service.set_auto_advance(True)
    print(f"   After enabling: {audio_service.get_auto_advance()}")
    
    # Test 4: Track loading without playing
    print("\n4. Testing Track Loading States:")
    print(f"   Before loading - Playing: {audio_service.is_playing}, Paused: {audio_service.is_paused}")
    
    # Clean up
    audio_service.cleanup()
    
    print("\n✅ Track switching tests completed!")
    return True

if __name__ == "__main__":
    test_track_switching()
