import cv2
import numpy as np

def find_checkerboard_targets(image_path):
    image = cv2.imread(image_path)
    if image is None:
        print(f"Cannot read {image_path}")
        return
        
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Preprocessing
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    
    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    targets = []
    
    for cnt in contours:
        # Approximate contour
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        
        # If the contour has 4 points and is convex
        if len(approx) == 4 and cv2.isContourConvex(approx):
            area = cv2.contourArea(approx)
            # Filter by area to avoid noise and huge boxes
            if 400 < area < 50000:
                # Warp perspective to a perfect square to check the 2x2 pattern
                pts = approx.reshape(4, 2).astype(np.float32)
                
                # Order points (top-left, top-right, bottom-right, bottom-left)
                s = pts.sum(axis=1)
                diff = np.diff(pts, axis=1)
                
                ordered = np.zeros((4, 2), dtype=np.float32)
                ordered[0] = pts[np.argmin(s)]       # top-left
                ordered[2] = pts[np.argmax(s)]       # bottom-right
                ordered[1] = pts[np.argmin(diff)]    # top-right
                ordered[3] = pts[np.argmax(diff)]    # bottom-left
                
                # Warp to 100x100 square
                dst_pts = np.array([[0, 0], [99, 0], [99, 99], [0, 99]], dtype=np.float32)
                M = cv2.getPerspectiveTransform(ordered, dst_pts)
                warped = cv2.warpPerspective(gray, M, (100, 100))
                
                # Divide into 4 quadrants
                q1 = warped[0:50, 0:50]     # Top-left
                q2 = warped[0:50, 50:100]   # Top-right
                q3 = warped[50:100, 0:50]   # Bottom-left
                q4 = warped[50:100, 50:100] # Bottom-right
                
                # Calculate mean intensities
                m1 = np.mean(q1)
                m2 = np.mean(q2)
                m3 = np.mean(q3)
                m4 = np.mean(q4)
                
                # Check for checkerboard pattern:
                # Condition A: q1 and q4 are dark, q2 and q3 are bright
                # Condition B: q1 and q4 are bright, q2 and q3 are dark
                diff_A = abs(m1 - m4) + abs(m2 - m3)
                contrast_A = abs((m1+m4)/2 - (m2+m3)/2)
                
                print(f"  Quad area {area}: m1={m1:.1f}, m2={m2:.1f}, m3={m3:.1f}, m4={m4:.1f}, contrast={contrast_A:.1f}, diff_A={diff_A:.1f}")
                
                if contrast_A > 30 and diff_A < contrast_A * 1.5:
                    targets.append(ordered)
                    
    print(f"Found {len(targets)} targets in {image_path}")
    for i, t in enumerate(targets):
        print(f"Target {i+1} corners:")
        for pt in t:
            print(f"  [{pt[0]}, {pt[1]}]")

if __name__ == '__main__':
    find_checkerboard_targets("../TestImages/Box/box1.png")
