import re

from backend import core, dify, jobs, spoken
from tests.test_api import client

EXAMPLE = '这台工作台\n真的能帮你把\n短视频创作流程全搞定\n以前我做带货视频的时候\n总得翻一堆资料\n现在只要把抖音链接丢进去\n就能自动整理出口播稿和文案结构'


def test_user_line_breaks_and_words_survive():
    assert spoken.format_spoken(EXAMPLE) == EXAMPLE.replace("\n", "")
    paragraph = '这台工作台真的能帮你把短视频创作流程全搞定，以前我做带货视频的时候总得翻一堆资料，现在只要把抖音链接丢进去就能自动整理出口播稿和文案结构。'
    result = spoken.format_spoken(paragraph)
    assert result == paragraph.replace("，", "，\n\n")
    assert re.sub(r'\s', '', result) == re.sub(r'\s', '', paragraph)
    assert spoken.format_spoken(result) == result
    assert 'ViralLab' in spoken.format_spoken('ViralLab 工作台把视频研究和创作整理到一起，然后可以回看素材。')


def test_obsidian_web_export_and_revision_share_line_breaks(client):
    text = '这是第一段，保留完整意思。\n\n这是第二段，不逐字换行。'
    draft = jobs.draft_version('case', 'product', text)
    note = core.note_read(draft['note']['path'])
    formatted = '这是第一段，\n\n保留完整意思。\n\n这是第二段，\n\n不逐字换行。'
    assert formatted in spoken.plain_lines(note)
    assert client.get('/api/drafts/' + draft['id'] + '/export?format=txt').text == formatted
    assert formatted in spoken.plain_lines(client.get('/api/drafts/' + draft['id'] + '/export?format=md').text)
    web = client.get('/api/drafts').json()[0]['content']
    assert spoken.plain_lines(spoken.plain_body(web)) == formatted
    revised = client.post('/api/drafts/' + draft['id'] + '/versions', json={'content': '我自己修改的段落\n\n这一段要保留'}).json()
    assert client.get('/api/drafts/' + revised['id'] + '/export?format=txt').text == '我自己修改的段落\n\n这一段要保留'
    assert core.note_read(draft['note']['path']) == note


def test_generated_paragraphs_and_recovery_are_formatted(client, monkeypatch):
    case = core.put('case', {'title': '测试参考素材', 'transcript': '原始素材'})
    product = core.put('product', {'name': '测试产品', 'files': [], 'note': core.sync_note('产品资料', 'p', '测试产品', '测试资料')})
    monkeypatch.setattr(dify, 'validate_inputs', lambda *args: {})
    payload = dict(case_id=case['id'], product_id=product['id'], mode='prototype', request_key='layout-test')
    preview = client.post('/api/dify/preview', json=payload).json()
    assert spoken.FORMAT_REQUIREMENT in preview['inputs']['extra_requirements']
    task = client.post('/api/dify/generate', json=payload).json()
    monkeypatch.setattr(dify, 'upload', lambda *a: {})
    text = '这是单元测试中的一段长文案，现在需要根据口播停顿逐行展示，然后验证文字没有被修改。'
    monkeypatch.setattr(dify, 'run', lambda *a: {'final_copy': text})
    result = jobs.work(task)
    first = core.get(result['draft_id'], 'draft')
    exported = client.get('/api/drafts/' + first['id'] + '/export?format=txt').text
    assert exported == spoken.format_spoken(text)
    assert re.sub(r'\s', '', exported) == re.sub(r'\s', '', text)
    jobs.task_update(task['id'], status='interrupted', run_id='existing-layout-run')
    monkeypatch.setattr(dify, 'request', lambda *a: {'status': 'succeeded', 'outputs': {'final_copy': text}})
    recovered = client.post('/api/tasks/' + task['id'] + '/resume').json()
    assert recovered['result']['draft_id'] == first['id']
    assert len(core.records('draft')) == 1


def test_character_fragments_and_paragraphs():
    assert spoken.format_spoken("真的\n能\n帮你\n把\n脖子\n护\n好") == "真的能帮你把脖子护好"
    assert spoken.format_spoken("第一段。\n\n第二段。") == "第一段。\n\n第二段。"
    assert spoken.format_spoken("Hello\nworld") == "Hello world"


def test_sentence_lines_with_semantic_paragraphs():
    text = '它是一个 U 型的设计，后面有魔术贴，可以调整松紧。围好之后，整个脖子能有一个支撑。\n\n介绍这个产品，主要就是看中了这一点。'
    result = spoken.format_spoken(text)
    assert '调整松紧。\n\n围好之后' in result
    assert '一个支撑。\n\n介绍' in result
    assert re.sub(r'\s', '', result) == re.sub(r'\s', '', text)
    assert spoken.format_spoken(result) == result
    assert spoken.plain_lines(spoken.markdown_lines(result)) == result


