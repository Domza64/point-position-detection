import cv2
import numpy as np

def find_calibration_checkerboard(image_path):
    image = cv2.imread(image_path)
    if image is None:
        print(f"Cannot read {image_path}")
        return
        
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Common calibration checkerboard sizes (inner corners)
    # E.g. a 9x7 checkerboard has 8x6 inner corners
    common_sizes = [
        (9, 6), (8, 6), (7, 6), (7, 5), (6, 5), (5, 4), (4, 3), (3, 3)
    ]
    
    for pattern_size in common_sizes:
        found, corners = cv2.findChessboardCorners(gray, pattern_size, None)
        if found:
            print(f"SUCCESS! Found checkerboard of size {pattern_size} in {image_path}!")
            # Refine corner locations
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            
            # Extract the 4 OUTERMOST corners of the checkerboard pattern
            # These are usually the top-left, top-right, bottom-right, bottom-left of the inner grid
            w, h = pattern_size
            tl = corners[0][0]
            tr = corners[w - 1][0]
            bl = corners[(h - 1) * w][0]
            br = corners[-1][0]
            
            print("The 4 outer corners are:")
            print(f"  TL: {tl}")
            print(f"  TR: {tr}")
            print(f"  BL: {bl}")
            print(f"  BR: {br}")
            return
            
    print(f"No checkerboard pattern found in {image_path} using standard sizes.")

if __name__ == '__main__':
    find_calibration_checkerboard("../TestImages/Box/box1.png")
