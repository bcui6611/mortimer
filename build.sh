#!/bin/sh
git rev-parse HEAD > resources/git-rev.txt
lein uberjar
