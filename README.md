Granger's gardening toolbox
===========================

![Cute Granger](doc/cute-granger.512.png)  
_My lovely granger needs a gardening toolbox to care for his little flower._

Description
-----------

This is a toolset to modify `.map` and `.bsp` files.

This toolbox is currently [Unvanquished](http://unvanquished.net)-centric, but could be extended in the future.

Help
----

Currently, the `-il` option for `bsp_cutter.py` (to read lightmaps from a directory to embed them inside the BSP lightmaps lump) is a stub.

```
$ ./bsp_cutter.py -h
usage: bsp_cutter.py [-h] [-D] [-ib FILENAME] [-ob FILENAME] [-ie FILENAME]
                     [-oe FILENAME] [-it FILENAME] [-ot FILENAME]
                     [-il DIRNAME] [-ol DIRNAME] [-sl] [-od DIRNAME] [-la]
                     [-lL] [-le] [-ls] [-lt] [-ll] [-pe]

bsp_cutter.py is a BSP parser for my lovely granger.

optional arguments:
  -h, --help            show this help message and exit
  -D, --debug           print debug information
  -ib FILENAME, --input-bsp FILENAME
                        read from .bsp file FILENAME
  -ob FILENAME, --output-bsp FILENAME
                        write to .bsp file FILENAME
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
  -od DIRNAME, --output-bsp-dir DIRNAME
                        write to .bspdir directory DIRNAME
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

Currently, `map_cutter.py` does not parse yet vertex matrices, it carbon copy them instead.

```
$ ./map_cutter.py -h
usage: map_cutter.py [-h] [-D] [-im FILENAME] [-de FILENAME] [-se FILENAME]
                     [-om FILENAME]

map_cutter.py is a map parser for my lovely granger.

optional arguments:
  -h, --help            show this help message and exit
  -D, --debug           print debug information
  -im FILENAME, --input-map FILENAME
                        read from .map file FILENAME
  -de FILENAME, --dump-bsp-entities FILENAME
                        dump entities to .bsp entities format to .txt file
                        FILENAME
  -se FILENAME, --substitute-entities FILENAME
                        use entitie substitution rules from .csv file FILENAME
  -om FILENAME, --output-map FILENAME
                        write to .map file FILENAME
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
