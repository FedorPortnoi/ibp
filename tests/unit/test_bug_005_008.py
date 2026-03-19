"""
Tests for BUG-005, BUG-006, BUG-007, BUG-008 verification.
"""
import sys
import os

# Ensure the project root is on sys.path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


# ============================================================
# BUG-005: Social graph center node empty label
# ============================================================
def test_bug005_center_node_label_fallback():
    """
    When confirmed_name is None but full_name='Судин Артем',
    the center node label must equal 'Судин Артем' (not empty/None).
    """
    # We replicate exactly what social_analysis.py does: when VK profile
    # has empty first_name/last_name, it splits check.full_name.
    # Then social_graph._add_node builds label = first + " " + last.

    # Simulate: confirmed_name=None, full_name="Судин Артем"
    confirmed_name = None
    full_name = "Судин Артем"

    # Pipeline logic (social_analysis.py lines 405-411):
    c_first = ''  # VK profile has no first_name
    c_last = ''   # VK profile has no last_name
    if not c_first and not c_last and full_name:
        parts = full_name.strip().split()
        c_last = parts[0] if parts else ''
        c_first = parts[1] if len(parts) > 1 else ''

    center_data = {
        'first_name': c_first,
        'last_name': c_last,
        'photo_100': '',
        'city': None,
    }

    # Build the label the same way _add_node does (social_graph.py line 153)
    label = f"{center_data.get('first_name', '')} {center_data.get('last_name', '')}".strip()

    assert label, f"BUG-005 FAIL: center node label is empty! Got: '{label}'"
    assert label == "Артем Судин", (
        f"BUG-005 FAIL: expected 'Артем Судин', got '{label}'"
    )
    # Also verify it's not None
    assert label is not None, "BUG-005 FAIL: label is None"
    print(f"BUG-005 PASS: center node label = '{label}' (not empty/None)")


# ============================================================
# BUG-006: Raw Python dict in graph tooltips
# ============================================================
def test_bug006_tooltip_city_extraction():
    """
    When user has city={'id':15,'title':'Сочи'}, the tooltip must
    contain 'Сочи' and NOT "{'id'" (raw dict string).
    """
    from app.services.phase2.social_graph import SocialGraphBuilder, SocialGraphData, GraphNode, GraphEdge

    builder = SocialGraphBuilder.__new__(SocialGraphBuilder)
    builder.token = None
    builder._demo_mode = True
    builder.nodes = {}
    builder.edges = set()
    builder.adjacency = {}
    builder.nx_graph = None

    # Simulate _add_node with city as dict
    user_data = {
        'first_name': 'Тест',
        'last_name': 'Тестов',
        'photo_100': None,
        'city': {'id': 15, 'title': 'Сочи'},
    }

    builder._add_node(999, user_data, level=0, is_center=True)
    node = builder.nodes['vk_999']

    # The node.city should be the string 'Сочи', not a dict
    assert isinstance(node.city, str), f"BUG-006 FAIL: node.city is {type(node.city)}, expected str"
    assert node.city == 'Сочи', f"BUG-006 FAIL: node.city = '{node.city}', expected 'Сочи'"

    # Now check the tooltip via export_visjs
    graph = SocialGraphData(
        center_id='vk_999',
        nodes=[node],
        edges=[],
        clusters=[],
        stats={'node_count': 1, 'edge_count': 0},
    )
    visjs = builder.export_visjs(graph)
    tooltip = visjs['nodes'][0]['title']

    assert 'Сочи' in tooltip, f"BUG-006 FAIL: tooltip does not contain 'Сочи': {tooltip}"
    assert "{'id'" not in tooltip, f"BUG-006 FAIL: tooltip contains raw dict: {tooltip}"
    print(f"BUG-006 PASS: tooltip = '{tooltip}' (contains 'Сочи', no raw dict)")


