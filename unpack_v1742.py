#!/usr/bin/env python3

"""
Unpack CAEN WaveDump V1742/x742 binary waveform files.

Expected input:
    wave_0.dat
    wave_1.dat
    ...
    wave_31.dat

Configuration:
    RECORD_LENGTH       1024
    OUTPUT_FILE_HEADER  YES
    CORRECTION_LEVEL    AUTO

V1742 WaveDump x742 output format:

    uint32 header[6]
    float32 samples[1024]

Header:
    [0] Event size in bytes = 24 + 4*N
    [1] Board ID
    [2] Pattern
    [3] Channel (0..7, relative to group)
    [4] Event counter
    [5] Trigger time tag

ROOT output:

    events
        waveform       float32[32][1024]
        event_counter  uint32[32]
        trigger_time   uint32[32]
        board_id       uint32[32]
        pattern        uint32[32]

The waveform is therefore:

    waveform[event, channel, sample]

"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import uproot


# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------

N_CHANNELS = 32
N_SAMPLES = 1024

HEADER_WORDS = 8
HEADER_BYTES = HEADER_WORDS * 4

SAMPLE_DTYPE = np.dtype("<f4")       # x742 corrected waveform
HEADER_DTYPE = np.dtype("<u4")       # 32-bit header words

BLOCK_BYTES = HEADER_BYTES + N_SAMPLES * SAMPLE_DTYPE.itemsize


# ----------------------------------------------------------------------
# One channel file
# ----------------------------------------------------------------------

class ChannelReader:
    """
    Sequential reader for one wave_N.dat file.
    """

    def __init__(self, path: Path, channel: int):
        self.path = path
        self.channel = channel
        self.fp = path.open("rb")

        self.event_index = 0

    def close(self):
        self.fp.close()

    def read_event(self):
        """
        Read one event.

        Returns
        -------
        dict or None
            None means EOF.
        """

        header_raw = self.fp.read(HEADER_BYTES)

        if not header_raw:
            return None

        if len(header_raw) != HEADER_BYTES:
            raise RuntimeError(
                f"{self.path}: truncated header at event "
                f"{self.event_index}: got {len(header_raw)} bytes"
            )

        header = np.frombuffer(
            header_raw,
            dtype=HEADER_DTYPE,
            count=HEADER_WORDS,
        )

        event_size = int(header[0])
        board_id = int(header[1])
        pattern = int(header[2])
        channel_in_file = int(header[3])
        event_counter = int(header[4])
        trigger_time = int(header[5])

        # --------------------------------------------------------------
        # Validate event size
        # --------------------------------------------------------------

        expected_event_size = (
            HEADER_BYTES
            + N_SAMPLES * SAMPLE_DTYPE.itemsize
        )

        if event_size != expected_event_size:
            raise RuntimeError(
                f"{self.path}: unexpected event size at event "
                f"{self.event_index}: "
                f"header says {event_size} bytes, "
                f"expected {expected_event_size} bytes "
                f"for {N_SAMPLES} float32 samples."
            )

        sample_bytes = N_SAMPLES * SAMPLE_DTYPE.itemsize

        data_raw = self.fp.read(sample_bytes)

        if len(data_raw) != sample_bytes:
            raise RuntimeError(
                f"{self.path}: truncated waveform at event "
                f"{self.event_index}: got {len(data_raw)} bytes, "
                f"expected {sample_bytes}"
            )

        waveform = np.frombuffer(
            data_raw,
            dtype=SAMPLE_DTYPE,
            count=N_SAMPLES,
        ).copy()

        # --------------------------------------------------------------
        # Validate channel
        # --------------------------------------------------------------


        if channel_in_file != self.channel:
            raise RuntimeError(
                f"{self.path}: channel mismatch at event "
                f"{self.event_index}: "
                f"header channel={channel_in_file}, "
                f"expected {self.channel}"
            )

        result = {
            "waveform": waveform,
            "board_id": board_id,
            "pattern": pattern,
            "channel": channel_in_file,
            "event_counter": event_counter,
            "trigger_time": trigger_time,
        }

        self.event_index += 1

        return result


# ----------------------------------------------------------------------
# Open all 32 files
# ----------------------------------------------------------------------

def open_channels(input_dir: Path):
    readers = []

    for ch in range(N_CHANNELS):
        path = input_dir / f"wave_{ch}.dat"

        if not path.exists():
            raise FileNotFoundError(
                f"Missing channel file: {path}"
            )

        readers.append(ChannelReader(path, ch))

    return readers


# ----------------------------------------------------------------------
# Read one synchronized event from all channels
# ----------------------------------------------------------------------

def read_event(readers, event_number):
    """
    Read event_number from all 32 channels.

    Returns:
        waveform       (32, 1024) float32
        event_counter  (32,) uint32
        trigger_time   (32,) uint32
        board_id       (32,) uint32
        pattern        (32,) uint32

    Returns None if all files reached EOF simultaneously.
    """

    records = []

    for reader in readers:
        records.append(reader.read_event())

    # --------------------------------------------------------------
    # EOF handling
    # --------------------------------------------------------------

    eof = [r is None for r in records]

    if all(eof):
        return None

    if any(eof):
        bad_channels = [
            i for i, x in enumerate(eof) if x
        ]

        raise RuntimeError(
            f"Files are not synchronized at event {event_number}. "
            f"EOF encountered in channels {bad_channels}"
        )

    # --------------------------------------------------------------
    # Allocate fixed-size event arrays
    # --------------------------------------------------------------

    waveform = np.empty(
        (N_CHANNELS, N_SAMPLES),
        dtype=np.float32,
    )

    event_counter = np.empty(
        N_CHANNELS,
        dtype=np.uint32,
    )

    trigger_time = np.empty(
        N_CHANNELS,
        dtype=np.uint32,
    )

    board_id = np.empty(
        N_CHANNELS,
        dtype=np.uint32,
    )

    pattern = np.empty(
        N_CHANNELS,
        dtype=np.uint32,
    )

    # --------------------------------------------------------------
    # Fill arrays
    # --------------------------------------------------------------

    for ch, record in enumerate(records):

        waveform[ch] = record["waveform"]

        event_counter[ch] = record["event_counter"]
        trigger_time[ch] = record["trigger_time"]
        board_id[ch] = record["board_id"]
        pattern[ch] = record["pattern"]

    # --------------------------------------------------------------
    # Verify that all channels correspond to the same event
    # --------------------------------------------------------------

    counters = event_counter

    if not np.all(counters == counters[0]):
        raise RuntimeError(
            f"Event counter mismatch at event {event_number}: "
            f"{counters}"
        )

    # Trigger timestamp is group-dependent on x742, so we do
    # NOT require all 32 channels to have the same trigger time.

    return {
        "waveform": waveform,
        "event_counter": event_counter,
        "trigger_time": trigger_time,
        "board_id": board_id,
        "pattern": pattern,
    }


# ----------------------------------------------------------------------
# Unpacker
# ----------------------------------------------------------------------

def unpack(input_dir: Path, output_file: Path, chunk_size: int = 1000):

    readers = open_channels(input_dir)

    try:

        # --------------------------------------------------------------
        # ROOT tree
        #
        # Fixed-size dimensions are explicitly specified here.
        # --------------------------------------------------------------

        tree = None

        event_number = 0

        while True:

            # ----------------------------------------------------------
            # Allocate one chunk
            # ----------------------------------------------------------

            waveforms = np.empty(
                (chunk_size, N_CHANNELS, N_SAMPLES),
                dtype=np.float32,
            )

            event_counters = np.empty(
                (chunk_size, N_CHANNELS),
                dtype=np.uint32,
            )

            trigger_times = np.empty(
                (chunk_size, N_CHANNELS),
                dtype=np.uint32,
            )

            board_ids = np.empty(
                (chunk_size, N_CHANNELS),
                dtype=np.uint32,
            )

            patterns = np.empty(
                (chunk_size, N_CHANNELS),
                dtype=np.uint32,
            )

            n = 0

            # ----------------------------------------------------------
            # Fill chunk
            # ----------------------------------------------------------

            while n < chunk_size:

                record = read_event(
                    readers,
                    event_number,
                )

                if record is None:
                    break

                waveforms[n] = record["waveform"]

                event_counters[n] = record["event_counter"]
                trigger_times[n] = record["trigger_time"]
                board_ids[n] = record["board_id"]
                patterns[n] = record["pattern"]

                n += 1
                event_number += 1

            # ----------------------------------------------------------
            # No more data
            # ----------------------------------------------------------

            if n == 0:
                break

            # ----------------------------------------------------------
            # Trim chunk to actual size
            # ----------------------------------------------------------

            waveforms = waveforms[:n]
            event_counters = event_counters[:n]
            trigger_times = trigger_times[:n]
            board_ids = board_ids[:n]
            patterns = patterns[:n]

            # ----------------------------------------------------------
            # Create ROOT file/tree on first chunk
            # ----------------------------------------------------------

            if tree is None:

                root_file = uproot.recreate(
                    output_file,
                    compression=uproot.ZLIB(4),
                )

                tree = root_file.mktree(
                    "events",
                    {
                        "waveform": np.dtype(
                            (
                                np.float32,
                                (N_CHANNELS, N_SAMPLES),
                            )
                        ),

                        "event_counter": np.dtype(
                            (
                                np.uint32,
                                (N_CHANNELS,),
                            )
                        ),

                        "trigger_time": np.dtype(
                            (
                                np.uint32,
                                (N_CHANNELS,),
                            )
                        ),

                        "board_id": np.dtype(
                            (
                                np.uint32,
                                (N_CHANNELS,),
                            )
                        ),

                        "pattern": np.dtype(
                            (
                                np.uint32,
                                (N_CHANNELS,),
                            )
                        ),
                    },
                )

            # ----------------------------------------------------------
            # Write chunk
            # ----------------------------------------------------------

            tree.extend(
                {
                    "waveform": waveforms,
                    "event_counter": event_counters,
                    "trigger_time": trigger_times,
                    "board_id": board_ids,
                    "pattern": patterns,
                }
            )

            print(
                f"\rEvents unpacked: {event_number}",
                end="",
                flush=True,
            )

        print()

        if tree is None:
            raise RuntimeError(
                "No events found in the input files."
            )

        print(
            f"Finished: {event_number} events"
        )

        print(
            f"Output: {output_file}"
        )

        print(
            f"Waveform shape per event: "
            f"({N_CHANNELS}, {N_SAMPLES})"
        )

    finally:

        for reader in readers:
            reader.close()

        if tree is not None:
            root_file.close()


# ----------------------------------------------------------------------
# Command line interface
# ----------------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description="Unpack CAEN V1742 WaveDump binary files"
    )

    parser.add_argument(
        "input_dir",
        type=Path,
        help="Directory containing wave_0.dat ... wave_31.dat",
    )

    parser.add_argument(
        "output_file",
        type=Path,
        help="Output ROOT file",
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Number of events written per ROOT chunk (default: 1000)",
    )

    args = parser.parse_args()

    unpack(
        input_dir=args.input_dir,
        output_file=args.output_file,
        chunk_size=args.chunk_size,
    )


if __name__ == "__main__":
    main()
