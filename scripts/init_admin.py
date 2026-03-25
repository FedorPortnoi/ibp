"""
Initialize admin user and clean old check data.
Run once after deploying the multiuser system.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app, db
from app.models.user import User
from app.models.candidate_check import CandidateCheck

# ── ADMIN CREDENTIALS ──────────────────────────
ADMIN_USERNAME = "Fedor"
ADMIN_PASSWORD = "fedorportnoiisthebestplayerinhofstralionsbasketballhistory9"
# ───────────────────────────────────────────────

app = create_app()

with app.app_context():
    # Delete old checks
    old_count = CandidateCheck.query.count()
    if old_count > 0:
        CandidateCheck.query.delete()
        db.session.commit()
        print(f"Deleted {old_count} old checks")
    else:
        print("No old checks to delete")

    # Create/recreate admin
    existing = User.query.filter_by(username=ADMIN_USERNAME).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        print(f"Removed existing admin '{ADMIN_USERNAME}'")

    admin = User(username=ADMIN_USERNAME, role='admin')
    admin.set_password(ADMIN_PASSWORD)
    db.session.add(admin)
    db.session.commit()
    print(f"Admin created: {ADMIN_USERNAME} (role=admin, id={admin.id})")
