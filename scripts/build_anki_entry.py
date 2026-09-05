#!/usr/bin/env python3
"""Configure the optional writer on card 02, then run the canonical builder.

Card 02 (Hán Việt → Kanji): drawing is optional. A correct drawing auto-flips,
but the normal Anki Show Answer action always remains available.
Card 03 keeps its existing strict write-before-answer gate.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import builder.build_anki as core

core.Q_HV2K = r'''<div class="ht-card tappable" id="ht-write-root" data-side="front" data-kanji="{{Kanji}}" data-key="hv2k:{{Key}}" data-strokes="{{StrokeDataB64}}"><div class="eyebrow">Hán Việt → Kanji</div><div class="hv">{{HanViet}}</div><div class="disambig">Nghĩa: {{Meaning}}</div><div class="writer-wrap"><div class="writer-box tappable" id="ht-writer-box"></div><div class="writer-tools"><button type="button" id="ht-reset">Viết lại</button><button type="button" id="ht-hint">Gợi ý nét</button></div><div id="ht-writer-status" class="writer-status"></div></div><div class="small">Vẽ đúng sẽ tự lật thẻ. Nếu chưa vẽ được, bạn vẫn có thể lật thủ công để xem đáp án.</div></div>''' + core.WRITER_JS
core.A_HV2K = core.COMMON_BACK

if __name__ == '__main__':
    core.main()
