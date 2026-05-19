import os
import sys
import cv2
import numpy as np
import re

# Add path to import PnP solver and auto_pnp
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "point-position-detection"))
from PnP.pnp_solver import CameraPoseSolver
from auto_pnp import order_square_corners, find_checkerboard_in_gray
from solve_consistent_pnp import solve_candidate_pose

def test_box():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_dir = os.path.join(base_dir, "TestImages", "Box")
    
    # Load ground truth cameras
    from triangulate import load_cameras
    gt_cameras = load_cameras(os.path.join(dataset_dir, "boxInput.txt"))
    
    solver = CameraPoseSolver(dataset_dir)
    
    # Test on camera 1
    img_path = os.path.join(dataset_dir, "box1.png")
    image = cv2.imread(img_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Find contours for the single square target in Box dataset
    # Otsu thresholding
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    # Find the square contour
    sq = None
    for cnt in contours:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.05 * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            area = cv2.contourArea(approx)
            if 1000 < area < 50000:
                sq = approx.reshape(4, 2).astype(np.float32)
                break
                
    if sq is None:
        print("[-] Target square not found in box1.png")
        return
        
    # Refine corners
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.001)
    sq = cv2.cornerSubPix(gray, sq.reshape(-1, 1, 2).astype(np.float32), (8, 8), (-1, -1), criteria).reshape(4, 2)
    
    # Ground truth 3D points from box.csv
    # -25,-27,249 (bottom-left)
    # 25,-25,250 (bottom-right)
    # 25,26,251 (top-right)
    # -25,22,249 (top-left)
    pts_3d_gt = np.array([
        [-25, -27, 249],
        [25, -25, 250],
        [25, 26, 251],
        [-25, 22, 249]
    ], dtype=np.float64)
    
    # Find the top-left index of the detected 2D square to align with pts_3d_gt
    # We can try all 4 cyclic shifts of the 2D points to find the correct alignment
    gt = gt_cameras[1]
    print("Ground Truth Pose:")
    print(f"  Position: {gt['position']}")
    print(f"  Forward:  {gt['forward']}")
    print(f"  Right:    {gt['right']}")
    print(f"  Up:       {gt['up']}")
    
    print("\nTrying 4 cyclic shifts and both winding orders:")
    for shift in range(4):
        for reverse in [False, True]:
            pts_2d_temp = np.roll(sq, -shift, axis=0)
            if reverse:
                pts_2d_temp = pts_2d_temp[::-1]
                
            pose = solver.solve_pose(pts_3d_gt, pts_2d_temp)
            pos_diff = np.linalg.norm(pose['position'] - gt['position'])
            fwd_dot = np.dot(pose['forward'], gt['forward'])
            
            print(f"  Shift {shift}, Reverse={reverse}: pos_diff={pos_diff:.4f}, fwd_dot={fwd_dot:.4f}")
            if pos_diff < 5.0 and fwd_dot > 0.99:
                print(f"    [+] SUCCESS! Shift {shift}, Reverse={reverse} matches ground truth!")
                print(f"    Position: {pose['position']}")
                print(f"    Forward:  {pose['forward']}")
                print(f"    Right:    {pose['right']}")
                print(f"    Up:       {pose['up']}")

if __name__ == "__main__":
    test_box()
