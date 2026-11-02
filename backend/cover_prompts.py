from . import core

from .cover_rules import PERSON_PRODUCT_RULES,DEFAULT_STYLE


def material(case,transcript):
    product_id=case.get('cover_product_id')
    product=core.get(product_id,'product') if product_id else None
    draft_id=case.get('cover_draft_id')
    if draft_id:
        draft=core.get(draft_id,'draft')
        if draft.get('case_id')!=case['id']:raise ValueError('只能选择关联此案例的原创文案')
        if draft.get('product_id')!=product_id:raise ValueError('原创文案关联的产品与当前选择不一致，请更换产品资料')
        transcript=core.note_read(draft['note']['path'])
    if not transcript.strip():raise ValueError('封面提示词需要文案，请先转写或补充文案')
    reference=None;image=None
    if case.get('cover_reference_case_id'):
        reference=core.get(case['cover_reference_case_id'],'case')
        if not reference.get('cover'):raise ValueError('所选参考案例没有封面图，请更换参考或填写样式说明')
        image=core.contained(core.media_root(),reference['cover'])
    return {'transcript':transcript,'topic_tags':case.get('publication_hashtags',[]),'person_product_rules':PERSON_PRODUCT_RULES,
        'product_name':product['name'] if product else '待填入本期真实产品',
        'product_material':core.note_read(product['note']['path']) if product else '尚未指定用户产品资料：按文案研究产品类别和展示方向，生成可替换产品占位方案。不得把参考视频中的属性、价格、功效认定为用户产品事实。最终产品名称、外观、规格以用户提供的产品资料和实拍参考图为准。',
        'product_notice':'已使用所选产品资料' if product else '未选择真实产品资料，已生成产品占位方案；使用前替换真实产品并附产品照片',
        'product_id':product_id,'draft_id':draft_id,'style_profile':core.settings()['cover_style_profile'],
        'reference_style':case.get('cover_reference_style',''),
        'reference_case_id':reference['id'] if reference else None,
        'reference_notice':'将实际输入参考封面图，不能仅以互动量断言其成功原因' if image else '没有参考图片；只使用用户提供的样式说明和固定设计规范，不声称完成视觉研究或验证爆款效果'},image

def assemble(result,material):
    if not material.get('product_id'):
        topic=next((t for t in material.get('topic_tags',[]) if isinstance(t,str) and t),'产品')[:6]
        result={**result,'封面主标题':topic+'观察笔记','副标题':'',
            '画面描述':'固定双主体：左侧为本人参考照片中的同一个真实人物，右侧为本期真实产品照片占位；暖白背景、炭黑标题、鼠尾草绿强调色、固定柔和侧光，沿用系列构图，不依据参考视频猜测产品外观。',
            '产品呈现':'[请替换为本期真实产品照片及已核实资料]。保留产品真实外形、颜色、材质和标识；未提供照片前不补造细节，不把研究视频中的参数当作本人产品参数。',
            '可变元素':'仅替换真实产品照片、与产品对应的标题文字及轻微持物姿势；本人面貌与系列风格保持不变。'}
    def value(key):
        v=result.get(key,'')
        if isinstance(v,dict):v=v.get('conclusion','')
        return v if isinstance(v,str) else ''
    if not value('画面描述') or not value('封面主标题'):raise ValueError('本地模型未返回完整封面方案，请重新生成')
    fixed=material['style_profile']
    if PERSON_PRODUCT_RULES not in fixed:fixed+='\n'+PERSON_PRODUCT_RULES
    prompt='请生成一张短视频封面。\n\n【固定系列风格：不可修改】\n'+fixed+'\n\n【本期内容】\n'
    for k in ('封面主标题','副标题','画面描述','产品呈现','可变元素'):prompt+=k+'：'+value(k)+'\n'
    prompt+='\n【约束】\n仅使用提供的产品真实信息；如需准确产品外观，请同时附上真实产品照片作为生成参考。不得添加未经证实的价格、效果或品牌标识。\n负面提示词：'+value('负面提示词')+'；杂乱背景、过多装饰、文字乱码、虚假宣传、擅自改变固定风格。'
    return {**result,'可复制的封面提示词':prompt,'固定风格版本':material['style_profile'],'参考来源说明':material['reference_notice'],'产品资料状态':material.get('product_notice',''),'本人参考要求':'生成图片时附本人参考照片及产品实拍图，提示词不臆测本人外貌','封面规则版本':'person-product-v2.1'}
