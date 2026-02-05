"""
Face Comparator - IBP Prototype B.5
Compare faces between two images using multiple backends

Features:
- Face detection using dlib/MTCNN/OpenCV cascades
- Face embedding generation using face_recognition/DeepFace
- Similarity calculation (cosine distance, euclidean)
- Multi-face handling in single images
- Batch comparison support
- Quality assessment for input images

Usage:
    comparator = FaceComparator()
    result = comparator.compare("photo1.jpg", "photo2.jpg")
    print(f"Match: {result.is_match}, Confidence: {result.confidence}%")
"""

import os
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any, Union
from pathlib import Path
import logging
import json
from enum import Enum
import math

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional imports with fallbacks
HAS_FACE_RECOGNITION = False
HAS_DEEPFACE = False
HAS_CV2 = False
HAS_NUMPY = False
HAS_PIL = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    logger.warning("numpy not installed - some features limited")

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    logger.warning("opencv-python not installed - using fallback detection")

try:
    import face_recognition
    HAS_FACE_RECOGNITION = True
except ImportError:
    logger.warning("face_recognition not installed - using fallback")

try:
    from deepface import DeepFace
    HAS_DEEPFACE = True
except ImportError:
    logger.warning("deepface not installed - using fallback")

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    logger.warning("Pillow not installed - image loading limited")


class Backend(Enum):
    """Available face recognition backends"""
    FACE_RECOGNITION = "face_recognition"
    DEEPFACE = "deepface"
    OPENCV = "opencv"
    DEMO = "demo"


class DetectionModel(Enum):
    """Face detection models"""
    HOG = "hog"  # Faster, less accurate
    CNN = "cnn"  # Slower, more accurate
    MTCNN = "mtcnn"
    RETINAFACE = "retinaface"
    OPENCV = "opencv"


@dataclass
class BoundingBox:
    """Face bounding box coordinates"""
    top: int
    right: int
    bottom: int
    left: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def center(self) -> Tuple[int, int]:
        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)

    def to_dict(self) -> Dict[str, int]:
        return {
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "left": self.left,
            "width": self.width,
            "height": self.height
        }


@dataclass
class DetectedFace:
    """Detected face with metadata"""
    bounding_box: BoundingBox
    confidence: float = 1.0
    embedding: Optional[List[float]] = None
    landmarks: Optional[Dict[str, Tuple[int, int]]] = None
    quality_score: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bounding_box": self.bounding_box.to_dict(),
            "confidence": self.confidence,
            "has_embedding": self.embedding is not None,
            "embedding_size": len(self.embedding) if self.embedding else 0,
            "landmarks": self.landmarks,
            "quality_score": self.quality_score
        }


@dataclass
class ImageAnalysis:
    """Analysis results for a single image"""
    file_path: str
    faces: List[DetectedFace] = field(default_factory=list)
    image_width: int = 0
    image_height: int = 0
    quality_score: float = 1.0
    error: Optional[str] = None

    @property
    def face_count(self) -> int:
        return len(self.faces)

    @property
    def has_faces(self) -> bool:
        return len(self.faces) > 0

    @property
    def primary_face(self) -> Optional[DetectedFace]:
        """Return the largest/most prominent face"""
        if not self.faces:
            return None
        return max(self.faces, key=lambda f: f.bounding_box.area)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "face_count": self.face_count,
            "faces": [f.to_dict() for f in self.faces],
            "image_dimensions": {"width": self.image_width, "height": self.image_height},
            "quality_score": self.quality_score,
            "error": self.error
        }


