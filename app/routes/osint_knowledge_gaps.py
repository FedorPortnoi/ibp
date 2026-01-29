"""
OSINT Knowledge Gaps - Supplementary Resources
===============================================
This file contains OSINT resources, tools, and information that were NOT included
in the original osint_knowledge.py file. These are supplementary resources to fill
the gaps in the original knowledge base.

Author: Claude (Anthropic)
Purpose: Supplementary educational reference for OSINT practitioners
Note: This file should be used in conjunction with osint_knowledge.py
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum, auto


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class OSINTResource:
    """Represents an OSINT resource or tool."""
    name: str
    category: str
    description: str
    url: Optional[str] = None
    is_free: bool = True
    requires_registration: bool = False
    platforms: List[str] = field(default_factory=list)
    use_cases: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class TrainingPlatform:
    """Represents an OSINT training or practice platform."""
    name: str
    description: str
    url: Optional[str] = None
    difficulty_range: str = "Beginner to Advanced"
    is_free: bool = True
    has_solutions: bool = False
    creator: str = ""


@dataclass
class CommunityResource:
    """Represents an OSINT community or forum."""
    name: str
    platform: str
    description: str
    url: Optional[str] = None
    focus_area: str = "General OSINT"


@dataclass
class BlogResource:
    """Represents an OSINT blog or newsletter."""
    name: str
    author: str
    description: str
    url: Optional[str] = None
    update_frequency: str = "Varies"
    content_type: List[str] = field(default_factory=list)


# =============================================================================
# MAIN OSINT GAPS KNOWLEDGE CLASS
# =============================================================================

class OSINTKnowledgeGaps:
    """
    Supplementary OSINT Knowledge Base - Contains resources NOT in osint_knowledge.py
    
    This class fills the gaps in the original knowledge base with:
    - Exercise and CTF platforms
    - Master resource collections (Start.me pages, GitHub repos)
    - AI-powered OSINT tools
    - Facial recognition tools (beyond PimEyes)
    - Cryptocurrency/blockchain investigation tools
    - Vehicle OSINT tools
    - Specialized intelligence categories (ORBINT, VATINT, DNINT)
    - Blogs and newsletters
    - Communities and Discord servers
    - Notable practitioners
    - Training games and gamified learning
    """
    
    def __init__(self):
        """Initialize the OSINT Gaps Knowledge Base."""
        self._initialize_exercise_platforms()
        self._initialize_resource_collections()
        self._initialize_ai_tools()
        self._initialize_facial_recognition_tools()
        self._initialize_cryptocurrency_tools()
        self._initialize_vehicle_osint_tools()
        self._initialize_orbital_intelligence()
        self._initialize_blogs_newsletters()
        self._initialize_communities()
        self._initialize_notable_practitioners()
        self._initialize_training_games()
        self._initialize_github_repositories()
        self._initialize_specialized_platforms()
        self._initialize_additional_techniques()
        self._initialize_additional_search_engines()
        self._initialize_data_breach_tools()
        self._initialize_additional_geolocation_tools()
        self._initialize_additional_definitions()
    
    # =========================================================================
    # EXERCISE AND CTF PLATFORMS
    # =========================================================================
    
    def _initialize_exercise_platforms(self):
        """Initialize OSINT exercise and CTF platforms NOT in original."""
        self.exercise_platforms = {
            "free_exercises": [
                TrainingPlatform(
                    name="Gralhix OSINT Exercises",
                    description="Free OSINT challenges with video walkthroughs by Sofia Santos. "
                               "Covers finding, verifying, and analyzing data. Difficulty ranges "
                               "from beginner (ðŸ¥¸) to expert (ðŸ•µï¸).",
                    url="https://gralhix.com/list-of-osint-exercises/",
                    difficulty_range="Easy to Hard",
                    is_free=True,
                    has_solutions=True,
                    creator="Sofia Santos"
                ),
                TrainingPlatform(
                    name="Hacktoria",
                    description="Free CTF challenges and monthly competitions. Offers realistic "
                               "investigation scenarios with storylines.",
                    url="https://hacktoria.com",
                    difficulty_range="Beginner to Advanced",
                    is_free=True,
                    has_solutions=False
                ),
                TrainingPlatform(
                    name="OSINT4Fun / Advent of OSINT",
                    description="French OSINT community offering challenges including annual "
                               "Advent calendar with daily challenges in December.",
                    url="https://en.osint4fun.eu",
                    difficulty_range="Beginner to Expert",
                    is_free=True,
                    has_solutions=True
                ),
                TrainingPlatform(
                    name="Sourcing.Games",
                    description="30+ gamified OSINT challenges created by recruitment specialist "
                               "Jan Tegze. Focuses on cybersecurity and research skills.",
                    url="https://sourcing.games",
                    difficulty_range="Medium to Hard",
                    is_free=True,
                    has_solutions=False,
                    creator="Jan Tegze"
                ),
                TrainingPlatform(
                    name="Quiztime",
                    description="Daily geolocation challenges posted on Twitter/X. Community-driven "
                               "with participants sharing solutions.",
                    url="https://twitter.com/quaborations",
                    difficulty_range="Easy to Hard",
                    is_free=True,
                    has_solutions=True
                ),
                TrainingPlatform(
                    name="TryHackMe OSINT Rooms",
                    description="Interactive OSINT learning rooms including Sakura, OhSINT, and "
                               "WebOSINT. Guided challenges with hints.",
                    url="https://tryhackme.com",
                    difficulty_range="Beginner to Intermediate",
                    is_free=True,  # Free tier available
                    has_solutions=True
                ),
                TrainingPlatform(
                    name="Cyber Detective CTF",
                    description="Cardiff University CTF with 40 challenges across 3 streams: "
                               "General Knowledge, Life on the Internet, and Investigating Evidence.",
                    url="https://ctf.cybersoc.wales/",
                    difficulty_range="Beginner to Advanced",
                    is_free=True,
                    has_solutions=False
                ),
                TrainingPlatform(
                    name="OSINT Games CTF",
                    description="Capture The Flag learning experience for people of all levels "
                               "who want to challenge themselves with open source research.",
                    url="https://www.osintgames.com/",
                    difficulty_range="Beginner to Advanced",
                    is_free=True,
                    has_solutions=False
                ),
                TrainingPlatform(
                    name="OSINT.IT Challenges",
                    description="Interactive OSINT scenarios and practical exercises for "
                               "skill enhancement.",
                    url="https://osintit.io/challenges",
                    difficulty_range="Beginner to Advanced",
                    is_free=True,
                    has_solutions=False
                ),
                TrainingPlatform(
                    name="Bellingcat Open Source Challenges",
                    description="Periodic challenges created by Bellingcat, often with themed "
                               "sets like 'Back in Time' challenges.",
                    url="https://www.bellingcat.com/",
                    difficulty_range="Intermediate to Advanced",
                    is_free=True,
                    has_solutions=True,
                    creator="Bellingcat"
                )
            ],
            
            "mobile_apps": [
                TrainingPlatform(
                    name="Project VOID",
                    description="Mobile puzzle game with missions centered around investigative work. "
                               "Helps sharpen creative thinking and problem-solving skills.",
                    url="https://apps.apple.com/app/project-void",
                    difficulty_range="Easy to Hard",
                    is_free=True,
                    platforms=["iOS", "Android"]
                )
            ]
        }
    
    # =========================================================================
    # MASTER RESOURCE COLLECTIONS
    # =========================================================================
    
    def _initialize_resource_collections(self):
        """Initialize comprehensive OSINT resource collections NOT in original."""
        self.resource_collections = {
            "start_me_pages": [
                OSINTResource(
                    name="The Ultimate OSINT Collection",
                    category="Resource Collection",
                    description="Massive Start.me page by @hatless1der (Griffin Glynn) with "
                               "the very best OSINT materials, resources, trainings, and tools.",
                    url="https://start.me/p/DPYPMz/the-ultimate-osint-collection",
                    use_cases=["Tool discovery", "Training resources", "Bookmark collection"]
                ),
                OSINTResource(
                    name="Nixintel's OSINT Resource List",
                    category="Resource Collection",
                    description="Excellent bookmark collection covering most OSINT topics and fields. "
                               "Great starting point for beginners and experienced investigators.",
                    url="https://start.me/p/rx6Qj8/nixintel-s-osint-resource-list",
                    use_cases=["General OSINT", "Investigation categories"]
                ),
                OSINTResource(
                    name="OSINT Inception",
                    category="Resource Collection",
                    description="Start.me page by OSINT Tactical with hundreds of tools "
                               "organized by investigation categories.",
                    url="https://start.me/p/Pwy0X4/osint-inception",
                    use_cases=["Tool organization", "Category-based research"]
                ),
                OSINTResource(
                    name="OSINT Tools (Lorand Bodo)",
                    category="Resource Collection",
                    description="Curated list of Internet resources for FOSINT, GEOINT, OSINT, "
                               "SIGINT & SOCMINT. Regularly updated.",
                    url="https://start.me/p/7kxyy2/osint-tools-curated-by-lorand-bodo",
                    use_cases=["Multiple INT disciplines"]
                ),
                OSINTResource(
                    name="Terrorism Radicalization Research Dashboard",
                    category="Resource Collection",
                    description="Specialized Start.me page focused on terrorism and "
                               "radicalization research resources.",
                    url="https://start.me/p/OmExgb/terrorism-radicalisation-research-dashboard",
                    use_cases=["Counter-terrorism", "Extremism research"]
                ),
                OSINTResource(
                    name="Arno Reuser's Collection",
                    category="Resource Collection",
                    description="Academic-focused collection covering search engines to premium "
                               "providers, with special focus on international relations and news.",
                    url="https://start.me/p/1kBrw9/arno-reuser-osint",
                    use_cases=["Academic research", "International relations"]
                )
            ],
            
            "comprehensive_guides": [
                OSINTResource(
                    name="OH SHINT! It's A Blog",
                    category="Comprehensive Guide",
                    description="One of the most detailed OSINT resources available. Covers "
                               "SOCMINT, GEOINT, IMINT, ORBINT, TRADINT, FININT, VATINT, DNINT, "
                               "SIGINT, and more. Includes downloadable PDF and HTML bookmarks.",
                    url="https://ohshint.gitbook.io/oh-shint-its-a-blog/",
                    use_cases=["Complete OSINT reference", "Multiple INT categories", "Techniques"]
                ),
                OSINTResource(
                    name="MetaOSINT",
                    category="Tool Discovery",
                    description="Visual tool discovery interface with over 5,000 OSINT tools and "
                               "resources. Uses citation counts to prioritize most trusted resources.",
                    url="https://metaosint.github.io",
                    use_cases=["Tool discovery", "Resource prioritization"]
                ),
                OSINTResource(
                    name="My OSINT Training Free Resources",
                    category="Training Resources",
                    description="Free tools and projects from My OSINT Training team including "
                               "Obsidian templates, browser extensions, and YOGA (pivoting visualization).",
                    url="https://www.myosint.training/pages/free-resources",
                    use_cases=["Obsidian workflows", "Browser tools", "Pivoting"]
                ),
                OSINTResource(
                    name="OSINT Techniques Website",
                    category="Tool Collection",
                    description="Comprehensive collection of Start.me pages and tool resources "
                               "organized by category.",
                    url="https://www.osinttechniques.com/osint-tools.html",
                    use_cases=["Tool organization", "Category navigation"]
                ),
                OSINTResource(
                    name="s0cm0nkey's Security Reference Guide - OSINT Section",
                    category="Security Guide",
                    description="OSINT section of a comprehensive security reference guide "
                               "with focus on passive reconnaissance and penetration testing.",
                    url="https://s0cm0nkey.gitbook.io/s0cm0nkeys-security-reference-guide/cyber-intelligence/osint",
                    use_cases=["Pentest recon", "Security research"]
                )
            ]
        }
    
    # =========================================================================
    # AI-POWERED OSINT TOOLS
    # =========================================================================
    
    def _initialize_ai_tools(self):
        """Initialize AI-powered OSINT tools NOT in original."""
        self.ai_tools = {
            "geolocation_ai": [
                OSINTResource(
                    name="GeoSpy",
                    category="AI Geolocation",
                    description="AI-powered geolocation tool that analyzes images to predict "
                               "locations. Uses deep learning to identify landmarks, terrain, "
                               "and contextual clues.",
                    url="https://geospy.ai",
                    use_cases=["Photo geolocation", "Location identification"],
                    notes="Game-changer for GEOINT investigations"
                ),
                OSINTResource(
                    name="Picarta",
                    category="AI Geolocation",
                    description="AI-powered tool that predicts where a photo was taken using "
                               "advanced machine learning algorithms.",
                    url="https://picarta.ai",
                    use_cases=["Photo location finder", "GPS coordinate prediction"]
                ),
                OSINTResource(
                    name="ChatGPT/GPT-4 Vision (o3/o4-mini)",
                    category="AI Analysis",
                    description="OpenAI's latest models have strong geolocation capabilities. "
                               "Can analyze images to identify locations by examining terrain, "
                               "architecture, signage, and other visual clues.",
                    url="https://chat.openai.com",
                    is_free=False,
                    use_cases=["Image analysis", "Geolocation reasoning", "Visual research"],
                    notes="Viral 'GeoGuessr' ability emerged in 2025"
                ),
                OSINTResource(
                    name="IntellGPT",
                    category="AI Analysis",
                    description="ChatGPT-based agent designed for intelligence analysts using "
                               "data science methodologies and OSINT techniques. Strong at "
                               "photo geolocation.",
                    use_cases=["Intelligence workflows", "Geolocation", "Data analysis"]
                )
            ],
            
            "image_analysis_ai": [
                OSINTResource(
                    name="Ovis 1.6 Gemma 2-9B",
                    category="AI Image Analysis",
                    description="Open-source AI model excellent for entity recognition in "
                               "large datasets of photos and videos. Good for terrain analysis.",
                    use_cases=["Entity recognition", "Photo/video analysis", "Land texture analysis"]
                ),
                OSINTResource(
                    name="CarNet.AI",
                    category="AI Vehicle Identification",
                    description="AI-driven car model recognition with 97% accuracy. Identifies "
                               "make, model, generation, color from photos. Supports 3100+ models "
                               "since 1995.",
                    url="https://carnet.ai",
                    use_cases=["Vehicle identification", "Car model recognition"]
                ),
                OSINTResource(
                    name="Face Match",
                    category="AI Face Comparison",
                    description="AI tool for comparing two photos to get similarity index. "
                               "Uses deep neural networks for accurate identification.",
                    use_cases=["Face comparison", "Identity verification"]
                ),
                OSINTResource(
                    name="LipReader AI Tools",
                    category="AI Video Analysis",
                    description="Tools that recognize words by lip movements in videos with "
                               "low or no sound. Uses ML for non-verbal data analysis.",
                    use_cases=["Video analysis", "Silent video interpretation"]
                ),
                OSINTResource(
                    name="AI Image Upscalers",
                    category="AI Enhancement",
                    description="Tools that enlarge images 2x, 4x, or 8x without losing quality. "
                               "Examples: Upscale.media, Let's Enhance, Topaz Gigapixel AI.",
                    use_cases=["Image enhancement", "Detail extraction"]
                ),
                OSINTResource(
                    name="GVision",
                    category="AI Image Analysis",
                    description="Reverse image search app using Google Cloud Vision API to "
                               "detect landmarks and web entities from images.",
                    use_cases=["Landmark detection", "Entity identification"]
                ),
                OSINTResource(
                    name="Img2loc",
                    category="AI Geolocation",
                    description="Analyzes images to identify locations, explains reasoning. "
                               "Requires ChatGPT Plus subscription.",
                    use_cases=["Photo geolocation", "Location reasoning"]
                )
            ],
            
            "text_analysis_ai": [
                OSINTResource(
                    name="Skopenow",
                    category="AI People Search",
                    description="AI-powered tool that extracts data from social media and "
                               "public records to compile detailed profiles. Uses ML for "
                               "entity recognition and persona linking.",
                    url="https://skopenow.com",
                    is_free=False,
                    use_cases=["People search", "Identity verification", "Fraud detection"]
                )
            ]
        }
    
    # =========================================================================
    # FACIAL RECOGNITION TOOLS
    # =========================================================================
    
    def _initialize_facial_recognition_tools(self):
        """Initialize facial recognition tools NOT in original (beyond PimEyes)."""
        self.facial_recognition_tools = [
            OSINTResource(
                name="FaceCheck.ID",
                category="Facial Recognition",
                description="Free tool that matches faces across dozens of platforms. Claims "
                           "to scan 560+ million faces online. Can have false positives.",
                url="https://facecheck.id",
                use_cases=["Face matching", "Profile discovery"]
            ),
            OSINTResource(
                name="Search4faces",
                category="Facial Recognition",
                description="Reverse face search engine for VK, OK, TikTok, and Clubhouse. "
                           "Be prepared for high rate of false positive matches.",
                url="https://search4faces.com",
                use_cases=["Russian social media", "Face search"]
            ),
            OSINTResource(
                name="FindClone",
                category="Facial Recognition",
                description="Was excellent for searching Russian Internet before 2022. "
                           "Now has limited access due to sanctions.",
                url="https://findclone.ru",
                use_cases=["Russian internet face search"],
                notes="Access may be limited due to sanctions"
            ),
            OSINTResource(
                name="FaceSeek",
                category="Facial Recognition",
                description="Reverse face search and AI tools for OSINT and identity. "
                           "Offers alternatives to PimEyes and FaceCheck.",
                url="https://www.faceseek.online",
                use_cases=["Face search", "Identity verification"]
            ),
            OSINTResource(
                name="Lenso.ai",
                category="Facial Recognition",
                description="Reverse face search engine with API available. Find face "
                           "matches and URLs where images appear.",
                url="https://lenso.ai",
                use_cases=["Face search", "Image tracking", "API integration"]
            ),
            OSINTResource(
                name="FacePlusPlus",
                category="Facial Recognition",
                description="Business-focused facial recognition with interesting solutions. "
                           "Unclear if available to individual clients.",
                url="https://faceplusplus.com",
                use_cases=["Business verification", "Customer identification"]
            ),
            OSINTResource(
                name="Kairos",
                category="Facial Recognition",
                description="Markets itself as an 'ethical vendor'. More angled towards "
                           "business and customer verification than OSINT in the wild.",
                url="https://kairos.com",
                use_cases=["Business verification", "Customer ID"]
            ),
            OSINTResource(
                name="Espy Face Lookup",
                category="Facial Recognition",
                description="Part of a wider OSINT toolkit (IRBIS). Provides facial "
                           "recognition capabilities for investigations.",
                url="https://espysys.com",
                use_cases=["Face lookup", "Investigation support"]
            ),
            OSINTResource(
                name="DeepFace UI",
                category="Facial Recognition",
                description="Web application for facial recognition and analysis built "
                           "with DeepFace. Open source.",
                url="https://github.com/serengil/deepface",
                use_cases=["Face analysis", "Face matching"]
            ),
            OSINTResource(
                name="Pictriev",
                category="Facial Recognition",
                description="Free face analysis tool. Currently somewhat limited - appears "
                           "to be an unfinished project.",
                url="https://pictriev.com",
                use_cases=["Face analysis"],
                notes="Limited functionality"
            ),
            OSINTResource(
                name="Karma Decay",
                category="Image Search",
                description="Designed specifically for Reddit reverse image search. "
                           "Permanently stuck in beta with limited success.",
                url="https://karmadecay.com",
                use_cases=["Reddit image search"],
                notes="Beta version, limited effectiveness"
            )
        ]
    
    # =========================================================================
    # CRYPTOCURRENCY/BLOCKCHAIN TOOLS
    # =========================================================================
    
    def _initialize_cryptocurrency_tools(self):
        """Initialize cryptocurrency OSINT tools NOT in original."""
        self.cryptocurrency_tools = {
            "blockchain_explorers": [
                OSINTResource(
                    name="Blockchain.com",
                    category="Blockchain Explorer",
                    description="One of the first and most robust Bitcoin explorers. Tracks "
                               "transactions on the blockchain for Bitcoin, Ethereum, BCH.",
                    url="https://blockchain.com/explorer",
                    use_cases=["Transaction tracking", "Wallet analysis"]
                ),
                OSINTResource(
                    name="Etherscan",
                    category="Blockchain Explorer",
                    description="Comprehensive Ethereum blockchain explorer covering "
                               "transactions, blocks, token values, sidechains, and private chains.",
                    url="https://etherscan.io",
                    use_cases=["Ethereum investigation", "Smart contract analysis"]
                ),
                OSINTResource(
                    name="Ethplorer",
                    category="Blockchain Explorer",
                    description="Interactive visualization of Ethereum network. Makes exploring "
                               "transfers more interactive than traditional explorers.",
                    url="https://ethplorer.io",
                    use_cases=["Ethereum visualization", "Transfer exploration"]
                ),
                OSINTResource(
                    name="Blockchair",
                    category="Blockchain Explorer",
                    description="Universal blockchain explorer supporting multiple cryptocurrencies "
                               "including BTC, ETH, LTC, BSC, Cardano, and more.",
                    url="https://blockchair.com",
                    use_cases=["Multi-chain analysis", "Search by address/transaction/embedded text"]
                ),
                OSINTResource(
                    name="OXT.me",
                    category="Blockchain Explorer",
                    description="Bitcoin blockchain analysis tool. Activity tab shows transaction "
                               "patterns that can indicate illicit wallet usage.",
                    url="https://oxt.me",
                    use_cases=["Bitcoin analysis", "Transaction pattern detection"]
                ),
                OSINTResource(
                    name="BTC.com",
                    category="Blockchain Explorer",
                    description="Simple Bitcoin address explorer displaying transaction details "
                               "and wallet history.",
                    url="https://btc.com",
                    use_cases=["Bitcoin address lookup"]
                )
            ],
            
            "analytics_platforms": [
                OSINTResource(
                    name="Chainalysis",
                    category="Blockchain Analytics",
                    description="Industry-leading blockchain analytics and AML solutions. "
                               "Used by law enforcement and financial institutions.",
                    url="https://chainalysis.com",
                    is_free=False,
                    use_cases=["Criminal investigation", "AML compliance", "Risk assessment"]
                ),
                OSINTResource(
                    name="TRM Labs",
                    category="Blockchain Analytics",
                    description="Transaction Monitor and Forensics tools for in-depth "
                               "blockchain transaction analysis.",
                    url="https://trmlabs.com",
                    is_free=False,
                    use_cases=["Transaction monitoring", "Forensic analysis"]
                ),
                OSINTResource(
                    name="GraphSense",
                    category="Blockchain Analytics",
                    description="Open-source cryptoasset analytics platform emphasizing "
                               "data sovereignty, algorithmic transparency, and scalability.",
                    url="https://graphsense.info",
                    use_cases=["Cryptoasset analysis", "Open-source investigation"]
                ),
                OSINTResource(
                    name="Bitquery Coinpath",
                    category="Blockchain Analytics",
                    description="Track illegal funds and monitor real-time money flow from "
                               "addresses and transactions to exchanges.",
                    url="https://bitquery.io",
                    use_cases=["Fund tracking", "Money flow monitoring"]
                ),
                OSINTResource(
                    name="Spyderlab",
                    category="Blockchain Forensics",
                    description="Offers blockchain forensics, crypto AML solutions, and "
                               "OSINT tools for comprehensive investigative analysis.",
                    url="https://spyderlab.org",
                    use_cases=["Blockchain forensics", "AML solutions"]
                ),
                OSINTResource(
                    name="Whale Alert",
                    category="Blockchain Monitoring",
                    description="Alerting system for large cryptocurrency transactions. "
                               "Monitors wallets with significant fund movements.",
                    url="https://whale-alert.io",
                    use_cases=["Transaction alerts", "Whale watching"]
                ),
                OSINTResource(
                    name="Wallet Explorer",
                    category="Blockchain Analysis",
                    description="Helps visualize address relations. Very helpful for "
                               "understanding wallet connections.",
                    url="https://walletexplorer.com",
                    use_cases=["Address visualization", "Wallet relationships"]
                )
            ],
            
            "abuse_tracking": [
                OSINTResource(
                    name="Bitcoin Abuse",
                    category="Abuse Database",
                    description="Specializes in tracking abusive Bitcoin behavior including "
                               "fake investments, exchanges, theft, ransomware.",
                    url="https://bitcoinabuse.com",
                    use_cases=["Scam identification", "Fraud tracking", "Ransomware wallets"]
                ),
                OSINTResource(
                    name="CheckBitcoinAddress",
                    category="Abuse Database",
                    description="Check if a Bitcoin address has been reported for scams or fraud.",
                    url="https://checkbitcoinaddress.com",
                    use_cases=["Address verification", "Scam checking"]
                )
            ],
            
            "specialized_tools": [
                OSINTResource(
                    name="AnuBitux",
                    category="Investigation Environment",
                    description="Free Linux distribution providing a safe environment for "
                               "crypto investigations. Full documentation and tutorials available.",
                    url="https://anubitux.org",
                    use_cases=["Secure crypto environment", "Investigation OS"]
                ),
                OSINTResource(
                    name="ENS Domain Explorer",
                    category="Domain Lookup",
                    description="Search for Ethereum Name Service domains and related information.",
                    url="https://app.ens.domains",
                    use_cases=["ENS lookup", "Ethereum identity"]
                )
            ]
        }
    
    # =========================================================================
    # VEHICLE OSINT TOOLS
    # =========================================================================
    
    def _initialize_vehicle_osint_tools(self):
        """Initialize vehicle OSINT tools NOT in original."""
        self.vehicle_tools = {
            "identification_tools": [
                OSINTResource(
                    name="CarNet",
                    category="Vehicle Identification",
                    description="Upload an image of a vehicle to determine make, model, "
                               "and year. AI-powered recognition.",
                    url="https://carnet.ai",
                    use_cases=["Vehicle identification", "Make/model determination"]
                ),
                OSINTResource(
                    name="WorldLicensePlates.com",
                    category="License Plate Reference",
                    description="Information on license plates from all over the world. "
                               "Helps understand plate formats and country identification.",
                    url="https://worldlicenseplates.com",
                    use_cases=["Plate format research", "Country identification"]
                ),
                OSINTResource(
                    name="PlatesMania",
                    category="License Plate Database",
                    description="Large database of license plate photos from around the world. "
                               "Useful for vehicle spotting and identification.",
                    url="https://platesmania.com",
                    use_cases=["Plate identification", "Vehicle spotting"]
                )
            ],
            
            "history_lookup": [
                OSINTResource(
                    name="VehicleHistory.com",
                    category="Vehicle History",
                    description="Search vehicle history based on VIN and license plate. "
                               "Includes accident reports and ownership history.",
                    url="https://vehiclehistory.com",
                    use_cases=["Vehicle history", "VIN lookup", "Ownership history"]
                ),
                OSINTResource(
                    name="Poctra",
                    category="Salvage Search",
                    description="Search salvage and auctioned cars in the US and EU. "
                               "Useful for finding vehicle history.",
                    url="https://poctra.com",
                    use_cases=["Salvage vehicle search", "Auction history"]
                ),
                OSINTResource(
                    name="CarFax",
                    category="Vehicle History",
                    description="Leading vehicle history report service in the US. "
                               "Comprehensive ownership and accident data.",
                    url="https://carfax.com",
                    is_free=False,
                    use_cases=["Vehicle history reports", "Damage history"]
                ),
                OSINTResource(
                    name="InfoTracer Vehicle Search",
                    category="License Plate Lookup",
                    description="Paid service for license plate lookup. Can sometimes "
                               "retrieve vehicle registrant information.",
                    url="https://infotracer.com",
                    is_free=False,
                    use_cases=["License plate lookup", "Registrant search"]
                )
            ],
            
            "vin_decoders": [
                OSINTResource(
                    name="VIN Decoder (NHTSA)",
                    category="VIN Decoder",
                    description="Official NHTSA VIN decoder. Provides manufacturer details "
                               "and vehicle specifications.",
                    url="https://vpic.nhtsa.dot.gov/decoder/",
                    use_cases=["VIN decoding", "Vehicle specifications"]
                ),
                OSINTResource(
                    name="VINCheck.info",
                    category="VIN Decoder",
                    description="Free VIN lookup tool with basic vehicle information.",
                    url="https://vincheck.info",
                    use_cases=["VIN lookup", "Basic vehicle info"]
                )
            ],
            
            "regional_databases": [
                OSINTResource(
                    name="RDW (Netherlands)",
                    category="Regional Database",
                    description="Dataset of 15 million Netherlands license plates with "
                               "extensive vehicle information.",
                    url="https://ovi.rdw.nl",
                    use_cases=["Dutch vehicle lookup"]
                ),
                OSINTResource(
                    name="Cipher Registry Services Map",
                    category="Regional Database",
                    description="Interactive map of useful online public/registry services "
                               "by location for vehicle and other records.",
                    url="https://cipher.com",
                    use_cases=["Global registry access"]
                )
            ],
            
            "technical_tools": [
                OSINTResource(
                    name="OpenALPR",
                    category="License Plate Recognition",
                    description="Open-source Automatic License Plate Recognition (ALPR) tool. "
                               "Can analyze images/video to extract plate numbers.",
                    url="https://github.com/openalpr/openalpr",
                    use_cases=["ALPR", "Plate extraction from media"]
                ),
                OSINTResource(
                    name="Skiptracer (Vehicle Module)",
                    category="OSINT Tool",
                    description="Python tool with vehicle plate lookup module. Queries "
                               "multiple APIs for free information from US plate numbers.",
                    url="https://github.com/xillwillx/skiptracer",
                    use_cases=["Plate lookup", "VIN discovery"]
                )
            ],
            
            "spotting_sites": [
                OSINTResource(
                    name="Car Spotting Websites",
                    category="Vehicle Spotting",
                    description="Sites where enthusiasts post photos of luxury/sports cars. "
                               "Can be useful for tracking special vehicles.",
                    use_cases=["Luxury car tracking", "Vehicle location"]
                )
            ]
        }
    
    # =========================================================================
    # ORBITAL INTELLIGENCE (ORBINT)
    # =========================================================================
    
    def _initialize_orbital_intelligence(self):
        """Initialize orbital intelligence tools NOT in original."""
        self.orbital_intelligence = {
            "satellite_tracking": [
                OSINTResource(
                    name="Space-Track",
                    category="Satellite Tracking",
                    description="Official US Space Force tool promoting space flight safety. "
                               "Shares space situational awareness with satellite operators worldwide.",
                    url="https://space-track.org",
                    requires_registration=True,
                    use_cases=["Satellite tracking", "Space situational awareness"]
                ),
                OSINTResource(
                    name="N2YO",
                    category="Satellite Tracking",
                    description="Real-time tracking of any satellite orbiting Earth. "
                               "Check satellite passes and set phone alerts.",
                    url="https://n2yo.com",
                    use_cases=["Satellite tracking", "Pass predictions"]
                ),
                OSINTResource(
                    name="Heavens-Above",
                    category="Satellite Tracking",
                    description="Satellite predictions and astronomical data customized "
                               "for your location.",
                    url="https://heavens-above.com",
                    use_cases=["Satellite predictions", "ISS tracking"]
                ),
                OSINTResource(
                    name="SatFlare",
                    category="Satellite Tracking",
                    description="Real-time tracking with 2D and 3D representations. "
                               "Predict passes, flares, and transits.",
                    url="https://satflare.com",
                    use_cases=["2D/3D tracking", "Satellite flares"]
                ),
                OSINTResource(
                    name="LeoLabs LEO Visualization",
                    category="Satellite Tracking",
                    description="Visualization of satellites, debris, and objects in "
                               "low Earth orbit tracked by LeoLabs.",
                    url="https://platform.leolabs.space",
                    use_cases=["LEO visualization", "Debris tracking"]
                ),
                OSINTResource(
                    name="ESRI Satellite Map",
                    category="Satellite Tracking",
                    description="Shows current position and trajectory of 19,300+ satellites. "
                               "Filter by country, type, size, launch date.",
                    url="https://www.esri.com/en-us/satellite-map",
                    use_cases=["Global satellite view", "Filtered searches"]
                ),
                OSINTResource(
                    name="Live Starlink Satellite Map",
                    category="Satellite Tracking",
                    description="Live view of SpaceX Starlink and OneWeb satellite "
                               "constellations.",
                    url="https://satellitemap.space",
                    use_cases=["Starlink tracking", "Constellation monitoring"]
                ),
                OSINTResource(
                    name="Find A Starlink",
                    category="Satellite Tracking",
                    description="Calculate when you can see SpaceX Starlink satellites "
                               "above your location.",
                    url="https://findstarlink.com",
                    use_cases=["Starlink visibility"]
                ),
                OSINTResource(
                    name="ISS Tracker",
                    category="Satellite Tracking",
                    description="Real-time tracking of the International Space Station.",
                    url="https://isstracker.com",
                    use_cases=["ISS location", "Pass predictions"]
                )
            ],
            
            "space_resources": [
                OSINTResource(
                    name="Gunter's Space Page",
                    category="Space Reference",
                    description="Established 1996. One of the leading online resources for "
                               "space missions, satellites, rockets, and exploration.",
                    url="https://space.skyrocket.de",
                    use_cases=["Space history", "Mission data"]
                ),
                OSINTResource(
                    name="Jonathan's Space Home Page",
                    category="Space Reference",
                    description="Extensive data on the history of space exploration.",
                    url="https://planet4589.org",
                    use_cases=["Space history research"]
                ),
                OSINTResource(
                    name="List of Mission Patches",
                    category="Space Reference",
                    description="Images and information for mission patches from early "
                               "space exploration to present day.",
                    use_cases=["Mission identification", "Patch research"]
                ),
                OSINTResource(
                    name="Stellarium",
                    category="Astronomy",
                    description="Virtual online planetarium showing night sky from any location.",
                    url="https://stellarium-web.org",
                    use_cases=["Star identification", "Astronomy verification"]
                ),
                OSINTResource(
                    name="Moon Trek",
                    category="Space Reference",
                    description="NASA exploration portal for the Moon with mapping and data.",
                    url="https://trek.nasa.gov/moon",
                    use_cases=["Lunar research"]
                )
            ]
        }
    
    # =========================================================================
    # BLOGS AND NEWSLETTERS
    # =========================================================================
    
    def _initialize_blogs_newsletters(self):
        """Initialize blogs and newsletters NOT in original."""
        self.blogs_newsletters = [
            BlogResource(
                name="Nixintel",
                author="Nixintel",
                description="Deep geolocation techniques, website OSINT, and technical "
                           "investigative methods. High-quality tutorials.",
                url="https://nixintel.info",
                content_type=["Geolocation", "Website OSINT", "Tutorials"]
            ),
            BlogResource(
                name="Aware Online",
                author="Aware Online Academy (Netherlands)",
                description="Dutch training institute specialized in OSINT and SOCMINT. "
                           "Offers tools pages and training resources.",
                url="https://aware-online.com",
                content_type=["SOCMINT", "Training", "Tools"]
            ),
            BlogResource(
                name="OS2INT",
                author="OS2INT Team",
                description="Technical OSINT tutorials and guides.",
                url="https://os2int.com",
                content_type=["Technical tutorials", "Guides"]
            ),
            BlogResource(
                name="The OSINT Newsletter",
                author="Various",
                description="One of the largest OSINT publications with ~11,000 subscribers. "
                           "Covers tools, techniques, and in-depth guides.",
                url="https://osintnewsletter.com",
                update_frequency="Weekly",
                content_type=["Tools", "Techniques", "Tutorials"]
            ),
            BlogResource(
                name="Digital Investigations Substack",
                author="Craig Silverman",
                description="Investigative journalism and OSINT techniques from journalist "
                           "Craig Silverman. Covers AI integration and verification.",
                url="https://digitalinvestigations.substack.com",
                content_type=["Journalism", "Verification", "AI tools"]
            ),
            BlogResource(
                name="Molfar",
                author="Molfar Team",
                description="Ukrainian OSINT agency blog covering AI tools, vehicle OSINT, "
                           "and investigation techniques.",
                url="https://molfar.com/en/blog",
                content_type=["AI OSINT", "Vehicle OSINT", "Investigation guides"]
            ),
            BlogResource(
                name="OSINT ME",
                author="OSINT ME Team",
                description="Resources for facial recognition, darkweb OSINT, Reddit "
                           "research, and investigator tools.",
                url="https://osintme.com",
                content_type=["Facial recognition", "Dark web", "Tool reviews"]
            ),
            BlogResource(
                name="HackyourMom",
                author="HackyourMom Team",
                description="Ukrainian cybersecurity and OSINT resource with CTF challenges "
                           "and AI integration guides.",
                url="https://hackyourmom.com",
                content_type=["CTF", "AI OSINT", "Cybersecurity"]
            ),
            BlogResource(
                name="Social Links Blog",
                author="Social Links",
                description="OSINT tool vendor blog covering techniques, case studies, "
                           "and industry trends.",
                url="https://blog.sociallinks.io",
                content_type=["Industry trends", "Case studies", "Tools"]
            ),
            BlogResource(
                name="Hackers Arise",
                author="Master OTW",
                description="Cybersecurity and OSINT tutorials including cryptocurrency "
                           "investigations and facial recognition.",
                url="https://hackers-arise.com",
                content_type=["Crypto OSINT", "Facial recognition", "Hacking"]
            ),
            BlogResource(
                name="Secjuice",
                author="Community",
                description="Community-driven security articles. Sinwindie and other "
                           "OSINT practitioners contribute here.",
                url="https://secjuice.com",
                content_type=["Security", "OSINT", "Community articles"]
            ),
            BlogResource(
                name="OSINT Team Blog (Medium)",
                author="OSINT Team",
                description="Medium publication focused on OSINT investigations and techniques.",
                url="https://osintteam.blog",
                content_type=["Investigations", "Techniques", "Case studies"]
            )
        ]
    
    # =========================================================================
    # COMMUNITIES AND DISCORD SERVERS
    # =========================================================================
    
    def _initialize_communities(self):
        """Initialize communities NOT in original."""
        self.communities = [
            CommunityResource(
                name="TOCP Discord (The OSINT Curious Project)",
                platform="Discord",
                description="Active community from the OSINT Curious team. Join via their website.",
                url="https://osintcurio.us",
                focus_area="General OSINT"
            ),
            CommunityResource(
                name="OSINT-FR Discord",
                platform="Discord",
                description="French-speaking OSINT community with active discussions.",
                url="https://osintfr.com",
                focus_area="French OSINT"
            ),
            CommunityResource(
                name="Digital Forensics Discord",
                platform="Discord",
                description="Community focused on digital forensics with OSINT overlap.",
                focus_area="Digital Forensics"
            ),
            CommunityResource(
                name="0x4rk0 Discord",
                platform="Discord",
                description="Security and OSINT community.",
                focus_area="Security/OSINT"
            ),
            CommunityResource(
                name="HackTheBox Discord",
                platform="Discord",
                description="Cybersecurity and CTF community with OSINT-related content.",
                url="https://hackthebox.com",
                focus_area="CTF/Cybersecurity"
            ),
            CommunityResource(
                name="LaptopHackingCoffee Discord",
                platform="Discord",
                description="OSINT and security community.",
                focus_area="OSINT/Security"
            ),
            CommunityResource(
                name="Abstract Security Discord",
                platform="Discord",
                description="Security-focused community with OSINT discussions.",
                focus_area="Security"
            ),
            CommunityResource(
                name="OSINT Jobs Community",
                platform="Various",
                description="Community for finding OSINT communities after Twitter exodus. "
                           "Provides guides for joining relevant communities.",
                focus_area="Community Discovery"
            )
        ]
    
    # =========================================================================
    # NOTABLE PRACTITIONERS
    # =========================================================================
    
    def _initialize_notable_practitioners(self):
        """Initialize notable practitioners NOT in original."""
        self.notable_practitioners = {
            "educators_creators": [
                {
                    "name": "Sofia Santos (Gralhix)",
                    "handle": "@yourauntsarah / gralhix.com",
                    "contribution": "Creator of widely-used OSINT exercises with video walkthroughs. "
                                   "Technical Lead & Senior OSINT Investigator.",
                    "notable_work": "Gralhix OSINT Exercises, Bellingcat challenges, YouTube tutorials"
                },
                {
                    "name": "Sinwindie",
                    "handle": "@sinwindie",
                    "contribution": "Created visual 'attack surface' flowcharts for various OSINT "
                                   "targets. Active contributor to Secjuice.",
                    "notable_work": "OSINT Flowcharts (GitHub) covering Twitter, Snapchat, Email, etc."
                },
                {
                    "name": "Dutch OSINT Guy",
                    "handle": "@dutch_osintguy",
                    "contribution": "OSINT educator and practitioner from Netherlands.",
                    "notable_work": "OSINT tutorials and community contributions"
                },
                {
                    "name": "Cyb_Detective",
                    "handle": "@cyb_detective",
                    "contribution": "Shares OSINT tips, tools, and discoveries. Active on X/Twitter.",
                    "notable_work": "Tool recommendations, technique sharing"
                },
                {
                    "name": "Jake Creps",
                    "handle": "@jakecreps",
                    "contribution": "OSINT trainer and practitioner.",
                    "notable_work": "Training and community education"
                },
                {
                    "name": "Joe Grey (Osintion)",
                    "handle": "osintion.com",
                    "contribution": "OSINT and Social Engineering master. Offers resources, "
                                   "courses, and consultation services.",
                    "notable_work": "Osintion website and training"
                },
                {
                    "name": "Griffin Glynn (hatless1der)",
                    "handle": "@hatless1der",
                    "contribution": "Creator of The Ultimate OSINT Collection Start.me page.",
                    "notable_work": "Ultimate OSINT Collection - one of the most comprehensive "
                                   "OSINT bookmark collections"
                },
                {
                    "name": "Micah Hoffman (WebBreacher)",
                    "handle": "@WebBreacher",
                    "contribution": "Creator of WhatsMyName project and OSINT tools. "
                                   "Part of My OSINT Training team.",
                    "notable_work": "WhatsMyName.app, Obsidian OSINT templates, YOGA pivoting tool"
                },
                {
                    "name": "Sector035",
                    "handle": "@sector035",
                    "contribution": "Author of 'Week in OSINT' newsletter - weekly roundup of "
                                   "OSINT tools and techniques.",
                    "notable_work": "Week in OSINT newsletter"
                },
                {
                    "name": "Lorand Bodo",
                    "handle": "@Lorandbodo",
                    "contribution": "Maintains curated OSINT tools Start.me page. "
                                   "Regularly updated resource list.",
                    "notable_work": "OSINT Tools Start.me page"
                },
                {
                    "name": "OH SHINT!",
                    "handle": "@ohshint_",
                    "contribution": "Licensed private investigator who created one of the most "
                                   "comprehensive OSINT resource guides.",
                    "notable_work": "OH SHINT! Gitbook with extensive OSINT web resources"
                }
            ]
        }
    
    # =========================================================================
    # TRAINING GAMES
    # =========================================================================
    
    def _initialize_training_games(self):
        """Initialize investigation-themed games for training NOT in original."""
        self.training_games = [
            {
                "name": "Return of the Obra Dinn",
                "type": "Video Game",
                "description": "Insurance investigation game where you determine identity and "
                              "cause of death of ship crew members. Uses journals and "
                              "cross-referencing - open-ended investigation style.",
                "skills_trained": ["Pattern recognition", "Cross-referencing", "Deduction"],
                "platform": "PC/Mac/Consoles"
            },
            {
                "name": "Hypnospace Outlaw",
                "type": "Video Game",
                "description": "Browse a fictional 90s-style internet to solve cases. "
                              "Requires examining archives for leads and researching topics.",
                "skills_trained": ["Archive research", "Pattern finding", "Documentation review"],
                "platform": "PC/Mac/Consoles"
            },
            {
                "name": "Sector035's Quiz",
                "type": "Online Quiz",
                "description": "OSINT quiz created by the author of Week in OSINT.",
                "skills_trained": ["General OSINT knowledge", "Tool familiarity"]
            },
            {
                "name": "Her Story",
                "type": "Video Game",
                "description": "Search through a police database of interview clips to "
                              "uncover the truth about a crime.",
                "skills_trained": ["Pattern recognition", "Interview analysis", "Timeline building"],
                "platform": "PC/Mac/Mobile"
            },
            {
                "name": "Telling Lies",
                "type": "Video Game",
                "description": "Sequel to Her Story - search through video conversations "
                              "to piece together a narrative.",
                "skills_trained": ["Video analysis", "Pattern recognition", "Cross-referencing"],
                "platform": "PC/Mac/Consoles"
            },
            {
                "name": "The Painscreek Killings",
                "type": "Video Game",
                "description": "Investigate a murder in an abandoned town. Search for "
                              "clues and piece together what happened.",
                "skills_trained": ["Evidence collection", "Documentation", "Deduction"],
                "platform": "PC"
            }
        ]
    
    # =========================================================================
    # GITHUB REPOSITORIES
    # =========================================================================
    
    def _initialize_github_repositories(self):
        """Initialize GitHub repositories NOT in original."""
        self.github_repositories = [
            OSINTResource(
                name="Awesome-OSINT (jivoi)",
                category="Resource Collection",
                description="Massive curated list of OSINT tools and resources. One of the "
                           "most comprehensive GitHub OSINT collections.",
                url="https://github.com/jivoi/awesome-osint",
                use_cases=["Tool discovery", "Comprehensive reference"]
            ),
            OSINTResource(
                name="The-Osint-Toolbox/Image-Research-OSINT",
                category="Image Research",
                description="Learn how to research images - tools, techniques & tradecraft. "
                           "Covers reverse image search, AI geolocation, and more.",
                url="https://github.com/The-Osint-Toolbox/Image-Research-OSINT",
                use_cases=["Image research", "Geolocation", "Reverse image search"]
            ),
            OSINTResource(
                name="awesome_osint_blockchain_analysis",
                category="Cryptocurrency",
                description="Collection of tools and resources for OSINT investigations "
                           "on cryptocurrencies and blockchain analysis.",
                url="https://github.com/aaarghhh/awesome_osint_blockchain_analysis",
                use_cases=["Crypto investigation", "Blockchain analysis"]
            ),
            OSINTResource(
                name="Vehicle-OSINT-Collection",
                category="Vehicle OSINT",
                description="Comprehensive list of tools for finding vehicle information. "
                           "VIN decoders, plate lookups, and regional databases.",
                url="https://github.com/TheBurnsy/Vehicle-OSINT-Collection",
                use_cases=["Vehicle investigation", "License plate lookup"]
            ),
            OSINTResource(
                name="osint-ai-guide (atlas-bear)",
                category="AI Integration",
                description="Comprehensive guide to AI applications in OSINT workflows. "
                           "Covers security considerations and tool comparisons.",
                url="https://github.com/atlas-bear/osint-ai-guide",
                use_cases=["AI integration", "Security considerations"]
            ),
            OSINTResource(
                name="blockchain-osint (codeluu)",
                category="Cryptocurrency",
                description="Tools and resources for cryptocurrency OSINT investigations.",
                url="https://github.com/codeluu/blockchain-osint",
                use_cases=["Crypto investigation"]
            ),
            OSINTResource(
                name="Sinwindie OSINT Flowcharts",
                category="Methodology",
                description="Visual 'attack surface' diagrams for various OSINT targets. "
                           "Covers Twitter, Snapchat, Websites, Email, and more pivot points.",
                url="https://github.com/sinwindie/OSINT",
                use_cases=["Methodology", "Pivot points", "Attack surface visualization"]
            ),
            OSINTResource(
                name="OhShINT Gitbook Repository",
                category="Resource Collection",
                description="GitHub repository for OH SHINT! blog. Contains downloadable "
                           "HTML bookmarks and PDF resources.",
                url="https://github.com/OhShINT/ohshint.gitbook.io",
                use_cases=["Bookmark import", "Comprehensive resources"]
            ),
            OSINTResource(
                name="osintxcarplate",
                category="Vehicle OSINT",
                description="Obtain vehicle profile from Mexican car plates including "
                           "carjacking reports. Part of investigation toolkit.",
                url="https://github.com/e-m3din4/osintxcarplate",
                use_cases=["Mexican vehicle lookup"]
            )
        ]
    
    # =========================================================================
    # SPECIALIZED PLATFORMS
    # =========================================================================
    
    def _initialize_specialized_platforms(self):
        """Initialize specialized OSINT platforms NOT in original."""
        self.specialized_platforms = {
            "enterprise_platforms": [
                OSINTResource(
                    name="Social Links (SL Crimewall)",
                    category="Enterprise Platform",
                    description="Full-circle OSINT platform using ML-powered features for "
                               "investigations. Supports identity intelligence and facial recognition.",
                    url="https://sociallinks.io",
                    is_free=False,
                    use_cases=["Enterprise investigation", "Identity intelligence"]
                ),
                OSINTResource(
                    name="IRBIS",
                    category="Enterprise Platform",
                    description="OSINT platform with face search, username enumeration, and "
                               "multiple investigation modules. API available.",
                    url="https://irbis.espysys.com",
                    is_free=False,
                    use_cases=["Face search", "Username enumeration", "API integration"]
                ),
                OSINTResource(
                    name="Talkwalker / Hootsuite OSINT",
                    category="Social Monitoring",
                    description="Scans 150M+ websites and 30+ social networks in 187 languages. "
                               "AI sentiment analysis and visual intelligence capabilities.",
                    url="https://talkwalker.com",
                    is_free=False,
                    use_cases=["Social monitoring", "Brand intelligence", "Trend detection"]
                ),
                OSINTResource(
                    name="Babel Street",
                    category="Enterprise Platform",
                    description="Analyzes content across 200+ languages. Uses AI to find "
                               "connections in multilingual data from social media and deep web.",
                    url="https://babelstreet.com",
                    is_free=False,
                    use_cases=["Multilingual analysis", "Threat intelligence"]
                ),
                OSINTResource(
                    name="OSINT Combine NexusXplore",
                    category="Enterprise Platform",
                    description="All-in-one, investigation-agnostic software platform from "
                               "OSINT Combine. Supports OSINT collection and analytical uplift.",
                    url="https://osintcombine.com",
                    is_free=False,
                    use_cases=["Investigation management", "Analysis platform"]
                )
            ],
            
            "socmint_specific": [
                OSINTResource(
                    name="SMAT (Social Media Analysis Toolkit)",
                    category="Social Media Analysis",
                    description="Analyze and visualize trends on Reddit, Gab, Parler, 4chan, "
                               "8kun, Telegram, Gettr and more.",
                    url="https://smat-app.com",
                    use_cases=["Alternative platform analysis", "Trend visualization"]
                ),
                OSINTResource(
                    name="HuntIntel",
                    category="Location-Based Social",
                    description="Find Instagram places, Facebook places, VK photos, Snapchat "
                               "stories, and Tweets based on location.",
                    url="https://huntintel.io",
                    requires_registration=True,
                    use_cases=["Location-based social media search"]
                ),
                OSINTResource(
                    name="Shreateh Social Media Tools",
                    category="Multi-Platform",
                    description="Large collection of SOCMINT tools for Facebook, YouTube, "
                               "Instagram, Twitter, and TikTok.",
                    url="https://khalil-shreateh.com/tools",
                    use_cases=["Multi-platform SOCMINT"]
                ),
                OSINTResource(
                    name="EffectGroup",
                    category="People Search",
                    description="Search by username, email, real name, or phone. Searches "
                               "social media, data breaches, documents. Paid after first search.",
                    url="https://effectgroup.io",
                    is_free=False,
                    use_cases=["People search", "Dossier building"]
                ),
                OSINTResource(
                    name="Synapsint",
                    category="Unified OSINT",
                    description="Unified OSINT research tool. Search domain, IP, ASN, SSL certs, "
                               "Google accounts, email, phone, Twitter, Bitcoin address.",
                    url="https://synapsint.com",
                    use_cases=["Multi-source search", "Quick reconnaissance"]
                )
            ],
            
            "street_art": [
                OSINTResource(
                    name="Street Art Cities",
                    category="Geolocation Resource",
                    description="Online map for finding street art worldwide. Useful for "
                               "geolocating images containing graffiti or murals.",
                    url="https://streetartcities.com",
                    use_cases=["Street art geolocation", "Artist identification"]
                )
            ]
        }
    
    # =========================================================================
    # ADDITIONAL TECHNIQUES
    # =========================================================================
    
    def _initialize_additional_techniques(self):
        """Initialize additional techniques NOT covered in original."""
        self.additional_techniques = {
            "gaming_osint": {
                "description": "OSINT on gaming platforms - an emerging area with 3.2 billion "
                              "players worldwide. Used for extremist recruitment detection, "
                              "financial fraud, and money laundering investigations.",
                "platforms": ["Steam", "Discord", "Xbox Live", "PlayStation Network", 
                             "Epic Games", "Battle.net", "Twitch"],
                "techniques": [
                    "Username correlation across platforms",
                    "Friend list analysis",
                    "In-game chat monitoring",
                    "Achievement/trophy timeline analysis",
                    "Virtual item transaction tracking"
                ],
                "tools": [
                    "Steam ID Finder",
                    "SteamDB",
                    "Xbox Gamertag lookup tools",
                    "PSN Profile trackers"
                ]
            },
            
            "mobile_app_osint": {
                "description": "Emerging area as mobile apps become part of digital footprints. "
                              "Apps like Clubhouse, Strava, Spotify offer untapped data.",
                "platforms": ["Strava", "Clubhouse", "Spotify", "Fitness apps", 
                             "Dating apps", "Ride-sharing apps"],
                "techniques": [
                    "Activity pattern analysis",
                    "Location history from fitness apps",
                    "Social graph from audio apps",
                    "Music preference analysis",
                    "Route and location data from Strava"
                ],
                "privacy_concerns": [
                    "Strava heatmaps revealing military base locations",
                    "Dating app location disclosure",
                    "Fitness route predictability"
                ]
            },
            
            "mac_address_bluetooth_osint": {
                "description": "Modern vehicles and devices have unique identifiers (MAC addresses, "
                              "BSSIDs, Bluetooth IDs) that can be used for tracking.",
                "data_sources": ["Wigle.net", "Bluetooth scanners", "WiFi probe requests"],
                "techniques": [
                    "Vehicle multimedia system MAC address tracking",
                    "Bluetooth device pairing history",
                    "WiFi SSID from vehicle hotspots"
                ]
            },
            
            "favicon_osint": {
                "description": "Using favicon hashes to discover related infrastructure. "
                              "Hash the favicon and search in IoT search engines.",
                "tools": ["FaviconHash browser extension", "Shodan", "Censys"],
                "use_cases": [
                    "Find real IP behind Cloudflare",
                    "Discover related infrastructure",
                    "Identify custom applications"
                ]
            },
            
            "api_reconnaissance": {
                "description": "Finding exposed APIs and data through platforms like Postman.",
                "tools": ["Porch Pirate", "Postman public workspaces", "API documentation search"],
                "use_cases": [
                    "Find exposed credentials",
                    "Discover undocumented endpoints",
                    "Map application architecture"
                ]
            }
        }
    
    # =========================================================================
    # ADDITIONAL SEARCH ENGINES
    # =========================================================================
    
    def _initialize_additional_search_engines(self):
        """Initialize search engines NOT in original."""
        self.additional_search_engines = {
            "privacy_focused": [
                OSINTResource(
                    name="Swisscows",
                    category="Privacy Search",
                    description="Data-secure Google alternative from Switzerland. "
                               "Does not monitor or save any data.",
                    url="https://swisscows.com",
                    use_cases=["Anonymous searching", "Privacy-focused research"]
                ),
                OSINTResource(
                    name="Startpage",
                    category="Privacy Search",
                    description="Dutch search engine highlighting privacy. Uses Google "
                               "results without tracking.",
                    url="https://startpage.com",
                    use_cases=["Anonymous Google results"]
                ),
                OSINTResource(
                    name="Gigablast",
                    category="Privacy Search",
                    description="Cryptographically-protected private search engine.",
                    url="https://gigablast.com",
                    use_cases=["Privacy-focused search"]
                )
            ],
            
            "file_search": [
                OSINTResource(
                    name="UVRX",
                    category="File Search",
                    description="Most comprehensive online file storage search engine.",
                    url="https://uvrx.com",
                    use_cases=["Cloud storage search", "File discovery"]
                ),
                OSINTResource(
                    name="FilePursuit",
                    category="File Search",
                    description="Search for files across various hosting platforms.",
                    url="https://filepursuit.com",
                    use_cases=["File search", "Document discovery"]
                )
            ],
            
            "regional_search": [
                OSINTResource(
                    name="Parseek (Iran)",
                    category="Regional Search",
                    description="Iranian search engine for news articles with category filtering.",
                    url="https://parseek.com",
                    use_cases=["Iranian content"]
                ),
                OSINTResource(
                    name="Tazaa (India)",
                    category="Regional Search",
                    description="Indian search engine using Google custom search.",
                    url="https://tazaa.com",
                    use_cases=["Indian content"]
                ),
                OSINTResource(
                    name="CyprusGate",
                    category="Regional Directory",
                    description="Comprehensive directory of Cyprus websites.",
                    url="https://cyprusgate.com",
                    use_cases=["Cyprus web content"]
                )
            ]
        }
    
    # =========================================================================
    # DATA BREACH TOOLS
    # =========================================================================
    
    def _initialize_data_breach_tools(self):
        """Initialize data breach tools NOT in original."""
        self.data_breach_tools = [
            OSINTResource(
                name="Bloopbase Searchable Data Dumps",
                category="Breach Search",
                description="Collection of searchable data dumps.",
                use_cases=["Breach searching"]
            ),
            OSINTResource(
                name="Information Operations Archive",
                category="Influence Operations",
                description="Archive of publicly available data from known online influence "
                           "operations. 10M+ messages from Russian and Iranian operations "
                           "on Twitter and Reddit.",
                url="https://io-archive.org",
                use_cases=["Influence operation research", "State-sponsored activity"]
            ),
            OSINTResource(
                name="Snusbase",
                category="Breach Search",
                description="Database breach search engine. Paid service.",
                url="https://snusbase.com",
                is_free=False,
                use_cases=["Credential search", "Breach lookup"]
            ),
            OSINTResource(
                name="LeakCheck",
                category="Breach Search",
                description="Check if credentials have been leaked. Paid service.",
                url="https://leakcheck.io",
                is_free=False,
                use_cases=["Credential verification"]
            )
        ]
    
    # =========================================================================
    # ADDITIONAL GEOLOCATION TOOLS
    # =========================================================================
    
    def _initialize_additional_geolocation_tools(self):
        """Initialize geolocation tools NOT in original."""
        self.additional_geolocation_tools = [
            OSINTResource(
                name="Mapillary",
                category="Street Imagery",
                description="Access street-level images and map data from around the world. "
                           "Crowdsourced street photography.",
                url="https://mapillary.com",
                use_cases=["Street-level imagery", "Alternative to Google Street View"]
            ),
            OSINTResource(
                name="KartaView",
                category="Street Imagery",
                description="Collect and access street-level imagery from around the world. "
                           "OpenStreetMap partner.",
                url="https://kartaview.org",
                use_cases=["Street imagery", "OpenStreetMap integration"]
            ),
            OSINTResource(
                name="GeoHack Tools",
                category="Location Tools",
                description="Add location coordinates and receive a list of OSINT resources "
                           "for that area including satellite imagery, photos, weather, etc.",
                url="https://geohack.toolforge.org",
                use_cases=["Location-based resource discovery"]
            ),
            OSINTResource(
                name="NOAA Digital Coast",
                category="Coastal Intelligence",
                description="Data, tools, and training for coastal resource management. "
                           "Climate adaptation to ocean planning.",
                url="https://coast.noaa.gov/digitalcoast/",
                use_cases=["Coastal investigation", "Environmental OSINT"]
            ),
            OSINTResource(
                name="Terria Australia",
                category="Regional Imagery",
                description="Australian geospatial investigations tool with incredibly "
                           "high-res imagery.",
                url="https://nationalmap.gov.au",
                use_cases=["Australian GEOINT"]
            ),
            OSINTResource(
                name="Peakbagger",
                category="Mountain/Peak Data",
                description="Database of mountain peaks and hiking information.",
                url="https://peakbagger.com",
                use_cases=["Mountain identification", "Peak geolocation"]
            ),
            OSINTResource(
                name="Photo Location Finder",
                category="AI Geolocation",
                description="Uses AI image geolocation and reverse photo location search "
                           "to identify GPS coordinates from pictures.",
                url="https://www.picarta.ai",
                use_cases=["Photo geolocation"]
            )
        ]
    
    # =========================================================================
    # ADDITIONAL DEFINITIONS
    # =========================================================================
    
    def _initialize_additional_definitions(self):
        """Initialize additional definitions NOT in original."""
        self.additional_definitions = {
            "ORBINT": {
                "full_name": "Orbital Intelligence",
                "definition": "Intelligence gathered from tracking and analyzing satellites, "
                             "space debris, and other objects in Earth's orbit. Includes "
                             "satellite position data, launch information, and space situational awareness."
            },
            "VATINT": {
                "full_name": "Vehicle and Transportation Intelligence",
                "definition": "Intelligence derived from vehicle tracking, license plate analysis, "
                             "VIN lookups, and transportation infrastructure monitoring. Includes "
                             "cars, trucks, boats, aircraft, and rail."
            },
            "DNINT": {
                "full_name": "Digital Network Intelligence",
                "definition": "Intelligence focused on digital infrastructure including domains, "
                             "IP addresses, ASNs, SSL certificates, and network architecture."
            },
            "CORPINT": {
                "full_name": "Corporate Intelligence",
                "definition": "Intelligence gathered about businesses, corporate structures, "
                             "beneficial ownership, financial filings, and business relationships."
            },
            "ALPR": {
                "full_name": "Automatic License Plate Recognition",
                "definition": "Technology that uses optical character recognition to automatically "
                             "read vehicle license plates from images or video."
            },
            "ENS": {
                "full_name": "Ethereum Name Service",
                "definition": "Decentralized naming system on Ethereum blockchain. Maps human-readable "
                             "names to cryptocurrency addresses and other identifiers."
            },
            "KYC": {
                "full_name": "Know Your Customer",
                "definition": "Process by which businesses verify customer identity. In crypto "
                             "investigations, KYC data from exchanges can link wallet addresses "
                             "to real identities."
            },
            "Coinjoin": {
                "definition": "Method to combine multiple Bitcoin payments into a single transaction "
                             "to make associating spenders with recipients difficult."
            },
            "Tumbler": {
                "definition": "Service that attempts to anonymize Bitcoin by mixing them with "
                             "other Bitcoins using different patterns to obscure the money trail."
            },
            "Chain Hopping": {
                "definition": "The act of exchanging cryptocurrency from one type to another "
                             "to obfuscate the trail of funds."
            }
        }
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def get_all_exercise_platforms(self) -> List[TrainingPlatform]:
        """Get all exercise and CTF platforms."""
        all_platforms = []
        for category in self.exercise_platforms.values():
            all_platforms.extend(category)
        return all_platforms
    
    def get_free_resources(self) -> List[OSINTResource]:
        """Get all free resources from the gaps knowledge base."""
        free_resources = []
        
        # Collect from all categories
        for collection_type in [self.resource_collections, self.ai_tools, 
                                self.cryptocurrency_tools, self.vehicle_tools,
                                self.orbital_intelligence, self.additional_search_engines,
                                self.specialized_platforms]:
            if isinstance(collection_type, dict):
                for category in collection_type.values():
                    if isinstance(category, list):
                        for item in category:
                            if isinstance(item, OSINTResource) and item.is_free:
                                free_resources.append(item)
        
        # Add facial recognition tools
        for tool in self.facial_recognition_tools:
            if tool.is_free:
                free_resources.append(tool)
        
        # Add GitHub repos
        for repo in self.github_repositories:
            if repo.is_free:
                free_resources.append(repo)
        
        return free_resources
    
    def get_resources_by_category(self, category: str) -> List[OSINTResource]:
        """Get all resources matching a category."""
        results = []
        category_lower = category.lower()
        
        # Search all resource collections
        for collection in [self.facial_recognition_tools, self.github_repositories,
                          self.data_breach_tools, self.additional_geolocation_tools]:
            for item in collection:
                if category_lower in item.category.lower():
                    results.append(item)
        
        return results
    
    def print_summary(self) -> str:
        """Print a summary of the gaps knowledge base contents."""
        exercise_count = sum(len(platforms) for platforms in self.exercise_platforms.values())
        resource_collection_count = sum(len(items) for items in self.resource_collections.values())
        ai_tool_count = sum(len(tools) for tools in self.ai_tools.values())
        crypto_tool_count = sum(len(tools) for tools in self.cryptocurrency_tools.values())
        vehicle_tool_count = sum(len(tools) for tools in self.vehicle_tools.values())
        orbital_count = sum(len(items) for items in self.orbital_intelligence.values())
        
        summary = f"""
