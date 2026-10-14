"""Find the iPad screen in the camera picture, rectify it to source coordinates, read the codes.

The four ArUco markers of a prepared booth clip have known positions in source pixels, so
a homography from camera pixels to source pixels follows from their corners. Markers are
searched every `redetect_every` frames (and whenever a code read fails), otherwise the
last homography is reused, because the tripod is still.

Per camera frame this gives:
- the analysis image: the screen warped to source coordinates at analysis resolution,
  with the corner blocks masked;
- the decoded frame code (clean, blended or torn) read at full source resolution from
  four small warps of the corner blocks only.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from wfglink.screen.codes import CORNER_IDS, DICT, FrameCode, Layout, read_frame_code


@dataclass
class Rectified:
    image: np.ndarray | None        # analysis image (source coordinates scaled by `scale`)
    mask: np.ndarray | None         # uint8, nonzero = ignore (corner blocks)
    code: FrameCode | None
    scale: float                    # analysis pixels per source pixel
    markers_found: int
    homography: np.ndarray | None   # camera -> source pixels


class ScreenRectifier:
    def __init__(self, layout: Layout, analysis_max_width: int = 1280, redetect_every: int = 15):
        self.layout = layout
        self.scale = min(1.0, analysis_max_width / layout.width)
        self.out_size = (int(round(layout.width * self.scale)), int(round(layout.height * self.scale)))
        self.redetect_every = max(1, int(redetect_every))
        params = cv2.aruco.DetectorParameters()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        self.detector = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(DICT), params)
        self.H: np.ndarray | None = None
        self._frames_since = 10 ** 9
        self.markers_found = 0
        src_mask = layout.mask()
        self.mask = cv2.resize(src_mask, self.out_size, interpolation=cv2.INTER_NEAREST)
        self._block_warps = [self._block_affine(c) for c in range(4)]

    def _block_affine(self, corner: int) -> tuple[np.ndarray, tuple[int, int], tuple[int, int]]:
        bx, by = self.layout.block_origin(corner)
        T = np.array([[1, 0, -bx], [0, 1, -by], [0, 0, 1]], np.float64)
        return T, (self.layout.block_w, self.layout.block_h), (bx, by)

    def detect(self, gray: np.ndarray) -> int:
        corners, ids, _ = self.detector.detectMarkers(gray)
        if ids is None:
            return 0
        cam, src = [], []
        for c, mid in zip(corners, ids.ravel()):
            if int(mid) in CORNER_IDS:
                cam.append(c.reshape(4, 2))
                src.append(self.layout.marker_corners(CORNER_IDS.index(int(mid))))
        if len(cam) < 2:
            return len(cam)
        cam_pts = np.concatenate(cam).astype(np.float32)
        src_pts = np.concatenate(src).astype(np.float32)
        H, _ = cv2.findHomography(cam_pts, src_pts, cv2.RANSAC, 3.0)
        if H is not None:
            self.H = H
        return len(cam)

    def process(self, frame_bgr: np.ndarray) -> Rectified:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        self._frames_since += 1
        if self.H is None or self._frames_since >= self.redetect_every:
            self.markers_found = self.detect(gray)
            self._frames_since = 0
        if self.H is None:
            return Rectified(None, None, None, self.scale, self.markers_found, None)
        code = self._read_code(gray)
        if (code.index is None or not any(c.parity_ok for c in code.corners)) and self._frames_since > 0:
            # Lost lock (tripod bumped?): search again right away.
            self.markers_found = self.detect(gray)
            self._frames_since = 0
            code = self._read_code(gray)
        S = np.diag([self.scale, self.scale, 1.0])
        image = cv2.warpPerspective(frame_bgr, S @ self.H, self.out_size, flags=cv2.INTER_AREA if self.scale < 1 else cv2.INTER_LINEAR)
        return Rectified(image, self.mask, code, self.scale, self.markers_found, self.H)

    def _read_code(self, gray: np.ndarray) -> FrameCode:
        canvas = np.zeros((self.layout.height, self.layout.width), np.uint8)
        for T, (bw, bh), (bx, by) in self._block_warps:
            block = cv2.warpPerspective(gray, T @ self.H, (bw, bh), flags=cv2.INTER_LINEAR)
            canvas[by:by + bh, bx:bx + bw] = block
        return read_frame_code(canvas, self.layout)
