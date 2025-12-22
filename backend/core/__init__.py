"""
Core package for KaggleIngest v3.0
Provides single context file (TXT or TOON format) for each competition of kaggle,
containing all relevant metadata/information about the competition.
"""

__version__ = "3.0.0"

from .toon_encoder import (
                           ToonDecoder,
                           ToonEncoder,
                           decode_from_toon,
                           encode_to_toon,
                           json_to_toon,
                           toon_to_json,
)
