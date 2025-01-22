import os
import subprocess
import json
from openpyxl import Workbook

def main():
    # Prompt user for the ffprobe path
    ffprobe_path = input("Enter full path to the ffprobe executable: ").strip()
    if not os.path.isfile(ffprobe_path):
        print("ffprobe not found at that location.")
        return

    # Prompt user for the folder containing .mp3 files
    folder_path = input("Enter the folder path containing .mp3 files: ").strip()
    if not os.path.isdir(folder_path):
        print("Specified folder does not exist.")
        return

    # Create a new Excel workbook and set up the header row
    wb = Workbook()
    ws = wb.active
    headers = [
        "File", "StreamIndex", "StreamID", "Language", "CodecName",
        "Profile", "CodecTagString", "CodecTag", "SampleRate",
        "Channels", "ChannelLayout", "SampleFmt", "BitRate", "DispositionDefault"
    ]
    ws.append(headers)

    # Walk through the directory to find .mp3 files
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith('.mp3'):
                full_path = os.path.join(root, file)
                # Run ffprobe on the file to get stream info in JSON format
                try:
                    result = subprocess.run(
                        [ffprobe_path, '-v', 'quiet', '-print_format', 'json', '-show_streams', full_path],
                        capture_output=True, text=True
                    )
                    if result.returncode != 0:
                        print(f"ffprobe error on file {file}: {result.stderr}")
                        continue
                    data = json.loads(result.stdout)
                except Exception as e:
                    print(f"Error processing file {file}: {e}")
                    continue

                # Process each stream in the file
                for stream in data.get("streams", []):
                    if stream.get("codec_type") == "audio":
                        row = []
                        row.append(file)  # File name
                        row.append(stream.get("index"))  # Stream index
                        row.append(stream.get("id"))     # Stream ID
                        # Language tag if available
                        language = stream.get("tags", {}).get("language", "")
                        row.append(language)
                        row.append(stream.get("codec_name"))
                        row.append(stream.get("profile"))
                        row.append(stream.get("codec_tag_string"))
                        row.append(stream.get("codec_tag"))
                        row.append(stream.get("sample_rate"))
                        row.append(stream.get("channels"))
                        row.append(stream.get("channel_layout"))
                        row.append(stream.get("sample_fmt"))
                        row.append(stream.get("bit_rate"))
                        disposition_default = stream.get("disposition", {}).get("default")
                        row.append(disposition_default)
                        ws.append(row)

    # Save the workbook in the same folder as the MP3 files
    output_excel = os.path.join(folder_path, "audio_streams.xlsx")
    wb.save(output_excel)
    print(f"Data saved to {output_excel}")

if __name__ == "__main__":
    main()
