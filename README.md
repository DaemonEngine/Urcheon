Urcheon
=======


![Cute Granger](doc/cute-granger.512.png)  
_My lovely granger needs a tender knight to care for his little flower._


Description
-----------

ℹ️ Urcheon is purposed to manage and build source directories to produce game packages like Dæmon engine `dpk` packages or id Tech engines `pk3` or `pk4` packages.

The primary usage of this toolset is to build of [Unvanquished](http://unvanquished.net) game media files. It was initially  developed and tested against the files from [Interstellar Oasis](https://github.com/interstellar-oasis/interstellar-oasis).

ℹ️ The Esquirel tool is also shipped with Urcheon, which is a tool to do some common editions on `.map` and `.bsp` files. Esquirel is a bit id Tech 3 map and bsp format centric at this time.


How to run Urcheon and Esquirel
-------------------------------

💡️ You may want to install the [DaemonMediaAuthoringKit](https://github.com/DaemonEngine/DaemonMediaAuthoringKit). The _DaemonMediaAuthoringKit_ provides a convenient way to install Urcheon with its dependencies alongside some other usual edition tools (like the NetRadiant level editor). This makes easy to set-up a complete production environment.

If you're installing Urcheon separately, for example if you already own all tools required by Urcheon (see [Dependencies](#dependencies)), once you cloned this repository you can add this `bin/` directory to your `$PATH` environment variable to run them easily.


Urcheon help
------------

ℹ️ Urcheon is a game data package builder and packager. It converts files, compile maps, and produce distributables packages from them.


Type `urcheon --help` for generic help.


### Creating a package source

So you want to make a package, in this example we create a simple resource package that contains a text file. We will name this package `res-helloworld`. The DPK specifications reserves the `_` character as a version separator (can't be used in package name or version string).

We create a folder named `res-helloworld_src.dpkdir` and enter it:

```sh
mkdir res-helloworld_src.dpkdir
cd res-helloworld_src.dpkdir
```

This will be a package for the Unvanquished game so let's configure it this way:

```sh
mkdir .urcheon
echo 'unvanquished' > .urcheon/game.txt
```

We need the package to ship some content, let's add a simple text file:

```sh
mkdir about
echo 'Hello world!' > about/helloworld.txt
```


### Basic package tutorial

Now we can build the package, this will produce another dpkdir you can use with your game, with files being either copied, converted or compiled given the need.

It will be stored as `res-helloworld_src.dpkdir/build/_pakdir/pkg/res-helloworld_test.dpkdir`, you can tell the game engine to use `res-helloworld_src.dpkdir/build/_pakdir/pkg` as a pakpath to be able to find the package (example: `daemon -pakpath res-helloworld_src.dpkdir/build/_pakdir/pkg`).

```sh
urcheon build
```

Then we can produce the distributable `dpk` package.

It will be stored as `res-helloworld_src.dpkdir/build/pkg/map-castle_<version>.dpk`. The version will be computed by Urcheon (see below).

You can tell the game engine to use `res-helloworld_src.dpkdir/build/_pakdir/pkg` as a pakpath to be able to find the package (example: `daemon -pakpath res-helloworld_src.dpkdir/build/_pakdir/pkg`).

```sh
urcheon package
```

We can also pass the dpkdir path to Urcheon, this way:

```sh
cd ..
urcheon build res-helloworld_src.dpkdir
urcheon package res-helloworld_src.dpkdir
```


### Building in an arbitrary folder

As you noticed with our previous example, the built files were produced within the source dpkdir, with this layout:

```
res-helloworld_src.dpkdir/build/_pakdir/pkg/res-helloworld_test.dpkdir
res-helloworld_src.dpkdir/build/pkg/res-helloworld_<version>.dpk
```

You may not want this, especially if you want to build many package and want to get a single build directory. You can use the `--build-prefix <path>` option to change that, like that:

```sh
urcheon --build-prefix build build res-helloworld_src.dpkdir
urcheon --build-prefix build package res-helloworld_src.dpkdir
```

You get:

```
build/_pakdir/pkg/res-helloworld_test.dpkdir
build/pkg/res-helloworld_<version>.dpk
```


### Special case of prepared dpkdir

Some packages need to be prepared before being built. This is because some third-party software requires some files to exist in source directories, for example map editors and compilers.

Urcheon can produce `.shader` material files or model formats and others in source directory with the `prepare` command, for such package, the build and package routine is:

```sh
urcheon prepare <dpkdir>
urcheon build <dpkdir>
urcheon package <dpkdir>
```


### Package collection tutorial

A package collection is a folder containing a `src` subdirectory full of source dpkdirs.

Let's create a package collection, enter it and create the basic layout:

```sh
mkdir PackageCollection
cd PackageCollection
```

To tell Urcheon this folder is a package collection, you just need to create the `.urcheon/collection.txt` file, it just has to exist, en empty file is enough:

```sh
mkdir .urcheon
touch .urcheon/collection.txt
```

Then we create two packages, they must be stored in a subdirectory named `src`:

```sh
mkdir pkg

mkdir pkg/res-package1_src.dpkdir
mkdir pkg/res-package1_src.dpkdir/.urcheon
echo 'unvanquished' > pkg/res_package1_src.dpkdir/.urcheon/game.txt
mkdir pkg/res-package1_src.dpkdir/about
echo 'Package 1' > pkg/res_package1_src.dpkdir/about/package1.txt

mkdir pkg/res-package2_src.dpkdir
mkdir pkg/res-package2_src.dpkdir/.urcheon
echo 'unvanquished' > pkg/res_package2_src.dpkdir/.urcheon/game.txt
mkdir pkg/res-package2_src.dpkdir/about
echo 'Package 2' > pkg/res_package1_src.dpkdir/about/package2.txt

urcheon build pkg/*.dpkdir
urcheon package pkg/*.dpkdir
```

You'll get this layout:

```
build/_pakdir/pkg/res-package1_test.dpkdir
build/_pakdir/pkg/res-package2_test.dpkdir
build/pkg/res-package1_<version>.dpk
build/pkg/res-package2_<version>.dpk
```

You'll be able to use `build/_pakdir/pkg` or `build/pkg` as pakpath to make the game engine able to find those packages, example: `daemon -pakpath PackageCollection/build/_pakdir/pkg` or `daemon -pakpath PackageCollection/build/pkg`.


### Delta package building

Urcheon can produce partial packages relying on older versions of the same package. To be able to do that you need to have your dpkdirs stored in git repositories with version computed from git repositories.

You pass the old reference with the `--reference` build option followed by the git reference (for example a git tag), this way:

```sh
urcheon build --reference <tag> <dpkdir>
urcheon package <dpkdir>
```


### Dealing with multiple collections

When building dpkdirs from a collection requiring dpkdirs from another collection, one can set the `PAKPATH` environment variable this way (the separator is `;` on Windows and `:` on every other operating system):

```sh
export PAKPATH='Collection1/pkg:Collection2/pkg:Collection3/plg'
```

or (Windows):

```cmd
set PAKPATH='Collection1/plg;Collection2/pkg;Collection3/pkg'
```


### Real life examples

Here we clone the [UnvanquishedAssets](https://github.com/UnvanquishedAssets/UnvanquishedAssets) repository, prepare, build and package it:

```sh
git clone --recurse-submodules \
   https://github.com/UnvanquishedAssets/UnvanquishedAssets.git

urcheon prepare UnvanquishedAssets/pkg/*.dpkdir
urcheon build UnvanquishedAssets/pkg/*.dpkdir
urcheon package UnvanquishedAssets/pkg/*.dpkdir
```

We can load the Unvanquished game with the stock plat23 map this way:

```sh
daemon -pakpath UnvanquishedAssets/build/pkg +devmap plat23
```


Here we build and package delta Unvanquished packages for `res-` and `tex-` packages, only shipping files modified since Unvanquished 0.52.0, and full packages for map ones:

```sh
urcheon prepare UnvanquishedAssets/pkg/*.dpkdir
urcheon build --reference unvanquished/0.54.1 \
    UnvanquishedAssets/pkg/res-*.dpkdir \
    UnvanquishedAssets/pkg/tex-*.dpkdir
urcheon build UnvanquishedAssets/pkg/map-*.dpkdir
urcheon package UnvanquishedAssets/pkg/*.dpkdir
```

Here we clone the [InterstellarOasis](https://github.com/InterstellarOasis/InterstellarOasis) and build it.

Since it needs to access dpkdirs from UnvanquishedAssets, we set `UnvanquishedAssets/pkg` as a pakpath using the `PAKPATH` environment variable.

We also need the `UnvanquishedAsset/pkg` folder to be prepared, but there is no need to prepare `InterstellarOasis/pkg`, only build and package it:

```sh
git clone --recurse-submodules \
   https://github.com/InterstellarOasis/InterstellarOasis.git

export PAKPATH=UnvanquishedAssets/pkg

urcheon prepare UnvanquishedAssets/pkg/*.dpkdir
urcheon build InterstellarOasis/pkg/*.dpkdir
urcheon package InterstellarOasis/pkg/*.dpkdir
```

Given both `UnvanquishedAssets` and `InterstellarOasis` are built, one can load the Unvanquished game with the third-party atcshd map this way:

```sh
daemon -pakpath UnvanquishedAssets/build/pkg InterstellarOasis/build/pkg +devmap atcshd
```


### DPK version computation

Urcheon knows how to write the DPK version string, computing it if needed.

The recommended way is to store the dpkdir as a git repository, preferably one repository per dpkdir. Doing this unlock all abilities of Urcheon. It will be able to compute versions from git tag and do delta paks (partial DPK relying on older versions of it).

If the dpkdir is not a git repository, Urcheon provides two ways to set the version string.

One way is to write the version string in the `.urcheon/version.txt` file, like this:

```sh
echo '0.1' > .urcheon/version.txt
```

Urcheon does not implement delta packaging when doing this way (it may be implementable though).

Another way is to set the version string in the dpkdir name.

For example: `res-helloworld_0.1.dpkdir`

This is the least recommended method if you care about version control. Urcheon will never implement delta packaging for this (it's an unsolvable problem).


### More about Urcheon abilities

As we seen, this tool can prepare the assets (sloth-driven material generation, iqe compilation), build them (asset compression, bspdir merge, map compilation), then package them

Each file type (lightmap, skybox, texture, model…) is recognized thanks to some profiles you can extend or modify, picking the optimal compression format for each kind.

If needed, you can write explicit rules for some specific files to force some format or blacklist some files.

The Urcheon tool becomes more powerful when used in git-tracked asset repositories: it can build partial package given any given git reference (for example to build a package that contains only things since the previous release tag), and it can automatically computes the package version using tags, commits date, and commit id.

Urcheon also allows to define per-map compilation profile.

The asset conversion and compression pass is heavily parallelized to speed-up the process.


## More about Urcheon options and commands

Type `urcheon --help` for help about generic options.


### The `discover` command

This is an optional and not recommended command, you can use it if you want or need to not rely on automatic action lists. This stage produces your action lists, do not forget to use `-n` or `--no-auto` options on `prepare` and `build` stages later!

In most case, you don't need it. If you need it, it means you have to fix or extend file detection profiles.

This stage is not recommended since it will add a lot of noise to your git history each time you add or remove files.

This can be used to debug the automatic action list generation (what Urcheon decides to do for each file).

Type `urcheon discover --help` for help about the specific `discover` command options.


### The `prepare` command

This is an optional stage to prepare your source directory, it is needed when you have to produce files to feed your map editor or your map compiler, like material files or models. If your texture package is `sloth` driven, you must define a `slothrun` file per texture set and use the `prepare` stage.

If you need to prepare your source, always call this stage before the `build` one.

Type `urcheon prepare --help` for help about the specific `prepare` command options.


### The `build` command

This stage is required, it produces for you a testable pakdir with final formats: compressed textures, compiled map etc. If your assets are tracked in a git repository, you can build a partial pakdir using the `-r` or `--reference` options followed by an arbitrary past git reference (tag, commit…)

You can set a `PAKPATH` environment variable to declare multiple directories containing other pakdir, it's needed if your package relies on other packages that are not in the current collection. The format is like the good old `PATH` environment variable: pathes separated with semicolons on Windows and colons on every other operating system.

If you're building a partial `dpk` package, an extra entry containing your previous package version is added to the `DEPS` file automatically.

You must call this stage before the `package` one.

Type `urcheon build --help` for help about the specific `build` command options.


### The `package` command

This stage produces a pak file from your previously built pakdir. Urcheon automatically writes the version string of the produced pak and if your game supports `dpk` format it will automatically rewrites your `DEPS` file with versions from other pakdirs found in `PAKPATH`.

Type `urcheon package --help` for help about the specific `package` command options.


### The `clean` command

This stage is convenient to clean stuff, it has multiple options if you don't want to clean-up everything.

This will delete built files from the source dpkdir if prepared, and from the `build/_pakdir/pkg` and `build/pkg` folders:

```sh
urcheon clean pkg/<dpkdir>
```

You can clean those folders selectively:

```sh
urcheon clean --source pkg/<dpkdir>
urcheon clean --test pkg/<dpkdir>
urcheon clean --package pkg/<dpkdir>
```

Those special options also exist, here to only clean `build/_pakdir/pkg` and `build/pkg`: 

```sh
urcheon clean --build pkg/<dpkdir>
```

This will only delete built maps from `build/_pakdir/pkg` (keeping every other build files:

```sh
urcheon clean --maps pkg/<dpkdir>
```

Type `urcheon clean --help` for help about the specific `clean` command options.


### Dependencies

💡️ The [DaemonMediaAuthoringKit](https://github.com/DaemonEngine/DaemonMediaAuthoringKit) makes easy to set-up a complete production environment with Urcheon, its dependencies, and other tools.

These are the Python3 modules you will need to run `urcheon`: `argparse`, `colorama`, `pillow`, `psutil`, and `toml` >= 0.9.0.

The `urcheon` tool relies on:

- [`q3map2` from NetRadiant](https://gitlab.com/xonotic/netradiant), the one maintained by the Xonotic team, to compile maps (the one from GtkRadiant is lacking required features);
- [Sloth](https://github.com/Unvanquished/Sloth) if you need it to generate shader files;
- [`cwebp` from Google](https://developers.google.com/speed/webp/docs/cwebp) to convert images to webp format;
- [`crunch` from Dæmon](https://github.com/DaemonEngine/crunch) to convert images to crn format (the one from BinomialLLC is not compatible and the one from Unity lacks required features);
- [`opusenc` from Xiph](http://opus-codec.org) to convert sound files to opus format;
- [`iqmtool` from FTE QuakeWorld](https://sourceforge.net/p/fteqw/code/HEAD/tree/trunk/iqm/) to convert iqe models (the `iqm` one from Sauerbraten is lacking required features).
- [`sloth`](https://github.com/DaemonEngine/Sloth/) to generate .shader material files.

To summarize:

* Python3 modules: `argparse colorama pillow psutil toml>=0.9.0`
* Third party tools: `crunch cwebp iqmtool opusenc q3map2 sloth.py`


Esquirel help
-------------

ℹ️ Esquirel is a tool to inspect `.map` and `.bsp` files and apply some modifications to them.

Type `esquirel --help` for generic help.

Esquirel offers multiple commands.


### The `map` command

It allows to parse some maps (id Tech 3 format only supported at this time): de-numberize them for better diff, export entities as seen in bsp, or substitutes entity keywords using some substitution list you can write yourself.

Example:

```sh
esquirel map --input-map file.map \
	--substitute-keywords substitution.csv \
	--disable-numbering \
	--output-map file.map
```

This `esquirel` call updates obsolete entities keywords using the `substitution.csv` list, disabling the entity numbering to make lately diffing easier.

Type `esquirel map --help` about the specific `map` command options.


### The `bsp` command

It allows to edit some bsp (id Tech 3 format only supported at this time): import/export texture lists (this way you can rename them or tweak their surface flags), import/export entities, import/export lightmaps (this way you can repaint them by hand or use them as compressed external instead of internal one), or print some statistics. The best part in the `bsp` stage is the ability to convert a `bsp` to a `bspdir` that contains one file per lump, and some of them are stored in editable text format. These `bspdir` are mergeable back as a new `bsp`, allowing many modification or fixes to maps you lost source for. It allows easy maintenance or port to other games.

Example:

```sh
esquirel bsp --input-bsp level.bsp \
	--list-lumps \
	--output-bspdir level.bspdir
```

This `esquirel` call converts a `bsp` file to a `bspdir` directory, printing some lump statistics at the same time.

The reverse operation is:

```sh
esquirel bsp --input-bspdir level.bspdir \
	--list-lumps \
	--output-bsp level.bsp
```

Type `esquirel bsp --help` about the specific `bsp` command options.


Warning
-------

No warranty is given, use this at your own risk. It can make you awesome in space if used inconsiderately.


Author
------

Thomas Debesse <hidden email="dev [ad] illwieckz.net"/>


Copyright
---------

This toolbox is distributed under the highly permissive and laconic [ISC License](COPYING.md).


Trivia
------

_Esquirel is the Englo-Norman word for “squirrel”, from the Old French “escurel” who displaced Middle English “aquerne”._

_Urcheon is the Middle English term for “hedgehog”, used to refer the related ordinary in heraldry._
