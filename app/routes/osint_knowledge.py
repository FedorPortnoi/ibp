"""
OSINT (Open Source Intelligence) Comprehensive Knowledge Base
==============================================================
A complete reference class containing virtually all known information about OSINT,
including history, methodologies, tools, techniques, legal frameworks, and resources.

Author: Claude (Anthropic)
Purpose: Educational reference for OSINT practitioners, researchers, and students
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum, auto
from datetime import datetime
import json


# =============================================================================
# ENUMERATIONS
# =============================================================================

class OSINTCategory(Enum):
    """Primary categories of Open Source Intelligence."""
    SOCMINT = "Social Media Intelligence"
    GEOINT = "Geospatial Intelligence"
    TECHINT = "Technical Intelligence"
    FININT = "Financial Intelligence"
    HUMINT_OPEN = "Open Source Human Intelligence"
    CYBINT = "Cyber Intelligence"
    IMINT = "Imagery Intelligence"
    SIGINT_OPEN = "Open Source Signals Intelligence"
    MEDINT = "Media Intelligence"
    ACADINT = "Academic Intelligence"
    TRADINT = "Trade/Commercial Intelligence"
    LEGINT = "Legal Intelligence"
    DARKINT = "Dark Web Intelligence"
    WEBINT = "Web Intelligence"


class ThreatLevel(Enum):
    """Threat assessment levels used in OSINT analysis."""
    CRITICAL = 5
    HIGH = 4
    MEDIUM = 3
    LOW = 2
    INFORMATIONAL = 1


class SourceReliability(Enum):
    """NATO Admiralty Code for source reliability."""
    A = "Completely Reliable"
    B = "Usually Reliable"
    C = "Fairly Reliable"
    D = "Not Usually Reliable"
    E = "Unreliable"
    F = "Reliability Cannot Be Judged"


class InformationCredibility(Enum):
    """NATO Admiralty Code for information credibility."""
    ONE = "Confirmed by Other Sources"
    TWO = "Probably True"
    THREE = "Possibly True"
    FOUR = "Doubtful"
    FIVE = "Improbable"
    SIX = "Truth Cannot Be Judged"


class IntelligenceCycle(Enum):
    """Stages of the intelligence cycle."""
    PLANNING_DIRECTION = "Planning and Direction"
    COLLECTION = "Collection"
    PROCESSING = "Processing"
    ANALYSIS_PRODUCTION = "Analysis and Production"
    DISSEMINATION = "Dissemination"
    FEEDBACK = "Feedback"


class AnalysisTechnique(Enum):
    """Structured analytic techniques used in OSINT."""
    ACH = "Analysis of Competing Hypotheses"
    LINK_ANALYSIS = "Link Analysis"
    TIMELINE_ANALYSIS = "Timeline/Chronological Analysis"
    PATTERN_ANALYSIS = "Pattern Analysis"
    GEOSPATIAL_ANALYSIS = "Geospatial Analysis"
    SOCIAL_NETWORK_ANALYSIS = "Social Network Analysis"
    SENTIMENT_ANALYSIS = "Sentiment Analysis"
    CONTENT_ANALYSIS = "Content Analysis"
    NETWORK_ANALYSIS = "Network Analysis"
    RED_TEAMING = "Red Team Analysis"
    DEVIL_ADVOCACY = "Devil's Advocacy"
    TEAM_A_B = "Team A/Team B Analysis"
    HIGH_IMPACT_LOW_PROBABILITY = "High Impact/Low Probability Analysis"
    INDICATOR_ANALYSIS = "Indicators and Warnings Analysis"
    SWOT = "SWOT Analysis"
    PESTLE = "PESTLE Analysis"
    SCENARIO_PLANNING = "Scenario Planning"
    BRAINSTORMING = "Structured Brainstorming"
    NOMINAL_GROUP = "Nominal Group Technique"
    STARBURSTING = "Starbursting"
    KEY_ASSUMPTIONS_CHECK = "Key Assumptions Check"
    QUALITY_OF_INFO_CHECK = "Quality of Information Check"
    DECEPTION_DETECTION = "Deception Detection"
    ARGUMENT_MAPPING = "Argument Mapping"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class OSINTTool:
    """Represents an OSINT tool or platform."""
    name: str
    category: str
    description: str
    url: Optional[str] = None
    is_free: bool = True
    requires_api: bool = False
    platforms: List[str] = field(default_factory=list)
    use_cases: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    alternatives: List[str] = field(default_factory=list)


@dataclass
class OSINTSource:
    """Represents an OSINT data source."""
    name: str
    source_type: str
    description: str
    url: Optional[str] = None
    access_type: str = "public"
    geographic_coverage: str = "global"
    data_types: List[str] = field(default_factory=list)
    update_frequency: str = "varies"
    reliability_rating: SourceReliability = SourceReliability.C


@dataclass
class LegalFramework:
    """Legal framework governing OSINT activities."""
    jurisdiction: str
    law_name: str
    description: str
    key_provisions: List[str] = field(default_factory=list)
    implications_for_osint: List[str] = field(default_factory=list)
    year_enacted: Optional[int] = None


@dataclass
class OSINTMethodology:
    """Represents an OSINT methodology or framework."""
    name: str
    description: str
    phases: List[str] = field(default_factory=list)
    best_practices: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)


@dataclass 
class SearchOperator:
    """Search engine operator/dork."""
    operator: str
    description: str
    example: str
    supported_engines: List[str] = field(default_factory=list)


# =============================================================================
# MAIN OSINT KNOWLEDGE CLASS
# =============================================================================

class OSINTKnowledgeBase:
    """
    Comprehensive OSINT (Open Source Intelligence) Knowledge Base.
    
    This class contains extensive information about OSINT including:
    - History and evolution
    - Definitions and terminology
    - Categories and subcategories
    - Tools and platforms
    - Methodologies and frameworks
    - Legal and ethical considerations
    - Techniques and tradecraft
    - Resources and databases
    - Best practices
    - Case studies and applications
    """
    
    def __init__(self):
        """Initialize the OSINT Knowledge Base with all data."""
        self._initialize_definitions()
        self._initialize_history()
        self._initialize_tools()
        self._initialize_sources()
        self._initialize_methodologies()
        self._initialize_legal_frameworks()
        self._initialize_search_operators()
        self._initialize_techniques()
        self._initialize_resources()
        self._initialize_best_practices()
        self._initialize_terminology()
        self._initialize_sock_puppet_guidance()
        self._initialize_opsec()
        self._initialize_verification_methods()
        self._initialize_reporting_standards()
    
    # =========================================================================
    # DEFINITIONS AND CORE CONCEPTS
    # =========================================================================
    
    def _initialize_definitions(self):
        """Initialize core OSINT definitions."""
        self.definitions = {
            "OSINT": {
                "full_name": "Open Source Intelligence",
                "definition": "Intelligence collected from publicly available sources, including "
                              "media, internet, public government data, professional and academic "
                              "publications, commercial data, and grey literature.",
                "nato_definition": "Intelligence derived from publicly available information that "
                                   "is collected, exploited and disseminated in a timely manner "
                                   "to an appropriate audience for the purpose of addressing a "
                                   "specific intelligence requirement.",
                "us_dni_definition": "Intelligence produced from publicly available information "
                                     "that is collected, exploited, and disseminated in a timely "
                                     "manner to an appropriate audience for the purpose of "
                                     "addressing a specific intelligence requirement.",
                "key_characteristics": [
                    "Derived from publicly available sources",
                    "Legally obtainable",
                    "Does not require clandestine collection",
                    "Can be collected by anyone with access",
                    "Often requires analysis to derive intelligence value",
                    "Volume of data is typically very high",
                    "Cost-effective compared to classified collection"
                ]
            },
            "SOCMINT": {
                "full_name": "Social Media Intelligence",
                "definition": "Intelligence gathered from social media platforms and online "
                              "communities to support investigation and analysis.",
                "platforms": ["Facebook", "Twitter/X", "LinkedIn", "Instagram", "TikTok", 
                             "Reddit", "Discord", "Telegram", "WhatsApp (public groups)",
                             "YouTube", "VKontakte", "Weibo", "WeChat (public)"]
            },
            "GEOINT": {
                "full_name": "Geospatial Intelligence",
                "definition": "Intelligence derived from the exploitation and analysis of "
                              "imagery and geospatial information to describe, assess, and "
                              "visually depict physical features and geographically referenced "
                              "activities on Earth."
            },
            "IMINT": {
                "full_name": "Imagery Intelligence",
                "definition": "Intelligence derived from the exploitation of imagery collected "
                              "by visual photography, infrared sensors, lasers, multi-spectral "
                              "sensors, and radar."
            },
            "WEBINT": {
                "full_name": "Web Intelligence",
                "definition": "Intelligence gathered from websites, web applications, and other "
                              "web-based resources including the surface web and deep web."
            },
            "FININT": {
                "full_name": "Financial Intelligence",
                "definition": "Intelligence derived from financial data and transactions to "
                              "identify illicit financial activities, money laundering, and "
                              "terrorist financing."
            },
            "CYBINT": {
                "full_name": "Cyber Intelligence",
                "definition": "Intelligence derived from cyberspace, including information about "
                              "cyber threats, vulnerabilities, and malicious actors."
            },
            "TECHINT": {
                "full_name": "Technical Intelligence",
                "definition": "Intelligence concerning foreign technological developments and "
                              "the performance characteristics of foreign equipment."
            },
            "PAI": {
                "full_name": "Publicly Available Information",
                "definition": "Information that has been published or broadcast for public "
                              "consumption, available on request, accessible through subscription "
                              "or purchase, or obtainable by visiting a location open to the public."
            },
            "Grey_Literature": {
                "full_name": "Grey Literature",
                "definition": "Information produced outside traditional commercial or academic "
                              "publishing channels, including government reports, white papers, "
                              "working papers, newsletters, technical reports, and dissertations."
            }
        }
        
        self.intelligence_disciplines = {
            "HUMINT": "Human Intelligence - from human sources",
            "SIGINT": "Signals Intelligence - from intercepted signals",
            "IMINT": "Imagery Intelligence - from imagery",
            "MASINT": "Measurement and Signature Intelligence - from technical measurements",
            "GEOINT": "Geospatial Intelligence - from geospatial data",
            "OSINT": "Open Source Intelligence - from open sources",
            "TECHINT": "Technical Intelligence - from technical analysis",
            "CYBINT": "Cyber Intelligence - from cyber domain",
            "FININT": "Financial Intelligence - from financial data"
        }
    
    # =========================================================================
    # HISTORY AND EVOLUTION
    # =========================================================================
    
    def _initialize_history(self):
        """Initialize OSINT history and evolution."""
        self.history = {
            "origins": {
                "description": "OSINT has roots dating back centuries, but became formalized "
                               "during World War II with the creation of the Foreign Broadcast "
                               "Information Service (FBIS) in 1941.",
                "key_milestone": "1941 - FBIS established to monitor Axis propaganda"
            },
            "timeline": [
                {
                    "period": "Pre-1900s",
                    "description": "Intelligence from newspapers, books, and public records",
                    "key_events": [
                        "Military scouts gathered info from local populations",
                        "Diplomatic dispatches analyzed public sentiment",
                        "Maritime intelligence from ship manifests"
                    ]
                },
                {
                    "period": "1941-1945",
                    "description": "WWII - Formal establishment of open source intelligence",
                    "key_events": [
                        "1941: Foreign Broadcast Information Service (FBIS) created",
                        "1942: Office of Strategic Services (OSS) Research & Analysis Branch",
                        "BBC Monitoring Service established",
                        "Analysis of Axis radio broadcasts and newspapers"
                    ]
                },
                {
                    "period": "1945-1991",
                    "description": "Cold War Era - Emphasis on Soviet bloc monitoring",
                    "key_events": [
                        "1947: CIA established, inherits FBIS",
                        "1952: NSA created",
                        "Extensive monitoring of Soviet media",
                        "Analysis of technical journals and scientific publications",
                        "Development of systematic collection methodologies"
                    ]
                },
                {
                    "period": "1991-2001",
                    "description": "Post-Cold War - Internet emergence",
                    "key_events": [
                        "1992: Intelligence Reform - Open Source Collection recognized",
                        "1994: Community Open Source Program Office (COSPO)",
                        "1996: Aspin-Brown Commission recommends OSINT expansion",
                        "Rise of the World Wide Web",
                        "Email and early social platforms emerge"
                    ]
                },
                {
                    "period": "2001-2010",
                    "description": "Post-9/11 - OSINT gains prominence",
                    "key_events": [
                        "2001: 9/11 attacks highlight intelligence failures",
                        "2004: 9/11 Commission recommends OSINT enhancement",
                        "2005: Open Source Center (OSC) established under DNI",
                        "2005: ODNI position of Assistant Deputy DNI for Open Source created",
                        "Rise of social media platforms (Facebook 2004, Twitter 2006)",
                        "Web 2.0 and user-generated content explosion"
                    ]
                },
                {
                    "period": "2010-2020",
                    "description": "Social Media and Big Data Era",
                    "key_events": [
                        "2010: Arab Spring demonstrates social media intelligence value",
                        "2013: Bellingcat founded - citizen journalism OSINT",
                        "2014: MH17 investigation showcases OSINT capabilities",
                        "Growth of commercial OSINT tools and platforms",
                        "Deep/Dark web intelligence emerges",
                        "Machine learning applied to OSINT analysis"
                    ]
                },
                {
                    "period": "2020-Present",
                    "description": "Modern Era - AI and Advanced Analytics",
                    "key_events": [
                        "2022: Ukraine conflict demonstrates real-time OSINT",
                        "AI/ML tools for automated analysis",
                        "Satellite imagery democratization",
                        "Facial recognition and biometric OSINT",
                        "Synthetic media and deepfake challenges",
                        "OSINT professionalization and certification",
                        "Commercial satellite proliferation"
                    ]
                }
            ],
            "key_figures": [
                {
                    "name": "Robert David Steele",
                    "contribution": "Pioneer of OSINT advocacy, founded Open Source Solutions Inc.",
                    "notable_work": "First international conference on OSINT (1992)"
                },
                {
                    "name": "Eliot Higgins",
                    "contribution": "Founder of Bellingcat, pioneered citizen journalism OSINT",
                    "notable_work": "MH17 investigation, Syria weapons analysis"
                },
                {
                    "name": "Michael Bazzell",
                    "contribution": "OSINT trainer, author of 'Open Source Intelligence Techniques'",
                    "notable_work": "Comprehensive OSINT methodology development"
                },
                {
                    "name": "Rae Baker",
                    "contribution": "OSINT educator and author",
                    "notable_work": "Deep Dive: Exploring the Real-World Value of OSINT"
                }
            ],
            "notable_investigations": [
                {
                    "name": "MH17 Investigation",
                    "year": 2014,
                    "description": "Bellingcat's analysis of the downing of Malaysia Airlines Flight 17",
                    "methods_used": ["Social media analysis", "Geolocation", "Photo/video verification",
                                    "Open satellite imagery", "Vehicle tracking"]
                },
                {
                    "name": "Boston Marathon Bombing",
                    "year": 2013,
                    "description": "Crowdsourced identification efforts (with lessons on risks)",
                    "methods_used": ["Social media mining", "Photo analysis", "Crowdsourcing"]
                },
                {
                    "name": "Skripal Poisoning Investigation",
                    "year": 2018,
                    "description": "Identification of GRU operatives through open sources",
                    "methods_used": ["Passport database leaks", "Travel records", "Phone records",
                                    "Social media", "Real estate records"]
                },
                {
                    "name": "Capitol Riot Investigations",
                    "year": 2021,
                    "description": "Identification of participants through social media and video",
                    "methods_used": ["Social media archiving", "Facial recognition", "Geolocation",
                                    "Video analysis", "Crowdsourced identification"]
                },
                {
                    "name": "Xinjiang Camps Documentation",
                    "year": "2018-present",
                    "description": "Mapping of detention facilities using satellite imagery",
                    "methods_used": ["Satellite imagery analysis", "Construction monitoring",
                                    "Government document analysis", "Survivor testimony correlation"]
                },
                {
                    "name": "Ukraine Conflict Monitoring",
                    "year": "2022-present",
                    "description": "Real-time battlefield intelligence from open sources",
                    "methods_used": ["Satellite imagery", "Social media monitoring", "TikTok/Telegram",
                                    "Equipment identification", "Geolocation", "Signal interception (open)"]
                }
            ]
        }
    
    # =========================================================================
    # TOOLS AND PLATFORMS
    # =========================================================================
    
    def _initialize_tools(self):
        """Initialize comprehensive OSINT tools database."""
        self.tools = {
            "search_engines": [
                OSINTTool(
                    name="Google",
                    category="Search Engine",
                    description="Primary search engine with advanced operators",
                    url="https://google.com",
                    use_cases=["General search", "Dorking", "Cache access", "Image search"],
                    limitations=["Personalized results", "Limited deep web access"]
                ),
                OSINTTool(
                    name="Bing",
                    category="Search Engine",
                    description="Microsoft search engine with unique index",
                    url="https://bing.com",
                    use_cases=["Alternative index", "Image search", "Social media search"]
                ),
                OSINTTool(
                    name="DuckDuckGo",
                    category="Search Engine",
                    description="Privacy-focused search engine",
                    url="https://duckduckgo.com",
                    use_cases=["Anonymous searching", "Bang shortcuts"]
                ),
                OSINTTool(
                    name="Yandex",
                    category="Search Engine",
                    description="Russian search engine with excellent image search",
                    url="https://yandex.com",
                    use_cases=["Russian content", "Reverse image search", "Maps"]
                ),
                OSINTTool(
                    name="Baidu",
                    category="Search Engine",
                    description="Chinese search engine",
                    url="https://baidu.com",
                    use_cases=["Chinese content", "Chinese social media"]
                ),
                OSINTTool(
                    name="Shodan",
                    category="IoT Search Engine",
                    description="Search engine for Internet-connected devices",
                    url="https://shodan.io",
                    requires_api=True,
                    use_cases=["IoT discovery", "Vulnerability research", "Infrastructure mapping"]
                ),
                OSINTTool(
                    name="Censys",
                    category="IoT Search Engine",
                    description="Internet-wide scanning and certificate analysis",
                    url="https://censys.io",
                    requires_api=True,
                    use_cases=["Certificate transparency", "Host discovery", "TLS analysis"]
                ),
                OSINTTool(
                    name="ZoomEye",
                    category="IoT Search Engine",
                    description="Chinese cyberspace search engine",
                    url="https://zoomeye.org",
                    use_cases=["Chinese infrastructure", "IoT devices"]
                ),
                OSINTTool(
                    name="Fofa",
                    category="IoT Search Engine",
                    description="Chinese asset search engine",
                    url="https://fofa.info",
                    use_cases=["Asset discovery", "Chinese networks"]
                ),
                OSINTTool(
                    name="Wigle",
                    category="WiFi Search",
                    description="Wireless network mapping database",
                    url="https://wigle.net",
                    use_cases=["WiFi geolocation", "SSID searching", "Historical wireless data"]
                )
            ],
            
            "social_media_tools": [
                OSINTTool(
                    name="Namechk",
                    category="Username Search",
                    description="Check username availability across platforms",
                    url="https://namechk.com",
                    use_cases=["Username enumeration", "Account discovery"]
                ),
                OSINTTool(
                    name="Sherlock",
                    category="Username Search",
                    description="Hunt usernames across social networks",
                    url="https://github.com/sherlock-project/sherlock",
                    platforms=["Command Line"],
                    use_cases=["Username enumeration", "Social media discovery"]
                ),
                OSINTTool(
                    name="Maigret",
                    category="Username Search",
                    description="Advanced username search across 2500+ sites",
                    url="https://github.com/soxoj/maigret",
                    platforms=["Command Line"],
                    use_cases=["Comprehensive username search", "Profile correlation"]
                ),
                OSINTTool(
                    name="WhatsMyName",
                    category="Username Search",
                    description="Username enumeration project",
                    url="https://whatsmyname.app",
                    use_cases=["Username checking", "API integration"]
                ),
                OSINTTool(
                    name="Social Searcher",
                    category="Social Media Search",
                    description="Search social media content",
                    url="https://social-searcher.com",
                    use_cases=["Social media monitoring", "Keyword tracking"]
                ),
                OSINTTool(
                    name="TweetDeck",
                    category="Twitter/X Tool",
                    description="Twitter monitoring and management",
                    url="https://tweetdeck.twitter.com",
                    use_cases=["Real-time monitoring", "Advanced search"]
                ),
                OSINTTool(
                    name="Twint",
                    category="Twitter/X Tool",
                    description="Twitter scraping tool",
                    url="https://github.com/twintproject/twint",
                    platforms=["Command Line"],
                    use_cases=["Tweet scraping", "User analysis"],
                    limitations=["May violate ToS", "Frequent breaking changes"]
                ),
                OSINTTool(
                    name="Snscrape",
                    category="Social Media Scraper",
                    description="Social network service scraper",
                    url="https://github.com/JustAnotherArchivist/snscrape",
                    platforms=["Python", "Command Line"],
                    use_cases=["Twitter scraping", "Reddit scraping", "Historical data"]
                ),
                OSINTTool(
                    name="Instaloader",
                    category="Instagram Tool",
                    description="Instagram data downloader",
                    url="https://github.com/instaloader/instaloader",
                    platforms=["Python", "Command Line"],
                    use_cases=["Instagram scraping", "Profile download"]
                ),
                OSINTTool(
                    name="Telegram Scraper",
                    category="Telegram Tool",
                    description="Various tools for Telegram channel analysis",
                    use_cases=["Channel monitoring", "Message extraction"]
                ),
                OSINTTool(
                    name="Reddit Search Tools",
                    category="Reddit Tool",
                    description="Reddit-specific search (Pushshift, Redditsearch.io)",
                    use_cases=["Historical Reddit data", "Deleted content recovery"]
                )
            ],
            
            "geolocation_tools": [
                OSINTTool(
                    name="Google Earth Pro",
                    category="Satellite Imagery",
                    description="Free satellite imagery and mapping",
                    url="https://earth.google.com",
                    use_cases=["Historical imagery", "3D terrain", "Measurement"]
                ),
                OSINTTool(
                    name="Google Maps",
                    category="Mapping",
                    description="Mapping and Street View",
                    url="https://maps.google.com",
                    use_cases=["Street View", "Business search", "Navigation"]
                ),
                OSINTTool(
                    name="Bing Maps",
                    category="Mapping",
                    description="Microsoft mapping with Bird's Eye View",
                    url="https://bing.com/maps",
                    use_cases=["Oblique imagery", "Alternative perspective"]
                ),
                OSINTTool(
                    name="Yandex Maps",
                    category="Mapping",
                    description="Russian mapping service",
                    url="https://yandex.com/maps",
                    use_cases=["Russia/CIS coverage", "Alternative Street View"]
                ),
                OSINTTool(
                    name="Baidu Maps",
                    category="Mapping",
                    description="Chinese mapping service",
                    url="https://map.baidu.com",
                    use_cases=["Chinese street-level imagery"]
                ),
                OSINTTool(
                    name="Sentinel Hub",
                    category="Satellite Imagery",
                    description="ESA Sentinel satellite data",
                    url="https://www.sentinel-hub.com",
                    use_cases=["Multispectral imagery", "Environmental monitoring"]
                ),
                OSINTTool(
                    name="Planet Labs",
                    category="Satellite Imagery",
                    description="Commercial daily satellite imagery",
                    url="https://planet.com",
                    is_free=False,
                    use_cases=["Daily imagery", "Change detection"]
                ),
                OSINTTool(
                    name="Maxar",
                    category="Satellite Imagery",
                    description="High-resolution commercial imagery",
                    url="https://maxar.com",
                    is_free=False,
                    use_cases=["Very high resolution imagery"]
                ),
                OSINTTool(
                    name="FIRMS",
                    category="Fire/Thermal",
                    description="NASA Fire Information Resource Management System",
                    url="https://firms.modaps.eosdis.nasa.gov",
                    use_cases=["Fire detection", "Thermal anomalies"]
                ),
                OSINTTool(
                    name="SunCalc",
                    category="Sun/Shadow Analysis",
                    description="Sun position and shadow calculator",
                    url="https://suncalc.org",
                    use_cases=["Shadow analysis for geolocation", "Time estimation"]
                ),
                OSINTTool(
                    name="GeoGuessr",
                    category="Geolocation Training",
                    description="Location guessing game for training",
                    url="https://geoguessr.com",
                    use_cases=["Geolocation skill development"]
                ),
                OSINTTool(
                    name="Overpass Turbo",
                    category="OpenStreetMap",
                    description="OpenStreetMap data query tool",
                    url="https://overpass-turbo.eu",
                    use_cases=["Custom map queries", "Infrastructure identification"]
                ),
                OSINTTool(
                    name="What3Words",
                    category="Location Reference",
                    description="3-word location system",
                    url="https://what3words.com",
                    use_cases=["Precise location sharing"]
                ),
                OSINTTool(
                    name="GeoHints",
                    category="Geolocation Resource",
                    description="Visual clues for geolocation",
                    url="https://geohints.com",
                    use_cases=["Country identification", "Regional indicators"]
                )
            ],
            
            "image_analysis_tools": [
                OSINTTool(
                    name="Google Reverse Image Search",
                    category="Reverse Image",
                    description="Find image sources and similar images",
                    url="https://images.google.com",
                    use_cases=["Image sourcing", "Finding original"]
                ),
                OSINTTool(
                    name="TinEye",
                    category="Reverse Image",
                    description="Reverse image search engine",
                    url="https://tineye.com",
                    use_cases=["Image history", "Modified image detection"]
                ),
                OSINTTool(
                    name="Yandex Images",
                    category="Reverse Image",
                    description="Excellent facial recognition reverse search",
                    url="https://yandex.com/images",
                    use_cases=["Facial matching", "Russian internet sources"]
                ),
                OSINTTool(
                    name="PimEyes",
                    category="Facial Recognition",
                    description="Facial recognition search engine",
                    url="https://pimeyes.com",
                    is_free=False,
                    use_cases=["Face matching", "Identity verification"],
                    limitations=["Ethical concerns", "Accuracy varies"]
                ),
                OSINTTool(
                    name="FotoForensics",
                    category="Image Forensics",
                    description="Image manipulation detection",
                    url="https://fotoforensics.com",
                    use_cases=["ELA analysis", "Metadata extraction"]
                ),
                OSINTTool(
                    name="Jeffrey's EXIF Viewer",
                    category="Metadata",
                    description="Comprehensive EXIF metadata viewer",
                    url="https://exif.regex.info",
                    use_cases=["EXIF extraction", "GPS coordinates"]
                ),
                OSINTTool(
                    name="InVID/WeVerify",
                    category="Video Verification",
                    description="Video verification toolkit",
                    url="https://www.invid-project.eu",
                    platforms=["Browser Extension"],
                    use_cases=["Video analysis", "Keyframe extraction", "Reverse video search"]
                ),
                OSINTTool(
                    name="ExifTool",
                    category="Metadata",
                    description="Comprehensive metadata reader/writer",
                    url="https://exiftool.org",
                    platforms=["Command Line"],
                    use_cases=["Complete metadata extraction"]
                ),
                OSINTTool(
                    name="Forensically",
                    category="Image Forensics",
                    description="Browser-based image forensics",
                    url="https://29a.ch/photo-forensics",
                    use_cases=["Clone detection", "Noise analysis", "Level sweep"]
                )
            ],
            
            "domain_ip_tools": [
                OSINTTool(
                    name="WHOIS",
                    category="Domain Lookup",
                    description="Domain registration information",
                    url="https://whois.domaintools.com",
                    use_cases=["Registrant info", "Domain history"]
                ),
                OSINTTool(
                    name="DomainTools",
                    category="Domain Intelligence",
                    description="Comprehensive domain research platform",
                    url="https://domaintools.com",
                    is_free=False,
                    use_cases=["Historical WHOIS", "Domain scoring", "Infrastructure mapping"]
                ),
                OSINTTool(
                    name="SecurityTrails",
                    category="Domain/IP Intelligence",
                    description="DNS and domain intelligence",
                    url="https://securitytrails.com",
                    use_cases=["DNS history", "Subdomain enumeration", "Associated domains"]
                ),
                OSINTTool(
                    name="VirusTotal",
                    category="Threat Intelligence",
                    description="Multi-AV scanning and threat intel",
                    url="https://virustotal.com",
                    use_cases=["Malware analysis", "URL reputation", "IP reputation"]
                ),
                OSINTTool(
                    name="URLScan.io",
                    category="URL Analysis",
                    description="Website scanning and analysis",
                    url="https://urlscan.io",
                    use_cases=["Website screenshots", "Resource analysis", "DOM inspection"]
                ),
                OSINTTool(
                    name="DNSDumpster",
                    category="DNS Recon",
                    description="DNS reconnaissance tool",
                    url="https://dnsdumpster.com",
                    use_cases=["Subdomain discovery", "DNS mapping"]
                ),
                OSINTTool(
                    name="crt.sh",
                    category="Certificate Transparency",
                    description="Certificate transparency log search",
                    url="https://crt.sh",
                    use_cases=["Subdomain discovery", "Certificate history"]
                ),
                OSINTTool(
                    name="Builtwith",
                    category="Technology Profiling",
                    description="Website technology identification",
                    url="https://builtwith.com",
                    use_cases=["Tech stack identification", "Website relationships"]
                ),
                OSINTTool(
                    name="Wappalyzer",
                    category="Technology Profiling",
                    description="Browser-based technology identification",
                    url="https://wappalyzer.com",
                    platforms=["Browser Extension"],
                    use_cases=["Quick tech identification"]
                ),
                OSINTTool(
                    name="Wayback Machine",
                    category="Web Archive",
                    description="Internet Archive's web archive",
                    url="https://web.archive.org",
                    use_cases=["Historical website versions", "Deleted content recovery"]
                ),
                OSINTTool(
                    name="Archive.today",
                    category="Web Archive",
                    description="Web page archiving service",
                    url="https://archive.today",
                    use_cases=["Page preservation", "Archive searching"]
                ),
                OSINTTool(
                    name="SpyOnWeb",
                    category="Domain Relationships",
                    description="Find related websites",
                    url="https://spyonweb.com",
                    use_cases=["Analytics ID matching", "AdSense relationships"]
                ),
                OSINTTool(
                    name="BGP Toolkit",
                    category="Network Analysis",
                    description="BGP and ASN information",
                    url="https://bgp.he.net",
                    use_cases=["ASN lookup", "IP range identification"]
                ),
                OSINTTool(
                    name="IPinfo",
                    category="IP Intelligence",
                    description="IP address information",
                    url="https://ipinfo.io",
                    use_cases=["Geolocation", "ASN info", "Privacy detection"]
                )
            ],
            
            "email_phone_tools": [
                OSINTTool(
                    name="Hunter.io",
                    category="Email Search",
                    description="Email finder and verifier",
                    url="https://hunter.io",
                    use_cases=["Corporate email discovery", "Email verification"]
                ),
                OSINTTool(
                    name="Have I Been Pwned",
                    category="Breach Search",
                    description="Check if email/phone in data breaches",
                    url="https://haveibeenpwned.com",
                    use_cases=["Breach detection", "Account exposure"]
                ),
                OSINTTool(
                    name="Phonebook.cz",
                    category="Email/Domain Search",
                    description="Email and domain search from IntelX",
                    url="https://phonebook.cz",
                    use_cases=["Email discovery", "Domain intelligence"]
                ),
                OSINTTool(
                    name="Epieos",
                    category="Email Investigation",
                    description="Email OSINT tool",
                    url="https://epieos.com",
                    use_cases=["Google account detection", "Social media linking"]
                ),
                OSINTTool(
                    name="Truecaller",
                    category="Phone Lookup",
                    description="Phone number identification",
                    url="https://truecaller.com",
                    use_cases=["Caller ID", "Spam detection"]
                ),
                OSINTTool(
                    name="CallerID Test",
                    category="Phone Lookup",
                    description="Phone number lookup",
                    use_cases=["Carrier identification", "Number validation"]
                ),
                OSINTTool(
                    name="Dehashed",
                    category="Breach Search",
                    description="Breach database search engine",
                    url="https://dehashed.com",
                    is_free=False,
                    use_cases=["Credential searching", "PII discovery"]
                ),
                OSINTTool(
                    name="Intelligence X",
                    category="Data Archive",
                    description="Historical data and leak archive",
                    url="https://intelx.io",
                    is_free=False,
                    use_cases=["Breach data", "Paste sites", "Dark web"]
                )
            ],
            
            "people_search_tools": [
                OSINTTool(
                    name="Pipl",
                    category="People Search",
                    description="Professional people search engine",
                    url="https://pipl.com",
                    is_free=False,
                    use_cases=["Identity verification", "Contact discovery"]
                ),
                OSINTTool(
                    name="That's Them",
                    category="People Search",
                    description="Free people search",
                    url="https://thatsthem.com",
                    use_cases=["US people search", "Address lookup"]
                ),
                OSINTTool(
                    name="Whitepages",
                    category="People Search",
                    description="US people and business directory",
                    url="https://whitepages.com",
                    use_cases=["US address lookup", "Phone search"]
                ),
                OSINTTool(
                    name="192.com",
                    category="People Search",
                    description="UK people and business search",
                    url="https://192.com",
                    use_cases=["UK people search", "Company search"]
                ),
                OSINTTool(
                    name="FamilySearch",
                    category="Genealogy",
                    description="Free genealogy database",
                    url="https://familysearch.org",
                    use_cases=["Genealogy research", "Historical records"]
                ),
                OSINTTool(
                    name="Ancestry",
                    category="Genealogy",
                    description="Genealogy and DNA testing",
                    url="https://ancestry.com",
                    is_free=False,
                    use_cases=["Family history", "DNA matching"]
                ),
                OSINTTool(
                    name="LinkedIn",
                    category="Professional Network",
                    description="Professional social network",
                    url="https://linkedin.com",
                    use_cases=["Professional profiles", "Corporate research"]
                ),
                OSINTTool(
                    name="Spokeo",
                    category="People Search",
                    description="Aggregated people search",
                    url="https://spokeo.com",
                    is_free=False,
                    use_cases=["Contact info", "Social profiles"]
                )
            ],
            
            "business_corporate_tools": [
                OSINTTool(
                    name="OpenCorporates",
                    category="Corporate Registry",
                    description="Global company database",
                    url="https://opencorporates.com",
                    use_cases=["Company registration", "Director information"]
                ),
                OSINTTool(
                    name="SEC EDGAR",
                    category="Financial Filings",
                    description="US SEC filings database",
                    url="https://sec.gov/edgar",
                    use_cases=["Company filings", "Insider trading", "Beneficial ownership"]
                ),
                OSINTTool(
                    name="Companies House",
                    category="Corporate Registry",
                    description="UK company registry",
                    url="https://find-and-update.company-information.service.gov.uk",
                    use_cases=["UK company search", "Director search", "Filings"]
                ),
                OSINTTool(
                    name="OCCRP Aleph",
                    category="Investigative Database",
                    description="Cross-border investigative data",
                    url="https://aleph.occrp.org",
                    use_cases=["Corporate investigations", "PEP screening", "Document search"]
                ),
                OSINTTool(
                    name="OpenOwnership",
                    category="Beneficial Ownership",
                    description="Beneficial ownership register",
                    url="https://register.openownership.org",
                    use_cases=["Ultimate beneficial owners", "Corporate structures"]
                ),
                OSINTTool(
                    name="Offshore Leaks Database",
                    category="Investigative",
                    description="ICIJ offshore entities database",
                    url="https://offshoreleaks.icij.org",
                    use_cases=["Offshore entities", "Panama/Paradise papers"]
                ),
                OSINTTool(
                    name="Crunchbase",
                    category="Business Intelligence",
                    description="Startup and company database",
                    url="https://crunchbase.com",
                    use_cases=["Funding rounds", "Company profiles", "Investor info"]
                ),
                OSINTTool(
                    name="Dun & Bradstreet",
                    category="Business Intelligence",
                    description="Commercial database",
                    url="https://dnb.com",
                    is_free=False,
                    use_cases=["Company credit", "Corporate hierarchies"]
                ),
                OSINTTool(
                    name="Import/Export Databases",
                    category="Trade Intelligence",
                    description="Shipping and customs data (ImportGenius, Panjiva)",
                    is_free=False,
                    use_cases=["Supply chain analysis", "Trade relationships"]
                )
            ],
            
            "dark_web_tools": [
                OSINTTool(
                    name="Tor Browser",
                    category="Access Tool",
                    description="Anonymous browser for .onion sites",
                    url="https://torproject.org",
                    use_cases=["Dark web access", "Anonymous browsing"]
                ),
                OSINTTool(
                    name="Ahmia",
                    category="Onion Search",
                    description="Search engine for Tor network",
                    url="https://ahmia.fi",
                    use_cases=["Onion site search"]
                ),
                OSINTTool(
                    name="Torch",
                    category="Onion Search",
                    description="Tor search engine",
                    use_cases=["Dark web search"]
                ),
                OSINTTool(
                    name="DarkSearch",
                    category="Onion Search",
                    description="Dark web search engine",
                    url="https://darksearch.io",
                    use_cases=["Dark web content search"]
                ),
                OSINTTool(
                    name="Hunchly",
                    category="Documentation",
                    description="Web capture and documentation",
                    url="https://hunch.ly",
                    is_free=False,
                    platforms=["Browser Extension"],
                    use_cases=["Evidence preservation", "Automated screenshots"]
                )
            ],
            
            "frameworks_automation": [
                OSINTTool(
                    name="Maltego",
                    category="Link Analysis",
                    description="Visual link analysis platform",
                    url="https://maltego.com",
                    is_free=False,
                    use_cases=["Entity graphing", "Relationship mapping", "Investigation"]
                ),
                OSINTTool(
                    name="SpiderFoot",
                    category="Automated OSINT",
                    description="Automated OSINT collection",
                    url="https://spiderfoot.net",
                    use_cases=["Automated reconnaissance", "Target profiling"]
                ),
                OSINTTool(
                    name="Recon-ng",
                    category="Recon Framework",
                    description="Web reconnaissance framework",
                    url="https://github.com/lanmaster53/recon-ng",
                    platforms=["Command Line"],
                    use_cases=["Modular recon", "API integration"]
                ),
                OSINTTool(
                    name="theHarvester",
                    category="Email/Domain Harvester",
                    description="Email and subdomain harvester",
                    url="https://github.com/laramies/theHarvester",
                    platforms=["Command Line"],
                    use_cases=["Email enumeration", "Subdomain discovery"]
                ),
                OSINTTool(
                    name="Photon",
                    category="Web Crawler",
                    description="Fast web crawler for OSINT",
                    url="https://github.com/s0md3v/Photon",
                    platforms=["Command Line"],
                    use_cases=["URL extraction", "Parameter discovery"]
                ),
                OSINTTool(
                    name="OSINT Framework",
                    category="Resource Collection",
                    description="Collection of OSINT tools and resources",
                    url="https://osintframework.com",
                    use_cases=["Tool discovery", "Resource navigation"]
                ),
                OSINTTool(
                    name="Buscador",
                    category="OSINT VM",
                    description="OSINT-focused Linux distribution",
                    use_cases=["Pre-configured OSINT environment"],
                    limitations=["No longer actively maintained"]
                ),
                OSINTTool(
                    name="Trace Labs OSINT VM",
                    category="OSINT VM",
                    description="VM for missing persons investigations",
                    url="https://tracelabs.org",
                    use_cases=["CTF competitions", "Missing persons OSINT"]
                )
            ],
            
            "transportation_tracking": [
                OSINTTool(
                    name="FlightRadar24",
                    category="Aviation",
                    description="Real-time flight tracking",
                    url="https://flightradar24.com",
                    use_cases=["Aircraft tracking", "Historical flights", "Airport monitoring"]
                ),
                OSINTTool(
                    name="FlightAware",
                    category="Aviation",
                    description="Flight tracking and aviation data",
                    url="https://flightaware.com",
                    use_cases=["Flight status", "Aircraft ownership"]
                ),
                OSINTTool(
                    name="ADS-B Exchange",
                    category="Aviation",
                    description="Unfiltered ADS-B flight data",
                    url="https://adsbexchange.com",
                    use_cases=["Military/government aircraft", "Unfiltered tracking"]
                ),
                OSINTTool(
                    name="MarineTraffic",
                    category="Maritime",
                    description="Ship tracking and maritime intel",
                    url="https://marinetraffic.com",
                    use_cases=["Vessel tracking", "Port monitoring", "Ship info"]
                ),
                OSINTTool(
                    name="VesselFinder",
                    category="Maritime",
                    description="Ship tracking",
                    url="https://vesselfinder.com",
                    use_cases=["AIS tracking", "Historical voyages"]
                ),
                OSINTTool(
                    name="OpenRailwayMap",
                    category="Rail",
                    description="Global railway infrastructure map",
                    url="https://openrailwaymap.org",
                    use_cases=["Rail infrastructure", "Station locations"]
                )
            ],
            
            "communications_tools": [
                OSINTTool(
                    name="Scan of the Month",
                    category="Radio",
                    description="Radio communications database",
                    use_cases=["Scanner frequencies", "Radio systems"]
                ),
                OSINTTool(
                    name="RadioReference",
                    category="Radio",
                    description="Radio frequency database",
                    url="https://radioreference.com",
                    use_cases=["Scanner frequencies", "Trunked systems"]
                ),
                OSINTTool(
                    name="WebSDR",
                    category="Radio",
                    description="Web-based software defined radio",
                    url="https://websdr.org",
                    use_cases=["Remote radio reception"]
                ),
                OSINTTool(
                    name="EchoLink",
                    category="Amateur Radio",
                    description="Amateur radio over IP",
                    use_cases=["Ham radio monitoring"]
                )
            ]
        }
    
    # =========================================================================
    # DATA SOURCES
    # =========================================================================
    
    def _initialize_sources(self):
        """Initialize OSINT data sources."""
        self.sources = {
            "government_sources": [
                OSINTSource(
                    name="PACER",
                    source_type="Court Records",
                    description="US Federal Court Records",
                    url="https://pacer.uscourts.gov",
                    access_type="subscription",
                    geographic_coverage="United States",
                    data_types=["Court filings", "Case information", "Legal documents"]
                ),
                OSINTSource(
                    name="RECAP Archive",
                    source_type="Court Records",
                    description="Free access to PACER documents",
                    url="https://courtlistener.com",
                    geographic_coverage="United States"
                ),
                OSINTSource(
                    name="SEC EDGAR",
                    source_type="Financial Filings",
                    description="US Securities filings",
                    url="https://sec.gov/edgar",
                    geographic_coverage="United States",
                    data_types=["10-K", "10-Q", "8-K", "Proxy statements", "Insider trading"]
                ),
                OSINTSource(
                    name="USPTO",
                    source_type="Intellectual Property",
                    description="US Patent and Trademark Office",
                    url="https://uspto.gov",
                    geographic_coverage="United States",
                    data_types=["Patents", "Trademarks", "Assignments"]
                ),
                OSINTSource(
                    name="FEC",
                    source_type="Political Finance",
                    description="Federal Election Commission",
                    url="https://fec.gov",
                    geographic_coverage="United States",
                    data_types=["Campaign contributions", "PAC data", "Candidate filings"]
                ),
                OSINTSource(
                    name="SAM.gov",
                    source_type="Government Contracts",
                    description="System for Award Management",
                    url="https://sam.gov",
                    geographic_coverage="United States",
                    data_types=["Federal contracts", "Grants", "Entity registration"]
                ),
                OSINTSource(
                    name="FOIA Libraries",
                    source_type="Government Documents",
                    description="Freedom of Information Act releases",
                    geographic_coverage="United States"
                ),
                OSINTSource(
                    name="Data.gov",
                    source_type="Open Data",
                    description="US Government open data portal",
                    url="https://data.gov",
                    geographic_coverage="United States"
                ),
                OSINTSource(
                    name="European Data Portal",
                    source_type="Open Data",
                    description="EU open data",
                    url="https://data.europa.eu",
                    geographic_coverage="European Union"
                ),
                OSINTSource(
                    name="UK National Archives",
                    source_type="Historical Records",
                    description="British historical records",
                    url="https://nationalarchives.gov.uk",
                    geographic_coverage="United Kingdom"
                )
            ],
            
            "media_sources": [
                OSINTSource(
                    name="LexisNexis",
                    source_type="News Archive",
                    description="Comprehensive news and legal database",
                    access_type="subscription",
                    data_types=["News articles", "Legal documents", "Company info"]
                ),
                OSINTSource(
                    name="Factiva",
                    source_type="News Archive",
                    description="Dow Jones news archive",
                    access_type="subscription"
                ),
                OSINTSource(
                    name="Google News",
                    source_type="News Aggregator",
                    description="News aggregation service",
                    url="https://news.google.com"
                ),
                OSINTSource(
                    name="Internet Archive",
                    source_type="Web Archive",
                    description="Historical web content",
                    url="https://archive.org",
                    data_types=["Websites", "Books", "Video", "Audio"]
                ),
                OSINTSource(
                    name="Common Crawl",
                    source_type="Web Archive",
                    description="Open web crawl data",
                    url="https://commoncrawl.org"
                )
            ],
            
            "academic_sources": [
                OSINTSource(
                    name="Google Scholar",
                    source_type="Academic",
                    description="Academic paper search",
                    url="https://scholar.google.com"
                ),
                OSINTSource(
                    name="PubMed",
                    source_type="Medical Literature",
                    description="Biomedical literature database",
                    url="https://pubmed.ncbi.nlm.nih.gov"
                ),
                OSINTSource(
                    name="arXiv",
                    source_type="Preprints",
                    description="Scientific preprint repository",
                    url="https://arxiv.org"
                ),
                OSINTSource(
                    name="JSTOR",
                    source_type="Academic Journals",
                    description="Digital library of journals",
                    url="https://jstor.org",
                    access_type="subscription"
                ),
                OSINTSource(
                    name="ResearchGate",
                    source_type="Academic Network",
                    description="Scientific network",
                    url="https://researchgate.net"
                ),
                OSINTSource(
                    name="Semantic Scholar",
                    source_type="AI Academic Search",
                    description="AI-powered academic search",
                    url="https://semanticscholar.org"
                )
            ],
            
            "sanctions_watchlists": [
                OSINTSource(
                    name="OFAC SDN List",
                    source_type="Sanctions",
                    description="US Treasury sanctions list",
                    url="https://sanctionssearch.ofac.treas.gov",
                    geographic_coverage="Global"
                ),
                OSINTSource(
                    name="EU Sanctions Map",
                    source_type="Sanctions",
                    description="European Union sanctions",
                    url="https://sanctionsmap.eu",
                    geographic_coverage="Global"
                ),
                OSINTSource(
                    name="UN Security Council Sanctions",
                    source_type="Sanctions",
                    description="UN consolidated list",
                    url="https://un.org/securitycouncil/sanctions",
                    geographic_coverage="Global"
                ),
                OSINTSource(
                    name="Interpol Red Notices",
                    source_type="Wanted Persons",
                    description="International wanted notices",
                    url="https://interpol.int/notice/search/wanted",
                    geographic_coverage="Global"
                ),
                OSINTSource(
                    name="FBI Most Wanted",
                    source_type="Wanted Persons",
                    description="FBI wanted list",
                    url="https://fbi.gov/wanted",
                    geographic_coverage="United States"
                ),
                OSINTSource(
                    name="OpenSanctions",
                    source_type="Sanctions Aggregator",
                    description="Open source sanctions database",
                    url="https://opensanctions.org",
                    geographic_coverage="Global"
                )
            ],
            
            "property_records": [
                OSINTSource(
                    name="County Assessor Records",
                    source_type="Property",
                    description="Local property tax records",
                    geographic_coverage="United States (by county)"
                ),
                OSINTSource(
                    name="Land Registry",
                    source_type="Property",
                    description="UK property ownership",
                    url="https://landregistry.gov.uk",
                    geographic_coverage="United Kingdom"
                ),
                OSINTSource(
                    name="Zillow",
                    source_type="Real Estate",
                    description="Property values and sales",
                    url="https://zillow.com",
                    geographic_coverage="United States"
                ),
                OSINTSource(
                    name="Redfin",
                    source_type="Real Estate",
                    description="Real estate data",
                    url="https://redfin.com",
                    geographic_coverage="United States"
                )
            ]
        }
    
    # =========================================================================
    # METHODOLOGIES AND FRAMEWORKS
    # =========================================================================
    
    def _initialize_methodologies(self):
        """Initialize OSINT methodologies."""
        self.methodologies = {
            "intelligence_cycle": OSINTMethodology(
                name="The Intelligence Cycle",
                description="Traditional intelligence production cycle adapted for OSINT",
                phases=[
                    "1. Planning & Direction: Define intelligence requirements and priorities",
                    "2. Collection: Gather information from open sources",
                    "3. Processing: Convert raw data into usable format",
                    "4. Analysis & Production: Analyze and create intelligence products",
                    "5. Dissemination: Distribute to stakeholders",
                    "6. Feedback: Refine based on consumer feedback"
                ]
            ),
            
            "osint_cycle": OSINTMethodology(
                name="OSINT Cycle",
                description="Specialized cycle for open source intelligence",
                phases=[
                    "1. Requirements Definition: What do we need to know?",
                    "2. Source Identification: Where can we find this information?",
                    "3. Acquisition: Collect the data",
                    "4. Processing: Clean and organize data",
                    "5. Analysis: Extract insights and meaning",
                    "6. Production: Create reports and visualizations",
                    "7. Dissemination: Share with stakeholders",
                    "8. Feedback: Iterate and improve"
                ]
            ),
            
            "f3ead": OSINTMethodology(
                name="F3EAD",
                description="Military targeting cycle (Find, Fix, Finish, Exploit, Analyze, Disseminate)",
                phases=[
                    "Find: Identify targets through intelligence",
                    "Fix: Locate target precisely",
                    "Finish: Engage/take action on target",
                    "Exploit: Gather intelligence from action",
                    "Analyze: Process intelligence gained",
                    "Disseminate: Share intelligence products"
                ],
                best_practices=[
                    "Continuous cycle - not linear",
                    "Each phase informs the others",
                    "Rapid iteration is key"
                ]
            ),
            
            "pivoting": OSINTMethodology(
                name="Pivoting Methodology",
                description="Using one piece of information to discover connected information",
                phases=[
                    "1. Start with seed data (email, username, phone, etc.)",
                    "2. Search for accounts associated with seed",
                    "3. Extract new identifiers from discovered accounts",
                    "4. Use new identifiers as seeds",
                    "5. Build connection map between entities",
                    "6. Validate connections"
                ],
                best_practices=[
                    "Document every pivot point",
                    "Verify connections before assuming validity",
                    "Use multiple sources for corroboration",
                    "Be aware of common usernames/emails"
                ]
            ),
            
            "bellingcat_workflow": OSINTMethodology(
                name="Bellingcat Investigation Workflow",
                description="Methodology used by Bellingcat for investigations",
                phases=[
                    "1. Define the question/hypothesis",
                    "2. Identify potential sources",
                    "3. Collect and archive evidence",
                    "4. Verify authenticity of evidence",
                    "5. Geolocate and chronolocate",
                    "6. Cross-reference and corroborate",
                    "7. Document methodology",
                    "8. Peer review",
                    "9. Publish findings"
                ]
            ),
            
            "sock_methodology": OSINTMethodology(
                name="SOCK (Skills, Objectives, Collection, Knowledge)",
                description="Framework for planning OSINT operations",
                phases=[
                    "Skills: Assess available skills and tools",
                    "Objectives: Define clear intelligence objectives",
                    "Collection: Plan collection strategy",
                    "Knowledge: Produce and share knowledge"
                ]
            ),
            
            "pir_framework": OSINTMethodology(
                name="Priority Intelligence Requirements (PIR)",
                description="Framework for prioritizing intelligence collection",
                phases=[
                    "1. Identify decision points",
                    "2. Define information needs for each decision",
                    "3. Prioritize requirements by importance and urgency",
                    "4. Assign collection resources",
                    "5. Track collection progress",
                    "6. Review and update priorities"
                ]
            ),
            
            "craap_test": OSINTMethodology(
                name="CRAAP Test",
                description="Source evaluation framework",
                phases=[
                    "Currency: How recent is the information?",
                    "Relevance: Does it relate to your topic?",
                    "Authority: Who is the source? What are their credentials?",
                    "Accuracy: Is the information supported by evidence?",
                    "Purpose: Why does this information exist?"
                ]
            ),
            
            "4chan_8chan_methodology": OSINTMethodology(
                name="Anonymous Board Investigation",
                description="Methods for investigating anonymous imageboard content",
                phases=[
                    "1. Archive threads before they expire",
                    "2. Extract unique identifiers (tripcodes, file hashes)",
                    "3. Analyze posting patterns and timestamps",
                    "4. Cross-reference with archived content",
                    "5. Image forensics on posted media",
                    "6. Metadata extraction"
                ],
                limitations=[
                    "Content expires quickly",
                    "Anonymity makes attribution difficult",
                    "High volume of false/misleading information"
                ]
            )
        }
        
        self.analysis_frameworks = {
            "ach": {
                "name": "Analysis of Competing Hypotheses",
                "description": "Structured technique to evaluate multiple hypotheses",
                "steps": [
                    "1. Identify possible hypotheses",
                    "2. List significant evidence and arguments",
                    "3. Create a matrix with hypotheses vs. evidence",
                    "4. Refine matrix, reconsider hypotheses",
                    "5. Draw tentative conclusions",
                    "6. Analyze sensitivity of conclusions",
                    "7. Report conclusions and evidence",
                    "8. Identify milestones for future observation"
                ]
            },
            "sna": {
                "name": "Social Network Analysis",
                "description": "Analysis of social structures through networks",
                "metrics": [
                    "Degree Centrality: Number of connections",
                    "Betweenness Centrality: Bridge position",
                    "Closeness Centrality: Distance to all nodes",
                    "Eigenvector Centrality: Connection quality",
                    "Clustering Coefficient: Community detection"
                ]
            },
            "link_analysis": {
                "name": "Link Analysis",
                "description": "Visual representation of relationships",
                "elements": [
                    "Nodes: Entities (people, organizations, etc.)",
                    "Edges: Relationships between entities",
                    "Attributes: Properties of nodes and edges",
                    "Clusters: Groups of related entities"
                ]
            }
        }
    
    # =========================================================================
    # LEGAL FRAMEWORKS
    # =========================================================================
    
    def _initialize_legal_frameworks(self):
        """Initialize legal frameworks governing OSINT."""
        self.legal_frameworks = {
            "united_states": [
                LegalFramework(
                    jurisdiction="United States",
                    law_name="Computer Fraud and Abuse Act (CFAA)",
                    description="Prohibits unauthorized access to protected computers",
                    year_enacted=1986,
                    key_provisions=[
                        "Unauthorized access to computers",
                        "Exceeding authorized access",
                        "Trafficking in passwords",
                        "Transmitting code causing damage"
                    ],
                    implications_for_osint=[
                        "Scraping may violate if terms of service prohibit",
                        "hiQ v. LinkedIn provides some protection for public data",
                        "Cannot circumvent access controls",
                        "Gray area around Terms of Service violations"
                    ]
                ),
                LegalFramework(
                    jurisdiction="United States",
                    law_name="Electronic Communications Privacy Act (ECPA)",
                    description="Protects electronic communications from interception",
                    year_enacted=1986,
                    implications_for_osint=[
                        "Cannot intercept communications in transit",
                        "Public posts are generally fair game",
                        "Private messages require authorization"
                    ]
                ),
                LegalFramework(
                    jurisdiction="United States",
                    law_name="Driver's Privacy Protection Act (DPPA)",
                    description="Restricts disclosure of personal information from motor vehicle records",
                    year_enacted=1994
                ),
                LegalFramework(
                    jurisdiction="United States",
                    law_name="Freedom of Information Act (FOIA)",
                    description="Provides public access to federal agency records",
                    year_enacted=1966,
                    implications_for_osint=[
                        "Powerful tool for obtaining government records",
                        "Nine exemptions limit disclosure",
                        "Can take months to years for response"
                    ]
                ),
                LegalFramework(
                    jurisdiction="United States - California",
                    law_name="California Consumer Privacy Act (CCPA)",
                    description="Consumer privacy rights in California",
                    year_enacted=2020,
                    implications_for_osint=[
                        "Right to know what data is collected",
                        "Right to delete personal information",
                        "Does not apply to publicly available information"
                    ]
                )
            ],
            
            "european_union": [
                LegalFramework(
                    jurisdiction="European Union",
                    law_name="General Data Protection Regulation (GDPR)",
                    description="Comprehensive data protection regulation",
                    year_enacted=2018,
                    key_provisions=[
                        "Consent required for data processing",
                        "Right to erasure (right to be forgotten)",
                        "Data portability rights",
                        "Strict breach notification requirements",
                        "Heavy fines for violations"
                    ],
                    implications_for_osint=[
                        "Processing personal data requires legal basis",
                        "Legitimate interest may apply for some OSINT",
                        "Cannot profile EU citizens without basis",
                        "Extraterritorial reach affects global operations",
                        "Journalism exemption may apply"
                    ]
                ),
                LegalFramework(
                    jurisdiction="European Union",
                    law_name="ePrivacy Directive",
                    description="Privacy in electronic communications",
                    implications_for_osint=[
                        "Cookie consent requirements",
                        "Email marketing restrictions"
                    ]
                ),
                LegalFramework(
                    jurisdiction="European Union",
                    law_name="Digital Services Act (DSA)",
                    description="Regulation of digital services",
                    year_enacted=2022,
                    implications_for_osint=[
                        "Platform transparency requirements",
                        "Researcher access to platform data"
                    ]
                )
            ],
            
            "united_kingdom": [
                LegalFramework(
                    jurisdiction="United Kingdom",
                    law_name="Data Protection Act 2018",
                    description="UK implementation of GDPR",
                    year_enacted=2018
                ),
                LegalFramework(
                    jurisdiction="United Kingdom",
                    law_name="Computer Misuse Act 1990",
                    description="Criminalizes unauthorized computer access",
                    year_enacted=1990
                ),
                LegalFramework(
                    jurisdiction="United Kingdom",
                    law_name="Regulation of Investigatory Powers Act (RIPA)",
                    description="Governs surveillance and investigation powers",
                    year_enacted=2000
                )
            ],
            
            "other_jurisdictions": [
                LegalFramework(
                    jurisdiction="Australia",
                    law_name="Privacy Act 1988",
                    description="Australian federal privacy law"
                ),
                LegalFramework(
                    jurisdiction="Canada",
                    law_name="PIPEDA",
                    description="Personal Information Protection and Electronic Documents Act"
                ),
                LegalFramework(
                    jurisdiction="Brazil",
                    law_name="LGPD",
                    description="Lei Geral de ProteÃ§Ã£o de Dados (Brazilian GDPR)"
                )
            ]
        }
        
        self.ethical_guidelines = {
            "principles": [
                "Minimize harm to individuals",
                "Respect privacy where reasonable",
                "Verify information before acting on it",
                "Consider downstream consequences",
                "Document methodology for accountability",
                "Maintain objectivity and avoid bias",
                "Protect sources and methods appropriately",
                "Comply with applicable laws",
                "Consider public interest",
                "Be transparent about limitations"
            ],
            
            "red_lines": [
                "Never hack or gain unauthorized access",
                "Do not harass or stalk individuals",
                "Avoid doxxing private individuals",
                "Do not engage in social engineering under false pretenses",
                "Never endanger sources or subjects",
                "Do not violate court orders or legal restrictions",
                "Avoid facilitating illegal activities"
            ],
            
            "consent_considerations": [
                "Public figures have reduced privacy expectations",
                "Private individuals deserve more protection",
                "Context matters - business vs personal information",
                "Consider how information will be used",
                "Aggregation can reveal sensitive patterns"
            ]
        }
    
    # =========================================================================
    # SEARCH OPERATORS
    # =========================================================================
    
    def _initialize_search_operators(self):
        """Initialize search engine operators (Google Dorks, etc.)."""
        self.search_operators = {
            "google": [
                SearchOperator(
                    operator="site:",
                    description="Limit results to specific domain",
                    example='site:linkedin.com "John Smith"',
                    supported_engines=["Google", "Bing", "DuckDuckGo"]
                ),
                SearchOperator(
                    operator="filetype:",
                    description="Search for specific file types",
                    example="filetype:pdf annual report",
                    supported_engines=["Google", "Bing"]
                ),
                SearchOperator(
                    operator="inurl:",
                    description="Search for terms in URL",
                    example="inurl:admin login",
                    supported_engines=["Google", "Bing"]
                ),
                SearchOperator(
                    operator="intitle:",
                    description="Search for terms in page title",
                    example='intitle:"index of"',
                    supported_engines=["Google", "Bing"]
                ),
                SearchOperator(
                    operator="intext:",
                    description="Search for terms in page body",
                    example='intext:"confidential"',
                    supported_engines=["Google"]
                ),
                SearchOperator(
                    operator="cache:",
                    description="View cached version of page",
                    example="cache:example.com",
                    supported_engines=["Google"]
                ),
                SearchOperator(
                    operator="related:",
                    description="Find similar websites",
                    example="related:nytimes.com",
                    supported_engines=["Google"]
                ),
                SearchOperator(
                    operator="OR",
                    description="Boolean OR operator",
                    example="apple OR microsoft",
                    supported_engines=["Google", "Bing", "DuckDuckGo"]
                ),
                SearchOperator(
                    operator="-",
                    description="Exclude term from results",
                    example="python -snake",
                    supported_engines=["Google", "Bing", "DuckDuckGo"]
                ),
                SearchOperator(
                    operator='"..."',
                    description="Exact phrase match",
                    example='"open source intelligence"',
                    supported_engines=["Google", "Bing", "DuckDuckGo"]
                ),
                SearchOperator(
                    operator="*",
                    description="Wildcard for unknown terms",
                    example='"CEO of * company"',
                    supported_engines=["Google"]
                ),
                SearchOperator(
                    operator="AROUND(n)",
                    description="Terms within n words of each other",
                    example="apple AROUND(4) ceo",
                    supported_engines=["Google"]
                ),
                SearchOperator(
                    operator="before:",
                    description="Results before date",
                    example="covid before:2020-03-01",
                    supported_engines=["Google"]
                ),
                SearchOperator(
                    operator="after:",
                    description="Results after date",
                    example="covid after:2020-01-01",
                    supported_engines=["Google"]
                ),
                SearchOperator(
                    operator="define:",
                    description="Dictionary definition",
                    example="define:osint",
                    supported_engines=["Google"]
                ),
                SearchOperator(
                    operator="info:",
                    description="Information about a URL",
                    example="info:example.com",
                    supported_engines=["Google"]
                ),
                SearchOperator(
                    operator="link:",
                    description="Find pages linking to URL (deprecated)",
                    example="link:example.com",
                    supported_engines=["Google"]
                ),
                SearchOperator(
                    operator="ext:",
                    description="Alternative to filetype",
                    example="ext:docx budget",
                    supported_engines=["Google", "Bing"]
                )
            ],
            
            "google_dorks_examples": {
                "sensitive_files": [
                    'filetype:xls "password"',
                    'filetype:doc "confidential"',
                    'filetype:pdf "internal use only"',
                    'filetype:sql "insert into"',
                    'filetype:log "password"',
                    'filetype:bak inurl:"backup"'
                ],
                "directory_listings": [
                    'intitle:"index of" "parent directory"',
                    'intitle:"index of" inurl:ftp',
                    'intitle:"index of" mp3',
                    'intitle:"index of" "backup"'
                ],
                "login_pages": [
                    'inurl:admin intitle:login',
                    'inurl:adminlogin',
                    'inurl:wp-admin',
                    'inurl:"/phpmyadmin"'
                ],
                "exposed_data": [
                    '"index of" "database.sql"',
                    'filetype:env "DB_PASSWORD"',
                    'filetype:yml "password:"',
                    '"BEGIN RSA PRIVATE KEY" filetype:key'
                ],
                "social_media": [
                    'site:linkedin.com/in/ "current" "company name"',
                    'site:twitter.com "company name"',
                    'site:facebook.com "email@domain.com"'
                ],
                "information_gathering": [
                    'site:pastebin.com "target.com"',
                    'site:github.com "api_key" "target.com"',
                    '"@target.com" filetype:xls',
                    'site:*.target.com -www'
                ]
            },
            
            "shodan_queries": {
                "webcams": [
                    'webcam has_screenshot:true',
                    'device:webcam country:US',
                    'title:"webcamXP"'
                ],
                "databases": [
                    'port:27017 "MongoDB"',
                    'port:9200 "elastic"',
                    'port:6379 "redis"'
                ],
                "industrial": [
                    'port:502 "Modbus"',
                    '"Siemens" port:102',
                    'ics protocol'
                ],
                "network_devices": [
                    'cisco-ios "last-modified"',
                    'mikrotik country:US',
                    'huawei router'
                ]
            }
        }
    
    # =========================================================================
    # TECHNIQUES AND TRADECRAFT
    # =========================================================================
    
    def _initialize_techniques(self):
        """Initialize OSINT techniques."""
        self.techniques = {
            "geolocation": {
                "description": "Determining location from images, videos, and other data",
                "methods": [
                    {
                        "name": "Landmark Identification",
                        "description": "Identifying known structures, monuments, or unique features",
                        "tools": ["Google Maps", "Google Earth", "Wikimapia"]
                    },
                    {
                        "name": "Sun/Shadow Analysis",
                        "description": "Using sun position and shadows to determine time and location",
                        "tools": ["SunCalc", "ShadowMap", "SunEarthTools"]
                    },
                    {
                        "name": "Language/Script Analysis",
                        "description": "Identifying location through visible text and signage",
                        "indicators": ["Street signs", "Shop names", "License plates", "Billboards"]
                    },
                    {
                        "name": "Infrastructure Analysis",
                        "description": "Using visible infrastructure to narrow location",
                        "indicators": ["Power lines", "Road markings", "Utility covers", "Architecture style"]
                    },
                    {
                        "name": "Flora/Fauna Analysis",
                        "description": "Using vegetation and animals to determine region",
                        "indicators": ["Tree species", "Crop types", "Animal species"]
                    },
                    {
                        "name": "Weather Correlation",
                        "description": "Matching visible weather conditions to weather data",
                        "tools": ["Weather Underground", "Historical weather data"]
                    },
                    {
                        "name": "EXIF Data Extraction",
                        "description": "Extracting GPS coordinates from image metadata",
                        "tools": ["ExifTool", "Jeffrey's EXIF Viewer"]
                    },
                    {
                        "name": "Reverse Image Search",
                        "description": "Finding original source or similar images",
                        "tools": ["Google Images", "TinEye", "Yandex Images"]
                    }
                ],
                "visual_indicators": {
                    "road_signs": "Color schemes, shapes, and languages vary by country",
                    "license_plates": "Formats indicate country/region",
                    "electrical_outlets": "Different standards by country",
                    "driving_side": "Left vs right-hand driving",
                    "architecture": "Building styles, roof types, materials",
                    "vegetation": "Climate-specific plants and landscapes",
                    "street_furniture": "Bollards, benches, lampposts vary regionally",
                    "telecommunications": "Phone booth styles, antenna types",
                    "currency": "Visible prices or currency symbols"
                }
            },
            
            "chronolocation": {
                "description": "Determining when an image or video was taken",
                "methods": [
                    "EXIF timestamp analysis",
                    "Shadow length calculation",
                    "Weather data correlation",
                    "Event correlation (visible events with known dates)",
                    "Construction progress comparison",
                    "Satellite imagery timeline comparison",
                    "Social media timestamp analysis",
                    "Newspaper/TV screens in images"
                ]
            },
            
            "image_verification": {
                "description": "Verifying authenticity of images",
                "techniques": [
                    {
                        "name": "Error Level Analysis (ELA)",
                        "description": "Detects areas with different compression levels",
                        "tools": ["FotoForensics", "Forensically"]
                    },
                    {
                        "name": "Metadata Analysis",
                        "description": "Examining EXIF and other metadata",
                        "tools": ["ExifTool", "Jeffrey's EXIF Viewer"]
                    },
                    {
                        "name": "Reverse Image Search",
                        "description": "Finding original or earlier versions",
                        "tools": ["Google", "TinEye", "Yandex"]
                    },
                    {
                        "name": "Clone Detection",
                        "description": "Finding duplicated regions within image",
                        "tools": ["Forensically", "Image Manipulation Detector"]
                    },
                    {
                        "name": "Lighting/Shadow Consistency",
                        "description": "Checking for inconsistent lighting sources"
                    },
                    {
                        "name": "Perspective Analysis",
                        "description": "Verifying perspective is consistent"
                    },
                    {
                        "name": "Reflection Analysis",
                        "description": "Checking reflections match the scene"
                    },
                    {
                        "name": "Digital Watermark Detection",
                        "description": "Finding hidden watermarks"
                    }
                ]
            },
            
            "video_verification": {
                "description": "Verifying authenticity of videos",
                "techniques": [
                    "Keyframe extraction and analysis",
                    "Audio analysis",
                    "Metadata examination",
                    "Reverse video search (YouTube DataViewer)",
                    "Frame-by-frame analysis",
                    "Deepfake detection",
                    "Compression artifact analysis"
                ],
                "tools": ["InVID", "WeVerify", "YouTube DataViewer"]
            },
            
            "social_media_investigation": {
                "description": "Techniques for investigating social media",
                "methods": [
                    {
                        "name": "Account Analysis",
                        "description": "Examining account metadata, creation date, posting patterns",
                        "indicators": ["Account age", "Post frequency", "Follower/following ratio",
                                      "Bio consistency", "Profile picture analysis"]
                    },
                    {
                        "name": "Content Analysis",
                        "description": "Analyzing posted content for intelligence",
                        "techniques": ["Sentiment analysis", "Topic modeling", "Language analysis",
                                      "Image/video analysis"]
                    },
                    {
                        "name": "Network Analysis",
                        "description": "Mapping connections and interactions",
                        "metrics": ["Who interacts with whom", "Group memberships",
                                   "Shared connections", "Engagement patterns"]
                    },
                    {
                        "name": "Temporal Analysis",
                        "description": "Analyzing timing of posts and activity",
                        "indicators": ["Time zones", "Activity patterns", "Response times"]
                    },
                    {
                        "name": "Cross-Platform Correlation",
                        "description": "Linking accounts across platforms",
                        "methods": ["Username searching", "Image matching", "Bio correlation",
                                   "Writing style analysis"]
                    }
                ],
                "platform_specific": {
                    "twitter": {
                        "tools": ["TweetDeck", "Social Bearing", "Twitonomy"],
                        "techniques": ["Advanced search operators", "Tweet archiving",
                                      "Follower analysis", "Hashtag tracking"]
                    },
                    "facebook": {
                        "tools": ["Graph Search (limited)", "Social Searcher"],
                        "techniques": ["Group infiltration", "Event tracking", "Check-in analysis"]
                    },
                    "instagram": {
                        "tools": ["Instaloader", "Picuki", "ImgInn"],
                        "techniques": ["Location tagging", "Story archiving", "Comment analysis"]
                    },
                    "linkedin": {
                        "tools": ["LinkedIn Sales Navigator", "PhantomBuster"],
                        "techniques": ["Employment verification", "Connection mapping",
                                      "Company employee enumeration"]
                    },
                    "telegram": {
                        "tools": ["Telegram Scraper", "TGStat"],
                        "techniques": ["Channel monitoring", "Member enumeration",
                                      "Message archiving"]
                    },
                    "discord": {
                        "tools": ["DiscordLeaks", "DiscordBee"],
                        "techniques": ["Server infiltration", "User ID tracking", "Bot integration"]
                    },
                    "reddit": {
                        "tools": ["Pushshift", "Redective", "Reddit Investigator"],
                        "techniques": ["Comment history analysis", "Subreddit mapping",
                                      "Deleted content recovery"]
                    },
                    "tiktok": {
                        "tools": ["TikTok scraping tools"],
                        "techniques": ["Hashtag analysis", "Sound tracking", "Comment mining"]
                    }
                }
            },
            
            "domain_investigation": {
                "description": "Investigating domain names and websites",
                "steps": [
                    "WHOIS lookup for registration information",
                    "Historical WHOIS for previous ownership",
                    "DNS record enumeration",
                    "Subdomain discovery",
                    "SSL certificate analysis",
                    "Web archive review",
                    "Technology stack identification",
                    "Related domain discovery",
                    "IP resolution and reverse DNS",
                    "ASN and network analysis"
                ],
                "tools": ["DomainTools", "SecurityTrails", "crt.sh", "DNSDumpster",
                         "BuiltWith", "Wayback Machine", "ViewDNS.info"]
            },
            
            "email_investigation": {
                "description": "Investigating email addresses",
                "techniques": [
                    "Email header analysis",
                    "Breach database checking",
                    "Social media account discovery",
                    "Domain reputation checking",
                    "Email validation",
                    "Gravatar lookup",
                    "Google account discovery"
                ],
                "tools": ["Hunter.io", "Have I Been Pwned", "Epieos", "EmailRep"]
            },
            
            "phone_investigation": {
                "description": "Investigating phone numbers",
                "techniques": [
                    "Carrier lookup",
                    "Caller ID databases",
                    "Social media reverse lookup",
                    "Messaging app enumeration",
                    "International format parsing"
                ],
                "tools": ["Truecaller", "NumVerify", "PhoneInfoga", "Sync.me"]
            }
        }
    
    # =========================================================================
    # RESOURCES
    # =========================================================================
    
    def _initialize_resources(self):
        """Initialize OSINT learning resources."""
        self.resources = {
            "books": [
                {
                    "title": "Open Source Intelligence Techniques",
                    "author": "Michael Bazzell",
                    "description": "Comprehensive OSINT methodology guide, updated regularly",
                    "topics": ["Search engines", "Social media", "People search", "Methodology"]
                },
                {
                    "title": "We Are Bellingcat",
                    "author": "Eliot Higgins",
                    "description": "Story of Bellingcat and open source investigations",
                    "topics": ["Case studies", "Methodology", "History"]
                },
                {
                    "title": "OSINT Techniques",
                    "author": "Rae Baker",
                    "description": "Practical guide to OSINT investigation",
                    "topics": ["Techniques", "Tools", "Case studies"]
                },
                {
                    "title": "Hunting Cyber Criminals",
                    "author": "Vinny Troia",
                    "description": "Using OSINT to investigate cybercriminals",
                    "topics": ["Cyber investigation", "Dark web", "Attribution"]
                },
                {
                    "title": "The Art of Intrusion",
                    "author": "Kevin Mitnick",
                    "description": "Social engineering and information gathering",
                    "topics": ["Social engineering", "Reconnaissance"]
                },
                {
                    "title": "Hacking: The Art of Exploitation",
                    "author": "Jon Erickson",
                    "description": "Technical hacking with recon components",
                    "topics": ["Technical skills", "Network analysis"]
                }
            ],
            
            "training_courses": [
                {
                    "name": "SANS SEC487",
                    "provider": "SANS Institute",
                    "description": "Open-Source Intelligence Gathering and Analysis",
                    "cost": "Paid"
                },
                {
                    "name": "TCM Security OSINT Fundamentals",
                    "provider": "TCM Security",
                    "description": "Practical OSINT training",
                    "cost": "Paid"
                },
                {
                    "name": "Bellingcat Online Investigation Toolkit",
                    "provider": "Bellingcat",
                    "description": "Free resources and guides",
                    "cost": "Free",
                    "url": "https://docs.google.com/spreadsheets/d/18rtqh8EG2q1xBo2cLNyhIDuK9jrPGwYr9DI2UncoqJQ"
                },
                {
                    "name": "OSINT Combine",
                    "provider": "OSINT Combine",
                    "description": "Various OSINT training options",
                    "url": "https://www.osintcombine.com"
                },
                {
                    "name": "Trace Labs Training",
                    "provider": "Trace Labs",
                    "description": "Missing persons OSINT training",
                    "cost": "Free/Paid",
                    "url": "https://tracelabs.org"
                },
                {
                    "name": "Cyber Mentor OSINT",
                    "provider": "TCM Security",
                    "description": "Practical Ethical Hacking OSINT module",
                    "cost": "Paid"
                },
                {
                    "name": "IntelTechniques Training",
                    "provider": "Michael Bazzell",
                    "description": "Privacy and OSINT training",
                    "url": "https://inteltechniques.com"
                }
            ],
            
            "certifications": [
                {
                    "name": "GOSI",
                    "full_name": "GIAC Open Source Intelligence",
                    "provider": "GIAC/SANS",
                    "description": "Industry-recognized OSINT certification"
                },
                {
                    "name": "MCSI MOIS",
                    "full_name": "MCSI OSINT Certification",
                    "provider": "MCSI",
                    "description": "Practical OSINT certification"
                },
                {
                    "name": "OSINT Combine Certifications",
                    "provider": "OSINT Combine",
                    "description": "Various specialized certifications"
                }
            ],
            
            "communities": [
                {
                    "name": "OSINT Curious",
                    "type": "Community/Podcast",
                    "url": "https://osintcurio.us",
                    "description": "OSINT community with webcasts and resources"
                },
                {
                    "name": "Trace Labs",
                    "type": "Non-profit/CTF",
                    "url": "https://tracelabs.org",
                    "description": "Missing persons OSINT CTF events"
                },
                {
                    "name": "OSINT Dojo",
                    "type": "Training Platform",
                    "url": "https://www.osintdojo.com",
                    "description": "Free OSINT training resources"
                },
                {
                    "name": "Bellingcat Discord",
                    "type": "Discord Community",
                    "description": "Active OSINT investigation community"
                },
                {
                    "name": "r/OSINT",
                    "type": "Reddit",
                    "url": "https://reddit.com/r/OSINT",
                    "description": "OSINT subreddit"
                },
                {
                    "name": "OSINT-FR",
                    "type": "French Community",
                    "description": "French-speaking OSINT community"
                }
            ],
            
            "podcasts": [
                {
                    "name": "OSINT Curious Webcasts",
                    "description": "Regular OSINT webcasts and discussions"
                },
                {
                    "name": "The Privacy, Security, & OSINT Show",
                    "host": "Michael Bazzell",
                    "description": "Privacy and OSINT techniques"
                },
                {
                    "name": "Hacking Humans",
                    "description": "Social engineering focus"
                },
                {
                    "name": "Darknet Diaries",
                    "description": "True stories from the dark side of the internet"
                },
                {
                    "name": "Malicious Life",
                    "description": "Cybersecurity history and stories"
                }
            ],
            
            "youtube_channels": [
                {"name": "OSINT Dojo", "focus": "OSINT tutorials"},
                {"name": "The Cyber Mentor", "focus": "Ethical hacking including OSINT"},
                {"name": "John Hammond", "focus": "Cybersecurity and CTFs"},
                {"name": "NahamSec", "focus": "Bug bounty and recon"},
                {"name": "David Bombal", "focus": "Network security and tools"},
                {"name": "Bellingcat", "focus": "Investigation case studies"},
                {"name": "Benjamin Strick", "focus": "Visual investigations"}
            ],
            
            "conferences": [
                {
                    "name": "OSMOSIS",
                    "description": "OSINT Mini Summit",
                    "frequency": "Annual"
                },
                {
                    "name": "DEF CON Recon Village",
                    "description": "Reconnaissance focused village at DEF CON",
                    "frequency": "Annual"
                },
                {
                    "name": "OSINT Summit",
                    "description": "SANS OSINT Summit",
                    "frequency": "Annual"
                },
                {
                    "name": "Trace Labs OSINT CTF",
                    "description": "Missing persons CTF events",
                    "frequency": "Multiple per year"
                }
            ],
            
            "newsletters": [
                {
                    "name": "Week in OSINT",
                    "description": "Weekly OSINT news and tools",
                    "url": "https://sector035.nl/articles/category:week-in-osint"
                },
                {
                    "name": "OSINT Newsletter",
                    "description": "Curated OSINT content"
                },
                {
                    "name": "IntelTechniques Blog",
                    "description": "Michael Bazzell's blog",
                    "url": "https://inteltechniques.com/blog"
                }
            ]
        }
    
    # =========================================================================
    # BEST PRACTICES
    # =========================================================================
    
    def _initialize_best_practices(self):
        """Initialize OSINT best practices."""
        self.best_practices = {
            "documentation": {
                "description": "Proper documentation is essential for OSINT",
                "guidelines": [
                    "Screenshot everything - pages can be edited or deleted",
                    "Use archiving services (archive.today, Wayback Machine)",
                    "Record timestamps for all findings",
                    "Document your methodology step by step",
                    "Use hash values for file integrity",
                    "Maintain chain of custody for legal matters",
                    "Use dedicated documentation tools (Hunchly, etc.)",
                    "Create detailed logs of searches and results",
                    "Preserve metadata when possible",
                    "Back up everything to multiple locations"
                ]
            },
            
            "verification": {
                "description": "All information should be verified before use",
                "guidelines": [
                    "Use multiple independent sources",
                    "Verify original source of information",
                    "Check for signs of manipulation",
                    "Consider source bias and motivation",
                    "Apply the CRAAP test",
                    "Use NATO source/information rating system",
                    "Look for corroborating evidence",
                    "Be skeptical of too-good-to-be-true findings",
                    "Verify before publicizing or acting"
                ]
            },
            
            "operational_security": {
                "description": "Protecting yourself during OSINT operations",
                "guidelines": [
                    "Use dedicated devices/VMs for investigations",
                    "Implement proper network isolation",
                    "Use VPN/Tor appropriately",
                    "Create sock puppet accounts properly",
                    "Avoid attribution through careless mistakes",
                    "Never interact with targets directly",
                    "Be aware of honeypots and counterintelligence",
                    "Separate personal and operational activities",
                    "Regularly audit your own digital footprint",
                    "Use different browsers for different purposes"
                ]
            },
            
            "data_management": {
                "description": "Managing collected data effectively",
                "guidelines": [
                    "Organize data systematically from the start",
                    "Use consistent naming conventions",
                    "Tag and categorize findings",
                    "Create relationship maps",
                    "Maintain data integrity",
                    "Implement proper backup procedures",
                    "Consider data retention policies",
                    "Encrypt sensitive findings",
                    "Delete data when no longer needed"
                ]
            },
            
            "legal_compliance": {
                "description": "Staying within legal boundaries",
                "guidelines": [
                    "Know the laws in relevant jurisdictions",
                    "Never access systems without authorization",
                    "Respect terms of service (understand the risks)",
                    "Be aware of GDPR and privacy laws",
                    "Document legal basis for collection",
                    "Consult legal counsel when unsure",
                    "Consider ethical implications",
                    "Avoid collection that could constitute harassment"
                ]
            },
            
            "reporting": {
                "description": "Creating effective OSINT reports",
                "guidelines": [
                    "Start with executive summary",
                    "Clearly state confidence levels",
                    "Include methodology description",
                    "Present findings chronologically or by importance",
                    "Use visualizations effectively",
                    "Include all relevant evidence",
                    "Cite all sources properly",
                    "Acknowledge limitations and gaps",
                    "Provide recommendations when appropriate",
                    "Tailor detail level to audience"
                ]
            },
            
            "continuous_learning": {
                "description": "Maintaining and improving OSINT skills",
                "guidelines": [
                    "Stay current with new tools and techniques",
                    "Participate in CTF competitions",
                    "Join OSINT communities",
                    "Practice regularly with exercises",
                    "Learn from published investigations",
                    "Contribute to the community",
                    "Attend conferences and training",
                    "Read books and follow newsletters",
                    "Experiment with new data sources"
                ]
            }
        }
    
    # =========================================================================
    # TERMINOLOGY
    # =========================================================================
    
    def _initialize_terminology(self):
        """Initialize OSINT terminology glossary."""
        self.terminology = {
            # General Terms
            "Attribution": "The process of identifying the source or origin of information or activity",
            "Breach Data": "Information exposed through security breaches of databases or systems",
            "Collection": "The process of gathering raw information from sources",
            "Correlation": "Linking related pieces of information together",
            "Deep Web": "Parts of the web not indexed by search engines (not necessarily illegal)",
            "Dark Web": "Encrypted network requiring special software to access (Tor, I2P)",
            "Doxing": "Publishing private information about an individual online",
            "Enumeration": "Systematically discovering and listing information",
            "Footprinting": "Gathering information about a target before an operation",
            "Geolocation": "Determining the geographic location associated with data",
            "Indicator": "A piece of information that points to a conclusion",
            "Intelligence": "Information that has been analyzed and has value for decision-making",
            "Metadata": "Data about data (e.g., EXIF data in photos)",
            "OPSEC": "Operational Security - protecting sensitive information",
            "PAI": "Publicly Available Information",
            "Passive Reconnaissance": "Gathering information without directly interacting with target",
            "Pivot": "Using one piece of information to discover related information",
            "Reconnaissance": "Preliminary surveying to gain information",
            "Scraping": "Automatically extracting data from websites",
            "Sock Puppet": "Fake online identity used for investigations",
            "Tradecraft": "Techniques and methods used in intelligence operations",
            "Verification": "Confirming the accuracy and authenticity of information",
            
            # Technical Terms
            "ADS-B": "Automatic Dependent Surveillance-Broadcast (aircraft tracking)",
            "AIS": "Automatic Identification System (ship tracking)",
            "API": "Application Programming Interface",
            "ASN": "Autonomous System Number (network identification)",
            "BGP": "Border Gateway Protocol (internet routing)",
            "CIDR": "Classless Inter-Domain Routing (IP addressing)",
            "CNAME": "Canonical Name record (DNS)",
            "DNS": "Domain Name System",
            "ELA": "Error Level Analysis (image forensics)",
            "EXIF": "Exchangeable Image File Format (image metadata)",
            "FQDN": "Fully Qualified Domain Name",
            "Hash": "Fixed-size output from a hash function (MD5, SHA, etc.)",
            "IoC": "Indicator of Compromise",
            "IP": "Internet Protocol address",
            "MX": "Mail Exchanger (DNS record type)",
            "NS": "Name Server (DNS record type)",
            "PTR": "Pointer record (reverse DNS)",
            "SSL/TLS": "Secure Sockets Layer/Transport Layer Security",
            "WHOIS": "Protocol for querying domain registration info",
            
            # Intelligence Community Terms
            "ACH": "Analysis of Competing Hypotheses",
            "All-Source": "Intelligence from multiple collection disciplines",
            "Assessment": "Analytical judgment about a situation or subject",
            "CI": "Counterintelligence",
            "Clandestine": "Secret or covert (opposite of overt/open source)",
            "Collection Discipline": "Category of intelligence (HUMINT, SIGINT, etc.)",
            "Dissemination": "Distribution of intelligence products",
            "Estimate": "Analytical projection about future events",
            "Fusion": "Combining intelligence from multiple sources",
            "IC": "Intelligence Community",
            "NIE": "National Intelligence Estimate",
            "PIR": "Priority Intelligence Requirements",
            "Raw Intelligence": "Unprocessed information before analysis",
            "Reporting": "Formal intelligence communication",
            "Requirement": "Specific intelligence need",
            "Standing Requirements": "Ongoing intelligence needs",
            "Tearline": "Classification marking separating shareable from classified info"
        }
    
    # =========================================================================
    # SOCK PUPPET GUIDANCE
    # =========================================================================
    
    def _initialize_sock_puppet_guidance(self):
        """Initialize guidance for creating investigation personas."""
        self.sock_puppet_guidance = {
            "overview": """
            A sock puppet is a fake online identity used during investigations to
            avoid attribution and access information. Creating and maintaining
            believable personas requires significant effort and planning.
            """,
            
            "legal_ethical_considerations": [
                "Check legal restrictions in your jurisdiction",
                "Many platforms prohibit fake accounts in ToS",
                "Government use may require special authorization",
                "Consider ethical implications of deception",
                "Never use for harassment or illegal activity",
                "Be aware of fraud implications"
            ],
            
            "persona_creation": {
                "identity_elements": [
                    "Name (gender, ethnicity, age-appropriate)",
                    "Birth date and location",
                    "Current location",
                    "Education history",
                    "Employment history",
                    "Interests and hobbies",
                    "Political/religious views (if needed)",
                    "Relationship status",
                    "Daily schedule and timezone"
                ],
                
                "technical_elements": [
                    "Dedicated email address (aged if possible)",
                    "Phone number (VOIP or prepaid)",
                    "Profile pictures (AI-generated or stock)",
                    "VPN/clean IP address",
                    "Dedicated browser profile",
                    "Consistent device fingerprint",
                    "Separate password manager"
                ],
                
                "profile_picture_options": [
                    "AI-generated faces (thispersondoesnotexist.com)",
                    "Stock photos (check reverse image search)",
                    "Modified images (not recommended)",
                    "No photo (for technical personas)"
                ]
            },
            
            "account_aging": {
                "description": "New accounts are often restricted or flagged",
                "techniques": [
                    "Create accounts well before needed",
                    "Gradually build activity history",
                    "Engage with non-investigation content",
                    "Build connections organically",
                    "Vary activity patterns",
                    "Use accounts for normal activities first"
                ],
                "timeline": "Minimum 1-3 months of aging recommended"
            },
            
            "opsec_for_sock_puppets": [
                "Never mix personal and sock puppet activities",
                "Use dedicated devices or VMs",
                "Different VPN exit nodes than personal use",
                "Maintain consistent persona behavior",
                "Don't friend/follow personal contacts",
                "Avoid behavioral patterns that identify you",
                "Log activities to maintain consistency",
                "Have cover story ready if questioned"
            ],
            
            "platform_specific_tips": {
                "linkedin": [
                    "Premium accounts look more legitimate",
                    "Build connections in target industry slowly",
                    "Join relevant groups",
                    "Engage with industry content"
                ],
                "facebook": [
                    "Harder to maintain - requires more activity",
                    "Join groups slowly over time",
                    "Build friend network organically",
                    "Post regular personal-seeming content"
                ],
                "twitter": [
                    "Easier to maintain than Facebook",
                    "Follow relevant accounts",
                    "Engage with trending topics",
                    "Retweet before tweeting"
                ],
                "discord": [
                    "Join servers gradually",
                    "Participate before investigating",
                    "Build rapport with members"
                ]
            },
            
            "red_flags_to_avoid": [
                "New account with no history",
                "Stock photo profile picture (reverse searchable)",
                "Inconsistent persona details",
                "Only engagement is with target",
                "Technical metadata inconsistencies",
                "Posting at unusual hours for stated timezone",
                "Perfect grammar in supposed non-native speaker",
                "Over-eagerness to connect with target"
            ]
        }
    
    # =========================================================================
    # OPERATIONAL SECURITY
    # =========================================================================
    
    def _initialize_opsec(self):
        """Initialize operational security guidance."""
        self.opsec = {
            "threat_model": {
                "description": "Understanding who might be watching and why",
                "questions": [
                    "Who is your adversary?",
                    "What are they capable of?",
                    "What are you trying to protect?",
                    "What happens if you fail?",
                    "What are acceptable risks?"
                ],
                "common_threats": [
                    "Target becoming aware of investigation",
                    "Personal information exposure",
                    "Legal consequences",
                    "Retaliation from target",
                    "Data breach of collected information"
                ]
            },
            
            "technical_opsec": {
                "network_isolation": [
                    "Use separate network for investigations",
                    "VPN with no-log policy",
                    "Tor for high-risk research",
                    "Avoid home IP for sensitive searches",
                    "Consider dedicated investigation internet connection"
                ],
                
                "device_isolation": [
                    "Dedicated investigation devices",
                    "Virtual machines for containment",
                    "Separate browser profiles",
                    "Clean device fingerprints",
                    "Regular malware scans"
                ],
                
                "browser_opsec": [
                    "Disable JavaScript when possible",
                    "Block trackers and fingerprinting",
                    "Clear cookies regularly",
                    "Use privacy-focused browsers",
                    "Different browsers for different purposes"
                ],
                
                "account_opsec": [
                    "Unique passwords for all accounts",
                    "Separate email for investigations",
                    "Avoid linking accounts",
                    "Enable 2FA where possible",
                    "Be aware of OAuth connections"
                ]
            },
            
            "behavioral_opsec": {
                "search_patterns": [
                    "Vary search engines used",
                    "Don't always search from same location",
                    "Mix investigation queries with normal ones",
                    "Be aware of filter bubbles"
                ],
                
                "social_media_behavior": [
                    "Don't like/react to target content",
                    "Avoid viewing profiles repeatedly",
                    "Be aware of 'viewers' features",
                    "Don't follow investigation-related accounts from personal"
                ],
                
                "communication_opsec": [
                    "Use encrypted communications",
                    "Avoid discussing investigations on unsecured channels",
                    "Be careful about screenshots with metadata",
                    "Verify recipient identity before sharing"
                ]
            },
            
            "physical_opsec": [
                "Secure physical access to investigation devices",
                "Use screen privacy filters in public",
                "Be aware of shoulder surfing",
                "Secure document storage",
                "Proper data destruction procedures"
            ],
            
            "common_mistakes": [
                "Forgetting to use VPN",
                "Logging into personal accounts on investigation browser",
                "Reusing usernames or passwords",
                "Not clearing clipboard after copying sensitive data",
                "Leaving investigation tabs open",
                "Using personal device for investigation",
                "Discussing investigation on personal channels",
                "Not archiving before interacting with content"
            ],
            
            "tools_for_opsec": [
                {
                    "name": "VPNs",
                    "examples": ["Mullvad", "ProtonVPN", "IVPN"],
                    "notes": "Choose no-log providers"
                },
                {
                    "name": "Tor Browser",
                    "use_case": "High-risk research",
                    "limitations": "Slow, some sites block"
                },
                {
                    "name": "Virtual Machines",
                    "examples": ["VirtualBox", "VMware", "Qubes OS"],
                    "use_case": "Isolation"
                },
                {
                    "name": "Tails OS",
                    "use_case": "Amnesic operating system",
                    "notes": "Leaves no trace"
                },
                {
                    "name": "Whonix",
                    "use_case": "Tor-routed OS",
                    "notes": "VM-based anonymity"
                }
            ]
        }
    
    # =========================================================================
    # VERIFICATION METHODS
    # =========================================================================
    
    def _initialize_verification_methods(self):
        """Initialize verification methods."""
        self.verification_methods = {
            "source_verification": {
                "questions_to_ask": [
                    "Who created this content?",
                    "What is their motivation?",
                    "What is their track record?",
                    "Are they in a position to know?",
                    "Is this the original source?"
                ],
                
                "admiralty_system": {
                    "source_reliability": {
                        "A": "Completely Reliable - No doubt about authenticity",
                        "B": "Usually Reliable - Minor doubt",
                        "C": "Fairly Reliable - Doubt exists",
                        "D": "Not Usually Reliable - Significant doubt",
                        "E": "Unreliable - Lacking authenticity",
                        "F": "Cannot Be Judged - No basis for evaluation"
                    },
                    "information_credibility": {
                        "1": "Confirmed - Confirmed by other sources",
                        "2": "Probably True - Likely based on available info",
                        "3": "Possibly True - Not confirmed but reasonable",
                        "4": "Doubtful - Unreliable but not dismissed",
                        "5": "Improbable - Unlikely based on available info",
                        "6": "Cannot Be Judged - No basis for evaluation"
                    }
                }
            },
            
            "content_verification": {
                "images": [
                    "Reverse image search (Google, TinEye, Yandex)",
                    "Check EXIF metadata",
                    "Error Level Analysis",
                    "Look for inconsistent shadows/lighting",
                    "Check for clone stamp artifacts",
                    "Verify location claims through geolocation"
                ],
                
                "videos": [
                    "Extract and analyze keyframes",
                    "Check for audio/video sync issues",
                    "Look for digital artifacts",
                    "Verify through reverse search (InVID)",
                    "Analyze metadata",
                    "Check for deepfake indicators"
                ],
                
                "documents": [
                    "Verify through official sources",
                    "Check formatting consistency",
                    "Analyze metadata",
                    "Look for linguistic anomalies",
                    "Verify referenced information",
                    "Check dates and version history"
                ],
                
                "social_media_posts": [
                    "Check account creation date",
                    "Analyze posting history",
                    "Verify profile picture originality",
                    "Check for bot-like behavior",
                    "Look for coordinated activity",
                    "Verify claimed identity/location"
                ]
            },
            
            "cross_verification": {
                "description": "Using multiple sources to verify information",
                "techniques": [
                    "Find independent sources",
                    "Compare details across sources",
                    "Look for contradictions",
                    "Verify through official records",
                    "Use satellite imagery to verify ground claims",
                    "Cross-reference with known events/timelines"
                ]
            },
            
            "red_flags": {
                "manipulation_indicators": [
                    "Emotional manipulation language",
                    "Too perfect or convenient",
                    "Lack of verifiable details",
                    "Circular sourcing",
                    "Metadata inconsistencies",
                    "Poor quality hiding details"
                ],
                
                "bot_indicators": [
                    "New account with high activity",
                    "Posting at all hours",
                    "Repetitive content patterns",
                    "Generic profile information",
                    "Coordinated posting with other accounts",
                    "Stock photo profile pictures"
                ],
                
                "disinformation_indicators": [
                    "Amplification by suspicious accounts",
                    "Lack of original source",
                    "Contradicts established facts",
                    "Designed to provoke emotional response",
                    "Timing aligned with geopolitical events"
                ]
            }
        }
    
    # =========================================================================
    # REPORTING STANDARDS
    # =========================================================================
    
    def _initialize_reporting_standards(self):
        """Initialize intelligence reporting standards."""
        self.reporting_standards = {
            "report_types": {
                "intelligence_report": {
                    "purpose": "Formal intelligence product",
                    "sections": [
                        "Executive Summary",
                        "Key Judgments",
                        "Background",
                        "Analysis",
                        "Sources and Methods (if appropriate)",
                        "Outlook/Implications",
                        "Annexes/Supporting Evidence"
                    ]
                },
                
                "situation_report": {
                    "purpose": "Current status update",
                    "sections": [
                        "Summary",
                        "Current Situation",
                        "Recent Developments",
                        "Assessment",
                        "Outlook"
                    ]
                },
                
                "target_package": {
                    "purpose": "Comprehensive profile of target",
                    "sections": [
                        "Basic Information",
                        "Background",
                        "Activities",
                        "Associations",
                        "Assessment",
                        "Collection Gaps"
                    ]
                },
                
                "link_chart": {
                    "purpose": "Visual representation of relationships",
                    "elements": [
                        "Entity nodes",
                        "Relationship links",
                        "Annotations",
                        "Legend"
                    ]
                }
            },
            
            "confidence_levels": {
                "high_confidence": "Multiple credible sources; consistent with established facts",
                "moderate_confidence": "Some corroboration; generally consistent",
                "low_confidence": "Limited sources; plausible but not verified",
                "assessment": "Analytical judgment; based on interpretation"
            },
            
            "language_standards": {
                "words_of_estimative_probability": {
                    "almost_certain": ">95%",
                    "highly_likely": "85-95%",
                    "likely": "55-85%",
                    "roughly_even_chance": "45-55%",
                    "unlikely": "15-45%",
                    "highly_unlikely": "5-15%",
                    "remote": "<5%"
                },
                
                "avoid": [
                    "Vague qualifiers without probability",
                    "Absolute statements without evidence",
                    "Passive voice obscuring attribution",
                    "Technical jargon without explanation",
                    "Assumptions presented as facts"
                ]
            },
            
            "citation_standards": [
                "Include source type and reliability rating",
                "Date of access for online sources",
                "Archive links where possible",
                "Full URL or document reference",
                "Page/paragraph numbers for long sources",
                "Screenshot references where appropriate"
            ],
            
            "classification_handling": {
                "note": "For open source/civilian use, adapt as appropriate",
                "markings": [
                    "Source sensitivity",
                    "Distribution restrictions",
                    "Handling caveats",
                    "Releasability"
                ]
            },
            
            "visual_standards": {
                "charts": [
                    "Clear legend and labels",
                    "Consistent color coding",
                    "Date ranges specified",
                    "Source attribution"
                ],
                
                "maps": [
                    "Scale indicator",
                    "North arrow",
                    "Date of imagery",
                    "Source attribution",
                    "Legend for symbols"
                ],
                
                "timelines": [
                    "Consistent date format",
                    "Clear time intervals",
                    "Source attribution for events"
                ]
            }
        }
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def get_tools_by_category(self, category: str) -> List[OSINTTool]:
        """Get all tools in a specific category."""
        all_tools = []
        for tool_list in self.tools.values():
            for tool in tool_list:
                if category.lower() in tool.category.lower():
                    all_tools.append(tool)
        return all_tools
    
    def get_free_tools(self) -> List[OSINTTool]:
        """Get all free tools."""
        free_tools = []
        for tool_list in self.tools.values():
            for tool in tool_list:
                if tool.is_free:
                    free_tools.append(tool)
        return free_tools
    
    def search_tools(self, query: str) -> List[OSINTTool]:
        """Search tools by name or description."""
        results = []
        query_lower = query.lower()
        for tool_list in self.tools.values():
            for tool in tool_list:
                if (query_lower in tool.name.lower() or 
                    query_lower in tool.description.lower()):
                    results.append(tool)
        return results
    
    def get_definition(self, term: str) -> Optional[str]:
        """Get definition of a term."""
        # Check main definitions
        if term.upper() in self.definitions:
            return self.definitions[term.upper()].get("definition")
        
        # Check terminology
        for key, value in self.terminology.items():
            if term.lower() == key.lower():
                return value
        
        return None
    
    def get_methodology(self, name: str) -> Optional[OSINTMethodology]:
        """Get a specific methodology."""
        name_lower = name.lower().replace(" ", "_")
        return self.methodologies.get(name_lower)
    
    def get_legal_frameworks_by_jurisdiction(self, jurisdiction: str) -> List[LegalFramework]:
        """Get legal frameworks for a specific jurisdiction."""
        jurisdiction_lower = jurisdiction.lower()
        
        for key, frameworks in self.legal_frameworks.items():
            if jurisdiction_lower in key.lower():
                return frameworks
        
        return []
    
    def get_search_operators(self, engine: str = "google") -> List[SearchOperator]:
        """Get search operators for a specific engine."""
        return self.search_operators.get(engine.lower(), [])
    
    def get_resources_by_type(self, resource_type: str) -> List[Dict]:
        """Get resources by type (books, courses, etc.)."""
        return self.resources.get(resource_type.lower(), [])
    
    def generate_investigation_checklist(self, investigation_type: str) -> List[str]:
        """Generate a checklist for a specific investigation type."""
        checklists = {
            "person": [
                "â–¡ Full name and variations/aliases",
                "â–¡ Date of birth",
                "â–¡ Current and past addresses",
                "â–¡ Phone numbers",
                "â–¡ Email addresses",
                "â–¡ Social media profiles",
                "â–¡ Professional history (LinkedIn)",
                "â–¡ Education history",
                "â–¡ Associates and family",
                "â–¡ Business affiliations",
                "â–¡ Court records",
                "â–¡ Property records",
                "â–¡ Vehicle registrations",
                "â–¡ Professional licenses",
                "â–¡ News mentions",
                "â–¡ Academic publications",
                "â–¡ Images and photos"
            ],
            
            "company": [
                "â–¡ Official registration details",
                "â–¡ Registered address(es)",
                "â–¡ Directors and officers",
                "â–¡ Shareholders/ownership structure",
                "â–¡ Financial filings",
                "â–¡ Regulatory filings",
                "â–¡ Domain and website analysis",
                "â–¡ Technology stack",
                "â–¡ Employee enumeration (LinkedIn)",
                "â–¡ Social media presence",
                "â–¡ News coverage",
                "â–¡ Court records and lawsuits",
                "â–¡ Patents and trademarks",
                "â–¡ Supplier/customer relationships",
                "â–¡ Industry reputation"
            ],
            
            "domain": [
                "â–¡ WHOIS registration",
                "â–¡ Historical WHOIS",
                "â–¡ DNS records (A, MX, NS, TXT, CNAME)",
                "â–¡ Subdomains",
                "â–¡ SSL/TLS certificates",
                "â–¡ Technology stack",
                "â–¡ Web archive history",
                "â–¡ Associated domains (same registrant)",
                "â–¡ IP address and hosting info",
                "â–¡ Related infrastructure",
                "â–¡ Reputation scores",
                "â–¡ Linked social profiles"
            ],
            
            "social_media": [
                "â–¡ Profile information and bio",
                "â–¡ Account creation date",
                "â–¡ Posting history",
                "â–¡ Connections/friends/followers",
                "â–¡ Group memberships",
                "â–¡ Posted images/videos",
                "â–¡ Check-ins and locations",
                "â–¡ Tagged content",
                "â–¡ Cross-platform presence",
                "â–¡ Activity patterns",
                "â–¡ Archive content before changes"
            ],
            
            "image": [
                "â–¡ Extract EXIF metadata",
                "â–¡ Reverse image search (multiple engines)",
                "â–¡ Geolocation attempt",
                "â–¡ Chronolocation attempt",
                "â–¡ Error Level Analysis",
                "â–¡ Facial recognition search",
                "â–¡ Identify objects/landmarks",
                "â–¡ Check for modifications",
                "â–¡ Find original source",
                "â–¡ Document chain of custody"
            ],
            
            "incident": [
                "â–¡ Define timeline of events",
                "â–¡ Identify all involved parties",
                "â–¡ Collect all available media",
                "â–¡ Geolocate incident location",
                "â–¡ Verify authenticity of evidence",
                "â–¡ Cross-reference with news sources",
                "â–¡ Check satellite imagery",
                "â–¡ Monitor social media for new content",
                "â–¡ Document everything",
                "â–¡ Archive all sources"
            ]
        }
        
        return checklists.get(investigation_type.lower(), [
            "â–¡ Define investigation objectives",
            "â–¡ Identify relevant sources",
            "â–¡ Collect initial data",
            "â–¡ Verify information",
            "â–¡ Analyze and correlate",
            "â–¡ Document findings",
            "â–¡ Report results"
        ])
    
    def export_to_json(self) -> str:
        """Export the knowledge base to JSON format."""
        export_data = {
            "definitions": self.definitions,
            "intelligence_disciplines": self.intelligence_disciplines,
            "terminology": self.terminology,
            "history": self.history,
            "methodologies": {k: {
                "name": v.name,
                "description": v.description,
                "phases": v.phases
            } for k, v in self.methodologies.items()},
            "best_practices": self.best_practices,
            "opsec": self.opsec,
            "verification_methods": self.verification_methods,
            "reporting_standards": self.reporting_standards,
            "ethical_guidelines": self.ethical_guidelines
        }
        return json.dumps(export_data, indent=2)
    
    def print_summary(self) -> str:
        """Print a summary of the knowledge base contents."""
        tool_count = sum(len(tools) for tools in self.tools.values())
        source_count = sum(len(sources) for sources in self.sources.values())
        
        summary = f"""
