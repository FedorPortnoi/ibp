# Image and Face Recognition OSINT Research
## Comprehensive Findings for IBP Project

---

## Table of Contents
1. [Reverse Image Search APIs](#1-reverse-image-search-apis)
2. [Face Recognition Libraries Comparison](#2-face-recognition-libraries-comparison)
3. [PimEyes Alternatives](#3-pimeyes-alternatives)
4. [Face Matching Approaches](#4-face-matching-approaches)
5. [Photo Metadata Extraction](#5-photo-metadata-extraction)
6. [Social Media Photo Scraping](#6-social-media-photo-scraping)
7. [Code Examples](#7-code-examples)

---

## 1. Reverse Image Search APIs

### 1.1 Google Images

**Official API Status:** Google does NOT offer an official public Reverse Image Search API.

**Alternatives:**
- [Zenserp](https://zenserp.com/google-image-reverse-search-api/) - Paid API with Python support
- [SerpApi](https://serpapi.com/blog/using-google-reverse-images-api/) - Handles reverse image search with fast response times
- [Google-Reverse-Image-Search](https://github.com/RMNCLDYO/Google-Reverse-Image-Search) - Open-source Python library

**Automation Approaches:**
1. Selenium browser automation (clicking camera icon, uploading URL)
2. Network request reverse engineering with XPath selectors
3. Third-party scraping services (ScrapFly, ScrapingBee)

### 1.2 Yandex Images (Best for Russian Internet)

**Official API:** No official API for reverse image search.

**Third-Party Solutions:**
- [SerpApi Yandex Reverse Image API](https://serpapi.com/yandex-reverse-image-api) - Returns image_preview, similar_images, shopping_results
- [SearchAPI](https://www.searchapi.io/yandex-reverse-image-api) - Upload image URL for visually similar results
- [ScrapingBee Yandex Scraper](https://www.scrapingbee.com/scrapers/yandex-reverse-image-api/)
- [Zenserp Yandex API](https://zenserp.com/yandex-reverse-image-search-api/)

**Why Yandex is Critical for Russian OSINT:**
- Better facial recognition for finding Russian social media profiles
- Stronger at finding VK/OK profile photos
- Uses CBIR (Content-Based Image Retrieval) technology

### 1.3 TinEye API (Official)

**Status:** Official paid API available

**Python Library:** [pytineye](https://github.com/TinEye/pytineye)

**Installation:**
```bash
pip install pytineye
```

**Basic Usage:**
```python
from pytineye import TinEyeAPIRequest

# Initialize with API key
api = TinEyeAPIRequest(api_key='your_api_key')

# Search by URL
results = api.search_url('https://example.com/image.jpg')

# Search by file
results = api.search_data(image_data)

for match in results.matches:
    print(f"Found at: {match.backlinks[0].url}")
    print(f"Score: {match.score}")
```

**Pricing:** Pay-per-search bundles (commercial use)

### 1.4 Bing Visual Search

**API:** Part of Azure Cognitive Services

**Python SDK:**
```python
from azure.cognitiveservices.search.imagesearch import ImageSearchClient
from msrest.authentication import CognitiveServicesCredentials

client = ImageSearchClient(
    endpoint="https://api.cognitive.microsoft.com",
    credentials=CognitiveServicesCredentials(subscription_key)
)

# Visual search by URL
result = client.images.visual_search(url=image_url)
```

---

## 2. Face Recognition Libraries Comparison

### 2.1 face_recognition (dlib-based)

**Already mentioned in IBP CLAUDE.md**

| Metric | Value |
|--------|-------|
| Accuracy (LFW) | 99.38% |
| Embedding size | 128-dimensional |
| Default threshold | 0.6 (Euclidean distance) |
| Speed | Moderate (CPU-based) |

**Installation:**
```bash
pip install face_recognition
pip install dlib  # May require cmake
```

**Usage:**
```python
import face_recognition

# Load images
image1 = face_recognition.load_image_file("person1.jpg")
image2 = face_recognition.load_image_file("person2.jpg")

# Get face encodings (128-D vectors)
encoding1 = face_recognition.face_encodings(image1)[0]
encoding2 = face_recognition.face_encodings(image2)[0]

# Compare faces
distance = face_recognition.face_distance([encoding1], encoding2)[0]
is_match = distance < 0.6  # Default threshold

# Or use compare_faces
results = face_recognition.compare_faces([encoding1], encoding2, tolerance=0.6)
```

**Threshold Tuning:**
- Default 0.6 gives 99.38% accuracy on LFW
- Lower threshold (0.45-0.5) = fewer false positives, more false negatives
- Higher threshold (0.7) = more matches but more false positives

### 2.2 DeepFace

**Multi-model wrapper supporting 10+ face recognition models**

| Metric | Value |
|--------|-------|
| Accuracy (LFW) | 97.35% (base DeepFace) |
| Models | VGG-Face, Facenet, OpenFace, DeepID, ArcFace, Dlib, SFace |
| Embedding sizes | 128-4096D depending on model |
| Speed | Varies by model |

**Installation:**
```bash
pip install deepface
```

**Usage:**
```python
from deepface import DeepFace

# Verify if two images are the same person
result = DeepFace.verify(
    img1_path="img1.jpg",
    img2_path="img2.jpg",
    model_name="ArcFace",  # Best accuracy
    distance_metric="cosine"
)
print(f"Same person: {result['verified']}")
print(f"Distance: {result['distance']}")
print(f"Threshold: {result['threshold']}")

# Find faces in a database
dfs = DeepFace.find(
    img_path="query.jpg",
    db_path="facial_database/",
    model_name="ArcFace"
)

# Extract embeddings
embedding = DeepFace.represent(
    img_path="face.jpg",
    model_name="ArcFace"
)  # Returns 512-D vector for ArcFace
```

**DeepFace Model Thresholds (Cosine Distance):**
| Model | Threshold |
|-------|-----------|
| VGG-Face | 0.40 |
| Facenet | 0.40 |
| Facenet512 | 0.30 |
| ArcFace | 0.68 |
| Dlib | 0.07 |
| SFace | 0.593 |

### 2.3 InsightFace (ArcFace)

**State-of-the-art accuracy, GPU-optimized**

| Metric | Value |
|--------|-------|
| Accuracy (LFW) | 99.83% |
| Accuracy (MegaFace) | 98.36% |
| Embedding size | 512-dimensional |
| Speed | Fast (GPU), slow (CPU) |

**Installation:**
```bash
pip install insightface
pip install onnxruntime-gpu  # or onnxruntime for CPU
```

**Usage:**
```python
import insightface
from insightface.app import FaceAnalysis
import cv2
import numpy as np

# Initialize
app = FaceAnalysis(name='buffalo_l')  # or 'antelope'
app.prepare(ctx_id=0, det_size=(640, 640))  # ctx_id=-1 for CPU

# Load image
img = cv2.imread('face.jpg')

# Get face embeddings
faces = app.get(img)

if faces:
    embedding = faces[0].embedding  # 512-D numpy array
    bbox = faces[0].bbox
    landmarks = faces[0].kps

    # Compare two faces
    similarity = np.dot(embedding1, embedding2) / (
        np.linalg.norm(embedding1) * np.linalg.norm(embedding2)
    )
    # Threshold: similarity > 0.4 for same person
```

**ArcFace Threshold Recommendations:**
- Cosine similarity > 0.4: Same person (high confidence)
- Cosine similarity 0.3-0.4: Possible match (verify manually)
- Cosine similarity < 0.3: Different people

### 2.4 facenet-pytorch

**FaceNet implementation with MTCNN detector**

| Metric | Value |
|--------|-------|
| Accuracy (LFW) | 99.63% |
| Embedding size | 512-dimensional |
| Speed | Fast with GPU |

**Installation:**
```bash
pip install facenet-pytorch
```

**Usage:**
```python
from facenet_pytorch import MTCNN, InceptionResnetV1
from PIL import Image
import torch

# Initialize
mtcnn = MTCNN(image_size=160, margin=0)
resnet = InceptionResnetV1(pretrained='vggface2').eval()

# Load and align face
img = Image.open('face.jpg')
img_aligned = mtcnn(img)

# Get embedding
if img_aligned is not None:
    embedding = resnet(img_aligned.unsqueeze(0))  # 512-D tensor

    # Compare embeddings
    distance = (embedding1 - embedding2).norm().item()
    is_match = distance < 1.0  # Euclidean threshold
```

### Comparison Summary

| Library | Accuracy | Speed | GPU Support | Ease of Use | Best For |
|---------|----------|-------|-------------|-------------|----------|
| face_recognition | 99.38% | Slow | No | Very Easy | Quick prototyping |
| DeepFace | 97-99% | Medium | Optional | Easy | Multi-model flexibility |
| InsightFace | 99.83% | Fast | Yes | Medium | Production, high accuracy |
| facenet-pytorch | 99.63% | Fast | Yes | Medium | Deep learning projects |

**Recommendation for IBP:** Use **InsightFace** for best accuracy, or **DeepFace with ArcFace model** for easier integration.

---

## 3. PimEyes Alternatives

### 3.1 Open-Source Tools

**Search by Image (Browser Extension)**
- Supports Google, Bing, Yandex, Baidu, TinEye
- [GitHub Project](https://github.com/nickytonline/search-by-image)

**EagleEye**
- Ethical hacking/research tool
- Searches across social media platforms
- Requires technical setup

### 3.2 Commercial Alternatives

| Service | Coverage | Price | API |
|---------|----------|-------|-----|
| FaceCheck.ID | 560M+ faces | Free trial | Limited |
| Search4faces | VK/OK 1.1B faces | Free | No official |
| Yandex Images | Russian internet | Free | Via third-party |
| Lenso.ai | General | Freemium | Yes |
| FaceOnLive | Global | Paid | Yes |

### 3.3 Building Your Own Face Search Engine

**Architecture:**
1. **Face Detection:** MTCNN, RetinaFace, or InsightFace detector
2. **Embedding Extraction:** ArcFace/InsightFace (512-D vectors)
3. **Vector Storage:** FAISS, Milvus, or Pinecone
4. **Search:** Approximate nearest neighbor (ANN) search

**FAISS Implementation:**
```python
import faiss
import numpy as np
from insightface.app import FaceAnalysis

# Initialize face analyzer
app = FaceAnalysis(name='buffalo_l')
app.prepare(ctx_id=0)

# Create FAISS index for 512-D embeddings
dimension = 512
index = faiss.IndexFlatIP(dimension)  # Inner product (cosine similarity)

# Add embeddings to index
embeddings = np.array(all_embeddings).astype('float32')
faiss.normalize_L2(embeddings)  # Normalize for cosine similarity
index.add(embeddings)

# Search for similar faces
query = app.get(query_image)[0].embedding
query = np.array([query]).astype('float32')
faiss.normalize_L2(query)

k = 10  # Top 10 matches
distances, indices = index.search(query, k)

for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
    print(f"Match {i+1}: Index {idx}, Similarity {dist:.3f}")
```

**Scaling with FAISS IVF:**
```python
# For large datasets (millions of faces)
nlist = 100  # Number of clusters
quantizer = faiss.IndexFlatIP(dimension)
index = faiss.IndexIVFFlat(quantizer, dimension, nlist, faiss.METRIC_INNER_PRODUCT)

# Train the index
index.train(embeddings)
index.add(embeddings)

# Set search parameters
index.nprobe = 10  # Number of clusters to search
```

---

## 4. Face Matching Approaches

### 4.1 Embedding Generation

**What are Face Embeddings?**
- Dense vector representations of faces (128-512 dimensions)
- Encode facial features in a way that similar faces have similar vectors
- Generated by CNN models trained on millions of faces

**Best Models for Embeddings:**
1. **ArcFace (InsightFace):** 512-D, best accuracy
2. **FaceNet:** 512-D, widely used
3. **VGG-Face:** 2048-D, older but reliable
4. **Dlib:** 128-D, good for CPU-only

### 4.2 Similarity Metrics

**Cosine Similarity:**
```python
import numpy as np

def cosine_similarity(emb1, emb2):
    return np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))

# Range: -1 to 1 (1 = identical)
# Threshold: > 0.4 for ArcFace
```

**Euclidean Distance:**
```python
def euclidean_distance(emb1, emb2):
    return np.linalg.norm(emb1 - emb2)

# Range: 0 to infinity (0 = identical)
# Threshold: < 0.6 for dlib face_recognition
```

**L2 Normalized Euclidean (equivalent to cosine):**
```python
def l2_normalized_distance(emb1, emb2):
    emb1_norm = emb1 / np.linalg.norm(emb1)
    emb2_norm = emb2 / np.linalg.norm(emb2)
    return np.linalg.norm(emb1_norm - emb2_norm)

# Range: 0 to 2
# Distance = sqrt(2 * (1 - cosine_similarity))
```

### 4.3 Threshold Tuning

**Finding Optimal Threshold:**
```python
from sklearn.metrics import precision_recall_curve

# positive_pairs: list of (emb1, emb2) for same person
# negative_pairs: list of (emb1, emb2) for different people

similarities = []
labels = []

for emb1, emb2 in positive_pairs:
    similarities.append(cosine_similarity(emb1, emb2))
    labels.append(1)

for emb1, emb2 in negative_pairs:
    similarities.append(cosine_similarity(emb1, emb2))
    labels.append(0)

precision, recall, thresholds = precision_recall_curve(labels, similarities)

# Find threshold for desired precision/recall
target_recall = 0.95
idx = np.argmin(np.abs(recall - target_recall))
optimal_threshold = thresholds[idx]
```

**Risk-Based Thresholds:**
- High security (few false positives): Threshold 0.5+
- Balanced: Threshold 0.4
- High recall (few false negatives): Threshold 0.3

### 4.4 Handling Multiple Faces

**Face Detection and Cropping:**
```python
import cv2
from insightface.app import FaceAnalysis

app = FaceAnalysis(name='buffalo_l')
app.prepare(ctx_id=0)

def extract_all_faces(image_path):
    img = cv2.imread(image_path)
    faces = app.get(img)

    results = []
    for i, face in enumerate(faces):
        bbox = face.bbox.astype(int)
        x1, y1, x2, y2 = bbox

        # Crop face with margin
        margin = 20
        face_crop = img[max(0, y1-margin):y2+margin, max(0, x1-margin):x2+margin]

        results.append({
            'embedding': face.embedding,
            'bbox': bbox,
            'confidence': face.det_score,
            'crop': face_crop,
            'landmarks': face.kps
        })

    return results
```

**Face Alignment:**
```python
from insightface.utils import face_align

def align_face(img, landmarks):
    # InsightFace uses 5-point landmarks for alignment
    aligned = face_align.norm_crop(img, landmarks)
    return aligned  # 112x112 aligned face
```

---

## 5. Photo Metadata Extraction

### 5.1 EXIF Data with Pillow

```python
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

def extract_exif(image_path):
    image = Image.open(image_path)
    exif_data = image._getexif()

    if not exif_data:
        return None

    metadata = {}
    for tag_id, value in exif_data.items():
        tag = TAGS.get(tag_id, tag_id)
        metadata[tag] = value

    return metadata

def extract_gps(image_path):
    image = Image.open(image_path)
    exif_data = image._getexif()

    if not exif_data:
        return None

    gps_info = {}
    for tag_id, value in exif_data.items():
        tag = TAGS.get(tag_id, tag_id)
        if tag == 'GPSInfo':
            for gps_tag_id, gps_value in value.items():
                gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                gps_info[gps_tag] = gps_value

    return gps_info
```

### 5.2 GPS Coordinate Conversion

```python
def dms_to_decimal(dms, ref):
    """Convert GPS coordinates from DMS to decimal degrees."""
    degrees = float(dms[0])
    minutes = float(dms[1])
    seconds = float(dms[2])

    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)

    if ref in ['S', 'W']:
        decimal = -decimal

    return decimal

def get_coordinates(image_path):
    gps = extract_gps(image_path)

    if not gps:
        return None

    lat = dms_to_decimal(gps['GPSLatitude'], gps['GPSLatitudeRef'])
    lon = dms_to_decimal(gps['GPSLongitude'], gps['GPSLongitudeRef'])

    return {'latitude': lat, 'longitude': lon}
```

### 5.3 Comprehensive Metadata with exifread

```python
import exifread

def extract_all_metadata(image_path):
    with open(image_path, 'rb') as f:
        tags = exifread.process_file(f)

    metadata = {
        'camera': {
            'make': str(tags.get('Image Make', '')),
            'model': str(tags.get('Image Model', '')),
            'software': str(tags.get('Image Software', '')),
        },
        'settings': {
            'exposure_time': str(tags.get('EXIF ExposureTime', '')),
            'f_number': str(tags.get('EXIF FNumber', '')),
            'iso': str(tags.get('EXIF ISOSpeedRatings', '')),
            'focal_length': str(tags.get('EXIF FocalLength', '')),
        },
        'datetime': {
            'original': str(tags.get('EXIF DateTimeOriginal', '')),
            'digitized': str(tags.get('EXIF DateTimeDigitized', '')),
        },
        'gps': {}
    }

    # GPS data
    if 'GPS GPSLatitude' in tags:
        metadata['gps'] = {
            'latitude': tags.get('GPS GPSLatitude'),
            'latitude_ref': str(tags.get('GPS GPSLatitudeRef', 'N')),
            'longitude': tags.get('GPS GPSLongitude'),
            'longitude_ref': str(tags.get('GPS GPSLongitudeRef', 'E')),
            'altitude': str(tags.get('GPS GPSAltitude', '')),
        }

    return metadata
```

### 5.4 Device Identification

```python
def identify_device(image_path):
    """Extract device fingerprinting information."""
    with open(image_path, 'rb') as f:
        tags = exifread.process_file(f)

    return {
        'device_make': str(tags.get('Image Make', 'Unknown')),
        'device_model': str(tags.get('Image Model', 'Unknown')),
        'software_version': str(tags.get('Image Software', 'Unknown')),
        'unique_camera_id': str(tags.get('EXIF BodySerialNumber',
                                         tags.get('MakerNote SerialNumber', 'Unknown'))),
        'lens_info': str(tags.get('EXIF LensModel',
                                  tags.get('EXIF LensMake', 'Unknown'))),
    }
```

---

## 6. Social Media Photo Scraping

### 6.1 VK API Photo Access

**Getting Profile Photos:**
```python
import vk_api

def get_vk_photos(access_token, user_id):
    vk_session = vk_api.VkApi(token=access_token)
    vk = vk_session.get_api()

    # Get profile photos (album -6 = profile)
    photos = vk.photos.get(
        owner_id=user_id,
        album_id='profile',  # or -6
        extended=1,
        photo_sizes=1,
        count=100
    )

    photo_urls = []
    for photo in photos['items']:
        # Get largest size
        sizes = sorted(photo['sizes'], key=lambda x: x['width'], reverse=True)
        if sizes:
            photo_urls.append({
                'url': sizes[0]['url'],
                'width': sizes[0]['width'],
                'height': sizes[0]['height'],
                'date': photo['date']
            })

    return photo_urls

def download_vk_photo(url, save_path):
    import requests
    response = requests.get(url)
    with open(save_path, 'wb') as f:
        f.write(response.content)
```

**VK Photo Albums:**
```python
def get_all_vk_albums(access_token, user_id):
    vk_session = vk_api.VkApi(token=access_token)
    vk = vk_session.get_api()

    albums = vk.photos.getAlbums(
        owner_id=user_id,
        need_system=1,  # Include system albums (wall, profile, saved)
        need_covers=1
    )

    return albums['items']
```

### 6.2 Telegram Avatar Access

**Using Telethon:**
```python
from telethon import TelegramClient
from telethon.tl.functions.photos import GetUserPhotosRequest
import asyncio

async def get_telegram_photos(client, username):
    # Get user entity
    user = await client.get_entity(username)

    # Get profile photos
    photos = await client(GetUserPhotosRequest(
        user_id=user,
        offset=0,
        max_id=0,
        limit=100
    ))

    downloaded = []
    for i, photo in enumerate(photos.photos):
        path = f'telegram_photo_{i}.jpg'
        await client.download_media(photo, path)
        downloaded.append(path)

    return downloaded

# Usage
async def main():
    client = TelegramClient('session', api_id, api_hash)
    await client.start()

    photos = await get_telegram_photos(client, '@username')
    print(f"Downloaded {len(photos)} photos")
```

**Using Pyrogram:**
```python
from pyrogram import Client

async def get_chat_photos_pyrogram(client, chat_id):
    photos = []
    async for photo in client.get_chat_photos(chat_id):
        path = await client.download_media(photo.file_id)
        photos.append(path)
    return photos
```

### 6.3 Legal Considerations

**VK API Terms:**
- Use official VK API with access token
- Respect rate limits (3 requests/second)
- User must authorize access to their data
- Don't store personal data longer than needed

**Telegram API Terms:**
- Use official Telegram APIs (MTProto)
- Respect user privacy settings
- Don't spam or abuse the API
- Consider GDPR for EU users

**General OSINT Ethics:**
- Public information only (unless authorized)
- Document data sources
- Comply with local laws (especially GDPR, Russian 152-FZ)
- Consider the impact on individuals

---

## 7. Code Examples

### 7.1 Complete Face Matching Pipeline

```python
"""
Complete face matching pipeline for IBP.
Uses InsightFace for best accuracy with FAISS for fast search.
"""

import cv2
import numpy as np
import faiss
from insightface.app import FaceAnalysis
from pathlib import Path
import pickle
import logging

logger = logging.getLogger(__name__)


class FaceMatchingService:
    def __init__(self, model_name='buffalo_l', use_gpu=True):
        """Initialize face analysis and FAISS index."""
        self.app = FaceAnalysis(name=model_name)
        ctx_id = 0 if use_gpu else -1
        self.app.prepare(ctx_id=ctx_id, det_size=(640, 640))

        self.dimension = 512  # ArcFace embedding dimension
        self.index = None
        self.embeddings = []
        self.metadata = []  # Store profile info for each embedding

    def extract_embedding(self, image_path):
        """Extract face embedding from image."""
        img = cv2.imread(str(image_path))
        if img is None:
            logger.error(f"Could not read image: {image_path}")
            return None

        faces = self.app.get(img)

        if not faces:
            logger.warning(f"No face detected in: {image_path}")
            return None

        # Return embedding of largest/most confident face
        faces.sort(key=lambda x: x.det_score, reverse=True)
        return faces[0].embedding

    def extract_all_embeddings(self, image_path):
        """Extract embeddings for all faces in image."""
        img = cv2.imread(str(image_path))
        if img is None:
            return []

        faces = self.app.get(img)

        results = []
        for face in faces:
            results.append({
                'embedding': face.embedding,
                'bbox': face.bbox.tolist(),
                'confidence': float(face.det_score),
                'landmarks': face.kps.tolist()
            })

        return results

    def build_index(self, embeddings_with_metadata):
        """
        Build FAISS index from embeddings.

        Args:
            embeddings_with_metadata: List of (embedding, metadata) tuples
        """
        self.embeddings = []
        self.metadata = []

        for emb, meta in embeddings_with_metadata:
            self.embeddings.append(emb)
            self.metadata.append(meta)

        # Convert to numpy array
        embeddings_array = np.array(self.embeddings).astype('float32')

        # Normalize for cosine similarity
        faiss.normalize_L2(embeddings_array)

        # Create index
        self.index = faiss.IndexFlatIP(self.dimension)
        self.index.add(embeddings_array)

        logger.info(f"Built index with {len(self.embeddings)} faces")

    def search(self, query_image_path, top_k=10, threshold=0.4):
        """
        Search for similar faces.

        Args:
            query_image_path: Path to query image
            top_k: Number of results to return
            threshold: Minimum similarity score (0-1)

        Returns:
            List of (metadata, similarity_score) tuples
        """
        if self.index is None:
            logger.error("Index not built")
            return []

        embedding = self.extract_embedding(query_image_path)
        if embedding is None:
            return []

        # Normalize query
        query = np.array([embedding]).astype('float32')
        faiss.normalize_L2(query)

        # Search
        distances, indices = self.index.search(query, top_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if dist >= threshold:
                results.append((self.metadata[idx], float(dist)))

        return results

    def compare_two_faces(self, image1_path, image2_path):
        """
        Compare two faces and return similarity.

        Returns:
            dict with 'is_match', 'similarity', 'threshold'
        """
        emb1 = self.extract_embedding(image1_path)
        emb2 = self.extract_embedding(image2_path)

        if emb1 is None or emb2 is None:
            return {'is_match': False, 'similarity': 0, 'error': 'Face not detected'}

        # Cosine similarity
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))

        threshold = 0.4
        is_match = similarity > threshold

        return {
            'is_match': bool(is_match),
            'similarity': float(similarity),
            'threshold': threshold
        }

    def save_index(self, path):
        """Save index and metadata to disk."""
        faiss.write_index(self.index, str(path) + '.faiss')
        with open(str(path) + '.meta', 'wb') as f:
            pickle.dump({
                'embeddings': self.embeddings,
                'metadata': self.metadata
            }, f)

    def load_index(self, path):
        """Load index and metadata from disk."""
        self.index = faiss.read_index(str(path) + '.faiss')
        with open(str(path) + '.meta', 'rb') as f:
            data = pickle.load(f)
            self.embeddings = data['embeddings']
            self.metadata = data['metadata']


# Example usage
if __name__ == '__main__':
    service = FaceMatchingService(use_gpu=False)

    # Compare two faces
    result = service.compare_two_faces('face1.jpg', 'face2.jpg')
    print(f"Match: {result['is_match']}, Similarity: {result['similarity']:.3f}")
```

### 7.2 Multi-Service Reverse Image Search

```python
"""
Multi-service reverse image search combining:
- Search4faces (VK/OK)
- Yandex Images
- TinEye (if API key available)
"""

import asyncio
import aiohttp
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ReverseSearchResult:
    source_url: str
    page_url: str
    platform: str
    title: Optional[str] = None
    similarity: Optional[float] = None
    service: str = ""


class ReverseImageSearchService:

    def __init__(self, tineye_api_key=None):
        self.tineye_key = tineye_api_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'
        })

    async def search_all(self, image_path) -> List[ReverseSearchResult]:
        """Search all available services."""
        results = []

        # Run searches in parallel
        tasks = [
            self._search_yandex(image_path),
        ]

        if self.tineye_key:
            tasks.append(self._search_tineye(image_path))

        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for result in completed:
            if isinstance(result, list):
                results.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Search failed: {result}")

        return self._deduplicate(results)

    async def _search_yandex(self, image_path) -> List[ReverseSearchResult]:
        """Search Yandex Images."""
        results = []

        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()

            response = self.session.post(
                'https://yandex.ru/images/search',
                files={'upfile': ('photo.jpg', image_data, 'image/jpeg')},
                data={'rpt': 'imageview'},
                timeout=30,
                allow_redirects=True
            )

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Find social media links
                for link in soup.find_all('a', href=True):
                    url = link.get('href', '')

                    platform = self._detect_platform(url)
                    if platform:
                        results.append(ReverseSearchResult(
                            source_url=url,
                            page_url=response.url,
                            platform=platform,
                            service='yandex'
                        ))

        except Exception as e:
            logger.error(f"Yandex search failed: {e}")

        return results

    async def _search_tineye(self, image_path) -> List[ReverseSearchResult]:
        """Search TinEye API."""
        results = []

        try:
            from pytineye import TinEyeAPIRequest

            api = TinEyeAPIRequest(api_key=self.tineye_key)

            with open(image_path, 'rb') as f:
                response = api.search_data(f.read())

            for match in response.matches:
                for backlink in match.backlinks:
                    platform = self._detect_platform(backlink.url)
                    results.append(ReverseSearchResult(
                        source_url=match.image_url,
                        page_url=backlink.url,
                        platform=platform or 'web',
                        title=backlink.page_title,
                        similarity=match.score,
                        service='tineye'
                    ))

        except ImportError:
            logger.warning("pytineye not installed")
        except Exception as e:
            logger.error(f"TinEye search failed: {e}")

        return results

    @staticmethod
    def _detect_platform(url):
        """Detect social media platform from URL."""
        platforms = {
            'vk.com': 'vk',
            'ok.ru': 'ok',
            'instagram.com': 'instagram',
            'facebook.com': 'facebook',
            't.me': 'telegram',
            'twitter.com': 'twitter',
            'x.com': 'twitter',
            'tiktok.com': 'tiktok',
            'linkedin.com': 'linkedin',
        }

        for domain, platform in platforms.items():
            if domain in url.lower():
                return platform
        return None

    @staticmethod
    def _deduplicate(results):
        """Remove duplicate URLs."""
        seen = set()
        unique = []
        for r in results:
            key = r.page_url.lower().rstrip('/')
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique
```

### 7.3 EXIF Analysis Tool

```python
"""
Comprehensive EXIF metadata extractor for OSINT.
"""

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import exifread
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class PhotoMetadata:
    # Camera info
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    software: Optional[str] = None

    # Location
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None

    # Time
    datetime_original: Optional[datetime] = None
    datetime_digitized: Optional[datetime] = None

    # Camera settings
    exposure_time: Optional[str] = None
    f_number: Optional[float] = None
    iso: Optional[int] = None
    focal_length: Optional[float] = None

    # Dimensions
    width: Optional[int] = None
    height: Optional[int] = None
    orientation: Optional[int] = None

    # Device ID
    serial_number: Optional[str] = None
    lens_model: Optional[str] = None


class EXIFAnalyzer:

    @staticmethod
    def analyze(image_path: str) -> PhotoMetadata:
        """Extract all metadata from image."""
        metadata = PhotoMetadata()
        path = Path(image_path)

        if not path.exists():
            logger.error(f"Image not found: {image_path}")
            return metadata

        # Use exifread for comprehensive extraction
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f, details=True)

        # Camera info
        metadata.camera_make = str(tags.get('Image Make', '')).strip()
        metadata.camera_model = str(tags.get('Image Model', '')).strip()
        metadata.software = str(tags.get('Image Software', '')).strip()

        # Dimensions
        metadata.width = int(str(tags.get('EXIF ExifImageWidth', 0))) or None
        metadata.height = int(str(tags.get('EXIF ExifImageLength', 0))) or None
        metadata.orientation = int(str(tags.get('Image Orientation', 1)))

        # Camera settings
        metadata.iso = int(str(tags.get('EXIF ISOSpeedRatings', 0))) or None
        metadata.exposure_time = str(tags.get('EXIF ExposureTime', ''))

        # F-number
        fnumber = tags.get('EXIF FNumber')
        if fnumber:
            try:
                metadata.f_number = float(fnumber.values[0])
            except:
                pass

        # Focal length
        focal = tags.get('EXIF FocalLength')
        if focal:
            try:
                metadata.focal_length = float(focal.values[0])
            except:
                pass

        # Datetime
        dt_original = str(tags.get('EXIF DateTimeOriginal', ''))
        if dt_original:
            try:
                metadata.datetime_original = datetime.strptime(
                    dt_original, '%Y:%m:%d %H:%M:%S'
                )
            except:
                pass

        dt_digitized = str(tags.get('EXIF DateTimeDigitized', ''))
        if dt_digitized:
            try:
                metadata.datetime_digitized = datetime.strptime(
                    dt_digitized, '%Y:%m:%d %H:%M:%S'
                )
            except:
                pass

        # GPS
        gps_coords = EXIFAnalyzer._extract_gps(tags)
        if gps_coords:
            metadata.latitude = gps_coords[0]
            metadata.longitude = gps_coords[1]

        altitude = tags.get('GPS GPSAltitude')
        if altitude:
            try:
                metadata.altitude = float(altitude.values[0])
            except:
                pass

        # Serial number
        metadata.serial_number = str(tags.get('EXIF BodySerialNumber',
                                              tags.get('MakerNote SerialNumber', '')))
        metadata.lens_model = str(tags.get('EXIF LensModel', ''))

        return metadata

    @staticmethod
    def _extract_gps(tags) -> Optional[Tuple[float, float]]:
        """Extract GPS coordinates from EXIF tags."""
        lat = tags.get('GPS GPSLatitude')
        lat_ref = str(tags.get('GPS GPSLatitudeRef', 'N'))
        lon = tags.get('GPS GPSLongitude')
        lon_ref = str(tags.get('GPS GPSLongitudeRef', 'E'))

        if not lat or not lon:
            return None

        try:
            lat_decimal = EXIFAnalyzer._dms_to_decimal(lat.values, lat_ref)
            lon_decimal = EXIFAnalyzer._dms_to_decimal(lon.values, lon_ref)
            return (lat_decimal, lon_decimal)
        except Exception as e:
            logger.error(f"GPS conversion failed: {e}")
            return None

    @staticmethod
    def _dms_to_decimal(dms, ref):
        """Convert DMS to decimal degrees."""
        d = float(dms[0])
        m = float(dms[1])
        s = float(dms[2])

        decimal = d + (m / 60.0) + (s / 3600.0)

        if ref in ['S', 'W']:
            decimal = -decimal

        return decimal

    @staticmethod
    def get_google_maps_url(lat: float, lon: float) -> str:
        """Generate Google Maps URL for coordinates."""
        return f"https://www.google.com/maps?q={lat},{lon}"

    @staticmethod
    def get_yandex_maps_url(lat: float, lon: float) -> str:
        """Generate Yandex Maps URL for coordinates."""
        return f"https://yandex.ru/maps/?pt={lon},{lat}&z=15"


# Example usage
if __name__ == '__main__':
    analyzer = EXIFAnalyzer()
    metadata = analyzer.analyze('photo.jpg')

    print(f"Camera: {metadata.camera_make} {metadata.camera_model}")
    print(f"Date: {metadata.datetime_original}")

    if metadata.latitude and metadata.longitude:
        print(f"Location: {metadata.latitude}, {metadata.longitude}")
        print(f"Map: {analyzer.get_google_maps_url(metadata.latitude, metadata.longitude)}")
```

---

## References

### Reverse Image Search
- [Zenserp Google Reverse Image API](https://zenserp.com/google-image-reverse-search-api/)
- [SerpApi](https://serpapi.com/blog/using-google-reverse-images-api/)
- [SerpApi Yandex API](https://serpapi.com/yandex-reverse-image-api)
- [TinEye API](https://services.tineye.com/TinEyeAPI)
- [pytineye GitHub](https://github.com/TinEye/pytineye)

### Face Recognition
- [DeepFace GitHub](https://github.com/serengil/deepface)
- [InsightFace GitHub](https://github.com/deepinsight/insightface)
- [face_recognition Documentation](https://face-recognition.readthedocs.io/)
- [ArcFace Deep Dive](https://learnopencv.com/face-recognition-with-arcface/)
- [DeepFace vs InsightFace Comparison](https://dev.to/wintrover/upgrading-face-recognition-from-deepface-to-insightface-performance-quality-and-integration-5b7f)

### Vector Search
- [FAISS GitHub](https://github.com/facebookresearch/faiss)
- [Pinecone Vector Similarity](https://www.pinecone.io/learn/vector-similarity/)
- [FAISS Tutorial](https://www.pinecone.io/learn/series/faiss/faiss-tutorial/)

### Threshold Tuning
- [Fine-Tuning Face Recognition Thresholds](https://sefiks.com/2020/05/22/fine-tuning-the-threshold-in-face-recognition/)
- [dlib Threshold Documentation](http://blog.dlib.net/2017/02/high-quality-face-recognition-with-deep.html)

### EXIF and Metadata
- [GPS from Photos with Python](https://sylvaindurand.org/gps-data-from-photos-with-python/)
- [Python Pillow Metadata](https://www.tutorialspoint.com/python_pillow/python_pillow_extracting_image_metadata.htm)
- [EXIF Extraction Guide](https://auth0.com/blog/read-edit-exif-metadata-in-photos-with-python/)

### Social Media APIs
- [vk_api Documentation](https://vk-api.readthedocs.io/)
- [Telethon Documentation](https://docs.telethon.dev/)
- [Pyrogram Documentation](https://docs.pyrogram.org/)

### PimEyes Alternatives
- [PimEyes Alternatives 2025](https://lenso.ai/en/blog/news/best-pimeyes-alternatives-competitors-for-reverse-face-search-in-2024)
- [Search4faces (Bellingcat reference)](https://bellingcat.gitbook.io/toolkit/more/all-tools/search4faces)
