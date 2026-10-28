# Round 2026-10-28: mods page layout + autosave slots + autosave load crash
Orchestrator: "SC3 mods page layout + autosave rotation + load crash". Rules: re/sessions/CHILD_PROTOCOL.md.
Workspaces made from main 5748523 (`dev\modsui`, `dev\autosave3`).

Owner report (2026-10-28, with screenshots of the sc3mods-2026-10-28 build):
1. "el botón puede tener el mismo fondo gris que el resto de las preferencias? ubicalo abajo a la izquierda, misma
   altura que el tick, lo mismo para el botón de volver"
2. "que los sliders estén sobre un recuadro celeste que cubra ambos"
3. "guardar hasta 3 autosave, el de los últimos 5 minutos, últimos 10, última hora"
4. "al cargar un autosave el juego crashea"

| stream | owner report | expected |
|---|---|---|
| modsui | 1, 2 | "Opciones de mods..." and "Volver" drawn without the blue fill rectangle behind them (same grey/lavender as the dialog), bottom-left, vertically centred on the OK tick (game OK = id 0x02F95AD8 at local (0x1b0, 0x1b2) = (432, 434), FUN_1005853f in SIMUI FUN_100564d9:384). Camera sliders (CS_ARROW_LBL..CS_DRAG) sit on one light-blue panel covering both rows, like the game's own framed sections. sc3resize.c MODSPAGE / CAMSET blocks only. |
| autosave3 | 3, 4 | (a) three autosave files with fixed meaning: "last 5 min", "last 10 min", "last hour" (owner wording; propose exact rotation in STATUS before building, e.g. save every N min into slot A; slot A promoted to B when B is >=10 min old; to C when C is >=60 min old). Names readable in Load City. (b) loading an autosave crashes: reproduce in the tree, find the cause (file content vs file name vs load path vs our hooks running during load), fix. sc3autosave.c (and the mods page autosave rows in sc3resize.c only if the interval group must change: coordinate with modsui through the orchestrator). |
