import os
import pretty_midi
import shutil

SOURCE = "data/raw/lakh"
DEST = "data/raw/lakh_filtered"

os.makedirs(DEST, exist_ok=True)

count = 0
total_checked = 0

for root, dirs, files in os.walk(SOURCE):
    for file in files:
        if not file.endswith(".mid"):
            continue

        total_checked += 1
        path = os.path.join(root, file)

        try:
            midi = pretty_midi.PrettyMIDI(path)

            # Keep only multi-track (>=3 instruments)
            if len(midi.instruments) >= 3:

                total_notes = sum(len(inst.notes) for inst in midi.instruments)

                # Avoid huge files
                if 50 < total_notes < 2000:
                    shutil.copy(path, os.path.join(DEST, f"{count}_{file}"))
                    count += 1

        except Exception as e:
            continue

print("Total checked:", total_checked)
print("Filtered kept:", count)