"""
Entity Identification Module
Trích xuất thực thể và quan hệ từ câu hỏi chính trị Việt Nam
"""

from .entity_extractor import EntityExtractor, ENTITY_EXTRACTION_PROMPT

__all__ = ['EntityExtractor', 'ENTITY_EXTRACTION_PROMPT']
