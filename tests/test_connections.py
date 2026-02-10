"""
Tests for Cross-Investigation Connection Intelligence
======================================================
Validation tests written by connection-tester to verify the
ConnectionIntelligence engine and API routes.

Covers:
1. Scoring algorithm with known overlaps
2. Single investigation edge case
3. Empty friends lists edge case
4. Duplicate entries deduplication
5. Integration test with full DB data
6. API test - valid payload
7. API test - invalid payload
8. Graph data vis.js format validation
9. Zero overlap test
"""

import json
import os
import uuid
import pytest

# Disable auth for tests
os.environ.pop('IBP_PASSWORD', None)
os.environ.pop('IBP_PASSWORD_HASH', None)

from app import create_app, db
from app.models import Investigation, SocialProfile, Friend
from app.services.connection_intelligence import ConnectionIntelligence


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def app():
    """Create application for testing with in-memory DB."""
    os.environ.pop('IBP_PASSWORD', None)
    os.environ.pop('IBP_PASSWORD_HASH', None)
    application = create_app('testing')
    application.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    application.config['TESTING'] = True
    application.config['SECRET_KEY'] = 'test-secret-connections'

    with application.app_context():
        db.drop_all()
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def engine(app):
    """ConnectionIntelligence engine instance within app context."""
    return ConnectionIntelligence()


# ============================================================
# Helpers
# ============================================================

def create_investigation(input_name, status='phase_2_complete', emails=None,
                         phones=None, groups=None):
    """Create and persist an Investigation record."""
    inv = Investigation(
        id=str(uuid.uuid4()),
        input_name=input_name,
        status=status,
    )
    if emails is not None:
        inv.discovered_emails = emails
    if phones is not None:
        inv.discovered_phones = phones
    if groups is not None:
        inv.group_memberships = groups
    db.session.add(inv)
    return inv


def create_profile(investigation_id, platform_id, first_name, last_name,
                   is_confirmed=True, city=None, age=None, career=None):
    """Create and persist a SocialProfile record."""
    profile = SocialProfile(
        investigation_id=investigation_id,
        platform='vk',
        platform_id=platform_id,
        first_name=first_name,
        last_name=last_name,
        display_name=f"{first_name} {last_name}",
        is_confirmed=is_confirmed,
        city=city,
        age=age,
    )
    if career is not None:
        profile.career = career
    db.session.add(profile)
    return profile


def create_friend(investigation_id, platform_id, first_name, last_name,
                  parent_profile_id=None):
    """Create and persist a Friend record."""
    friend = Friend(
        investigation_id=investigation_id,
        parent_profile_id=parent_profile_id,
        platform='vk',
        platform_id=platform_id,
        first_name=first_name,
        last_name=last_name,
    )
    db.session.add(friend)
    return friend


# ============================================================
# Test 1: Scoring Algorithm — Known Overlaps
# ============================================================

