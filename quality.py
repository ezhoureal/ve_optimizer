BASE_IMAGE = "base.jpeg"
DATA_DIR = "data/"

import platform
if platform.system() == "Windows":
    RECORD_BATCH = "snap.bat"
else:
    RECORD_BATCH = "./snap.sh"

import os
import subprocess
import re

from config_ve import DEFAULT_EFFECTS, send_config

def get_ssim_score(filename, base_file=BASE_IMAGE):
    """
    Calculate SSIM score between a file and base.jpeg
    
    Args:
        filename (str): Path to the video file to compare
        base_file (str): Path to the base video file (default: "base.jpeg")
    
    Returns:
        float: SSIM score (0.0 to 1.0) or None if error
    """
    try:
        # Build the ffmpeg command
        # Crop out the top 200 pixels from both inputs, then run SSIM on the cropped regions
        # [0:v] and [1:v] refer to the two inputs (base_file and filename)
        cmd = [
            'ffmpeg',
            '-i', base_file,
            '-i', filename,
            '-lavfi', '[0:v]crop=iw:ih-200:0:200[a];[1:v]crop=iw:ih-200:0:200[b];[a][b]ssim',
            '-f', 'null',
            '-'
        ]
        
        # Run the command and capture output
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True,
            check=True
        )
        
        # Search for SSIM pattern in stderr (ffmpeg outputs to stderr)
        output = result.stderr
        
        # Look for the SSIM All score
        ssim_pattern = r"All:([0-9.]+)"
        match = re.search(ssim_pattern, output)
        
        if match:
            ssim_score = float(match.group(1))
            return ssim_score
        else:
            print("SSIM score not found in output")
            return None
            
    except subprocess.CalledProcessError as e:
        print(f"Error running ffmpeg: {e}")
        print(f"stderr: {e.stderr}")
        return None
    except FileNotFoundError:
        print("Error: ffmpeg not found. Please install ffmpeg and ensure it's in your PATH.")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

def get_snapshot(batch_script_path=RECORD_BATCH):
    """
    Run the screen recording batch script and capture the generated filename
    
    Args:
        batch_script_path (str): Path to the batch script
    
    Returns:
        str: The generated filename or None if error
    """
    try:
        # Run the batch script and capture output
        result = subprocess.run(
            batch_script_path,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Combine stdout and stderr (batch scripts often output to stderr)
        output = result.stdout + result.stderr
        # Look for the filename pattern in the output
        filename_pattern = r"Using filename: (photo_\d+\.jpeg)"
        match = re.search(filename_pattern, output)
        
        if match:
            filename = os.path.join(DATA_DIR, match.group(1))
            print(f"Generated filename: {filename}")
            
            # Check if file was actually downloaded
            if os.path.exists(filename):
                print(f"File successfully downloaded: {filename}")
                return filename
            else:
                print(f"Warning: Filename found in output but file doesn't exist: {filename}")
                return None
        else:
            print("Could not find filename in batch script output")
            return None
        
    except subprocess.CalledProcessError as e:
        print(f"Error running batch script: {e}")
        print(f"Output: {e.stderr}")
        return None
    except FileNotFoundError:
        print(f"Error: Batch script not found at {batch_script_path}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

def get_base_snapshot():
    filename = get_snapshot()
    if not filename:
        return None
    try:
        # Atomically replace existing base image if present
        os.replace(filename, BASE_IMAGE)
        print(f"Renamed snapshot {filename} -> {BASE_IMAGE}")
        return BASE_IMAGE
    except Exception as e:
        print(f"Error renaming snapshot to {BASE_IMAGE}: {e}")
        return None

def test_quality() -> float:
    filename = get_snapshot()

    # Get just the overall SSIM score
    ssim_score = get_ssim_score(filename)
    if ssim_score is not None:
        print(f"SSIM Score: {ssim_score:.6f}")
        print(f"Visual Similarity: {ssim_score * 100:.2f}%")
        print(f"Visual Loss: {(1 - ssim_score) * 100:.2f}%")
    
    print("\n" + "="*50 + "\n")
    return (1 - ssim_score) * 100 # scale to percentage to better match other loss metrics

# Example usage
if __name__ == "__main__":
    send_config(DEFAULT_EFFECTS)
    get_base_snapshot()
    quality_score = test_quality()
    
    print(f"\nOverall Visual Similarity: {quality_score * 100:.2f}%")
    print(f"Visual Loss: {(1 - quality_score) * 100:.2f}%")