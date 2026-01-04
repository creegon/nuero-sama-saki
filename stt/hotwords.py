# -*- coding: utf-8 -*-
"""
热词配置 - 提升特定词汇的识别准确率

用法：将经常识别错误的词添加到 HOTWORDS 列表
"""

# 热词列表（经常识别错误的关键词）
HOTWORDS = [
    # 角色相关
    "小祥",
    "祥子",
    "丰川祥子",
    "睦",
    "丰川睦",
    "Ave Mujica",
    "月之森",

    # 常用词汇
    "钢琴",
    "作曲",
    "音乐会",
    "键盘",

    # 技术词汇（如果你的对话涉及）
    "live2d",
    "模型",
    "调试",
    "优化",

    # 根据你的实际使用添加...
    # 比如你发现总是识别错的词
]

# 热词权重（可选）
# 数值越大，优先级越高（范围：1-50）
HOTWORD_WEIGHTS = {
    "小祥": 50,     # 最高优先级
    "祥子": 50,
    "钢琴": 30,
    "作曲": 30,
}


def get_hotwords_with_weights():
    """
    获取带权重的热词字符串（FunASR 格式）

    Returns:
        str: "word1 weight1 word2 weight2 ..."
    """
    result = []
    for word in HOTWORDS:
        weight = HOTWORD_WEIGHTS.get(word, 20)  # 默认权重 20
        result.append(f"{word} {weight}")
    return " ".join(result)


def get_hotwords_list():
    """获取热词列表（简单格式）"""
    return HOTWORDS


# 示例：如何在 FunASR 中使用
"""
from funasr import AutoModel

model = AutoModel(
    model="paraformer-zh",
    ...
)

# 方式1：生成时指定热词
result = model.generate(
    input=audio,
    hotword=get_hotwords_with_weights()
)

# 方式2：使用热词列表
result = model.generate(
    input=audio,
    hotword=" ".join(HOTWORDS)
)
"""
