"""
Tests for Cross-Investigation Connection Intelligence Engine
=============================================================
Unit, integration, and API tests for connection analysis between investigations.
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


@pytest.fixture
def app():
    """Create application for testing with in-memory DB."""
    os.environ.pop('IBP_PASSWORD', None)
    os.environ.pop('IBP_PASSWORD_HASH', None)
    app = create_app('testing')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret'

    # Re-init DB with in-memory URI
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
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


def make_investigation(input_name, status='phase_2_complete', emails=None, phones=None,
                       groups=None):
    """Helper to create an Investigation with given data."""
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


def make_profile(investigation_id, platform_id, first_name, last_name,
                 is_confirmed=True, city=None, age=None, career=None):
    """Helper to create a SocialProfile."""
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


def make_friend(investigation_id, platform_id, first_name, last_name,
                parent_profile_id=None):
    """Helper to create a Friend."""
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
# Unit Tests: Mutual Friends
# ============================================================

class TestMutualFriends:
    """Test mutual friend detection via platform_id intersection."""

    def test_mutual_friends_found(self, app, engine):
        """Two investigations sharing friends by platform_id get mutual_friend connection."""
        inv_a = make_investigation('Иван Иванов')
        inv_b = make_investigation('Петр Петров')
        db.session.flush()

        # Shared friends: platform_ids 100, 200
        make_friend(inv_a.id, '100', 'Общий', 'Друг1')
        make_friend(inv_a.id, '200', 'Общий', 'Друг2')
        make_friend(inv_a.id, '300', 'Только', 'А')

        make_friend(inv_b.id, '100', 'Общий', 'Друг1')
        make_friend(inv_b.id, '200', 'Общий', 'Друг2')
        make_friend(inv_b.id, '400', 'Только', 'Б')
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])

        assert len(result['connections']) == 1
        conn = result['connections'][0]
        mutual = [d for d in conn['details'] if d['type'] == 'mutual_friend']
        assert len(mutual) == 1
        assert mutual[0]['count'] == 2
        # Weight: 1.0 * min(count, 5) = 1.0 * 2 = 2.0
        assert mutual[0]['score'] == 2.0

    def test_mutual_friends_capped_at_5(self, app, engine):
        """Score for mutual friends is capped at 5 * weight."""
        inv_a = make_investigation('А А')
        inv_b = make_investigation('Б Б')
        db.session.flush()

        # Create 10 shared friends
        for i in range(10):
            pid = str(1000 + i)
            make_friend(inv_a.id, pid, f'Друг{i}', 'Общий')
            make_friend(inv_b.id, pid, f'Друг{i}', 'Общий')
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])
        conn = result['connections'][0]
        mutual = [d for d in conn['details'] if d['type'] == 'mutual_friend'][0]
        assert mutual['count'] == 10
        # Capped: 1.0 * min(10, 5) = 5.0
        assert mutual['score'] == 5.0


# ============================================================
# Unit Tests: Same Employer
# ============================================================

class TestSameEmployer:
    """Test same employer detection via career data on confirmed profiles."""

    def test_same_employer_found(self, app, engine):
        """Two investigations with same employer in career → connection with 0.8 weight."""
        inv_a = make_investigation('Анна Сидорова')
        inv_b = make_investigation('Мария Козлова')
        db.session.flush()

        make_profile(inv_a.id, '10', 'Анна', 'Сидорова',
                     career=[{'company': 'Яндекс'}])
        make_profile(inv_b.id, '20', 'Мария', 'Козлова',
                     career=[{'company': 'Яндекс'}, {'company': 'Google'}])
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])

        conn = result['connections'][0]
        employer = [d for d in conn['details'] if d['type'] == 'same_employer']
        assert len(employer) == 1
        assert employer[0]['count'] == 1
        # Weight: 0.8 * 1 = 0.8
        assert employer[0]['score'] == pytest.approx(0.8)

    def test_multiple_shared_employers(self, app, engine):
        """Multiple shared employers multiply the score."""
        inv_a = make_investigation('А')
        inv_b = make_investigation('Б')
        db.session.flush()

        make_profile(inv_a.id, '10', 'А', 'А',
                     career=[{'company': 'Яндекс'}, {'company': 'VK'}])
        make_profile(inv_b.id, '20', 'Б', 'Б',
                     career=[{'company': 'яндекс'}, {'company': 'vk'}])
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])
        conn = result['connections'][0]
        employer = [d for d in conn['details'] if d['type'] == 'same_employer'][0]
        assert employer['count'] == 2
        assert employer['score'] == pytest.approx(1.6)


# ============================================================
# Unit Tests: Same City + Age
# ============================================================

class TestSameCityAge:
    """Test same city + similar age detection."""

    def test_same_city_close_age(self, app, engine):
        """Same city and age within 5 years → connection with 0.1 weight."""
        inv_a = make_investigation('Олег')
        inv_b = make_investigation('Дмитрий')
        db.session.flush()

        make_profile(inv_a.id, '10', 'Олег', 'О', city='Москва', age=25)
        make_profile(inv_b.id, '20', 'Дмитрий', 'Д', city='Москва', age=28)
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])
        conn = result['connections'][0]
        city_age = [d for d in conn['details'] if d['type'] == 'same_city_age']
        assert len(city_age) == 1
        assert city_age[0]['score'] == pytest.approx(0.1)

    def test_same_city_far_age(self, app, engine):
        """Same city but age difference > 5 → no connection."""
        inv_a = make_investigation('Олег')
        inv_b = make_investigation('Дмитрий')
        db.session.flush()

        make_profile(inv_a.id, '10', 'Олег', 'О', city='Москва', age=20)
        make_profile(inv_b.id, '20', 'Дмитрий', 'Д', city='Москва', age=40)
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])
        assert len(result['connections']) == 0

    def test_different_city(self, app, engine):
        """Different cities → no same_city_age connection even with same age."""
        inv_a = make_investigation('Олег')
        inv_b = make_investigation('Дмитрий')
        db.session.flush()

        make_profile(inv_a.id, '10', 'Олег', 'О', city='Москва', age=25)
        make_profile(inv_b.id, '20', 'Дмитрий', 'Д', city='Питер', age=25)
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])
        assert len(result['connections']) == 0


# ============================================================
# Unit Tests: Shared Contacts (phone/email)
# ============================================================

class TestSharedContacts:
    """Test shared phone and email detection."""

    def test_shared_email(self, app, engine):
        """Two investigations with same email → shared_contact connection (1.0 weight)."""
        inv_a = make_investigation('А', emails=[{'email': 'test@mail.ru'}])
        inv_b = make_investigation('Б', emails=[{'email': 'test@mail.ru'}])
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])
        conn = result['connections'][0]
        shared = [d for d in conn['details'] if d['type'] == 'shared_contact']
        assert len(shared) == 1
        assert shared[0]['score'] == pytest.approx(1.0)
        assert shared[0]['count'] == 1

    def test_shared_phone_normalized(self, app, engine):
        """Phone numbers starting with 8 and 7 normalize to same → connection found."""
        inv_a = make_investigation('А', phones=[{'phone': '89161234567'}])
        inv_b = make_investigation('Б', phones=[{'phone': '+79161234567'}])
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])
        conn = result['connections'][0]
        shared = [d for d in conn['details'] if d['type'] == 'shared_contact']
        assert len(shared) == 1

    def test_shared_email_case_insensitive(self, app, engine):
        """Email comparison is case-insensitive."""
        inv_a = make_investigation('А', emails=[{'email': 'Test@Mail.RU'}])
        inv_b = make_investigation('Б', emails=[{'email': 'test@mail.ru'}])
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])
        assert len(result['connections']) == 1

    def test_string_format_emails(self, app, engine):
        """Emails stored as plain strings (not dicts) also work."""
        inv_a = make_investigation('А', emails=['shared@ya.ru'])
        inv_b = make_investigation('Б', emails=['shared@ya.ru'])
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])
        assert len(result['connections']) == 1

    def test_string_format_phones(self, app, engine):
        """Phones stored as plain strings also work."""
        inv_a = make_investigation('А', phones=['89161234567'])
        inv_b = make_investigation('Б', phones=['+79161234567'])
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])
        assert len(result['connections']) == 1


# ============================================================
# Unit Tests: Edge Cases
# ============================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_investigation(self, app, engine):
        """Single investigation → no connections possible, empty edges."""
        inv = make_investigation('Один')
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv.id])
        assert result['connections'] == []
        assert result['edges'] == []
        assert result['summary']['total_connections'] == 0
        assert result['summary']['strongest_connection'] is None
        # Node should still be present
        assert len(result['nodes']) == 1
        assert result['nodes'][0]['id'] == inv.id

    def test_zero_investigations(self, app, engine):
        """No investigations (nonexistent IDs) → empty results."""
        result = engine.analyze(investigation_ids=['nonexistent-id'])
        assert result['nodes'] == []
        assert result['edges'] == []
        assert result['connections'] == []

    def test_empty_friends_lists(self, app, engine):
        """Two investigations with no friends → no friend-based connections."""
        inv_a = make_investigation('А')
        inv_b = make_investigation('Б')
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])
        assert len(result['connections']) == 0

    def test_no_duplicate_connections(self, app, engine):
        """Same pair analyzed → produces exactly one connection entry per pair."""
        inv_a = make_investigation('А', emails=[{'email': 'same@test.ru'}])
        inv_b = make_investigation('Б', emails=[{'email': 'same@test.ru'}])
        db.session.flush()

        # Add mutual friends too
        make_friend(inv_a.id, '999', 'Друг', 'Общий')
        make_friend(inv_b.id, '999', 'Друг', 'Общий')
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])
        # Should be 1 connection (one pair), with 2 detail types
        assert len(result['connections']) == 1
        types = [d['type'] for d in result['connections'][0]['details']]
        assert 'mutual_friend' in types
        assert 'shared_contact' in types

    def test_no_confirmed_profile(self, app, engine):
        """Investigation without confirmed profile → employer/city checks skipped gracefully."""
        inv_a = make_investigation('А')
        inv_b = make_investigation('Б')
        db.session.flush()

        # Add unconfirmed profiles
        make_profile(inv_a.id, '10', 'А', 'А', is_confirmed=False,
                     city='Москва', age=25, career=[{'company': 'Яндекс'}])
        make_profile(inv_b.id, '20', 'Б', 'Б', is_confirmed=False,
                     city='Москва', age=25, career=[{'company': 'Яндекс'}])
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])
        # No confirmed profiles → no employer or city+age connections
        assert len(result['connections']) == 0

    def test_three_investigations(self, app, engine):
        """Three investigations → all pairs analyzed (3 choose 2 = 3 pairs)."""
        inv_a = make_investigation('А', emails=[{'email': 'ab@test.ru'}])
        inv_b = make_investigation('Б', emails=[{'email': 'ab@test.ru'}])
        inv_c = make_investigation('В', emails=[{'email': 'bc@test.ru'}])
        # B and C share an email, A and B share an email
        inv_b.discovered_emails = [{'email': 'ab@test.ru'}, {'email': 'bc@test.ru'}]
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id, inv_c.id])
        assert len(result['nodes']) == 3
        # A-B connected (ab@test.ru), B-C connected (bc@test.ru), A-C not connected
        assert len(result['connections']) == 2

    def test_friend_of_friend(self, app, engine):
        """A's confirmed profile platform_id is in B's friends → friend_of_friend connection."""
        inv_a = make_investigation('А')
        inv_b = make_investigation('Б')
        db.session.flush()

        # A's confirmed profile has platform_id '50'
        make_profile(inv_a.id, '50', 'А', 'А', is_confirmed=True)
        # B has '50' as a friend
        make_friend(inv_b.id, '50', 'А', 'А')
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])
        assert len(result['connections']) == 1
        fof = [d for d in result['connections'][0]['details'] if d['type'] == 'friend_of_friend']
        assert len(fof) == 1
        assert fof[0]['score'] == pytest.approx(0.5)

    def test_same_groups(self, app, engine):
        """Two investigations sharing VK group IDs → same_group connection."""
        inv_a = make_investigation('А', groups=[{'id': '111'}, {'id': '222'}])
        inv_b = make_investigation('Б', groups=[{'id': '222'}, {'id': '333'}])
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])
        assert len(result['connections']) == 1
        grp = [d for d in result['connections'][0]['details'] if d['type'] == 'same_group'][0]
        assert grp['count'] == 1
        assert grp['score'] == pytest.approx(0.3)


# ============================================================
# Unit Tests: Phone Normalization
# ============================================================

class TestPhoneNormalization:
    """Test the _normalize_phone static method."""

    def test_normalize_8_to_7(self):
        """Phone starting with 8 and 11 digits → 8 replaced by 7."""
        assert ConnectionIntelligence._normalize_phone('89161234567') == '79161234567'

    def test_normalize_plus7(self):
        """Phone with +7 prefix → digits only."""
        assert ConnectionIntelligence._normalize_phone('+79161234567') == '79161234567'

    def test_normalize_short_number(self):
        """Short number starting with 8 but not 11 digits → unchanged."""
        assert ConnectionIntelligence._normalize_phone('8123456') == '8123456'

    def test_normalize_empty(self):
        """Empty phone → empty string."""
        assert ConnectionIntelligence._normalize_phone('') == ''
        assert ConnectionIntelligence._normalize_phone(None) == ''


# ============================================================
# Unit Tests: Graph Data Structure
# ============================================================

class TestGraphStructure:
    """Test that graph nodes and edges have vis.js compatible structure."""

    def test_node_structure(self, app, engine):
        """Nodes have required vis.js fields: id, label, shape, etc."""
        inv = make_investigation('Тест Тестов')
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv.id])
        assert len(result['nodes']) == 1
        node = result['nodes'][0]
        assert 'id' in node
        assert 'label' in node
        assert node['label'] == 'Тест Тестов'
        assert 'shape' in node
        assert 'size' in node
        assert 'font' in node
        assert 'color' in node

    def test_edge_structure(self, app, engine):
        """Edges have required vis.js fields: from, to, value, color, etc."""
        inv_a = make_investigation('А', emails=[{'email': 'x@t.ru'}])
        inv_b = make_investigation('Б', emails=[{'email': 'x@t.ru'}])
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])
        assert len(result['edges']) == 1
        edge = result['edges'][0]
        assert 'from' in edge
        assert 'to' in edge
        assert 'value' in edge
        assert 'label' in edge
        assert 'color' in edge
        assert 'width' in edge
        assert edge['from'] == inv_a.id
        assert edge['to'] == inv_b.id

    def test_summary_structure(self, app, engine):
        """Summary has expected keys."""
        inv_a = make_investigation('А')
        inv_b = make_investigation('Б')
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])
        summary = result['summary']
        assert 'total_investigations' in summary
        assert 'total_connections' in summary
        assert 'strongest_connection' in summary
        assert 'connection_types' in summary
        assert summary['total_investigations'] == 2

    def test_edge_color_by_type(self, app, engine):
        """Edge color reflects the strongest connection type."""
        inv_a = make_investigation('А', emails=[{'email': 'x@t.ru'}])
        inv_b = make_investigation('Б', emails=[{'email': 'x@t.ru'}])
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])
        edge = result['edges'][0]
        # shared_contact → red
        assert edge['color']['color'] == '#ef4444'


# ============================================================
# Integration Tests
# ============================================================

class TestIntegration:
    """Integration tests: create full DB data, run analysis, verify end-to-end."""

    def test_full_analysis_two_investigations(self, app, engine):
        """Create 2 investigations with overlapping friends, run analysis, verify results."""
        inv_a = make_investigation(
            'Иван Иванов',
            emails=[{'email': 'ivan@mail.ru'}, {'email': 'shared@company.ru'}],
            phones=[{'phone': '+79161111111'}],
        )
        inv_b = make_investigation(
            'Петр Петров',
            emails=[{'email': 'petr@mail.ru'}, {'email': 'shared@company.ru'}],
            phones=[{'phone': '+79162222222'}],
        )
        db.session.flush()

        # Confirmed profiles with same employer and same city+similar age
        prof_a = make_profile(inv_a.id, '1001', 'Иван', 'Иванов',
                              city='Москва', age=30,
                              career=[{'company': 'Яндекс'}])
        prof_b = make_profile(inv_b.id, '2001', 'Петр', 'Петров',
                              city='Москва', age=32,
                              career=[{'company': 'Яндекс'}])
        db.session.flush()

        # Add friends: 3 mutual, some unique
        for i in range(3):
            pid = str(5000 + i)
            make_friend(inv_a.id, pid, f'Друг{i}', 'Общий', parent_profile_id=prof_a.id)
            make_friend(inv_b.id, pid, f'Друг{i}', 'Общий', parent_profile_id=prof_b.id)
        make_friend(inv_a.id, '6001', 'Только', 'А', parent_profile_id=prof_a.id)
        make_friend(inv_b.id, '6002', 'Только', 'Б', parent_profile_id=prof_b.id)
        db.session.commit()

        result = engine.analyze(investigation_ids=[inv_a.id, inv_b.id])

        # Should find exactly 1 connection pair
        assert len(result['connections']) == 1
        conn = result['connections'][0]
        types_found = {d['type'] for d in conn['details']}

        # Should detect: mutual_friend, same_employer, same_city_age, shared_contact
        assert 'mutual_friend' in types_found
        assert 'same_employer' in types_found
        assert 'same_city_age' in types_found
        assert 'shared_contact' in types_found

        # Verify total score > 0
        assert conn['total_score'] > 0

        # Verify graph data
        assert len(result['nodes']) == 2
        assert len(result['edges']) == 1

        # Verify summary
        assert result['summary']['total_connections'] == 1
        assert result['summary']['strongest_connection'] is not None

    def test_analyze_all_investigations(self, app, engine):
        """Calling analyze() without IDs analyzes all investigations."""
        inv_a = make_investigation('А', emails=[{'email': 'all@test.ru'}])
        inv_b = make_investigation('Б', emails=[{'email': 'all@test.ru'}])
        db.session.commit()

        result = engine.analyze()  # No IDs → all
        assert len(result['nodes']) == 2
        assert len(result['connections']) == 1


# ============================================================
# API Tests
# ============================================================

class TestAPI:
    """Test the /api/connections/* routes."""

    def test_analyze_with_valid_ids(self, app, client):
        """POST /api/connections/analyze with valid IDs → 200 with connections."""
        with app.app_context():
            inv_a = make_investigation('А', emails=[{'email': 'api@test.ru'}])
            inv_b = make_investigation('Б', emails=[{'email': 'api@test.ru'}])
            db.session.commit()
            ids = [inv_a.id, inv_b.id]

        resp = client.post('/api/connections/analyze',
                           data=json.dumps({'investigation_ids': ids}),
                           content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'nodes' in data
        assert 'edges' in data
        assert 'connections' in data
        assert 'summary' in data
        assert len(data['connections']) == 1

    def test_analyze_empty_payload(self, app, client):
        """POST /api/connections/analyze with empty JSON → analyzes all (no error)."""
        with app.app_context():
            make_investigation('А')
            db.session.commit()

        resp = client.post('/api/connections/analyze',
                           data=json.dumps({}),
                           content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'nodes' in data

    def test_analyze_no_json(self, app, client):
        """POST /api/connections/analyze with no body → 200 (analyzes all)."""
        resp = client.post('/api/connections/analyze')
        assert resp.status_code == 200

    def test_analyze_invalid_investigation_ids_type(self, app, client):
        """POST with investigation_ids as string (not list) → 400 error."""
        resp = client.post('/api/connections/analyze',
                           data=json.dumps({'investigation_ids': 'not-a-list'}),
                           content_type='application/json')
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data

    def test_graph_data_endpoint(self, app, client):
        """GET /api/connections/graph-data → vis.js compatible JSON."""
        with app.app_context():
            inv_a = make_investigation('А', emails=[{'email': 'graph@test.ru'}])
            inv_b = make_investigation('Б', emails=[{'email': 'graph@test.ru'}])
            db.session.commit()

        resp = client.get('/api/connections/graph-data')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'nodes' in data
        assert 'edges' in data
        assert 'summary' in data
        assert isinstance(data['nodes'], list)
        assert isinstance(data['edges'], list)

    def test_graph_data_with_ids_param(self, app, client):
        """GET /api/connections/graph-data?ids=id1,id2 → filtered results."""
        with app.app_context():
            inv_a = make_investigation('А', emails=[{'email': 'filter@t.ru'}])
            inv_b = make_investigation('Б', emails=[{'email': 'filter@t.ru'}])
            inv_c = make_investigation('В')  # Not included
            db.session.commit()
            ids_param = f"{inv_a.id},{inv_b.id}"

        resp = client.get(f'/api/connections/graph-data?ids={ids_param}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data['nodes']) == 2

    def test_graph_data_vis_js_node_format(self, app, client):
        """Verify graph-data nodes have vis.js required fields."""
        with app.app_context():
            inv = make_investigation('Тест')
            db.session.commit()
            inv_id = inv.id

        resp = client.get(f'/api/connections/graph-data?ids={inv_id}')
        data = resp.get_json()
        assert len(data['nodes']) == 1
        node = data['nodes'][0]
        assert 'id' in node
        assert 'label' in node

    def test_graph_data_vis_js_edge_format(self, app, client):
        """Verify graph-data edges have vis.js required from/to/value fields."""
        with app.app_context():
            inv_a = make_investigation('А', emails=[{'email': 'vis@t.ru'}])
            inv_b = make_investigation('Б', emails=[{'email': 'vis@t.ru'}])
            db.session.commit()

        resp = client.get('/api/connections/graph-data')
        data = resp.get_json()
        assert len(data['edges']) == 1
        edge = data['edges'][0]
        assert 'from' in edge
        assert 'to' in edge
        assert 'value' in edge


# ============================================================
# Template Tests
# ============================================================

class TestTemplate:
    """Test that the connections template renders correctly."""

    def test_connections_page_renders(self, app, client):
        """GET /connections → 200, HTML response."""
        resp = client.get('/connections')
        assert resp.status_code == 200
        assert b'<!DOCTYPE html>' in resp.data or b'<html' in resp.data

    def test_connections_page_has_expected_elements(self, app, client):
        """GET /connections → contains key UI elements."""
        with app.app_context():
            make_investigation('Тест1')
            make_investigation('Тест2')
            db.session.commit()

        resp = client.get('/connections')
        assert resp.status_code == 200
        html = resp.data.decode('utf-8')
        # Check for key elements
        assert 'connections-graph' in html
        assert 'vis-network' in html  # vis.js CDN reference
        assert 'Анализировать' in html  # Analyze button text
        assert 'Связи' in html  # Page title

    def test_connections_page_few_investigations(self, app, client):
        """GET /connections with < 2 investigations → shows 'not enough' message."""
        with app.app_context():
            make_investigation('Один')
            db.session.commit()

        resp = client.get('/connections')
        html = resp.data.decode('utf-8')
        assert 'Недостаточно расследований' in html
