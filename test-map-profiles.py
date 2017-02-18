#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

from Urcheon import MapCompiler
import logging
import sys

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

a=MapCompiler.Config("/home/Archive/dev/mapping/urcheon-tests/map-rsmse_src.pk3dir/build/test/map-rsmse_test.pk3dir/", "unvanquished")
a.printConfig()