class TestScoringAlgorithm:
    """Verify correct connection scores with known overlapping data."""

    def test_known_overlaps_3_mutual_friends_same_employer(self, app, engine):
        """
        Two investigations with 3 mutual friends and same employer should
        produce a predictable composite score.

        Expected:
        - mutual_friend: weight 1.0 * min(3, 5) = 3.0
        - same_employer: weight 0.8 * 1 = 0.8
        - Total: 3.8
        """
        inv_a = create_investigation('Алексей Смирнов')
        inv_b = create_investigation('Борис Козлов')
        db.session.flush()

        # Confirmed profiles with same employer
        prof_a = create_profile(inv_a.id, '100', 'Алексей', 'Смирнов',
                                career=[{'company': 'Сбербанк'}])
        prof_b = create_profile(inv_b.id, '200', 'Борис', 'Козлов',
                                career=[{'company': 'Сбербанк'}])
        db.session.flush()

        # 3 mutual friends
        for i in range(3):
            pid = str(500 + i)
            create_friend(inv_a.id, pid, f'Друг{i}', 'Общий', parent_profile_id=prof_a.id)
            create_friend(inv_b.id, pid, f'Друг{i}', 'Общий', parent_profile_id=prof_b.id)

        # 2 unique friends each (should not affect score)
        create_friend(inv_a.id, '800', 'Уникальный', 'А')
        create_friend(inv_a.id, '801', 'Уникальный2', 'А')
        create_friend(inv_b.id, '900', 'Уникальный', 'Б')
        create_friend(inv_b.id, '901', 'Уникальный2', 'Б')
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])

        assert len(result['connections']) == 1, "Should find exactly 1 connection pair"
        conn = result['connections'][0]

        # Check individual connection types
        details_by_type = {d['type']: d for d in conn['details']}

        assert 'mutual_friend' in details_by_type, "Should detect mutual friends"
        assert details_by_type['mutual_friend']['count'] == 3, "Should find exactly 3 mutual friends"
        assert details_by_type['mutual_friend']['score'] == pytest.approx(3.0), \
            "Mutual friend score should be 1.0 * min(3, 5) = 3.0"

        assert 'same_employer' in details_by_type, "Should detect same employer"
        assert details_by_type['same_employer']['score'] == pytest.approx(0.8), \
            "Same employer score should be 0.8"

        assert conn['total_score'] == pytest.approx(3.8), \
            "Total score should be 3.0 + 0.8 = 3.8"

    def test_scoring_weights_match_documented_values(self, app, engine):
        """Verify the weight constants match the documented specification."""
        assert engine.WEIGHTS['mutual_friend'] == 1.0
        assert engine.WEIGHTS['friend_of_friend'] == 0.5
        assert engine.WEIGHTS['same_employer'] == 0.8
        assert engine.WEIGHTS['same_group'] == 0.3
        assert engine.WEIGHTS['same_city_age'] == 0.1
        assert engine.WEIGHTS['shared_contact'] == 1.0

    def test_all_connection_types_combined(self, app, engine):
        """Investigation pair with ALL connection types scores correctly."""
        inv_a = create_investigation(
            'Полный',
            emails=[{'email': 'shared@test.ru'}],
            phones=[{'phone': '89161111111'}],
            groups=[{'id': '777'}],
        )
        inv_b = create_investigation(
            'Набор',
            emails=[{'email': 'shared@test.ru'}],
            phones=[{'phone': '+79161111111'}],
            groups=[{'id': '777'}],
        )
        db.session.flush()

        # Confirmed profiles: same employer + same city/age
        prof_a = create_profile(inv_a.id, '10', 'Полный', 'П',
                                city='Москва', age=30,
                                career=[{'company': 'TestCo'}])
        prof_b = create_profile(inv_b.id, '20', 'Набор', 'Н',
                                city='Москва', age=32,
                                career=[{'company': 'TestCo'}])
        db.session.flush()

        # 1 mutual friend + A is in B's friends (friend_of_friend)
        create_friend(inv_a.id, '300', 'Общий', 'Друг')
        create_friend(inv_b.id, '300', 'Общий', 'Друг')
        create_friend(inv_b.id, '10', 'Полный', 'П')  # A's profile in B's friends
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])

        assert len(result['connections']) == 1
        types_found = {d['type'] for d in result['connections'][0]['details']}

        assert 'mutual_friend' in types_found, "Should detect mutual friends"
        assert 'friend_of_friend' in types_found, "Should detect friend-of-friend"
        assert 'same_employer' in types_found, "Should detect same employer"
        assert 'same_group' in types_found, "Should detect same group"
        assert 'same_city_age' in types_found, "Should detect same city+age"
        assert 'shared_contact' in types_found, "Should detect shared contacts"

        # Total should be positive and reflect all connection types
        total = result['connections'][0]['total_score']
        assert total > 0, "Total score must be positive"


# ============================================================
# Test 2: Edge Case — Single Investigation
# ============================================================

