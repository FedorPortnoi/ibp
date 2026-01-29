"""
Video Analyzer - Extract frames and metadata from videos
========================================================
Analyze video content from social media for OSINT purposes.
"""

import logging
import os
import re
import time
import tempfile
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import requests

logger = logging.getLogger(__name__)

# Try to import OpenCV
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV not installed. Video analysis limited.")


@dataclass
class VideoFrame:
    """A single extracted video frame."""
    frame_number: int
    timestamp_seconds: float
    image_path: str = ""
    has_faces: bool = False
    face_count: int = 0
    confidence: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'frame_number': self.frame_number,
            'timestamp_seconds': self.timestamp_seconds,
            'image_path': self.image_path,
            'has_faces': self.has_faces,
            'face_count': self.face_count,
            'confidence': self.confidence
        }


@dataclass
class VideoMetadata:
    """Video file metadata."""
    filename: str = ""
    duration_seconds: float = 0
    width: int = 0
    height: int = 0
    fps: float = 0
    frame_count: int = 0
    codec: str = ""
    filesize_bytes: int = 0
    creation_date: str = ""
    gps_coordinates: Optional[Tuple[float, float]] = None
    device_info: str = ""
    source_url: str = ""

    def to_dict(self) -> Dict:
        return {
            'filename': self.filename,
            'duration_seconds': self.duration_seconds,
            'duration_formatted': self._format_duration(self.duration_seconds),
            'width': self.width,
            'height': self.height,
            'resolution': f"{self.width}x{self.height}",
            'fps': self.fps,
            'frame_count': self.frame_count,
            'codec': self.codec,
            'filesize_bytes': self.filesize_bytes,
            'filesize_formatted': self._format_size(self.filesize_bytes),
            'creation_date': self.creation_date,
            'gps_coordinates': self.gps_coordinates,
            'device_info': self.device_info,
            'source_url': self.source_url
        }

    def _format_duration(self, seconds: float) -> str:
        """Format duration as MM:SS or HH:MM:SS."""
        if seconds < 0:
            return "00:00"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _format_size(self, bytes_size: int) -> str:
        """Format file size as human-readable."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} TB"


@dataclass
class VideoAnalysisResult:
    """Complete video analysis result."""
    metadata: VideoMetadata = None
    frames: List[VideoFrame] = field(default_factory=list)
    faces_found: int = 0
    analysis_time: float = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'metadata': self.metadata.to_dict() if self.metadata else None,
            'frames': [f.to_dict() for f in self.frames],
            'faces_found': self.faces_found,
            'analysis_time': self.analysis_time,
            'errors': self.errors
        }


class VideoAnalyzer:
    """
    Analyze video files for OSINT investigations.

    Features:
    - Extract key frames at regular intervals
    - Get video metadata (duration, resolution, GPS)
    - Detect faces in frames
    - Download videos from social media URLs
    """

    SUPPORTED_FORMATS = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v', '.flv'}

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'video/*,*/*',
    }

    def __init__(self, output_dir: str = None, max_frames: int = 10):
        self.output_dir = output_dir or tempfile.mkdtemp(prefix='ibp_video_')
        self.max_frames = max_frames
        os.makedirs(self.output_dir, exist_ok=True)

    def analyze_url(
        self,
        video_url: str,
        extract_frames: bool = True,
        detect_faces: bool = True
    ) -> VideoAnalysisResult:
        """
        Download and analyze a video from URL.

        Args:
            video_url: URL of the video
            extract_frames: Whether to extract key frames
            detect_faces: Whether to run face detection

        Returns:
            VideoAnalysisResult with metadata and frames
        """
        start_time = time.time()
        result = VideoAnalysisResult()

        if not CV2_AVAILABLE:
            result.errors.append("OpenCV not installed - video analysis unavailable")
            return result

        # Download video
        try:
            local_path = self._download_video(video_url)
            if not local_path:
                result.errors.append("Failed to download video")
                return result
        except Exception as e:
            result.errors.append(f"Download error: {str(e)}")
            return result

        try:
            # Get metadata
            result.metadata = self._get_metadata(local_path)
            result.metadata.source_url = video_url

            # Extract frames
            if extract_frames:
                result.frames = self._extract_frames(local_path, detect_faces)
                result.faces_found = sum(f.face_count for f in result.frames)

        finally:
            # Cleanup downloaded video
            try:
                os.remove(local_path)
            except Exception:
                pass

        result.analysis_time = time.time() - start_time
        return result

    def analyze_file(
        self,
        file_path: str,
        extract_frames: bool = True,
        detect_faces: bool = True
    ) -> VideoAnalysisResult:
        """
        Analyze a local video file.

        Args:
            file_path: Path to the video file
            extract_frames: Whether to extract key frames
            detect_faces: Whether to run face detection

        Returns:
            VideoAnalysisResult with metadata and frames
        """
        start_time = time.time()
        result = VideoAnalysisResult()

        if not CV2_AVAILABLE:
            result.errors.append("OpenCV not installed")
            return result

        if not os.path.exists(file_path):
            result.errors.append(f"File not found: {file_path}")
            return result

        # Get metadata
        result.metadata = self._get_metadata(file_path)

        # Extract frames
        if extract_frames:
            result.frames = self._extract_frames(file_path, detect_faces)
            result.faces_found = sum(f.face_count for f in result.frames)

        result.analysis_time = time.time() - start_time
        return result

    def _download_video(self, url: str, max_size_mb: int = 100) -> Optional[str]:
        """Download video from URL to temporary file."""
        try:
            # Stream download with size limit
            response = requests.get(url, headers=self.HEADERS, stream=True, timeout=60)

            if response.status_code != 200:
                logger.warning(f"Video download failed: HTTP {response.status_code}")
                return None

            # Check content length
            content_length = int(response.headers.get('content-length', 0))
            if content_length > max_size_mb * 1024 * 1024:
                logger.warning(f"Video too large: {content_length / (1024*1024):.1f}MB")
                return None

            # Determine extension from URL or content-type
            ext = '.mp4'
            content_type = response.headers.get('content-type', '')
            if 'webm' in content_type:
                ext = '.webm'
            elif 'quicktime' in content_type or 'mov' in content_type:
                ext = '.mov'

            # Save to temp file
            temp_path = os.path.join(self.output_dir, f"video_{int(time.time())}{ext}")

            downloaded = 0
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if downloaded > max_size_mb * 1024 * 1024:
                            break

            return temp_path

        except Exception as e:
            logger.warning(f"Video download error: {e}")
            return None

    def _get_metadata(self, file_path: str) -> VideoMetadata:
        """Extract metadata from video file."""
        metadata = VideoMetadata(filename=os.path.basename(file_path))

        try:
            cap = cv2.VideoCapture(file_path)

            if not cap.isOpened():
                logger.warning(f"Could not open video: {file_path}")
                return metadata

            # Basic properties
            metadata.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            metadata.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            metadata.fps = cap.get(cv2.CAP_PROP_FPS)
            metadata.frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # Calculate duration
            if metadata.fps > 0:
                metadata.duration_seconds = metadata.frame_count / metadata.fps

            # Codec (fourcc)
            fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
            metadata.codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])

            cap.release()

            # File size
            metadata.filesize_bytes = os.path.getsize(file_path)

        except Exception as e:
            logger.warning(f"Metadata extraction error: {e}")

        return metadata

    def _extract_frames(
        self,
        file_path: str,
        detect_faces: bool = True
    ) -> List[VideoFrame]:
        """Extract key frames from video at regular intervals."""
        frames = []

        try:
            cap = cv2.VideoCapture(file_path)

            if not cap.isOpened():
                logger.warning(f"Could not open video: {file_path}")
                return frames

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)

            if total_frames <= 0 or fps <= 0:
                cap.release()
                return frames

            # Calculate frame interval
            interval = max(1, total_frames // self.max_frames)

            # Load face cascade for detection
            face_cascade = None
            if detect_faces:
                try:
                    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                    face_cascade = cv2.CascadeClassifier(cascade_path)
                except Exception as e:
                    logger.warning(f"Face cascade load error: {e}")

            frame_number = 0
            extracted_count = 0

            while cap.isOpened() and extracted_count < self.max_frames:
                # Set position
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                ret, frame = cap.read()

                if not ret:
                    break

                timestamp = frame_number / fps if fps > 0 else 0

                # Save frame
                frame_filename = f"frame_{extracted_count:04d}_{int(timestamp)}s.jpg"
                frame_path = os.path.join(self.output_dir, frame_filename)
                cv2.imwrite(frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

                # Detect faces
                face_count = 0
                has_faces = False
                if face_cascade is not None:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = face_cascade.detectMultiScale(
                        gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
                    )
                    face_count = len(faces)
                    has_faces = face_count > 0

                frames.append(VideoFrame(
                    frame_number=frame_number,
                    timestamp_seconds=timestamp,
                    image_path=frame_path,
                    has_faces=has_faces,
                    face_count=face_count,
                    confidence=0.8 if has_faces else 0.5
                ))

                frame_number += interval
                extracted_count += 1

            cap.release()

        except Exception as e:
            logger.warning(f"Frame extraction error: {e}")

        return frames

    def extract_vk_video(self, video_url: str) -> VideoAnalysisResult:
        """Extract and analyze a VK video."""
        # VK video URLs are typically: https://vk.com/video-XXXXX_XXXXX
        # or with player: https://vk.com/video_ext.php?oid=-XXXXX&id=XXXXX

        result = VideoAnalysisResult()

        # VK requires authentication for most videos
        # This is a placeholder for future VK API integration
        result.errors.append("VK video extraction requires API access - coming soon")

        return result

    def extract_telegram_video(self, video_url: str) -> VideoAnalysisResult:
        """Extract and analyze a Telegram video."""
        # Telegram videos are harder to extract without API
        result = VideoAnalysisResult()
        result.errors.append("Telegram video extraction requires API access - coming soon")
        return result

    def cleanup(self):
        """Remove all extracted frames and temporary files."""
        import shutil
        try:
            if os.path.exists(self.output_dir):
                shutil.rmtree(self.output_dir)
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")


# Singleton instance
video_analyzer = VideoAnalyzer()