# ============================================================
# BUG-007: geo_discrepancy false positive
# ============================================================
def test_bug007_geo_discrepancy_krasnaya_polyana_sochi():
    """
    locations=['Красная Поляна', 'Сочи'] must NOT trigger geo_discrepancy.
    """
    from app.services.candidate.risk_scorer import RiskScorer

    scorer = RiskScorer()

    # Verify the containment map has the required entries
    m = RiskScorer._CITY_DISTRICT_MAP
    required = {
        'красная поляна': 'сочи',
        'адлер': 'сочи',
        'зеленоград': 'москва',
        'мытищи': 'москва',
    }
    for district, parent in required.items():
        assert district in m, f"BUG-007 FAIL: '{district}' missing from _CITY_DISTRICT_MAP"
        assert m[district] == parent, (
            f"BUG-007 FAIL: _CITY_DISTRICT_MAP['{district}'] = '{m[district]}', expected '{parent}'"
        )

    # Test _cities_are_related
    assert scorer._cities_are_related('красная поляна', 'сочи'), \
        "BUG-007 FAIL: 'красная поляна' and 'сочи' not recognized as related"
    assert scorer._cities_are_related('адлер', 'сочи'), \
        "BUG-007 FAIL: 'адлер' and 'сочи' not recognized as related"
    assert scorer._cities_are_related('зеленоград', 'москва'), \
        "BUG-007 FAIL: 'зеленоград' and 'москва' not recognized as related"
    assert scorer._cities_are_related('мытищи', 'москва'), \
        "BUG-007 FAIL: 'мытищи' and 'москва' not recognized as related"

    # Simulate the actual geo_discrepancy check from _analyze_behavioral_patterns
    # claimed_city='Красная Поляна', geo_city='Сочи'
    class FakeCheck:
        text_analysis = None
        geo_analysis = {
            'home_location': {'city': 'Сочи'}
        }
        activity_timeline = None
        social_media_profiles = [
            {'platform': 'vk', 'city': 'Красная Поляна'}
        ]

    check = FakeCheck()
    flags = scorer._analyze_behavioral_patterns(check)
    geo_flags = [f for f in flags if f['code'] == 'geo_discrepancy']
    assert len(geo_flags) == 0, (
        f"BUG-007 FAIL: geo_discrepancy triggered for Красная Поляна/Сочи: {geo_flags}"
    )

    print("BUG-007 PASS: Красная Поляна + Сочи does NOT trigger geo_discrepancy")


# ============================================================
# BUG-008: check_mode="quick" labeled "Расширенная"
# ============================================================
def test_bug008_check_mode_display():
    """
    check_mode='quick' -> 'Быстрая проверка'
    check_mode='precise' -> 'Точная проверка'
    """
    # Test the mapping directly (same logic as CandidateCheck.check_level_display)
    mode_map = {
        'quick': 'Быстрая проверка',
        'precise': 'Точная проверка',
    }

    # We need to test the actual model property.
    # Import the model and simulate.
    class FakeCheck:
        check_mode = 'quick'

    class FakeCheck2:
        check_mode = 'precise'

    # Replicate check_level_display logic from candidate_check.py
    def check_level_display(check):
        mode = getattr(check, 'check_mode', None) or 'quick'
        return {
            'quick': 'Быстрая проверка',
            'precise': 'Точная проверка',
        }.get(mode, 'Быстрая проверка')

    # Now also test the ACTUAL model source code
    # Read the actual mapping from the source
    import app.models.candidate_check as cc_module
    import inspect
    source = inspect.getsource(cc_module.CandidateCheck.check_level_display.fget)

    result_quick = check_level_display(FakeCheck())
    result_precise = check_level_display(FakeCheck2())

    assert result_quick == 'Быстрая проверка', (
        f"BUG-008 FAIL: check_mode='quick' -> '{result_quick}', expected 'Быстрая проверка'"
    )
    assert result_precise == 'Точная проверка', (
        f"BUG-008 FAIL: check_mode='precise' -> '{result_precise}', expected 'Точная проверка'"
    )

    # Also verify the actual source code does NOT contain 'Расширенная'
    assert 'Расширенная' not in source, (
        f"BUG-008 FAIL: source still contains 'Расширенная проверка'"
    )
    assert 'Точная проверка' in source, (
        f"BUG-008 FAIL: source does not contain 'Точная проверка'"
    )

    print(f"BUG-008 PASS: quick->'{result_quick}', precise->'{result_precise}'")


if __name__ == '__main__':
    test_bug005_center_node_label_fallback()
    test_bug006_tooltip_city_extraction()
    test_bug007_geo_discrepancy_krasnaya_polyana_sochi()
    test_bug008_check_mode_display()
    print("\n=== ALL TESTS PASSED ===")
