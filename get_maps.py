import struct
import json
import os

def gba_lz77_decompress(data: bytes) -> bytes:
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
        print(f"Header bytes: {' '.join([f'{b:02X}' for b in header])}")
        print(f"Uncompressed size from header: {uncompressed_size} bytes")

        # GBA often uses 4-byte alignment, so the actual data might be padded
        # Calculate what the size would be if aligned to 2 or 4 bytes
        aligned_2 = (uncompressed_size + 1) & ~1  # Align to 2 bytes (16-bit)
        aligned_4 = (uncompressed_size + 3) & ~3  # Align to 4 bytes (32-bit)
        print(f"2-byte aligned size would be: {aligned_2}")
        print(f"4-byte aligned size would be: {aligned_4}")

        # Reading more than strictly necessary to avoid truncation
        estimated_max_size = uncompressed_size * 2

        # Go back to the start address and read the estimated amount
        rom_file.seek(address)
        compressed_data = rom_file.read(estimated_max_size)

        try:
            decompressed_data = gba_lz77_decompress(compressed_data)
            print(f"Actual decompressed size: {len(decompressed_data)} bytes")

            # Analyze the end of the decompressed data to see if there's padding
            if len(decompressed_data) >= 4:
                print(f"Last 4 bytes: {' '.join([f'{b:02X}' for b in decompressed_data[-4:]])}")

            # Try trimming to the expected size if the data is longer
            if len(decompressed_data) > uncompressed_size:
                print(f"Trimming extra {len(decompressed_data) - uncompressed_size} bytes")
                decompressed_data = decompressed_data[:uncompressed_size]

            return decompressed_data
        except Exception as e:
            print(f"Error decompressing data at address 0x{address:X}: {e}")
            return None

def ensure_directory_exists(directory):
    """
    Create directory if it doesn't exist
    """
    if not os.path.exists(directory):
        print(f"Creating directory: {directory}")
        os.makedirs(directory)

def main():
    # Specify the ROM path
    rom_path = "Fire Emblem (FE7)  - The Blazing Blade.gba"

    # Create output directories
    spritemap_dir = "spritemaps"
    tilemap_dir = "tilemaps"
    ensure_directory_exists(spritemap_dir)
    ensure_directory_exists(tilemap_dir)

    # Load mappings from JSON file
    try:
        with open("mappings.json", "r") as f:
            mappings = json.load(f)
    except Exception as e:
        print(f"Error loading mappings file: {e}")
        return

    # Process each mapping
    for map_id, addresses in mappings.items():
        print(f"\nProcessing map {map_id}:")

        # Extract sprite map
        sprite_address = int(addresses[0], 16)
        print(f"Extracting and decompressing spritemap at address 0x{sprite_address:X}...")
        sprite_data = extract_and_decompress(rom_path, sprite_address)

        if sprite_data:
            print(f"Successfully decompressed {len(sprite_data)} bytes from spritemap")
            # Save the decompressed data to the spritemaps directory
            sprite_filename = f"spritemap_{map_id}_{sprite_address:X}.bin"
            sprite_filepath = os.path.join(spritemap_dir, sprite_filename)
            with open(sprite_filepath, "wb") as f:
                f.write(sprite_data)
            print(f"Saved to {sprite_filepath}")

        # Extract tile map
        tile_address = int(addresses[1], 16)
        print(f"Extracting and decompressing tilemap at address 0x{tile_address:X}...")
        tile_data = extract_and_decompress(rom_path, tile_address)

        if tile_data:
            print(f"Successfully decompressed {len(tile_data)} bytes from tilemap")
            # Save the decompressed data to the tilemaps directory
            tile_filename = f"tilemap_{map_id}_{tile_address:X}.bin"
            tile_filepath = os.path.join(tilemap_dir, tile_filename)
            with open(tile_filepath, "wb") as f:
                f.write(tile_data)
            print(f"Saved to {tile_filepath}")

if __name__ == "__main__":
    main()
