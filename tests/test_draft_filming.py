from backend import core, jobs
from tests.test_api import client


def test_filming_persists_per_card_and_keeps_text(client):
    first = jobs.draft_version('case', 'product', '第一句话。\n\n第二段。')
    other = jobs.draft_version('case', 'product', '另一篇文案。')
    note = core.note_read(first['note']['path'])
    url = '/api/drafts/' + first['id'] + '/filming'
    saved = client.patch(url, json={'filmed': True}).json()
    assert saved['filmed'] is True and saved['filmed_at']
    assert core.get(first['id'], 'draft')['filmed'] is True
    assert not core.get(other['id'], 'draft').get('filmed', False)
    assert core.note_read(first['note']['path']) == note
    assert client.patch(url, json={'filmed': True}).json()['filmed'] is True
    assert client.patch(url, json={'filmed': False}).json()['filmed_at'] is None
    assert core.get(first['id'], 'draft')['filmed'] is False


def test_cannot_mark_a_case_as_draft(client):
    case = core.put('case', {'title': 'case'})
    assert client.patch('/api/drafts/' + case['id'] + '/filming', json={'filmed': True}).status_code == 400
    assert 'filmed' not in core.get(case['id'])
