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

import importlib
import math
import re
from functools import lru_cache
from typing import Optional, Tuple


@lru_cache(maxsize=None)
def _guarded_import(module_name: str):
    try:
        return importlib.import_module(module_name), None
    except Exception as exc:  # pragma: no cover - depends on host runtime
        return None, exc


def _get_optional_module(module_name: str):
    module, _ = _guarded_import(module_name)
    return module


def _get_optional_import_error(module_name: str):
    _, error = _guarded_import(module_name)
    return error


def _format_missing_dependency(module_name: str, context: str) -> str:
    error = _get_optional_import_error(module_name)
    details = f" ({error})" if error else ""
    return f"{context} requires optional dependency '{module_name}' at runtime{details}."


def _get_requests_exception(name: str):
    requests_module = _get_optional_module("requests")
    if requests_module is None:
        return None

    exceptions_module = getattr(requests_module, "exceptions", None)
    exception_type = getattr(exceptions_module, name, None)
    if isinstance(exception_type, type) and issubclass(exception_type, Exception):
        return exception_type
    return None


def _balance_delimiter_pair(text: str, open_char: str, close_char: str) -> str:
    balanced = []
    depth = 0

    for char in text:
        if char == open_char:
            depth += 1
            balanced.append(char)
        elif char == close_char:
            if depth > 0:
                depth -= 1
                balanced.append(char)
        else:
            balanced.append(char)

    if depth > 0:
        balanced.append(close_char * depth)

    return "".join(balanced)


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
    API_TIMEOUT_SECONDS = 10
    _warned_api_fallbacks = set()

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
        optimized = _balance_delimiter_pair(optimized, "(", ")")
        optimized = _balance_delimiter_pair(optimized, "[", "]")
        optimized = _balance_delimiter_pair(optimized, "{", "}")
        return optimized

    @classmethod
    def _warn_api_fallback(cls, key: str, message: str):
        if key in cls._warned_api_fallbacks:
            return

        cls._warned_api_fallbacks.add(key)
        print(f"[intelliPrompt] {message}")

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
        requests_module = _get_optional_module("requests")
        if requests_module is None:
            self._warn_api_fallback(
                "missing-requests",
                "API mode unavailable because requests is missing; using local processing.",
            )
            return None

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

            response = requests_module.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=self.API_TIMEOUT_SECONDS,
            )

            if response.status_code == 200:
                result = response.text.strip()
                if result:
                    return result
                self._warn_api_fallback(
                    "empty-response",
                    "API returned an empty response; using local processing.",
                )
            else:
                self._warn_api_fallback(
                    f"status-{response.status_code}",
                    f"API returned status {response.status_code}; using local processing.",
                )

        except Exception as exc:
            timeout_exception = _get_requests_exception("Timeout")
            request_exception = _get_requests_exception("RequestException")

            if timeout_exception and isinstance(exc, timeout_exception):
                self._warn_api_fallback(
                    "timeout",
                    f"API timeout after {self.API_TIMEOUT_SECONDS}s; using local processing.",
                )
            elif request_exception and isinstance(exc, request_exception):
                self._warn_api_fallback(
                    f"request-{type(exc).__name__}",
                    f"API request error ({type(exc).__name__}); using local processing.",
                )
            else:
                self._warn_api_fallback(
                    f"unexpected-{type(exc).__name__}",
                    f"Unexpected API error ({type(exc).__name__}); using local processing.",
                )

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
        comfy_model_management = _get_optional_module("comfy.model_management")
        if comfy_model_management is not None:
            try:
                return comfy_model_management.intermediate_device()
            except Exception as exc:  # pragma: no cover - host runtime specific
                print(f"[intelliPrompt] Unable to resolve Comfy intermediate device: {exc}")
        return "cpu"

    def generate(self, preset: str, batch_size: int = 1):
        torch_module = _get_optional_module("torch")
        if torch_module is None:
            raise RuntimeError(
                _format_missing_dependency("torch", "IntelliPromptResolutionPresetLatent.generate()")
            )

        width, height = self.RESOLUTION_PRESETS.get(preset, self.RESOLUTION_PRESETS[self.DEFAULT_PRESET])
        latent = torch_module.zeros(
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
