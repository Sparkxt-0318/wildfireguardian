# Perturbation probe (not product code): force OpenCV's non-SIMD code paths for this process.
import cv2
cv2.setUseOptimized(False)
