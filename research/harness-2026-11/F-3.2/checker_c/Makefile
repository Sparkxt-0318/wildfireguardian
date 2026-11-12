CC ?= cc
CFLAGS = -std=c99 -O2 -Wall -Wextra -Werror -pedantic
SANFLAGS = -std=c99 -O1 -g -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined -fno-omit-frame-pointer -fno-sanitize-recover=all

.PHONY: all sanitize test clean

all: wfgc_check

wfgc_check: wfgc_check.c
	$(CC) $(CFLAGS) -o $@ wfgc_check.c

sanitize: wfgc_check_san

wfgc_check_san: wfgc_check.c
	$(CC) $(SANFLAGS) -o $@ wfgc_check.c

test: wfgc_check
	./tests/run_tests.sh ./wfgc_check

clean:
	rm -f wfgc_check wfgc_check_san
