import cv2
import numpy as np
import math

def find_checkerboard(image_path):
    image = cv2.imread(image_path)
    if image is None:
        return
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Adaptive threshold to find black squares regardless of lighting
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 21, 10)
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    squares = []
    for cnt in contours:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.05 * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            area = cv2.contourArea(approx)
            if 100 < area < 10000:
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
                    if dist < 15: # if corners are within 15 pixels, they might be touching
                        # Check if their centers are diagonally separated
                        center1 = np.mean(sq1, axis=0)
                        center2 = np.mean(sq2, axis=0)
                        center_dist = math.hypot(center1[0]-center2[0], center1[1]-center2[1])
                        
                        # Expected center distance is roughly sqrt(2) * side_length
                        # Area = side^2 -> side = sqrt(area)
                        side1 = math.sqrt(cv2.contourArea(sq1))
                        side2 = math.sqrt(cv2.contourArea(sq2))
                        avg_side = (side1 + side2) / 2
                        
                        expected_dist = avg_side * math.sqrt(2)
                        
                        if abs(center_dist - expected_dist) < avg_side * 0.4:
                            if dist < min_dist:
                                min_dist = dist
                                best_pair = (sq1, sq2)
                                
    if best_pair:
        print("Found touching black squares!")
        sq1, sq2 = best_pair
        for idx, pt in enumerate(sq1):
            print(f"Sq1 pt{idx}: {pt}")
        for idx, pt in enumerate(sq2):
            print(f"Sq2 pt{idx}: {pt}")
    else:
        print("No checkerboard pair found.")

if __name__ == '__main__':
    find_checkerboard("../TestImages/Box/box1.png")
