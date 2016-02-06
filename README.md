Granger's gardening toolbox
===========================

![Cute Granger](doc/cute-granger.512.png)  
_My lovely granger needs a gardening toolbox to care for his little flower._

Description
-----------

This is a toolset to modify `.map` and `.bsp` files and to package `.pk3` files.

This toolbox is currently [Unvanquished](http://unvanquished.net)-centric, but could be extended in the future.

This toolbox was developed for the [Interstellar Oasis](https://github.com/interstellar-oasis/interstellar-oasis) initiative.

Help
----

```
$ ./bsp_cutter.py -h
usage: bsp_cutter.py [-h] [-D] [-ib FILENAME] [-id DIRNAME] [-ob FILENAME]
                     [-od DIRNAME] [-ie FILENAME] [-oe FILENAME]
                     [-it FILENAME] [-ot FILENAME] [-il DIRNAME] [-ol DIRNAME]
                     [-sl] [-la] [-lL] [-le] [-ls] [-lt] [-ll] [-pe]

bsp_cutter.py is a BSP parser for my lovely granger.

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

Currently, `map_cutter.py` does not parse vertex matrices yet, it carbon copies them instead.

```
$ ./map_cutter.py -h
usage: map_cutter.py [-h] [-D] [-im FILENAME] [-ob FILENAME] [-se FILENAME]
                     [-dn] [-om FILENAME]

map_cutter.py is a map parser for my lovely granger.

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

Currently, `pak_mallet.py` relies on a not yet upstreamed branch of q3map2.


```
$ ./pak_mallet.py -h
usage: pak_mallet.py [-h] [-D] [-v] [-g GAMENAME] [-id DIRNAME] [-pd DIRNAME]
                     [-pp DIRNAME] [-od DIRNAME] [-op FILENAME] [-bp PROFILE]
                     [-ev VERSION] [-u] [-b] [-p]

pak_mallet.py is a pak builder for my lovely granger.

optional arguments:
  -h, --help            show this help message and exit
  -D, --debug           print debug information
  -v, --verbose         print verbose information
  -g GAMENAME, --game-profile GAMENAME
                        use game profile GAMENAME, default: unvanquished
  -id DIRNAME, --input-pk3dir DIRNAME
                        build from directory DIRNAME, default: .
  -pd DIRNAME, --output-prefix-pk3dir DIRNAME
                        build pk3dir in directory DIRNAME, default: build/test
  -pp DIRNAME, --output-prefix-pk3 DIRNAME
                        build pk3 in directory DIRNAME, default: build/pkg
  -od DIRNAME, --output-pk3dir DIRNAME
                        build pk3dir as directory DIRNAME
  -op FILENAME, --output-pk3 FILENAME
                        build pk3 as file FILENAME
  -bp PROFILE, --build-profile PROFILE
                        build map with profile PROFILE, default: fast
  -ev VERSION, --extra-version VERSION
                        add VERSION to pk3 version string
  -u, --update          update paklist
  -b, --build           build pak
  -p, --package         compress pak
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