@dataclass
class ComparisonResult:
    """Face comparison result"""
    is_match: bool
    confidence: float  # 0-100%
    distance: float  # Raw distance value
    threshold: float  # Threshold used for matching

    image1_analysis: Optional[ImageAnalysis] = None
    image2_analysis: Optional[ImageAnalysis] = None

    face1_index: int = 0  # Which face in image1 was compared
    face2_index: int = 0  # Which face in image2 was compared

    backend_used: str = "unknown"
    comparison_time_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_match": self.is_match,
            "confidence": round(self.confidence, 2),
            "distance": round(self.distance, 6),
            "threshold": self.threshold,
            "face1_index": self.face1_index,
            "face2_index": self.face2_index,
            "backend_used": self.backend_used,
            "comparison_time_ms": round(self.comparison_time_ms, 2),
            "image1": self.image1_analysis.to_dict() if self.image1_analysis else None,
            "image2": self.image2_analysis.to_dict() if self.image2_analysis else None,
            "error": self.error
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


@dataclass
class BatchComparisonResult:
    """Results from comparing multiple image pairs"""
    comparisons: List[ComparisonResult] = field(default_factory=list)
    total_pairs: int = 0
    matches_found: int = 0
    average_confidence: float = 0.0
    processing_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_pairs": self.total_pairs,
            "matches_found": self.matches_found,
            "match_rate": round(self.matches_found / self.total_pairs * 100, 2) if self.total_pairs > 0 else 0,
            "average_confidence": round(self.average_confidence, 2),
            "processing_time_ms": round(self.processing_time_ms, 2),
            "comparisons": [c.to_dict() for c in self.comparisons]
        }


