#!/usr/bin/env python3
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'Flex'))

from Flex.audio_service import AudioService
from Flex.loggers import NullLogger

def test_audio_player():
    """Test audio player functionality without UI"""
    print("Testing Audio Player Core Functionality")
    print("=" * 50)
    
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
            print(f"Found test file: {test_file}")
            
            # Test shuffle functionality
            print("\n1. Testing Shuffle Functionality:")
            print(f"   Shuffle initially: {audio_service.shuffle_enabled}")
            
            audio_service.toggle_shuffle()
            print(f"   After toggle: {audio_service.shuffle_enabled}")
            
            # Test playlist creation
            print("\n2. Testing Playlist Creation:")
            audio_service.set_playlist_from_folder(test_file)
            print(f"   Playlist created with {len(audio_service.playlist)} files")
            print(f"   Current track index: {audio_service.current_track_index}")
            print(f"   Current track: {os.path.basename(audio_service.playlist[audio_service.current_track_index])}")
            
            # Test track navigation
            print("\n3. Testing Track Navigation:")
            next_track = audio_service.get_next_track()
            if next_track:
                print(f"   Next track: {os.path.basename(next_track)}")
            else:
                print("   No next track available")
                
            prev_track = audio_service.get_previous_track()
            if prev_track:
                print(f"   Previous track: {os.path.basename(prev_track)}")
            else:
                print("   No previous track available")
            
            # Test file loading (without playing)
            print("\n4. Testing File Loading:")
            try:
                # Just test if the file can be decoded
                from pydub import AudioSegment
                audio_segment = AudioSegment.from_file(test_file)
                print(f"   File loaded successfully!")
                print(f"   Duration: {len(audio_segment)} ms")
                print(f"   Sample rate: {audio_segment.frame_rate} Hz")
                print(f"   Channels: {audio_segment.channels}")
            except Exception as e:
                print(f"   Error loading file: {e}")
            
            print("\n5. Testing Controls:")
            print(f"   Auto-advance enabled: {getattr(audio_service, 'auto_advance_enabled', True)}")
            print(f"   Is playing: {audio_service.is_playing}")
            print(f"   Is paused: {audio_service.is_paused}")
            
            print("\n✅ All core functionality tests completed!")
            return True
        else:
            print("❌ No audio files found in Downloaded Audio directory")
            return False
    else:
        print("❌ Downloaded Audio directory not found")
        return False

if __name__ == "__main__":
    test_audio_player()
