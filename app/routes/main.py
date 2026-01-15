"""
IBP Main Routes
===============
Redirects root URL to Phase 1 investigation page
"""

from flask import Blueprint, redirect, url_for, jsonify
import subprocess
import re

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Redirect root to Phase 1 start page."""
    return redirect(url_for('phase1.index'))


@main_bp.route('/dashboard')
def dashboard():
    """Dashboard - coming soon."""
    return redirect(url_for('phase1.index'))


@main_bp.route('/diagnostic')
def diagnostic():
    """
    Diagnostic endpoint to debug search issues.
    Shows what's installed and working.
    """
    results = {
        'status': 'running',
        'maigret': {'installed': False, 'version': None, 'test_results': []},
        'sherlock': {'installed': False, 'version': None},
        'username_generator': {'working': False, 'sample': []},
        'parsing_test': {'input_lines': [], 'parsed_results': []},
    }

    # Test Maigret installation
    try:
        proc = subprocess.run(
            ['maigret', '--version'],
            capture_output=True, text=True, timeout=10,
            encoding='utf-8', errors='replace'
        )
        results['maigret']['installed'] = True
        results['maigret']['version'] = proc.stdout.strip() or proc.stderr.strip()
    except FileNotFoundError:
        results['maigret']['error'] = 'Not installed'
    except Exception as e:
        results['maigret']['error'] = str(e)

    # Test Sherlock installation
    try:
        proc = subprocess.run(
            ['sherlock', '--version'],
            capture_output=True, text=True, timeout=10,
            encoding='utf-8', errors='replace'
        )
        results['sherlock']['installed'] = True
        results['sherlock']['version'] = proc.stdout.strip() or proc.stderr.strip()
    except FileNotFoundError:
        results['sherlock']['error'] = 'Not installed'
    except Exception as e:
        results['sherlock']['error'] = str(e)

    # Test username generator
    try:
        from app.services.username_generator_v2 import EnhancedUsernameGenerator
        gen = EnhancedUsernameGenerator(max_results=5)
        sample = gen.generate_usernames("Test User", max_results=5)
        results['username_generator']['working'] = True
        results['username_generator']['sample'] = sample
    except Exception as e:
        results['username_generator']['error'] = str(e)

    # Run quick Maigret test
    if results['maigret']['installed']:
        try:
            proc = subprocess.run(
                ['maigret', 'john', '--timeout', '20'],
                capture_output=True, text=True, timeout=60,
                encoding='utf-8', errors='replace'
            )

            # Show raw output sample
            results['maigret']['stdout_length'] = len(proc.stdout)
            results['maigret']['stderr_length'] = len(proc.stderr)
            results['maigret']['stdout_sample'] = proc.stdout[:1500]

            # Parse output
            for line in proc.stdout.split('\n'):
                match = re.search(r'\[\+\]\s*([^:]+?):\s*(https?://[^\s]+)', line)
                if match:
                    results['maigret']['test_results'].append({
                        'platform': match.group(1).strip(),
                        'url': match.group(2).strip()
                    })

            results['maigret']['parsed_count'] = len(results['maigret']['test_results'])

        except subprocess.TimeoutExpired:
            results['maigret']['test_error'] = 'Timeout after 60s'
        except Exception as e:
            results['maigret']['test_error'] = str(e)

    # Test parsing logic
    test_lines = [
        'on 3: [+] WordPress: https://john.wordpress.com/',
        '[+] GitHub: https://github.com/john',
        'on 14: [+] YouTube: https://www.youtube.com/@john',
        '[+] VK: https://vk.com/john',
        '[-] Instagram: Not Found',
        '[*] Checking username john on:',
    ]
    results['parsing_test']['input_lines'] = test_lines

    for line in test_lines:
        match = re.search(r'\[\+\]\s*([^:]+?):\s*(https?://[^\s]+)', line)
        if match:
            results['parsing_test']['parsed_results'].append({
                'platform': match.group(1).strip(),
                'url': match.group(2).strip()
            })

    results['status'] = 'complete'
    return jsonify(results)


@main_bp.route('/diagnostic/search/<name>')
def diagnostic_search(name):
    """
    Run a full search and return detailed diagnostics.
    """
    from app.services.combined_search import CombinedSearchService

    service = CombinedSearchService(max_usernames=10, timeout=20)
    results = service.search(name)

    return jsonify({
        'search_results': results,
        'debug_log': results.get('debug_log', []),
        'stats': results.get('stats', {}),
        'accounts_count': len(results.get('accounts', [])),
        'accounts_sample': results.get('accounts', [])[:20]
    })
