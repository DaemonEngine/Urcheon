Urcheon
=======

Urcheon is the Middle English term for “hedgehog”, used to refer the related ordinary in heraldry.

![Cute Granger](doc/cute-granger.512.png)  
_My lovely granger needs a tender knight to care for his little flower._

Description
-----------

This is a toolset to modify `.map` and `.bsp` files and to package `.pk3` files.

This toolset is still [Unvanquished](http://unvanquished.net)-centric in some minor parts, but could be extended in the future, many things were thought to be extended.

This toolset was initially developed for the [Interstellar Oasis](https://github.com/interstellar-oasis/interstellar-oasis) initiative.

Help
----

Urcheon offers multiple stages.

### The `map` stage

It allows to parse some maps (quake3 format only supported at this time): de-numberize them for better diff, export entities as seen in bsp, or subsitutes entities using some substitution list you can write as needed.

Example:

```
urcheon map --input-map file.map --substitute-entities substitution.csv --disable-numbering --output-map file.map
```

This `map` call updates obsolete entities keywords using the `substitution.csv` list, disabling the entity numbering to make later diffing easier.

Type `urcheon map --help` for some help.

### The `bsp` stage

It allows to edit some bsp (quake3 format only supported at this time): import/export texture lists (this way you can rename them or tweak their surface flags), import/export entities, import/export lightmaps, this way you can repaint them by hand or use them as compressed external insted of internal one, or print some statistics. The best part in the `bsp` stage is the ability to convert a `bsp` to a `bspdir` that contains one file per lump, and some of them are stored in text editable format. These `bspdir` are mergeable back in a new `bsp`, allowing many modification, fixes to maps you lost source. It allows easy maintenance or port to other games.

Example:

```
urcheon bsp --input-bsp file.bsp --list-lumps --output-bspdir directory.bspdir
```

This `bsp` call converts a `bsp` file to a `bspdir` directory, printing some lump statistics at the same time.

Type `urcheon bsp --help` for some help.

### The `pak` stage.

This is where the beast comes. This stage handle an asset repository, being able to build them (asset compression, bspdir merge, map compilation) and package them. Each file type (lightmap, skybox, texture, model…) is recognized thanks to some profiles you can extend or modify, picking the optimal compression format for each type. If needed, you can write explicit rules for some specific files to force some format or blacklist some files. The `pak` stage becomes more powerful when used in git-tracked asset repositories: it can build partial package given any given git reference (to build a package that contains only things since last release tag for example), and it can automatically compute the package version using tags and commits date and id. It allows to define per-map compilation profile. The asset conversion and compression pass is parallelized to speed-up the process.

Example:

Having this `.pakinfo/pak.ini` file in your repository:

````
[config]
name = map-name
version = @ref
game = unvanquished
```

Running this command:

```
urcheon pak --clean all --build --auto-actions --since-reference v2.1 --map-profile final --package

```

This `pak` call cleans the previous build, automatically computes build rules (named _actions_) using the `unvanquished` profile, builds your source tree since tag `v2.1`, compiles the map using a predefined `final` stage and packages the whole as `map-name_2.1+timestamp~sha1.pk3` because there was some modifications since `v2.1`, otherwise the package would be named `map-name_2.1.pk3`.

Type `urcheon pak --help` from some help.

The `urcheon pak` stage relies on [`q3map2` from netradiant](https://gitlab.com/xonotic/netradiant), the one maintained by the Xonotic team. The navmesh code merge is still pending so you must use my [navmesh branch](https://gitlab.com/illwieckz/netradiant/commits/navmesh) if you use `urcheon pak` to build map packages. Other `urcheon pak` dependencies are: [`convert` from ImageMagick](https://www.imagemagick.org/), [`cwebp` from Google](https://developers.google.com/speed/webp/docs/cwebp), [`crunch` from Unvanquished](https://github.com/Unvanquished/crunch), [`opusenc` from Xiph](http://opus-codec.org), and if you need to convert iqe models, [`iqm` from Sauerbraten](http://sauerbraten.org/iqm/).

Warning
-------

No warranty is given, use this at your own risk.

Author
------

Thomas Debesse <dev@illwieckz.net>

Copyright
---------

This script is distributed under the highly permissive and laconic [ISC License](COPYING.md).
