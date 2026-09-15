import httpx
import pytest
from backend.app.india import IndiaQuotes

@pytest.mark.asyncio
async def test_india_missing_credentials_does_not_invent_quotes(monkeypatch):
    monkeypatch.delenv('KITE_API_KEY', raising=False)
    monkeypatch.delenv('KITE_ACCESS_TOKEN', raising=False)
    result = await IndiaQuotes().snapshot()
    assert result['status'] == 'not_configured'
    assert len(result['stocks']) == 20
    assert all(s['price'] is None for s in result['stocks'])

@pytest.mark.asyncio
async def test_india_partial_quotes_and_auth_failure(monkeypatch):
    monkeypatch.setenv('KITE_API_KEY', 'test-key')
    monkeypatch.setenv('KITE_ACCESS_TOKEN', 'test-token')
    original = httpx.AsyncClient
    def handler(request):
        assert request.headers['Authorization'] == 'token test-key:test-token'
        assert 'NSE:RELIANCE' in request.url.params.get_list('i')
        return httpx.Response(200, json={'status':'success','data':{'NSE:RELIANCE':{'last_price':110,'ohlc':{'close':100},'timestamp':'2026-09-15 10:00:00'}}})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    result = await IndiaQuotes().snapshot()
    assert result['stocks'][0]['price'] == 110
    assert result['stocks'][0]['change_percent'] == 10
    assert result['stocks'][1]['price'] is None
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(lambda r:httpx.Response(403)), **kwargs))
    result = await IndiaQuotes().snapshot()
    assert result['status'] == 'unavailable'
    assert all(s['price'] is None for s in result['stocks'])
    assert 'test-token' not in str(result)
