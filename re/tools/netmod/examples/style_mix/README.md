# Style mix: all three building styles in one city

Normally a city has one building style. Pick European and every building that has a European version switches to
it. Style mix lets North American, European and Asian buildings grow side by side, at random, in the same city.

## How it works

The European and Asian versions of the zoned buildings are added to the game as new buildings, next to the North
American ones. Nothing is replaced. When a lot develops, the game picks from all three, so for a building that has
all three versions each style comes up about a third of the time. Buildings that only exist in one style keep
growing as they always did. Landmarks, civic buildings and industry aren't affected.

The new buildings use the game's own European and Asian art, so the package doesn't ship any art of its own.

## Getting the even mix

Each city remembers its own style. Many of the shipped cities (Berlin, London, Moscow and others) are saved with the
European style, and Seoul and Craterville with the Asian one. In a city like that the game still draws its
base buildings in that style, so you'll see mostly European (or Asian) with the other style mixed in. For the full
three-way mix, play a city saved with the North American (default) style, such as Madison or Sacramento, or a new
city in that style.

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
py -3.12 re/tools/netmod/examples/style_mix/build_style_mix.py --euro 2 --asian 2
```
