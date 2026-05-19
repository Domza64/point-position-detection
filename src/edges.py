import cv2

# Load image
image = cv2.imread('TestImages/Box/box7.png')
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

# FAST corner detection
fast = cv2.FastFeatureDetector_create()
keypoints = fast.detect(gray, None)

# Draw keypoints
image = cv2.drawKeypoints(image, keypoints, None, color=(255, 0, 0))

# Show result
cv2.imshow('FAST Corners', image)
cv2.waitKey(0)