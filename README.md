# intelliPrompt for ComfyUI

An intelligent prompt optimizer for ComfyUI that automatically fixes typos, balances parentheses, enhances prompts with quality tags, and optionally uses AI for advanced prompt optimization.

![intelliPrompt](https://img.shields.io/badge/ComfyUI-intelliPrompt-blue)
![License](https://img.shields.io/badge/License-GPL--3.0-green)
![Python](https://img.shields.io/badge/Python-3.10+-yellow)

## Features

✅ **Typo Correction** - Fixes common English typos automatically  
✅ **Parentheses Balancing** - Fixes unbalanced `()`, `[]`, `{}`  
✅ **Punctuation Fix** - Ensures proper ending punctuation  
✅ **Quality Enhancement** - Adds quality tags (masterpiece, best quality, etc.)  
✅ **AI-Powered Mode** - Uses Pollinations AI for advanced prompt enhancement when optional API dependencies are available  
✅ **Offline Mode** - Works completely offline with local processing  
✅ **Graceful Fallback** - Missing API/runtime deps no longer block node registration; local mode still works  
✅ **Non-English Support** - Translates prompts to English via AI  
✅ **Lazy Torch Use** - The latent preset node registers even if `torch` is unavailable and only errors when executed  

## Installation

### Fresh install with comfy-sage

For a new `comfy-sage` install, the supported base/local flow is:

1. Bootstrap `comfy-sage` once with `./launch-comfy.sh`
2. Clone `comfy-intelliPrompt` into `ComfyUI/custom_nodes`
3. Relaunch `./launch-comfy.sh`
4. Use the node immediately in local mode without any manual `pip install` step

```bash
# from the unpacked comfy-sage directory
./launch-comfy.sh

# after the first launch completes
git clone https://github.com/galpt/comfy-intelliPrompt.git ComfyUI/custom_nodes/comfy-intelliPrompt

# relaunch so ComfyUI registers the node
./launch-comfy.sh
```

API mode is optional. If its extra dependency is not present or the API is unavailable, intelliPrompt still registers and falls back to local processing.

### Standard ComfyUI install

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/galpt/comfy-intelliPrompt.git
```

Restart ComfyUI after cloning.

### Option 2: Copy folder

1. Download or copy the `comfy-intelliPrompt` folder
2. Paste it into your ComfyUI's `custom_nodes/` directory
3. Restart ComfyUI

### Requirements

- ComfyUI
- Python 3.10+
- No extra Python packages are required for base/local prompt cleanup
- Optional API enrichment only applies when its runtime dependency is available
- `torch` is only required when executing `IntelliPromptResolutionPresetLatent`
- `comfy.model_management` is only used when available inside a ComfyUI runtime

## Usage

1. After installation, find the **"✨ intelliPrompt"** node in the node list (under "utils" category)
2. Add it to your workflow between your prompt input and CLIPTextEncode
3. Configure:
   - **prompt**: Your input prompt
   - **optimizer_seed**: Random seed (for AI mode consistency; protected from ComfyUI's special `seed` handling)
   - **use_api**: Enable/disable AI-powered processing
   - **preserve_negative_terms**: Conservative cleanup path for negative prompts
   - **quality_tags**: Additional tags to add (optional)

### Node Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| prompt | STRING | "A beautiful sunset..." | Your input prompt (positive or negative) |
| optimizer_seed | INT | 42 | Random seed for AI API calls |
| use_api | BOOLEAN | True | Use Pollinations AI (True) or local only (False) |
| preserve_negative_terms | BOOLEAN | False | Conservative local cleanup for negative prompts; disables enrichment/API |
| quality_tags | STRING | "masterpiece, best quality..." | Additional quality tags to add (optional) |

### Node Outputs

| Output | Type | Description |
|--------|------|-------------|
| optimized_prompt | STRING | The processed/optimized prompt |

## Workflow Example

```
[Prompt Input] --> [intelliPrompt] --> [CLIPTextEncode] --> [KSampler]
                    (node 21)          (node 6)             (node 3)
```

## How It Works

### Local Processing (always available)

When `use_api=False`, optional API support is unavailable, or the API fails, intelliPrompt performs:

1. **Typo Correction**: Fixes 20+ common English typos
2. **Parenthesis Balancing**: Ensures `(` `)`, `[` `]`, `{` `}` are balanced
3. **Punctuation Fix**: Ensures prompt ends with `.`, `!`, or `?`
4. **Space Cleanup**: Removes multiple spaces, fixes spacing after punctuation
5. **Quality Enhancement**: Adds quality tags if none present

### AI Processing (optional)

When `use_api=True` and optional API support is available, intelliPrompt sends the prompt to Pollinations AI which:
- Translates non-English to English
- Adds rich sensory details (lighting, mood, colors, atmosphere)
- Expands style references and artist mentions
- Avoids repetitive vocabulary
- Optimizes for text-to-image models

If the API is unavailable or fails, it automatically falls back to local processing.

### Runtime compatibility notes

- `__init__.py` avoids top-level imports of optional/runtime dependencies so missing extras do not break node registration.
- `intelliPrompt` always keeps a local fallback path available.
- `IntelliPromptResolutionPresetLatent` stays registered even in reduced environments; it raises a clear runtime error only if executed without `torch`.

## Why intelliPrompt?

Unlike other prompt optimizers, intelliPrompt:

1. **Keeps prompt cleanup available when API mode fails** - Falls back to local processing when API optimization is unavailable
2. **Works offline** - Local mode doesn't need internet
3. **Fast processing** - Local mode is instant
4. **Easy to use** - Simple node interface
5. **Open source** - GPL-3.0 licensed, community-driven

## Comparison

| Feature | intelliPrompt | ciga2011's PromptOptimizer |
|---------|--------------|---------------------------|
| Bug-free | ✅ Yes | ❌ No (unassigned variable bug) |
| Offline mode | ✅ Yes | ❌ No |
| Fallback on error | ✅ Yes | ❌ No |
| Typo correction | ✅ Yes | ❌ No |
| Parenthesis balancing | ✅ Yes | ❌ No |

## License

GPL-3.0 - Open source and free to use.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Acknowledgments

- Uses [Pollinations](https://pollinations.ai/) for AI-powered prompt optimization
- Inspired by the ComfyUI community's need for better prompt handling

## Links

- [GitHub Repository](https://github.com/galpt/comfy-intelliPrompt)
- [Report Issues](https://github.com/galpt/comfy-intelliPrompt/issues)
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
