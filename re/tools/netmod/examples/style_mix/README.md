# Style mix: all three building styles in one city

Normally a city has one building style. Pick European and every building that has a European version switches to
it. Style mix lets North American, European and Asian buildings grow side by side, at random, in the same city.

## How it works

The European and Asian versions of the zoned buildings are added to the game as new buildings, next to the North
American ones. Nothing is replaced. When a lot develops, the game picks from all three, so for a building that has
all three versions each style comes up about a third of the time. Buildings that only exist in one style keep
growing as they always did. Landmarks, civic buildings and industry aren't affected.

The new buildings use the game's own European and Asian art, so the package doesn't ship any art of its own.

## Picking a style, like SimCity 4 (sc3netmod "Style: new buildings only")

With the road mod's style switch on (the default), the building style in Options > City Properties works like
SimCity 4: it picks which style **new** buildings grow in, and the buildings already standing keep their look. There
is no long "change in progress" any more, nothing is redrawn.

- Pick North American, European or Asian and untick **Mix all three styles**: new lots grow in that style.
- Tick **Mix all three styles**: new lots grow in all three at random (the style mix described here).
- Each city remembers its choice in its save. A city saved before this version starts with the mix ticked and its
  own style picked, so it keeps growing what it grew before.
- The New City window has the same box.
- A city saved with a European or Asian style keeps drawing its old buildings that way. If you then pick North
  American, the new buildings come from the North American copies (ids + 2600000), so they really are North
  American.

To get the old behaviour back (picking a style redraws every building), untick "Style: new buildings only" on the
Turn mods on/off page and restart. Same switch outside the game: `SC3NETMOD_STYLEPICK=0`. With "Building style mix"
unticked no copies grow at all, whatever the style.

## Civic buildings and rewards in every style (sc3resize "Civic + rewards: game styles")

The European and Asian versions of the civic buildings and parks are added too, but nothing grows them: you pick
them. Press a civic button that has them and the list window opens with one row per style, for example
"Norteamérica: Comisaría", "Europa: Comisaría", "Asia: Comisaría". The first row is the game's own building, drawn
in your city's style. Pick a row and place it as usual. Every look keeps the original's size, price and service.

Which buttons have them: Police, Fire, School, Museum, Baseball and Marina have European and Asian versions; Jail,
Hospital, College, Library, Small Park, Big Park, Playground, Pond and Fountain have an Asian one. Zoo, Bus Stop,
Train Station and Subway have none.

Rewards work the same way (1.4.0). Pick a reward in Rewards and Opportunities and, if the game has other styles of
it, a second window asks which look to build, for example "Norteamérica: Casa del Alcalde" or "Asia: Casa del
Alcalde". The first row is the game's own reward in your city's style. Esc builds nothing. The look is still the same
reward: it counts as built, costs the same, and turns with TAB, moves and undoes like the original. Rewards with other
styles: City Hall, County Courthouse, Lighthouse, Stadium, Stock Exchange and GigaMall (European and Asian), Mayor's
House, Historic Statue and Performing Arts Center (Asian). The other rewards have none and open no second window.

Untick "Civic + rewards: game styles" on the Turn mods on/off page (`SC3RESIZE_CIVSTYLE=0`) and the buttons and the
Rewards list work as without the mod again (`SC3RESIZE_REWARDLOOK=0` turns off only the rewards part). Placed looks
stay. A city with placed looks loads without the mods: each one comes back as the game's own building of the same
kind.

## Lawns that match the city (1.3.0)

A European or Asian house in a North American city used to bring its own dark, dull lawn and vegetable plots, so a
street of them read as another neighbourhood. The copies keep their buildings, but their lawn is now recoloured to
the lawn of the same building in the North American style, and most garden plots become lawn where the North
American version has none. The North American copies (grown in a European or Asian city) get the darker European
and Asian lawn the same way. Stock buildings and the game's own styles are not changed.

## Getting the even mix

Each city remembers its own style. Many of the shipped cities (Berlin, London, Moscow and others) are saved with the
European style, and Seoul and Craterville with the Asian one. In a city like that the game still draws its
base buildings in that style, so you'll see mostly European (or Asian) with the other style mixed in. For the full
three-way mix, play a city saved with the North American (default) style, such as Madison or Sacramento, or a new
city in that style.

## Turning it off

Untick "Building style mix" on the Turn mods on/off page (Preferences, Mod options, Turn mods on/off...) and
restart the game. New buildings then grow in the North American style only, as without the mod, and the road mod
keeps working. European and Asian buildings already in your city stay as they are and keep their look until the
lot is rebuilt, which then picks a North American building. Same switch outside the game: `SC3NETMOD_STYLEMIX=0`.

## Saves

Cities saved with style mix load fine without it. Each mixed building is swapped for another building of the same
kind as the city loads, so you don't get empty lots, just the usual styles again.

## Installing

Style mix is a netpack package (`examples/style_mix`). It installs together with the road packages and other
building packages:

```
py -3.12 re/tools/netmod/netpack.py install re/tools/netmod/examples/style_mix --tree <game folder>
```

To change the mix, rebuild the manifest with different weights before installing, for example twice as many
European and Asian buildings as North American ones:

```
py -3.12 re/tools/netmod/stylemix_build.py --euro 2 --asian 2
```
