"""HA-owned lighting designs, exposed as a dedicated MCP tool set."""
import asyncio
import base64
from copy import deepcopy
import re

import probatio as vol
from homeassistant.helpers import llm
from homeassistant.helpers.storage import Store
from homeassistant.loader import async_get_integration

from .design import Library, compile_strip

DOMAIN = "bosso_studio"

MAX_TEXT = vol.All(str, vol.Length(max=8000))
KEY = vol.All(str, vol.Length(min=1, max=64))
COLORS = [str]
SECTION = {"first": int, "last": int, "colors": COLORS}
ID = vol.Required("id")
REV = vol.Required("revision")


class StudioTool(llm.Tool):
    integration = DOMAIN

    def __init__(self, name, description, schema, callback, *, read=True, live=False):
        self.name = name
        self.description = description
        self.parameters = vol.Schema(schema, required=True)
        self.callback = callback
        self.annotations = llm.ToolAnnotations(read_only=read, destructive=live,
                                              idempotent=read, open_world=live or name=="BossoInspectPreset")

    async def async_call(self, hass, tool_input, llm_context):
        try:
            result = await self.callback(**tool_input.tool_args)
        except (ValueError, KeyError) as err:
            return llm.ToolResult(data={"error": str(err)}, error=True)
        return llm.ToolResult(data=result)


class StudioAPI(llm.API):
    async def async_get_api_instance(self, llm_context):
        return llm.APIInstance(api=self, llm_context=llm_context, tools=self.studio_tools,
            api_prompt="Retrieve the current revision before editing. Save and preview are local. Only apply when explicitly asked to change the physical lights.")


