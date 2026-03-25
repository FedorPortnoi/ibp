"""Validate subscription system implementation."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pathlib import Path
from app import create_app, db
from app.models.subscription import Subscription
from app.models.user import User

app = create_app('testing')
checks = []

with app.app_context():
    # 1. Subscriptions table
    try:
        Subscription.query.count()
        checks.append(("Subscriptions table", True, ""))
    except Exception as e:
        checks.append(("Subscriptions table", False, str(e)))

    # 2. Email field on User
    checks.append((
        "Email field on User",
        hasattr(User, 'email'),
        ""
    ))

    # 3. Admin Fedor exists (prod only)
    admin = User.query.filter_by(username='Fedor').first()
    if admin:
        checks.append(("Admin Fedor exists", True, ""))
        checks.append(("Admin is_admin=True", admin.is_admin, ""))
    else:
        checks.append(("Admin Fedor (test DB, skipped)", True, "not in test DB"))

    # 4. Files exist
    root = Path(__file__).parent.parent
    for f in [
        "app/routes/subscribe.py",
        "app/services/email_service.py",
        "app/templates/subscribe.html",
        "app/templates/subscribe_success.html",
        "app/templates/subscribe_status.html",
        "app/models/subscription.py",
    ]:
        checks.append((f, (root / f).exists(), ""))

    # 5. subscribe_bp registered
    init_text = (root / "app/__init__.py").read_text(encoding="utf-8")
    checks.append((
        "subscribe_bp registered",
        "subscribe_bp" in init_text,
        ""
    ))

    # 6. Middleware checks subscription
    checks.append((
        "Middleware checks subscription",
        "is_active" in init_text or "subscribe.subscribe_page" in init_text,
        ""
    ))

    # 7. Subscription model works
    try:
        u = User(username='_val_test_user', role='user')
        u.set_password('test123')
        db.session.add(u)
        db.session.commit()

        sub = Subscription(user_id=u.id)
        sub.activate(payment_id='val_test')
        db.session.add(sub)
        db.session.commit()

        ok = sub.is_active and sub.days_left >= 29
        checks.append(("Subscription activate/is_active", ok, f"days_left={sub.days_left}"))

        db.session.delete(sub)
        db.session.delete(u)
        db.session.commit()
    except Exception as e:
        checks.append(("Subscription activate/is_active", False, str(e)))

    # 8. Routes registered
    rules = [r.rule for r in app.url_map.iter_rules()]
    sub_rules = [r for r in rules if 'subscribe' in r]
    checks.append((
        "Subscribe routes (4)",
        len(sub_rules) == 4,
        f"found {len(sub_rules)}: {sub_rules}"
    ))

print("=" * 55)
for name, ok, note in checks:
    status = "PASS" if ok else "FAIL"
    suffix = f" ({note})" if note else ""
    print(f"  [{status}] {name}{suffix}")

all_ok = all(ok for _, ok, _ in checks)
print("=" * 55)
print(f"  {'ALL CHECKS PASSED' if all_ok else 'SOME CHECKS FAILED'}")
print("=" * 55)

sys.exit(0 if all_ok else 1)
