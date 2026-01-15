"""
Face Comparator Service
=======================
Detects faces in images and compares them to a target photo.

Uses the `face_recognition` library (based on dlib):
- Free and runs locally
- CPU-friendly (no GPU required)
- Accurate face detection and comparison

Install: pip install face_recognition

Note: On Windows, you may need to install dlib first:
  pip install cmake
  pip install dlib
  pip install face_recognition

Or use pre-built wheel:
  pip install https://github.com/jloh02/dlib/releases/download/v19.22/dlib-19.22.99-cp310-cp310-win_amd64.whl

Author: IBP Project
"""

import os
import gc
import time
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field

# Check if face_recognition is available
FACE_RECOGNITION_AVAILABLE = False
try:
    import face_recognition
    import numpy as np
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    print("⚠️ face_recognition not installed. Install with: pip install face_recognition")


@dataclass
class FaceComparisonResult:
    """Result of comparing a face to the target."""
    image_path: str
    has_face: bool = False
    face_count: int = 0
    best_match_similarity: float = 0.0
    is_match: bool = False
    face_locations: List[Tuple] = field(default_factory=list)
    error: Optional[str] = None


class FaceComparator:
    """
    Compares faces in images to a target photo.
    
    Device-friendly features:
    - Processes one image at a time
    - Uses 'hog' model (CPU-friendly) instead of 'cnn' (GPU)
    - Clears memory after each comparison
    - Configurable match threshold
    """
    
    def __init__(self, 
                 match_threshold: float = 0.6,
                 model: str = 'hog',
                 num_jitters: int = 1,
                 delay_between_images: float = 0.5):
        """
        Initialize face comparator.
        
        Args:
            match_threshold: Distance threshold for match (lower = stricter)
                            0.6 is default, 0.5 is strict, 0.4 is very strict
            model: Face detection model ('hog' for CPU, 'cnn' for GPU)
            num_jitters: Number of times to re-sample face (more = accurate but slower)
            delay_between_images: Delay between processing images (device-friendly)
        """
        self.match_threshold = match_threshold
        self.model = model
        self.num_jitters = num_jitters
        self.delay = delay_between_images
        
        # Target face encoding
        self.target_encoding = None
        self.target_loaded = False
        
        if not FACE_RECOGNITION_AVAILABLE:
            print("⚠️ Face recognition not available!")
            print("   Install with: pip install face_recognition")
    
    def load_target_photo(self, target_path: str) -> Dict:
        """
        Load and encode the target photo.
        
        Args:
            target_path: Path to target's photo
            
        Returns:
            Dict with success status and face info
        """
        if not FACE_RECOGNITION_AVAILABLE:
            return {
                'success': False,
                'error': 'face_recognition library not installed'
            }
        
        if not os.path.exists(target_path):
            return {
                'success': False,
                'error': f'Target photo not found: {target_path}'
            }
        
        try:
            print(f"  Loading target photo: {target_path}")
            
            # Load image
            image = face_recognition.load_image_file(target_path)
            
            # Find faces
            face_locations = face_recognition.face_locations(image, model=self.model)
            
            if not face_locations:
                return {
                    'success': False,
                    'error': 'No face detected in target photo'
                }
            
            if len(face_locations) > 1:
                print(f"    ⚠️ Multiple faces detected ({len(face_locations)}), using largest")
                # Use the largest face (probably the main subject)
                face_locations = [max(face_locations, key=lambda f: (f[2]-f[0]) * (f[1]-f[3]))]
            
            # Get face encoding
            encodings = face_recognition.face_encodings(
                image, 
                known_face_locations=face_locations,
                num_jitters=self.num_jitters
            )
            
            if not encodings:
                return {
                    'success': False,
                    'error': 'Could not encode face in target photo'
                }
            
            self.target_encoding = encodings[0]
            self.target_loaded = True
            
            # Clear memory
            del image
            gc.collect()
            
            print(f"    ✓ Target face loaded successfully")
            
            return {
                'success': True,
                'face_location': face_locations[0],
                'faces_detected': 1
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def compare_image(self, image_path: str) -> FaceComparisonResult:
        """
        Compare faces in an image to the target.
        
        Args:
            image_path: Path to image to compare
            
        Returns:
            FaceComparisonResult with match info
        """
        result = FaceComparisonResult(image_path=image_path)
        
        if not FACE_RECOGNITION_AVAILABLE:
            result.error = 'face_recognition library not installed'
            return result
        
        if not self.target_loaded:
            result.error = 'Target photo not loaded'
            return result
        
        if not os.path.exists(image_path):
            result.error = f'Image not found: {image_path}'
            return result
        
        try:
            # Load image
            image = face_recognition.load_image_file(image_path)
            
            # Find faces (use HOG for CPU-friendly)
            face_locations = face_recognition.face_locations(image, model=self.model)
            
            result.face_count = len(face_locations)
            result.face_locations = face_locations
            
            if not face_locations:
                result.has_face = False
                del image
                gc.collect()
                return result
            
            result.has_face = True
            
            # Get encodings for all faces
            encodings = face_recognition.face_encodings(
                image,
                known_face_locations=face_locations,
                num_jitters=self.num_jitters
            )
            
            if not encodings:
                del image
                gc.collect()
                return result
            
            # Compare each face to target
            best_similarity = 0.0
            
            for encoding in encodings:
                # Calculate face distance (lower = more similar)
                distance = face_recognition.face_distance([self.target_encoding], encoding)[0]
                
                # Convert distance to similarity percentage (0-100)
                # Distance of 0 = 100% similar, distance of 1 = 0% similar
                similarity = max(0, (1 - distance)) * 100
                
                if similarity > best_similarity:
                    best_similarity = similarity
            
            result.best_match_similarity = best_similarity
            
            # Check if it's a match (distance below threshold)
            # threshold 0.6 = similarity of 40%+
            # We use 40% as minimum match
            result.is_match = best_similarity >= 40
            
            # Clear memory
            del image
            del encodings
            gc.collect()
            
            return result
            
        except Exception as e:
            result.error = str(e)
            return result
    
    def compare_multiple_images(self, 
                                 image_paths: List[str],
                                 progress_callback: Optional[callable] = None) -> List[FaceComparisonResult]:
        """
        Compare multiple images to target.
        
        Device-friendly: processes one at a time with delays.
        
        Args:
            image_paths: List of image paths
            progress_callback: Optional callback(current, total, status)
            
        Returns:
            List of FaceComparisonResult
        """
        if not self.target_loaded:
            print("⚠️ Target photo not loaded!")
            return []
        
        results = []
        total = len(image_paths)
        matches_found = 0
        
        print(f"\n🔍 Comparing {total} images to target face...")
        print(f"   (Device-safe mode: processing one at a time)")
        
        for i, path in enumerate(image_paths, 1):
            if progress_callback:
                progress_callback(i, total, f"Comparing {Path(path).name}")
            
            # Compare
            result = self.compare_image(path)
            results.append(result)
            
            # Log result
            if result.has_face:
                status = f"👤 {result.face_count} face(s)"
                if result.is_match:
                    status += f" - ✅ MATCH ({result.best_match_similarity:.1f}%)"
                    matches_found += 1
                else:
                    status += f" - ({result.best_match_similarity:.1f}%)"
            else:
                status = "❌ No face"
            
            print(f"  [{i}/{total}] {Path(path).name}: {status}")
            
            # Device-friendly delay
            time.sleep(self.delay)
            
            # Periodic memory cleanup
            if i % 10 == 0:
                gc.collect()
        
        print(f"\n✅ Face comparison complete: {matches_found}/{total} matches")
        
        return results
    
    def get_match_confidence_label(self, similarity: float) -> str:
        """Convert similarity score to human-readable label."""
        if similarity >= 80:
            return "Very High (almost certain match)"
        elif similarity >= 60:
            return "High (likely same person)"
        elif similarity >= 45:
            return "Medium (possible match)"
        elif similarity >= 30:
            return "Low (unlikely match)"
        else:
            return "Very Low (different person)"
    
    def unload_target(self):
        """Unload target encoding to free memory."""
        self.target_encoding = None
        self.target_loaded = False
        gc.collect()


class FaceComparisonPipeline:
    """
    Complete pipeline for comparing found accounts to target photo.
    
    Combines:
    1. Profile photo scraping
    2. Face detection
    3. Face comparison
    4. Result ranking
    """
    
    def __init__(self, 
                 match_threshold: float = 0.6,
                 max_photos_per_profile: int = 10,
                 delay_seconds: float = 1.0):
        """
        Initialize pipeline.
        
        Args:
            match_threshold: Face match threshold (0.6 default)
            max_photos_per_profile: Max photos to scrape per profile
            delay_seconds: Delay between operations (device-friendly)
        """
        from app.services.profile_scraper import ProfilePhotoScraper
        
        self.scraper = ProfilePhotoScraper(
            delay_seconds=delay_seconds,
            max_photos_per_profile=max_photos_per_profile
        )
        
        self.comparator = FaceComparator(
            match_threshold=match_threshold,
            delay_between_images=delay_seconds / 2
        )
        
        self.delay = delay_seconds
    
    def process_accounts(self,
                         target_photo_path: str,
                         accounts: List[Dict],
                         progress_callback: Optional[callable] = None) -> List[Dict]:
        """
        Process accounts: scrape photos and compare faces.
        
        Args:
            target_photo_path: Path to target's photo
            accounts: List of account dicts with 'url' field
            progress_callback: Optional callback(phase, current, total, status)
            
        Returns:
            Accounts sorted by face match (matches first)
        """
        if not FACE_RECOGNITION_AVAILABLE:
            print("⚠️ Face recognition not available - skipping face comparison")
            return accounts
        
        # Load target photo
        print("\n" + "=" * 60)
        print("🎯 Face Comparison Pipeline")
        print("=" * 60)
        
        target_result = self.comparator.load_target_photo(target_photo_path)
        
        if not target_result['success']:
            print(f"❌ Failed to load target: {target_result['error']}")
            return accounts
        
        total_accounts = len(accounts)
        print(f"\n📊 Processing {total_accounts} accounts...")
        
        # Process each account
        for i, account in enumerate(accounts, 1):
            url = account.get('url', '')
            if not url:
                continue
            
            if progress_callback:
                progress_callback('scraping', i, total_accounts, url)
            
            print(f"\n[{i}/{total_accounts}] {url}")
            
            # Scrape photos from this profile
            photos = self.scraper.scrape_profile(url)
            
            if not photos:
                print("    No photos found")
                account['face_checked'] = True
                account['face_match'] = False
                account['photos_checked'] = 0
                continue
            
            # Compare faces
            best_similarity = 0.0
            photos_with_faces = 0
            
            for photo in photos:
                if not photo.downloaded or not photo.local_path:
                    continue
                
                result = self.comparator.compare_image(photo.local_path)
                
                if result.has_face:
                    photos_with_faces += 1
                    if result.best_match_similarity > best_similarity:
                        best_similarity = result.best_match_similarity
                
                # Small delay between photos
                time.sleep(self.delay / 4)
            
            # Update account with face match info
            account['face_checked'] = True
            account['face_match'] = best_similarity >= 40
            account['face_similarity'] = best_similarity
            account['photos_checked'] = len(photos)
            account['photos_with_faces'] = photos_with_faces
            
            if account['face_match']:
                confidence = self.comparator.get_match_confidence_label(best_similarity)
                print(f"    ✅ FACE MATCH: {best_similarity:.1f}% - {confidence}")
            
            # Cleanup photos for this profile
            self.scraper.cleanup(photos)
            
            # Memory cleanup
            gc.collect()
            
            # Delay between profiles
            time.sleep(self.delay)
        
        # Sort: face matches first, then by similarity
        accounts.sort(key=lambda x: (
            x.get('face_match', False),
            x.get('face_similarity', 0)
        ), reverse=True)
        
        # Summary
        matches = sum(1 for a in accounts if a.get('face_match'))
        print(f"\n" + "=" * 60)
        print(f"✅ Pipeline complete: {matches} face matches out of {total_accounts} accounts")
        print("=" * 60)
        
        # Cleanup
        self.comparator.unload_target()
        self.scraper.cleanup()
        gc.collect()
        
        return accounts


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Face Comparator Test")
    print("=" * 60)
    
    if not FACE_RECOGNITION_AVAILABLE:
        print("\n❌ face_recognition library not installed!")
        print("\nInstall with:")
        print("  pip install face_recognition")
        print("\nOn Windows, you may need:")
        print("  pip install cmake")
        print("  pip install dlib")
        print("  pip install face_recognition")
        exit(1)
    
    print("✅ face_recognition is installed")
    
    comparator = FaceComparator(
        match_threshold=0.6,
        model='hog'  # CPU-friendly
    )
    
    print("\nTo test, load a target photo:")
    print("  result = comparator.load_target_photo('path/to/target.jpg')")
    print("  comparison = comparator.compare_image('path/to/other.jpg')")
    print("\nResult will show:")
    print("  - has_face: True/False")
    print("  - face_count: number of faces")
    print("  - best_match_similarity: 0-100%")
    print("  - is_match: True if similarity > 40%")
