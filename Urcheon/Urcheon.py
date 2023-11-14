#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
#


from Urcheon import Action
from Urcheon import Pak
from Urcheon import Repository
from Urcheon import Ui
import argparse
import logging
import os
import sys

def discover(args):
	source_dir_list = args.source_dir

	for source_dir in source_dir_list:
		Ui.notice("discover from: " + source_dir)
		source_dir = os.path.realpath(source_dir)

		source_tree = Repository.Tree(source_dir, game_name=args.game_name)

		# TODO: find a way to update "prepare" actions too
		file_list = source_tree.listFiles()

		action_list = Action.List(source_tree, "build")
		action_list.updateActions(action_list)

def prepare(args):
	args.__dict__.update(stage_name="prepare")

	source_dir_list = args.source_dir

	is_parallel = not args.no_parallel
	multi_runner = Pak.MultiRunner(source_dir_list, args)
	multi_runner.run()

def build(args):
	args.__dict__.update(stage_name="build")

	source_dir_list = args.source_dir

	if args.test_dir and len(source_dir_list) > 1:
		Ui.error("--test-dir can't be used while building more than one source directory", silent=True)

	multi_runner = Pak.MultiRunner(source_dir_list, args)
	multi_runner.run()

def package(args):
	args.__dict__.update(stage_name="package")

	source_dir_list = args.source_dir

	if args.test_dir and len(source_dir_list) > 1:
		Ui.error("--test-dir can't be used while packaging more than one source directory", silent=True)

	if args.pak_name and len(source_dir_list) > 1:
		Ui.error("--pak-name can't be used while packaging more than one source directory", silent=True)

	if args.pak_file and len(source_dir_list) > 1:
		Ui.error("--pak-file can't be used while packaging more than one source directory", silent=True)

	is_parallel = not args.no_parallel
	multi_runner = Pak.MultiRunner(source_dir_list, args)
	multi_runner.run()

def clean(args):
	clean_all = args.clean_all

	if not args.clean_source \
		and not args.clean_map \
		and not args.clean_build \
		and not args.clean_test \
		and not args.clean_package \
		and not args.clean_all:
		clean_all = True

	source_dir_list = args.source_dir

	if args.test_dir and len(source_dir_list) > 1:
		Ui.error("--test-dir can't be used while cleaning more than one source directory", silent=True)

	for source_dir in source_dir_list:
		Ui.notice("clean from: " + source_dir)
		source_dir = os.path.realpath(source_dir)

		source_tree = Repository.Tree(source_dir, game_name=args.game_name)

		cleaner = Pak.Cleaner(source_tree)

		if args.clean_map:
			pak_config = Repository.Config(source_tree)
			# Do not use pak_name
			test_dir = pak_config.getTestDir(build_prefix=args.build_prefix, test_prefix=args.test_prefix, test_dir=args.test_dir)
			cleaner.cleanMap(test_dir)

		if args.clean_source or clean_all:
			paktrace = Repository.Paktrace(source_tree, source_dir)
			previous_file_list = paktrace.listAll()
			cleaner.cleanDust(source_dir, [], previous_file_list)

		if args.clean_test or args.clean_build or clean_all:
			pak_config = Repository.Config(source_tree)
			test_dir = pak_config.getTestDir(build_prefix=args.build_prefix, test_prefix=args.test_prefix, test_dir=args.test_dir)
			cleaner.cleanTest(test_dir)

		if args.clean_package or args.clean_build or clean_all:
			pak_config = Repository.Config(source_tree)
			pak_prefix = pak_config.getPakPrefix(build_prefix=args.build_prefix, pak_prefix=args.pak_prefix)
			cleaner.cleanPak(pak_prefix)

