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
✅ **AI-Powered Mode** - Uses Pollinations AI for advanced prompt enhancement  
✅ **Offline Mode** - Works completely offline with local processing  
✅ **Graceful Fallback** - Falls back to local processing if API fails  
✅ **Non-English Support** - Translates prompts to English via AI  

## Installation

### Option 1: Clone to custom_nodes (Recommended)

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/galpt/comfy-intelliPrompt.git
```

### Option 2: Copy folder

1. Download or copy the `comfy-intelliPrompt` folder
2. Paste it into your ComfyUI's `custom_nodes/` directory
3. Restart ComfyUI

### Requirements

- ComfyUI
- Python 3.10+
- `requests` library (usually pre-installed with ComfyUI)

## Usage

1. After installation, find the **"✨ intelliPrompt"** node in the node list (under "utils" category)
2. Add it to your workflow between your prompt input and CLIPTextEncode
3. Configure:
   - **prompt**: Your input prompt
   - **seed**: Random seed (for AI mode consistency)
   - **use_api**: Enable/disable AI-powered processing
   - **quality_tags**: Additional tags to add (optional)

### Node Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| prompt | STRING | "A beautiful sunset..." | Your input prompt (positive or negative) |
| seed | INT | 42 | Random seed for AI API calls |
| use_api | BOOLEAN | True | Use Pollinations AI (True) or local only (False) |
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

When `use_api=False` or when API fails, intelliPrompt performs:

1. **Typo Correction**: Fixes 20+ common English typos
2. **Parenthesis Balancing**: Ensures `(` `)`, `[` `]`, `{` `}` are balanced
3. **Punctuation Fix**: Ensures prompt ends with `.`, `!`, or `?`
4. **Space Cleanup**: Removes multiple spaces, fixes spacing after punctuation
5. **Quality Enhancement**: Adds quality tags if none present

### AI Processing (optional)

When `use_api=True`, intelliPrompt sends the prompt to Pollinations AI which:
- Translates non-English to English
- Adds rich sensory details (lighting, mood, colors, atmosphere)
- Expands style references and artist mentions
- Avoids repetitive vocabulary
- Optimizes for text-to-image models

If the API fails, it automatically falls back to local processing.

## Why intelliPrompt?

Unlike other prompt optimizers, intelliPrompt:

1. **Never crashes** - Guaranteed fallback to local processing
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
