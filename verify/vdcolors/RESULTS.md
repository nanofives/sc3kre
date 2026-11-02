# vdcolors (2026-11-02)
1. Cuadros bars (sc3resize_vdbars.c, off: SC3RESIZE_VDREDBARS=0): in Educacion, Salud and Agua the demand bar and its number are
   red when demand > capacity, green when covered; legend line "rojo = falta capacidad, verde = cubierto" under the bars.
   Water sources (output/capacity) stay blue; treatment pollution/plants use produced as demand.
   Libraries/museums: the 25-89 figure is the population the sim measures places against (seats*eff/max(seats,residents)),
   so 152.2K residents vs 328K places = covered (green). Seen in Berlin: Escuelas 156K/120K and Universidades 64.8K/45K red, Museos 500K/581K green.
2. RCI A/P (sc3resize_rcibars.c, off: SC3RESIZE_RCIBARS_FULL=0 = first build): letters on the bottom row of the visible meter
   (row 78 minus font height; the RCI bottom rows are clipped by the HUD), bars from just above the letters up to the top of the RCI
   meter (100% = top), 75% tick, tooltip on the letters. Seen in Berlin: A 56% / P 17%.
Not verified in game: Salud/Agua tab pictures (posted tab clicks missed; same code path as Educacion), English strings.
