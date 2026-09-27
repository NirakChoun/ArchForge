# ArchForge workloads. Build on the login node with at most -j 2:
#   source scripts/env.sh && make -C workloads -j 2
# gem5's X86 model has no AVX, so the SSE2 baseline (-march=x86-64) is used
# for everything; `make check-avx` verifies it.
CC      ?= gcc
OPT     ?= -O2
CFLAGS  := $(OPT) -march=x86-64 -static -Wall -Icommon -I$(M5_INC)
LDLIBS  := $(M5_LIB)/libm5.a
BIN     := bin
NATIVE  := bin/native

MICRO := seqsum stride chase compute branch conflict
APPS  := matmul aos_soa reduce sort

SRCS_micro := $(addprefix micro/,$(addsuffix .c,$(MICRO)))
SRCS_apps  := $(wildcard $(addprefix apps/,$(addsuffix .c,$(APPS))))
PROGS := $(patsubst micro/%.c,%,$(SRCS_micro)) $(patsubst apps/%.c,%,$(SRCS_apps))

all: $(addprefix $(BIN)/,$(PROGS))
native: $(addprefix $(NATIVE)/,$(PROGS))

$(BIN)/%.o: micro/%.c common/af.h | $(BIN)
	$(CC) $(CFLAGS) -c -o $@ $<
$(BIN)/%.o: apps/%.c common/af.h | $(BIN)
	$(CC) $(CFLAGS) -c -o $@ $<
$(BIN)/%: $(BIN)/%.o
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS)

$(NATIVE)/%: micro/%.c common/af.h | $(NATIVE)
	$(CC) $(OPT) -march=x86-64 -Wall -Icommon -DAF_NATIVE -o $@ $<
$(NATIVE)/%: apps/%.c common/af.h | $(NATIVE)
	$(CC) $(OPT) -march=x86-64 -Wall -Icommon -DAF_NATIVE -o $@ $<

$(BIN) $(NATIVE):
	mkdir -p $@

# Stage 7 compiler-flag variants: bin/<prog>_<tag> for matmul and reduce.
FLAGVARS := O1 O2 O3 O3nv
FLAGS_O1 := -O1
FLAGS_O2 := -O2
FLAGS_O3 := -O3
FLAGS_O3nv := -O3 -fno-tree-vectorize
VARPROGS := $(foreach p,matmul reduce,$(foreach v,$(FLAGVARS),$(BIN)/$(p)_$(v)))

variants: $(VARPROGS)

define VARRULE
$(BIN)/$(1)_$(2).o: apps/$(1).c common/af.h | $(BIN)
	$$(CC) $$(FLAGS_$(2)) -march=x86-64 -static -Wall -Icommon -I$$(M5_INC) -c -o $$@ $$<
$(BIN)/$(1)_$(2): $(BIN)/$(1)_$(2).o
	$$(CC) $$(FLAGS_$(2)) -march=x86-64 -static -o $$@ $$< $$(LDLIBS)
endef
$(foreach p,matmul reduce,$(foreach v,$(FLAGVARS),$(eval $(call VARRULE,$(p),$(v)))))

check-avx-variants: variants
	../scripts/check_no_avx.sh $(VARPROGS)

check-avx: all
	../scripts/check_no_avx.sh $(addprefix $(BIN)/,$(PROGS))

clean:
	rm -rf $(BIN)

.PHONY: all native check-avx clean variants check-avx-variants
.PRECIOUS: $(BIN)/%.o
