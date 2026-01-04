# -*- coding: utf-8 -*-
"""
STT Client
Communicates with the remote STT Service
"""

import requests
import numpy as np
import io
import soundfile as sf
import time
from loguru import logger
import config

class STTClient:
    """Client for STT Service"""
    
    def __init__(self, base_url: str = config.STT_SERVICE_URL):
        self.base_url = base_url
    
    def load_model(self):
        """Mock method for compatibility"""
        # Service should already have model loaded
        pass
    
    def transcribe(self, audio: np.ndarray, sample_rate: int = config.AUDIO_SAMPLE_RATE):
        """
        Transcribe audio via API
        """
        start_time = time.time()
        
        # Serialize numpy audio to WAV bytes
        try:
            with io.BytesIO() as bio:
                sf.write(bio, audio, sample_rate, format='WAV')
                bio.seek(0)
                audio_bytes = bio.read()
            
            # Send to API
            files = {'file': ('audio.wav', audio_bytes, 'audio/wav')}
            response = requests.post(f"{self.base_url}/transcribe", files=files, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                text = data.get("text", "")
                stats = data.get("stats", {})
                
                # Adjust stats with network time
                total_time = time.time() - start_time
                stats["client_total_time"] = total_time
                
                return text, stats
            else:
                logger.error(f"STT Service Error: {response.status_code} - {response.text}")
                return "", {}
                
        except Exception as e:
            logger.error(f"STT Client Error: {e}")
            return "", {}

# Global instance
_client = None

def get_transcriber():
    global _client
    if _client is None:
        _client = STTClient()
    return _client