OSINT Knowledge Gaps Summary
============================
Exercise/CTF Platforms: {exercise_count}
Master Resource Collections: {resource_collection_count}
AI-Powered Tools: {ai_tool_count}
Facial Recognition Tools: {len(self.facial_recognition_tools)}
Cryptocurrency Tools: {crypto_tool_count}
Vehicle OSINT Tools: {vehicle_tool_count}
Orbital Intelligence Tools: {orbital_count}
Blogs/Newsletters: {len(self.blogs_newsletters)}
Communities: {len(self.communities)}
Notable Practitioners: {len(self.notable_practitioners.get('educators_creators', []))}
Training Games: {len(self.training_games)}
GitHub Repositories: {len(self.github_repositories)}
Additional Definitions: {len(self.additional_definitions)}
Additional Search Engines: {sum(len(e) for e in self.additional_search_engines.values())}
Data Breach Tools: {len(self.data_breach_tools)}
Additional Geolocation Tools: {len(self.additional_geolocation_tools)}
        """
        return summary.strip()


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    # Initialize the gaps knowledge base
    osint_gaps = OSINTKnowledgeGaps()
    
    # Print summary
    print(osint_gaps.print_summary())
    
    # Example: Get exercise platforms
    print("\n--- Sample Exercise Platforms ---")
    exercises = osint_gaps.get_all_exercise_platforms()[:3]
    for ex in exercises:
        print(f"  - {ex.name}: {ex.description[:60]}...")
    
    # Example: Get facial recognition tools
    print("\n--- Sample Facial Recognition Tools ---")
    for tool in osint_gaps.facial_recognition_tools[:3]:
        print(f"  - {tool.name}: {tool.description[:60]}...")
    
    # Example: Get notable practitioners
    print("\n--- Notable Practitioners ---")
    for practitioner in osint_gaps.notable_practitioners.get('educators_creators', [])[:3]:
        print(f"  - {practitioner['name']}: {practitioner['contribution'][:50]}...")
    
    print("\n[Gaps knowledge base initialized successfully]")
    print("\nNOTE: This file supplements osint_knowledge.py with resources that were missing.")