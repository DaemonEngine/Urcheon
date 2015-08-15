#! /bin/sh

# generate a REDAME.md file with up-to-date built-in help.

rm "README.md"
exec 1<&-
exec 1<>"README.md"

cat <<\EOF
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

Currently, the `-il` option for `bsp_cutter.py` (to read lightmaps from a directory to embed them inside the BSP lightmaps lump) is a stub.

```
$ ./bsp_cutter.py -h
EOF

./bsp_cutter.py -h

cat <<\EOF
```

Currently, `map_cutter.py` does not parse yet vertex matrices, it carbon copy them instead.

```
$ ./map_cutter.py -h
EOF

./map_cutter.py -h

cat <<\EOF
```

Currently, `pak_mallet.py` needs [q3map2_helper.sh](https://github.com/illwieckz/q3map2_helper) and the [illwieckz`s netradiant branch](https://gitlab.com/illwieckz/netradiant/commits/illwieckz) to be able to correctly compile `.map` files.

```
$ ./pak_mallet.py -h
EOF

./pak_mallet.py -h

cat <<\EOF
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
EOF

#EOF
