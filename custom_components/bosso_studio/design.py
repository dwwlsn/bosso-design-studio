"""Pure design compiler and revision store. No network or HA dependencies."""
import asyncio
import re
from copy import deepcopy


def compile_strip(colors, count, sections):
    if type(count) is not int or not 1 <= count <= 8192:
        raise ValueError("LED count must be between 1 and 8192.")
    def palette(values):
        if not isinstance(values, list) or not 1 <= len(values) <= 8192:
            raise ValueError("Supply a nonempty list of RGB colors.")
        if not all(isinstance(v, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", v) for v in values):
            raise ValueError("Colors must use #RRGGBB.")
        return [v.upper() for v in values]
    def repeat(values, length):
        return [values[i % len(values)] for i in range(length)]
    strip = repeat(palette(colors), count)
    end = 0
    for section in sections:
        first, last = section["first"], section["last"]
        if type(first) is not int or type(last) is not int or not end < first <= last <= count:
            raise ValueError("Sections must be ordered, disjoint, 1-based inclusive ranges.")
        strip[first-1:last] = repeat(palette(section["colors"]), last-first+1)
        end = last
    return strip


class Library:
    def __init__(self, storage, designs):
        self.storage = storage
        self.designs = designs
        self.lock = asyncio.Lock()

    def get(self, key, revision=None):
        history = self.designs.get(key, [])
        revision = len(history) if revision is None else revision
        if type(revision) is not int or not 1 <= revision <= len(history):
            raise ValueError("Design revision not found.")
        return deepcopy(history[revision-1])

    async def save(self, key, base, record):
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", key):
            raise ValueError("Use a short lowercase design ID.")
        async with self.lock:
            history = self.designs.get(key, [])
            if base != len(history):
                raise ValueError(f"Revision conflict. Current revision is {len(history)}.")
            revision = base + 1
            updated = {**self.designs, key: [*history, {**deepcopy(record), "revision": revision}]}
            await self.storage.async_save(updated)
            self.designs = updated
            return {"id": key, "revision": revision}