class TestSingleInvestigation:
    """Single investigation should return empty connections, not crash."""

    def test_single_investigation_returns_empty_connections(self, app, engine):
        """With only one investigation, connections list is empty."""
        inv = create_investigation('Одиночка Тест')
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv.id])

        assert result['connections'] == [], \
            "Single investigation must produce no connections"
        assert result['edges'] == [], \
            "Single investigation must produce no edges"
        assert result['summary']['total_connections'] == 0, \
            "Connection count must be 0"
        assert result['summary']['strongest_connection'] is None, \
            "No strongest connection possible"

    def test_single_investigation_still_has_node(self, app, engine):
        """Even with one investigation, the node should appear in graph data."""
        inv = create_investigation('Единственный')
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv.id])
        assert len(result['nodes']) == 1, "Should have exactly 1 node"
        assert result['nodes'][0]['id'] == inv.id, "Node ID should match investigation"
        assert result['nodes'][0]['label'] == 'Единственный', "Node label should match name"


# ============================================================
# Test 3: Edge Case — Empty Friends Lists
# ============================================================

class TestEmptyFriendsLists:
    """Investigations with no friends should handle gracefully."""

    def test_no_friends_no_connections(self, app, engine):
        """Two investigations with zero friends → no friend-based connections."""
        inv_a = create_investigation('Без друзей А')
        inv_b = create_investigation('Без друзей Б')
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])

        assert len(result['connections']) == 0, \
            "No friends means no connections"
        assert len(result['nodes']) == 2, \
            "Both investigations should still appear as nodes"

    def test_one_has_friends_other_empty(self, app, engine):
        """One investigation has friends, other has none → no mutual friends."""
        inv_a = create_investigation('С друзьями')
        inv_b = create_investigation('Без друзей')
        db.session.flush()

        create_friend(inv_a.id, '111', 'Друг', 'ОдногоА')
        create_friend(inv_a.id, '222', 'Другой', 'ДругА')
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])
        mutual = []
        for conn in result['connections']:
            for d in conn['details']:
                if d['type'] == 'mutual_friend':
                    mutual.append(d)
        assert len(mutual) == 0, "No mutual friends when one side has no friends"


# ============================================================
# Test 4: Edge Case — Duplicate Entries
# ============================================================

class TestDuplicateEntries:
    """Duplicate data should be deduplicated."""

    def test_duplicate_friends_same_platform_id(self, app, engine):
        """Duplicate friends (same platform_id) in one investigation
        should not inflate the mutual friend count."""
        inv_a = create_investigation('А')
        inv_b = create_investigation('Б')
        db.session.flush()

        # Add same platform_id twice for inv_a (shouldn't count double)
        create_friend(inv_a.id, '100', 'Друг', 'Один')
        create_friend(inv_a.id, '100', 'Друг', 'Дубль')  # duplicate platform_id
        create_friend(inv_b.id, '100', 'Друг', 'Один')
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])

        assert len(result['connections']) == 1
        mutual = [d for d in result['connections'][0]['details'] if d['type'] == 'mutual_friend']
        assert len(mutual) == 1
        # platform_ids are collected as a set, so duplicates are inherently deduped
        assert mutual[0]['count'] == 1, \
            "Duplicate platform_id should count as 1 mutual friend"

    def test_same_pair_not_duplicated_in_results(self, app, engine):
        """Same pair of investigations should produce exactly one connection entry."""
        inv_a = create_investigation('А', emails=[{'email': 'dup@test.ru'}])
        inv_b = create_investigation('Б', emails=[{'email': 'dup@test.ru'}])
        db.session.flush()

        create_friend(inv_a.id, '555', 'Общий', 'Друг')
        create_friend(inv_b.id, '555', 'Общий', 'Друг')
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])
        # Exactly one connection entry for the pair
        assert len(result['connections']) == 1, "Should have exactly 1 connection per pair"
        # But multiple detail types within that connection
        assert len(result['connections'][0]['details']) == 2, \
            "Should have 2 detail types: mutual_friend + shared_contact"


