# -*- coding: utf-8 -*-
"""
Live2D 表情和参数定义
参数值已放大以获得更明显的表情效果
"""

# 参数名常量
class Params:
    # 眼睛
    EYE_L_OPEN = "ParamEyeLOpen"
    EYE_R_OPEN = "ParamEyeROpen"
    EYE_L_SMILE = "ParamEyeLSmile"
    EYE_R_SMILE = "ParamEyeRSmile"
    EYE_BALL_X = "ParamEyeBallX"
    EYE_BALL_Y = "ParamEyeBallY"
    # 眉毛
    BROW_L_Y = "ParamBrowLY"
    BROW_R_Y = "ParamBrowRY"
    BROW_L_FORM = "ParamBrowLForm"
    BROW_R_FORM = "ParamBrowRForm"
    # 嘴
    MOUTH_FORM = "ParamMouthForm"
    MOUTH_OPEN_Y = "ParamMouthOpenY"
    # 脸红
    CHEEK = "ParamCheek"
    # 头部
    ANGLE_X = "ParamAngleX"
    ANGLE_Y = "ParamAngleY"
    ANGLE_Z = "ParamAngleZ"


# 基于参数的表情定义 (模型没有 .exp3.json 文件，需要用参数实现)
# 丰川祥子人设：大小姐、自称"本神明"、容易害羞
# 2025-01-01 更新：增大参数值使表情更明显

EXPRESSIONS = {
    # 默认表情 - 从容自信的大小姐
    "neutral": {},
    
    # 开心 - 眼睛弯弯
    "happy": {
        Params.EYE_L_SMILE: 1.0,
        Params.EYE_R_SMILE: 1.0,
        Params.MOUTH_FORM: 0.8,
        Params.BROW_L_Y: 0.5,
        Params.BROW_R_Y: 0.5,
        Params.CHEEK: 0.6,
    },
    
    # 难过
    "sad": {
        Params.BROW_L_Y: -0.5,
        Params.BROW_R_Y: -0.5,
        Params.BROW_L_FORM: 0.8,
        Params.BROW_R_FORM: 0.8,
        Params.MOUTH_FORM: -0.6,
        Params.EYE_L_OPEN: 0.5,
        Params.EYE_R_OPEN: 0.5,
    },
    
    # 生气 - "哈？！"
    "angry": {
        Params.BROW_L_FORM: 1.0,
        Params.BROW_R_FORM: 1.0,
        Params.BROW_L_Y: -0.8,
        Params.BROW_R_Y: -0.8,
        Params.EYE_L_OPEN: 1.3,
        Params.EYE_R_OPEN: 1.3,
        Params.MOUTH_FORM: -0.7,
    },
    
    # 思考 - 视线飘向一边
    "thinking": {
        Params.EYE_BALL_X: -0.8,
        Params.EYE_BALL_Y: 0.5,
        Params.BROW_L_Y: 0.6,
        Params.BROW_R_Y: 0.2,
        Params.ANGLE_Z: 8.0,
    },
    
    # 惊讶 - "欸？"
    "surprised": {
        Params.EYE_L_OPEN: 1.5,
        Params.EYE_R_OPEN: 1.5,
        Params.BROW_L_Y: 0.8,
        Params.BROW_R_Y: 0.8,
        Params.MOUTH_OPEN_Y: 0.5,
    },
    
    # 害羞 - 脸红！视线躲避
    "shy": {
        Params.CHEEK: 1.0,
        Params.EYE_L_SMILE: 0.8,
        Params.EYE_R_SMILE: 0.8,
        Params.EYE_BALL_X: 0.7,
        Params.EYE_L_OPEN: 0.5,
        Params.EYE_R_OPEN: 0.5,
        Params.ANGLE_Z: 10.0,
    },
    
    # 困惑
    "confused": {
        Params.BROW_L_Y: 0.7,
        Params.BROW_R_Y: -0.4,
        Params.EYE_BALL_X: 0.5,
        Params.ANGLE_Z: -8.0,
    },
    
    # 得意 - "哼~本神明"
    "smug": {
        Params.EYE_L_SMILE: 1.0,
        Params.EYE_R_SMILE: 0.7,
        Params.MOUTH_FORM: 0.9,
        Params.BROW_L_Y: 0.5,
        Params.BROW_R_Y: -0.2,
        Params.ANGLE_Z: 8.0,
        Params.CHEEK: 0.3,
    },
    
    # 嘟嘴 - 不高兴
    "pout": {
        Params.MOUTH_FORM: -1.0,
        Params.CHEEK: 0.8,
        Params.BROW_L_Y: -0.5,
        Params.BROW_R_Y: -0.5,
        Params.EYE_L_OPEN: 0.6,
        Params.EYE_R_OPEN: 0.6,
    },
    
    # 担心
    "worried": {
        Params.BROW_L_Y: 0.6,
        Params.BROW_R_Y: 0.6,
        Params.BROW_L_FORM: 0.8,
        Params.BROW_R_FORM: 0.8,
        Params.EYE_L_OPEN: 1.2,
        Params.EYE_R_OPEN: 1.2,
    },
    
    # 困/无聊
    "sleepy": {
        Params.EYE_L_OPEN: 0.2,
        Params.EYE_R_OPEN: 0.2,
        Params.BROW_L_Y: -0.5,
        Params.BROW_R_Y: -0.5,
        Params.ANGLE_Z: 10.0,
    },
    
    # 兴奋
    "excited": {
        Params.EYE_L_OPEN: 1.4,
        Params.EYE_R_OPEN: 1.4,
        Params.EYE_L_SMILE: 0.8,
        Params.EYE_R_SMILE: 0.8,
        Params.BROW_L_Y: 0.8,
        Params.BROW_R_Y: 0.8,
        Params.MOUTH_FORM: 1.0,
        Params.CHEEK: 0.7,
    },
    
    # 好奇
    "curious": {
        Params.EYE_L_OPEN: 1.4,
        Params.EYE_R_OPEN: 1.4,
        Params.BROW_L_Y: 0.7,
        Params.BROW_R_Y: 0.7,
        Params.ANGLE_X: 10.0,
        Params.ANGLE_Z: 8.0,
    },
    
    # 尴尬
    "embarrassed": {
        Params.CHEEK: 1.0,
        Params.EYE_L_OPEN: 0.4,
        Params.EYE_R_OPEN: 0.4,
        Params.EYE_BALL_Y: -0.5,
        Params.ANGLE_Z: 10.0,
    },
    
    # 调皮
    "mischievous": {
        Params.EYE_L_SMILE: 0.9,
        Params.EYE_R_SMILE: 0.5,
        Params.MOUTH_FORM: 0.8,
        Params.BROW_L_Y: 0.5,
        Params.BROW_R_Y: -0.3,
        Params.ANGLE_Z: -8.0,
    },
}