class FaceComparator:
    """
    Multi-backend face comparison engine

    Supports face_recognition, DeepFace, and OpenCV backends
    with automatic fallback to demo mode when libraries unavailable.
    """

    # Default thresholds for different backends
    THRESHOLDS = {
        Backend.FACE_RECOGNITION: 0.6,  # Euclidean distance
        Backend.DEEPFACE: 0.4,  # Cosine distance
        Backend.OPENCV: 0.5,
        Backend.DEMO: 0.5
    }

    def __init__(
        self,
        backend: Backend = Backend.FACE_RECOGNITION,
        detection_model: DetectionModel = DetectionModel.HOG,
        threshold: Optional[float] = None
    ):
        """
        Initialize face comparator

        Args:
            backend: Which face recognition library to use
            detection_model: Face detection model (affects speed/accuracy)
            threshold: Custom matching threshold (default varies by backend)
        """
        self.backend = self._select_backend(backend)
        self.detection_model = detection_model
        self.threshold = threshold or self.THRESHOLDS.get(self.backend, 0.5)

        logger.info(f"FaceComparator initialized: backend={self.backend.value}, "
                   f"detection={detection_model.value}, threshold={self.threshold}")

    def _select_backend(self, preferred: Backend) -> Backend:
        """Select best available backend"""
        if preferred == Backend.FACE_RECOGNITION and HAS_FACE_RECOGNITION:
            return Backend.FACE_RECOGNITION
        elif preferred == Backend.DEEPFACE and HAS_DEEPFACE:
            return Backend.DEEPFACE
        elif preferred == Backend.OPENCV and HAS_CV2:
            return Backend.OPENCV

        # Fallback chain
        if HAS_FACE_RECOGNITION:
            logger.info("Using face_recognition backend")
            return Backend.FACE_RECOGNITION
        elif HAS_DEEPFACE:
            logger.info("Using DeepFace backend")
            return Backend.DEEPFACE
        elif HAS_CV2:
            logger.info("Using OpenCV backend")
            return Backend.OPENCV
        else:
            logger.warning("No face recognition library available - using DEMO mode")
            return Backend.DEMO

    def analyze_image(self, image_path: str) -> ImageAnalysis:
        """
        Detect and analyze faces in an image

        Args:
            image_path: Path to image file

        Returns:
            ImageAnalysis with detected faces and embeddings
        """
        import time
        start = time.time()

        analysis = ImageAnalysis(file_path=image_path)

        # Validate file exists
        if not os.path.exists(image_path):
            analysis.error = f"File not found: {image_path}"
            return analysis

        try:
            if self.backend == Backend.FACE_RECOGNITION:
                return self._analyze_face_recognition(image_path)
            elif self.backend == Backend.DEEPFACE:
                return self._analyze_deepface(image_path)
            elif self.backend == Backend.OPENCV:
                return self._analyze_opencv(image_path)
            else:
                return self._analyze_demo(image_path)

        except Exception as e:
            analysis.error = str(e)
            logger.error(f"Error analyzing {image_path}: {e}")
            return analysis

    def _analyze_face_recognition(self, image_path: str) -> ImageAnalysis:
        """Analyze using face_recognition library"""
        analysis = ImageAnalysis(file_path=image_path)

        # Load image
        image = face_recognition.load_image_file(image_path)
        analysis.image_height, analysis.image_width = image.shape[:2]

        # Detect faces
        model = "cnn" if self.detection_model == DetectionModel.CNN else "hog"
        face_locations = face_recognition.face_locations(image, model=model)

        if not face_locations:
            return analysis

        # Get embeddings
        face_encodings = face_recognition.face_encodings(image, face_locations)

        # Get landmarks
        face_landmarks_list = face_recognition.face_landmarks(image, face_locations)

        for i, (location, encoding) in enumerate(zip(face_locations, face_encodings)):
            top, right, bottom, left = location

            bbox = BoundingBox(top=top, right=right, bottom=bottom, left=left)

            landmarks = None
            if i < len(face_landmarks_list):
                lm = face_landmarks_list[i]
                landmarks = {
                    k: v[0] if v else None
                    for k, v in lm.items()
                }

            face = DetectedFace(
                bounding_box=bbox,
                embedding=encoding.tolist(),
                landmarks=landmarks,
                confidence=1.0
            )
            analysis.faces.append(face)

        return analysis

    def _analyze_deepface(self, image_path: str) -> ImageAnalysis:
        """Analyze using DeepFace library"""
        analysis = ImageAnalysis(file_path=image_path)

        try:
            # Get image dimensions
            if HAS_CV2:
                img = cv2.imread(image_path)
                if img is not None:
                    analysis.image_height, analysis.image_width = img.shape[:2]

            # DeepFace detection and embedding
            detector = "mtcnn" if self.detection_model == DetectionModel.MTCNN else "opencv"

            embeddings = DeepFace.represent(
                img_path=image_path,
                model_name="Facenet512",
                detector_backend=detector,
                enforce_detection=False
            )

            for emb_data in embeddings:
                if "facial_area" in emb_data:
                    area = emb_data["facial_area"]
                    bbox = BoundingBox(
                        top=area.get("y", 0),
                        left=area.get("x", 0),
                        bottom=area.get("y", 0) + area.get("h", 0),
                        right=area.get("x", 0) + area.get("w", 0)
                    )
                else:
                    bbox = BoundingBox(top=0, left=0, bottom=100, right=100)

                face = DetectedFace(
                    bounding_box=bbox,
                    embedding=emb_data.get("embedding", []),
                    confidence=emb_data.get("face_confidence", 1.0)
                )
                analysis.faces.append(face)

        except Exception as e:
            analysis.error = str(e)

        return analysis

    def _analyze_opencv(self, image_path: str) -> ImageAnalysis:
        """Analyze using OpenCV (detection only, no embeddings)"""
        analysis = ImageAnalysis(file_path=image_path)

        img = cv2.imread(image_path)
        if img is None:
            analysis.error = "Failed to load image"
            return analysis

        analysis.image_height, analysis.image_width = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Use Haar cascade for face detection
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face_cascade = cv2.CascadeClassifier(cascade_path)

        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )

        for (x, y, w, h) in faces:
            bbox = BoundingBox(
                top=y,
                left=x,
                bottom=y + h,
                right=x + w
            )
            face = DetectedFace(
                bounding_box=bbox,
                confidence=0.8  # OpenCV doesn't provide confidence
            )
            analysis.faces.append(face)

        return analysis

    def _analyze_demo(self, image_path: str) -> ImageAnalysis:
        """Demo mode analysis (simulated)"""
        import hashlib
        import random

        analysis = ImageAnalysis(file_path=image_path)

        # Generate deterministic "detection" based on filename
        file_hash = hashlib.md5(image_path.encode()).hexdigest()
        random.seed(file_hash)

        # Simulated dimensions
        analysis.image_width = 800
        analysis.image_height = 600

        # Generate 1-2 simulated faces
        num_faces = random.randint(1, 2)

        for i in range(num_faces):
            # Random face location
            x = random.randint(100, 400)
            y = random.randint(50, 200)
            w = random.randint(100, 200)
            h = random.randint(120, 240)

            bbox = BoundingBox(
                top=y,
                left=x,
                bottom=y + h,
                right=x + w
            )

            # Generate deterministic embedding (128-dim like face_recognition)
            embedding = [random.gauss(0, 1) for _ in range(128)]
            # Normalize
            if HAS_NUMPY:
                embedding = (np.array(embedding) / np.linalg.norm(embedding)).tolist()

            face = DetectedFace(
                bounding_box=bbox,
                embedding=embedding,
                confidence=random.uniform(0.85, 0.99)
            )
            analysis.faces.append(face)

        return analysis

    def compare(
        self,
        image1_path: str,
        image2_path: str,
        face1_index: int = 0,
        face2_index: int = 0
    ) -> ComparisonResult:
        """
        Compare faces between two images

        Args:
            image1_path: Path to first image
            image2_path: Path to second image
            face1_index: Index of face to use from image1 (if multiple)
            face2_index: Index of face to use from image2 (if multiple)

        Returns:
            ComparisonResult with match status and confidence
        """
        import time
        start = time.time()

        result = ComparisonResult(
            is_match=False,
            confidence=0.0,
            distance=1.0,
            threshold=self.threshold,
            face1_index=face1_index,
            face2_index=face2_index,
            backend_used=self.backend.value
        )

        try:
            # Analyze both images
            analysis1 = self.analyze_image(image1_path)
            analysis2 = self.analyze_image(image2_path)

            result.image1_analysis = analysis1
            result.image2_analysis = analysis2

            # Check for errors
            if analysis1.error:
                result.error = f"Image 1 error: {analysis1.error}"
                return result

            if analysis2.error:
                result.error = f"Image 2 error: {analysis2.error}"
                return result

            # Check faces detected
            if not analysis1.has_faces:
                result.error = "No face detected in image 1"
                return result

            if not analysis2.has_faces:
                result.error = "No face detected in image 2"
                return result

            # Validate indices
            if face1_index >= len(analysis1.faces):
                face1_index = 0
            if face2_index >= len(analysis2.faces):
                face2_index = 0

            face1 = analysis1.faces[face1_index]
            face2 = analysis2.faces[face2_index]

            # Compare embeddings
            if face1.embedding and face2.embedding:
                distance = self._calculate_distance(face1.embedding, face2.embedding)
                result.distance = distance
                result.is_match = distance < self.threshold

                # Convert distance to confidence (0-100%)
                # Lower distance = higher confidence
                result.confidence = self._distance_to_confidence(distance)
            else:
                result.error = "Missing face embeddings for comparison"

        except Exception as e:
            result.error = str(e)
            logger.error(f"Comparison error: {e}")

        result.comparison_time_ms = (time.time() - start) * 1000
        return result

    def _calculate_distance(
        self,
        embedding1: List[float],
        embedding2: List[float],
        metric: str = "euclidean"
    ) -> float:
        """Calculate distance between two embeddings"""
        if HAS_NUMPY:
            e1 = np.array(embedding1)
            e2 = np.array(embedding2)

            if metric == "cosine":
                # Cosine distance
                dot = np.dot(e1, e2)
                norm1 = np.linalg.norm(e1)
                norm2 = np.linalg.norm(e2)
                return 1 - (dot / (norm1 * norm2))
            else:
                # Euclidean distance
                return np.linalg.norm(e1 - e2)
        else:
            # Pure Python fallback
            if metric == "cosine":
                dot = sum(a * b for a, b in zip(embedding1, embedding2))
                norm1 = math.sqrt(sum(a * a for a in embedding1))
                norm2 = math.sqrt(sum(b * b for b in embedding2))
                return 1 - (dot / (norm1 * norm2))
            else:
                return math.sqrt(sum((a - b) ** 2 for a, b in zip(embedding1, embedding2)))

    def _distance_to_confidence(self, distance: float) -> float:
        """Convert distance to confidence percentage"""
        # Sigmoid-like mapping
        # distance 0 -> 100% confidence
        # distance = threshold -> ~50% confidence
        # distance >> threshold -> ~0% confidence

        if distance <= 0:
            return 100.0

        # Exponential decay
        confidence = 100 * math.exp(-distance / self.threshold * math.log(2))
        return max(0, min(100, confidence))

    def compare_batch(
        self,
        image_pairs: List[Tuple[str, str]]
    ) -> BatchComparisonResult:
        """
        Compare multiple image pairs

        Args:
            image_pairs: List of (image1_path, image2_path) tuples

        Returns:
            BatchComparisonResult with all comparisons
        """
        import time
        start = time.time()

        result = BatchComparisonResult(total_pairs=len(image_pairs))

        for img1, img2 in image_pairs:
            comparison = self.compare(img1, img2)
            result.comparisons.append(comparison)

            if comparison.is_match:
                result.matches_found += 1

        # Calculate average confidence
        confidences = [c.confidence for c in result.comparisons if c.error is None]
        if confidences:
            result.average_confidence = sum(confidences) / len(confidences)

        result.processing_time_ms = (time.time() - start) * 1000
        return result

    def find_matches(
        self,
        target_image: str,
        candidate_images: List[str],
        min_confidence: float = 50.0
    ) -> List[ComparisonResult]:
        """
        Find all matching faces for a target image

        Args:
            target_image: Reference image to match against
            candidate_images: List of images to search
            min_confidence: Minimum confidence threshold (0-100)

        Returns:
            List of matching ComparisonResults, sorted by confidence
        """
        matches = []

        for candidate in candidate_images:
            result = self.compare(target_image, candidate)

            if result.is_match and result.confidence >= min_confidence:
                matches.append(result)

        # Sort by confidence (highest first)
        matches.sort(key=lambda x: x.confidence, reverse=True)
        return matches

    def extract_face(
        self,
        image_path: str,
        face_index: int = 0,
        output_path: Optional[str] = None,
        margin: float = 0.2
    ) -> Optional[str]:
        """
        Extract and save a detected face from an image

        Args:
            image_path: Source image path
            face_index: Which face to extract (if multiple)
            output_path: Where to save extracted face
            margin: Extra margin around face (0.2 = 20%)

        Returns:
            Path to extracted face image, or None if failed
        """
        analysis = self.analyze_image(image_path)

        if not analysis.has_faces:
            logger.warning(f"No faces found in {image_path}")
            return None

        if face_index >= len(analysis.faces):
            face_index = 0

        face = analysis.faces[face_index]
        bbox = face.bounding_box

        # Calculate margins
        margin_x = int(bbox.width * margin)
        margin_y = int(bbox.height * margin)

        # Expanded bounding box
        x1 = max(0, bbox.left - margin_x)
        y1 = max(0, bbox.top - margin_y)
        x2 = min(analysis.image_width, bbox.right + margin_x)
        y2 = min(analysis.image_height, bbox.bottom + margin_y)

        if HAS_CV2:
            img = cv2.imread(image_path)
            if img is None:
                return None

            face_img = img[y1:y2, x1:x2]

            if output_path is None:
                base, ext = os.path.splitext(image_path)
                output_path = f"{base}_face_{face_index}{ext}"

            cv2.imwrite(output_path, face_img)
            return output_path

        elif HAS_PIL:
            img = Image.open(image_path)
            face_img = img.crop((x1, y1, x2, y2))

            if output_path is None:
                base, ext = os.path.splitext(image_path)
                output_path = f"{base}_face_{face_index}{ext}"

            face_img.save(output_path)
            return output_path

        else:
            logger.error("No image library available for face extraction")
            return None


