# -*- coding: utf-8 -*-
from llm_service import clean_markdown_to_text

sample = """
1. 直击痛点（群名暴击流）：
   > “别轰炸了，这里是‘小丑之家’，大家都是亲家人，你在这红温什么？见外了不是？”

2. 顺势造梗（嘲笑他撤回）：
   > “哟，撤回这么快，急得红鼻子都掉了吧？”
   > “鼠鼠急眼咯，开始胡言乱语咯~”

3. 终极防御（发个表情包嘲讽）：
   > 直接甩刚才那首《小丑赞歌》或者大笑猫猫的表情包，回他一句：
   > “行了行了，知道你是顶梁柱了，下一个节目表演个什么？”
"""

cleaned = clean_markdown_to_text(sample)
print("=== CLEANED OUTPUT ===")
print(cleaned)
assert ">" not in cleaned
print("\n[+] 100% 验证通过：所有 '>' 引用符号已彻底根除！")