def main():
	description="Urcheon is a tender knight who takes care of my lovely granger's little flower."
	parser = argparse.ArgumentParser(description=description)

	parser.add_argument("-D", "--debug", dest="debug", help="print debug information", action="store_true")
	parser.add_argument("-v", "--verbose", dest="verbose", help="print verbose information", action="store_true")
	parser.add_argument("-l", "--laconic", dest="laconic", help="print laconic information", action="store_true")
	parser.add_argument("-g", "--game", dest="game_name", metavar="GAMENAME", help="use game %(metavar)s game profile, example: unvanquished")

	parser.add_argument("-C", "--change-directory", dest="change_directory", metavar="DIRNAME", default=".", help="run Urcheon in %(metavar)s directory, default: %(default)s")

	parser.add_argument("--build-prefix", dest="build_prefix", metavar="DIRNAME", help="build in %(metavar)s prefix, example: build")
	parser.add_argument("--test-prefix", dest="test_prefix", metavar="DIRNAME", help="use test pakdir from %(metavar)s prefix, example: build/test")
	parser.add_argument("--pak-prefix", dest="pak_prefix", metavar="DIRNAME", help="build release pak in %(metavar)s prefix, example: build/pkg")
	parser.add_argument("--test-dir", dest="test_dir", metavar="DIRNAME", help="use directory %(metavar)s as pakdir")
	# FIXME: check on windows if / works
	parser.add_argument("--pak-name", dest="pak_name", metavar="STRING", help="user %(metavar)s as pak name, example dev/nightly will produce build/pkg/dev/nightly_<version>.dpk")
	parser.add_argument("--pak-file", dest="pak_file", metavar="FILENAME", help="build release pak as %(metavar)s file")
	parser.add_argument("--version-suffix", dest="version_suffix", metavar="STRING", default=None, help="version suffix string, default: %(default)s")
	parser.add_argument("-np", "--no-parallel", dest="no_parallel", help="process tasks sequentially (disable parallel multitasking)", action="store_true")

	subparsers = parser.add_subparsers(help='commands')
	subparsers.required = True

	# Discover
	discover_parser = subparsers.add_parser('discover', help='discover a package (do not use)')
	discover_parser.set_defaults(func=discover)

	discover_parser.add_argument("source_dir", nargs="*", metavar="DIRNAME", default=".", help="discover %(metavar)s directory, default: %(default)s")

	# Prepare
	prepare_parser = subparsers.add_parser('prepare', help='prepare a package')
	prepare_parser.set_defaults(func=prepare)

	prepare_parser.add_argument("-n", "--no-auto-actions", dest="no_auto_actions", help="do not compute actions at build time", action="store_true")
	prepare_parser.add_argument("-k", "--keep", dest="keep_dust", help="keep dust from previous build", action="store_true")
	prepare_parser.add_argument("source_dir", nargs="*", metavar="DIRNAME", default=".", help="prepare %(metavar)s directory, default: %(default)s")

	# Build
	build_parser = subparsers.add_parser('build', help='build a package')
	build_parser.set_defaults(func=build)

	build_parser.add_argument("-mp", "--map-profile", dest="map_profile", metavar="PROFILE", help="build map with %(metavar)s profile, default: %(default)s")
	build_parser.add_argument("-n", "--no-auto", dest="no_auto_actions", help="do not compute actions", action="store_true")
	build_parser.add_argument("-k", "--keep", dest="keep_dust", help="keep dust from previous build", action="store_true")
	build_parser.add_argument("-cm", "--clean-map", dest="clean_map", help="clean previous map build", action="store_true")
	build_parser.add_argument("-r", "--reference", dest="since_reference", metavar="REFERENCE", help="build partial pakdir since given reference")
	build_parser.add_argument("source_dir", nargs="*", metavar="DIRNAME", default=".", help="build from %(metavar)s directory, default: %(default)s")

	# Package
	package_parser = subparsers.add_parser('package', help='package a package')
	package_parser.set_defaults(func=package)

	package_parser.add_argument("-ad", "--allow-dirty", dest="allow_dirty", help="allow to package from repositories with uncommitted files", action="store_true")
	package_parser.add_argument("-nc", "--no-compress", dest="no_compress", help="package without compression", action="store_true")
	package_parser.add_argument("source_dir", nargs="*", metavar="DIRNAME", default=".", help="package from %(metavar)s directory, default: %(default)s")

	# Clean
	clean_parser = subparsers.add_parser('clean', help='clean a package')
	clean_parser.set_defaults(func=clean)

	clean_parser.add_argument("-a", "--all", dest="clean_all", help="clean all (default)", action="store_true")
	clean_parser.add_argument("-b", "--build", dest="clean_build", help="clean test directory and generated packages (alias for --test --package)", action="store_true")
	clean_parser.add_argument("-s", "--source", dest="clean_source", help="clean source directory", action="store_true")
	clean_parser.add_argument("-t", "--test", dest="clean_test", help="clean test directory", action="store_true")
	clean_parser.add_argument("-m", "--map", dest="clean_map", help="clean map build", action="store_true")
	clean_parser.add_argument("-p", "--package", dest="clean_package", help="clean previously generated packages", action="store_true")
	clean_parser.add_argument("source_dir", nargs="*", metavar="DIRNAME", default=[ "." ], help="clean %(metavar)s directory, default: .")

	args = parser.parse_args()

	if args.debug:
		logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
		logging.debug("Debug logging activated")
		logging.debug("args: " + str(args))

	if args.laconic:
		Ui.verbosity = "laconic"
	elif args.verbose:
		Ui.verbosity = "verbose"

	os.chdir(args.change_directory)

	args.func(args)

if __name__ == "__main__":
	main()
