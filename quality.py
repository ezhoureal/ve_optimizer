BASE_IMAGE = "base.jpeg"
RECORD_BATCH = "snap_glass.sh"

import os
import subprocess
import re

from config_ve import VisualEffect, send_config

def get_ssim_score(filename, base_file=BASE_IMAGE):
    """
    Calculate SSIM score between a file and base.jpeg
    
    Args:
        filename (str): Path to the video file to compare
        base_file (str): Path to the base video file (default: "base.mp4")
    
    Returns:
        float: SSIM score (0.0 to 1.0) or None if error
    """
    try:
        # Build the ffmpeg command
        cmd = [
            'ffmpeg',
            '-i', base_file,
            '-i', filename,
            '-lavfi', 'ssim',
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

# More robust version that also returns the full SSIM breakdown
def get_detailed_ssim(filename, base_file=BASE_IMAGE):
    """
    Get detailed SSIM scores including Y, U, V components
    
    Args:
        filename (str): Path to the video file to compare
        base_file (str): Path to the base video file
    
    Returns:
        dict: Dictionary with SSIM scores or None if error
    """
    try:
        cmd = [
            'ffmpeg',
            '-i', base_file,
            '-i', filename,
            '-lavfi', 'ssim',
            '-f', 'null',
            '-'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stderr
        
        # Pattern for all SSIM components
        patterns = {
            'Y': r"Y:([0-9.]+)",
            'U': r"U:([0-9.]+)", 
            'V': r"V:([0-9.]+)",
            'All': r"All:([0-9.]+)"
        }
        
        scores = {}
        for component, pattern in patterns.items():
            match = re.search(pattern, output)
            if match:
                scores[component] = float(match.group(1))
        
        return scores if scores else None
        
    except Exception as e:
        print(f"Error: {e}")
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
        
        print('after record.bat')
        # Combine stdout and stderr (batch scripts often output to stderr)
        output = result.stdout + result.stderr
        # Look for the filename pattern in the output
        filename_pattern = r"Using filename: (photo_\d+\.jpeg)"
        match = re.search(filename_pattern, output)
        
        if match:
            filename = match.group(1)
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
    
    # Get detailed breakdown
    detailed_scores = get_detailed_ssim(filename)
    if detailed_scores:
        print("Detailed SSIM Scores:")
        for component, score in detailed_scores.items():
            print(f"  {component}: {score:.6f}")
        
        return detailed_scores.get('All', 0)

# Example usage
if __name__ == "__main__":
    send_config([
        VisualEffect(effect_name="borderSizeX", o = 350, t=0, s=0),
        VisualEffect(effect_name="borderSizeY", o = 250, t=0, s=0),
        VisualEffect(effect_name="cornerRadius", o = 35, t=0, s=0),
        VisualEffect(effect_name="blurParamsR2", o = 48, t=0, s=0),
        VisualEffect(effect_name="blurParamsK", o = 4, t=0, s=0),
        VisualEffect(effect_name="borderWidthPx", o = 2.9, t=0, s=0),
        VisualEffect(effect_name="embossOffset", o = 1.88, t=0, s=0),
        VisualEffect(effect_name="refractOutPx", o = 20, t=0, s=0),
        VisualEffect(effect_name="envK", o = 0.8, t=0, s=0),
        VisualEffect(effect_name="envB", o = 0, t=0, s=0),
        VisualEffect(effect_name="envS", o = 0, t=0, s=0),
        VisualEffect(effect_name="refractInPx", o = 15, t=0, s=0),
        VisualEffect(effect_name="sdK", o = 0.9, t=0, s=0),
        VisualEffect(effect_name="sdB", o = 0, t=0, s=0),
        VisualEffect(effect_name="sdS", o = 1.0, t=0, s=0),
        VisualEffect(effect_name="highLightDirectionX", o = 1.0, t=0, s=0),
        VisualEffect(effect_name="highLightDirectionY", o = -1.0, t=0, s=0),
        VisualEffect(effect_name="highLightAngleDeg", o = 45.0, t=0, s=0),
        VisualEffect(effect_name="highLightFeatherDeg", o = 30.0, t=0, s=0),
        VisualEffect(effect_name="highLightWidthPx", o = 2.0, t=0, s=0),
        VisualEffect(effect_name="highLightFeatherPx", o = 1.0, t=0, s=0),
        VisualEffect(effect_name="highLightShiftPx", o = 0.0, t=0, s=0),
        VisualEffect(effect_name="hlK", o = 0.6027, t=0, s=0),
        VisualEffect(effect_name="hlB", o = 160, t=0, s=0),
        VisualEffect(effect_name="hlS", o = 2.0, t=0, s=0),
        VisualEffect(effect_name="glassPositionX", o = 50, t=0, s=0),
        VisualEffect(effect_name="glassPositionY", o = 600, t=0, s=0),
        VisualEffect(effect_name="bgFactor", o = 0.9, t=0, s=0)
    ])
    quality_score = test_quality()
    
    print(f"\nOverall Visual Similarity: {quality_score * 100:.2f}%")
    print(f"Visual Loss: {(1 - quality_score) * 100:.2f}%")