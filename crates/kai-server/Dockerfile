# Build context is the repo ROOT, not this directory — see
# docker-compose.yml's `build.context: ../..`. kai-server is one member of
# the Cargo workspace declared in the root Cargo.toml, so the whole
# workspace manifest tree has to be visible to `cargo build`, even though
# only kai-shared + kai-server actually get compiled.

# --- The phone web app (mobile/), built once and served by kai-server itself
# at the site root — same address as the API, so no CORS and nothing else to
# host. Its own stage so the Rust image never needs Node, and so a change to
# the Rust code alone doesn't redo the npm install.
FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY mobile/package.json mobile/package-lock.json ./
RUN npm ci
COPY mobile ./
RUN npm run build

FROM rust:1-slim-bookworm AS builder
WORKDIR /build

COPY Cargo.toml Cargo.lock ./
COPY src-tauri/Cargo.toml src-tauri/Cargo.toml
COPY crates ./crates

# Stub out src-tauri's own source so the workspace resolves without it —
# cargo needs *a* src/main.rs + src/lib.rs to exist to infer that member's
# targets, even though kai-server doesn't depend on it and its real
# Tauri/WebView build-dependencies (which need Linux GUI packages this
# image doesn't have) never actually get compiled as a result.
RUN mkdir -p src-tauri/src \
    && echo "fn main() {}" > src-tauri/src/main.rs \
    && echo "" > src-tauri/src/lib.rs

RUN cargo build --release -p kai-server

# --- Runtime: just the one binary, no Rust toolchain ---
FROM debian:bookworm-slim AS runtime
# wget only exists here for docker-compose's healthcheck to curl /health with.
RUN apt-get update \
    && apt-get install -y --no-install-recommends wget \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --system --create-home --uid 10001 kai
WORKDIR /app
COPY --from=builder /build/target/release/kai-server /usr/local/bin/kai-server
COPY --from=web /web/dist /app/web
# Tells kai-server to serve the folder above at "/" (see routes::with_static_files).
ENV KAI_STATIC_DIR=/app/web
USER kai
EXPOSE 8787
ENTRYPOINT ["/usr/local/bin/kai-server"]
