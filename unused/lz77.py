#!/usr/bin/env python3

def gba_lz77_decompress(data: bytes) -> bytes:
    """
    Decompress GBA LZ77 compressed data.

    Args:
        data (bytes): The compressed data starting with the LZ77 header (0x10)

    Returns:
        bytes: The decompressed data
    """
    if len(data) < 4:
        raise ValueError("Data too short to contain LZ77 header")

    if data[0] != 0x10:
        raise ValueError("Not a valid GBA LZ77 compressed stream (missing 0x10 header)")

    decompressed = bytearray()
    uncompressed_size = int.from_bytes(data[1:4], 'little')
    src_offset = 4  # Skip the 0x10 header and 3-byte decompressed size

    try:
        while len(decompressed) < uncompressed_size:
            if src_offset >= len(data):
                print(f"Warning: Ran out of compressed data before reaching expected uncompressed size")
                break

            flags = data[src_offset]
            src_offset += 1

            for i in range(8):
                if src_offset >= len(data) or len(decompressed) >= uncompressed_size:
                    break

                if (flags & (0x80 >> i)) == 0:
                    # Literal byte
                    decompressed.append(data[src_offset])
                    src_offset += 1
                else:
                    # Compressed block
                    # Make sure we have at least 2 more bytes
                    if src_offset + 1 >= len(data):
                        print(f"Warning: Compressed block at offset {src_offset} is incomplete")
                        break

                    byte1 = data[src_offset]
                    byte2 = data[src_offset + 1]
                    src_offset += 2

                    # Format: Length = ((byte1 >> 4) + 3), Offset = (((byte1 & 0xF) << 8) | byte2) + 1
                    disp = ((byte1 & 0xF) << 8) | byte2
                    length = (byte1 >> 4) + 3

                    # Check if the displacement is valid (points within the decompressed data)
                    if disp >= len(decompressed):
                        print(f"Warning: Invalid displacement {disp} at position {src_offset-2}, decompressed length: {len(decompressed)}")
                        # Try to recover by just copying what we can
                        disp = max(0, min(disp, len(decompressed) - 1))

                    for _ in range(length):
                        if len(decompressed) <= disp:
                            # This should not happen with valid compressed data, but we'll handle it gracefully
                            decompressed.append(0)  # Append a placeholder
                        else:
                            decompressed.append(decompressed[-(disp + 1)])
    except Exception as e:
        print(f"Error during decompression at offset {src_offset}: {e}")
        # Return what we have decompressed so far

    return bytes(decompressed)


def extract_and_decompress(rom_path, address):
    """
    Extract data from a ROM file at a specific address and decompress it.
    Automatically determines how much data to read based on the LZ77 header.

    Args:
        rom_path (str): Path to the ROM file
        address (int): Memory address to extract data from

    Returns:
        bytes: The decompressed data, or None if decompression failed
    """
    with open(rom_path, 'rb') as rom_file:
        # First read just the header (4 bytes) to get uncompressed size
        rom_file.seek(address)
        header = rom_file.read(4)

        if len(header) < 4:
            print(f"Error: Could not read header at address 0x{address:X}")
            return None

        if header[0] != 0x10:
            print(f"Error: Data at address 0x{address:X} is not LZ77 compressed (missing 0x10 header)")
            return None

        uncompressed_size = int.from_bytes(header[1:4], 'little')

        # Reading more than strictly necessary to avoid truncation
        estimated_max_size = uncompressed_size * 2

        # Go back to the start address and read the estimated amount
        rom_file.seek(address)
        compressed_data = rom_file.read(estimated_max_size)

        try:
            decompressed_data = gba_lz77_decompress(compressed_data)

            # Try trimming to the expected size if the data is longer
            if len(decompressed_data) > uncompressed_size:
                decompressed_data = decompressed_data[:uncompressed_size]

            return decompressed_data
        except Exception as e:
            print(f"Error decompressing data at address 0x{address:X}: {e}")
            return None