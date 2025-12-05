# OCaml Core/Risk Engine - Dockerfile
FROM ocaml/opam:debian-12-ocaml-5.1 AS builder

USER opam
WORKDIR /home/opam/app

# Install dependencies
RUN opam update && opam install -y \
    dune \
    core \
    core_unix \
    yojson \
    ppx_deriving \
    ppx_deriving_yojson \
    ppx_sexp_conv \
    lwt \
    lwt_ppx \
    cohttp-lwt-unix

# Copy project files
COPY --chown=opam:opam . .

# Build
RUN eval $(opam env) && dune build --release

# Runtime image
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    ca-certificates \
    libgmp10 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /home/opam/app/_build/default/bin/risk_gateway.exe /usr/local/bin/risk_gateway

ENV RISK_GATEWAY_PORT=8081
ENV RISK_MAX_POSITION=1.0
ENV RISK_MAX_DRAWDOWN=0.05

EXPOSE 8081

CMD ["risk_gateway"]
