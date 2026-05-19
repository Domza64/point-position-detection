import os
import sys
import cv2
import numpy as np
import math
import glob

# Add parent directory to path to import PnP solver
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PnP.pnp_solver import CameraPoseSolver

def order_square_corners(sq, touch_idx, center_pt, is_sq1):
    pts_3d = [None] * 4
    pts_2d = [None] * 4
    
    # touch_idx maps to [0, 0, 0]
    pts_3d[touch_idx] = [0, 0, 0]
    pts_2d[touch_idx] = sq[touch_idx]
    
    # diagonally opposite maps to [100, 100, 0] (sq1) or [-100, -100, 0] (sq2)
    diag_idx = (touch_idx + 2) % 4
    pts_3d[diag_idx] = [100, 100, 0] if is_sq1 else [-100, -100, 0]
    pts_2d[diag_idx] = sq[diag_idx]
    
    # side points
    side1_idx = (touch_idx + 1) % 4
    side2_idx = (touch_idx + 3) % 4
    
    # Determine orientation of side points using cross product
    touch_pt = sq[touch_idx]
    vec_c = center_pt - touch_pt
    vec_a = sq[side1_idx] - touch_pt
    
    cross = vec_c[0]*vec_a[1] - vec_c[1]*vec_a[0]
    if cross < 0:
        pts_3d[side1_idx] = [100, 0, 0] if is_sq1 else [-100, 0, 0]
        pts_3d[side2_idx] = [0, 100, 0] if is_sq1 else [0, -100, 0]
    else:
        pts_3d[side1_idx] = [0, 100, 0] if is_sq1 else [0, -100, 0]
        pts_3d[side2_idx] = [100, 0, 0] if is_sq1 else [-100, 0, 0]
        
    pts_2d[side1_idx] = sq[side1_idx]
    pts_2d[side2_idx] = sq[side2_idx]
    
    return pts_3d, pts_2d

def find_checkerboard_in_gray(gray, use_adaptive=False):
    if use_adaptive:
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 21, 10)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    else:
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        
    squares = []
    for cnt in contours:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.05 * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            area = cv2.contourArea(approx)
            if 50 < area < 20000:
                squares.append(approx.reshape(4, 2).astype(np.float32))
                
    best_pair = None
    min_dist = float('inf')
    touch1, touch2 = -1, -1
    
    for i in range(len(squares)):
        for j in range(i+1, len(squares)):
            sq1 = squares[i]
            sq2 = squares[j]
            for idx1, c1 in enumerate(sq1):
                for idx2, c2 in enumerate(sq2):
                    dist = math.hypot(c1[0]-c2[0], c1[1]-c2[1])
                    if dist < 30:
                        c1_m = np.mean(sq1, axis=0)
                        c2_m = np.mean(sq2, axis=0)
                        center_dist = math.hypot(c1_m[0]-c2_m[0], c1_m[1]-c2_m[1])
                        
                        area1 = cv2.contourArea(sq1)
                        area2 = cv2.contourArea(sq2)
                        side1 = math.sqrt(area1) if area1 > 0 else 0.1
                        side2 = math.sqrt(area2) if area2 > 0 else 0.1
                        
                        # Size ratio check (squares must be within 30% of each other's size)
                        ratio = max(side1, side2) / min(side1, side2)
                        if ratio > 1.3:
                            continue
                            
                        avg_side = (side1 + side2) / 2
                        expected_dist = avg_side * math.sqrt(2)
                        if abs(center_dist - expected_dist) < avg_side * 0.4:
                            if dist < min_dist:
                                min_dist = dist
                                best_pair = (sq1, sq2)
                                touch1, touch2 = idx1, idx2
                                
    return best_pair, touch1, touch2

def process_image(image_path, solver, camera_id):
    image = cv2.imread(image_path)
    if image is None: return False
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 1. Try global Otsu thresholding first
    best_pair, touch1, touch2 = find_checkerboard_in_gray(gray, use_adaptive=False)
    
    # 2. Fall back to adaptive thresholding if nothing found
    if not best_pair:
        best_pair, touch1, touch2 = find_checkerboard_in_gray(gray, use_adaptive=True)
        
    if not best_pair:
        print(f"  [-] Target not found in {os.path.basename(image_path)}")
        return False
        
    sq1, sq2 = best_pair
    c1_m = np.mean(sq1, axis=0)
    c2_m = np.mean(sq2, axis=0)
    
    if c1_m[0] < c2_m[0]:
        sq1, sq2 = sq2, sq1
        c1_m, c2_m = c2_m, c1_m
        touch1, touch2 = touch2, touch1
        
    # Refine corners to sub-pixel accuracy before ordering them
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.001)
    sq1 = cv2.cornerSubPix(gray, sq1.reshape(-1, 1, 2).astype(np.float32), (8, 8), (-1, -1), criteria).reshape(4, 2)
    sq2 = cv2.cornerSubPix(gray, sq2.reshape(-1, 1, 2).astype(np.float32), (8, 8), (-1, -1), criteria).reshape(4, 2)

    pts3d_1, pts2d_1 = order_square_corners(sq1, touch1, c1_m, True)
    pts3d_2, pts2d_2 = order_square_corners(sq2, touch2, c2_m, False)
    
    # Combine
    pts_3d = pts3d_1 + pts3d_2
    pts_2d = pts2d_1 + pts2d_2
    
    # Solve PnP
    try:
        pose = solver.solve_pose(pts_3d, pts_2d)
        solver.save_camera_to_input_file(camera_id, pose)
        print(f"  [+] Solved and saved {os.path.basename(image_path)}")
        return True
    except Exception as e:
        print(f"  [-] Error solving {os.path.basename(image_path)}: {e}")
        return False

def run_all():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_images_dir = os.path.join(base_dir, "TestImages")
    
    for dataset in ["Fountain", "Statue"]:
        print(f"\nProcessing {dataset}...")
        dataset_dir = os.path.join(test_images_dir, dataset)
        if not os.path.exists(dataset_dir): continue
        
        # Remove old input file if exists to start fresh
        input_file = os.path.join(dataset_dir, f"{dataset.lower()}Input.txt")
        if os.path.exists(input_file):
            # Write the header first
            with open(input_file, "w", encoding="utf-8") as f:
                f.write("(camera field of view is always 90 degrees)\n")
        else:
            with open(input_file, "w", encoding="utf-8") as f:
                f.write("(camera field of view is always 90 degrees)\n")
                
        try:
            solver = CameraPoseSolver(dataset_dir)
        except Exception as e:
            print(f"Cannot initialize solver: {e}")
            continue
            
        images = glob.glob(os.path.join(dataset_dir, "*.jpg")) + glob.glob(os.path.join(dataset_dir, "*.png"))
        
        # Sort images by number
        def get_num(p):
            name = os.path.basename(p)
            import re
            nums = re.findall(r'\d+', name)
            return int(nums[0]) if nums else 0
        images.sort(key=get_num)
        
        for img_path in images:
            cid = get_num(img_path)
            process_image(img_path, solver, str(cid))

if __name__ == '__main__':
    run_all()
