SC3KU APACHE FLYOVER v0.9 RC1 — RELEASE PACKAGE

Standalone Apache patrol and manual flight mod for SimCity 3000 Unlimited.
Includes the DLL, three matching sprite files, full Apache source and art,
build tools, SDK source, licenses and notices. Runtime tests require the game.

INSTALL
Close SimCity 3000 Unlimited. Back up the previous Apache files.
Copy these FOUR files into the matching folders of your game installation:
  Apps/SC3KUApacheFlyover.dll
  Apps/Res/Sprites/SC3KU_ApacheFlyover.DAT
  Apps/Res/Sprites/SC3KU_ApacheFlyover.IXF
  Apps/Res/Sprites/SC3KU_ApacheFlyover.SII
Replace all four together. Do not delete unrelated Apps files.
No hurricane files are required. Do not install multiple Apache DLL versions.

COMMANDS
apache on      Three-minute automatic flyover.
apache patrol  Continuous road-biased patrol until apache off.
apache pilot   Manual screen-relative flight with W/A/S/D.
               W up, A left, S down, D right; combine keys for diagonals.
               Release keys to brake and hover. Nose follows flight direction.
[ / ]          Tap to adjust facing counterclockwise/clockwise while hovering.
               Each tap requests 45 degrees from the current world heading.
               Movement resumes automatic facing; it no longer stays locked.
apache turn    Turn around while hovering (180 degrees).
apache auto    Resume automatic route.
apache up/down/left/right   Smooth movement about four tiles in that direction.
apache off     Remove the formation and shadows.
Arrow keys remain available to the game's camera. Game shortcuts may still
respond to WASD; steering is active only while the game process has focus.

WHAT CHANGED
Eight airframe headings replace the two mirrored facing images. New matching
art includes front and rear views. Independent main/tail rotor cels accompany
each heading. Each helicopter eases its yaw toward its own actual velocity,
including on patrol and while followers catch up. Camera rotation selects the
appropriate visible heading without changing the aircraft's world heading.
Flight speed, acceleration, formation spacing and ground shadows retain v0.8
settings. This is eight-direction sprite animation, not continuous 3D rotation.
Only visible sprite variants are created on demand; hidden variants are reused.

RELEASE VERIFICATION
Repeat the mountain test without turning the camera: W/A/S/D and diagonals
should visibly turn the noses toward travel. Check all camera angles and zooms,
automatic patrol turns, hovering, brackets, apache turn, and apache off.
Switch cities and confirm no aircraft/shadow remains from the old city.
Send Apps/SC3KUApacheFlyover.log if you see a missing sprite or a crash.

LIMITATIONS
Patrol uses road counts for a lightweight route preference, not precise road
following or building avoidance. If road data is unavailable it uses a city
circuit. It does not know rooftop heights. Shadows sample ground elevation;
they do not conform to slopes or project onto roofs. No weapons, damage,
lights, flares, disaster changes or save edits. In-game testing is performed
by the user; compilation and automated checks do not guarantee crash-free play.

SOURCE AND BUILD
Source/Apache contains the DLL code, artwork, sprite builder and motion tests.
Source/vendor contains the SC3K community SDK and its license/notices.
Linux: bash build.sh (Python 3 + Pillow and i686-w64-mingw32-g++ or Zig).
Windows: install Zig, add it to PATH, run BUILD-WINDOWS.cmd to rebuild the DLL.
To regenerate assets: python Source/Apache/build_assets.py Apps/Res/Sprites
Tests: g++ -std=c++17 Source/Apache/test_flight.cpp -o test-flight
then run test-flight.
Our Apache source and artwork are supplied under LICENSE.txt (MIT). The SDK
retains LGPL-2.1-or-later with source and notices in Source/vendor. See
Source/RELINK-LGPL.txt to rebuild with a modified SDK. This unofficial mod is
not endorsed by Maxis/EA. No game executables or SimCity art are distributed.
Remove the four installed Apache files to uninstall. Roll back by restoring
all four files together from a backed-up earlier version.