# ============================================================
# Test 5: Integration Test — Full DB Data
# ============================================================

class TestIntegration:
    """Create realistic investigations in DB, run analysis, verify end-to-end."""

    def test_full_scenario_two_connected_people(self, app, engine):
        """
        Create 2 investigations with:
        - 3 mutual friends
        - Same employer (Яндекс)
        - Same city (Москва) and close age
        - Shared email
        Run analysis and verify all connection types found.
        """
        inv_a = create_investigation(
            'Иван Иванов',
            emails=[{'email': 'ivan@ya.ru'}, {'email': 'shared@company.ru'}],
            phones=[{'phone': '+79161234567'}],
        )
        inv_b = create_investigation(
            'Петр Петров',
            emails=[{'email': 'petr@ya.ru'}, {'email': 'shared@company.ru'}],
            phones=[{'phone': '+79169876543'}],
        )
        db.session.flush()

        prof_a = create_profile(inv_a.id, '1001', 'Иван', 'Иванов',
                                city='Москва', age=28,
                                career=[{'company': 'Яндекс'}])
        prof_b = create_profile(inv_b.id, '2001', 'Петр', 'Петров',
                                city='Москва', age=30,
                                career=[{'company': 'Яндекс'}])
        db.session.flush()

        # 3 mutual friends
        mutual_ids = ['5001', '5002', '5003']
        for i, pid in enumerate(mutual_ids):
            create_friend(inv_a.id, pid, f'Общий{i}', f'Друг{i}',
                          parent_profile_id=prof_a.id)
            create_friend(inv_b.id, pid, f'Общий{i}', f'Друг{i}',
                          parent_profile_id=prof_b.id)

        # Unique friends
        create_friend(inv_a.id, '6001', 'Только', 'А', parent_profile_id=prof_a.id)
        create_friend(inv_b.id, '6002', 'Только', 'Б', parent_profile_id=prof_b.id)
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])

        # Basic structure
        assert len(result['nodes']) == 2, "Should have 2 nodes"
        assert len(result['edges']) >= 1, "Should have at least 1 edge"
        assert len(result['connections']) == 1, "Should have 1 connection pair"

        conn = result['connections'][0]
        types_found = {d['type'] for d in conn['details']}

        assert 'mutual_friend' in types_found, "Should detect 3 mutual friends"
        assert 'same_employer' in types_found, "Should detect same employer (Яндекс)"
        assert 'same_city_age' in types_found, "Should detect same city+age (Москва, 28/30)"
        assert 'shared_contact' in types_found, "Should detect shared email"

        # Verify scoring
        mutual_detail = next(d for d in conn['details'] if d['type'] == 'mutual_friend')
        assert mutual_detail['count'] == 3
        assert mutual_detail['score'] == pytest.approx(3.0)

        employer_detail = next(d for d in conn['details'] if d['type'] == 'same_employer')
        assert employer_detail['score'] == pytest.approx(0.8)

        # Summary
        assert result['summary']['total_connections'] == 1
        assert result['summary']['strongest_connection'] is not None
        assert result['summary']['strongest_connection']['score'] == conn['total_score']

    def test_three_way_analysis(self, app, engine):
        """Three investigations produce correct number of pairs (3 choose 2 = 3 max)."""
        inv_a = create_investigation('А', emails=[{'email': 'ab@test.ru'}])
        inv_b = create_investigation('Б', emails=[{'email': 'ab@test.ru'}, {'email': 'bc@test.ru'}])
        inv_c = create_investigation('В', emails=[{'email': 'bc@test.ru'}])
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id, inv_c.id])

        assert len(result['nodes']) == 3, "All 3 investigations should be nodes"
        # A-B connected (shared ab@test.ru), B-C connected (shared bc@test.ru)
        # A-C NOT connected (no shared data)
        assert len(result['connections']) == 2, "Should find 2 connection pairs (A-B, B-C)"


# ============================================================
# Test 6: API Test — Valid Payload
# ============================================================

