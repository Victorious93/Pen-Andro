# Pen-Andro PC-tools image.
#
# IMPORTANT — this container only provides the PC-side tooling (jadx,
# apktool, scrcpy, frida-tools, objection, the adb client). It does NOT
# make on-device steps (root cert install, Magisk module flashing) work
# inside a container — those still require the host's Magisk/root workflow
# described in README.md. To reach a real device from inside the container:
#   - USB passthrough:  docker run --privileged -v /dev/bus/usb:/dev/bus/usb ...
#   - or network ADB:   adb connect <device-ip>:5555 (from inside the container)
# Reaching a Burp instance on the host's 127.0.0.1 also generally requires
# --network host (Linux) rather than the default bridge network.
FROM kalilinux/kali-rolling

RUN apt-get update && apt-get install -y --no-install-recommends \
        adb \
        openjdk-17-jre-headless \
        python3 \
        python3-pip \
        curl \
        openssl \
        unzip \
        jadx \
        apktool \
        scrcpy \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/pen-andro
COPY pyproject.toml requirements.txt ./
COPY pen_andro ./pen_andro
COPY assets ./assets

RUN pip3 install --no-cache-dir --break-system-packages .

ENTRYPOINT ["pen-andro"]
