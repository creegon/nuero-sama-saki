# -*- coding: utf-8 -*-
"""
VoxCPM TTS Engine - LoRA 微调版
使用 VoxCPM 1.5 + Sakiko LoRA 进行本地语音合成，支持流式播放
"""

import os
import sys
import time
import numpy as np
import sounddevice as sd
import torch
import soundfile as sf
import tempfile
import asyncio
from typing import Optional, Generator, List, Tuple
from loguru import logger
import config
from .emotion_data import get_emotion_audio

# (已移除 model_loader 导入)

class VoxCPMEngine:
    """VoxCPM TTS 引擎 - 支持流式播放"""
    
    def __init__(self):
        self._model = None
        self._sample_rate = 44100
        self._stream: Optional[sd.OutputStream] = None
        
        # RTF 监控
        self._rtf_history: List[float] = []
        self._rtf_window = 5
        self._health_monitor = None
        
        self.output_device = config.AUDIO_OUTPUT_DEVICE
    
    def initialize(self) -> bool:
        """初始化模型"""
        if self._model is not None:
            return True
            
        try:
            self._model = self._load_model()
            if self._model:
                self._sample_rate = self._model.tts_model.sample_rate
                return True
            return False
        except Exception as e:
            logger.error(f"VoxCPM 初始化失败: {e}")
            return False

    def _load_model(self):
        """加载 VoxCPM 模型（内联自原 model_loader.py）"""
        from voxcpm.core import VoxCPM
        
        model = None
        merged_weights_path = os.path.join(config.BASE_DIR, "checkpoints", "sakiko_merged", "tts_model_merged.pt")
        
        if os.path.exists(merged_weights_path):
            # 优先使用合并后的模型 (无 LoRA 开销，RTF < 1.0)
            logger.info("加载 VoxCPM 1.5 (合并后权重)...")
            voxcpm = VoxCPM.from_pretrained(
                hf_model_id="openbmb/VoxCPM1.5",
                load_denoiser=False,
                optimize=False,
                lora_config=None,  # 不注入 LoRA 层
                lora_weights_path=None,
            )
            
            # 加载合并后的权重
            logger.info(f"加载合并后权重: {merged_weights_path}")
            merged_state = torch.load(merged_weights_path, map_location="cuda")
            model_state = voxcpm.tts_model.state_dict()
            
            for key in merged_state:
                if key in model_state:
                    model_state[key] = merged_state[key]
            
            voxcpm.tts_model.load_state_dict(model_state, strict=False)
            logger.info("合并权重加载完成。")
            
        else:
            # 回退到 LoRA 模式 (较慢但可用)
            logger.warning(f"合并权重不存在: {merged_weights_path}，回退到 LoRA 模式")
            from voxcpm.model.voxcpm import LoRAConfig
            
            lora_config = LoRAConfig(
                enable_lm=True,
                enable_dit=True,
                enable_proj=False,
                r=32,
                alpha=16,
                dropout=0.0,
                target_modules_lm=["q_proj", "v_proj", "k_proj", "o_proj"],
                target_modules_dit=["q_proj", "v_proj", "k_proj", "o_proj"],
            )
            
            voxcpm = VoxCPM.from_pretrained(
                hf_model_id="openbmb/VoxCPM1.5",
                load_denoiser=False,
                lora_config=lora_config,
                lora_weights_path=config.VOXCPM_LORA_PATH,
                optimize=False,
            )
            
            if os.path.exists(config.VOXCPM_LORA_PATH):
                voxcpm.tts_model.set_lora_enabled(True)
        
        # ⭐ FP16 优化：减少约 2GB 显存，降低 RTF
        use_fp16 = getattr(config, "VOXCPM_USE_FP16", True)
        
        if use_fp16 and torch.cuda.is_available():
            try:
                # 1. 转换模型权重为 FP16
                voxcpm.tts_model = voxcpm.tts_model.half()
                # 2. 同步更新 config.dtype
                voxcpm.tts_model.config.dtype = "float16"
                logger.info("✓ TTS 模型已转换为 FP16（节省约 2GB 显存，RTF 更低）")
            except Exception as e:
                logger.warning(f"FP16 转换失败，保持默认精度: {e}")
        else:
            logger.info("✓ 保持默认精度 (FP16 已禁用或无 CUDA)")
        
        logger.info(f"VoxCPM 加载完成，采样率: {voxcpm.tts_model.sample_rate}Hz, 设备: cuda")
        return voxcpm

    def cleanup_cuda(self, aggressive: bool = False):
        """清理 CUDA 缓存 (缓解内存碎片化)"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            if aggressive:
                import gc
                gc.collect()

    def reload_model(self):
        """重新加载模型 (用于 RTF 退化时恢复)"""
        logger.warning("🔄 正在重新加载 VoxCPM 模型...")
        
        # 1. 彻底释放旧模型
        if self._model:
            del self._model
            self._model = None
            
        self.cleanup_cuda(aggressive=True)
        
        # 2. 重新加载
        if self.initialize():
            logger.info("✓ 模型重载成功")
            # 重置 RTF 历史
            self._rtf_history.clear()
        else:
            logger.error("❌ 模型重载失败!")
            if self._health_monitor:
                self._health_monitor.report_issue("tts_reload_failed", "模型重载失败")

    def set_health_monitor(self, health_monitor):
        """设置健康监控器"""
        self._health_monitor = health_monitor

    def record_rtf(self, rtf: float):
        """记录 RTF 并检查是否需要恢复"""
        self._rtf_history.append(rtf)
        if len(self._rtf_history) > self._rtf_window:
            self._rtf_history.pop(0)
            
        # 计算移动平均
        avg_rtf = sum(self._rtf_history) / len(self._rtf_history)
        
        if self._health_monitor:
            self._health_monitor.record_rtf(rtf)
            
            # 如果平均 RTF 持续过高 (> 1.5)，且不在健康监控器的冷却期内
            # 注意：HealthMonitor 会处理冷却逻辑，这里只需上报
            if avg_rtf > 1.5:
                pass # 交给 HealthMonitor 判断是否触发回调
    
    def _calculate_dynamic_cfg(self, text: str) -> float:
        """根据文本长度动态计算CFG值
        
        短句 (<20字): 高CFG (2.5) - 追求清晰度
        中句 (20-60字): 中CFG (2.0) - 平衡
        长句 (>60字): 低CFG (1.8) - 提高稳定性，减少错误累积
        """
        if not config.VOXCPM_USE_DYNAMIC_CFG:
            return config.VOXCPM_CFG_VALUE
        
        # 去除标点符号计算纯文本长度
        import re
        text_clean = re.sub(r'[，。！？、,.!?…\s]', '', text)
        length = len(text_clean)
        
        if length < 20:
            cfg = config.VOXCPM_CFG_SHORT
            logger.debug(f"📏 短句 ({length}字) → CFG={cfg}")
        elif length <= 60:
            cfg = config.VOXCPM_CFG_MEDIUM
            logger.debug(f"📏 中句 ({length}字) → CFG={cfg}")
        else:
            cfg = config.VOXCPM_CFG_LONG
            logger.debug(f"📏 长句 ({length}字) → CFG={cfg}")
        
        return cfg
    
    def _preprocess_text(self, text: str) -> str:
        """预处理文本以避免TTS问题"""
        import re
        
        # 1. 去除多余空格
        text = re.sub(r'\s+', ' ', text.strip())
        
        # 2. 限制长度（过长文本容易出问题）
        if len(text) > 150:
            logger.warning(f"文本过长 ({len(text)} 字)，截断到150字")
            text = text[:150]
        
        # 3. 移除特殊字符（可能导致异常）
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9，。！？、,.!?…\s]', '', text)
        
        # 4. 短文本处理（优化）
        # 去除标点符号计算纯文本长度
        text_no_punct = re.sub(r'[，。！？、,.!?…\s]', '', text)
        if len(text_no_punct) < 3:
            logger.warning(f"文本过短 ({len(text_no_punct)} 字): '{text}'，添加停顿符")
            # 添加停顿让TTS更稳定
            if not text.endswith('…'):
                text = text.rstrip(',.!?，。！？、') + '…'
        
        # 5. 🔥 结尾填充：防止音频被截断
        # 确保句子结尾有适当的标点，给VoxCPM足够的“结束信号”
        if text and len(text_no_punct) >= 3:  # 只处理正常长度的文本
            ending_puncts = ['。', '！', '？', '.', '!', '?', '…']
            has_ending = any(text.endswith(p) for p in ending_puncts)
            
            if not has_ending:
                # 没有结束标点，添加省略号作为缓冲
                text = text.rstrip() + '…'
                logger.debug(f"🔧 结尾填充: 添加省略号")
        
        # 6. 最终确保非空
        if not text or len(text) == 0:
            logger.warning("文本为空，使用默认文本")
            text = "嗯…"
        
        return text

 
    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def synthesize_streaming(
        self,
        text: str,
        prompt_wav_path: Optional[str] = None,
        prompt_text: Optional[str] = None,
        cfg_value: float = config.VOXCPM_CFG_VALUE,
        inference_timesteps: int = config.VOXCPM_INFERENCE_STEPS,
        emotion: Optional[str] = None,
    ) -> Generator[np.ndarray, None, None]:
        """
        流式生成语音
        
        Args:
            text: 要合成的文本
            prompt_wav_path: 参考音频路径 (可选)
            prompt_text: 参考音频对应文本 (可选)
            cfg_value: CFG 强度
            inference_timesteps: 推理步数
            emotion: 情感标签
        """
        if not self.initialize():
            logger.error("TTS 模型未初始化")
            yield np.zeros(1024, dtype=np.float32)
            return

        # 1. 自动选择情感参考音频 (如果未指定 prompt)
        if emotion and not prompt_wav_path and config.VOXCPM_USE_EMOTION_REF:
            prompt_wav_path, prompt_text = get_emotion_audio(emotion)
            if prompt_wav_path:
                logger.debug(f"🎭 使用情感参考音频 [{emotion}]: {os.path.basename(prompt_wav_path)}")

        # 2. 默认参考音频
        if not prompt_wav_path:
            prompt_wav_path = config.VOXCPM_PROMPT_WAV
            prompt_text = config.VOXCPM_PROMPT_TEXT

        # 文本预处理
        text = self._preprocess_text(text)
        
        # 🔥 动态CFG：根据文本长度自动调整
        if cfg_value == config.VOXCPM_CFG_VALUE:  # 只在使用默认值时动态调整
            cfg_value = self._calculate_dynamic_cfg(text)
        
        logger.info(f"🎵 TTS 合成: '{text}' (情感: {emotion or 'default'}, CFG: {cfg_value})")
        start_time = time.time()
        
        try:
            # 🔥 移除每次合成前的 cleanup_cuda()
            # torch.cuda.empty_cache() 会导致 GPU 同步，增加首包延迟
            # 只在 OOM 异常时清理即可
            
            # 3. 流式推理
            wav_generator = self._model.generate_streaming(
                text=text,
                prompt_wav_path=prompt_wav_path,
                prompt_text=prompt_text,
                cfg_value=cfg_value,
                inference_timesteps=inference_timesteps,
                max_len=2048
                # 注：retry_badcase 在 streaming 模式下不支持，已移除
            )

            
            # 4. 生成所有块
            full_wav_chunks = []
            first_chunk_Time = 0
            
            for i, chunk in enumerate(wav_generator):
                if i == 0:
                    first_chunk_Time = time.time() - start_time
                    logger.debug(f"⚡ 首包延迟: {first_chunk_Time*1000:.1f}ms")
                
                # float32 chunk
                yield chunk
                full_wav_chunks.append(chunk)

            # 5. 计算 RTF 并验证音频质量
            if full_wav_chunks:
                full_wav = np.concatenate(full_wav_chunks)
                audio_duration = len(full_wav) / self._sample_rate
                total_time = time.time() - start_time
                rtf = total_time / audio_duration if audio_duration > 0 else 0
                
                # 音频质量验证
                from .audio_validator import AudioValidator
                is_valid, reason = AudioValidator.validate(full_wav, self._sample_rate)
                if not is_valid:
                    logger.warning(f"⚠️ 音频质量异常: {reason}")
                
                logger.info(f"✓ 合成完成 (时长: {audio_duration:.1f}s, RTF: {rtf:.2f})")
                self.record_rtf(rtf)
                
        except Exception as e:
            logger.error(f"TTS 合成失败: {e}")
            if "CUDA out of memory" in str(e):
                self.cleanup_cuda(aggressive=True)

    def synthesize_and_play(
        self,
        text: str,
        prompt_wav_path: Optional[str] = None,
        prompt_text: Optional[str] = None,
        cfg_value: float = config.VOXCPM_CFG_VALUE,
        inference_timesteps: int = config.VOXCPM_INFERENCE_STEPS,
        on_first_chunk: Optional[callable] = None,
        emotion: Optional[str] = None,
    ):
        """边生成边播放"""
        try:
            # 初始化播放流
            if self._stream is None or not self._stream.active:
                self._stream = sd.OutputStream(
                    samplerate=self._sample_rate,
                    channels=1,
                    dtype=np.float32,
                    device=self.output_device
                )
                self._stream.start()

            for i, chunk in enumerate(self.synthesize_streaming(
                text, prompt_wav_path, prompt_text, cfg_value, inference_timesteps, emotion
            )):
                if i == 0 and on_first_chunk:
                    on_first_chunk()
                
                self._stream.write(chunk)
                
            # 这里的流不关闭，保持复用，直到对象销毁或错误

        except Exception as e:
            logger.error(f"播放失败: {e}")
            if self._stream:
                self._stream.close()
                self._stream = None

    def synthesize(
        self,
        text: str,
        output_path: Optional[str] = None,
        emotion: Optional[str] = None,
    ) -> Optional[np.ndarray]:
        """生成语音并保存到文件"""
        chunks = []
        for chunk in self.synthesize_streaming(text, emotion=emotion):
            chunks.append(chunk)
            
        if not chunks:
            return None
            
        full_wav = np.concatenate(chunks)
        
        if output_path:
            sf.write(output_path, full_wav, self._sample_rate)
            logger.info(f"已保存音频: {output_path}")
            
        return full_wav


# 全局单例
_engine: Optional[VoxCPMEngine] = None


def get_voxcpm_engine() -> VoxCPMEngine:
    """获取全局 VoxCPM 引擎实例"""
    global _engine
    if _engine is None:
        _engine = VoxCPMEngine()
    return _engine


if __name__ == "__main__":
    engine = VoxCPMEngine()
    
    if engine.initialize():
        test_texts = [
            "你好呀，见到你真开心！",
            "别用那种眼神看我，我不需要同情。",
        ]
        
        for text in test_texts:
            print(f"\n播放: {text}")
            engine.synthesize_and_play(text)
    else:
        print("VoxCPM 初始化失败")