class TestAPIValidPayload:
    """POST /api/connections/analyze with valid investigation IDs."""

    def test_analyze_valid_ids_returns_200(self, app, client):
        """Valid IDs return 200 with correct JSON structure."""
        with app.app_context():
            inv_a = create_investigation('API А', emails=[{'email': 'api@test.ru'}])
            inv_b = create_investigation('API Б', emails=[{'email': 'api@test.ru'}])
            db.session.commit()
            ids = [inv_a.id, inv_b.id]

        resp = client.post('/api/connections/analyze',
                           data=json.dumps({'investigation_ids': ids}),
                           content_type='application/json')

        assert resp.status_code == 200, "Should return 200 for valid payload"
        data = resp.get_json()
        assert 'nodes' in data, "Response must contain nodes"
        assert 'edges' in data, "Response must contain edges"
        assert 'connections' in data, "Response must contain connections"
        assert 'summary' in data, "Response must contain summary"
        assert isinstance(data['nodes'], list), "Nodes must be a list"
        assert isinstance(data['edges'], list), "Edges must be a list"
        assert isinstance(data['connections'], list), "Connections must be a list"

    def test_analyze_empty_body_analyzes_all(self, app, client):
        """Empty JSON body analyzes all investigations (no error)."""
        with app.app_context():
            create_investigation('Все А')
            create_investigation('Все Б')
            db.session.commit()

        resp = client.post('/api/connections/analyze',
                           data=json.dumps({}),
                           content_type='application/json')
        assert resp.status_code == 200, "Empty body should be accepted"

    def test_analyze_no_body(self, app, client):
        """POST with no body at all should still work (analyze all)."""
        resp = client.post('/api/connections/analyze')
        assert resp.status_code == 200, "No body should default to analyze all"

    def test_analyze_returns_connection_details(self, app, client):
        """Verify connection details in response contain expected fields."""
        with app.app_context():
            inv_a = create_investigation('Детали А', emails=[{'email': 'detail@test.ru'}])
            inv_b = create_investigation('Детали Б', emails=[{'email': 'detail@test.ru'}])
            db.session.commit()
            ids = [inv_a.id, inv_b.id]

        resp = client.post('/api/connections/analyze',
                           data=json.dumps({'investigation_ids': ids}),
                           content_type='application/json')
        data = resp.get_json()

        assert len(data['connections']) == 1, "Should find 1 connection"
        conn = data['connections'][0]
        assert 'inv_a_id' in conn, "Connection must have inv_a_id"
        assert 'inv_b_id' in conn, "Connection must have inv_b_id"
        assert 'details' in conn, "Connection must have details"
        assert 'total_score' in conn, "Connection must have total_score"
        assert 'summary' in conn, "Connection must have summary"


# ============================================================
# Test 7: API Test — Invalid Payload
# ============================================================

class TestAPIInvalidPayload:
    """API error handling for bad requests."""

    def test_investigation_ids_not_a_list(self, app, client):
        """investigation_ids as a string (not list) returns 400."""
        resp = client.post('/api/connections/analyze',
                           data=json.dumps({'investigation_ids': 'not-a-list'}),
                           content_type='application/json')
        assert resp.status_code == 400, \
            "Non-list investigation_ids should return 400"
        data = resp.get_json()
        assert 'error' in data, "Error response must contain error message"

    def test_nonexistent_ids_returns_empty(self, app, client):
        """Nonexistent investigation IDs return 200 with empty results (not crash)."""
        resp = client.post('/api/connections/analyze',
                           data=json.dumps({
                               'investigation_ids': ['fake-id-1', 'fake-id-2']
                           }),
                           content_type='application/json')
        assert resp.status_code == 200, \
            "Nonexistent IDs should not cause a server error"
        data = resp.get_json()
        assert data['connections'] == [], "No connections for nonexistent IDs"
        assert data['nodes'] == [], "No nodes for nonexistent IDs"

    def test_investigation_ids_as_number(self, app, client):
        """investigation_ids as a number returns 400."""
        resp = client.post('/api/connections/analyze',
                           data=json.dumps({'investigation_ids': 42}),
                           content_type='application/json')
        assert resp.status_code == 400, \
            "Numeric investigation_ids should return 400"