async def async_setup_entry(hass, entry):

    from custom_components.bosso.presets import get_device_i_array, get_zones_i_array
    verified_version = (await async_get_integration(hass, "bosso")).version
    store = Store(hass, 1, DOMAIN + ".designs", private=True, atomic_writes=True)
    library = Library(store, await store.async_load() or {})
    apply_lock = asyncio.Lock()

    def target():
        if str(verified_version).lstrip("v") != "2.1.0":
            raise ValueError("Bosso adapter requires verified version 2.1.0.")
        accounts = hass.data.get("bosso", {})
        if len(accounts) != 1:
            raise ValueError("Configure exactly one Bosso account to use this adapter.")
        coordinator = next(iter(accounts.values()))
        if coordinator is None or len(coordinator.data or {}) != 1:
            raise ValueError("Expected exactly one device on the Bosso account.")
        return coordinator, next(iter(coordinator.data))

    async def inspect(preset, category="predefined"):
        coord, device = target()
        catalog = (coord.predefined_preset_name_to_id if category=="predefined"
                   else coord.user_preset_name_to_id)
        if preset not in catalog:
            raise ValueError("Preset name not found in the selected catalog.")
        data = await coord.api.async_get_preset(catalog[preset])
        config = await coord.api.async_get_device_config(device)
        counts = [int(config.get(f"data_{n}_led_count") or 0) for n in range(1, 5)]
        pixels = get_device_i_array(data) or get_zones_i_array(data) or []
        if len(pixels) > 8192:
            raise ValueError("Reference exceeds supported strip length.")
        fields = ("fx","sx","ix","pal","col","c1x","c2x","c3x","rev","mi","cct")
        return {"name":preset,"category":category,"device":device,"channels":counts,
                "colors_from_bosso":pixels,"state":{k:data[k] for k in fields if k in data}}

    async def listing():
        return {"designs":[{"id":k,"revision":len(v)} for k,v in sorted(library.designs.items())]}

    async def get(id, revision=None):
        record = library.get(id,revision)
        record["images"] = [{"type": item["type"], "index": i} for i,item in enumerate(record.get("images",[]))]
        return record

    async def image(id, revision, index):
        images = library.get(id,revision).get("images",[])
        if not 0 <= index < len(images):
            raise ValueError("Image index out of range.")
        return images[index]

    async def save(id, base_revision, brief, colors, led_count, sections=None, references="", images=None, preset=None, category="predefined"):
        sections = sections or []
        compile_strip(colors, led_count, sections)
        previous = library.get(id,base_revision) if base_revision else {}
        source = await inspect(preset, category) if preset else previous.get("source")
        if images is None:
            images = previous.get("images", [])
        if len(images) > 3:
            raise ValueError("At most three reference images per design.")
        for item in images:
            raw = item["data"]
            if len(raw) > 1400000:
                raise ValueError("Each reference image must be 1 MiB or smaller.")
            image = base64.b64decode(raw, validate=True)
            signature = bytes.fromhex("89504e470d0a1a0a") if item["type"] == "image/png" else bytes.fromhex("ffd8ff")
            if len(image) > 1048576 or not image.startswith(signature):
                raise ValueError("Invalid reference image.")

        return await library.save(id, base_revision, {
            "brief":brief,"references":references,"images":images,"colors":colors,"led_count":led_count,
            "sections":sections,"source":source})

    async def preview(id, revision):
        record = library.get(id,revision)
        pixels = compile_strip(record["colors"],record["led_count"],record["sections"])
        return {"id":id,"revision":revision,"order":"LED 1 first","pixels":pixels}

    async def apply(id, revision):
        async with apply_lock:
            record = library.get(id,revision)
            source = record.get("source") or {}
            samples = source.get("colors_from_bosso",[])
            if not samples or not all(isinstance(v,str) for v in samples):
                raise ValueError("Requires a static reference preset with a verified RGB string encoding.")
            prefix = "#" if samples[0].startswith("#") else ""
            if source.get("state",{}).get("fx") != 0 or not all(re.fullmatch(prefix+r"[0-9a-fA-F]{6}",v) for v in samples):
                raise ValueError("Live playback supports only verified static RGB references.")
            coord, device = target()
            actual = await coord.api.async_get_device_config(device)
            counts = [int(actual.get(f"data_{n}_led_count") or 0) for n in range(1,5)]
            if device != source["device"] or counts != source["channels"] or sum(counts) != record["led_count"]:
                raise ValueError("Controller or LED layout differs from this design.")
            pixels = (await preview(id,revision))["pixels"]
            payload = deepcopy(source["state"])
            payload["device"] = {"device":device,"i":[prefix+p[1:] for p in pixels]}
            await coord.async_apply_to_home(payload)
            return {"id":id,"revision":revision,"status":"submitted","physical_result":"unverified"}

    tools = [
        StudioTool("BossoListDesigns","List saved designs and latest revisions.",{},listing),
        StudioTool("BossoReadDesign","Read a complete saved design and its references.",{ID:KEY,vol.Optional("revision"):int},get),
        StudioTool("BossoReadImage","Read an archived design reference image as base64.",{ID:KEY,REV:int,"index":int},image),
        StudioTool("BossoInspectPreset","Read a Bosso preset and channel lengths without applying it.",
                   {"preset":str,vol.Optional("category"):vol.In(["predefined","user"])},inspect),
        StudioTool("BossoSaveDesign","Save a complete static design. Supply base_revision=0 for new designs. Copy unchanged fields on edit. Optional preset captures a Bosso reference. Colors repeat; sorted section ranges override them.",
                   {ID:KEY,"base_revision":int,"brief":MAX_TEXT,"colors":COLORS,"led_count":int,
                    vol.Optional("images"):[{"type":vol.In(["image/png","image/jpeg"]),"data":str}],vol.Optional("sections"):[SECTION],vol.Optional("references"):MAX_TEXT,
                    vol.Optional("preset"):str,vol.Optional("category"):vol.In(["predefined","user"])},save,read=False),
        StudioTool("BossoPreviewDesign","Return the ordered RGB pixels for an exact revision.",{ID:KEY,REV:int},preview),
    ]
    if entry.data.get("enable_playback"):
        tools.append(StudioTool("BossoApplyDesign","Display a saved revision on the physical house lights.",
                                {ID:KEY,REV:int},apply,read=False,live=True))
    api = StudioAPI(hass=hass,id=DOMAIN,name="Bosso Design Studio",requires_admin=True)
    api.studio_tools = tools
    entry.async_on_unload(llm.async_register_api(hass,api))
    return True


async def async_unload_entry(hass, entry):
    return True


