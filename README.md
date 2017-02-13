Urcheon
=======

Urcheon is the Middle English term for “hedgehog”, used to refer the related ordinary in heraldry.

![Cute Granger](doc/cute-granger.512.png)  
_My lovely granger needs a tender knight to care for his little flower._

Description
-----------

This is a toolset to modify `.map` and `.bsp` files and to package `.pk3` files.

This toolset is currently [Unvanquished](http://unvanquished.net)-centric, but could be extended in the future.

This toolset was initially developed for the [Interstellar Oasis](https://github.com/interstellar-oasis/interstellar-oasis) initiative.

Help
----

```
$ urcheon bsp -h
usage: urcheon bsp [-h] [-D] [-ib FILENAME] [-id DIRNAME] [-ob FILENAME]
                   [-od DIRNAME] [-ie FILENAME] [-oe FILENAME] [-it FILENAME]
                   [-ot FILENAME] [-il DIRNAME] [-ol DIRNAME] [-sl] [-la]
                   [-lL] [-le] [-ls] [-lt] [-ll] [-pe]

urcheon bsp is a BSP parser for my lovely granger.

optional arguments:
  -h, --help            show this help message and exit
  -D, --debug           print debug information
  -ib FILENAME, --input-bsp FILENAME
                        read from .bsp file FILENAME
  -id DIRNAME, --input-bsp-dir DIRNAME
                        read from .bspdir directory DIRNAME
  -ob FILENAME, --output-bsp FILENAME
                        write to .bsp file FILENAME
  -od DIRNAME, --output-bsp-dir DIRNAME
                        write to .bspdir directory DIRNAME
  -ie FILENAME, --input-entities FILENAME
                        read from entities .txt file FILENAME
  -oe FILENAME, --output-entities FILENAME
                        write to entities .txt file FILENAME
  -it FILENAME, --input-textures FILENAME
                        read rom textures .csv file FILENAME
  -ot FILENAME, --output-textures FILENAME
                        write to textures .csv file FILENAME
  -il DIRNAME, --input-lightmaps DIRNAME
                        read from lightmaps directory DIRNAME
  -ol DIRNAME, --output-lightmaps DIRNAME
                        write to lightmaps directory DIRNAME
  -sl, --strip-lightmaps
                        empty the lightmap lump
  -la, --list-all       list all
  -lL, --list-lumps     list lumps
  -le, --list-entities  list entities
  -ls, --list-sounds    list sounds
  -lt, --list-textures  list textures
  -ll, --list-lightmaps
                        list lightmaps
  -pe, --print-entities
                        print entities
```

Currently, `urcheon map` does not parse vertex matrices yet, it carbon copies them instead.

```
$ urcheon map -h
usage: urcheon map [-h] [-D] [-im FILENAME] [-ob FILENAME] [-se FILENAME]
                   [-dn] [-om FILENAME]

urcheon map is a map parser for my lovely granger.

optional arguments:
  -h, --help            show this help message and exit
  -D, --debug           print debug information
  -im FILENAME, --input-map FILENAME
                        read from .map file FILENAME
  -ob FILENAME, --output-bsp-entities FILENAME
                        dump entities to .bsp entities format to .txt file
                        FILENAME
  -se FILENAME, --substitute-entities FILENAME
                        use entitie substitution rules from .csv file FILENAME
  -dn, --disable-numbering
                        disable entity and shape numbering
  -om FILENAME, --output-map FILENAME
                        write to .map file FILENAME
```

The `urcheon pak` stage relies on [`q3map2` from netradiant](https://gitlab.com/xonotic/netradiant), the one maintained by the Xonotic team. The navmesh code merge is still pending so you must use my [navmesh branch](https://gitlab.com/illwieckz/netradiant/commits/navmesh) if you use `urcheon pak` to build map packages. Other `urcheon pak` dependencies are: [`convert` from ImageMagick](https://www.imagemagick.org/), [`cwebp` from Google](https://developers.google.com/speed/webp/docs/cwebp), [`crunch` from Unvanquished](https://github.com/Unvanquished/crunch), [`opusenc` from Xiph](http://opus-codec.org), and if you need to convert iqe models, [`iqm` from Sauerbraten](http://sauerbraten.org/iqm/).


```
$ urcheon pak -h
usage: urcheon pak [-h] [-D] [-v] [-g GAMENAME] [-sd DIRNAME] [-bp DIRNAME]
                   [-tp DIRNAME] [-pp DIRNAME] [-td DIRNAME] [-pf FILENAME]
                   [-mp PROFILE] [-ev VERSION] [-u] [-b] [-a] [-p] [-c]

urcheon pak is a pak builder for my lovely granger.

optional arguments:
  -h, --help            show this help message and exit
  -D, --debug           print debug information
  -v, --verbose         print verbose information
  -g GAMENAME, --game-profile GAMENAME
                        use game profile GAMENAME, default: unvanquished
  -sd DIRNAME, --source-dir DIRNAME
                        build from directory DIRNAME, default: .
  -bp DIRNAME, --build-prefix DIRNAME
                        build in prefix DIRNAME, default: build
  -tp DIRNAME, --test-parent DIRNAME
                        build test pakdir in parent directory DIRNAME,
                        default: test
  -pp DIRNAME, --pkg-parent DIRNAME
                        build release pak in parent directory DIRNAME,
                        default: pkg
  -td DIRNAME, --test-dir DIRNAME
                        build test pakdir as directory DIRNAME
  -pf FILENAME, --pkg-file FILENAME
                        build release pak as file FILENAME
  -mp PROFILE, --map-profile PROFILE
                        build map with profile PROFILE, default: fast
  -ev VERSION, --extra-version VERSION
                        add VERSION to pak version string
  -u, --update          update paklist, compute actions
  -b, --build           build source pakdir
  -a, --auto            compute actions at build time and do not store paklist
  -p, --package         compress release pak
  -c, --clean           clean previous build
```

Warning
-------

No warranty is given, use this at your own risk.

Author
------

Thomas Debesse <dev@illwieckz.net>

Copyright
---------

This script is distributed under the highly permissive and laconic [ISC License](COPYING.md).
