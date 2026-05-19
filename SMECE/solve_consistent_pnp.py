import os
import sys
import cv2
import numpy as np
import math
import glob
import re

# Add directories to path to import PnP solver and auto_pnp
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "point-position-detection"))
from PnP.pnp_solver import CameraPoseSolver
from auto_pnp import order_square_corners, find_checkerboard_in_gray

def solve_candidate_pose(sq1, sq2, touch1, touch2, c1_m, c2_m, solver, gray, swap_squares=False):
    # If swap_squares is True, we map sq1 to negative square and sq2 to positive square
    if not swap_squares:
        pts3d_1, pts2d_1 = order_square_corners(sq1, touch1, c1_m, True)
        pts3d_2, pts2d_2 = order_square_corners(sq2, touch2, c2_m, False)
    else:
        # Swap assignments
        pts3d_1, pts2d_1 = order_square_corners(sq1, touch1, c1_m, False)
        pts3d_2, pts2d_2 = order_square_corners(sq2, touch2, c2_m, True)
        
    pts_3d = pts3d_1 + pts3d_2
    pts_2d = pts2d_1 + pts2d_2
    
    return solver.solve_pose(pts_3d, pts_2d)

def run_consistent_pnp():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    test_images_dir = os.path.join(base_dir, "TestImages")
    
    for dataset in ["Fountain", "Statue"]:
        print(f"\n[+] Processing {dataset} with Pose Consistency Tracking...")
        dataset_dir = os.path.join(test_images_dir, dataset)
        if not os.path.exists(dataset_dir): continue
        
        # Clear/initialize input file
        input_file = os.path.join(dataset_dir, f"{dataset.lower()}Input.txt")
        with open(input_file, "w", encoding="utf-8") as f:
            f.write("(camera field of view is always 90 degrees)\n")
            
        try:
            solver = CameraPoseSolver(dataset_dir)
        except Exception as e:
            print(f"[-] Cannot initialize solver: {e}")
            continue
            
        images = glob.glob(os.path.join(dataset_dir, "*.jpg")) + glob.glob(os.path.join(dataset_dir, "*.png"))
        
        # Sort images by camera index
        def get_num(p):
            name = os.path.basename(p)
            nums = re.findall(r'\d+', name)
            return int(nums[0]) if nums else 0
        images.sort(key=get_num)
        
        previous_pose = None
        
        for img_path in images:
            cid = get_num(img_path)
            image = cv2.imread(img_path)
            if image is None: continue
            
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Find checkerboard
            best_pair, touch1, touch2 = find_checkerboard_in_gray(gray, use_adaptive=False)
            if not best_pair:
                best_pair, touch1, touch2 = find_checkerboard_in_gray(gray, use_adaptive=True)
                
            if not best_pair:
                print(f"  [-] Target not found in {os.path.basename(img_path)}")
                continue
                
            sq1, sq2 = best_pair
            c1_m = np.mean(sq1, axis=0)
            c2_m = np.mean(sq2, axis=0)
            
            # Sub-pixel corner refinement
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.001)
            sq1 = cv2.cornerSubPix(gray, sq1.reshape(-1, 1, 2).astype(np.float32), (8, 8), (-1, -1), criteria).reshape(4, 2)
            sq2 = cv2.cornerSubPix(gray, sq2.reshape(-1, 1, 2).astype(np.float32), (8, 8), (-1, -1), criteria).reshape(4, 2)
            
            # Solve both candidate poses
            try:
                pose1 = solve_candidate_pose(sq1, sq2, touch1, touch2, c1_m, c2_m, solver, gray, swap_squares=False)
                pose2 = solve_candidate_pose(sq1, sq2, touch1, touch2, c1_m, c2_m, solver, gray, swap_squares=True)
            except Exception as e:
                print(f"  [-] Error solving PnP for {os.path.basename(img_path)}: {e}")
                continue
                
            # Choose the correct pose
            chosen_pose = None
            if previous_pose is None:
                # For the first camera, select the one that makes camera look at the target (Z < 0 relative to target)
                # Usually pose1 is fine, but let's prefer Z < 0
                if pose1['position'][2] < 0:
                    chosen_pose = pose1
                    print(f"  [*] Initial camera {cid}: picked Pose 1 (Z={pose1['position'][2]:.2f})")
                else:
                    chosen_pose = pose2
                    print(f"  [*] Initial camera {cid}: picked Pose 2 (Z={pose2['position'][2]:.2f})")
            else:
                # Compare to previous pose using distance and orientation dot product
                dist1 = np.linalg.norm(pose1['position'] - previous_pose['position'])
                dist2 = np.linalg.norm(pose2['position'] - previous_pose['position'])
                
                dot1 = np.dot(pose1['forward'], previous_pose['forward'])
                dot2 = np.dot(pose2['forward'], previous_pose['forward'])
                
                # Combine metric: smaller distance and dot product close to 1
                # (since dot product can be negative if flipped, we want to maximize dot)
                score1 = -dist1 + 1000 * dot1
                score2 = -dist2 + 1000 * dot2
                
                if score1 > score2:
                    chosen_pose = pose1
                    # print(f"  [+] Cam {cid}: Pose 1 (dist={dist1:.1f}, dot={dot1:.2f})")
                else:
                    chosen_pose = pose2
                    # print(f"  [+] Cam {cid}: Pose 2 (dist={dist2:.1f}, dot={dot2:.2f})")
            
            previous_pose = chosen_pose
            solver.save_camera_to_input_file(str(cid), chosen_pose)
            print(f"  [+] Solved and saved Cam {cid}")

if __name__ == "__main__":
    run_consistent_pnp()
