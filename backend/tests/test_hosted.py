"""Hosted routes must stay read-only and never turn failed feeds into simulated prices."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'frontend'))
from api import index


def test_hosted_routes_and_mutation_guard():
    client = TestClient(index.app)
    assert client.get('/api/health').json()['read_only'] is True
    assert client.post('/api/orders', json={}).status_code == 403
    assert client.get('/api/billing/status').json()['configured'] is False
    assert client.get('/api/unknown').status_code == 403


def test_failed_feeds_return_503():
    index.cached = None
    with patch.object(index, 'fetch_venue', AsyncMock(return_value=([], {'state':'unavailable'}))):
        result = TestClient(index.app).get('/api/analytics')
    assert result.status_code == 503
    assert 'prices' not in result.json()


def test_snapshot_contract_is_json_and_not_cached_by_browser():
    payload = {'timestamp': 123, 'prices': [], 'opportunities': []}
    with patch.object(index, 'snapshot', AsyncMock(return_value=payload)):
        response = TestClient(index.app).get('/api/analytics')
    assert response.json() == payload
    assert response.headers['cache-control'] == 'no-store'


def test_shared_core_matches_source():
    root = Path(__file__).resolve().parents[2]
    for copied in (root / 'frontend/hosted_core').rglob('*.py'):
        relative = copied.relative_to(root / 'frontend/hosted_core')
        assert copied.read_text() == (root / 'backend/app' / relative).read_text()


def test_empty_deployment_settings_use_defaults(monkeypatch):
    monkeypatch.setenv('MAX_PRICE_AGE_MS', '')
    monkeypatch.setenv('TRADE_NOTIONAL', '')
    from hosted_core.config import Settings
    assert Settings().max_price_age_ms == 5000
    assert Settings().trade_notional == 1000
