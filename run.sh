#!/bin/sh
# Fetch N_m3u8DL-RE on demand so the repo stays under the host's import
# limits (4 MB/file, 20 MB total). Re:Anime (the default source) does not
# need it; the binary is only used by the legacy anikoto/animesalt sources.
if [ ! -x binary/N_m3u8DL-RE ]; then
  echo "N_m3u8DL-RE not found, downloading..."
  mkdir -p binary
  wget -q https://github.com/nilaoda/N_m3u8DL-RE/releases/download/v0.2.1-beta/N_m3u8DL-RE_Beta_linux-x64_20240828.tar.gz -O /tmp/N_m3u8DL-RE.tar.gz \
    && tar -xzf /tmp/N_m3u8DL-RE.tar.gz -C /tmp \
    && mv /tmp/N_m3u8DL-RE_Beta_linux-x64/N_m3u8DL-RE binary/ \
    && chmod +x binary/N_m3u8DL-RE \
    && rm -rf /tmp/N_m3u8DL-RE.tar.gz /tmp/N_m3u8DL-RE_Beta_linux-x64 \
    || echo "WARNING: could not fetch N_m3u8DL-RE; legacy sources will be unavailable, Re:Anime still works."
fi
exec python3 -m cantarella
