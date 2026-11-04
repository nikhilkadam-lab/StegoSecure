
import struct

import numpy as np
from PIL import Image


HEADER_SIZE = 4
CHANNELS_PER_PIXEL = 3
BITS_PER_BYTE = 8

# Process at most 256 KB of payload per chunk.
CHUNK_SIZE = 256 * 1024

# Maximum embedded payload size: 15 MiB.
MAX_PAYLOAD_BYTES = 15 * 1024 * 1024


def get_image_capacity(image):
    """Return the maximum payload bytes available in an RGB image."""

    width, height = image.size
    total_channels = width * height * CHANNELS_PER_PIXEL

    return max(0, total_channels // BITS_PER_BYTE - HEADER_SIZE)


def _write_bytes_to_pixels(flat_pixels, start_channel, data):
    """Write bytes into pixel LSBs using bounded-size chunks."""

    total_written = 0

    for offset in range(0, len(data), CHUNK_SIZE):
        chunk = data[offset:offset + CHUNK_SIZE]

        bits = np.unpackbits(
            np.frombuffer(chunk, dtype=np.uint8)
        )

        end_channel = start_channel + len(bits)

        flat_pixels[start_channel:end_channel] = (
            flat_pixels[start_channel:end_channel] & 0xFE
        ) | bits

        start_channel = end_channel
        total_written += len(chunk)

    return start_channel, total_written


def _read_bytes_from_pixels(flat_pixels, start_channel, byte_count):
    """Read bytes from pixel LSBs using bounded-size chunks."""

    result = bytearray()
    remaining = byte_count

    while remaining > 0:
        chunk_bytes = min(remaining, CHUNK_SIZE)
        chunk_bits = chunk_bytes * BITS_PER_BYTE

        end_channel = start_channel + chunk_bits

        bits = flat_pixels[start_channel:end_channel] & 1

        packed = np.packbits(bits)

        result.extend(packed.tobytes())

        start_channel = end_channel
        remaining -= chunk_bytes

    return bytes(result)


def embed_payload(cover_image, payload_bytes):
    """
    Embed a binary payload into an image using RGB LSB steganography.

    Returns:
        A new RGB Pillow image containing the embedded payload.
    """

    if not isinstance(payload_bytes, bytes) or not payload_bytes:
        raise ValueError("Payload must contain valid binary data.")

    if len(payload_bytes) > MAX_PAYLOAD_BYTES:
        raise ValueError("Encrypted payload exceeds the maximum allowed size.")

    capacity = get_image_capacity(cover_image)

    if len(payload_bytes) > capacity:
        raise ValueError(
            f"Image capacity insufficient. "
            f"Available: {capacity} bytes; "
            f"Required: {len(payload_bytes)} bytes."
        )

    # Four-byte unsigned big-endian payload length.
    header = struct.pack(">I", len(payload_bytes))

    # Convert to RGB and make a writable contiguous array.
    rgb_image = cover_image.convert("RGB")

    try:
        pixels = np.array(rgb_image, dtype=np.uint8, copy=True)
    finally:
        rgb_image.close()

    flat_pixels = pixels.reshape(-1)

    # Write header followed by payload.
    next_channel, _ = _write_bytes_to_pixels(
        flat_pixels,
        0,
        header,
    )

    _write_bytes_to_pixels(
        flat_pixels,
        next_channel,
        payload_bytes,
    )

    return Image.fromarray(pixels)


def extract_payload(stego_image):
    """
    Extract an embedded payload from an RGB image.

    Returns:
        Original binary payload bytes.
    """

    width, height = stego_image.size

    total_channels = width * height * CHANNELS_PER_PIXEL

    if total_channels < HEADER_SIZE * BITS_PER_BYTE:
        raise ValueError("Image is too small to contain a payload header.")

    rgb_image = stego_image.convert("RGB")

    try:
        pixels = np.asarray(rgb_image, dtype=np.uint8)
        flat_pixels = pixels.reshape(-1)

        # Read the four-byte payload length.
        header = _read_bytes_from_pixels(
            flat_pixels,
            0,
            HEADER_SIZE,
        )

        payload_length = struct.unpack(">I", header)[0]

        available_capacity = get_image_capacity(stego_image)

        if payload_length <= 0:
            raise ValueError("No valid payload found in this image.")

        if payload_length > MAX_PAYLOAD_BYTES:
            raise ValueError("Embedded payload exceeds the allowed limit.")

        if payload_length > available_capacity:
            raise ValueError(
                "Embedded payload length is invalid or the image is corrupted."
            )

        # Read the actual payload.
        payload = _read_bytes_from_pixels(
            flat_pixels,
            HEADER_SIZE * BITS_PER_BYTE,
            payload_length,
        )

        return payload

    finally:
        rgb_image.close()