# ============================================================
# Test 8: Graph Data — vis.js Format Validation
# ============================================================

class TestGraphDataFormat:
    """GET /api/connections/graph-data returns valid vis.js format."""

    def test_graph_data_returns_nodes_and_edges(self, app, client):
        """graph-data endpoint returns nodes and edges arrays."""
        with app.app_context():
            inv_a = create_investigation('Граф А', emails=[{'email': 'graph@t.ru'}])
            inv_b = create_investigation('Граф Б', emails=[{'email': 'graph@t.ru'}])
            db.session.commit()

        resp = client.get('/api/connections/graph-data')
        assert resp.status_code == 200, "graph-data should return 200"
        data = resp.get_json()

        assert 'nodes' in data, "Must contain nodes"
        assert 'edges' in data, "Must contain edges"
        assert 'summary' in data, "Must contain summary"
        assert isinstance(data['nodes'], list), "Nodes must be a list"
        assert isinstance(data['edges'], list), "Edges must be a list"

    def test_node_has_vis_js_fields(self, app, client):
        """Each node has id, label, shape, size, font, color fields for vis.js."""
        with app.app_context():
            inv = create_investigation('Нода')
            db.session.commit()
            inv_id = inv.id

        resp = client.get(f'/api/connections/graph-data?ids={inv_id}')
        data = resp.get_json()

        assert len(data['nodes']) == 1, "Should have 1 node"
        node = data['nodes'][0]
        required_fields = ['id', 'label', 'shape', 'size', 'font', 'color']
        for field in required_fields:
            assert field in node, f"Node missing required vis.js field: {field}"

    def test_edge_has_vis_js_fields(self, app, client):
        """Each edge has from, to, value, label, color, width fields for vis.js."""
        with app.app_context():
            inv_a = create_investigation('Ребро А', emails=[{'email': 'edge@t.ru'}])
            inv_b = create_investigation('Ребро Б', emails=[{'email': 'edge@t.ru'}])
            db.session.commit()

        resp = client.get('/api/connections/graph-data')
        data = resp.get_json()

        assert len(data['edges']) == 1, "Should have 1 edge"
        edge = data['edges'][0]
        required_fields = ['from', 'to', 'value', 'label', 'color', 'width']
        for field in required_fields:
            assert field in edge, f"Edge missing required vis.js field: {field}"

    def test_graph_data_with_ids_filter(self, app, client):
        """graph-data with ids= query param filters to selected investigations."""
        with app.app_context():
            inv_a = create_investigation('Фильтр А')
            inv_b = create_investigation('Фильтр Б')
            inv_c = create_investigation('Не включён')
            db.session.commit()
            ids_str = f"{inv_a.id},{inv_b.id}"

        resp = client.get(f'/api/connections/graph-data?ids={ids_str}')
        data = resp.get_json()

        node_ids = {n['id'] for n in data['nodes']}
        assert len(node_ids) == 2, "Should filter to exactly 2 nodes"

    def test_summary_has_expected_fields(self, app, client):
        """Summary object has total_investigations, total_connections, etc."""
        with app.app_context():
            create_investigation('Сводка А')
            create_investigation('Сводка Б')
            db.session.commit()

        resp = client.get('/api/connections/graph-data')
        data = resp.get_json()
        summary = data['summary']

        assert 'total_investigations' in summary, "Summary must have total_investigations"
        assert 'total_connections' in summary, "Summary must have total_connections"
        assert 'strongest_connection' in summary, "Summary must have strongest_connection"
        assert 'connection_types' in summary, "Summary must have connection_types"


# ============================================================
# Test 9: Zero Overlap Test
# ============================================================

