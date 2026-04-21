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
- Falls back to local processing on API failure
- Supports conservative negative-prompt cleanup without enrichment
- No external API dependency for local processing mode
- Includes a preset-based latent generator for common output sizes

Installation:
1. Copy this folder to ComfyUI/custom_nodes/
2. Restart ComfyUI
3. Find "intelliPrompt" and the resolution preset latent node in the node list

License: GPL-3.0
Repository: https://github.com/galpt/comfy-intelliPrompt
"""

import math
import re
from typing import Optional, Tuple

import requests
import torch

try:
    import comfy.model_management
except ImportError:  # pragma: no cover - only available inside ComfyUI runtime
    comfy = None


class intelliPrompt:
    """
    intelliPrompt - Intelligent Prompt Optimizer for ComfyUI

    Two modes:
    1. API mode (default): Uses Pollinations AI for advanced optimization
    2. Local mode: Performs basic local processing (no API needed)
    """

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

    SEED_FALLBACK = 42
    SEED_MAX = 9_999_999_999

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "A beautiful sunset over the mountains",
                        "placeholder": "Edit the prompt here. Leave downstream CLIPTextEncode text blank.",
                        "tooltip": "Write the prompt in this node. The optimized output should feed into CLIPTextEncode, whose text box stays blank.",
                    },
                ),
                "optimizer_seed": (
                    "INT",
                    {
                        "default": cls.SEED_FALLBACK,
                        "min": 0,
                        "max": cls.SEED_MAX,
                        "step": 1,
                        "tooltip": "Seed used only by intelliPrompt optimization. Renamed to avoid ComfyUI special-casing of inputs literally named 'seed'.",
                    },
                ),
                "use_api": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Use Pollinations API for advanced optimization. Disable to use local processing only. Ignored when preserve_negative_terms is enabled.",
                    },
                ),
                "preserve_negative_terms": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Enable for negative prompts. Uses conservative local cleanup only, preserves negative terms, and disables API and quality-tag enrichment.",
                    },
                ),
            },
            "optional": {
                "quality_tags": (
                    "STRING",
                    {
                        "default": "masterpiece, best quality, detailed",
                        "tooltip": "Optional quality enhancement tags used only in normal local mode. Ignored when preserve_negative_terms is enabled or when API output is used.",
                    },
                )
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("optimized_prompt",)
    FUNCTION = "optimize_prompt"
    CATEGORY = "utils"
    DESCRIPTION = "Edit prompts here, keep downstream CLIPTextEncode text blank, and output optimized prompt text. Enable preserve_negative_terms for negative prompts."

    TYPO_REPLACEMENTS = {
        r"\bteh\b": "the",
        r"\brecieve\b": "receive",
        r"\boccured\b": "occurred",
        r"\bdefinately\b": "definitely",
        r"\bseperate\b": "separate",
        r"\buntill\b": "until",
        r"\bthier\b": "their",
        r"\bwierd\b": "weird",
        r"\boriginaly\b": "originally",
        r"\bbegining\b": "beginning",
        r"\bOccuring\b": "occurring",
        r"\bbeleive\b": "believe",
        r"\benviroment\b": "environment",
        r"\bgoverment\b": "government",
    }

    POSITIVE_ONLY_REPLACEMENTS = {
        r"\brealistic\b": "photorealistic",
        r"\banime\b": "anime style",
        r"\bmanga\b": "manga style",
        r"\bportait\b": "portrait",
        r"\blanscape\b": "landscape",
        r"\bgeneraton\b": "generation",
    }

    QUALITY_TAGS = [
        "masterpiece",
        "best quality",
        "highly detailed",
        "professional",
        "beautiful lighting",
        "sharp focus",
        "8k resolution",
        "cinematic lighting",
    ]

    def __init__(self):
        self.api_url = "https://text.pollinations.ai/"

    @classmethod
    def _coerce_seed(cls, raw_seed) -> int:
        fallback = cls.SEED_FALLBACK

        try:
            if raw_seed is None or isinstance(raw_seed, bool):
                raise ValueError("invalid seed")

            if isinstance(raw_seed, str):
                cleaned = raw_seed.strip()
                if not cleaned or cleaned.lower() in {"nan", "none", "null", "undefined"}:
                    raise ValueError("invalid seed string")
                if re.fullmatch(r"[-+]?\d+", cleaned):
                    parsed = int(cleaned)
                else:
                    parsed_float = float(cleaned)
                    if not math.isfinite(parsed_float):
                        raise ValueError("non-finite seed")
                    parsed = int(parsed_float)
            elif isinstance(raw_seed, float):
                if not math.isfinite(raw_seed):
                    raise ValueError("non-finite seed")
                parsed = int(raw_seed)
            else:
                parsed = int(raw_seed)
        except (TypeError, ValueError, OverflowError):
            parsed = fallback

        return max(0, min(parsed, cls.SEED_MAX))

    def _apply_replacements(self, prompt: str, replacements: dict) -> str:
        updated = prompt
        for pattern, replacement in replacements.items():
            updated = re.sub(pattern, replacement, updated, flags=re.IGNORECASE)
        return updated

    def _balance_delimiters(self, text: str) -> str:
        optimized = text

        open_parens = optimized.count("(")
        close_parens = optimized.count(")")
        if open_parens > close_parens:
            optimized += ")" * (open_parens - close_parens)
        elif close_parens > open_parens:
            for _ in range(close_parens - open_parens):
                idx = optimized.rfind(")")
                if idx > 0:
                    optimized = optimized[:idx] + optimized[idx + 1 :]

        open_brackets = optimized.count("[")
        close_brackets = optimized.count("]")
        if open_brackets > close_brackets:
            optimized += "]" * (open_brackets - close_brackets)
        elif close_brackets > open_brackets:
            for _ in range(close_brackets - open_brackets):
                idx = optimized.rfind("]")
                if idx > 0:
                    optimized = optimized[:idx] + optimized[idx + 1 :]

        open_braces = optimized.count("{")
        close_braces = optimized.count("}")
        if open_braces > close_braces:
            optimized += "}" * (open_braces - close_braces)
        elif close_braces > open_braces:
            for _ in range(close_braces - open_braces):
                idx = optimized.rfind("}")
                if idx > 0:
                    optimized = optimized[:idx] + optimized[idx + 1 :]

        return optimized

    def _normalize_prompt_text(self, text: str) -> str:
        normalized = re.sub(r"\s+", " ", text)
        normalized = re.sub(r",+", ",", normalized)
        normalized = re.sub(r"\s*,\s*", ", ", normalized)
        normalized = re.sub(r"([,.!?])([a-zA-Z])", r"\1 \2", normalized)
        return normalized.strip(" ,")

    def _local_process(self, prompt: str, quality_tags: str, preserve_negative_terms: bool = False) -> str:
        if not prompt or not prompt.strip():
            return ""

        optimized = prompt.strip()

        optimized = self._apply_replacements(optimized, self.TYPO_REPLACEMENTS)
        if not preserve_negative_terms:
            optimized = self._apply_replacements(optimized, self.POSITIVE_ONLY_REPLACEMENTS)

        optimized = self._balance_delimiters(optimized)
        optimized = self._normalize_prompt_text(optimized)

        if preserve_negative_terms:
            return optimized

        if optimized and optimized[-1] not in '.!?,"\'':
            optimized += "."

        if quality_tags:
            tags_to_add = [tag.strip() for tag in quality_tags.split(",") if tag.strip()]
            for tag in tags_to_add:
                if tag.lower() not in optimized.lower():
                    optimized = f"{tag}, {optimized}"

        has_quality = any(qt.lower() in optimized.lower() for qt in self.QUALITY_TAGS)
        if not has_quality:
            optimized = "masterpiece, best quality, highly detailed, " + optimized

        return optimized

    def _api_process(self, prompt: str, optimizer_seed: int) -> Optional[str]:
        try:
            payload = {
                "messages": [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"Prompt: {prompt}"},
                ],
                "seed": self._coerce_seed(optimizer_seed),
                "model": "openai",
            }
            headers = {"Content-Type": "application/json"}

            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                result = response.text.strip()
                if result:
                    return result

        except requests.exceptions.Timeout:
            print("[intelliPrompt] API timeout - using local processing")
        except requests.exceptions.RequestException as exc:
            print(f"[intelliPrompt] API error: {exc}")
        except Exception as exc:
            print(f"[intelliPrompt] Unexpected error: {exc}")

        return None

    def optimize_prompt(
        self,
        prompt: str,
        optimizer_seed: int = SEED_FALLBACK,
        use_api: bool = True,
        preserve_negative_terms: bool = False,
        quality_tags: str = "",
    ) -> Tuple[str]:
        if not prompt or not prompt.strip():
            return ("",)

        safe_seed = self._coerce_seed(optimizer_seed)

        if use_api and not preserve_negative_terms:
            api_result = self._api_process(prompt, safe_seed)
            if api_result:
                return (api_result,)

        optimized = self._local_process(prompt, quality_tags, preserve_negative_terms=preserve_negative_terms)
        return (optimized,)


class IntelliPromptResolutionPresetLatent:
    RESOLUTION_PRESETS = {
        "768 x 1344: Vertical (9:16)": (768, 1344),
        "915 x 1144: Portrait (4:5)": (915, 1144),
        "1024 x 1024: square 1:1": (1024, 1024),
        "1182 x 886: Photo (4:3)": (1182, 886),
        "1254 x 836: Landscape (3:2)": (1254, 836),
        "1365 x 768: Widescreen (16:9)": (1365, 768),
        "1564 x 670: Cinematic (21:9)": (1564, 670),
    }
    DEFAULT_PRESET = "1024 x 1024: square 1:1"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "preset": (
                    list(cls.RESOLUTION_PRESETS.keys()),
                    {
                        "default": cls.DEFAULT_PRESET,
                        "tooltip": "Choose a render size preset instead of editing width and height manually. Decoded output follows latent-grid rounding to the nearest lower multiple of 8 when a label is not divisible by 8.",
                    },
                ),
                "batch_size": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 4096,
                        "step": 1,
                    },
                ),
            }
        }

    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("latent",)
    FUNCTION = "generate"
    CATEGORY = "latent"
    DESCRIPTION = "Creates an empty latent using named resolution presets for projx workflows. Output dimensions round down to the nearest lower multiple of 8 when needed."

    @staticmethod
    def _intermediate_device():
        if "comfy" in globals() and comfy is not None:
            return comfy.model_management.intermediate_device()
        return "cpu"

    def generate(self, preset: str, batch_size: int = 1):
        width, height = self.RESOLUTION_PRESETS.get(preset, self.RESOLUTION_PRESETS[self.DEFAULT_PRESET])
        latent = torch.zeros(
            [batch_size, 4, height // 8, width // 8],
            device=self._intermediate_device(),
        )
        return ({"samples": latent},)


NODE_CLASS_MAPPINGS = {
    "intelliPrompt": intelliPrompt,
    "IntelliPromptResolutionPresetLatent": IntelliPromptResolutionPresetLatent,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "intelliPrompt": "✨ intelliPrompt",
    "IntelliPromptResolutionPresetLatent": "🖼️ Resolution Preset Latent",
}