def demo():
    """Demonstrate face comparison capabilities"""
    print("=" * 60)
    print("Face Comparator - IBP Prototype B.5")
    print("=" * 60)
    print()

    # Initialize comparator
    comparator = FaceComparator()
    print(f"Backend: {comparator.backend.value}")
    print(f"Threshold: {comparator.threshold}")
    print()

    # Demo with sample paths
    print("Demo Mode - Simulated Face Comparison")
    print("-" * 40)

    # Simulate comparison
    test_images = [
        ("person_a_photo1.jpg", "person_a_photo2.jpg"),  # Same person
        ("person_a_photo1.jpg", "person_b_photo1.jpg"),  # Different people
    ]

    for img1, img2 in test_images:
        print(f"\nComparing: {img1} vs {img2}")

        # Create temporary demo files for testing
        result = comparator.compare(img1, img2)

        print(f"  Match: {result.is_match}")
        print(f"  Confidence: {result.confidence:.1f}%")
        print(f"  Distance: {result.distance:.4f}")
        print(f"  Time: {result.comparison_time_ms:.1f}ms")

        if result.error:
            print(f"  Error: {result.error}")

    print()
    print("=" * 60)
    print("Usage Example:")
    print("-" * 40)
    print("""
from face_comparator import FaceComparator, Backend

# Initialize
comparator = FaceComparator(
    backend=Backend.FACE_RECOGNITION,  # or DEEPFACE, OPENCV
    threshold=0.6
)

# Compare two images
result = comparator.compare("photo1.jpg", "photo2.jpg")

if result.is_match:
    print(f"Match found! Confidence: {result.confidence:.1f}%")
else:
    print(f"No match. Confidence: {result.confidence:.1f}%")

# Analyze single image
analysis = comparator.analyze_image("photo.jpg")
print(f"Found {analysis.face_count} face(s)")

for i, face in enumerate(analysis.faces):
    print(f"  Face {i}: {face.bounding_box.width}x{face.bounding_box.height}")

# Find matches in batch
matches = comparator.find_matches(
    target_image="target.jpg",
    candidate_images=["photo1.jpg", "photo2.jpg", "photo3.jpg"],
    min_confidence=60.0
)

for match in matches:
    print(f"Match: {match.image2_analysis.file_path} ({match.confidence:.1f}%)")

# Extract face from image
extracted = comparator.extract_face("group_photo.jpg", face_index=0)
print(f"Face extracted to: {extracted}")
""")

    print("=" * 60)
    print()

    # Show JSON output example
    print("JSON Output Example:")
    print("-" * 40)

    # Create a sample result
    sample_result = ComparisonResult(
        is_match=True,
        confidence=87.5,
        distance=0.32,
        threshold=0.6,
        backend_used="face_recognition",
        comparison_time_ms=125.4,
        image1_analysis=ImageAnalysis(
            file_path="photo1.jpg",
            faces=[DetectedFace(
                bounding_box=BoundingBox(top=50, left=100, bottom=250, right=280),
                confidence=0.98
            )],
            image_width=800,
            image_height=600
        ),
        image2_analysis=ImageAnalysis(
            file_path="photo2.jpg",
            faces=[DetectedFace(
                bounding_box=BoundingBox(top=80, left=150, bottom=300, right=350),
                confidence=0.95
            )],
            image_width=1024,
            image_height=768
        )
    )

    print(sample_result.to_json())


if __name__ == "__main__":
    demo()
