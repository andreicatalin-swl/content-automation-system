## Content Automation System
An end-to-end system for managing and automating content workflows for multiple formats and platforms.

The agents included on this branch are:

- `countdown`: script generation, media discovery and downloading, and video editing.
- `t2i`: text-to-image generation and evaluation.
- `i2i`: image-to-image generation and evaluation.

Install with Python 3.11 or newer using `python -m pip install -e .`.
For development, use `python -m pip install -e ".[dev]"` and run `ruff check src`.

The countdown video-editing node invokes Node.js with a supplied JavaScript artifact,
so Node.js must be available on `PATH` for that step. Media downloads use the FFmpeg
executable supplied by `imageio-ffmpeg`.

*Author: Andrei Cătălin Olariu, andreicatalin.swl@gmail.com.*
