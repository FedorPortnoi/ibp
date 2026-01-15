"""
IBP Phase 1 Routes - Social Media Discovery (OPTIMIZED)
========================================================
Speed Optimized: 190 minutes → 5-10 minutes!
"""

from flask import Blueprint, render_template, request, jsonify, send_from_directory, current_app
from werkzeug.utils import secure_filename
import os
import uuid
import threading
from datetime import datetime

# Import the OPTIMIZED search service
from app.services.combined_search import CombinedSearchService

phase1_bp = Blueprint('phase1', __name__, url_prefix='/phase1')

# ============================================
# TASK STORAGE (in production, use Redis/DB)
# ============================================
tasks = {}

class TaskStatus:
    """Holds the status of a search task."""
    def __init__(self, task_id: str, target_name: str, photo_path: str = None):
        self.task_id = task_id
        self.target_name = target_name
        self.photo_path = photo_path
        self.photo_filename = os.path.basename(photo_path) if photo_path else None
        
        # Progress tracking
        self.phase = 'initializing'
        self.percent_complete = 0
        self.items_processed = 0
        self.total_items = 0
        
        # Counts
        self.usernames_generated = 0
        self.raw_accounts = 0
        self.accounts_validated = 0
        
        # Messages for terminal
        self.messages = []
        
        # Recent accounts for live display
        self.recent_accounts = []
        self.all_accounts = []
        
        # Results
        self.results = None
        self.error = None
        self.started_at = datetime.now()
        self.completed_at = None
    
    def add_message(self, text: str, msg_type: str = 'info'):
        """Add a message for the terminal display."""
        self.messages.append({
            'text': text,
            'type': msg_type,
            'time': datetime.now().isoformat()
        })
    
    def add_account(self, account: dict):
        """Add a discovered account."""
        self.all_accounts.append(account)
        # Keep last 50 in recent for UI updates
        self.recent_accounts.append(account)
        if len(self.recent_accounts) > 50:
            self.recent_accounts = self.recent_accounts[-50:]
    
    def to_dict(self):
        """Convert to dict for JSON response."""
        return {
            'task_id': self.task_id,
            'target_name': self.target_name,
            'phase': self.phase,
            'percent_complete': self.percent_complete,
            'items_processed': self.items_processed,
            'total_items': self.total_items,
            'usernames_generated': self.usernames_generated,
            'raw_accounts': self.raw_accounts,
            'accounts_validated': self.accounts_validated,
            'messages': self.messages,
            'recent_accounts': self.recent_accounts,
            'error': self.error
        }


# ============================================
# HELPER FUNCTIONS
# ============================================

def allowed_file(filename):
    """Check if file extension is allowed."""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_upload_folder():
    """Get the upload folder path."""
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    if not os.path.isabs(upload_folder):
        upload_folder = os.path.join(current_app.root_path, upload_folder)
    os.makedirs(upload_folder, exist_ok=True)
    return upload_folder


def run_search_task(task_id: str):
    """Background task to run the OPTIMIZED search."""
    task = tasks.get(task_id)
    if not task:
        return
    
    try:
        task.add_message(f'Target: {task.target_name}', 'info')
        task.add_message(f'Mode: SPEED OPTIMIZED (v6.0)', 'info')
        task.phase = 'generating'
        
        # Progress callback
        def progress_callback(data: dict):
            """Update task with progress data."""
            # Update phase
            phase_map = {
                'generating_usernames': 'generating',
                'searching': 'searching',
                'maigret_search': 'maigret',
                'sherlock_search': 'sherlock',
                'filtering': 'filtering',
                'validating': 'validating',
                'face_matching': 'face_matching',
                'finalizing': 'finalizing',
                'complete': 'complete'
            }
            
            if 'phase' in data:
                task.phase = phase_map.get(data['phase'], data['phase'])
            
            # Update counts
            if 'usernames_generated' in data:
                task.usernames_generated = data['usernames_generated']
            if 'items_total' in data and data['items_total'] > 0:
                task.usernames_generated = data['items_total']
            if 'raw_accounts' in data:
                task.raw_accounts = data['raw_accounts']
            if 'accounts_found' in data:
                task.raw_accounts = data['accounts_found']
            if 'accounts_validated' in data:
                task.accounts_validated = data['accounts_validated']
            if 'items_processed' in data:
                task.items_processed = data['items_processed']
            if 'items_total' in data:
                task.total_items = data['items_total']
            
            # Update percent
            if 'percent_complete' in data:
                task.percent_complete = data['percent_complete']
            
            # Add message if present
            if 'message' in data:
                msg_type = data.get('message_type', 'info')
                task.add_message(data['message'], msg_type)
            
            # Add account if present
            if 'account' in data:
                task.add_account(data['account'])
        
        # Initialize OPTIMIZED service
        has_photo = task.photo_path and os.path.exists(task.photo_path)
        
        # ============================================
        # OPTIMIZED PARAMETERS (was 100 usernames, now 15)
        # ============================================
        service = CombinedSearchService(
            max_usernames=15,           # ✅ Reduced from 100 (realistic variations only)
            request_delay=0.3,          # ✅ Reduced from 1.0
            enable_face_matching=has_photo,
            max_photos_per_profile=20,  # ✅ Reduced from 50
            timeout=30                  # ✅ Reduced from 120
        )
        
        # Run search
        task.add_message('Starting BATCH search (parallel mode)...', 'info')
        
        results = service.search(
            target_name=task.target_name,
            target_photo_path=task.photo_path if has_photo else None,
            progress_callback=progress_callback
        )
        
        # Store results
        task.results = results
        task.phase = 'complete'
        task.percent_complete = 100
        task.completed_at = datetime.now()
        
        # Final counts from results
        if results:
            stats = results.get('stats', {})
            task.accounts_validated = len(results.get('accounts', results.get('results', [])))
            task.raw_accounts = stats.get('raw_accounts', stats.get('accounts_found', task.raw_accounts))
            task.usernames_generated = stats.get('usernames_searched', stats.get('usernames_generated', task.usernames_generated))
        
        elapsed = (task.completed_at - task.started_at).total_seconds()
        task.add_message(f'✅ Search complete in {int(elapsed)}s! Found {task.accounts_validated} accounts', 'success')
        
    except Exception as e:
        task.phase = 'error'
        task.error = str(e)
        task.add_message(f'Error: {str(e)}', 'error')
        import traceback
        traceback.print_exc()


