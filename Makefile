LIB_DIR=$(shell pwd)/scripts


all: tests

tests:
	PYTHONPATH=${LIB_DIR} python3 scripts/tests/*
	