OSINT Knowledge Base Summary
============================
Definitions: {len(self.definitions)}
Intelligence Disciplines: {len(self.intelligence_disciplines)}
Terminology Entries: {len(self.terminology)}
Historical Timeline Entries: {len(self.history.get('timeline', []))}
Tools: {tool_count}
Data Sources: {source_count}
Methodologies: {len(self.methodologies)}
Analysis Frameworks: {len(self.analysis_frameworks)}
Legal Frameworks: {sum(len(f) for f in self.legal_frameworks.values())}
Search Operator Categories: {len(self.search_operators)}
Technique Categories: {len(self.techniques)}
Resource Categories: {len(self.resources)}
Best Practice Categories: {len(self.best_practices)}
        """
        return summary.strip()


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    # Initialize the knowledge base
    osint_kb = OSINTKnowledgeBase()
    
    # Print summary
    print(osint_kb.print_summary())
    
    # Example: Get definition
    print("\n--- OSINT Definition ---")
    osint_def = osint_kb.definitions.get("OSINT", {})
    print(f"Definition: {osint_def.get('definition', 'Not found')}")
    
    # Example: Get free tools
    print("\n--- Sample Free Tools ---")
    free_tools = osint_kb.get_free_tools()[:5]
    for tool in free_tools:
        print(f"  - {tool.name}: {tool.description[:50]}...")
    
    # Example: Generate checklist
    print("\n--- Person Investigation Checklist ---")
    checklist = osint_kb.generate_investigation_checklist("person")
    for item in checklist[:5]:
        print(f"  {item}")
    print("  ...")
    
    # Example: Get methodology
    print("\n--- Intelligence Cycle ---")
    intel_cycle = osint_kb.methodologies.get("intelligence_cycle")
    if intel_cycle:
        print(f"Phases: {len(intel_cycle.phases)}")
        for phase in intel_cycle.phases[:3]:
            print(f"  - {phase}")
    
    print("\n[Knowledge base initialized successfully]")