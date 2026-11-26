# Bosso Design Studio

Home Assistant custom integration for creating and previewing versioned static RGB designs and animated RGBW preset clones through MCP. Static designs support ordered LED ranges. Designs are stored in Home Assistant. An authorized MCP client can retrieve saved content, including reference images.

## Installation

Install Bosso Lights v2.1.0 and configure a single Bosso account with one controller. This adapter targets Home Assistant Core 2026.11.3. Add this repository under Settings > Marketplace > Add from link and select Install. Follow the restart instructions shown by your instance, then add Bosso Design Studio under Devices & services. Leave physical playback disabled for your first preview.

With the Home Assistant MCP server configured, use the dedicated endpoint path `/api/mcp/bosso_studio` through your existing authenticated HTTPS connection. This custom tool endpoint requires administrator authentication.

## Try a preview

Call BossoSaveDesign with this synthetic design:

    {"id":"sample","base_revision":0,"brief":"Alternate gold and violet","colors":["#FFAA00","#660099"],"led_count":12}

Call BossoPreviewDesign with the same ID and revision 1. Call BossoReadDesign from another authorized client to retrieve it. To edit a design, save the complete desired design with the current revision as base_revision. Stale writes are rejected.

BossoInspectPreset reads a named preset and the channel lengths. Physical playback is opt-in and requires a matching controller and channel layout. Static designs require a compatible static RGB reference. A successful submission does not verify the physical result.

## Animated designs

BossoSaveEffect clones an animated preset into a Studio revision. Supply colors in the source preset's RGBW slot order. For the Bills version of Carolina, use [the example tool arguments](examples/bills-carolina-pattern.json) after checking the current design revision.

Use base_revision 0 for a new design ID. To edit a saved effect, omit preset and supply only the colors or settings to change. BossoPreviewDesign returns its controller parameters. BossoApplyDesign submits the chosen revision when playback is enabled. Effect clones support RGBW slots on presets without per-pixel overrides. Studio stores these revisions in Home Assistant.

## Tests

Run `python tests/test_design.py` from the repository root.
