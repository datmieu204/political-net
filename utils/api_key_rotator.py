# utils/api_key_rotator.py

import os
import time
from typing import List, Optional
from dotenv import load_dotenv
import google.generativeai as genai

from utils._logger import get_logger
logger = get_logger("utils.api_key_rotator", log_file="logs/utils/api_key_rotator.log")


class APIKeyRotator:
    def __init__(self):
        load_dotenv(override=True)
        self.keys = self._load_api_keys()
        self.current_index = 0
        self.failed_keys = set()
        
        if not self.keys:
            raise ValueError("Not found any GOOGLE_API_KEY in the .env file")
        
        logger.info(f"Loaded {len(self.keys)} API keys")
        self._activate_current_key()
    
    def _load_api_keys(self) -> List[str]:
        keys = []
        
        main_key = os.getenv("GOOGLE_API_KEY")
        if main_key:
            keys.append(("GOOGLE_API_KEY", main_key))
        
        index = 1
        while True:
            key_name = f"GOOGLE_API_KEY_{index}"
            key_value = os.getenv(key_name)
            if not key_value:
                break
            keys.append((key_name, key_value))
            index += 1
        
        logger.info(f"Found keys: {[k[0] for k in keys]}")
        return keys
    
    def _activate_current_key(self):
        if self.current_index >= len(self.keys):
            raise Exception("All API keys have been exhausted!")
        
        key_name, key_value = self.keys[self.current_index]
        genai.configure(api_key=key_value)
        logger.info(f"Activated API key: {key_name}")
    
    def get_current_key_name(self) -> str:
        """
        Return the name of the current key
        """
        if self.current_index < len(self.keys):
            return self.keys[self.current_index][0]
        return "NO_KEY_AVAILABLE"
    
    def rotate_key(self, reason: str = "quota_exceeded") -> bool:
        current_key_name = self.get_current_key_name()
        self.failed_keys.add(current_key_name)
        
        logger.warning(f"Rotating key {current_key_name} due to: {reason}")
        
        self.current_index += 1
        
        if self.current_index >= len(self.keys):
            logger.error("All API keys exhausted!")
            return False
        
        self._activate_current_key()
        return True
    
    def handle_api_error(self, error: Exception) -> bool:
        error_str = str(error).lower()
        
        quota_errors = [
            "quota",
            "rate limit",
            "429",
            "resource_exhausted",
            "too many requests"
        ]
        
        is_quota_error = any(err in error_str for err in quota_errors)
        
        if is_quota_error:
            logger.warning(f"Quota error detected: {error}")
            return self.rotate_key(reason="quota_exceeded")
        else:
            logger.error(f"Non-quota error: {error}")
            return False
    
    def get_stats(self) -> dict:
        """
        Return statistics about key usage
        """
        return {
            "total_keys": len(self.keys),
            "current_key": self.get_current_key_name(),
            "current_index": self.current_index,
            "failed_keys": list(self.failed_keys),
            "remaining_keys": len(self.keys) - self.current_index - 1
        }


_rotator_instance: Optional[APIKeyRotator] = None


def get_api_key_rotator() -> APIKeyRotator:
    global _rotator_instance
    if _rotator_instance is None:
        _rotator_instance = APIKeyRotator()
    return _rotator_instance


def reset_api_key_rotator():
    global _rotator_instance
    _rotator_instance = None


if __name__ == "__main__":
    rotator = APIKeyRotator()
    for i in range(len(rotator.keys) + 1):
        success = rotator.rotate_key(reason="test")
        if not success:
            print("Reached end of keys")
            break
        time.sleep(0.5)
