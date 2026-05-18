#!/usr/bin/env python3
"""
Recursively find all OGG files in a directory, check if they are stereo,
and convert them to mono using ffmpeg. Optionally outputs GitHub Actions
variables and a JSON report.
"""

import subprocess
import json
import os
import sys
import argparse
from pathlib import Path

# ----------------------------------------------------------------------
# Audio validation (ffprobe)
# ----------------------------------------------------------------------
def check_audio_channels(file_path):
    """
    Use ffprobe to get channel count and other info for the first audio stream.
    Returns a dict with keys: valid, channels, duration, sample_rate.
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'a:0',
            '-show_entries', 'stream=channels,duration,sample_rate',
            '-of', 'json',
            str(file_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        if 'streams' in data and len(data['streams']) > 0:
            stream = data['streams'][0]
            return {
                'valid': True,
                'channels': stream.get('channels', 1),
                'duration': stream.get('duration', 'N/A'),
                'sample_rate': stream.get('sample_rate', 'N/A')
            }
    except Exception as e:
        print(f"Error checking {file_path}: {e}")

    return {'valid': False, 'channels': 0, 'duration': 'N/A', 'sample_rate': 'N/A'}

# ----------------------------------------------------------------------
# Mono conversion (ffmpeg)
# ----------------------------------------------------------------------
def convert_to_mono(input_path):
    """
    Convert a stereo audio file to mono using ffmpeg.
    Steps:
      1. Rename original to .backup
      2. Run ffmpeg to create mono file at original path
      3. Verify mono result
      4. Remove backup on success, restore on failure
    Returns True if conversion succeeded, False otherwise.
    """
    backup_path = input_path + '.backup'
    try:
        os.rename(input_path, backup_path)

        # ffmpeg command: mono, libvorbis codec, quality 5
        cmd = [
            'ffmpeg',
            '-i', backup_path,
            '-ac', '1',               # mono
            '-c:a', 'libvorbis',
            '-q:a', '5',               # good quality (0-10)
            '-y',                       # overwrite output
            input_path
        ]

        print(f"Converting {input_path} to mono...")
        subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Verify the conversion
        info = check_audio_channels(input_path)
        if info['valid'] and info['channels'] == 1:
            print(f"✅ Successfully converted to mono")
            os.remove(backup_path)
            return True
        else:
            print(f"❌ Conversion failed, still {info['channels']} channels")
            os.rename(backup_path, input_path)
            return False

    except Exception as e:
        print(f"Error converting {input_path}: {e}")
        # Restore backup if it exists
        if os.path.exists(backup_path):
            os.rename(backup_path, input_path)
        return False

# ----------------------------------------------------------------------
# File discovery
# ----------------------------------------------------------------------
def find_ogg_files(root_dir, skip_git=True):
    """
    Recursively find all .ogg files under root_dir.
    If skip_git is True, directories named .git are ignored.
    Returns a list of absolute or relative paths (as given by os.walk).
    """
    ogg_files = []
    root_dir = os.path.abspath(root_dir)
    for root, dirs, files in os.walk(root_dir):
        if skip_git and '.git' in root.split(os.sep):
            continue
        for file in files:
            if file.lower().endswith('.ogg'):
                ogg_files.append(os.path.join(root, file))
    return ogg_files

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Recursively convert stereo OGG files to mono."
    )
    parser.add_argument(
        'directory', nargs='?', default='.',
        help="Root directory to scan for OGG files (default: current directory)"
    )
    parser.add_argument(
        '--github-output', action='store_true',
        help="Print GitHub Actions output variables"
    )
    parser.add_argument(
        '--report', action='store_true',
        help="Generate a JSON report (ogg_conversion_report.json)"
    )
    parser.add_argument(
        '--extensions', nargs='+', default=['.ogg'],
        help="File extensions to process (default: .ogg)"
    )
    args = parser.parse_args()

    root = args.directory
    if not os.path.isdir(root):
        print(f"Error: '{root}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    # Find all files with given extensions (only .ogg by default)
    files_to_check = []
    for ext in args.extensions:
        # We'll just re-use find_ogg_files but filter by extension
        # For simplicity, we keep the original find_ogg_files and then filter.
        # A more general approach would be to walk again, but we can just collect all
        # with a generic walk. Let's keep it simple: if only .ogg, use find_ogg_files.
        if ext.lower() == '.ogg':
            files_to_check.extend(find_ogg_files(root, skip_git=True))
        else:
            # For other extensions, do a generic walk
            for root_dir, dirs, files in os.walk(root):
                if '.git' in root_dir.split(os.sep):
                    continue
                for file in files:
                    if file.lower().endswith(ext.lower()):
                        files_to_check.append(os.path.join(root_dir, file))

    if not files_to_check:
        print(f"No files with extensions {args.extensions} found in {root}.")
        return

    print(f"Found {len(files_to_check)} file(s) to check.")

    # Process each file
    stereo_files = []      # files that are stereo before conversion
    converted_files = []   # files successfully converted
    failed_files = []      # stereo files that failed conversion
    all_info = []          # detailed info for report

    for file_path in files_to_check:
        print(f"\nChecking: {file_path}")
        info = check_audio_channels(file_path)
        info['file'] = file_path
        all_info.append(info)

        if not info['valid']:
            print("⚠️  Could not read audio stream, skipping.")
            continue

        channels = info['channels']
        print(f"  Channels: {channels}")

        if channels > 1:
            stereo_files.append({
                'file': file_path,
                'channels': channels,
                'duration': info['duration'],
                'sample_rate': info['sample_rate']
            })
            # Attempt conversion
            if convert_to_mono(file_path):
                converted_files.append(file_path)
            else:
                failed_files.append(file_path)
        else:
            print("  Already mono, nothing to do.")

    # Summary
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    print(f"Total files checked: {len(all_info)}")
    print(f"Stereo files found:  {len(stereo_files)}")
    print(f"Successfully converted: {len(converted_files)}")
    if failed_files:
        print(f"Failed conversions:   {len(failed_files)}")
        for f in failed_files:
            print(f"  - {f}")

    # GitHub Actions output
    if args.github_output:
        # Set output variables
        converted_list = ' '.join(converted_files)
        stereo_list = ' '.join([sf['file'] for sf in stereo_files])
        print(f"::set-output name=converted_files::{converted_list}")
        print(f"::set-output name=converted_count::{len(converted_files)}")
        print(f"::set-output name=stereo_files::{stereo_list}")
        print(f"::set-output name=stereo_count::{len(stereo_files)}")
        print(f"::set-output name=has_stereo::{'true' if stereo_files else 'false'}")

    # JSON report
    if args.report:
        report = {
            'root_directory': os.path.abspath(root),
            'total_checked': len(all_info),
            'stereo_files': stereo_files,
            'converted_files': converted_files,
            'failed_conversions': failed_files,
            'all_files': all_info
        }
        report_path = 'ogg_conversion_report.json'
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved to {report_path}")

if __name__ == '__main__':
    main()
