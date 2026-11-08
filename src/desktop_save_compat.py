"""Observed FM27 save layouts; extends exact registrations, never disables checks.

Validated saves: 27.0.0+2486695 and 27.0.0+2493426. The latter keeps
summary/game/humans/tactics schemas 31/47/24/26. Plan flag 2 also occurs
in native standalone FMF plans, and does not change the slot layout.
This adapter is installed only inside the private save-reader process.
"""
from dataclasses import replace

PROFILE = 'fm27-save-2486695-2493426-v1'


def install():
    from fmsave import _layouts
    from fmsave._layouts import TacticsLayout
    if getattr(_layouts,'_fm27_desktop_profile',None)==PROFILE:
        return
    original=_layouts.registered_layouts()
    entries=[]
    for entry in original:
        if entry.build!='27.0.0+2486695':
            entries.append(entry)
            continue
        layout=entry.layout
        if isinstance(layout,TacticsLayout):
            # Keep user flag 0 and preset flag 1; add the observed user flag 2.
            layout=replace(layout,alternate_signature=layout.user_signature[:-1]+b'\x02')
        entries.append(replace(entry,layout=layout))
        entries.append(replace(entry,build='27.0.0+2493426',layout=layout))
    registered=tuple(entries)
    _layouts.registered_layouts=lambda:registered
    _layouts._fm27_desktop_profile=PROFILE
