from pathlib import Path

p = Path('builder/build_anki.py')
s = p.read_text(encoding='utf-8')

old = "  document.body.appendChild(overlay);"
new = "  /* Keep the fixed modal outside the body: on iOS/WKWebView the body is locked with position:fixed, and a body child can be shifted off-screen. */\n  document.documentElement.appendChild(overlay);"

if new in s:
    print('iPad modal host fix already present')
elif old in s:
    s = s.replace(old, new, 1)
    p.write_text(s, encoding='utf-8')
    print('Applied iPad modal host fix: overlay now lives under documentElement.')
else:
    raise SystemExit('Modal host source changed; refusing unsafe patch')

# Static regression: body locking must not contain the fixed overlay.
s = p.read_text(encoding='utf-8')
assert 'document.documentElement.appendChild(overlay);' in s
assert 'document.body.appendChild(overlay);' not in s
assert "document.body.style.position='fixed'" in s
assert '.comp-modal-body{min-height:0;overflow-y:auto' in s
print('Modal host/scroll-lock regression markers OK.')