class TestZeroOverlap:
    """Two investigations with no common data produce empty connections."""

    def test_no_shared_data_empty_connections(self, app, engine):
        """Two investigations with completely different data → no connections."""
        inv_a = create_investigation(
            'Изолированный А',
            emails=[{'email': 'only_a@test.ru'}],
            phones=[{'phone': '+79161111111'}],
        )
        inv_b = create_investigation(
            'Изолированный Б',
            emails=[{'email': 'only_b@test.ru'}],
            phones=[{'phone': '+79169999999'}],
        )
        db.session.flush()

        # Different cities, different ages, different employers
        create_profile(inv_a.id, '10', 'А', 'А', city='Москва', age=20,
                        career=[{'company': 'КомпанияА'}])
        create_profile(inv_b.id, '20', 'Б', 'Б', city='Владивосток', age=50,
                        career=[{'company': 'КомпанияБ'}])
        db.session.flush()

        # Different friends
        create_friend(inv_a.id, '111', 'Друг', 'ТолькоА')
        create_friend(inv_b.id, '999', 'Друг', 'ТолькоБ')
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])

        assert result['connections'] == [], "No shared data means no connections"
        assert result['edges'] == [], "No shared data means no edges"
        assert len(result['nodes']) == 2, "Both nodes should still exist"
        assert result['summary']['total_connections'] == 0
        assert result['summary']['strongest_connection'] is None

    def test_no_shared_data_via_api(self, app, client):
        """API returns empty connections for unrelated investigations."""
        with app.app_context():
            inv_a = create_investigation('API Ноль А',
                                         emails=[{'email': 'nope1@x.ru'}])
            inv_b = create_investigation('API Ноль Б',
                                         emails=[{'email': 'nope2@x.ru'}])
            db.session.commit()
            ids = [inv_a.id, inv_b.id]

        resp = client.post('/api/connections/analyze',
                           data=json.dumps({'investigation_ids': ids}),
                           content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['connections'] == [], "API should return empty connections for unrelated data"
        assert data['edges'] == [], "API should return empty edges for unrelated data"


# ============================================================
# Bonus: Template Rendering Tests
# ============================================================

class TestConnectionsTemplate:
    """Verify that the connections page template renders correctly."""

    def test_connections_page_renders_200(self, app, client):
        """GET /connections returns 200."""
        resp = client.get('/connections')
        assert resp.status_code == 200, "Connections page should return 200"

    def test_connections_page_contains_graph_div(self, app, client):
        """Page contains the connections-graph div for vis.js."""
        with app.app_context():
            create_investigation('Темплейт1')
            create_investigation('Темплейт2')
            db.session.commit()

        resp = client.get('/connections')
        html = resp.data.decode('utf-8')
        assert 'connections-graph' in html, "Page must contain connections-graph div"

    def test_connections_page_includes_vis_js(self, app, client):
        """Page includes vis-network JS library."""
        with app.app_context():
            create_investigation('JS1')
            create_investigation('JS2')
            db.session.commit()

        resp = client.get('/connections')
        html = resp.data.decode('utf-8')
        assert 'vis-network' in html, "Page must include vis-network library"

    def test_connections_page_analyze_button(self, app, client):
        """Page has the Analyze button."""
        with app.app_context():
            create_investigation('Кнопка1')
            create_investigation('Кнопка2')
            db.session.commit()

        resp = client.get('/connections')
        html = resp.data.decode('utf-8')
        assert 'Анализировать' in html, "Page must have Analyze button"

    def test_connections_page_insufficient_investigations(self, app, client):
        """With < 2 investigations, show 'not enough' message."""
        with app.app_context():
            create_investigation('Один')
            db.session.commit()

        resp = client.get('/connections')
        html = resp.data.decode('utf-8')
        assert 'Недостаточно расследований' in html, \
            "Should show insufficient investigations message"

    def test_connections_page_has_link_text(self, app, client):
        """Page contains 'Связи' in its content."""
        resp = client.get('/connections')
        html = resp.data.decode('utf-8')
        assert 'Связи' in html, "Page title must contain 'Связи'"
