import os
import re
import cv2
import numpy as np
import sys

# Copy functions from triangulate.py to test
from triangulate import load_cameras, get_line_equation, triangulate_rays

def debug_pair(dataset_name, cid1, cid2):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_dir = os.path.join(base_dir, "TestImages", dataset_name.capitalize())
    
    input_file = os.path.join(dataset_dir, f"{dataset_name.lower()}Input.txt")
    cameras = load_cameras(input_file)
    
    cam1 = cameras[cid1]
    cam2 = cameras[cid2]
    
    # Load images
    img1_path = os.path.join(dataset_dir, f"{dataset_name.lower()}{cid1}.png")
    img2_path = os.path.join(dataset_dir, f"{dataset_name.lower()}{cid2}.png")
    if not os.path.exists(img1_path):
        img1_path = img1_path.replace(".png", ".jpg")
        img2_path = img2_path.replace(".png", ".jpg")
        
    img1 = cv2.imread(img1_path)
    img2 = cv2.imread(img2_path)
    h, w, _ = img1.shape
    
    # Try different SIFT configurations to get more points
    sift = cv2.SIFT_create(nfeatures=8000, contrastThreshold=0.01, edgeThreshold=20)
    kp1, des1 = sift.detectAndCompute(img1, None)
    kp2, des2 = sift.detectAndCompute(img2, None)
    
    print(f"SIFT Features detected: Cam {cid1} = {len(kp1)}, Cam {cid2} = {len(kp2)}")
    
    bf = cv2.BFMatcher(cv2.NORM_L2)
    matches = bf.knnMatch(des1, des2, k=2)
    
    good_matches = []
    for m, n in matches:
        if m.distance < 0.75 * n.distance:
            good_matches.append(m)
            
    print(f"Good matches: {len(good_matches)}")
    
    errors = []
    depths = []
    valid_count = 0
    
    for match in good_matches:
        u1, v1 = kp1[match.queryIdx].pt
        u2, v2 = kp2[match.trainIdx].pt
        
        p1, d1 = get_line_equation(v1, u1, w, h, cam1)
        p2, d2 = get_line_equation(v2, u2, w, h, cam2)
        
        pt_3d, err, t1, t2 = triangulate_rays(p1, d1, p2, d2)
        if pt_3d is not None:
            errors.append(err)
            depths.append((t1, t2))
            
            avg_depth = (t1 + t2) / 2.0
            max_allowed_err = max(1.0, avg_depth * 0.02)
            if t1 > 0 and t2 > 0 and err < max_allowed_err:
                valid_count += 1
                
    errors = np.array(errors)
    if len(errors) > 0:
        print(f"Min error: {np.min(errors):.4f}")
        print(f"Max error: {np.max(errors):.4f}")
        print(f"Mean error: {np.mean(errors):.4f}")
        print(f"Median error: {np.median(errors):.4f}")
        print(f"Valid points (passing depth & error threshold): {valid_count} / {len(errors)}")
        
        # Print a few examples
        print("\nExamples of (Depth1, Depth2, Ray Error):")
        for i in range(min(10, len(errors))):
            t1, t2 = depths[i]
            print(f"  Match {i+1}: t1={t1:.2f}, t2={t2:.2f}, err={errors[i]:.4f}")

if __name__ == "__main__":
    debug_pair("statue", 1, 2)
