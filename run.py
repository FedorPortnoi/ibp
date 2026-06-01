"""
IBP - Identity-Based Profiler
=============================
Run the Flask development server.
"""

import os
from dotenv import load_dotenv

# Load .env BEFORE reading FLASK_ENV so the env file value takes effect.
# Without this, os.environ.get('FLASK_ENV') sees the system environment only,
# which is typically unset in development and always returns 'development'.
load_dotenv()

from app import create_app

# Get environment (default to development)
config_name = os.environ.get('FLASK_ENV', 'development')

# Create the app
app = create_app(config_name)

if __name__ == '__main__':
    # Print startup banner
    print("""
    ===========================================================
    IBP - Identity-Based Profiler
    OSINT Investigation Platform

    Server running at: http://127.0.0.1:5000
    Press CTRL+C to stop
    ===========================================================
    """)

    # Run startup validation checks
    try:
        from app.utils.startup_checks import run_startup_checks
        run_startup_checks()
    except Exception as e:
        print(f"  Startup checks failed: {e}")

    # Run the development server
    # debug=True enables the Werkzeug interactive console (/console) which gives
    # full Python RCE to anyone who can reach the process. Never enable in production.
    debug_mode = os.environ.get('IBP_DEBUG', '').lower() in ('1', 'true', 'yes')
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=debug_mode
    )
