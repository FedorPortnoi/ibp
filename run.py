"""
IBP - Identity-Based Profiler
=============================
Run the Flask development server.
"""

import os
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
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=True
    )
