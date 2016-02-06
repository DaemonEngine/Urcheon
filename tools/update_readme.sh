#! /bin/sh

# generate a README.md file with up-to-date built-in help.

test -f "README.md" && rm "README.md"
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

```
$ ./bsp_cutter.py -h
EOF

./bsp_cutter.py -h

cat <<\EOF
```

Currently, `map_cutter.py` does not parse vertex matrices yet, it carbon copies them instead.

```
$ ./map_cutter.py -h
EOF

./map_cutter.py -h

cat <<\EOF
```

Currently, `pak_mallet.py` relies on a not yet upstreamed branch of q3map2.


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
