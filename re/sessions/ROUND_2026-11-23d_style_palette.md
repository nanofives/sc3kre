# Round 2026-11-23d: style copies' lot colours follow the zone and land value of the city they grow in

Orchestrator: "SC3: pending items after recent rounds + SC4 style status". Rules: re/sessions/CHILD_PROTOCOL.md.
Owner 2026-11-23, looking at verify/forumshots/style_pick_before_after.jpg (copy of the owner's picture:
verify/forumshots/owner_palette_complaint.png): "I want to tweak the palette of colors of the houses and every zone type
according to land value ... on new buildings there's a blob of darker green that breaks with the immersion of the zone
density and value of that neighbourhood". Seen: European copies grown in Sacramento sit on dark olive lots with brown
garden plots, while the North American houses of the same class around them have bright green lawns and pools.

Background: re/analysis/BUILDING_PICK.md (style_mix copies at +400000 European / +1500000 Asian / +2600000 North
American, own keys and pixels in the netpack set .DAT files, family lines in BUILDFAM), memory
project-building-styles-mixing / project-stylepick, verify/stylepick, verify/civicstyle, re/analysis/BUILDING_ART.md.

## Stream stylepal (opus / medium). Evidence and mock-ups first, nothing installed until the owner picks

1. Measure: for every RCI class and wealth level (residential / commercial / industrial, density, low / mid / high
   wealth, the land value bands the game uses to pick them), the colour of the lot ground (grass, garden, paving,
   pools) and of the building body in the stock art of each style. Separate lot ground pixels from building pixels
   with evidence (frame masks, the art's own layers if any, or the lot footprint). Table per class x style: mean and
   spread in a perceptual space (Lab), with sample crops.
2. Say exactly which differences make the European / Asian copies read as another neighbourhood in a North American
   city (and the reverse in a European city): ground hue / lightness, garden plot share, building palette, or all.
3. Mock up recolour options on the copies only (never the stock art a stock European / Asian city uses):
   (a) lot ground only, matched to the host style's mean for the same class and wealth;
   (b) ground plus a light building tint toward the host palette;
   (c) per land value / wealth: ground follows the class's own wealth look (low = plainer, high = greener / pools look).
   Show each option on the owner's scene: Sacramento, same camera as verify/forumshots/style_pick_before_after.jpg
   (render the recoloured frames into a city frame offline, or install into a dev tree and grow, windowed, posted
   input only). Also show one European city with North American copies under the same rule.
4. Say what each option costs: which files (set .DAT pixels, CSAttrib frames, palettes), whether the copies need one
   recoloured art set per host style (European copies look different in an NA city vs an Asian city?) and what that
   does to package size and install time. Whether the game uses palettes per set or true colour pixels.
5. Results verify/stylepal/RESULTS.md with the mock-ups in owner_shots, STATUS re/sessions/STATUS_stylepal.md.
   Stop there and report: the owner picks the option before anything is built.

## Rules

EA set art only in the dev tree and gitignored verify folders, never in git or docs. Windowed game, never the real
mouse or keyboard, test slot, harness claim before game runs, kill only PIDs you started, delete BMP dumps, no git add /
commit.