def test_existing_draft_splits_at_each_comma_but_not_enumeration_marks():
    raw = '然后我看了一下，\n它能把这些结构，\n结合我本地存的产品资料，\n通过 Dify 工作流生成新文案，\n整个流程都是可回看的，\n就像把参考案例的结构，\n一点一点的拆解，\n再填进我自己的事实里。\n\n它不承诺你一定爆单，\n也不帮你自动发布，\n但它解决了创作时，\n找不到依据、版本混乱的痛点。'
    expected = '然后我看了一下，它能把这些结构，结合我本地存的产品资料，通过 Dify 工作流生成新文案，整个流程都是可回看的，就像把参考案例的结构，一点一点的拆解，再填进我自己的事实里。\n\n它不承诺你一定爆单，也不帮你自动发布，但它解决了创作时，找不到依据、版本混乱的痛点。'
    expected = expected.replace("，", "，\n\n")
    assert spoken.format_spoken(raw) == expected
    assert spoken.format_spoken(expected) == expected


def test_sentence_boundaries_preserve_quotes_numbers_and_words():
    raw = '你可能会问：“这个好用吗？”先看资料。规格是1.5厘米，价格1,200元。真的？！可以再确认。'
    expected = '你可能会问：“这个好用吗？”先看资料。\n\n规格是1.5厘米，\n\n价格1,200元。\n\n真的？！\n\n可以再确认。'
    assert spoken.format_spoken(raw) == expected


def test_saved_revision_uses_comma_paragraphs_without_changing_words(client):
    text = '它是一个 U 型的设计，\n后面有魔术贴，可以调整松紧。\n\n围好之后，整个脖子能有一个支撑。'
    first = jobs.draft_version('case', 'product', '原稿。')
    revised = client.post('/api/drafts/' + first['id'] + '/versions', json={'content': text}).json()
    expected = '它是一个 U 型的设计，\n\n后面有魔术贴，\n\n可以调整松紧。\n\n围好之后，\n\n整个脖子能有一个支撑。'
    assert client.get('/api/drafts/' + revised['id'] + '/export?format=txt').text == expected
    assert spoken.plain_body(spoken.plain_lines(core.note_read(revised['note']['path']))) == expected


def test_filming_does_not_reorder_old_drafts(client):
    first = jobs.draft_version('case', 'product', '旧稿。')
    latest = jobs.draft_version('case', 'product', '新稿。')
    client.patch('/api/drafts/' + first['id'] + '/filming', json={'filmed': True})
    assert [d['id'] for d in client.get('/api/drafts').json()][:2] == [latest['id'], first['id']]


def test_model_blank_lines_cannot_split_an_unfinished_sentence():
    raw = '它能把这些结构，\n\n结合产品资料，\n\n生成新文案。\n\n下一步再人工核对。'
    expected = '它能把这些结构，\n\n结合产品资料，\n\n生成新文案。\n\n下一步再人工核对。'
    assert spoken.format_spoken(raw) == expected
    assert spoken.format_spoken('真\n\n的\n\n能\n\n帮你。') == '真的能帮你。'


def test_historical_note_display_and_export_keep_original_untouched(client):
    text = '研究视频，整理产品，再写文案。'
    note = core.sync_note('原创文案', 'legacy-comma', '旧稿', text)
    draft = core.put('draft', {'title': '旧稿', 'note': note})
    before = core.note_read(note['path'])
    expected = '研究视频，\n\n整理产品，\n\n再写文案。'
    web = client.get('/api/drafts').json()[0]['content']
    assert spoken.plain_body(web) == expected
    assert client.get('/api/drafts/' + draft['id'] + '/export?format=txt').text == expected
    md = client.get('/api/drafts/' + draft['id'] + '/export?format=md').text
    assert spoken.plain_body(md) == expected
    assert core.note_read(note['path']) == before


def test_english_commas_and_quoted_commas_keep_numbers_intact():
    raw = 'ViralLab, keep facts, not guesses.金额1,299元，编号1.5。'
    expected = 'ViralLab,\n\nkeep facts,\n\nnot guesses.金额1,299元，\n\n编号1.5。'
    assert spoken.format_spoken(raw) == expected
    quoted = '他说“先研究，再创作”。'
    assert spoken.format_spoken(quoted) == '他说“先研究，\n\n再创作”。'
