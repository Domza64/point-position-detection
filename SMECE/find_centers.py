import cv2
import numpy as np
import os
import sys

def get_best_2x2_center(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return None
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Detektiramo najjače kuteve (najjači saddle spoj na 2x2 šahovnici je uvijek na 1. mjestu po kvaliteti)
    corners = cv2.goodFeaturesToTrack(gray, maxCorners=1, qualityLevel=0.01, minDistance=10)
    
    if corners is not None:
        corners = np.float32(corners)
        
        # Rafiniranje na sub-pixel preciznost
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.001)
        refined_corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        
        x, y = refined_corners[0].ravel()
        return float(x), float(y)
    return None

def process_folder(folder_path):
    if not os.path.exists(folder_path):
        print(f"[ERROR] Mapa '{folder_path}' ne postoji.")
        return
        
    print(f"\n===== REZULTATI DETEKCIJE ZA MAPU: {folder_path} =====")
    files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    
    # Sort files numerically if they have numbers (e.g. entrance1, entrance10, entrance12)
    def get_num(p):
        import re
        nums = re.findall(r'\d+', p)
        return int(nums[0]) if nums else 0
    files.sort(key=get_num)
    
    for file in files:
        img_path = os.path.join(folder_path, file)
        coords = get_best_2x2_center(img_path)
        if coords:
            print(f"{file} -> X = {coords[0]:.4f}, Y = {coords[1]:.4f}")
        else:
            print(f"{file} -> Nije pronađen centar šahovnice")

if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else r"TestImages\Entrance"
    process_folder(folder)
