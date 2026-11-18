# GBA Arabic Localization Pipeline & Patch

Technical localization tooling, custom pixel font assets, and binary differential patch (BPS) for Game Boy Advance.

## Overview

This repository contains the legal, non-infringing assets and tools for the Arabic fan translation:
- **Fonts (`fonts/`)**: Custom pixel font bitmaps, vector fonts, and character mapping tables.
- **Tools (`tools/`)**: Python pipeline for RTL text shaping, glyph bank generation, dynamic ROM injection, and BPS patch verification.
- **Patches (`patches/`)**: Binary differential patch (`khcom_us_arabic.bps`).
- **Translation (`translation/`)**: Translated dialogue and interface catalogues.
- **Documentation (`docs/`)**: Technical specifications, release notes, and glossary.

## Applying the Patch

The provided patch is in standard **BPS (Beat Patch System)** format. It contains solely binary byte differences and zero proprietary game assets.

1. Obtain a legally dumped, clean USA retail ROM (32 MB).
   - Target Base ROM SHA-1: `10729bd884f8fdca7a310b6d606c52e46657aa48`
2. Use any standard BPS-compatible patcher (such as Floating IPS or Rom Patcher JS).
3. Apply `patches/khcom_us_arabic.bps` to your clean ROM.

## Legal Disclaimer

This is a non-commercial, open-source fan translation project. 
This repository contains **NO ROMs, NO copyrighted game code, and NO copyrighted game audio/visual assets**. 
All trademarks and copyrights belong to their respective owners. Users must own and provide their own legally acquired copy of the original game to use the patch.

## License

All custom tooling and font generation scripts are licensed under the MIT License.
