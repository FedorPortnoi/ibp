# Sources & Bibliography

## Research conducted: 2026-02-05

This document lists all sources consulted during the ИАС "Буратино" reverse-engineering research.

---

## Primary Sources (Official)

### Буратино Official Resources
1. **Main Website:** https://byratino.info/
   - Version 1.4, operational since 2008
   - Developer: ООО "Санкт-Петербургская школа профессиональных аналитиков"
   - Contact: support@byratino.info, +7 (800) 550-10-73

2. **Partner/Distributor Site:** https://spspa.ru/
   - Educational programs and training
   - Test access registration

3. **System Information Page:** https://spspa.ru/informatsionno-analiticheskaya-sistema-buratino/
   - Pricing: 25,000₽/year
   - Feature overview
   - Use case descriptions

4. **Test Access Portal:** https://spspa.ru/testovyj-dostup-v-ias-buratino/
   - Registration form
   - Access requirements

---

## Technical Documentation

### VK API
1. **Official VK API Documentation:** https://dev.vk.com/
   - API methods reference
   - Authentication flows
   - Rate limits

2. **vk_api Python Library:** https://github.com/python273/vk_api
   - Documentation: https://vk-api.readthedocs.io/
   - PyPI: https://pypi.org/project/vk-api/
   - License: Apache 2.0

3. **VK API Methods (vknet):** https://vknet.github.io/vk/
   - users.get, users.search
   - friends.get, friends.getMutual
   - groups.get, groups.getMembers
   - wall.get
   - photos.getAll

---

## Russian NLP Tools

### Dostoevsky
1. **GitHub Repository:** https://github.com/bureaucratic-labs/dostoevsky
   - Sentiment analysis for Russian language
   - RuSentiment dataset trained
   - ~0.71 F1 score
   - Categories: positive, negative, neutral, speech, skip
   - License: MIT

2. **PyPI:** https://pypi.org/project/dostoevsky/

### Natasha
1. **GitHub Repository:** https://github.com/natasha/natasha
   - Tokenization, NER, morphology, syntax parsing
   - Slovnet models for Russian
   - Production-ready, CPU-optimized
   - License: MIT

2. **PyPI:** https://pypi.org/project/natasha/

### DeepPavlov
1. **GitHub Repository:** https://github.com/deeppavlov/DeepPavlov
   - Open-source NLP framework
   - Russian language support
   - Classification, QA, NER
   - Demo: https://demo.deeppavlov.ai/

2. **Russian Toxicity Classifier:** https://huggingface.co/s-nlp/russian_toxicity_classifier

---

## Graph Visualization

### Cytoscape.js
1. **Official Website:** https://js.cytoscape.org/
   - Graph theory library
   - Multiple layout algorithms
   - Analysis functions (centrality, pathfinding)

### vis.js / vis-network
1. **Official Website:** https://visjs.org/
2. **GitHub Repository:** https://github.com/visjs/vis-network
3. **Documentation:** https://visjs.github.io/vis-network/docs/
4. **Examples:** https://visjs.github.io/vis-network/examples/
5. **NPM:** https://www.npmjs.com/package/vis-network

---

## Competitor Platforms

### Lampyre
1. **Official Website:** https://lampyre.io/
   - 100+ data sources
   - $32/month, $313/year
   - Python API

2. **Blog:** https://lampyre-io.medium.com/
3. **Tutorial:** https://lampyre.io/blog/osint-framework-a-beginners-guide-to-open-source-intelligence/

### IRBIS PRO (EspySys)
1. **Official Website:** https://espysys.com/profiler/
   - OSINT profiler
   - API documentation: https://api-docs.espysys.com

2. **Blog:** https://espysys.com/blog/

### SL Crimewall (Social Links)
1. **Product Page:** https://sociallinks.io/products/sl-crimewall
   - 500+ data sources
   - Enterprise pricing
   - Law enforcement focus

2. **Blog:** https://blog.sociallinks.io/

---

## Open Source VK OSINT Tools

### OSINTvk
1. **GitHub Repository:** https://github.com/AdrianGuretto/OSINTvk
   - VK profile analysis
   - Friends extraction
   - Photo retrieval
   - License: Educational

### Spevktator
1. **GitHub Repository:** https://github.com/MischaU8/spevktator
   - VK community monitoring
   - Sentiment analysis (Dostoevsky)
   - Datasette-based UI
   - Translation support (DeepL)

### VKAnalysis
1. **GitHub Repository:** https://github.com/migalin/VKAnalysis
   - Text analysis (pymorphy2)
   - Photo analysis (OpenNSFW)
   - Social graph analysis
   - License: Apache 2.0