# ============================================
# ROUTES
# ============================================

@phase1_bp.route('/')
def index():
    """Phase 1 start page - input form."""
    return render_template('phase1_start.html')


@phase1_bp.route('/start', methods=['POST'])
def start_search():
    """Start a new search task."""
    # Get form data
    target_name = request.form.get('target_name', '').strip()
    
    if not target_name:
        return jsonify({'error': 'Target name is required'}), 400
    
    # Handle photo upload
    photo_path = None
    photo_filename = None
    
    if 'photo' in request.files:
        file = request.files['photo']
        if file and file.filename and allowed_file(file.filename):
            photo_filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
            upload_folder = get_upload_folder()
            photo_path = os.path.join(upload_folder, photo_filename)
            file.save(photo_path)
    
    # Create task
    task_id = uuid.uuid4().hex
    task = TaskStatus(task_id, target_name, photo_path)
    tasks[task_id] = task
    
    # Start background thread
    thread = threading.Thread(target=run_search_task, args=(task_id,))
    thread.daemon = True
    thread.start()
    
    # Redirect to loading page
    return jsonify({
        'success': True,
        'task_id': task_id,
        'redirect': f'/phase1/loading/{task_id}'
    })


@phase1_bp.route('/loading/<task_id>')
def loading(task_id):
    """Show the cyberpunk loading page."""
    task = tasks.get(task_id)
    
    if not task:
        return render_template('error.html', error='Task not found'), 404
    
    return render_template(
        'phase1_loading.html',
        task_id=task_id,
        target_name=task.target_name,
        has_photo=task.photo_path is not None,
        photo_filename=task.photo_filename
    )


@phase1_bp.route('/progress/<task_id>')
def get_progress(task_id):
    """Get task progress for polling."""
    task = tasks.get(task_id)
    
    if not task:
        return jsonify({'error': 'Task not found', 'phase': 'error'}), 404
    
    return jsonify(task.to_dict())


@phase1_bp.route('/results/<task_id>')
def results(task_id):
    """Show search results."""
    task = tasks.get(task_id)
    
    if not task:
        return render_template('error.html', error='Task not found'), 404
    
    if task.phase == 'error':
        return render_template('error.html', error=task.error), 500
    
    if task.phase != 'complete':
        # Still running, redirect to loading
        return render_template(
            'phase1_loading.html',
            task_id=task_id,
            target_name=task.target_name,
            has_photo=task.photo_path is not None,
            photo_filename=task.photo_filename
        )
    
    # Get accounts from results (handle both 'accounts' and 'results' keys)
    results_data = task.results or {}
    accounts = results_data.get('accounts', results_data.get('results', []))
    
    # Group by platform
    platforms = {}
    for acc in accounts:
        platform = acc.get('platform', 'Unknown')
        if platform not in platforms:
            platforms[platform] = []
        platforms[platform].append(acc)
    
    # Sort platforms by count
    sorted_platforms = sorted(platforms.items(), key=lambda x: len(x[1]), reverse=True)
    
    # Calculate stats
    stats = results_data.get('stats', {})
    elapsed_time = (task.completed_at - task.started_at).total_seconds() if task.completed_at else 0
    
    return render_template(
        'phase1_results.html',
        task_id=task_id,
        target_name=task.target_name,
        has_photo=task.photo_path is not None,
        photo_filename=task.photo_filename,
        platforms=sorted_platforms,
        total_accounts=len(accounts),
        stats={
            'usernames_searched': stats.get('usernames_searched', stats.get('usernames_generated', task.usernames_generated)),
            'raw_accounts': stats.get('raw_accounts', stats.get('accounts_found', task.raw_accounts)),
            'validated_accounts': stats.get('accounts_validated', task.accounts_validated),
            'elapsed_time': elapsed_time,
            'face_matches': sum(1 for a in accounts if a.get('face_match_score', 0) > 0 or a.get('face_match', False))
        }
    )


@phase1_bp.route('/uploads/<filename>')
def get_upload(filename):
    """Serve uploaded files."""
    upload_folder = get_upload_folder()
    return send_from_directory(upload_folder, filename)


# ============================================
# API ENDPOINTS
# ============================================

@phase1_bp.route('/api/task/<task_id>')
def api_task_status(task_id):
    """Full task status API."""
    task = tasks.get(task_id)
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    response = task.to_dict()
    
    if task.phase == 'complete' and task.results:
        response['results'] = {
            'accounts': task.results.get('accounts', task.results.get('results', [])),
            'stats': task.results.get('stats', {})
        }
    
    return jsonify(response)


@phase1_bp.route('/api/task/<task_id>/accounts')
def api_task_accounts(task_id):
    """Get all accounts for a task."""
    task = tasks.get(task_id)
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    return jsonify({
        'task_id': task_id,
        'accounts': task.all_accounts,
        'total': len(task.all_accounts)
    })
