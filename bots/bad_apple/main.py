"""
image_to_json.py

Reads ../image.txt, which is a Lua-style nested table:
  {
      [1] = { 1125899906842623, 999999999, 0, ... },   -- frame 1 rows
      [2] = { ... },                                    -- frame 2 rows
      ...
  }

Each number is a decimal integer representing a row of pixels.
It is converted to a 50-bit binary number, then flattened into a
1D boolean list where True = pixel ON (bit is 1).

Output JSON (written to output.json next to this script):
    [
        {
            "frame_index": 1,
            "row_count": 38,
            "pixel_count": 1900,
            "rows_raw": [1125899906842623, ...],
            "pixels": [true, true, ..., false]
        },
        ...
    ]
"""

import os
import re

from cambc import Controller, Position

class Player:
    def __init__(self):
        # ---------------------------------------------------------------------------
        # Parsing
        # ---------------------------------------------------------------------------

        def parse_image_file(filepath: str) -> dict:
            """
            Parse the Lua-table file into an ordered dict of {frame_key: [row_int, ...]}.
            Frame keys come from the [N] = { ... } syntax (1-based in the file).
            """
            with open(filepath, "r") as f:
                content = f.read()

            # Match each  [N] = { number, number, ... }  block
            frame_pattern = re.compile(r"\[(\d+)\]\s*=\s*\{([^}]*)\}", re.DOTALL)

            frames = {}
            for match in frame_pattern.finditer(content):
                frame_key = int(match.group(1))
                body = match.group(2)
                row_values = [int(tok) for tok in re.findall(r"\d+", body)]
                frames[frame_key] = row_values

            if not frames:
                raise ValueError("No frames found — check the file format.")

            return frames


        # ---------------------------------------------------------------------------
        # Pixel conversion
        # ---------------------------------------------------------------------------

        BITS = 50
        MASK = (1 << BITS) - 1  # keep only the lowest 50 bits


        def int_to_pixels(value: int) -> list:
            """
            Convert a decimal integer to a 50-bit boolean list.
            - Values < 2^50 : zero-padded on the left.
            - Values >= 2^50: lowest 50 bits kept (MSBs dropped).
            Returns a list of 50 booleans, index 0 = most-significant bit.
            """
            masked = value & MASK
            bits = format(masked, "050b")   # always exactly 50 chars
            return [ch == "1" for ch in bits]


        # ---------------------------------------------------------------------------
        # Assembly
        # ---------------------------------------------------------------------------

        def build_json(frames: dict) -> dict:
            output_frames = []

            for frame_key in sorted(frames):
                rows = frames[frame_key]
                flat_pixels = []

                for value in rows:
                    flat_pixels.extend(int_to_pixels(value))

                output_frames.append({
                    "frame_index": frame_key,          # original 1-based key from file
                    "row_count": len(rows),
                    "pixel_count": len(flat_pixels),   # always row_count * 50
                    "rows_raw": rows,                  # original decimal integers
                    "pixels": flat_pixels,             # flat 1D boolean array
                })

            return output_frames


        # ---------------------------------------------------------------------------
        # Main
        # ---------------------------------------------------------------------------

        def main():
            script_dir = os.path.dirname(os.path.abspath(__file__))
            input_path  = os.path.join(script_dir, "image.txt")

            print(f"Reading : {input_path}")
            frames = parse_image_file(input_path)
            print(f"Frames  : {len(frames)}")

            self.result = build_json(frames)

        main()

    def run(self, ct: Controller):
        current_frame_index = ct.get_current_round()

        if current_frame_index >= len(self.result):
            ct.resign()

        frame_info = self.result[current_frame_index]["pixels"][50:]
        row_count = self.result[current_frame_index - 1]["row_count"] - 1  # e.g. 38

        for y in range(row_count):   # rows (height)
            for x in range(50):
                is_black = frame_info[x + y * 50]
                if is_black:
                    ct.draw_indicator_dot(Position(x, y), 0, 0, 0)
                else:
                    ct.draw_indicator_dot(Position(x, y), 255, 255, 255)
