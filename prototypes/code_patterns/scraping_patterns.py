"""
Web Scraping Patterns
=====================

Patterns for robust web scraping in OSINT applications.
"""

import re
import time
import random
import logging
from typing import Dict, Any, Optional, List, Generator
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field

# Optional imports
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


# User Agent Rotation Pattern
# ===========================

USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Firefox Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
]


class UserAgentRotator:
    """
    Rotate user agents to avoid detection.

    Usage:
        rotator = UserAgentRotator()
        headers = {'User-Agent': rotator.get()}
    """

    def __init__(self, agents: Optional[List[str]] = None):
        self.agents = agents or USER_AGENTS
        self.index = 0

    def get(self) -> str:
        """Get next user agent"""
        agent = self.agents[self.index]
        self.index = (self.index + 1) % len(self.agents)
        return agent

    def random(self) -> str:
        """Get random user agent"""
        return random.choice(self.agents)


# Session Factory Pattern
# =======================

def create_scraping_session(
    retries: int = 3,
    backoff_factor: float = 0.5,
    timeout: float = 30.0
) -> 'requests.Session':
    """
    Create a requests session with retry logic and sensible defaults.

    Usage:
        session = create_scraping_session()
        response = session.get('https://example.com')
    """
    if not HAS_REQUESTS:
        raise ImportError("requests library required")

    session = requests.Session()

    # Configure retries
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # Set default headers
    session.headers.update({
        "User-Agent": UserAgentRotator().get(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    })

    return session


# Polite Scraper Pattern
# ======================

@dataclass
class ScraperConfig:
    """Configuration for polite scraping"""
    min_delay: float = 1.0
    max_delay: float = 3.0
    respect_robots: bool = True
    max_requests_per_domain: int = 100
    timeout: float = 30.0


class PoliteScraper:
    """
    Scraper that respects rate limits and robots.txt.

    Usage:
        scraper = PoliteScraper(config=ScraperConfig(min_delay=2.0))
        html = scraper.fetch('https://example.com/page')
    """

    def __init__(self, config: Optional[ScraperConfig] = None):
        self.config = config or ScraperConfig()
        self.session = create_scraping_session() if HAS_REQUESTS else None
        self._request_counts: Dict[str, int] = {}
        self._last_request_time: Dict[str, float] = {}
        self._ua_rotator = UserAgentRotator()

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL"""
        return urlparse(url).netloc

    def _wait_if_needed(self, domain: str):
        """Wait to respect rate limits"""
        if domain in self._last_request_time:
            elapsed = time.time() - self._last_request_time[domain]
            delay = random.uniform(self.config.min_delay, self.config.max_delay)

            if elapsed < delay:
                time.sleep(delay - elapsed)

        self._last_request_time[domain] = time.time()

    def _check_limit(self, domain: str) -> bool:
        """Check if request limit reached for domain"""
        count = self._request_counts.get(domain, 0)
        return count < self.config.max_requests_per_domain

    def fetch(self, url: str, **kwargs) -> Optional[str]:
        """
        Fetch URL content with polite behavior.

        Returns HTML string or None on error.
        """
        if not HAS_REQUESTS:
            logging.error("requests library required")
            return None

        domain = self._get_domain(url)

        if not self._check_limit(domain):
            logging.warning(f"Request limit reached for {domain}")
            return None

        self._wait_if_needed(domain)

        # Rotate user agent
        self.session.headers["User-Agent"] = self._ua_rotator.get()

        try:
            response = self.session.get(url, timeout=self.config.timeout, **kwargs)
            response.raise_for_status()

            self._request_counts[domain] = self._request_counts.get(domain, 0) + 1

            return response.text

        except requests.RequestException as e:
            logging.error(f"Fetch error for {url}: {e}")
            return None


# HTML Parsing Patterns
# =====================

class HTMLParser:
    """
    Common HTML parsing utilities.

    Usage:
        parser = HTMLParser(html)
        title = parser.get_text('h1')
        links = parser.get_all_links()
    """

    def __init__(self, html: str, base_url: Optional[str] = None):
        if not HAS_BS4:
            raise ImportError("beautifulsoup4 required")

        self.soup = BeautifulSoup(html, 'lxml' if 'lxml' in __import__('sys').modules else 'html.parser')
        self.base_url = base_url

    def get_text(self, selector: str, default: str = "") -> str:
        """Get text content from selector"""
        elem = self.soup.select_one(selector)
        return elem.get_text(strip=True) if elem else default

    def get_all_text(self, selector: str) -> List[str]:
        """Get all text content matching selector"""
        return [elem.get_text(strip=True) for elem in self.soup.select(selector)]

    def get_attr(self, selector: str, attr: str, default: str = "") -> str:
        """Get attribute value from selector"""
        elem = self.soup.select_one(selector)
        return elem.get(attr, default) if elem else default

    def get_all_links(self) -> List[str]:
        """Extract all links from page"""
        links = []
        for a in self.soup.find_all('a', href=True):
            href = a['href']
            if self.base_url:
                href = urljoin(self.base_url, href)
            links.append(href)
        return links

    def extract_emails(self) -> List[str]:
        """Extract email addresses from page"""
        text = self.soup.get_text()
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        return list(set(re.findall(pattern, text)))

    def extract_phones(self) -> List[str]:
        """Extract phone numbers from page"""
        text = self.soup.get_text()
        patterns = [
            r'(?:\+7|8)[\s\-\.]?\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{2}[\s\-\.]?\d{2}',
            r'\+\d{1,3}[\s\-\.]?\d{3}[\s\-\.]?\d{3}[\s\-\.]?\d{4}'
        ]
        phones = []
        for pattern in patterns:
            phones.extend(re.findall(pattern, text))
        return list(set(phones))

    def get_meta(self, name: str) -> Optional[str]:
        """Get meta tag content"""
        meta = self.soup.find('meta', {'name': name}) or self.soup.find('meta', {'property': name})
        return meta.get('content') if meta else None

    def get_structured_data(self) -> List[Dict]:
        """Extract JSON-LD structured data"""
        scripts = self.soup.find_all('script', {'type': 'application/ld+json'})
        data = []
        for script in scripts:
            try:
                import json
                data.append(json.loads(script.string))
            except (json.JSONDecodeError, TypeError):
                pass
        return data


# Data Extraction Patterns
# ========================

def extract_numbers(text: str) -> List[int]:
    """Extract all numbers from text"""
    return [int(n) for n in re.findall(r'\d+', text.replace(' ', ''))]


def clean_text(text: str) -> str:
    """Clean and normalize text"""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove control characters
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    return text.strip()


def extract_date_patterns(text: str) -> List[str]:
    """Extract common date patterns from text"""
    patterns = [
        r'\d{1,2}[./]\d{1,2}[./]\d{2,4}',  # DD.MM.YYYY or similar
        r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',     # YYYY-MM-DD
        r'\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4}',  # Russian dates
    ]

    dates = []
    for pattern in patterns:
        dates.extend(re.findall(pattern, text, re.IGNORECASE))

    return dates


# Proxy Rotation Pattern
# ======================

@dataclass
class Proxy:
    """Proxy server configuration"""
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "http"

    @property
    def url(self) -> str:
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"


class ProxyRotator:
    """
    Rotate through proxy servers.

    Usage:
        rotator = ProxyRotator([
            Proxy('proxy1.example.com', 8080),
            Proxy('proxy2.example.com', 8080)
        ])
        proxies = rotator.get_dict()
        response = requests.get(url, proxies=proxies)
    """

    def __init__(self, proxies: List[Proxy]):
        self.proxies = proxies
        self.index = 0
        self._failed: Dict[str, int] = {}

    def get(self) -> Proxy:
        """Get next proxy"""
        if not self.proxies:
            raise ValueError("No proxies configured")

        proxy = self.proxies[self.index]
        self.index = (self.index + 1) % len(self.proxies)
        return proxy

    def get_dict(self) -> Dict[str, str]:
        """Get proxy as requests-compatible dict"""
        proxy = self.get()
        return {
            "http": proxy.url,
            "https": proxy.url
        }

    def mark_failed(self, proxy: Proxy):
        """Mark proxy as failed"""
        self._failed[proxy.url] = self._failed.get(proxy.url, 0) + 1

        # Remove proxy if failed too many times
        if self._failed[proxy.url] >= 3:
            self.proxies = [p for p in self.proxies if p.url != proxy.url]
            logging.warning(f"Removed failed proxy: {proxy.host}")
