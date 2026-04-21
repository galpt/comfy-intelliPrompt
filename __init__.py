"""
ComfyUI intelliPrompt
=====================
An intelligent prompt optimizer for ComfyUI that enhances prompts for text-to-image models.

Features:
- Fixes typos and grammar
- Balances parentheses and punctuation
- Translates non-English prompts to English (via Pollinations API)
- Adds rich details (setting, colors, lighting, mood)
- Expands style references
- Falls back to original prompt on API failure
- No external API dependency for local processing mode

Installation:
1. Copy this folder to ComfyUI/custom_nodes/
2. Restart ComfyUI
3. Find "intelliPrompt" node in the node list

License: GPL-3.0
Repository: https://github.com/galpt/comfy-intelliPrompt
"""

import re
import json
import requests
from typing import Tuple, Optional

class intelliPrompt:
    """
    intelliPrompt - Intelligent Prompt Optimizer for ComfyUI
    
    Two modes:
    1. API mode (default): Uses Pollinations AI for advanced optimization
    2. Local mode: Performs basic local processing (no API needed)
    """
    
    # System prompt for Pollinations API
    SYSTEM_PROMPT = """You are an expert prompt engineer for text-to-image models.

Your task is to transform user prompts into optimized versions that:

1. Fix all typos and grammar errors
2. Balance incomplete parentheses, brackets, and braces
3. Complete incomplete sentences with proper punctuation
4. Add rich sensory details (colors, lighting, mood, atmosphere)
5. Translate non-English prompts to English
6. Expand style references and artist mentions
7. Avoid repetitive vocabulary
8. Keep prompts clear and under 200 tokens

Respond ONLY with the optimized prompt text. No explanations or formatting."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True, 
                    "default": "A beautiful sunset over the mountains",
                    "placeholder": "Enter your prompt here..."
                }),
                "seed": ("INT", {
                    "default": 42, 
                    "min": 0, 
                    "max": 9999999999,
                    "step": 1
                }),
                "use_api": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Use Pollinations API for advanced optimization. Disable to use local processing only (no external calls)."
                }),
            },
            "optional": {
                "quality_tags": ("STRING", {
                    "default": "masterpiece, best quality, detailed",
                    "tooltip": "Quality enhancement tags to add to the prompt"
                })
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("optimized_prompt",)
    FUNCTION = "optimize_prompt"
    CATEGORY = "utils"
    DESCRIPTION = "intelliPrompt - Intelligent prompt optimizer: fixes typos, balances parentheses, enhances details"

    # Class-level constants for common corrections
    TYPO_REPLACEMENTS = {
        # Common typos
        r'\bteh\b': 'the',
        r'\brecieve\b': 'receive',
        r'\boccured\b': 'occurred',
        r'\bdefinately\b': 'definitely',
        r'\bseperate\b': 'separate',
        r'\buntill\b': 'until',
        r'\bthier\b': 'their',
        r'\bwierd\b': 'weird',
        r'\boriginaly\b': 'originally',
        r'\bbegining\b': 'beginning',
        r'\bOccuring\b': 'occurring',
        r'\bbeleive\b': 'believe',
        r'\benviroment\b': 'environment',
        r'\bgoverment\b': 'government',
        # Common SD/AI art typos
        r'\brealistic\b': 'photorealistic',
        r'\banime\b': 'anime style',
        r'\bmanga\b': 'manga style',
        r'\bportait\b': 'portrait',
        r'\blanscape\b': 'landscape',
        r'\bgeneraton\b': 'generation',
    }
    
    QUALITY_TAGS = [
        "masterpiece",
        "best quality", 
        "highly detailed",
        "professional",
        "beautiful lighting",
        "sharp focus",
        "8k resolution",
        "cinematic lighting"
    ]

    def __init__(self):
        self.api_url = "https://text.pollinations.ai/"

    def _local_process(self, prompt: str, quality_tags: str) -> str:
        """
        Perform local prompt processing without API calls.
        Fixes common issues and enhances the prompt.
        """
        if not prompt or not prompt.strip():
            return ""
        
        optimized = prompt.strip()
        
        # Fix common typos
        for pattern, replacement in self.TYPO_REPLACEMENTS.items():
            optimized = re.sub(pattern, replacement, optimized, flags=re.IGNORECASE)
        
        # Fix unbalanced parentheses - count and fix
        open_parens = optimized.count('(')
        close_parens = optimized.count(')')
        if open_parens > close_parens:
            optimized += ')' * (open_parens - close_parens)
        elif close_parens > open_parens:
            # Remove extra closing parentheses from the end
            for _ in range(close_parens - open_parens):
                idx = optimized.rfind(')')
                if idx > 0:
                    optimized = optimized[:idx] + optimized[idx+1:]
        
        # Fix unbalanced brackets
        open_brackets = optimized.count('[')
        close_brackets = optimized.count(']')
        if open_brackets > close_brackets:
            optimized += ']' * (open_brackets - close_brackets)
        elif close_brackets > open_brackets:
            for _ in range(close_brackets - open_brackets):
                idx = optimized.rfind(']')
                if idx > 0:
                    optimized = optimized[:idx] + optimized[idx+1:]
        
        # Fix unbalanced braces
        open_braces = optimized.count('{')
        close_braces = optimized.count('}')
        if open_braces > close_braces:
            optimized += '}' * (open_braces - close_braces)
        elif close_braces > open_braces:
            for _ in range(close_braces - open_braces):
                idx = optimized.rfind('}')
                if idx > 0:
                    optimized = optimized[:idx] + optimized[idx+1:]
        
        # Fix missing punctuation at end
        if optimized and optimized[-1] not in '.!?,"\'':
            optimized += '.'
        
        # Fix multiple spaces
        optimized = re.sub(r'\s+', ' ', optimized)
        
        # Fix multiple commas
        optimized = re.sub(r',+', ',', optimized)
        
        # Fix missing spaces after punctuation
        optimized = re.sub(r'([,.!?])([a-zA-Z])', r'\1 \2', optimized)
        
        # Add quality tags if provided and not already present
        if quality_tags:
            tags_to_add = [t.strip() for t in quality_tags.split(',') if t.strip()]
            for tag in tags_to_add:
                if tag.lower() not in optimized.lower():
                    # Add at beginning with emphasis
                    optimized = f"{tag}, {optimized}"
        
        # Add default quality tags if none present
        has_quality = any(qt.lower() in optimized.lower() for qt in self.QUALITY_TAGS)
        if not has_quality:
            optimized = "masterpiece, best quality, highly detailed, " + optimized
        
        return optimized

    def _api_process(self, prompt: str, seed: int) -> Optional[str]:
        """
        Process prompt via Pollinations API with proper error handling.
        Returns optimized prompt or None if API fails.
        """
        try:
            payload = {
                "messages": [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"Prompt: {prompt}"}
                ],
                "seed": seed,
                "model": "openai",
            }
            headers = {
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                self.api_url, 
                json=payload, 
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.text.strip()
                # Ensure we got a valid response
                if result and len(result) > 0:
                    return result
                    
        except requests.exceptions.Timeout:
            print("[intelliPrompt] API timeout - using local processing")
        except requests.exceptions.RequestException as e:
            print(f"[intelliPrompt] API error: {e}")
        except Exception as e:
            print(f"[intelliPrompt] Unexpected error: {e}")
        
        # Return None to indicate API failed
        return None

    def optimize_prompt(self, prompt: str, seed: int, use_api: bool = True, quality_tags: str = "") -> Tuple[str]:
        """
        Main function to optimize a prompt.
        
        Args:
            prompt: Input prompt text
            seed: Random seed for API calls
            use_api: Whether to try Pollinations API first
            quality_tags: Additional quality tags to add
            
        Returns:
            Tuple containing optimized prompt string
        """
        if not prompt or not prompt.strip():
            return ("",)
        
        # First try API processing if enabled
        if use_api:
            api_result = self._api_process(prompt, seed)
            if api_result:
                return (api_result,)
        
        # Fall back to local processing
        optimized = self._local_process(prompt, quality_tags)
        return (optimized,)


# ComfyUI node registration
NODE_CLASS_MAPPINGS = {
    "intelliPrompt": intelliPrompt
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "intelliPrompt": "✨ intelliPrompt"
}