# Bosso Design Studio

Home Assistant custom integration for creating and previewing versioned static RGB lighting designs through MCP. Each design can include a brief, references, images, and ordered LED ranges. Designs are stored in Home Assistant. An authorized MCP client can retrieve saved content, including reference images.

## Installation

Install Bosso Lights v2.1.0 and configure a single Bosso account with one controller. This adapter targets Home Assistant Core 2026.11.3. Add this repository under Settings > Marketplace > Add from link and select Install. Follow the restart instructions shown by your instance, then add Bosso Design Studio under Devices & services. Leave physical playback disabled for your first preview.

With the Home Assistant MCP server configured, use the dedicated endpoint path `/api/mcp/bosso_studio` through your existing authenticated HTTPS connection. This custom tool endpoint requires administrator authentication.

## Try a preview

Call BossoSaveDesign with this synthetic design:

    {"id":"sample","base_revision":0,"brief":"Alternate gold and violet","colors":["#FFAA00","#660099"],"led_count":12}

Call BossoPreviewDesign with the same ID and revision 1. Call BossoReadDesign from another authorized client to retrieve it. To edit a design, save the complete desired design with the current revision as base_revision. Stale writes are rejected.

BossoInspectPreset reads a named preset and the channel lengths. Physical playback is opt-in and requires a compatible static reference snapshot plus matching controller and channel lengths. A successful submission does not verify the physical result. This initial release has offline tests only.

## Tests

Run `python tests/test_design.py` from the repository root.
