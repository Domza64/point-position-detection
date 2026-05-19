import cv2
import numpy as np
import math

def find_checkerboard(image_path):
    image = cv2.imread(image_path)
    if image is None:
        return
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Use Otsu's thresholding to separate black squares from white/brown background
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    squares = []
    for cnt in contours:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.05 * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            area = cv2.contourArea(approx)
            if 100 < area < 20000:
                squares.append(approx.reshape(4, 2))
                
    print(f"Found {len(squares)} potential black squares in {image_path}")
    
    # Check all pairs of squares to find two that share exactly one corner
    best_pair = None
    min_dist = float('inf')
    
    for i in range(len(squares)):
        for j in range(i+1, len(squares)):
            sq1 = squares[i]
            sq2 = squares[j]
            
            # Find the minimum distance between any corner of sq1 and any corner of sq2
            for c1 in sq1:
                for c2 in sq2:
                    dist = math.hypot(c1[0]-c2[0], c1[1]-c2[1])
                    if dist < 30: # increased threshold for touching corners under perspective
                        # Check if their centers are diagonally separated
                        center1 = np.mean(sq1, axis=0)
                        center2 = np.mean(sq2, axis=0)
                        center_dist = math.hypot(center1[0]-center2[0], center1[1]-center2[1])
                        
                        side1 = math.sqrt(cv2.contourArea(sq1))
                        side2 = math.sqrt(cv2.contourArea(sq2))
                        avg_side = (side1 + side2) / 2
                        
                        expected_dist = avg_side * math.sqrt(2)
                        
                        if abs(center_dist - expected_dist) < avg_side * 0.6:
                            if dist < min_dist:
                                min_dist = dist
                                best_pair = (sq1, sq2)
                                
    if best_pair:
        print("SUCCESS! Found touching black squares forming the checkerboard!")
        sq1, sq2 = best_pair
        
        # Draw them
        vis = image.copy()
        cv2.drawContours(vis, [np.int32(sq1)], 0, (0, 0, 255), 3)
        cv2.drawContours(vis, [np.int32(sq2)], 0, (0, 255, 0), 3)
        
        # The 4 outer points of the target are the corners of sq1 and sq2 
        # that are furthest from the touching corner!
        # Find the touching corner pair
        min_d = float('inf')
        touch1, touch2 = -1, -1
        for idx1, c1 in enumerate(sq1):
            for idx2, c2 in enumerate(sq2):
                d = math.hypot(c1[0]-c2[0], c1[1]-c2[1])
                if d < min_d:
                    min_d = d
                    touch1, touch2 = idx1, idx2
        
        # The outer corner of sq1 is diagonally opposite to touch1
        outer1 = sq1[(touch1 + 2) % 4]
        # The outer corner of sq2 is diagonally opposite to touch2
        outer2 = sq2[(touch2 + 2) % 4]
        
        # The other two outer corners are the remaining corners of sq1 and sq2
        other_sq1_1 = sq1[(touch1 + 1) % 4]
        other_sq1_2 = sq1[(touch1 + 3) % 4]
        other_sq2_1 = sq2[(touch2 + 1) % 4]
        other_sq2_2 = sq2[(touch2 + 3) % 4]
        
        print("Outer corners of the target:")
        print(f"  P1 (Outer Sq1): {outer1}")
        print(f"  P2 (Outer Sq2): {outer2}")
        print(f"  P3 (Side Sq1 A): {other_sq1_1}")
        print(f"  P4 (Side Sq1 B): {other_sq1_2}")
        print(f"  P5 (Side Sq2 A): {other_sq2_1}")
        print(f"  P6 (Side Sq2 B): {other_sq2_2}")
        
    else:
        print("No checkerboard pair found.")

if __name__ == '__main__':
    find_checkerboard("../TestImages/Box/box1.png")
