# -*- coding: utf-8 -*-
"""
STT Engine Factory
"""

from loguru import logger
import config
from typing import Any

def get_transcriber() -> Any:
    """
    Get the configured STT transcriber instance.
    Returns either ParaformerTranscriber or FireRedASRTranscriber.
    """
    engine_type = getattr(config, 'STT_ENGINE', 'paraformer')
    
    if engine_type == "fireredasr":
        logger.info("🏭 Loading FireRedASR Engine...")
        from .engines.fireredasr import get_transcriber as get_firered
        return get_firered()
    else:
        logger.info("🏭 Loading Paraformer Engine...")
        from .engines.paraformer import get_transcriber as get_paraformer
        return get_paraformer()
