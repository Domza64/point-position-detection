# https://blog.finxter.com/5-best-ways-to-find-patterns-in-a-chessboard-using-opencv-python/

import cv2
import numpy as np

# Load image
image = cv2.imread("TestImages/Box/box7.png")
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

# Harris corner detection
gray = np.float32(gray)
dst = cv2.cornerHarris(gray, 2, 3, 0.04)

# Result is dilated for marking the corners
dst = cv2.dilate(dst, None)

# Only keep areas with large corner responses
image[dst > 0.01 * dst.max()] = [0, 0, 255]

# Show result
cv2.imshow('Harris Corners', image)
cv2.waitKey(0)