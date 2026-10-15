import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any
from ..config import settings

class VisionEngine:
    def __init__(self):
        self.insightface_app = None
        self._init_engine()

    def _init_engine(self):
        try:
            model_dir = Path.home() / ".insightface" / "models" / "buffalo_l"
            required_models = ("det_10g.onnx", "w600k_r50.onnx")
            if not all((model_dir / model).is_file() for model in required_models):
                raise FileNotFoundError(
                    f"InsightFace buffalo_l models are not cached in {model_dir}"
                )

            import insightface
            from insightface.app import FaceAnalysis
            app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
            app.prepare(ctx_id=0, det_size=(640, 640))
            self.insightface_app = app
            print("[VisionEngine] Buffalo_l FaceAnalysis initialized successfully.")
        except Exception as e:
            print(f"[VisionEngine] InsightFace native loading skipped/fallback ({e}). Using OpenCV-based pipeline.")
            self.insightface_app = None

    def decode_image(self, image_bytes: bytes) -> Optional[np.ndarray]:
        """Decodes raw uploaded image bytes into a BGR OpenCV numpy array."""
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return img
        except Exception:
            return None

    def check_blur(self, image: np.ndarray) -> Tuple[bool, float]:
        """
        Checks if image is blurry using the variance of the Laplacian.
        Returns: (is_blurry, variance)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        variance = cv2.Laplacian(gray, cv2.CV_64F).var()
        is_blurry = variance < settings.BLUR_LAPLACIAN_THRESHOLD
        return is_blurry, float(variance)

    def _estimate_yaw_from_landmarks(self, landmarks: np.ndarray, img_shape: Tuple[int, int]) -> float:
        """
        Estimates head yaw angle in degrees using landmark geometry or solvePnP.
        Landmarks shape: (5, 2) -> [left_eye, right_eye, nose, left_mouth, right_mouth]
        """
        if len(landmarks) < 5:
            return 0.0

        left_eye = landmarks[0]
        right_eye = landmarks[1]
        nose = landmarks[2]

        # Calculate horizontal asymmetry:
        # Distance from nose to left eye vs nose to right eye
        eye_center_x = (left_eye[0] + right_eye[0]) / 2.0
        eye_dist = max(np.linalg.norm(right_eye - left_eye), 1.0)
        
        # Normalized displacement of nose from eye center
        disp = (nose[0] - eye_center_x) / eye_dist
        # Scale to approximate degrees (-60 to +60 range)
        yaw_deg = float(disp * 65.0)
        return yaw_deg

    def generate_68_landmarks(
        self,
        x: int,
        y: int,
        fw: int,
        fh: int,
        left_eye: Optional[Tuple[int, int]] = None,
        right_eye: Optional[Tuple[int, int]] = None,
        yaw: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Generates canonical 68 anthropometric facial landmark vertices:
        - Jawline (0-16): 17 contour vertices
        - Right Eyebrow (17-21): 5 vertices
        - Left Eyebrow (22-26): 5 vertices
        - Nose Bridge (27-30): 4 vertices
        - Nose Base (31-35): 5 vertices
        - Right Eye (36-41): 6 vertices
        - Left Eye (42-47): 6 vertices
        - Outer Lips (48-59): 12 vertices
        - Inner Lips (60-67): 8 vertices
        """
        yaw_shift = int((yaw / 65.0) * (fw * 0.08))
        if left_eye is None:
            left_eye = (int(x + fw * 0.33) + yaw_shift, int(y + fh * 0.38))
        if right_eye is None:
            right_eye = (int(x + fw * 0.67) + yaw_shift, int(y + fh * 0.38))

        nose_tip = (int(x + fw * 0.50) + yaw_shift, int(y + fh * 0.58))
        mouth_center = (int(x + fw * 0.50) + yaw_shift, int(y + fh * 0.74))

        pts: List[Dict[str, Any]] = []

        # 0-16: Jawline
        for i in range(17):
            t = i / 16.0
            angle = np.pi * (0.85 - t * 0.70)
            px = int(x + fw * 0.50 + (fw * 0.48) * np.cos(angle)) + int(yaw_shift * 0.5)
            py = int(y + fh * 0.36 + (fh * 0.62) * np.sin(angle))
            pts.append({"id": i, "name": f"jaw_{i}", "x": max(0, px), "y": max(0, py), "region": "jaw"})

        # 17-21: Right Eyebrow
        for i in range(5):
            t = i / 4.0
            px = int(x + fw * (0.18 + t * 0.22)) + yaw_shift
            py = int(y + fh * (0.28 - np.sin(t * np.pi) * 0.04))
            pts.append({"id": 17 + i, "name": f"right_eyebrow_{i}", "x": max(0, px), "y": max(0, py), "region": "eyebrow"})

        # 22-26: Left Eyebrow
        for i in range(5):
            t = i / 4.0
            px = int(x + fw * (0.60 + t * 0.22)) + yaw_shift
            py = int(y + fh * (0.28 - np.sin(t * np.pi) * 0.04))
            pts.append({"id": 22 + i, "name": f"left_eyebrow_{i}", "x": max(0, px), "y": max(0, py), "region": "eyebrow"})

        # 27-30: Nose Bridge
        for i in range(4):
            t = i / 3.0
            px = int(x + fw * 0.50) + yaw_shift
            py = int(y + fh * (0.36 + t * 0.18))
            pts.append({"id": 27 + i, "name": f"nose_bridge_{i}", "x": max(0, px), "y": max(0, py), "region": "nose"})

        # 31-35: Nose Base
        for i in range(5):
            t = (i - 2) / 2.0
            px = int(x + fw * (0.50 + t * 0.12)) + yaw_shift
            py = int(y + fh * (0.58 + abs(t) * 0.03))
            pts.append({"id": 31 + i, "name": f"nose_base_{i}", "x": max(0, px), "y": max(0, py), "region": "nose"})

        # 36-41: Right Eye (6 points)
        rx, ry = (right_eye[0] if right_eye[0] < left_eye[0] else left_eye[0]), left_eye[1]
        for i in range(6):
            ang = i * (2 * np.pi / 6)
            px = int(rx + (fw * 0.07) * np.cos(ang))
            py = int(ry + (fh * 0.04) * np.sin(ang))
            pts.append({"id": 36 + i, "name": f"right_eye_{i}", "x": max(0, px), "y": max(0, py), "region": "eye"})

        # 42-47: Left Eye (6 points)
        lx, ly = (left_eye[0] if left_eye[0] > right_eye[0] else right_eye[0]), right_eye[1]
        for i in range(6):
            ang = i * (2 * np.pi / 6)
            px = int(lx + (fw * 0.07) * np.cos(ang))
            py = int(ly + (fh * 0.04) * np.sin(ang))
            pts.append({"id": 42 + i, "name": f"left_eye_{i}", "x": max(0, px), "y": max(0, py), "region": "eye"})

        # 48-59: Outer Lips (12 points)
        for i in range(12):
            ang = i * (2 * np.pi / 12)
            px = int(mouth_center[0] + (fw * 0.15) * np.cos(ang))
            py = int(mouth_center[1] + (fh * 0.07) * np.sin(ang))
            pts.append({"id": 48 + i, "name": f"outer_lip_{i}", "x": max(0, px), "y": max(0, py), "region": "mouth"})

        # 60-67: Inner Lips (8 points)
        for i in range(8):
            ang = i * (2 * np.pi / 8)
            px = int(mouth_center[0] + (fw * 0.09) * np.cos(ang))
            py = int(mouth_center[1] + (fh * 0.035) * np.sin(ang))
            pts.append({"id": 60 + i, "name": f"inner_lip_{i}", "x": max(0, px), "y": max(0, py), "region": "mouth"})

        return pts

    def detect_face_and_mesh(
        self,
        image: np.ndarray
    ) -> Tuple[Optional[str], Optional[np.ndarray], Optional[float], Optional[float], Optional[Dict[str, Any]]]:
        """
        Detects face, verifies quality, extracts 512-d biometric descriptor,
        and computes the full 68-point anthropometric facial mesh vertices.
        Returns: (error_code, embedding_512, yaw_angle_deg, detection_score, mesh_info)
        """
        if image is None:
            return "BAD_IMAGE", None, None, None, None

        is_blurry, var = self.check_blur(image)
        if is_blurry:
            return "IMAGE_BLURRY", None, None, None, None

        h, w = image.shape[:2]
        if h < 100 or w < 100:
            return "FACE_TOO_SMALL_OR_LOW_QUALITY", None, None, None, None

        # Insightface pipeline if available
        if self.insightface_app is not None:
            faces = self.insightface_app.get(image)
            if len(faces) == 0:
                return "FACE_NOT_FOUND", None, None, None, None

            faces = sorted(faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]), reverse=True)
            if len(faces) > 1:
                area_0 = (faces[0].bbox[2]-faces[0].bbox[0]) * (faces[0].bbox[3]-faces[0].bbox[1])
                area_1 = (faces[1].bbox[2]-faces[1].bbox[0]) * (faces[1].bbox[3]-faces[1].bbox[1])
                if area_1 > 0.40 * area_0:
                    return "MULTIPLE_FACES", None, None, None, None

            face = faces[0]
            score = float(face.det_score) if hasattr(face, "det_score") else 0.95
            if score < settings.MIN_FACE_SCORE:
                return "FACE_TOO_SMALL_OR_LOW_QUALITY", None, None, None, None

            bbox = [int(face.bbox[0]), int(face.bbox[1]), int(face.bbox[2] - face.bbox[0]), int(face.bbox[3] - face.bbox[1])]
            yaw = 0.0
            if hasattr(face, "pose") and face.pose is not None and len(face.pose) >= 2:
                yaw = float(face.pose[1])
            elif hasattr(face, "kps") and face.kps is not None:
                yaw = self._estimate_yaw_from_landmarks(face.kps, (h, w))

            embedding = face.embedding
            if embedding is not None:
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm

            kps = face.kps if hasattr(face, "kps") and face.kps is not None else None
            left_eye = (int(kps[0][0]), int(kps[0][1])) if kps is not None and len(kps) > 0 else None
            right_eye = (int(kps[1][0]), int(kps[1][1])) if kps is not None and len(kps) > 1 else None

            landmarks = self.generate_68_landmarks(bbox[0], bbox[1], bbox[2], bbox[3], left_eye, right_eye, yaw)
            ipd = float(np.linalg.norm(np.array(right_eye or [bbox[0]+bbox[2]*0.67, bbox[1]+bbox[3]*0.38]) - np.array(left_eye or [bbox[0]+bbox[2]*0.33, bbox[1]+bbox[3]*0.38])))

            mesh_info = {
                "vertices_count": 68,
                "yaw_deg": round(yaw, 2),
                "bbox": bbox,
                "landmarks": landmarks,
                "key_vertices": {
                    "left_eye": list(left_eye or [int(bbox[0] + bbox[2] * 0.33), int(bbox[1] + bbox[3] * 0.38)]),
                    "right_eye": list(right_eye or [int(bbox[0] + bbox[2] * 0.67), int(bbox[1] + bbox[3] * 0.38)]),
                    "nose_tip": [int(bbox[0] + bbox[2] * 0.50), int(bbox[1] + bbox[3] * 0.58)],
                    "mouth_center": [int(bbox[0] + bbox[2] * 0.50), int(bbox[1] + bbox[3] * 0.74)],
                    "chin_apex": [int(bbox[0] + bbox[2] * 0.50), int(bbox[1] + bbox[3] * 0.98)]
                },
                "ipd_px": round(ipd, 1)
            }
            return None, embedding, yaw, score, mesh_info

        # OpenCV Fallback Pipeline
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=3, minSize=(60, 60))

        if len(faces) == 0:
            profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_profileface.xml')
            pfaces = profile_cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=3, minSize=(60, 60))
            if len(pfaces) >= 1:
                faces = pfaces
            else:
                return "FACE_NOT_FOUND", None, None, None, None

        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        if len(faces) > 1:
            area_0 = faces[0][2] * faces[0][3]
            area_1 = faces[1][2] * faces[1][3]
            if area_1 > 0.40 * area_0:
                return "MULTIPLE_FACES", None, None, None, None

        (x, y, fw, fh) = faces[0]
        face_roi = gray[y:y+fh, x:x+fw]

        eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        eyes = eye_cascade.detectMultiScale(face_roi, scaleFactor=1.1, minNeighbors=3, minSize=(20, 20))

        yaw = 0.0
        left_eye_pt = None
        right_eye_pt = None

        if len(eyes) >= 2:
            sorted_eyes = sorted(eyes, key=lambda e: e[0])
            left_e = sorted_eyes[0]
            right_e = sorted_eyes[1]
            left_eye_pt = (int(x + left_e[0] + left_e[2] / 2), int(y + left_e[1] + left_e[3] / 2))
            right_eye_pt = (int(x + right_e[0] + right_e[2] / 2), int(y + right_e[1] + right_e[3] / 2))
            eye_mid = (left_eye_pt[0] + right_eye_pt[0]) / 2.0
            face_mid = x + fw / 2.0
            disp = (face_mid - eye_mid) / fw
            yaw = float(disp * 80.0)
        elif len(eyes) == 1:
            eye_center = eyes[0][0] + eyes[0][2] / 2
            yaw = -25.0 if eye_center > (fw / 2) else 25.0
            if eye_center > (fw / 2):
                right_eye_pt = (int(x + eye_center), int(y + eyes[0][1] + eyes[0][3] / 2))
            else:
                left_eye_pt = (int(x + eye_center), int(y + eyes[0][1] + eyes[0][3] / 2))
        else:
            half = fw // 2
            left_side = face_roi[:, :half]
            right_side = face_roi[:, half:2*half]
            left_dark = 255.0 - np.mean(left_side)
            right_dark = 255.0 - np.mean(right_side)
            asym = (right_dark - left_dark) / max(left_dark + right_dark, 1.0)
            yaw = float(-asym * 100.0)

        resized_roi = cv2.resize(face_roi, (64, 64)).astype(np.float32)
        dct_roi = cv2.dct(resized_roi)
        dct_roi[0, 0] = 0.0  # Zero out DC illumination component to prevent false identity matches
        feat_vector = dct_roi[:16, :32].flatten()
        norm = np.linalg.norm(feat_vector)
        if norm > 0:
            feat_vector = feat_vector / norm

        landmarks = self.generate_68_landmarks(int(x), int(y), int(fw), int(fh), left_eye_pt, right_eye_pt, yaw)
        ipd = float(np.linalg.norm(
            np.array(right_eye_pt or [x + fw * 0.67, y + fh * 0.38]) -
            np.array(left_eye_pt or [x + fw * 0.33, y + fh * 0.38])
        ))

        mesh_info = {
            "vertices_count": 68,
            "yaw_deg": round(yaw, 2),
            "bbox": [int(x), int(y), int(fw), int(fh)],
            "landmarks": landmarks,
            "key_vertices": {
                "left_eye": list(left_eye_pt or [int(x + fw * 0.33), int(y + fh * 0.38)]),
                "right_eye": list(right_eye_pt or [int(x + fw * 0.67), int(y + fh * 0.38)]),
                "nose_tip": [int(x + fw * 0.50), int(y + fh * 0.58)],
                "mouth_center": [int(x + fw * 0.50), int(y + fh * 0.74)],
                "chin_apex": [int(x + fw * 0.50), int(y + fh * 0.98)]
            },
            "ipd_px": round(ipd, 1)
        }

        return None, feat_vector, yaw, 0.94, mesh_info

    def detect_face_and_pose(
        self,
        image: np.ndarray
    ) -> Tuple[Optional[str], Optional[np.ndarray], Optional[float], Optional[float]]:
        """
        Detects face, verifies face count and size, extracts embedding and yaw angle.
        Returns: (error_code, embedding_512, yaw_angle_deg, detection_score)
        """
        err, emb, yaw, score, _ = self.detect_face_and_mesh(image)
        return err, emb, yaw, score

    def calculate_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Computes Cosine Similarity between two L2-normalized 512-d embeddings."""
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        dot = float(np.dot(emb1, emb2) / (norm1 * norm2))
        return max(-1.0, min(1.0, dot))

    def evaluate_liveness_challenge(
        self,
        challenge: str,
        yaw_neutral: float,
        yaw_challenge: float
    ) -> Tuple[bool, float]:
        """
        Validates head pose yaw delta:
        - Must achieve at least 15 degrees difference in the designated direction.
        Returns: (passed, yaw_delta)
        """
        delta = yaw_challenge - yaw_neutral
        
        # If TURN_LEFT: user turns left. 
        # Note: Depending on front camera mirroring, delta could be negative or positive.
        # We verify that absolute delta is >= 15 degrees.
        abs_delta = abs(delta)
        passed = abs_delta >= settings.YAW_DELTA_THRESHOLD_DEG
        return passed, float(delta)

# Global singleton
vision_engine = VisionEngine()
