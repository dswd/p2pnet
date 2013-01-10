
PROTO = src/p2pnet/proto/p2p.proto src/p2pnet/proto/dht.proto
PROTO_OUT = ${PROTO:.proto=_pb2.py}
DOC = spec/Specification.lyx
DOC_OUT = ${DOC:.lyx=.pdf}
ALL_OUT = $(DOC_OUT) $(PROTO_OUT)

all: $(ALL_OUT)

clean:
	-rm $(ALL_OUT)

.SUFFIXES: .proto _pb2.py .lyx .pdf

.proto_pb2.py:
	protoc -Isrc/p2pnet/proto --python_out=src/p2pnet/proto "$<"

.lyx.pdf:
	lyx "$<" -e pdf
