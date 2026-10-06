## Content Automation System
An end-to-end system for managing and automating content workflows for multiple formats and platforms.

The agents included on this branch are:

- `countdown`: script generation, media discovery and downloading, and video editing.
- `t2i`: text-to-image generation and evaluation.
- `i2i`: image-to-image generation and evaluation.
- `content` (in development): image-based video assembly, animation, captions,
  audio, and optional YouTube publishing.

Install with Python 3.11 or newer using `python -m pip install -e .`.
For development, use `python -m pip install -e ".[dev]"` and run `ruff check src`.

The countdown video-editing node invokes Node.js with a supplied JavaScript artifact,
so Node.js must be available on `PATH` for that step. Media downloads use the FFmpeg
executable supplied by `imageio-ffmpeg`.

The content agent's parallax animation uses a Transformers depth-estimation model
with PyTorch and Torchvision. YouTube publishing requires Google OAuth credentials;
local credentials under `src/content_automation_system/agents/content/credentials/`
are ignored by Git, and credentials directories are excluded from package builds.

*Author: Andrei Cătălin Olariu, andreicatalin.swl@gmail.com.*
