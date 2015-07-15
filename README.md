Granger's toolbox
=================

Description
-----------

This is a toolset to modify `.map` and `.bsp` files.

This toolbox is currently [Unvanquished](http://unvanquished.net)-centric, but could be extended in the future.

Help
----

Currently, the `-il` option (to read lightmaps from a directory to embed them inside the BSP lightmaps lump) is a stub.

```
./bsp_cutter.py -h
usage: bsp_cutter.py [-h] [-D] [-ib FILENAME] [-ob FILENAME] [-ie FILENAME]
                     [-oe FILENAME] [-it FILENAME] [-ot FILENAME]
                     [-il DIRNAME] [-ol DIRNAME] [-sl] [-la] [-lL] [-le] [-ls]
                     [-lt] [-ll] [-pe]

bsp_cutter.py is a BSP parser for my lovely granger.

optional arguments:
  -h, --help            show this help message and exit
  -D, --debug           print debug information
  -ib FILENAME, --input-bsp FILENAME
                        read from BSP file FILENAME
  -ob FILENAME, --output-bsp FILENAME
                        write to BSP file FILENAME
  -ie FILENAME, --input-entities FILENAME
                        read from entities TXT file FILENAME
  -oe FILENAME, --output-entities FILENAME
                        write to entities TXT file FILENAME
  -it FILENAME, --input-textures FILENAME
                        read rom textures CSV file FILENAME
  -ot FILENAME, --output-textures FILENAME
                        write to textures CSV file FILENAME
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

```
$ ./map_cutter.py -h
usage: map_cutter.py [-h] [-D] [-im FILENAME] [-de FILENAME] [-se FILENAME]
                     [-om FILENAME]

map_cutter.py is a map parser for my lovely granger.

optional arguments:
  -h, --help            show this help message and exit
  -D, --debug           print debug information
  -im FILENAME, --input-map FILENAME
                        read from MAP file FILENAME
  -de FILENAME, --dump-bsp-entities FILENAME
                        dump entities to BSP entities format to TXT file
                        FILENAME
  -se FILENAME, --substitute-entities FILENAME
                        use entitie substitution rules from CSV file FILENAME
  -om FILENAME, --output-map FILENAME
                        write to MAP file FILENAME
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