### vk_friends
1. **GitHub Repository:** https://github.com/stleon/vk_friends
   - Friend graph visualization
   - Common friends analysis

### VK OSINT Resource Collections
1. **vk-osint-ru:** https://github.com/OSINT-mindset/vk-osint-ru
2. **vk-osint-en:** https://github.com/rawrdcore/vk-osint-en
3. **netstalking-osint:** https://github.com/netstalking-core/netstalking-osint
4. **awesome-osint:** https://github.com/jivoi/awesome-osint

---

## Technical Articles & Tutorials

### Habr (Russian Tech Community)
1. **VK Profile Analysis Tools:** https://habr.com/ru/articles/834280/
   - 220vk, VKHistoryRobot, FindClone, search4faces

2. **VK OSINT Bots & Services:** https://habr.com/ru/articles/804709/
   - InfoApp, Tool42, 3D Social Graph, Eye of God

3. **VK Friends Analysis with Python:** https://habr.com/ru/articles/263313/
   - NetworkX usage
   - API methods
   - Graph visualization

4. **VK Friends Analysis (Part 1):** https://sohabr.net/habr/post/229793/
5. **VK Friends Analysis (Part 2):** https://habr.com/ru/post/243229/

### Other Technical Resources
1. **VK Social Graph Age Inference:** https://www.pvsm.ru/vkontakte/314443
2. **VK Community Analysis:** https://sohabr.net/habr/post/303864/
3. **Gephi for VK Ego Network:** https://rcsoc.spbu.ru/v-pomoshch-polzovatelyam/433-gephi-analiz-i-vizualizatsiya-ego-seti-na-primere-akkaunta-vkontakte-vk-com.html

---

## VK Analysis Tools & Bots

### Web Services
1. **220vk:** https://v1.220vk.ru/ - Hidden friends, subscription history
2. **search4faces:** https://search4faces.com/ - Reverse image search for VK
3. **FindClone:** https://findclone.ru/ - Face recognition search
4. **photo-map.ru:** Photo location search
5. **topdb.ru:** Historical page copies (VPN required)
6. **bigbookname.com:** VK page archives
7. **YASIV:** https://yasiv.com/vk/ - Friends visualization

### Telegram Bots
1. **@VKHistoryRobot** - Historical profile snapshots
2. **@social_graph_osint_bot** - Friend graph analysis
3. **@friendly_graph_bot** - Connection graphs
4. **@FindNameVk_bot** - Surname change history
5. **@UniversalSearchRobot** - Multi-platform VK search

### VK Applications
1. **InfoApp:** vk.com/app7183114 - Account information
2. **Tool42** - Likes, activity, handshake analysis
3. **3D Social Graph** - Social cluster visualization

---

## Graph Analysis Libraries

### Python
1. **NetworkX:** https://networkx.org/
   - Graph manipulation and analysis
   - Centrality algorithms
   - Community detection

2. **python-louvain:** https://github.com/taynaud/python-louvain
   - Louvain community detection algorithm

### JavaScript Comparison
1. **Graph Library Comparison:** https://npm-compare.com/cytoscape,d3-graphviz,vis-network
2. **Knowledge Graph Libraries:** https://www.getfocal.co/post/top-10-javascript-libraries-for-knowledge-graph-visualization
3. **Graph Visualization Rankings:** https://mingyizhao.medium.com/background-b553fda47349

---

## VK API Python Wrappers

1. **vk_api (python273):** https://github.com/python273/vk_api
   - Most popular, maintained
   - Full API coverage

2. **vk.py:** https://github.com/vadimadr/vk.py
3. **vk (voronind):** https://github.com/voronind/vk
4. **aiovk:** https://github.com/Fahreeve/aiovk - Async support
5. **vkstat:** https://github.com/budnyjj/vkstat - Graph analysis focus

---

## Related Research & Publications

1. **Russian Text Detoxification Methods:** https://arxiv.org/pdf/2105.09052
2. **RuSentiment Dataset:** https://www.kaggle.com/c/sentiment-analysis-in-russian
3. **Social Network Analysis using VK API:** https://sudonull.com/post/96441

---

## VK API JSON Schema
1. **Official Schema Repository:** https://github.com/VKCOM/vk-api-schema

---

## Notes

- Several sources are in Russian and required translation
- Some tools/bots may have limited availability or require VPN
- VK API access may be restricted based on geographic location
- Pricing and features may change; verify current information

---

*Bibliography compiled: 2026-02-05*
*Total sources consulted: 70+*
