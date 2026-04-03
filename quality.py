'''
@ Description: 
    1. snap_eva.bat 会将截图先保存到 temp 目录
    2. base 图会统一放到 data/base/ 目录下
    3. 直接对 data/base/ 和 temp/ 两个目录进行比较（获取 quality_loss)
    4. 视情况, 删除 temp 目录下的图片, 或者将其移动到 data/[time]/ 目录下
'''

QUALITY_LOSS_WEIGHT = {
    "PSNR": 1.0,
    "SSIM": 0.0,
}
TEMP_DIR = "temp"

import glob
import platform
if platform.system() == "Windows":
    RECORD_BATCH = ".\\snap_scene_board.bat"
else:
    RECORD_BATCH = "./snap.sh"

import os
import shutil
import subprocess
import statistics
import re
import cv2
import datetime

from config_ve import DEFAULT_EFFECTS, send_config

def get_psnr_score(filename: str, base_file: str):
    """
    Calculate PSNR score between a file and base.jpeg
    Args:
        filename (str): Path to the video file to compare
        base_file (str): Path to the base video file (default: "base.jpeg")
    
    Returns:
        float: PSNR score (positive number, the larger the better) or None if error
    """
    img1 = cv2.imread(filename)
    img2 = cv2.imread(base_file)
    if img1 is None or img2 is None:
        print("Error: Could not load one or both images")
        return None

    if img1.shape != img2.shape:
        print("Error: Images have different sizes")
        return None

    # 需要裁掉上方状态栏和下方导航条进行比较
    psnr_value = cv2.PSNR(img1[150:-150, :, :], img2[150:-150, :, :])
    return -psnr_value

def get_ssim_score(filename: str, base_file: str):
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
            return (1.0 - ssim_score) * 100
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

def get_snapshots(verbose=False) -> dict[str, str]:
    """
    Run the screen recording batch script and capture the generated filename
    
    Args:
        batch_script_path (str): Path to the batch script
    
    Returns:
        str: The generated filename or None if error
    """
    try:
        path = TEMP_DIR
        if os.path.exists(path) and os.path.isdir(path):
            shutil.rmtree(path)
            if verbose:
                print(f"Removed existing directory: {path}")

        subprocess.run(
            RECORD_BATCH,
            capture_output=True,
            text=True,
            check=True
        )

        runtag = str(datetime.datetime.now().strftime("%m%d%H%M%S"))
        return runtag

    except Exception as e:
        print(f"Unexpected error: {e}")
        return []

def get_base_snapshots(verbose=False, data_dir="data"):
    # 在 data_dir/base 下生成图片
    get_snapshots(verbose=verbose)
    try:
        destination = os.path.join(data_dir, 'base')
        shutil.copytree(TEMP_DIR, destination, dirs_exist_ok=True)
        print(f"Moved temp directory to: {destination}")
    except Exception as e:
        print(f"Error renaming snapshots to base images: {e}")

def test_quality(verbose=False, dst_name=None, data_dir="data") -> float:
    runtag = get_snapshots(verbose=verbose)
    # 比较 temp 和 data_dir/base 下所有同名 jpeg 的值
    base_dir = os.path.join(data_dir, "base")
    base_images = []
    test_images = []
    test_items = os.listdir(TEMP_DIR)
    for item in os.listdir(base_dir):
        if item.endswith(".jpeg") and item in test_items:
            item_path = os.path.join(base_dir, item)
            base_images.append(item_path)
            test_images.append(os.path.join(TEMP_DIR, item))

    # Get just the overall scores
    quality_scores = {}
    for keyname in QUALITY_LOSS_WEIGHT.keys():
        if QUALITY_LOSS_WEIGHT[keyname] > 0.0:
            quality_scores[keyname] = []

    for i in range(len(base_images)):
        base_file = base_images[i]
        test_file = test_images[i]
        for keyname in quality_scores.keys():
            if keyname == "PSNR":
                quality_scores[keyname].append(get_psnr_score(test_file, base_file))
            elif keyname == "SSIM":
                quality_scores[keyname].append(get_ssim_score(test_file, base_file))

    score = 0
    for keyname in quality_scores.keys():
        if verbose:
            print(f"{keyname} score: {statistics.mean(quality_scores[keyname])}")
        score += statistics.mean(quality_scores[keyname]) * QUALITY_LOSS_WEIGHT[keyname]

    if dst_name is not None:
        if dst_name == -1:
            destination = os.path.join(data_dir, runtag)
        else:
            destination = os.path.join(data_dir, dst_name)
        shutil.copytree(TEMP_DIR, destination, dirs_exist_ok=True)
        if verbose:
            print(f"Moved temp directory to: {destination}")
    return score

# Example usage
if __name__ == "__main__":
    # 截图时序不对齐, 会导致 quality 得分较差
    send_config(DEFAULT_EFFECTS)
    get_base_snapshots()
    qss = []
    for i in range(2):
        quality_score = test_quality(verbose=True, dst_name=-1)
        qss.append(quality_score)
    for i in range(2):
        quality_score = test_quality(verbose=True, dst_name="rank"+str(i))
        qss.append(quality_score)
    # 如果下面得分较差, 说明截图脚本有问题, 没有保证截到相同条件下的
    # 由于保密条纹等原因, 似乎差别是会存在, base 图可能需要在过程中更新
    print("质量得分: ", qss)
